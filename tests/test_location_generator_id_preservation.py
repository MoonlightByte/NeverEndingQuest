"""
Tests for MP-C1: location_generator must instruct AI to preserve locationId
values from input stubs, and must post-process / validate the IDs returned.

Background (MP-C1):
  ``LocationGenerator.generate_location_batch`` builds the T026 batch prompt
  inline in code. The prompt previously did NOT tell the AI to preserve the
  locationId values from the stubs. As a result, the AI frequently invented
  new IDs (often R-prefixed because R-format examples appear in the prompt
  templates), and the map grid's IDs were effectively replaced.

This file pins down three contracts:

  1. (prompt content) The inline batch_prompt MUST contain an explicit
     CRITICAL instruction telling the AI to use the exact locationId values
     from the stubs.

  2. (happy path) When the mocked AI returns locations whose locationId
     values exactly match the input stubs, ``generate_locations`` returns
     them unchanged and does NOT raise.

  3. (significant drift) When the mocked AI returns locations whose
     locationId values do NOT match the input stubs (>30% drift, e.g. all
     R-prefixed instead of A-prefixed), ``generate_location_batch`` MUST
     raise ``ValueError`` to signal the batch should be retried or fail.

These tests do NOT hit any AI generation paths; the underlying
``capture_and_fanout`` (and the OpenAI client it routes to) is monkeypatched
to a deterministic stub. The tests also do not exercise the schema loader,
so ``LocationGenerator.load_schema`` is patched to a no-op.
"""

import os
import sys
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_generator():
    """Instantiate LocationGenerator without touching the real schema file."""
    from core.generators.location_generator import LocationGenerator

    with patch.object(LocationGenerator, "load_schema", return_value={}):
        return LocationGenerator()


def _stub_area_data(stub_ids):
    """Build minimal area_data with a map whose rooms use the given IDs."""
    rooms = []
    for i, lid in enumerate(stub_ids):
        rooms.append({
            "id": lid,
            "name": f"Room {lid}",
            "type": "chamber",
            "connections": [],
            "coordinates": [i, 0],
        })
    return {
        "areaId": "A1",
        "areaName": "Test Area",
        "areaType": "dungeon",
        "areaDescription": "A test area",
        "dangerLevel": "medium",
        "recommendedLevel": 1,
        "map": {"rooms": rooms},
    }


def _stub_plot_data():
    return {
        "plotTitle": "Stub Plot",
        "mainObjective": "Test objective",
        "plotPoints": [
            {"id": "PP001", "title": "Start", "description": "Begin", "location": ""},
        ],
    }


def _stub_module_data():
    return {
        "moduleName": "Test Module",
        "moduleDescription": "For testing",
        "worldSettings": {"era": "medieval", "magicPrevalence": "low"},
    }


def _ai_response(locations):
    """Wrap a list of locations into the shape generate_location_batch expects."""
    content = json.dumps({"locations": locations})
    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def _location(lid):
    """Minimal location object with the given locationId."""
    return {
        "locationId": lid,
        "name": f"Room {lid}",
        "type": "chamber",
        "connectivity": [],
        "areaConnectivity": [],
        "areaConnectivityId": [],
    }


# ---------------------------------------------------------------------------
# Test 1: prompt contains the CRITICAL preservation instruction
# ---------------------------------------------------------------------------


def test_batch_prompt_contains_preserve_locationid_instruction():
    """The T026 batch_prompt MUST instruct the AI to preserve locationIds.

    We capture the prompt passed to capture_and_fanout and assert that the
    user message body contains an explicit, unambiguous CRITICAL instruction
    naming the locationId field by name.
    """
    gen = _make_generator()
    stub_ids = ["A01", "A02"]
    area = _stub_area_data(stub_ids)
    plot = _stub_plot_data()
    module = _stub_module_data()
    stubs = [
        {"locationId": "A01", "name": "Room A01", "type": "chamber",
         "connections": [], "coordinates": [0, 0]},
        {"locationId": "A02", "name": "Room A02", "type": "chamber",
         "connections": [], "coordinates": [1, 0]},
    ]

    captured = {}

    def _fake_capture(task_id, fn, **kwargs):
        captured["task_id"] = task_id
        captured["messages"] = kwargs.get("messages")
        # Return a well-formed response so generate_location_batch doesn't blow up.
        return _ai_response([_location("A01"), _location("A02")])

    with patch("core.generators.location_generator.capture_and_fanout",
               side_effect=_fake_capture):
        gen.generate_location_batch(area, plot, module, stubs)

    assert captured["task_id"] == "T026"
    assert captured["messages"] is not None
    # The user message holds the batch_prompt body.
    user_msg = next(m for m in captured["messages"] if m["role"] == "user")
    body = user_msg["content"]
    # Required exact phrase from the task spec:
    assert "CRITICAL: You MUST use the exact locationId values" in body, (
        "batch_prompt is missing the locationId-preservation CRITICAL instruction.\n"
        "Got:\n" + body
    )
    # Belt-and-suspenders -- the instruction must mention not changing them.
    assert "Do not change, rename, or replace any locationId" in body


