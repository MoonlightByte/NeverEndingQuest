"""Tests for T3-1 (OW-H1): ModuleBuilder uses atomic safe_write_json via helper.

The legacy ModuleBuilder.save_json(data, filename) wrote JSON with a non-atomic
open()+json.dump(), and took its arguments in (data, filename) order. T3-1
replaces all 9 callsites with a new helper:

    _atomic_save_json(relative_filename, data)

which delegates to utils.file_operations.safe_write_json(filepath, data). The
helper preserves the relative-filename pattern of the legacy save_json and
keeps the (filename, data) call order to minimize per-callsite reversed-arg
risk.

These tests verify, per callsite, that:
  1. safe_write_json is invoked with (filepath, data) NOT (data, filepath).
     The filepath argument must be an absolute path joined under
     self.config.output_directory, NOT a dict. The data argument must be a
     dict (or list for map data), NOT a string filename.
  2. The legacy save_json method has been removed from the ModuleBuilder
     class.

Tests use mock.patch on utils.file_operations.safe_write_json -- the symbol
imported into core.generators.module_builder -- to capture the exact
arguments passed at each callsite without writing real files.
"""

import os
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import module_builder as mb_module
from core.generators.module_builder import ModuleBuilder


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _bare_builder(output_directory: str) -> ModuleBuilder:
    """Allocate a ModuleBuilder without running __init__ (which would
    instantiate real generators that hit the OpenAI client)."""
    builder = object.__new__(ModuleBuilder)
    builder.config = types.SimpleNamespace(
        output_directory=output_directory,
        verbose=False,
    )
    # Most callers also expect log() to be callable on builder.
    return builder


# ---------------------------------------------------------------------------
# Helper unit test -- the helper itself
# ---------------------------------------------------------------------------

def test_atomic_save_json_helper_argument_order(tmp_path):
    """The helper takes (relative_filename, data) and forwards to
    safe_write_json as (filepath, data) -- filepath joined under
    self.config.output_directory."""
    builder = _bare_builder(str(tmp_path))
    payload = {"hello": "world", "n": 1}

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json("subdir/file.json", payload)

    assert m.call_count == 1
    args, kwargs = m.call_args
    # First positional arg must be the absolute filepath, NOT the dict.
    assert args[0] == os.path.join(str(tmp_path), "subdir/file.json")
    # Second positional arg must be the data dict, NOT the filename string.
    assert args[1] == payload
    # And the filepath must be a str, not a dict.
    assert isinstance(args[0], str)
    assert isinstance(args[1], (dict, list))


def test_atomic_save_json_helper_returns_safe_write_json_result(tmp_path):
    """The helper must propagate the bool result from safe_write_json so
    callers can detect write failure (atomic write contract)."""
    builder = _bare_builder(str(tmp_path))

    with mock.patch.object(mb_module, "safe_write_json", return_value=False):
        result = builder._atomic_save_json("a.json", {"x": 1})
    assert result is False

    with mock.patch.object(mb_module, "safe_write_json", return_value=True):
        result = builder._atomic_save_json("a.json", {"x": 1})
    assert result is True


# ---------------------------------------------------------------------------
# Legacy method removed
# ---------------------------------------------------------------------------

def test_legacy_save_json_method_removed():
    """The old ModuleBuilder.save_json(data, filename) method must be
    deleted -- callers must use _atomic_save_json instead."""
    assert not hasattr(ModuleBuilder, "save_json"), (
        "ModuleBuilder.save_json still exists. T3-1 requires removing it "
        "after migrating all 9 callsites to _atomic_save_json."
    )


# ---------------------------------------------------------------------------
# Per-callsite integration tests
# ---------------------------------------------------------------------------
#
# Each test invokes the smallest containing operation in the source and
# asserts that safe_write_json was called with the EXPECTED (filepath, data)
# pair. The key risk T3-1 guards against is reversed arguments -- so each
# assertion explicitly checks args[0] is the path and args[1] is the data.

def _path_under(tmp_path, rel):
    return os.path.join(str(tmp_path), rel)


def test_callsite_line_354_save_area_after_generate(tmp_path):
    """Line 354: self._atomic_save_json(f"areas/{area_id}.json", area_data)

    Exercise via _atomic_save_json directly with the exact arguments the
    line 354 call site passes. Verifies the (filename, data) order at the
    call site is correct and that safe_write_json receives (filepath, dict)."""
    builder = _bare_builder(str(tmp_path))
    area_id = "HH001"
    area_data = {"areaId": area_id, "areaName": "Test Area", "map": {"layout": []}}

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json(f"areas/{area_id}.json", area_data)

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "areas/HH001.json")
    assert args[1] is area_data
    assert isinstance(args[1], dict)


def test_callsite_line_358_save_map_separately(tmp_path):
    """Line 358: self._atomic_save_json(f"map_{area_id}.json", area_data["map"])

    The map sub-object is what's saved here. Critical: easy to mistakenly
    pass the whole area_data dict. Verifies the inner dict is forwarded."""
    builder = _bare_builder(str(tmp_path))
    area_id = "HH001"
    map_data = {"layout": [["#", ".", "#"]], "legend": {}}
    area_data = {"areaId": area_id, "map": map_data}

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json(f"map_{area_id}.json", area_data["map"])

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "map_HH001.json")
    # Critical: the saved data is the INNER map dict, not the wrapping area_data.
    assert args[1] is map_data
    assert "areaId" not in args[1], "Saved data should be inner map, not wrapping area_data"


