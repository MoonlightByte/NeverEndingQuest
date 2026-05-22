"""Tests for T5-7 (OW-H2): module name collision detection in ModuleBuilder.

Bug: ``ai_driven_module_creation()`` and ``ModuleBuilder.create_module_directories()``
both use ``os.makedirs(..., exist_ok=True)`` against ``modules/<name>/``. If a
module with the same name already exists, the builder happily proceeds and
later overwrites the existing module's ``module_plot.json``, area files,
``party_tracker.json`` and ``_BU.json`` backups -- silently destroying the
prior module.

Fix: at the start of ``create_module_directories()``, detect a pre-built
module at ``output_directory`` by checking for ``module_plot.json``. If
present, pick the next free ``<name>_v2``, ``<name>_v3``, ... slot and
rename ``self.config.module_name`` + ``self.config.output_directory`` to
that new path BEFORE creating any subdirectories. Log a warning.

These tests exercise ``create_module_directories()`` directly with a bare
builder (no API key / generators required). They use ``tmp_path`` as the
``output_directory`` parent so collisions are simulated on disk.
"""

import json
import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators.module_builder import ModuleBuilder


def _bare_builder(module_name: str, modules_root: Path) -> ModuleBuilder:
    """Allocate a ModuleBuilder without running __init__.

    ``__init__`` would instantiate real generators that hit the OpenAI
    client, which we don't need for collision tests.
    """
    builder = object.__new__(ModuleBuilder)
    output_dir = os.path.join(str(modules_root), module_name)
    builder.config = types.SimpleNamespace(
        module_name=module_name,
        output_directory=output_dir,
        verbose=False,
    )
    return builder


def _seed_existing_module(modules_root: Path, module_name: str) -> Path:
    """Create a fake "already built" module dir with a recognisable
    module_plot.json so the collision detector trips.

    Also drops an areas file, party tracker, and a _BU backup so the test
    can later assert none of them were clobbered.
    """
    module_dir = modules_root / module_name
    (module_dir / "areas").mkdir(parents=True, exist_ok=True)

    plot_path = module_dir / "module_plot.json"
    plot_path.write_text(json.dumps({"plotTitle": "ORIGINAL", "marker": module_name}))

    area_path = module_dir / "areas" / "HH001.json"
    area_path.write_text(json.dumps({"areaId": "HH001", "marker": module_name}))

    party_path = module_dir / "party_tracker.json"
    party_path.write_text(json.dumps({"marker": module_name}))

    bu_path = module_dir / "module_plot_BU.json"
    bu_path.write_text(json.dumps({"plotTitle": "ORIGINAL_BU", "marker": module_name}))

    return module_dir


def _assert_original_untouched(module_dir: Path, module_name: str) -> None:
    """Verify the seeded module files survived the second build attempt."""
    plot = json.loads((module_dir / "module_plot.json").read_text())
    assert plot.get("plotTitle") == "ORIGINAL", (
        f"Original module_plot.json was overwritten at {module_dir}!"
    )
    assert plot.get("marker") == module_name

    area = json.loads((module_dir / "areas" / "HH001.json").read_text())
    assert area.get("marker") == module_name, "Original area file was overwritten!"

    party = json.loads((module_dir / "party_tracker.json").read_text())
    assert party.get("marker") == module_name, "Original party_tracker.json was overwritten!"

    bu = json.loads((module_dir / "module_plot_BU.json").read_text())
    assert bu.get("plotTitle") == "ORIGINAL_BU", "Original _BU.json backup was overwritten!"


# ---------------------------------------------------------------------------
# Test 1: single collision -> name becomes <base>_v2
# ---------------------------------------------------------------------------

