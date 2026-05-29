"""
Tests for OW-C2: correct save_json_safely argument order in
`core/generators/module_generator.py`.

`module_generator.py` imports safe_write_json under the alias
`save_json_safely` (line 82):
    from utils.file_operations import safe_write_json as save_json_safely

`safe_write_json`'s real signature (utils/file_operations.py:278) is
    safe_write_json(filepath: str, data: Dict[str, Any], ...)

Four call sites had the arguments REVERSED:

  PRODUCTION PATHS (covered by T1-2a):
    Line 621 (inside `ModuleGenerator.generate_module()`)
    Line 1012 (inside `ModuleGenerator.save_module()`)

  DEAD-CODE PATHS (covered by T1-2b):
    Line 360 (inside standalone `update_location_references()` function)
    Line 947 (inside `ModuleGenerator.generate_unified_plot_file()`)

With the bug, the atomic writer receives a dict where it expects a path
string. `safe_write_json` stringifies the dict via `str(filepath)` and
either writes the temp file to a path literally named after the
stringified dict or returns False. Either way, the expected on-disk file
is never created with the JSON payload.

Smoke tests for the dead-code paths invoke the containing functions
in isolation against a tmp directory and assert that the expected file
is written with the correct contents.

Pre-fix, all assertions fail: either the file does not exist or it does
not contain the expected JSON payload.
"""

import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import module_generator
from core.generators.module_generator import ModuleGenerator


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_generator() -> ModuleGenerator:
    """Allocate a ModuleGenerator without running __init__ (avoids schema
    load and OpenAI client init)."""
    gen = object.__new__(ModuleGenerator)
    gen.prompt_guide = None
    gen.schema = {"properties": {}}
    return gen


# ---------------------------------------------------------------------------
# Line 621: ModuleGenerator.generate_module() validation report write
# ---------------------------------------------------------------------------