# ---------------------------------------------------------------------------
# Test 2: happy path -- IDs match, no error, locations returned
# ---------------------------------------------------------------------------


def test_generate_locations_passes_through_when_ids_match():
    """When the AI returns the same IDs that were in the stubs, the pipeline
    returns the locations unchanged and does not raise."""
    gen = _make_generator()
    stub_ids = ["A01", "A02"]
    area = _stub_area_data(stub_ids)
    plot = _stub_plot_data()
    module = _stub_module_data()

    def _fake_capture(task_id, fn, **kwargs):
        return _ai_response([_location("A01"), _location("A02")])

    with patch("core.generators.location_generator.capture_and_fanout",
               side_effect=_fake_capture):
        result = gen.generate_locations(area, plot, module)

    returned_ids = sorted(loc["locationId"] for loc in result["locations"])
    assert returned_ids == ["A01", "A02"]


# ---------------------------------------------------------------------------
# Test 3: significant drift -- raise ValueError
# ---------------------------------------------------------------------------


def test_generate_location_batch_rejects_significant_id_drift():
    """When the AI invents completely different IDs (>30% drift), the batch
    must be rejected with a ValueError so the caller can retry or fail."""
    gen = _make_generator()
    stub_ids = ["A01", "A02", "A03", "A04"]
    area = _stub_area_data(stub_ids)
    plot = _stub_plot_data()
    module = _stub_module_data()
    stubs = [
        {"locationId": lid, "name": f"Room {lid}", "type": "chamber",
         "connections": [], "coordinates": [i, 0]}
        for i, lid in enumerate(stub_ids)
    ]

    # AI renames everything (100% drift) -- classic MP-C1 failure mode.
    drifted = [_location("R01"), _location("R02"), _location("R03"), _location("R04")]

    def _fake_capture(task_id, fn, **kwargs):
        return _ai_response(drifted)

    with patch("core.generators.location_generator.capture_and_fanout",
               side_effect=_fake_capture):
        with pytest.raises(ValueError) as exc_info:
            gen.generate_location_batch(area, plot, module, stubs)

    # The message should describe the drift problem so failures are debuggable.
    msg = str(exc_info.value).lower()
    assert "locationid" in msg or "location id" in msg


def test_generate_location_batch_allows_minor_id_drift_with_warning(capsys):
    """When the AI renames a small fraction of IDs (<=30%), we warn but do
    not reject -- the post-process pipeline still has to do something useful
    with what came back."""
    gen = _make_generator()
    stub_ids = ["A01", "A02", "A03", "A04", "A05"]
    area = _stub_area_data(stub_ids)
    plot = _stub_plot_data()
    module = _stub_module_data()
    stubs = [
        {"locationId": lid, "name": f"Room {lid}", "type": "chamber",
         "connections": [], "coordinates": [i, 0]}
        for i, lid in enumerate(stub_ids)
    ]

    # 1 of 5 IDs drifted (20%) -- under threshold.
    partial = [
        _location("A01"),
        _location("A02"),
        _location("A03"),
        _location("A04"),
        _location("R05"),  # drifted
    ]

    def _fake_capture(task_id, fn, **kwargs):
        return _ai_response(partial)

    with patch("core.generators.location_generator.capture_and_fanout",
               side_effect=_fake_capture):
        result = gen.generate_location_batch(area, plot, module, stubs)

    # Should not raise; should return the AI's output.
    returned_ids = sorted(loc["locationId"] for loc in result["locations"])
    assert returned_ids == ["A01", "A02", "A03", "A04", "R05"]

    # A warning should be emitted on stdout (matches existing print-based pattern).
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "R05" in combined, "Expected warning to mention the drifted ID"
