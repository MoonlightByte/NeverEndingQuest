"""
Tests for VAL-C1: connectivity validator must ignore *_BU.json backups.

`core/validation/validate_module_files.py` line 302-305 currently globs
`*_BU.json` FIRST, falling back to `*.json` only when no backup files
exist. This is wrong: a stale backup file poisons connectivity
validation because the live area file is silently ignored.

These tests exercise `ModuleValidator.validate_area_connectivity()`
against an `areas/` directory that contains both live files (valid
connectivity) and `_BU.json` files (BROKEN connectivity). Pre-fix the
validator reports the backup-file errors (False, [...]). Post-fix it
ignores the backups and reports the live-file truth (True, []).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.validation.validate_module_files import ModuleValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_validator(module_path: Path) -> ModuleValidator:
    """Allocate a ModuleValidator. schema_dir is irrelevant for
    validate_area_connectivity (it only reads area JSON files), but the
    constructor requires it."""
    # Point schema_dir at the real schemas dir for safety, though it is
    # never accessed by validate_area_connectivity().
    schema_dir = Path(__file__).resolve().parents[1] / "schemas"
    return ModuleValidator(str(module_path), str(schema_dir))


def _write_area(path: Path, area_id: str, area_name: str, connects_to: list) -> None:
    """Write a minimal area file with one location whose
    areaConnectivity points at `connects_to` (list of area NAMES)."""
    data = {
        "areaId": area_id,
        "areaName": area_name,
        "locations": [
            {
                "locationId": f"{area_id}01",
                "name": "Entry",
                "areaConnectivity": list(connects_to),
            }
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Main bug case: BU files must be ignored, live files are the truth
# ---------------------------------------------------------------------------

def test_connectivity_validation_ignores_BU_backups(tmp_path):
    """When both live and _BU.json files exist, the connectivity
    validator must use the LIVE files. A broken backup file must not
    poison the validation result."""
    module_dir = tmp_path / "test_module"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    # LIVE files: valid connectivity (A <-> B). Both reachable.
    _write_area(areas_dir / "A.json", "A", "Town", connects_to=["Forest"])
    _write_area(areas_dir / "B.json", "B", "Forest", connects_to=["Town"])

    # BACKUP files: BROKEN connectivity. No links at all -> starting
    # area has no connections AND B is unreachable. If the validator
    # loads these, it will report errors.
    _write_area(areas_dir / "A_BU.json", "A", "Town", connects_to=[])
    _write_area(areas_dir / "B_BU.json", "B", "Forest", connects_to=[])

    validator = _make_validator(module_dir)
    ok, errors = validator.validate_area_connectivity()

    assert ok is True, (
        f"validate_area_connectivity should return True because the LIVE "
        f"area files have valid connectivity. Pre-fix, the validator "
        f"loaded the *_BU.json backups first and reported errors from "
        f"the stale broken backups. errors={errors}"
    )
    assert errors == [], (
        f"Expected no errors from valid live files, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Regression guard: validator still works when no BU files exist
# ---------------------------------------------------------------------------

def test_connectivity_validation_works_without_BU_files(tmp_path):
    """When only live *.json files exist (no _BU.json backups), the
    validator must still load and validate them correctly. This guards
    against accidentally regressing to a state where BU files are
    REQUIRED."""
    module_dir = tmp_path / "test_module_no_bu"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    _write_area(areas_dir / "A.json", "A", "Town", connects_to=["Forest"])
    _write_area(areas_dir / "B.json", "B", "Forest", connects_to=["Town"])

    validator = _make_validator(module_dir)
    ok, errors = validator.validate_area_connectivity()

    assert ok is True, (
        f"Expected validation to pass with only live files present. "
        f"errors={errors}"
    )
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Regression guard: real broken connectivity in LIVE files is still caught
# ---------------------------------------------------------------------------

def test_connectivity_validation_catches_real_live_breakage(tmp_path):
    """If the LIVE files genuinely have broken connectivity, the
    validator must still report errors. This guards against an
    over-aggressive fix that ignores all files."""
    module_dir = tmp_path / "test_module_broken_live"
    areas_dir = module_dir / "areas"
    areas_dir.mkdir(parents=True)

    # Live files: A has NO connections, B has NO connections.
    # A is starting area -> "starting area has no connections" error.
    # B is unreachable from A -> "B is unreachable" error.
    _write_area(areas_dir / "A.json", "A", "Town", connects_to=[])
    _write_area(areas_dir / "B.json", "B", "Forest", connects_to=[])

    validator = _make_validator(module_dir)
    ok, errors = validator.validate_area_connectivity()

    assert ok is False, (
        f"Expected validation to FAIL because live files have broken "
        f"connectivity. Got ok=True with errors={errors}."
    )
    assert len(errors) > 0, "Expected at least one connectivity error"
