"""Tests for T3-3 (INT-H7): module_stitcher uses atomic safe_write_json
for the world_registry.json save inside integrate_module (line 584).

The legacy code path at core/generators/module_stitcher.py:585 was:

    safe_json_dump(self.world_registry, self.world_registry_file)

`safe_json_dump` is a thin wrapper around `json.dump()` -- it is NOT
atomic. An interruption mid-write corrupts the registry, which is the
single source of truth for inter-module world state.

T3-3 replaces ONLY that one callsite with:

    safe_write_json(self.world_registry_file, self.world_registry)

The other 7 `safe_json_dump` callsites in this file are deferred to
T3-3b and must remain unchanged in this commit.

These tests verify:
  1. The integrate_module success path calls safe_write_json with
     (filepath, data) order on the world_registry write.
  2. That same path does NOT use safe_json_dump for the registry save.
  3. The import `from utils.file_operations import safe_write_json`
     is present in module_stitcher.py so the call resolves at runtime.
  4. The other 7 safe_json_dump callsites (T3-3b scope) still exist
     and are untouched -- this commit must not regress them.
"""

import os
import sys
import types
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


def _patched_integrate_module_to_success_point(stitcher, module_name, module_data):
    """Drive integrate_module through the success path without hitting the
    real backup, analyze, conflict resolution, or safety validation steps.

    Returns the integrate_module return value.
    """
    with mock.patch.object(stitcher, "_create_module_backup", return_value=""), \
         mock.patch.object(stitcher, "analyze_module", return_value=module_data), \
         mock.patch.object(stitcher, "_resolve_id_conflicts", return_value=0), \
         mock.patch.object(stitcher, "_validate_module_safety", return_value=True):
        return stitcher.integrate_module(module_name)


# ---------------------------------------------------------------------------
# Import presence -- belt-and-suspenders
# ---------------------------------------------------------------------------

def test_safe_write_json_imported_in_module_stitcher():
    """safe_write_json must be imported into module_stitcher's namespace
    so the line 585 call resolves at runtime without NameError."""
    assert hasattr(ms_module, "safe_write_json"), (
        "module_stitcher.py does not import safe_write_json -- the T3-3 fix "
        "at line 585 will fail at runtime with NameError. Add "
        "`from utils.file_operations import safe_write_json` to the imports."
    )


# ---------------------------------------------------------------------------
# Behavior: integrate_module success path calls safe_write_json
# ---------------------------------------------------------------------------

def test_integrate_module_calls_safe_write_json_with_correct_arg_order(tmp_path):
    """The success path of integrate_module must call safe_write_json with
    (filepath, data) order on the world_registry write. Reversed args
    would pass a dict as the filepath -- an immediate runtime error in
    AtomicFileWriter.write_json."""
    stitcher = _bare_stitcher(tmp_path)
    module_name = "TestModule"
    module_data = {
        "themes": ["mystery"],
        "plotObjective": "Find the artifact",
        "levelRange": {"min": 1, "max": 3},
        "areas": {
            "AA001": {"areaId": "AA001", "areaName": "Entry"},
        },
        "travelNarration": {"travelNarration": "You travel forth."},
    }

    with mock.patch.object(ms_module, "safe_write_json", return_value=True) as m_atomic:
        result = _patched_integrate_module_to_success_point(
            stitcher, module_name, module_data
        )

    assert result is True, "integrate_module should return True on success path"
    assert m_atomic.call_count >= 1, (
        "safe_write_json was never called -- the line 585 fix is not in place. "
        "Code is still using safe_json_dump for the registry save."
    )

    # Find the registry save call specifically (filepath ends with world_registry.json).
    registry_calls = [
        call for call in m_atomic.call_args_list
        if call.args and isinstance(call.args[0], str)
           and call.args[0].endswith("world_registry.json")
    ]
    assert len(registry_calls) == 1, (
        f"Expected exactly one safe_write_json call for world_registry.json, "
        f"got {len(registry_calls)}: {m_atomic.call_args_list}"
    )

    args, kwargs = registry_calls[0]
    # Argument order: (filepath, data)
    assert args[0] == stitcher.world_registry_file, (
        f"First arg must be the filepath str, got {args[0]!r}"
    )
    assert args[1] is stitcher.world_registry, (
        "Second arg must be the world_registry dict (identity check)."
    )
    assert isinstance(args[0], str), "filepath arg must be a str"
    assert isinstance(args[1], dict), "data arg must be a dict, not a path"


