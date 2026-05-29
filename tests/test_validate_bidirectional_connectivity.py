"""
Tests for VAL-H2 / MP-H4: bidirectional connectivity validator.

`core/validation/validate_module_files.py` currently checks AREA-level
reachability (`validate_area_connectivity`), but does NOT check that
within an area, every LOCATION-to-LOCATION connection is bidirectional.

If location A lists B in its `connectivity`, but B does not list A,
players can travel A -> B but get stranded -- no way back. This is the
"one-way door" navigation bug.

These tests exercise `ModuleValidator.validate_bidirectional_connectivity()`.
It must:

  1. Return (True, []) when every connection has a matching reverse edge.
  2. Return (False, [errors]) listing one-way connections by ID.
  3. Return (True, []) (vacuous) when no locations declare connectivity.

`connectivity` lists are location IDs (the generator, ID remapper and
runtime pathfinder all treat them as IDs; the schema description was
corrected to match). Matching by name produced dozens of false positives
on valid modules, so this validator compares IDs.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.validation.validate_module_files import ModuleValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_validator(module_path: Path) -> ModuleValidator:
    """Allocate a ModuleValidator. schema_dir is irrelevant for
    validate_bidirectional_connectivity (only reads area JSON files),
    but the constructor requires it."""
    schema_dir = Path(__file__).resolve().parents[1] / "schemas"
    return ModuleValidator(str(module_path), str(schema_dir))


def _write_area_with_locations(path: Path, area_id: str, area_name: str, locations: list) -> None:
    """Write an area file with the given locations list.

    Each entry in `locations` is a dict of the form:
        {"locationId": "A01", "name": "Foyer", "connectivity": ["A02"]}
    where connectivity entries are the locationIds of neighbours.
    """
    data = {
        "areaId": area_id,
        "areaName": area_name,
        "locations": locations,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Test 1 (positive): all connections bidirectional -> 0 errors
# ---------------------------------------------------------------------------

def test_bidirectional_connectivity_all_valid(tmp_path):
    """When every location's connectivity has a matching reverse edge,
    the validator must return (True, []).

    Layout (connectivity uses location IDs):
        A01 <-> A02 <-> A03
        A01 lists [A02]
        A02 lists [A01, A03]
        A03 lists [A02]
    """
    module_dir = tmp_path / "test_module_valid"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    _write_area_with_locations(
        areas_dir / "A.json",
        "A",
        "Manor",
        [
            {"locationId": "A01", "name": "Foyer", "connectivity": ["A02"]},
            {"locationId": "A02", "name": "Hallway", "connectivity": ["A01", "A03"]},
            {"locationId": "A03", "name": "Library", "connectivity": ["A02"]},
        ],
    )

    validator = _make_validator(module_dir)
    ok, errors = validator.validate_bidirectional_connectivity(module_dir)

    assert ok is True, (
        f"Expected all-bidirectional connections to validate cleanly. "
        f"errors={errors}"
    )
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Test 2 (negative): A01 -> A02 but A02 has no A01 -> 1 error naming both
# ---------------------------------------------------------------------------

def test_bidirectional_connectivity_detects_one_way(tmp_path):
    """When a location lists a neighbor that does not list it back,
    the validator must return (False, [error]) with an error string
    mentioning BOTH location IDs so a fixer can locate the bug."""
    module_dir = tmp_path / "test_module_one_way"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    # A01 says it connects to A02. A02 does NOT list A01.
    # This is a one-way door: players in A01 can travel to A02,
    # but once in A02 they cannot return to A01.
    _write_area_with_locations(
        areas_dir / "A.json",
        "A",
        "Manor",
        [
            {"locationId": "A01", "name": "Foyer", "connectivity": ["A02"]},
            {"locationId": "A02", "name": "Hallway", "connectivity": []},
        ],
    )

    validator = _make_validator(module_dir)
    ok, errors = validator.validate_bidirectional_connectivity(module_dir)

    assert ok is False, (
        f"Expected validation to FAIL because A01 -> A02 has no "
        f"reverse edge. Got ok=True with errors={errors}."
    )
    assert len(errors) == 1, (
        f"Expected exactly one error for the one-way A01 -> A02 "
        f"link, got: {errors}"
    )
    err = errors[0]
    assert "A01" in err and "A02" in err, (
        f"Error message must name BOTH endpoints so the bug can be "
        f"located. Got: {err!r}"
    )


# ---------------------------------------------------------------------------
# Test 3 (regression / vacuous): no connectivity at all -> 0 errors
# ---------------------------------------------------------------------------

def test_bidirectional_connectivity_no_connections_is_vacuous(tmp_path):
    """When no location declares any connectivity, the bidirectional
    property is vacuously satisfied. The validator must return
    (True, []) -- it is not responsible for unreachable-area detection
    (that is `validate_area_connectivity`'s job)."""
    module_dir = tmp_path / "test_module_vacuous"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    _write_area_with_locations(
        areas_dir / "A.json",
        "A",
        "Empty",
        [
            {"locationId": "A01", "name": "Foyer", "connectivity": []},
            {"locationId": "A02", "name": "Hallway", "connectivity": []},
        ],
    )

    validator = _make_validator(module_dir)
    ok, errors = validator.validate_bidirectional_connectivity(module_dir)

    assert ok is True, (
        f"Expected vacuous case (no connectivity entries) to return "
        f"(True, []). errors={errors}"
    )
    assert errors == [], f"Expected no errors in vacuous case, got: {errors}"