def test_single_collision_renames_to_v2(tmp_path):
    """Building 'TestModule' when a real 'TestModule' already exists must
    rename the in-progress build to 'TestModule_v2' and leave the original
    files completely untouched.
    """
    modules_root = tmp_path / "modules"
    modules_root.mkdir()

    base = "TestModule"
    original_dir = _seed_existing_module(modules_root, base)

    builder = _bare_builder(base, modules_root)
    builder.create_module_directories()

    # In-progress build must have been renamed to <base>_v2
    assert builder.config.module_name == f"{base}_v2", (
        f"Expected renamed module_name '{base}_v2', got {builder.config.module_name!r}"
    )
    expected_output = os.path.join(str(modules_root), f"{base}_v2")
    assert builder.config.output_directory == expected_output, (
        f"Expected output_directory {expected_output!r}, got "
        f"{builder.config.output_directory!r}"
    )

    # The renamed directory exists with its required subdirs
    renamed_dir = modules_root / f"{base}_v2"
    assert renamed_dir.is_dir()
    for sub in ("characters", "monsters", "encounters", "areas",
                "media", "media/monsters", "media/npcs", "media/environment"):
        assert (renamed_dir / sub).is_dir(), (
            f"Expected subdir {sub} under renamed module dir"
        )

    # Original module is intact
    _assert_original_untouched(original_dir, base)


# ---------------------------------------------------------------------------
# Test 2: triple collision -> name becomes <base>_v3
# ---------------------------------------------------------------------------

def test_triple_collision_renames_to_v3(tmp_path):
    """If 'TestModule' AND 'TestModule_v2' both already exist (real builds),
    the next build of 'TestModule' must land at 'TestModule_v3'.
    """
    modules_root = tmp_path / "modules"
    modules_root.mkdir()

    base = "TestModule"
    original_dir = _seed_existing_module(modules_root, base)
    v2_dir = _seed_existing_module(modules_root, f"{base}_v2")

    builder = _bare_builder(base, modules_root)
    builder.create_module_directories()

    assert builder.config.module_name == f"{base}_v3", (
        f"Expected renamed module_name '{base}_v3', got {builder.config.module_name!r}"
    )
    expected_output = os.path.join(str(modules_root), f"{base}_v3")
    assert builder.config.output_directory == expected_output

    renamed_dir = modules_root / f"{base}_v3"
    assert renamed_dir.is_dir()
    assert (renamed_dir / "areas").is_dir()

    # Both prior versions untouched
    _assert_original_untouched(original_dir, base)
    _assert_original_untouched(v2_dir, f"{base}_v2")


# ---------------------------------------------------------------------------
# Test 3: regression -- fresh build keeps the requested name
# ---------------------------------------------------------------------------

def test_fresh_build_keeps_original_name(tmp_path):
    """If no module exists at the target path, the build proceeds with the
    requested name -- no spurious _v2 rename.
    """
    modules_root = tmp_path / "modules"
    modules_root.mkdir()

    base = "FreshModule"
    builder = _bare_builder(base, modules_root)
    builder.create_module_directories()

    assert builder.config.module_name == base, (
        f"Fresh build must keep requested name; got {builder.config.module_name!r}"
    )
    expected_output = os.path.join(str(modules_root), base)
    assert builder.config.output_directory == expected_output

    fresh_dir = modules_root / base
    assert fresh_dir.is_dir()
    for sub in ("characters", "monsters", "encounters", "areas",
                "media", "media/monsters", "media/npcs", "media/environment"):
        assert (fresh_dir / sub).is_dir()
        gitkeep = fresh_dir / sub / ".gitkeep"
        assert gitkeep.is_file(), f"Expected .gitkeep in {sub}"

    # No _v2 sibling was spuriously created
    assert not (modules_root / f"{base}_v2").exists()


# ---------------------------------------------------------------------------
# Test 4: pre-existing empty dir is NOT considered a collision
# ---------------------------------------------------------------------------

def test_empty_target_dir_is_not_a_collision(tmp_path):
    """An empty pre-existing target directory (e.g., one freshly created by
    ModuleBuilder.__init__ at line 88, or by an aborted prior run) must NOT
    trigger the rename. Only a directory containing module_plot.json
    (signalling a completed build) should trigger collision logic.
    """
    modules_root = tmp_path / "modules"
    modules_root.mkdir()

    base = "EmptyDirModule"
    (modules_root / base).mkdir()  # Empty dir -- mirrors __init__ creating output_directory

    builder = _bare_builder(base, modules_root)
    builder.create_module_directories()

    assert builder.config.module_name == base, (
        "Empty pre-existing dir must not trigger collision rename"
    )
    assert not (modules_root / f"{base}_v2").exists()
