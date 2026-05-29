"""Tests for OW-H5: add missing f-string prefix in MODULE_SUMMARY.md template.

ModuleBuilder.create_module_summary() in core/generators/module_builder.py
opens a triple-quoted string at line 1087 without an `f` prefix. The string
body contains placeholders referencing self.module_data['mainPlot']['mainObjective']
and self.module_data['mainPlot']['antagonist'].

Because the string is not an f-string, those placeholders are written
LITERALLY to MODULE_SUMMARY.md -- every generated module has gobbledygook
in the Main Plot section instead of the real objective and antagonist.

This test verifies:
1. After create_module_summary() runs, the on-disk MODULE_SUMMARY.md
   contains the interpolated values (e.g. "Defeat dragon", "Drakar").
2. The file does NOT contain the literal placeholder text
   "{self.module_data" (which would indicate the f-prefix is missing).

We bypass ModuleBuilder.__init__ (which instantiates real generators that
call the OpenAI client) by allocating an instance via object.__new__ and
populating only the attributes create_module_summary() reads:
    - self.module_data    (moduleName, moduleDescription, mainPlot)
    - self.areas_data     (one area is enough)
    - self.plots_data     (matched to the area id)
    - self.config         (output_directory, verbose)
"""

import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators.module_builder import ModuleBuilder


MAIN_OBJECTIVE = "Defeat dragon"
ANTAGONIST = "Drakar"


def _make_builder(output_directory: str) -> ModuleBuilder:
    """Allocate a ModuleBuilder without running __init__, then set only
    the attributes create_module_summary() reads."""
    builder = object.__new__(ModuleBuilder)
    builder.config = types.SimpleNamespace(
        output_directory=output_directory,
        verbose=False,
    )
    builder.module_data = {
        "moduleName": "Test Module",
        "moduleDescription": "A minimal module for unit testing.",
        "mainPlot": {
            "mainObjective": MAIN_OBJECTIVE,
            "antagonist": ANTAGONIST,
        },
    }
    # One area with one location is enough; create_module_summary iterates
    # areas_data and per-area plots_data to emit the Areas section.
    builder.areas_data = {
        "HH001": {
            "areaName": "Test Area",
            "areaDescription": "An empty test area.",
            "dangerLevel": "low",
            "recommendedLevel": 1,
            "locations": [
                {"locationId": "H01", "name": "Start", "description": "."}
            ],
        }
    }
    builder.plots_data = {
        "HH001": {
            "plotTitle": "Test Plot",
            "mainObjective": "Test objective.",
            "plotPoints": [{"description": "Begin the test."}],
        }
    }
    return builder


def test_module_summary_interpolates_main_plot_fields(tmp_path):
    """End-to-end: after create_module_summary() runs, MODULE_SUMMARY.md
    on disk must contain the interpolated mainObjective and antagonist,
    and must NOT contain the literal placeholder text that would indicate
    a missing f-string prefix."""
    output_dir = str(tmp_path / "test_module")
    os.makedirs(output_dir, exist_ok=True)

    builder = _make_builder(output_dir)
    builder.create_module_summary()

    summary_path = os.path.join(output_dir, "MODULE_SUMMARY.md")
    assert os.path.exists(summary_path), "MODULE_SUMMARY.md was not written"

    with open(summary_path, "r", encoding="utf-8") as f:
        content = f.read()

    # The interpolated values must appear in the file.
    assert MAIN_OBJECTIVE in content, (
        f"Expected interpolated mainObjective '{MAIN_OBJECTIVE}' in "
        f"MODULE_SUMMARY.md, but it was not found. Content:\n{content}"
    )
    assert ANTAGONIST in content, (
        f"Expected interpolated antagonist '{ANTAGONIST}' in "
        f"MODULE_SUMMARY.md, but it was not found. Content:\n{content}"
    )

    # The literal placeholder text must NOT appear (which would indicate
    # the triple-quoted block at module_builder.py:1087 is missing its
    # `f` prefix and the placeholders were written verbatim).
    assert "{self.module_data" not in content, (
        "MODULE_SUMMARY.md contains literal placeholder text "
        "'{self.module_data' -- the f-string prefix is missing at "
        "module_builder.py:1087. Content:\n" + content
    )