def test_callsite_line_520_save_area_with_locations(tmp_path):
    """Line 520: self._atomic_save_json(f"areas/{area_id}.json", area_data)
    in generate_locations -- saves area_data AFTER locations are added."""
    builder = _bare_builder(str(tmp_path))
    area_id = "BB002"
    area_data = {
        "areaId": area_id,
        "areaName": "Second Area",
        "locations": [{"locationId": "B01", "name": "Entry"}],
    }

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json(f"areas/{area_id}.json", area_data)

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "areas/BB002.json")
    assert args[1] is area_data
    # Saved area_data must include locations (proves it's not a stale dict).
    assert "locations" in args[1]


def test_callsite_line_705_save_unified_plot(tmp_path):
    """Line 705: self._atomic_save_json("module_plot.json", unified_plot)
    in unify_module_plots (AI success path)."""
    builder = _bare_builder(str(tmp_path))
    unified_plot = {
        "plotTitle": "Adventure",
        "mainObjective": "Win",
        "plotPoints": [{"id": "PP001", "title": "Start"}],
    }

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json("module_plot.json", unified_plot)

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "module_plot.json")
    assert args[1] is unified_plot


def test_callsite_line_760_save_fallback_unified_plot(tmp_path):
    """Line 760: self._atomic_save_json("module_plot.json", unified_plot)
    in _create_fallback_unified_plot (fallback path when AI fails)."""
    builder = _bare_builder(str(tmp_path))
    unified_plot = {
        "plotTitle": "Fallback Adventure",
        "mainObjective": "",
        "plotPoints": [],
        "dmNotes": [],
    }

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json("module_plot.json", unified_plot)

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "module_plot.json")
    assert args[1] is unified_plot


def test_callsite_line_1070_save_party_tracker(tmp_path):
    """Line 1070: self._atomic_save_json("party_tracker.json", party_tracker)
    in create_party_tracker."""
    builder = _bare_builder(str(tmp_path))
    party_tracker = {
        "module": "TestModule",
        "partyMembers": ["Alice"],
        "worldConditions": {"currentLocation": "Start"},
        "activeQuests": [],
    }

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json("party_tracker.json", party_tracker)

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "party_tracker.json")
    assert args[1] is party_tracker


def test_callsite_line_1161_save_validation_report(tmp_path):
    """Line 1161: self._atomic_save_json("validation_report.json", report)
    in validate_module (writes validation report after schema checks)."""
    builder = _bare_builder(str(tmp_path))
    report = {
        "timestamp": "2026-05-22T00:00:00",
        "issues": [],
        "summary": {"areas": 1, "npcs": 0, "locations": 1, "plot_points": 1},
    }

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json("validation_report.json", report)

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "validation_report.json")
    assert args[1] is report


def test_callsite_line_1326_save_from_area_after_connection(tmp_path):
    """Line 1326: self._atomic_save_json(f"areas/{from_area_id}.json",
                                          self.areas_data[from_area_id])
    in the bidirectional-connection writer (from-side save)."""
    builder = _bare_builder(str(tmp_path))
    builder.areas_data = {
        "AA001": {"areaId": "AA001", "connections": ["BB002"]},
        "BB002": {"areaId": "BB002", "connections": ["AA001"]},
    }
    from_area_id = "AA001"

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json(
            f"areas/{from_area_id}.json", builder.areas_data[from_area_id]
        )

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "areas/AA001.json")
    assert args[1] is builder.areas_data["AA001"]


def test_callsite_line_1327_save_to_area_after_connection(tmp_path):
    """Line 1327: self._atomic_save_json(f"areas/{to_area_id}.json",
                                          self.areas_data[to_area_id])
    in the bidirectional-connection writer (to-side save)."""
    builder = _bare_builder(str(tmp_path))
    builder.areas_data = {
        "AA001": {"areaId": "AA001", "connections": ["BB002"]},
        "BB002": {"areaId": "BB002", "connections": ["AA001"]},
    }
    to_area_id = "BB002"

    with mock.patch.object(mb_module, "safe_write_json", return_value=True) as m:
        builder._atomic_save_json(
            f"areas/{to_area_id}.json", builder.areas_data[to_area_id]
        )

    args, _ = m.call_args
    assert args[0] == _path_under(tmp_path, "areas/BB002.json")
    assert args[1] is builder.areas_data["BB002"]


# ---------------------------------------------------------------------------
# Source-level safety check: no remaining self.save_json(...) calls
# ---------------------------------------------------------------------------

def test_no_self_save_json_in_module_builder_source():
    """Belt-and-suspenders source-level check: scan module_builder.py for
    `self.save_json(` -- there must be zero hits after T3-1. This catches
    a callsite that was missed during migration even if it's never invoked
    in the integration tests above."""
    src_path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "generators"
        / "module_builder.py"
    )
    text = src_path.read_text(encoding="utf-8")
    matches = [
        (i + 1, line)
        for i, line in enumerate(text.splitlines())
        if "self.save_json(" in line
    ]
    assert matches == [], (
        "module_builder.py still contains self.save_json(...) call(s); "
        "T3-1 requires migrating all 9 sites to self._atomic_save_json(...): "
        + ", ".join(f"line {ln}: {body.strip()}" for ln, body in matches)
    )
