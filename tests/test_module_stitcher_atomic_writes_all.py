"""Tests for T3-3b (XS-1 expansion): extend atomic writes to the remaining
7 safe_json_dump callsites in core/generators/module_stitcher.py.

T3-3 migrated only the integrate_module registry save (line ~585). The
other 7 callsites all wrote game state non-atomically -- any mid-write
interruption could corrupt the world registry, party tracker, or area
files. T3-3b migrates each remaining site to safe_write_json with
(filepath, data) argument order.

The 7 sites (line numbers approximate, verify via grep):
  1. ModuleStitcher.__init__ migration write of self.world_registry
     (after deleting the legacy 'connections' key).
  2. _load_world_registry's default-registry creation write.
  3. ID rename inside _resolve_id_conflicts: per-area save under new ID.
  4. _update_party_tracker_for_area_change: party tracker save when the
     currentLocationId belongs to a renamed area.
  5. _resolve_id_conflicts prefix application: save updated area file.
  6. _update_location_references: write back per-file ID-remapped data.
  7. _update_location_references: party tracker save when the active
     module's currentLocationId was remapped.

Additionally, T3-3b removes the dormant `self.client = OpenAI(...)`
attribute and the now-unused `from openai import OpenAI` import. This
file also verifies those removals.

Each per-callsite test drives the target method with the minimum fixture
needed to reach the write, mocks safe_write_json, and asserts the call
arguments are (filepath, data) in that order. Reversed-argument bugs
would be caught immediately because filepath must be a str and data
must be a dict/list.
"""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import module_stitcher as ms_module
from core.generators.module_stitcher import ModuleStitcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bare_stitcher(tmp_path) -> ModuleStitcher:
    """Allocate a ModuleStitcher without running __init__ (which constructs
    a real OpenAI client and touches the filesystem)."""
    stitcher = object.__new__(ModuleStitcher)
    stitcher.modules_dir = str(tmp_path / "modules")
    stitcher.root_dir = str(tmp_path)
    stitcher.world_registry_file = str(tmp_path / "modules" / "world_registry.json")
    stitcher.party_tracker_file = str(tmp_path / "party_tracker.json")
    stitcher.world_registry = {
        "modules": {},
        "areas": {},
        "lastUpdated": "2026-05-22T00:00:00",
    }
    return stitcher


def _assert_filepath_data_order(call_args, expected_filepath_endswith=None,
                                 expected_data_type=dict):
    """Assert a safe_write_json call uses (filepath, data) order."""
    args = call_args.args
    assert len(args) >= 2, (
        f"safe_write_json must be called with at least 2 positional args, "
        f"got {len(args)}: {args!r}"
    )
    filepath, data = args[0], args[1]
    assert isinstance(filepath, str), (
        f"First arg must be a str filepath, got {type(filepath).__name__}: "
        f"{filepath!r}. Args may be reversed (data, filepath)."
    )
    assert isinstance(data, expected_data_type), (
        f"Second arg must be {expected_data_type.__name__}, got "
        f"{type(data).__name__}: {data!r}. Args may be reversed."
    )
    if expected_filepath_endswith is not None:
        assert filepath.endswith(expected_filepath_endswith), (
            f"Expected filepath to end with {expected_filepath_endswith!r}, "
            f"got {filepath!r}"
        )


# ---------------------------------------------------------------------------
# Site 1: __init__ legacy-connections migration write
# ---------------------------------------------------------------------------

