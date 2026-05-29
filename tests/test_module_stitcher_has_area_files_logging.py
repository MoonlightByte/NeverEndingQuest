"""
Tests for INT-M3: _has_area_files must log JSON parse failures instead of
silently swallowing them with a bare `except: continue`.

`core/generators/module_stitcher.py` line ~218 currently wraps the
`safe_json_load()` + structure-check inside a bare `except: continue`. If a
module directory has area JSON files that are all malformed (truncated,
unreadable, etc.), `_has_area_files()` returns False with no log output --
the module looks like it has no area files at all.

The fix logs a warning per skipped file (identifying the path and the
underlying exception) so the failure mode is visible in
modules/logs/game_errors.log instead of being silent.

These tests build a tmp module directory containing only a malformed
area JSON file and assert that:
  - `_has_area_files()` returns False (no VALID area files were found)
  - a warning identifying the malformed file was logged via
    `utils.enhanced_logger.warning()`
"""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import module_stitcher as module_stitcher_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_module_with_malformed_area(module_root: Path) -> Path:
    """Create a module directory whose only area file is malformed JSON."""
    module_path = module_root / "Broken_Module"
    areas_dir = module_path / "areas"
    areas_dir.mkdir(parents=True)

    # Truncated JSON -- json.load() will raise JSONDecodeError
    malformed = areas_dir / "ZZ001.json"
    malformed.write_text('{"areaId": "ZZ001", "areaName": "Broken", "locations":',
                         encoding="utf-8")
    return module_path


class _StubStitcher:
    """Minimal stand-in for ModuleStitcher.

    `_has_area_files` is a self-contained method that only reads
    `self` for nothing -- it just takes a module path. We bind the
    real method to a bare object so we don't have to construct a
    full ModuleStitcher (which builds an OpenAI client, loads the
    world registry, etc.).
    """

    _has_area_files = module_stitcher_module.ModuleStitcher._has_area_files


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_has_area_files_logs_warning_on_malformed_json(tmp_path, caplog):
    """A malformed area JSON file must be logged as a warning, not
    silently skipped. _has_area_files still returns False because no
    structurally-valid area files were found."""
    module_path = _build_module_with_malformed_area(tmp_path)

    stitcher = _StubStitcher()

    # Capture warnings emitted via the NeverEndingQuest logger
    with caplog.at_level(logging.WARNING, logger="NeverEndingQuest"):
        result = stitcher._has_area_files(str(module_path))

    assert result is False, (
        "Module with only malformed area files must report no area files"
    )

    # A warning naming the malformed file must have been logged.
    warning_records = [
        rec for rec in caplog.records
        if rec.levelno == logging.WARNING
        and "Skipped malformed area file" in rec.getMessage()
        and "ZZ001.json" in rec.getMessage()
    ]
    assert warning_records, (
        "Expected a warning identifying the malformed area file "
        "(message containing 'Skipped malformed area file' and 'ZZ001.json'); "
        f"got records: {[r.getMessage() for r in caplog.records]}"
    )


def test_has_area_files_returns_true_for_valid_area(tmp_path, caplog):
    """Regression guard: a structurally-valid area file is still detected,
    and no malformed-file warning is emitted."""
    import json

    module_path = tmp_path / "Good_Module"
    areas_dir = module_path / "areas"
    areas_dir.mkdir(parents=True)

    valid = areas_dir / "AA001.json"
    valid.write_text(
        json.dumps({
            "areaId": "AA001",
            "areaName": "A Place",
            "locations": [],
        }),
        encoding="utf-8",
    )

    stitcher = _StubStitcher()

    with caplog.at_level(logging.WARNING, logger="NeverEndingQuest"):
        result = stitcher._has_area_files(str(module_path))

    assert result is True

    malformed_warnings = [
        rec for rec in caplog.records
        if "Skipped malformed area file" in rec.getMessage()
    ]
    assert not malformed_warnings, (
        "No malformed-file warning should be emitted for a valid module; "
        f"got: {[r.getMessage() for r in malformed_warnings]}"
    )
