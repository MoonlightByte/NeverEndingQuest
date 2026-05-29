"""
Tests for VAL-H5: module_debugger.load_module_files() must include the
`areas/` subdirectory when globbing module JSON files.

Per CLAUDE.md's Module Structure documentation, the canonical layout is:

    modules/[module_name]/
    +-- areas/                  # Location JSON files (HH001.json, G001.json)
    +-- [module]_module.json
    +-- module_plot.json
    +-- ...

`module_debugger.py:111` previously globbed ONLY `self.module_path/*.json`
(root level). Area files inside `areas/` were never loaded, so
`validate_references()` built an empty `location_ids` set and every plot
location reference was logged as a false-positive "Plot references
non-existent location" error.

These tests cover:
  1. Positive: module with `areas/A.json` (valid area) + `module_plot.json`
     referencing that area's location -> both files load, 0 plot errors.
  2. Negative: areas/ file's locations are unknown to plot -> plot
     errors are correctly raised (sanity check that the validation is
     actually running, not just always-pass).
  3. Regression: root-level files still load normally and their dict
     keys are preserved (no name collisions, no replacements).
  4. Collision-safety: a root-level `X.json` and `areas/X.json` must
     both load, distinguished by a path-aware key.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from module_debugger import ModuleDebugger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_area_payload(area_id: str, location_ids: list) -> dict:
    """Minimal valid area file shape. Each location_id becomes a real
    location entry with a name so validate_references can build both
    location_ids and location_names sets without crashing."""
    locations = []
    for loc_id in location_ids:
        locations.append({
            "locationId": loc_id,
            "name": f"Loc {loc_id}",
            "connectivity": [],
            "areaConnectivity": [],
            "areaConnectivityId": [],
        })
    return {
        "areaId": area_id,
        "areaName": f"Area {area_id}",
        "areaType": "wilderness",
        "map": f"map_{area_id}.json",
        "locations": locations,
    }


def _make_plot_payload(location_refs: list) -> dict:
    """Minimal plot file with one plotPoint per location_ref."""
    return {
        "plotPoints": [
            {"id": f"pp{i}", "location": loc}
            for i, loc in enumerate(location_refs)
        ]
    }


def _plot_location_errors(dbg: ModuleDebugger) -> list:
    """Return errors that came from validate_references' plot-location
    check ('Plot references non-existent location ...')."""
    return [e for e in dbg.errors if "Plot references non-existent location" in e]


# ---------------------------------------------------------------------------
# Test 1: Positive -- area in areas/ subdir + plot file referencing its
# location id -> load_module_files loads both, validate_references
# reports zero plot-location errors.
# ---------------------------------------------------------------------------

def test_areas_subdirectory_files_are_loaded_and_resolve_plot_refs(tmp_path):
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    # Area file at <module>/areas/A.json with location A01.
    _write_json(
        module_dir / "areas" / "A.json",
        _make_area_payload("A001", ["A01", "A02"]),
    )

    # Plot file at module root referencing A01 (which lives inside
    # areas/A.json -- only resolvable if the areas/ subdir is loaded).
    _write_json(
        module_dir / "plot_A001.json",
        _make_plot_payload(["A01"]),
    )

    dbg = ModuleDebugger()
    dbg.module_path = str(module_dir)
    assert dbg.load_module_files(), "load_module_files() returned False"

    # Sanity: both files must be present in module_data.
    area_keys = [k for k, v in dbg.module_data.items()
                 if isinstance(v, dict) and v.get("areaId") == "A001"]
    assert len(area_keys) == 1, (
        f"Expected exactly one area file loaded from areas/, got "
        f"{len(area_keys)}: keys={list(dbg.module_data.keys())}"
    )
    assert "plot_A001.json" in dbg.module_data, (
        f"Root-level plot file not loaded. Keys: {list(dbg.module_data.keys())}"
    )

    # Validate references: plot's A01 must resolve to the area's A01.
    dbg.validate_references()
    errs = _plot_location_errors(dbg)
    assert errs == [], (
        "Expected no plot-location errors when areas/ file is loaded, "
        f"got: {errs}"
    )


# ---------------------------------------------------------------------------
# Test 2: Negative -- plot references a location id NOT present in the
# loaded area file. The validation must still flag this even after the
# subdir is included (i.e. we didn't accidentally always-pass).
# ---------------------------------------------------------------------------

def test_plot_unknown_location_still_flagged_after_areas_load(tmp_path):
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    _write_json(
        module_dir / "areas" / "A.json",
        _make_area_payload("A001", ["A01"]),
    )
    # Plot references Z99 which does not exist in area A001.
    _write_json(
        module_dir / "plot_A001.json",
        _make_plot_payload(["Z99"]),
    )

    dbg = ModuleDebugger()
    dbg.module_path = str(module_dir)
    assert dbg.load_module_files()
    dbg.validate_references()

    errs = _plot_location_errors(dbg)
    assert len(errs) == 1, (
        f"Expected exactly 1 plot-location error for unknown id Z99, "
        f"got {len(errs)}: {errs}"
    )
    assert "Z99" in errs[0], (
        f"Error should mention the offending location 'Z99', got: {errs[0]}"
    )


# ---------------------------------------------------------------------------
# Test 3: Regression -- root-level files still load normally, with their
# bare filename as the dict key (no surprise re-keying).
# ---------------------------------------------------------------------------

def test_root_level_files_still_load_with_bare_filename_keys(tmp_path):
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    # Root-only files (no areas/ subdir at all).
    _write_json(
        module_dir / "test_module.json",
        {"moduleName": "Test Module", "moduleId": "TM"},
    )
    _write_json(
        module_dir / "party_tracker.json",
        {"partyMembers": [], "partyNPCs": []},
    )

    dbg = ModuleDebugger()
    dbg.module_path = str(module_dir)
    assert dbg.load_module_files()

    assert "test_module.json" in dbg.module_data, (
        f"Root-level test_module.json not present under bare key. "
        f"Keys: {list(dbg.module_data.keys())}"
    )
    assert "party_tracker.json" in dbg.module_data, (
        f"Root-level party_tracker.json not present under bare key. "
        f"Keys: {list(dbg.module_data.keys())}"
    )


# ---------------------------------------------------------------------------
# Test 4: Collision safety -- root <module>/X.json and
# <module>/areas/X.json must BOTH end up in module_data, distinguished
# by a path-aware key so neither overwrites the other.
# ---------------------------------------------------------------------------

def test_root_and_areas_with_same_filename_do_not_collide(tmp_path):
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    # Same bare filename in two locations with deliberately different
    # contents so we can tell them apart.
    _write_json(
        module_dir / "X.json",
        {"source": "root", "data": "root-level"},
    )
    _write_json(
        module_dir / "areas" / "X.json",
        _make_area_payload("X001", ["X01"]),
    )

    dbg = ModuleDebugger()
    dbg.module_path = str(module_dir)
    assert dbg.load_module_files()

    # Both payloads must be findable in module_data. We don't pin the
    # exact key scheme (e.g. "areas/X.json" vs "X.json" alongside an
    # "areas/X.json"); we only assert both contents are present.
    values = list(dbg.module_data.values())
    root_present = any(
        isinstance(v, dict) and v.get("source") == "root" for v in values
    )
    area_present = any(
        isinstance(v, dict) and v.get("areaId") == "X001" for v in values
    )
    assert root_present, (
        f"Root-level X.json contents missing after load. "
        f"Loaded entries: {dbg.module_data}"
    )
    assert area_present, (
        f"areas/X.json contents missing after load. "
        f"Loaded entries: {dbg.module_data}"
    )