def test_site1_init_connections_migration_uses_atomic_write(tmp_path, monkeypatch):
    """__init__ deletes legacy 'connections' key and writes the registry.
    Must use safe_write_json(filepath, data)."""
    # Build a fake registry file containing the legacy 'connections' key
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    registry_path = modules_dir / "world_registry.json"
    import json as _json
    registry_path.write_text(_json.dumps({
        "modules": {},
        "areas": {},
        "connections": {"old": "data"},
    }))

    # Patch os.path.abspath so ModuleStitcher uses tmp_path
    monkeypatch.chdir(tmp_path)

    with mock.patch.object(ms_module, "safe_write_json", return_value=True) as m_atomic:
        ModuleStitcher()

    # Find the migration write (registry has isolatedModules=True after migration).
    migration_calls = [
        c for c in m_atomic.call_args_list
        if c.args and isinstance(c.args[0], str)
           and c.args[0].endswith("world_registry.json")
           and isinstance(c.args[1], dict)
           and c.args[1].get("isolatedModules") is True
           and "connections" not in c.args[1]
    ]
    assert len(migration_calls) >= 1, (
        f"__init__ migration did not call safe_write_json with the post-"
        f"migration registry. Calls: {m_atomic.call_args_list}"
    )
    _assert_filepath_data_order(
        migration_calls[0],
        expected_filepath_endswith="world_registry.json",
    )


# ---------------------------------------------------------------------------
# Site 2: _load_world_registry default-registry creation write
# ---------------------------------------------------------------------------

def test_site2_load_world_registry_default_creation_uses_atomic_write(tmp_path):
    """When world_registry.json does NOT exist, _load_world_registry creates
    a default and writes it. Must use safe_write_json(filepath, data)."""
    stitcher = _bare_stitcher(tmp_path)
    # The registry file does NOT exist on disk -- triggers the default path.
    assert not os.path.exists(stitcher.world_registry_file)

    with mock.patch.object(ms_module, "safe_write_json", return_value=True) as m_atomic:
        result = stitcher._load_world_registry()

    # safe_write_json should be called exactly once with the default registry.
    registry_calls = [
        c for c in m_atomic.call_args_list
        if c.args and isinstance(c.args[0], str)
           and c.args[0].endswith("world_registry.json")
    ]
    assert len(registry_calls) == 1, (
        f"Expected one safe_write_json call for default registry, got "
        f"{len(registry_calls)}: {m_atomic.call_args_list}"
    )
    _assert_filepath_data_order(
        registry_calls[0],
        expected_filepath_endswith="world_registry.json",
    )
    # The returned default registry must match what was written.
    assert result is registry_calls[0].args[1], (
        "Function should return the same default-registry dict it wrote."
    )
    assert result["isolatedModules"] is True
    assert result["worldName"] == "Fantasy Adventure World"


# ---------------------------------------------------------------------------
# Site 3: per-area rename write inside _resolve_id_conflicts
#         (the 'new_area_file' save after location ID remap)
# ---------------------------------------------------------------------------

def test_site3_area_rename_write_uses_atomic_write():
    """The per-area save after renaming location IDs (line ~706) must use
    safe_write_json(new_area_file, area_data).

    This site is inside a nested loop of _resolve_id_conflicts. Rather than
    drive the whole method, we verify via a source-text scan that the call
    immediately following the 'new_area_file = os.path.join(...)'
    assignment uses safe_write_json with the right arg order.
    """
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core" / "generators" / "module_stitcher.py"
    )
    text = src_path.read_text(encoding="utf-8")

    # Locate the line with 'new_area_file = os.path.join'.
    lines = text.splitlines()
    target_idx = None
    for i, line in enumerate(lines):
        if "new_area_file = os.path.join" in line:
            target_idx = i
            break
    assert target_idx is not None, (
        "Could not find 'new_area_file = os.path.join' assignment in "
        "module_stitcher.py -- the test fixture is stale."
    )

    # The next non-blank line should be the safe_write_json call.
    follow_up = ""
    for j in range(target_idx + 1, min(target_idx + 5, len(lines))):
        if lines[j].strip():
            follow_up = lines[j].strip()
            break

    assert follow_up.startswith("safe_write_json("), (
        f"Expected safe_write_json call after new_area_file assignment, "
        f"got: {follow_up!r}"
    )
    assert "safe_write_json(new_area_file, area_data)" in follow_up, (
        f"Expected safe_write_json(new_area_file, area_data), got: "
        f"{follow_up!r}. Argument order may be reversed."
    )


