"""
Tests for VAL-C2: strict location-file validation.

The legacy `locationfile_schema.json` only requires 3 per-location fields
(`locationId`, `name`, `description`). That is far weaker than the
`loca_schema.json` which requires the full 21 location-level fields. Newly
generated modules should be validated against the stricter contract so
omissions like a missing `doors` array are caught before stitching.

VAL-C2 fix: `schemas/locationfile_schema_strict.json` composes:
  - the top-level area wrapper from `locationfile_schema.json`
    (`areaName`, `areaId`, `locations` are all required)
  - the per-location requirements from `loca_schema.json`
    (all 21 fields are required for each location item)

`ModuleValidator.load_schemas()`, `run_validation()`,
`run_all_validations()`, and `validate_all_files()` accept a new
`strict: bool` keyword (default False -> backward compat). When True the
strict schema is loaded for the "area" type. `module_stitcher.py` passes
`strict=True` so that newly stitched modules must satisfy the strict
contract.

These tests exercise that behavior end to end against fixtures in
`tmp_path`. No real module data is touched.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.validation.validate_module_files import ModuleValidator


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_location(loc_id="A01", name="Entry"):
    """Build a location dict containing every field required by
    loca_schema.json. Tests can pop individual fields to verify each one
    is enforced in strict mode."""
    return {
        "locationId": loc_id,
        "name": name,
        "type": "Room",
        "description": "A plain room.",
        "dmInstructions": "Describe the room when entered.",
        "coordinates": "X1Y1",
        "accessibility": "Open doorway.",
        "npcs": [],
        "monsters": [],
        "plotHooks": [],
        "lootTable": [],
        "dangerLevel": "Low",
        "connectivity": [],
        "areaConnectivity": [],
        "areaConnectivityId": [],
        "traps": [],
        "features": [],
        "dcChecks": [],
        "encounters": [],
        "adventureSummary": "",
        "doors": [],
    }


def _write_area_file(path: Path, area_id: str, locations: list,
                     include_area_id: bool = True,
                     include_area_name: bool = True) -> None:
    data = {"locations": locations}
    if include_area_name:
        data["areaName"] = "Test Area"
    if include_area_id:
        data["areaId"] = area_id
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_validator(module_dir: Path) -> ModuleValidator:
    return ModuleValidator(str(module_dir), str(SCHEMA_DIR))


# ---------------------------------------------------------------------------
# Test 1 -- strict mode rejects a location missing a per-location field
# ---------------------------------------------------------------------------

def test_strict_rejects_location_missing_doors(tmp_path):
    """A location missing the `doors` field must FAIL validation under
    strict=True. The legacy schema would pass it (doors is not in its
    required list) so this proves the strict per-location requirements
    from loca_schema are in effect."""
    module_dir = tmp_path / "missing_doors_mod"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    loc = _full_location()
    loc.pop("doors")  # remove ONLY doors; everything else satisfies strict
    _write_area_file(areas_dir / "A.json", area_id="A", locations=[loc])

    validator = _make_validator(module_dir)
    validator.load_schemas(strict=True)
    validator.validate_area_files()

    assert validator.results["area"]["failed"] == 1, (
        "Expected strict mode to fail the area file when the only "
        "location is missing the `doors` field. results="
        f"{dict(validator.results['area'])}"
    )
    # Surface the error to confirm the failure reason is the missing
    # `doors` field, not some unrelated schema issue.
    joined_errors = " | ".join(validator.results["area"]["errors"])
    assert "doors" in joined_errors, (
        "Expected the validation error to mention the missing `doors` "
        f"field. errors={validator.results['area']['errors']}"
    )


# ---------------------------------------------------------------------------
# Test 2 -- strict wrapper still enforces top-level areaId requirement
# ---------------------------------------------------------------------------

def test_strict_rejects_area_missing_top_level_area_id(tmp_path):
    """An area file missing the top-level `areaId` must FAIL under
    strict=True. This confirms the strict schema COMPOSES the wrapper
    requirements (areaName, areaId, locations) on top of the per-location
    requirements. If a future refactor accidentally dropped the wrapper
    requirements (e.g., a direct swap to loca_schema), this test fails."""
    module_dir = tmp_path / "missing_area_id_mod"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    loc = _full_location()
    _write_area_file(
        areas_dir / "A.json",
        area_id="IGNORED",
        locations=[loc],
        include_area_id=False,  # drop areaId from the top level
    )

    # The validate_area_files() loader only treats a file as an "area"
    # when it sees areaId+areaName+locations. To force the strict
    # validator to actually run on a file missing `areaId`, call
    # validate_file() directly against the area schema. This isolates
    # the strict schema's wrapper-level enforcement.
    validator = _make_validator(module_dir)
    validator.load_schemas(strict=True)

    success, error = validator.validate_file(
        areas_dir / "A.json", "area"
    )
    assert success is False, (
        "Expected strict mode to reject an area file missing the "
        "top-level `areaId` field. The strict schema must keep the "
        "wrapper requirements from locationfile_schema.json, not just "
        "swap in loca_schema's per-location requirements."
    )
    assert error is not None and "areaId" in error, (
        f"Expected the error to mention `areaId`. error={error}"
    )


# ---------------------------------------------------------------------------
# Test 3 -- backward compatibility: legacy mode still accepts the same file
# ---------------------------------------------------------------------------

def test_legacy_mode_accepts_location_missing_doors(tmp_path):
    """The same location that fails in strict mode must PASS under
    strict=False. This preserves backward compatibility for callers that
    have not opted into the strict contract (e.g. older module
    validators). If this test fails, the default behaviour changed and
    will break existing modules."""
    module_dir = tmp_path / "missing_doors_legacy_mod"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    loc = _full_location()
    loc.pop("doors")
    _write_area_file(areas_dir / "A.json", area_id="A", locations=[loc])

    validator = _make_validator(module_dir)
    # Default strict=False -- backward compat path
    validator.load_schemas()
    validator.validate_area_files()

    assert validator.results["area"]["failed"] == 0, (
        "Expected legacy mode (strict=False) to accept a location "
        "missing `doors` -- the legacy schema does not require it. "
        f"errors={validator.results['area']['errors']}"
    )
    assert validator.results["area"]["passed"] == 1, (
        "Expected exactly one area file to pass under legacy mode. "
        f"results={dict(validator.results['area'])}"
    )


# ---------------------------------------------------------------------------
# Test 4 -- end-to-end: validate_all_files(strict=True) uses strict schema
# ---------------------------------------------------------------------------

def test_validate_all_files_strict_uses_strict_schema(tmp_path):
    """The production entry point used by module_stitcher.py is
    `validate_all_files(strict=True)`. This test wires up a minimal
    module directory with an area file missing `doors`, runs
    `validate_all_files(strict=True)`, and confirms the area validation
    fails (i.e. the strict schema was wired all the way through the
    public entry point, not just into `load_schemas`)."""
    module_dir = tmp_path / "end_to_end_strict_mod"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    loc = _full_location()
    loc.pop("doors")
    _write_area_file(areas_dir / "A.json", area_id="A", locations=[loc])

    validator = _make_validator(module_dir)
    results = validator.validate_all_files(strict=True)

    assert results["area"]["failed"] >= 1, (
        "Expected validate_all_files(strict=True) to fail the area "
        "file missing `doors`. If failed==0, the strict flag is not "
        "being threaded through validate_all_files -> "
        "run_all_validations -> load_schemas. "
        f"results={dict(results['area'])}"
    )

    # Sanity: same module under default (strict=False) must pass.
    validator2 = _make_validator(module_dir)
    results2 = validator2.validate_all_files()
    assert results2["area"]["failed"] == 0, (
        "Default validate_all_files() (no strict kwarg) must remain "
        "backward compatible and accept the same file. "
        f"results={dict(results2['area'])}"
    )