def test_integrate_module_does_not_use_safe_json_dump_for_registry(tmp_path):
    """The line 585 callsite must no longer use the non-atomic
    safe_json_dump. This test mocks BOTH functions and asserts the
    registry write went through safe_write_json, not safe_json_dump."""
    stitcher = _bare_stitcher(tmp_path)
    module_name = "TestModule"
    module_data = {
        "themes": [],
        "plotObjective": "",
        "levelRange": {"min": 1, "max": 1},
        "areas": {"AA001": {"areaId": "AA001"}},
        "travelNarration": {},
    }

    with mock.patch.object(ms_module, "safe_write_json", return_value=True) as m_atomic, \
         mock.patch.object(ms_module, "safe_json_dump", return_value=None) as m_legacy:
        _patched_integrate_module_to_success_point(
            stitcher, module_name, module_data
        )

    # Did safe_write_json get the registry write?
    atomic_registry_calls = [
        call for call in m_atomic.call_args_list
        if call.args and isinstance(call.args[0], str)
           and call.args[0].endswith("world_registry.json")
    ]
    assert len(atomic_registry_calls) == 1, (
        "world_registry.json must be saved via safe_write_json (atomic). "
        f"safe_write_json calls: {m_atomic.call_args_list}"
    )

    # Did safe_json_dump get the registry write? It must NOT.
    legacy_registry_calls = [
        call for call in m_legacy.call_args_list
        # safe_json_dump signature is (data, filepath) -- check arg[1].
        if len(call.args) >= 2 and isinstance(call.args[1], str)
           and call.args[1].endswith("world_registry.json")
    ]
    assert legacy_registry_calls == [], (
        "world_registry.json was still saved via the non-atomic safe_json_dump. "
        f"Offending calls: {legacy_registry_calls}"
    )


# ---------------------------------------------------------------------------
# Scope guard: T3-3b sites untouched
# ---------------------------------------------------------------------------

def test_t3_3b_safe_json_dump_callsites_still_present():
    """T3-3 fixes ONLY the line 584/585 callsite. The other 7
    safe_json_dump callsites (lines 139, 156, 705, 770, 869, 962, 984)
    are deferred to T3-3b and must remain unchanged in this commit.

    This guards against an over-eager rewrite that accidentally migrates
    all 8 sites at once.
    """
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "generators"
        / "module_stitcher.py"
    )
    text = src_path.read_text(encoding="utf-8")
    # Count call sites: lines containing "safe_json_dump(" but NOT the import line.
    call_lines = [
        (i + 1, line)
        for i, line in enumerate(text.splitlines())
        if "safe_json_dump(" in line and "import" not in line
    ]
    # T3-3 removes 1 (line 585) of the 8 original callsites, leaving 7.
    # The remaining 7 are T3-3b scope: lines 139 (__init__), 156
    # (_load_world_registry), 705, 770, 869, 962, 984. The line 139 and
    # 156 sites ALSO save world_registry but are explicitly deferred --
    # they handle creation/load-default, not integration.
    assert len(call_lines) == 7, (
        f"Expected 7 remaining safe_json_dump callsites after T3-3 (T3-3b scope), "
        f"got {len(call_lines)}. Either T3-3 was not applied (still 8) or T3-3b "
        f"was applied early (less than 7). Lines found: "
        + ", ".join(f"L{ln}" for ln, _ in call_lines)
    )

    # Belt-and-suspenders: the line numbers of the remaining 7 sites must
    # NOT include 585 (or whatever new line the registry save in
    # integrate_module now occupies). Easier: just confirm 585 is gone.
    line_numbers = [ln for ln, _ in call_lines]
    assert 585 not in line_numbers, (
        f"Line 585 still uses safe_json_dump -- T3-3 was not applied. "
        f"Lines with safe_json_dump: {line_numbers}"
    )
