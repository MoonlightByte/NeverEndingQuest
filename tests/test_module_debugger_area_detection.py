"""
Tests for VAL-C3: module_debugger must detect area files by structure,
not by a hardcoded filename prefix list.

`module_debugger.py` lines 158-161 currently route a file to
`validate_location_file()` only when the filename starts with one of
HH / GV / BH / BV / DS / EM / DG. Any module that uses a different
prefix (VO, TOWN, ZZ, ...) is silently NOT validated as an area file.

These tests build a tmp module dir containing:
  - ZZ001.json -- valid area structure but a NON-allowlisted prefix
  - random.json -- non-area JSON (regression guard: must NOT be treated
    as an area file even after the fix)

Pre-fix: ZZ001.json is skipped by the area-file branch and
`validate_location_file()` is never called for it.
Post-fix: ZZ001.json is recognized by its structure (`areaId` +
`locations`) and `validate_location_file()` IS called for it. The
`random.json` file is still NOT routed to area validation.
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_area_payload(area_id: str, area_name: str) -> dict:
    """Minimal valid area file structure (areaId + locations are the
    structural markers; other fields satisfy validate_location_file's
    required_area_fields check)."""
    return {
        "areaId": area_id,
        "areaName": area_name,
        "areaType": "wilderness",
        "map": f"map_{area_id}.json",
        "locations": [
            {
                "locationId": f"{area_id}01",
                "name": "Entry",
                "areaConnectivity": [],
            }
        ],
    }


def _build_debugger_with_files(tmp_module_dir: Path) -> ModuleDebugger:
    """Construct a ModuleDebugger pointed at tmp_module_dir, load its
    files into module_data, and return it ready for the area-detection
    branch to be exercised. We deliberately do not call load_schemas()
    because the area-file branch in validate_schema_compliance() runs
    BEFORE any schema lookup."""
    dbg = ModuleDebugger()
    dbg.module_path = str(tmp_module_dir)
    assert dbg.load_module_files(), "Failed to load module files"
    return dbg


# ---------------------------------------------------------------------------
# Test: area file with non-allowlisted prefix IS detected post-fix
# ---------------------------------------------------------------------------

def test_area_file_with_unlisted_prefix_is_detected(tmp_path, monkeypatch):
    """ZZ001.json has valid area structure but uses a prefix not in the
    hardcoded list. It must still be routed to validate_location_file()."""
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    area_path = module_dir / "ZZ001.json"
    _write_json(area_path, _make_area_payload("ZZ001", "Forgotten Plains"))

    dbg = _build_debugger_with_files(module_dir)

    # Spy on validate_location_file to record which filenames get routed
    # through the area-validation branch.
    routed = []

    def _spy(filename, data):
        routed.append(filename)

    monkeypatch.setattr(dbg, "validate_location_file", _spy)

    dbg.validate_schema_compliance()

    assert "ZZ001.json" in routed, (
        "Area file ZZ001.json was not routed to validate_location_file(). "
        f"Routed files: {routed}"
    )


# ---------------------------------------------------------------------------
# Regression guard: non-area JSON must NOT be detected as an area file
# ---------------------------------------------------------------------------

def test_non_area_file_is_not_detected(tmp_path, monkeypatch):
    """random.json has no areaId / locations -- structural detection
    must exclude it from area validation."""
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    random_path = module_dir / "random.json"
    _write_json(random_path, {"foo": "bar", "items": [1, 2, 3]})

    dbg = _build_debugger_with_files(module_dir)

    routed = []

    def _spy(filename, data):
        routed.append(filename)

    monkeypatch.setattr(dbg, "validate_location_file", _spy)

    dbg.validate_schema_compliance()

    assert "random.json" not in routed, (
        "Non-area file random.json was incorrectly routed to "
        f"validate_location_file(). Routed files: {routed}"
    )


# ---------------------------------------------------------------------------
# Belt-and-suspenders: allowlisted-prefix file is still detected
# (ensures the fix does not regress the original happy path)
# ---------------------------------------------------------------------------

def test_legacy_prefix_area_file_still_detected(tmp_path, monkeypatch):
    """HH001.json (in the original hardcoded allowlist) must continue
    to be routed to validate_location_file() after the fix."""
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    area_path = module_dir / "HH001.json"
    _write_json(area_path, _make_area_payload("HH001", "Harborhill"))

    dbg = _build_debugger_with_files(module_dir)

    routed = []

    def _spy(filename, data):
        routed.append(filename)

    monkeypatch.setattr(dbg, "validate_location_file", _spy)

    dbg.validate_schema_compliance()

    assert "HH001.json" in routed, (
        "Legacy-prefix area file HH001.json was not routed to "
        f"validate_location_file(). Routed files: {routed}"
    )
