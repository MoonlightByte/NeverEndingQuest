"""
Tests for OW-C1: correct safe_write_json argument order in antagonist injection.

ModuleBuilder._inject_antagonist_into_climactic_location() was calling
safe_write_json(area_data, area_file_path) -- arguments REVERSED.

safe_write_json's real signature (utils/file_operations.py:278) is
    safe_write_json(filepath: str, data: Dict[str, Any], ...)

With the bug, the dict was passed as `filepath`, which raised an exception
inside the atomic writer. The atomic writer logs the error and returns False,
so the build did not crash -- but every successful build silently lost the
antagonist injection.

This test verifies:
1. The function writes the area file back to disk.
2. The antagonist NPC entry is present in the climactic (last) location's
   `npcs` array after the function returns.

We bypass ModuleBuilder.__init__ (which instantiates real generators that
call the OpenAI client) by allocating an instance via object.__new__ and
populating only the attributes the function under test reads:
    - self.module_data
    - self.config.output_directory
    - self.log  (just emits debug strings)
"""

import json
import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators.module_builder import ModuleBuilder


ANTAGONIST_NAME = "Lord Malagor the Cruel"
CLIMACTIC_AREA_ID = "SD001"


def _write_module_plot(output_dir: str, climactic_area_id: str) -> None:
    """Write a minimal module_plot.json whose final plot point points at
    the climactic area."""
    plot = {
        "plotPoints": [
            {"id": "PP001", "title": "Beginning", "location": "HH001"},
            {"id": "PP002", "title": "Climax", "location": climactic_area_id},
        ]
    }
    plot_path = os.path.join(output_dir, "module_plot.json")
    with open(plot_path, "w", encoding="utf-8") as f:
        json.dump(plot, f, indent=2)


def _write_area_file(output_dir: str, area_id: str) -> str:
    """Write a minimal area JSON file with two locations. The LAST location
    is the climactic one (per the current builder convention)."""
    area_data = {
        "areaId": area_id,
        "areaName": "Shadow Depths",
        "locations": [
            {
                "locationId": f"{area_id[0]}01",
                "name": "Approach Chamber",
                "description": "An anteroom.",
                "npcs": [],
            },
            {
                "locationId": f"{area_id[0]}02",
                "name": "Throne of Shadows",
                "description": "The final showdown room.",
                "npcs": [],
            },
        ],
    }
    areas_dir = os.path.join(output_dir, "areas")
    os.makedirs(areas_dir, exist_ok=True)
    area_path = os.path.join(areas_dir, f"{area_id}.json")
    with open(area_path, "w", encoding="utf-8") as f:
        json.dump(area_data, f, indent=2)
    return area_path


def _make_builder(output_directory: str, antagonist: str) -> ModuleBuilder:
    """Allocate a ModuleBuilder without running __init__, then set only the
    attributes the function under test needs."""
    builder = object.__new__(ModuleBuilder)
    builder.config = types.SimpleNamespace(
        output_directory=output_directory,
        verbose=False,
    )
    builder.module_data = {"mainPlot": {"antagonist": antagonist}}
    # log() reads self.config.verbose; with verbose=False it's a no-op,
    # but we still need the method bound. It's a regular method on the
    # class, so it's already accessible via the instance.
    return builder


def test_antagonist_injection_writes_file_with_antagonist(tmp_path):
    """End-to-end: after _inject_antagonist_into_climactic_location runs,
    the area file on disk must contain the antagonist NPC entry in the
    last (climactic) location's `npcs` array."""
    output_dir = str(tmp_path / "test_module")
    os.makedirs(output_dir, exist_ok=True)

    _write_module_plot(output_dir, CLIMACTIC_AREA_ID)
    area_path = _write_area_file(output_dir, CLIMACTIC_AREA_ID)

    builder = _make_builder(output_dir, ANTAGONIST_NAME)

    # Invoke the function under test. Pre-fix, safe_write_json gets a dict
    # as `filepath`, which raises inside the atomic writer; the write fails
    # and the on-disk file is unchanged from its initial state.
    builder._inject_antagonist_into_climactic_location()

    # Verify the file on disk was actually updated.
    with open(area_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    climactic_location = result["locations"][-1]
    npc_names = [npc.get("name") for npc in climactic_location.get("npcs", [])]
    assert ANTAGONIST_NAME in npc_names, (
        f"Antagonist '{ANTAGONIST_NAME}' was not written to the climactic "
        f"location. npcs on disk: {climactic_location.get('npcs')}"
    )

    # Verify the entry has the expected shape (matches module_builder.py
    # line 290-294).
    antagonist_entry = next(
        npc for npc in climactic_location["npcs"] if npc.get("name") == ANTAGONIST_NAME
    )
    assert antagonist_entry.get("attitude") == "hostile"
    assert "description" in antagonist_entry

    # Verify the non-climactic location was NOT modified.
    first_location = result["locations"][0]
    assert first_location.get("npcs") == [], (
        "Antagonist must only be injected into the LAST (climactic) location."
    )
