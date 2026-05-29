"""
Tests for INT-H6 (T2-4): persist `summary_failed` sentinel + add
`regenerate_failed_summary` helper on CampaignManager.

Bug: when AI summary generation fails inside
core/managers/campaign_manager.py::_generate_module_summary, the
fallback returns {"summary": "Module X was completed successfully."}
with NO exportedData key. Callers proceed normally; all relationships,
artifacts, hubs, world-state changes from the completed module are
silently lost. No regeneration path exists.

Fix:
1. The fallback dict in the except branch must now include
   `summary_failed=True`, `exportedData={}`, and an `error` string.
2. The success path must mark `summary_failed=False`.
3. A new `regenerate_failed_summary(module_name)` method must
   atomically overwrite a previously-failed summary with the
   regenerated success payload.
"""

import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402  (side-effect import: pulls in model_config.*)
import model_config  # noqa: E402
from core.managers import campaign_manager  # noqa: E402
from utils.encoding_utils import safe_json_dump  # noqa: E402


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_fake_response(payload):
    """Build a minimal object that quacks like an OpenAI ChatCompletion."""
    content = payload if isinstance(payload, str) else json.dumps(payload)
    msg = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=msg)
    return types.SimpleNamespace(choices=[choice])


def _make_cm_instance(summaries_dir=None, archives_dir=None):
    """Build a CampaignManager without running __init__ (which creates
    the OpenAI client and loads campaign files)."""
    inst = object.__new__(campaign_manager.CampaignManager)
    inst.client = MagicMock()
    inst._archive_conversation_history = MagicMock(return_value=True)
    inst._load_module_plot_data = MagicMock(return_value={"plotPoints": []})
    inst._process_module_summary_for_export = MagicMock(
        return_value={"local_fallback": True}
    )
    inst.summaries_dir = summaries_dir or "modules/campaign_summaries"
    inst.archives_dir = archives_dir or "modules/campaign_archives"
    return inst


# --------------------------------------------------------------------------
# Test 1: AI failure persists `summary_failed` sentinel + exportedData={}
# --------------------------------------------------------------------------

def test_generate_module_summary_marks_failed_when_ai_raises(monkeypatch):
    """When the T038 AI call raises, the returned dict must carry the
    `summary_failed=True` sentinel, `exportedData={}`, and an `error`
    field -- so downstream callers (and operators) can detect the gap
    and trigger regeneration. The original fallback `summary` stub
    text must still be present for backward compatibility."""

    monkeypatch.setattr(model_config, "MODEL_PROVIDER", "legacy", raising=True)
    monkeypatch.setattr(campaign_manager, "config", config, raising=True)

    def fake_capture_and_fanout(task_id, fn, **kwargs):
        # Simulate T038 (saga generation) blowing up. The except branch
        # in _generate_module_summary should catch it and return the
        # failure-sentinel payload.
        if task_id == "T038":
            raise RuntimeError("simulated upstream model failure")
        raise AssertionError(
            f"Should not reach T039 after T038 fails; got task_id={task_id}"
        )

    monkeypatch.setattr(
        campaign_manager, "capture_and_fanout",
        fake_capture_and_fanout, raising=True,
    )

    inst = _make_cm_instance()
    result = inst._generate_module_summary(
        module_name="TestModule",
        party_tracker_data={"partyNPCs": [], "activeQuests": []},
        conversation_history=[{"role": "user", "content": "hi"}],
        skip_archiving=True,
    )

    # Sentinel + empty exportedData are the load-bearing assertions.
    assert result.get("summary_failed") is True, (
        "Failed summary must set summary_failed=True so callers can "
        "detect and regenerate"
    )
    assert result.get("exportedData") == {}, (
        "Failed summary must include exportedData={} so the existing "
        "_handle_module_completion_export contract is preserved without "
        "silently importing stale or missing data"
    )
    # Error must carry the original exception message for diagnostics.
    assert "error" in result, "Failed summary must include error field"
    assert "simulated upstream model failure" in result["error"]

    # Backward-compat: the stub summary text must still be present
    # (legacy callers may have relied on its existence as a non-empty
    # string). moduleName / completionDate must also still be present.
    assert result.get("moduleName") == "TestModule"
    assert "completionDate" in result
    assert isinstance(result.get("summary"), str)
    assert len(result["summary"]) > 0


# --------------------------------------------------------------------------
# Test 2: regenerate_failed_summary overwrites the file with a fresh summary
# --------------------------------------------------------------------------

