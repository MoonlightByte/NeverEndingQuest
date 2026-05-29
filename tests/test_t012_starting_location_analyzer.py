"""
Test for INT-L3 (T2-2): T012 starting-location analysis sub-call must route
through the provider-aware router, not the raw OpenAI client.

The T012 callsite lives inside _ai_analyze_starting_location at
core/ai/action_handler.py (~line 555). Before the fix it called
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    capture_and_fanout("T012", client.chat.completions.create, ...)
which is the raw OpenAI client and bypasses model_config.MODEL_PROVIDER
entirely -- it hard-fails on Gemini/LM Studio and always uses OpenAI
even when the operator selects another provider.

After the fix the callsite must:
1. Branch on MODEL_PROVIDER to pick a DM_LOCSTART_T012_* config dict.
2. Call api_client.create_completion (via capture_and_fanout) using the
   selected config dict's "model" key plus any provider-specific params
   (reasoning_effort, thinking_level, ...).
3. Preserve temperature=0.1 at the callsite (per per-callsite-config rule).
4. Preserve the existing system + user prompt content verbatim.
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Importing config is enough -- it imports model_config.* via `from model_config import *`
import config
import model_config
from core.ai import action_handler


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_fake_response(json_payload):
    """Build a minimal object that quacks like an OpenAI ChatCompletion: it
    has `.choices[0].message.content` returning the JSON-serialised payload."""
    msg = types.SimpleNamespace(content=json.dumps(json_payload))
    choice = types.SimpleNamespace(message=msg)
    return types.SimpleNamespace(choices=[choice])


# A minimal but realistic module_data the function knows how to parse.
SAMPLE_MODULE_DATA = {
    "moduleName": "TestModule",
    "areas": {
        "TT001": {
            "areaName": "Town of Test",
            "locations": [
                {"locationId": "A01", "name": "Town Square"},
                {"locationId": "A02", "name": "Inn"},
            ],
        },
    },
    "plotData": {
        "mainObjective": "Save the kingdom",
        "plotPoints": [{"id": "PP001", "description": "Arrive at the town"}],
    },
}


def _run_analyzer(provider, monkeypatch):
    """Drive _ai_analyze_starting_location with provider patched and
    capture_and_fanout intercepted so we can inspect what model the T012
    sub-call requested."""
    monkeypatch.setattr(model_config, "MODEL_PROVIDER", provider, raising=True)
    # The callsite imports MODEL_PROVIDER from model_config inside the function
    # body each call, so patching model_config.MODEL_PROVIDER is sufficient.
    monkeypatch.setattr(action_handler, "config", config, raising=True)

    seen_calls = []

    def fake_capture_and_fanout(task_id, fn, **kwargs):
        seen_calls.append({"task_id": task_id, "fn": fn, "kwargs": kwargs})
        if task_id == "T012":
            # Return a valid JSON payload the analyzer can parse.
            return _make_fake_response({
                "locationId": "A01",
                "locationName": "Town Square",
                "areaId": "TT001",
                "areaName": "Town of Test",
                "reasoning": "PP001 indicates this is the arrival point.",
            })
        raise AssertionError(f"Unexpected task_id: {task_id}")

    monkeypatch.setattr(action_handler, "capture_and_fanout",
                        fake_capture_and_fanout, raising=True)

    result = action_handler._ai_analyze_starting_location(SAMPLE_MODULE_DATA)
    return result, seen_calls


# --------------------------------------------------------------------------
# The four provider parameterisations
# --------------------------------------------------------------------------

EXPECTED = {
    "openai":   ("DM_LOCSTART_T012_GPT5MINI",                 "gpt-5-mini"),
    "gemini":   ("DM_LOCSTART_T012_GEMINI_FLASHLITE_MINIMAL", "gemini-3.1-flash-lite-preview"),
    "lmstudio": ("DM_LOCSTART_T012_LMSTUDIO",                 "local-model"),
    "legacy":   ("DM_LOCSTART_T012_LEGACY",                   "gpt-4.1-mini-2025-04-14"),
}


@pytest.mark.parametrize("provider", list(EXPECTED.keys()))
def test_t012_routes_through_provider_aware_router(provider, monkeypatch):
    cfg_name, expected_model = EXPECTED[provider]

    # Sanity: the named config dict exists and has the expected model string.
    assert hasattr(config, cfg_name), \
        f"model_config.{cfg_name} must be defined for T012 routing"
    assert getattr(config, cfg_name)["model"] == expected_model

    result, calls = _run_analyzer(provider, monkeypatch)

    # T012 must have been captured-and-fanned-out.
    task_ids = [c["task_id"] for c in calls]
    assert "T012" in task_ids, "T012 capture call missing"
    t012 = next(c for c in calls if c["task_id"] == "T012")

    # T012 must invoke the router, NOT the raw OpenAI client.
    from core.ai import api_client
    assert t012["fn"] is api_client.create_completion, (
        f"T012 must call api_client.create_completion, got {t012['fn']!r}"
    )

    # The router must be handed the right model string for this provider.
    assert t012["kwargs"]["model"] == expected_model, (
        f"provider={provider}: expected model={expected_model}, "
        f"got {t012['kwargs'].get('model')!r}"
    )

    # Temperature stays at the callsite (rule from CLAUDE.md).
    assert t012["kwargs"].get("temperature") == 0.1, (
        "T012 must preserve temperature=0.1 at the callsite"
    )

    # The system prompt text must be preserved verbatim (sentinel phrase check).
    msgs = t012["kwargs"]["messages"]
    assert msgs[0]["role"] == "system"
    assert "5th edition adventure module analyst" in msgs[0]["content"]
    assert "Use the EXACT locationId and areaId" in msgs[0]["content"]

    # The user prompt must include the serialised module data (sentinel check).
    assert msgs[1]["role"] == "user"
    assert "MODULE DATA:" in msgs[1]["content"]
    assert "Town of Test" in msgs[1]["content"]  # confirms module_data was inlined

    # Provider-specific params (reasoning_effort / thinking_level) must be
    # forwarded -- but only those that are part of the config dict, never
    # synthesised, never injected by the router.
    cfg = getattr(config, cfg_name)
    for k, v in cfg.items():
        if k == "model":
            continue
        assert t012["kwargs"].get(k) == v, (
            f"provider={provider}: expected {k}={v}, "
            f"got {t012['kwargs'].get(k)!r}"
        )

    # And: the result tuple must be correctly extracted from the fake response.
    assert result == ("A01", "Town Square", "TT001", "Town of Test")


def test_t012_passes_router_function_not_raw_client(monkeypatch):
    """Strict regression guard: the function-reference handed to
    capture_and_fanout() for T012 must be api_client.create_completion,
    NOT a method of a raw OpenAI client instance.

    This test would have caught the original INT-L3 bug directly: pre-fix
    the wrapper sees fn = <bound method of OpenAI client>, post-fix it
    sees fn = <function api_client.create_completion>.
    """
    from core.ai import api_client

    monkeypatch.setattr(model_config, "MODEL_PROVIDER", "openai", raising=True)
    monkeypatch.setattr(action_handler, "config", config, raising=True)

    fn_for_t012 = []

    def fake_capture_and_fanout(task_id, fn, **kwargs):
        if task_id == "T012":
            fn_for_t012.append(fn)
            return _make_fake_response({
                "locationId": "A01",
                "locationName": "Town Square",
                "areaId": "TT001",
                "areaName": "Town of Test",
                "reasoning": "test",
            })
        raise AssertionError(f"Unexpected task_id: {task_id}")

    monkeypatch.setattr(action_handler, "capture_and_fanout",
                        fake_capture_and_fanout, raising=True)

    action_handler._ai_analyze_starting_location(SAMPLE_MODULE_DATA)

    assert len(fn_for_t012) == 1, "T012 capture call missing"
    assert fn_for_t012[0] is api_client.create_completion, (
        "T012 must hand api_client.create_completion to capture_and_fanout; "
        f"got {fn_for_t012[0]!r} -- this likely means the raw OpenAI client "
        "is being used (INT-L3 regression)."
    )


def test_t012_capture_config_registered():
    """T012 should be registered in TASK_CAPTURE_CONFIGS so capture-and-fanout
    uses the per-callsite variants instead of falling back to tier defaults."""
    assert "T012" in model_config.TASK_CAPTURE_CONFIGS, (
        "T012 must be registered in TASK_CAPTURE_CONFIGS so capture testing "
        "uses the DM_LOCSTART_T012_* variants for this callsite."
    )
    openai_var, gemini_var = model_config.TASK_CAPTURE_CONFIGS["T012"]
    assert openai_var == "DM_LOCSTART_T012_GPT5MINI"
    assert gemini_var == "DM_LOCSTART_T012_GEMINI_FLASHLITE_MINIMAL"