# ---------------------------------------------------------------------------
# Site 4: party tracker save in _update_party_tracker_for_area_change
# ---------------------------------------------------------------------------

def test_site4_party_tracker_area_change_uses_atomic_write(tmp_path):
    """When an area ID is renamed and the party is currently inside it,
    _update_party_tracker_location_ids rewrites party_tracker.json.
    Must use safe_write_json(party_tracker_path, party_tracker)."""
    stitcher = _bare_stitcher(tmp_path)
    # Stage a party_tracker.json on disk pointing at the renamed location.
    party_tracker_path = stitcher.party_tracker_file
    Path(party_tracker_path).parent.mkdir(parents=True, exist_ok=True)
    import json as _json
    Path(party_tracker_path).write_text(_json.dumps({
        "module": "TestModule",
        "worldConditions": {"currentLocationId": "OLD001"},
    }))

    location_id_mapping = {"OLD001": "NEW001"}
    # module_path basename must match party_tracker's 'module' field.
    module_path = str(tmp_path / "modules" / "TestModule")

    with mock.patch.object(ms_module, "safe_write_json", return_value=True) as m_atomic:
        result = stitcher._update_party_tracker_location_ids(
            location_id_mapping, module_path
        )

    assert result is True
    party_calls = [
        c for c in m_atomic.call_args_list
        if c.args and isinstance(c.args[0], str)
           and c.args[0].endswith("party_tracker.json")
    ]
    assert len(party_calls) == 1, (
        f"Expected one safe_write_json call for party_tracker.json, got "
        f"{len(party_calls)}: {m_atomic.call_args_list}"
    )
    _assert_filepath_data_order(
        party_calls[0],
        expected_filepath_endswith="party_tracker.json",
    )
    written_data = party_calls[0].args[1]
    assert written_data["worldConditions"]["currentLocationId"] == "NEW001"


# ---------------------------------------------------------------------------
# Site 5: _resolve_id_conflicts prefix application
#         (write updated area data after prefix update)
# ---------------------------------------------------------------------------

def test_site5_prefix_update_area_write_uses_atomic_write():
    """The area-file save after applying a new prefix (line ~870) must use
    safe_write_json(area_file_path, updated_area_data).

    Driving this path end-to-end requires constructing the full module
    layout and triggering a conflict resolution. We verify via source-text
    scan that the relevant line uses the right arg order.
    """
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core" / "generators" / "module_stitcher.py"
    )
    text = src_path.read_text(encoding="utf-8")
    assert "safe_write_json(area_file_path, updated_area_data)" in text, (
        "Could not find safe_write_json(area_file_path, updated_area_data) "
        "in module_stitcher.py -- T3-3b site 5 may be missing or args reversed."
    )

    # Belt-and-suspenders: ensure no reversed form exists.
    assert "safe_write_json(updated_area_data, area_file_path)" not in text, (
        "Reversed-argument call found: safe_write_json(updated_area_data, "
        "area_file_path). Should be (area_file_path, updated_area_data)."
    )


# ---------------------------------------------------------------------------
# Site 6: _update_location_references per-file write
# ---------------------------------------------------------------------------

def test_site6_location_references_per_file_write_uses_atomic_write():
    """The per-file recursive-update save (line ~963) must use
    safe_write_json(file_path, updated_data).
    """
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core" / "generators" / "module_stitcher.py"
    )
    text = src_path.read_text(encoding="utf-8")
    assert "safe_write_json(file_path, updated_data)" in text, (
        "Could not find safe_write_json(file_path, updated_data) in "
        "module_stitcher.py -- T3-3b site 6 may be missing or args reversed."
    )
    assert "safe_write_json(updated_data, file_path)" not in text, (
        "Reversed-argument call found: safe_write_json(updated_data, "
        "file_path). Should be (file_path, updated_data)."
    )


