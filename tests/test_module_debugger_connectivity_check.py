"""
Tests for VAL-H1: module_debugger.validate_references() must compare
location `connectivity` entries against location NAMES, not location
IDs.

`loca_schema.json:88-92` defines `connectivity` as "Names of other
locations directly connected to this one." -- free-text names, NOT
locationId strings. The previous implementation in
`module_debugger.py:271-273` compared each `connectivity` entry to the
set of locationId strings, which meant every legitimate connection
registered as a false-positive broken reference.

These tests cover:
  1. Positive: connectivity uses real location names -> no error.
  2. Negative: connectivity references an unknown name -> 1 error.
  3. Regression: areaConnectivityId (which IS an ID) is still checked
     against the area_ids set, and intra-area connectivity-by-name +
     cross-area connectivity-by-ID can coexist with no false positives.
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
    """Return errors that came from the connectivity check (line 273:
    'Invalid connection ... in location ... of ...')."""
    return [e for e in dbg.errors if "Invalid connection" in e]


# ---------------------------------------------------------------------------
# Test 1: positive case -- connectivity uses real location NAMES.
#
# Pre-fix: comparison is against location_ids, so "B (Cave Entrance)"
# (a name) is NOT in the id set and gets flagged as an Invalid
# connection -- test fails.
# Post-fix: comparison is against location_names; "B (Cave Entrance)"
# matches and no error is recorded.
# ---------------------------------------------------------------------------

def test_connectivity_names_resolve_against_location_names():
    loc_a = _location(
        "A01",
        "A (Forest Path)",
        connectivity=["B (Cave Entrance)"],
    )
    loc_b = _location(
        "A02",
        "B (Cave Entrance)",
        connectivity=["A (Forest Path)"],
    )
    module_data = {
        "AA001.json": _make_area("AA001", [loc_a, loc_b]),
    }

    dbg = _run_validate(module_data)

    assert _connectivity_errors(dbg) == [], (
        "Expected no connectivity errors when connectivity references "
        "valid location names, got: " + repr(_connectivity_errors(dbg))
    )


# ---------------------------------------------------------------------------
# Test 2: negative case -- connectivity references an unknown name.
#
# Exactly one Invalid-connection error must be recorded.
# ---------------------------------------------------------------------------

def test_connectivity_unknown_name_is_flagged():
    loc_a = _location(
        "A01",
        "A (Forest Path)",
        connectivity=["Z (Ghost Town)"],
    )
    loc_b = _location(
        "A02",
        "B (Cave Entrance)",
        connectivity=[],
    )
    module_data = {
        "AA001.json": _make_area("AA001", [loc_a, loc_b]),
    }

    dbg = _run_validate(module_data)

    errs = _connectivity_errors(dbg)
    assert len(errs) == 1, (
        f"Expected exactly 1 connectivity error for unknown name, "
        f"got {len(errs)}: {errs}"
    )
    assert "Z (Ghost Town)" in errs[0], (
        f"Error should mention the offending name 'Z (Ghost Town)', "
        f"got: {errs[0]}"
    )


# ---------------------------------------------------------------------------
# Test 3: regression -- mixed intra-area connectivity (names) and
# cross-area areaConnectivityId (IDs) must coexist with no false
# positives. The areaConnectivityId check path (line 276-283) must
# still operate against the area_ids set.
# ---------------------------------------------------------------------------

def test_mixed_name_connectivity_and_id_area_connectivity_no_errors():
    # Area AA001: two locations, connected to each other by name and
    # one exits into area BB001 via areaConnectivityId.
    a01 = _location(
        "A01",
        "Town Square",
        connectivity=["Marketplace"],
        area_conn_ids=["BB001"],
    )
    a02 = _location(
        "A02",
        "Marketplace",
        connectivity=["Town Square"],
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

    # No connectivity errors (names resolve correctly).
    assert _connectivity_errors(dbg) == [], (
        "Mixed valid name-based connectivity should not produce "
        "errors, got: " + repr(_connectivity_errors(dbg))
    )
    # No area-connectivity errors either: AA001 and BB001 are both
    # known areas, so areaConnectivityId checks must pass cleanly.
    area_errs = [e for e in dbg.errors if "area" in e.lower()]
    assert area_errs == [], (
        "areaConnectivityId pointing at known areas should not produce "
        "errors, got: " + repr(area_errs)
    )
