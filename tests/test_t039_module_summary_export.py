"""
Test for INT-C1 (T2-1): T039 campaign export sub-call must route through the
provider-aware router, not the raw OpenAI client.

The T039 callsite lives inside CampaignManager._generate_module_summary at
core/managers/campaign_manager.py (~line 634). Before the fix it called
    self.client.chat.completions.create(...)
which is the raw OpenAI client and bypasses model_config.MODEL_PROVIDER
entirely -- it hard-fails on Gemini/LM Studio and always uses OpenAI
even when the operator selects another provider.

After the fix the callsite must:
1. Branch on MODEL_PROVIDER to pick a DM_SUMMARY_* config dict.
2. Call api_client.create_completion (via capture_and_fanout) using the
   selected config dict's "model" key plus any provider-specific params
   (reasoning_effort, thinking_level, ...).
3. Preserve temperature=0.3 at the callsite (per per-callsite-config rule).
4. Preserve the existing system + user prompt content verbatim.
"""

import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Importing config is enough -- it imports model_config.* via `from model_config import *`
import config
import model_config
from core.managers import campaign_manager


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_fake_response(json_payload):
    """Build a minimal object that quacks like an OpenAI ChatCompletion: it
    has `.choices[0].message.content` returning the JSON-serialised payload."""
    msg = types.SimpleNamespace(content=json.dumps(json_payload))
    choice = types.SimpleNamespace(message=msg)
    return types.SimpleNamespace(choices=[choice])


def _make_cm_instance():
    """Build a CampaignManager without running __init__ (which creates
    the OpenAI client and loads campaign files). We only need the methods
    that _generate_module_summary touches via self.* during the T039 call."""
    inst = object.__new__(campaign_manager.CampaignManager)
    # _archive_conversation_history is invoked unconditionally unless we pass
    # skip_archiving=True (we will). _process_module_summary_for_export is the
    # error fallback -- if T039 throws, we end up there.
    inst.client = MagicMock()  # would be the raw OpenAI client
    inst._archive_conversation_history = MagicMock(return_value=True)
    inst._load_module_plot_data = MagicMock(return_value={"plotPoints": []})
    inst._process_module_summary_for_export = MagicMock(return_value={"fallback": True})
    return inst


def _run_generate_summary(provider, monkeypatch):
    """Drive _generate_module_summary with provider patched and both
    api_client.create_completion + capture_and_fanout intercepted so we can
    inspect what model the T039 sub-call requested."""
    monkeypatch.setattr(model_config, "MODEL_PROVIDER", provider, raising=True)
    # The callsite imports MODEL_PROVIDER from model_config inside the function
    # body each call, so patching model_config.MODEL_PROVIDER is sufficient
    # and we also patch the campaign_manager module just in case it caches it.
    monkeypatch.setattr(campaign_manager, "config", config, raising=True)

    # The T038 call (saga generation) and the T039 call (export extraction)
    # both route through capture_and_fanout(...). We intercept it.
    seen_calls = []
    def fake_capture_and_fanout(task_id, fn, **kwargs):
        seen_calls.append({"task_id": task_id, "fn": fn, "kwargs": kwargs})
        if task_id == "T038":
            # T038 returns the human-readable saga text.
            return _make_fake_response("Once upon a time in the Thornwood...")
        if task_id == "T039":
            # T039 must return a valid JSON object the callsite can json.loads.
            return _make_fake_response({
                "relationships": {},
                "artifacts": {},
                "hubs": {},
                "worldState": {},
                "unlockedModules": []
            })
        raise AssertionError(f"Unexpected task_id: {task_id}")

    monkeypatch.setattr(campaign_manager, "capture_and_fanout",
                        fake_capture_and_fanout, raising=True)

    inst = _make_cm_instance()
    party_tracker = {"partyNPCs": [], "activeQuests": []}
    summary = inst._generate_module_summary(
        module_name="TestModule",
        party_tracker_data=party_tracker,
        conversation_history=[{"role": "user", "content": "hi"}],
        skip_archiving=True,
    )
    return summary, seen_calls


# --------------------------------------------------------------------------
# The four provider parameterisations
# --------------------------------------------------------------------------

