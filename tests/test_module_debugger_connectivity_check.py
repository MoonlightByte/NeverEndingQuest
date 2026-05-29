"""
Tests for VAL-H1 (corrected): module_debugger.validate_references() must
compare location `connectivity` entries against location IDs, not names.

`connectivity` holds locationId strings, NOT free-text names. The
generator (location_generator.py), the ID remapper (module_generator.py)
and the runtime pathfinder (location_path_finder.py) all treat connectivity
entries as IDs, and real module data is overwhelmingly ID-based (the audit
measured ~190 IDs vs 1 name across production area files). An earlier VAL-H1
attempt switched the comparison to location *names* based on a stale schema
description; that turned a correct check into a false-positive generator
(191 spurious errors on real modules) and is reverted here. The schema
description was corrected to "IDs of other locations".

These tests cover:
  1. Positive: connectivity uses real location IDs -> no error.
  2. Negative: connectivity references an unknown ID -> 1 error.
  3. Regression: intra-area connectivity (IDs) and cross-area
     areaConnectivityId (IDs) coexist with no false positives.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from module_debugger import ModuleDebugger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_area(area_id: str, locations: list) -> dict:
    """Minimal area payload with the fields validate_references reads."""
    return {
        "areaId": area_id,
        "areaName": f"Area {area_id}",
        "locations": locations,
    }


def _location(loc_id: str, name: str, connectivity=None, area_conn_ids=None) -> dict:
    loc = {
        "locationId": loc_id,
        "name": name,
        "connectivity": connectivity or [],
        "areaConnectivity": [],
        "areaConnectivityId": area_conn_ids or [],
    }
    return loc


def _run_validate(module_data: dict) -> ModuleDebugger:
    """Build a ModuleDebugger with the given module_data dict already
    populated and call validate_references() on it. Returns the
    debugger so tests can inspect errors/warnings."""
    dbg = ModuleDebugger()
    dbg.module_data = module_data
    dbg.validate_references()
    return dbg


def _connectivity_errors(dbg: ModuleDebugger) -> list:
    """Return errors that came from the connectivity check
    ('Invalid connection ... in location ... of ...')."""
    return [e for e in dbg.errors if "Invalid connection" in e]


# ---------------------------------------------------------------------------
# Test 1: positive case -- connectivity uses real location IDs.
#
# Correct behavior: comparison is against location_ids; "A02" / "A01"
# (real IDs in the area) match and no error is recorded.
# ---------------------------------------------------------------------------

def test_connectivity_ids_resolve_against_location_ids():
    loc_a = _location(
        "A01",
        "Forest Path",
        connectivity=["A02"],
    )
    loc_b = _location(
        "A02",
        "Cave Entrance",
        connectivity=["A01"],
    )
    module_data = {
        "AA001.json": _make_area("AA001", [loc_a, loc_b]),
    }

    dbg = _run_validate(module_data)

    assert _connectivity_errors(dbg) == [], (
        "Expected no connectivity errors when connectivity references "
        "valid location IDs, got: " + repr(_connectivity_errors(dbg))
    )


# ---------------------------------------------------------------------------
# Test 2: negative case -- connectivity references an unknown ID.
#
# A name where an ID is expected (the real-data anomaly class, e.g.
# "Black Lantern Hearth") must be flagged as exactly one Invalid
# connection error.
# ---------------------------------------------------------------------------

def test_connectivity_unknown_id_is_flagged():
    loc_a = _location(
        "A01",
        "Forest Path",
        connectivity=["Black Lantern Hearth"],  # a name, not a valid ID
    )
    loc_b = _location(
        "A02",
        "Cave Entrance",
        connectivity=[],
    )
    module_data = {
        "AA001.json": _make_area("AA001", [loc_a, loc_b]),
    }

    dbg = _run_validate(module_data)

    errs = _connectivity_errors(dbg)
    assert len(errs) == 1, (
        f"Expected exactly 1 connectivity error for unknown ID, "
        f"got {len(errs)}: {errs}"
    )
    assert "Black Lantern Hearth" in errs[0], (
        f"Error should mention the offending entry 'Black Lantern Hearth', "
        f"got: {errs[0]}"
    )


# ---------------------------------------------------------------------------
# Test 3: regression -- intra-area connectivity (IDs) and cross-area
# areaConnectivityId (IDs) must coexist with no false positives.
# ---------------------------------------------------------------------------

def test_id_connectivity_and_area_connectivity_no_errors():
    # Area AA001: two locations connected to each other by ID; one exits
    # into area BB001 via areaConnectivityId.
    a01 = _location(
        "A01",
        "Town Square",
        connectivity=["A02"],
        area_conn_ids=["BB001"],
    )
    a02 = _location(
        "A02",
        "Marketplace",
        connectivity=["A01"],
    )
    # Area BB001: one location connected back into AA001 by id.
    b01 = _location(
        "B01",
        "Forest Edge",
        connectivity=[],
        area_conn_ids=["AA001"],
    )
    module_data = {
        "AA001.json": _make_area("AA001", [a01, a02]),
        "BB001.json": _make_area("BB001", [b01]),
    }

    dbg = _run_validate(module_data)

    # No connectivity errors (IDs resolve correctly).
    assert _connectivity_errors(dbg) == [], (
        "Mixed valid ID-based connectivity should not produce "
        "errors, got: " + repr(_connectivity_errors(dbg))
    )
    # No area-connectivity errors either: AA001 and BB001 are both
    # known areas, so areaConnectivityId checks must pass cleanly.
    area_errs = [e for e in dbg.errors if "area" in e.lower()]
    assert area_errs == [], (
        "areaConnectivityId pointing at known areas should not produce "
        "errors, got: " + repr(area_errs)
    )