def test_regenerate_failed_summary_replaces_failed_file(tmp_path, monkeypatch):
    """Given a stored summary with summary_failed=True, the new
    regenerate_failed_summary(module_name) helper must:
    - re-run _generate_module_summary (with skip_archiving=True since
      the archive already exists from the original completion attempt),
    - atomically overwrite the summary file when the retry succeeds,
    - leave the resulting on-disk summary with summary_failed=False
      and a non-empty exportedData dict,
    - return True on success.
    """

    summaries_dir = tmp_path / "summaries"
    archives_dir = tmp_path / "archives"
    summaries_dir.mkdir()
    archives_dir.mkdir()

    module_name = "TestModule"
    summary_path = summaries_dir / f"{module_name}_summary_001.json"

    # Seed the directory with a previously-failed summary, exactly as
    # _generate_module_summary's except branch would have written it.
    failed_payload = {
        "moduleName": module_name,
        "completionDate": "2026-05-22T00:00:00",
        "summary": (
            f"Module {module_name} was completed successfully. "
            "(Summary generation failed - regenerate via "
            "campaign_manager.regenerate_failed_summary)"
        ),
        "exportedData": {},
        "summary_failed": True,
        "error": "simulated upstream model failure",
        "sequenceNumber": 1,
        "visitCount": 1,
        "firstVisitDate": "2026-05-22T00:00:00",
        "lastVisitDate": "2026-05-22T00:00:00",
    }
    safe_json_dump(failed_payload, str(summary_path))

    # Also seed an archive file so the regenerator can locate the
    # conversation history needed to retry. We use the same shape
    # _archive_conversation_history writes.
    archive_path = archives_dir / f"{module_name}_conversation_001.json"
    safe_json_dump(
        {
            "moduleName": module_name,
            "sequenceNumber": 1,
            "archiveDate": "2026-05-22T00:00:00",
            "conversationHistory": [
                {"role": "user", "content": "we slew the dragon"},
                {"role": "assistant", "content": "victory!"},
            ],
            "totalMessages": 2,
        },
        str(archive_path),
    )

    monkeypatch.setattr(model_config, "MODEL_PROVIDER", "legacy", raising=True)
    monkeypatch.setattr(campaign_manager, "config", config, raising=True)

    # This time the AI calls succeed. T038 returns a saga; T039 returns
    # a valid exportedData JSON object.
    def fake_capture_and_fanout(task_id, fn, **kwargs):
        if task_id == "T038":
            return _make_fake_response(
                "The party slew the dragon and saved the village."
            )
        if task_id == "T039":
            return _make_fake_response({
                "relationships": {"Innkeeper Bron": "grateful"},
                "artifacts": {"Dragonbone Sword": {"location": "vault"}},
                "hubs": {},
                "worldState": {"dragon_threat": "ended"},
                "unlockedModules": ["NextModule"],
            })
        raise AssertionError(f"Unexpected task_id: {task_id}")

    monkeypatch.setattr(
        campaign_manager, "capture_and_fanout",
        fake_capture_and_fanout, raising=True,
    )

    inst = _make_cm_instance(
        summaries_dir=str(summaries_dir),
        archives_dir=str(archives_dir),
    )

    # Method under test.
    assert hasattr(inst, "regenerate_failed_summary"), (
        "CampaignManager must expose regenerate_failed_summary(module_name)"
    )

    ok = inst.regenerate_failed_summary(module_name)
    assert ok is True, "regenerate_failed_summary must return True on success"

    # On-disk file must now reflect the regenerated summary.
    with open(str(summary_path), "r", encoding="utf-8") as f:
        new_payload = json.load(f)

    assert new_payload.get("summary_failed") is False, (
        "Regenerated summary must clear summary_failed"
    )
    assert new_payload.get("exportedData"), (
        "Regenerated summary must populate exportedData"
    )
    assert new_payload["exportedData"].get("unlockedModules") == ["NextModule"]
    assert new_payload.get("moduleName") == module_name
    # The saga text from T038 must replace the stub.
    assert "dragon" in new_payload.get("summary", "").lower()


def test_regenerate_failed_summary_returns_false_when_nothing_to_regenerate(
    tmp_path, monkeypatch,
):
    """If the stored summary is already healthy (summary_failed False or
    absent), regenerate_failed_summary must be a no-op returning False."""
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()

    module_name = "HealthyModule"
    summary_path = summaries_dir / f"{module_name}_summary_001.json"
    safe_json_dump(
        {
            "moduleName": module_name,
            "completionDate": "2026-05-22T00:00:00",
            "summary": "An actual saga.",
            "exportedData": {"relationships": {"X": "Y"}},
            "summary_failed": False,
            "sequenceNumber": 1,
        },
        str(summary_path),
    )

    # If the regenerator accidentally re-runs _generate_module_summary
    # we want the test to scream loudly.
    def fake_capture_and_fanout(task_id, fn, **kwargs):
        raise AssertionError(
            "regenerate_failed_summary must NOT re-run the AI when there "
            "is nothing to regenerate"
        )

    monkeypatch.setattr(
        campaign_manager, "capture_and_fanout",
        fake_capture_and_fanout, raising=True,
    )

    inst = _make_cm_instance(summaries_dir=str(summaries_dir))
    assert inst.regenerate_failed_summary(module_name) is False