# ---------------------------------------------------------------------------
# Site 7: _update_location_references party_tracker save
# ---------------------------------------------------------------------------

def test_site7_location_references_party_tracker_write_uses_atomic_write():
    """The party_tracker save in _update_location_references (line ~985)
    must use safe_write_json(party_tracker_path, party_tracker).

    Two distinct callsites write party_tracker -- this one and site 4.
    Both must use the correct arg order.
    """
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core" / "generators" / "module_stitcher.py"
    )
    text = src_path.read_text(encoding="utf-8")
    # Count occurrences of the correct form -- expect at least 2 in source
    # (sites 4 and 7 both write party_tracker_path, party_tracker).
    correct_form_count = text.count(
        "safe_write_json(party_tracker_path, party_tracker)"
    )
    assert correct_form_count >= 2, (
        f"Expected at least 2 occurrences of "
        f"safe_write_json(party_tracker_path, party_tracker) "
        f"(sites 4 and 7), got {correct_form_count}."
    )
    # And NO reversed forms.
    assert "safe_write_json(party_tracker, party_tracker_path)" not in text, (
        "Reversed-argument call found: safe_write_json(party_tracker, "
        "party_tracker_path). Should be (party_tracker_path, party_tracker)."
    )


# ---------------------------------------------------------------------------
# Bonus: source-scan assertions (post-T3-3b state)
# ---------------------------------------------------------------------------

def test_safe_json_dump_no_longer_imported():
    """T3-3b removes the last use of safe_json_dump. The import should
    NOT include safe_json_dump anymore (safe_json_load stays).
    """
    # Direct attribute check on the imported module namespace.
    assert not hasattr(ms_module, "safe_json_dump"), (
        "safe_json_dump is still imported into module_stitcher's namespace. "
        "After T3-3b it should be removed from the encoding_utils import."
    )
    # safe_json_load must still be present -- it's used by load paths.
    assert hasattr(ms_module, "safe_json_load"), (
        "safe_json_load is still required by module_stitcher load paths "
        "but is missing from the namespace."
    )


def test_safe_json_dump_callsites_gone_from_source():
    """No remaining safe_json_dump( call expressions in module_stitcher.py."""
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core" / "generators" / "module_stitcher.py"
    )
    text = src_path.read_text(encoding="utf-8")
    call_lines = [
        (i + 1, line)
        for i, line in enumerate(text.splitlines())
        if "safe_json_dump(" in line and "import" not in line
    ]
    assert call_lines == [], (
        f"Found leftover safe_json_dump( callsites after T3-3b: "
        + ", ".join(f"L{ln}: {line.strip()!r}" for ln, line in call_lines)
    )


def test_openai_import_removed():
    """T3-3b removes the dormant OpenAI client. The 'from openai import OpenAI'
    import line must be gone, and 'OpenAI(' must not appear in the file."""
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core" / "generators" / "module_stitcher.py"
    )
    text = src_path.read_text(encoding="utf-8")
    assert "from openai import OpenAI" not in text, (
        "from openai import OpenAI is still present -- dormant client was "
        "not fully removed."
    )
    assert "OpenAI(" not in text, (
        "OpenAI(...) construction is still present -- the dormant client "
        "was not removed."
    )
    # And not in the namespace.
    assert not hasattr(ms_module, "OpenAI"), (
        "OpenAI is still bound in the module_stitcher namespace."
    )


def test_self_client_attribute_removed():
    """The dormant 'self.client = OpenAI(...)' assignment is gone from
    __init__. No method ever read self.client -- it was dead state."""
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core" / "generators" / "module_stitcher.py"
    )
    text = src_path.read_text(encoding="utf-8")
    assert "self.client" not in text, (
        "self.client is still referenced in module_stitcher.py -- the "
        "dormant attribute was not fully removed."
    )