EXPECTED = {
    "openai":   ("DM_SUMMARY_GPT5MINI",            "gpt-5-mini"),
    "gemini":   ("DM_SUMMARY_GEMINI_FLASH_MINIMAL","gemini-3.1-flash-lite-preview"),
    "lmstudio": ("DM_SUMMARY_LMSTUDIO",            "local-model"),
    "legacy":   ("DM_SUMMARY_LEGACY",              "gpt-4.1-mini-2025-04-14"),
}


@pytest.mark.parametrize("provider", list(EXPECTED.keys()))
def test_t039_routes_through_provider_aware_router(provider, monkeypatch):
    cfg_name, expected_model = EXPECTED[provider]

    # Sanity: the named config dict exists and has the expected model string.
    assert hasattr(config, cfg_name), \
        f"model_config.{cfg_name} must be defined for T039 routing"
    assert getattr(config, cfg_name)["model"] == expected_model

    summary, calls = _run_generate_summary(provider, monkeypatch)

    # Both T038 and T039 must have been captured-and-fanned-out.
    task_ids = [c["task_id"] for c in calls]
    assert "T039" in task_ids, "T039 capture call missing"
    t039 = next(c for c in calls if c["task_id"] == "T039")

    # T039 must invoke the router, NOT the raw OpenAI client.
    from core.ai import api_client
    assert t039["fn"] is api_client.create_completion, (
        f"T039 must call api_client.create_completion, got {t039['fn']!r}"
    )

    # The router must be handed the right model string for this provider.
    assert t039["kwargs"]["model"] == expected_model, (
        f"provider={provider}: expected model={expected_model}, "
        f"got {t039['kwargs'].get('model')!r}"
    )

    # Temperature stays at the callsite (rule from CLAUDE.md).
    assert t039["kwargs"].get("temperature") == 0.3, (
        "T039 must preserve temperature=0.3 at the callsite"
    )

    # The system prompt text must be preserved verbatim.
    msgs = t039["kwargs"]["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == (
        "Extract campaign-relevant data from module completion summary. "
        "Be concise and factual."
    )

    # Provider-specific params (reasoning_effort / thinking_level) must be
    # forwarded -- but only those that are part of the config dict, never
    # synthesised, never injected by the router.
    cfg = getattr(config, cfg_name)
    for k, v in cfg.items():
        if k == "model":
            continue
        assert t039["kwargs"].get(k) == v, (
            f"provider={provider}: expected {k}={v}, "
            f"got {t039['kwargs'].get(k)!r}"
        )

    # And: the fallback _process_module_summary_for_export must NOT have
    # fired -- T039 succeeded and we used its parsed JSON.
    # (summary["exportedData"] is whatever fake_capture_and_fanout returned)
    assert "exportedData" in summary
    assert summary["exportedData"].get("unlockedModules") == []


def test_t039_passes_router_function_not_raw_client(monkeypatch):
    """Strict regression guard: the function-reference handed to
    capture_and_fanout() for T039 must be api_client.create_completion,
    NOT self.client.chat.completions.create.

    This test would have caught the original INT-C1 bug directly: pre-fix
    the wrapper sees fn = <bound method of OpenAI client>, post-fix it
    sees fn = <function api_client.create_completion>.
    """
    from core.ai import api_client

    inst = _make_cm_instance()
    monkeypatch.setattr(model_config, "MODEL_PROVIDER", "openai", raising=True)
    monkeypatch.setattr(campaign_manager, "config", config, raising=True)

    fn_for_t039 = []

    def fake_capture_and_fanout(task_id, fn, **kwargs):
        if task_id == "T039":
            fn_for_t039.append(fn)
            return _make_fake_response({
                "relationships": {}, "artifacts": {}, "hubs": {},
                "worldState": {}, "unlockedModules": [],
            })
        if task_id == "T038":
            return _make_fake_response("saga text")
        raise AssertionError(f"Unexpected task_id: {task_id}")

    monkeypatch.setattr(campaign_manager, "capture_and_fanout",
                        fake_capture_and_fanout, raising=True)

    inst._generate_module_summary(
        module_name="TestModule",
        party_tracker_data={"partyNPCs": [], "activeQuests": []},
        conversation_history=[{"role": "user", "content": "hi"}],
        skip_archiving=True,
    )

    assert len(fn_for_t039) == 1, "T039 capture call missing"
    assert fn_for_t039[0] is api_client.create_completion, (
        "T039 must hand api_client.create_completion to capture_and_fanout; "
        f"got {fn_for_t039[0]!r} -- this likely means the raw OpenAI client "
        "is being used (INT-C1 regression)."
    )