def test_generate_module_writes_validation_report_with_issues(tmp_path, monkeypatch):
    """When validate_module_structure() returns issues, generate_module()
    must write them to `modules/<module_name>/validation_report.json` with
    the issues list as the JSON payload (not a stringified dict path)."""
    # Use a unique module name so the path is deterministic.
    module_name = "OWC2_TestModuleGenerate"
    # generate_module() writes to a HARDCODED relative path: f"modules/{module_name}".
    # We chdir into tmp_path so that the writes land inside the test sandbox.
    monkeypatch.chdir(tmp_path)

    # Create the module directory structure that triggers validation issues
    # (missing npcs/monsters dirs, no area files -> validate_module_structure
    # will return a non-empty issues list, hitting the write path at line 621).
    module_dir = tmp_path / "modules" / module_name
    module_dir.mkdir(parents=True, exist_ok=True)

    gen = _make_generator()

    # Short-circuit all AI field generation: pass moduleName in custom_values
    # so the field_order loop skips every field (get_nested_value returns
    # non-None for moduleName, and we patch get_nested_value to return a
    # truthy value for everything else too).
    custom_values = {"moduleName": module_name}

    # Patch the field-generation loop so no OpenAI calls happen.
    with patch.object(ModuleGenerator, "get_nested_value", return_value="present"), \
         patch.object(ModuleGenerator, "set_nested_value", return_value=None), \
         patch.object(ModuleGenerator, "get_field_schema", return_value={}), \
         patch.object(ModuleGenerator, "generate_field", return_value="dummy"):
        gen.generate_module(initial_concept="test", custom_values=custom_values)

    # Assert the validation report file actually exists at the expected path.
    expected_path = module_dir / "validation_report.json"
    assert expected_path.exists(), (
        f"Validation report was not written to expected path {expected_path}. "
        f"Pre-fix, the dict was passed as filepath so the file never got created. "
        f"Files in module_dir: {list(module_dir.iterdir())}"
    )

    # Assert the file contents are the validation report JSON, not garbage.
    with open(expected_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    assert "issues" in report, (
        f"Validation report missing 'issues' key. Got: {report}"
    )
    assert isinstance(report["issues"], list), (
        f"'issues' should be a list, got {type(report['issues'])}: {report['issues']}"
    )
    assert len(report["issues"]) > 0, (
        f"Expected at least one validation issue (missing npcs/monsters dirs, "
        f"no area files), got empty list."
    )


# ---------------------------------------------------------------------------
# Line 1012: ModuleGenerator.save_module() validation report write
# ---------------------------------------------------------------------------

def test_save_module_writes_validation_report_with_errors_and_warnings(tmp_path, monkeypatch):
    """When save_module() runs the ModuleDebugger, it must write the
    validation report to `modules/<module_name>/validation_report.json`
    with the timestamp/errors/warnings JSON payload."""
    module_name = "OWC2_TestModuleSave"
    monkeypatch.chdir(tmp_path)

    gen = _make_generator()
    module_data = {"moduleName": module_name, "moduleDescription": "test"}

    # Mock the ModuleDebugger so we don't run the real validation pipeline.
    fake_debugger = MagicMock()
    fake_debugger.errors = ["fake_error_1", "fake_error_2"]
    fake_debugger.warnings = ["fake_warning_1"]
    fake_debugger.generate_report.return_value = "fake report"

    # Patch the import-inside-function so save_module() uses our mock.
    fake_debugger_module = types.ModuleType("module_debugger")
    fake_debugger_module.ModuleDebugger = MagicMock(return_value=fake_debugger)
    monkeypatch.setitem(sys.modules, "module_debugger", fake_debugger_module)

    # Mock the heavy area + plot generation methods so we don't invoke AI.
    with patch.object(ModuleGenerator, "generate_all_areas", return_value=["A001"]), \
         patch.object(ModuleGenerator, "generate_unified_plot_file", return_value=None):
        gen.save_module(module_data)

    # The save_module() method writes to f"modules/{module_name.replace(' ', '_')}".
    module_dir = tmp_path / "modules" / module_name
    expected_path = module_dir / "validation_report.json"

    assert expected_path.exists(), (
        f"Validation report was not written to expected path {expected_path}. "
        f"Pre-fix, dict-as-filepath caused atomic_writer to fail; file never "
        f"created. Files in module_dir: "
        f"{list(module_dir.iterdir()) if module_dir.exists() else 'module_dir does not exist'}"
    )

    with open(expected_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    # Verify the actual validation_data payload structure (lines 1007-1011).
    assert "timestamp" in report, f"Missing 'timestamp' key. Got: {report}"
    assert "errors" in report, f"Missing 'errors' key. Got: {report}"
    assert "warnings" in report, f"Missing 'warnings' key. Got: {report}"
    assert report["errors"] == ["fake_error_1", "fake_error_2"], (
        f"Errors mismatch. Expected mocked errors, got: {report['errors']}"
    )
    assert report["warnings"] == ["fake_warning_1"], (
        f"Warnings mismatch. Expected mocked warnings, got: {report['warnings']}"
    )


# ---------------------------------------------------------------------------
# Line 360: standalone update_location_references() dead-code path (T1-2b)
# ---------------------------------------------------------------------------

def test_update_location_references_writes_remapped_file(tmp_path):
    """When `update_location_references()` finds location IDs to remap, it
    must persist the remapped data back to `file_path`. Pre-fix the args
    were swapped: `save_json_safely(data, file_path)` instead of
    `save_json_safely(file_path, data)`, so the rewrite went nowhere and
    the file kept its original (old-ID) contents."""
    area_file = tmp_path / "AA01.json"
    original = {
        "locations": [
            {"locationId": "OLD_ID_1", "name": "Entry"},
            {"locationId": "OLD_ID_2", "name": "Hall"},
        ],
        "map": {
            "rooms": [
                {"id": "OLD_ID_1"},
                {"id": "OLD_ID_2"},
            ]
        },
    }
    with open(area_file, "w", encoding="utf-8") as f:
        json.dump(original, f)

    id_mappings = {
        "OLD_ID_1": "NEW_ID_1",
        "OLD_ID_2": "NEW_ID_2",
    }

    # Should not raise.
    module_generator.update_location_references(str(area_file), id_mappings)

    # File must still exist at the original path.
    assert area_file.exists(), (
        f"File {area_file} disappeared after update_location_references()."
    )

    with open(area_file, "r", encoding="utf-8") as f:
        updated = json.load(f)

    # All four references must be remapped.
    assert updated["locations"][0]["locationId"] == "NEW_ID_1", (
        f"Pre-fix, the args were reversed so the rewrite never persisted. "
        f"Got: {updated}"
    )
    assert updated["locations"][1]["locationId"] == "NEW_ID_2", updated
    assert updated["map"]["rooms"][0]["id"] == "NEW_ID_1", updated
    assert updated["map"]["rooms"][1]["id"] == "NEW_ID_2", updated


# ---------------------------------------------------------------------------
# Line 947: ModuleGenerator.generate_unified_plot_file() dead-code path
# ---------------------------------------------------------------------------

def test_generate_unified_plot_file_writes_module_plot_json(tmp_path, monkeypatch):
    """When `generate_unified_plot_file()` runs successfully, it must
    write the unified plot to `modules/<module_name>/module_plot.json`.
    Pre-fix the args were swapped: `save_json_safely(module_plot, path)`
    instead of `save_json_safely(path, module_plot)`, so the on-disk
    plot file was never created at the expected location."""
    module_name = "OWC2_TestPlotFile"

    # generate_unified_plot_file() writes to a HARDCODED relative path:
    # f"modules/{module_name.replace(' ', '_')}/module_plot.json".
    # chdir into tmp_path so writes land inside the sandbox.
    monkeypatch.chdir(tmp_path)

    module_dir = tmp_path / "modules" / module_name
    module_dir.mkdir(parents=True, exist_ok=True)

    # Seed the area file the function reads at f"{module_dir}/{area_id}.json".
    area_id = "AA01"
    area_payload = {"recommendedLevel": 1, "areaName": "Test Area"}
    with open(module_dir / f"{area_id}.json", "w", encoding="utf-8") as f:
        json.dump(area_payload, f)

    module_data = {
        "moduleName": module_name,
        "mainPlot": {
            "mainObjective": "Test objective",
            "plotStages": [
                {
                    "stageName": "Stage One",
                    "stageDescription": "First stage",
                    "keyNPCs": ["NPC One"],
                    "majorEvents": ["Event A"],
                },
            ],
        },
    }

    gen = _make_generator()

    # Should not raise.
    gen.generate_unified_plot_file(module_data, [area_id], module_name)

    expected_path = module_dir / "module_plot.json"
    assert expected_path.exists(), (
        f"module_plot.json was not written to expected path {expected_path}. "
        f"Pre-fix, the dict was passed as filepath so the file never got "
        f"created at this path. Files in module_dir: "
        f"{list(module_dir.iterdir())}"
    )

    with open(expected_path, "r", encoding="utf-8") as f:
        plot = json.load(f)

    assert plot.get("plotTitle") == module_name, (
        f"plotTitle mismatch. Got: {plot}"
    )
    assert plot.get("mainObjective") == "Test objective", (
        f"mainObjective mismatch. Got: {plot}"
    )
    assert isinstance(plot.get("plotPoints"), list), (
        f"plotPoints should be a list. Got: {plot}"
    )
    assert len(plot["plotPoints"]) == 1, (
        f"Expected 1 plot point from 1 stage. Got: {plot['plotPoints']}"
    )
    assert plot["plotPoints"][0]["id"] == "PP001", plot["plotPoints"][0]
    assert plot["plotPoints"][0]["title"] == "Stage One", plot["plotPoints"][0]
    assert plot["plotPoints"][0]["location"] == area_id, plot["plotPoints"][0]
