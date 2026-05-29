"""
Test for XS-4 (T2-8): T049 storage-processor AI sub-call must route through
the provider-aware router, not the raw OpenAI client.

The T049 callsite lives inside StorageProcessor.process_storage_description at
core/managers/storage_processor.py (~line 286). Before the fix it called
    self.client = OpenAI(api_key=config.OPENAI_API_KEY)
    capture_and_fanout("T049", self.client.chat.completions.create, ...)
which is the raw OpenAI client and bypasses model_config.MODEL_PROVIDER
entirely -- it hard-fails on Gemini/LM Studio and always uses OpenAI
even when the operator selects another provider.

After the fix the callsite must:
1. Branch on MODEL_PROVIDER to pick a STORAGE_PROCESSOR_T049_* config dict.
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
from core.managers import storage_processor as storage_processor_mod


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_fake_response(json_payload):
    """Build a minimal object that quacks like an OpenAI ChatCompletion: it
    has `.choices[0].message.content` returning the JSON-serialised payload."""
    msg = types.SimpleNamespace(content=json.dumps(json_payload))
    choice = types.SimpleNamespace(message=msg)
    return types.SimpleNamespace(choices=[choice])


def _build_processor_without_ctor(monkeypatch):
    """Construct a StorageProcessor without running its __init__ -- the ctor
    touches the filesystem (party_tracker.json, schemas/) and an OpenAI client
    we do not want for unit testing. We patch the bits the method under test
    actually reads."""
    sp = storage_processor_mod.StorageProcessor.__new__(
        storage_processor_mod.StorageProcessor)
    # The fix removes the .model attribute dependency at the callsite, but the
    # legacy code reads self.model. Set it to a sentinel so any leftover
    # reference would be obvious.
    sp.model = "sentinel-should-not-be-used-after-fix"
    sp.client = MagicMock(name="raw_openai_client_should_not_be_called")
    sp.path_manager = MagicMock()
    sp.schema = {}
    sp.schema_file = "schemas/storage_action_schema.json"
    # _get_game_context is its own thing -- stub it.
    monkeypatch.setattr(sp, "_get_game_context",
                        lambda character_name: {"character": {"name": character_name}},
                        raising=False)
    # _validate_operation must not run real schema validation.
    monkeypatch.setattr(sp, "_validate_operation",
                        lambda op: {"valid": True, "errors": []},
                        raising=False)
    # _execute_operation must not actually touch storage state.
    monkeypatch.setattr(sp, "_execute_operation",
                        lambda op: {"success": True, "message": "ok"},
                        raising=False)
    return sp


def _run_processor(provider, monkeypatch):
    """Drive StorageProcessor.process_storage_description with provider
    patched and capture_and_fanout intercepted so we can inspect what model
    the T049 sub-call requested."""
    # storage_processor binds MODEL_PROVIDER at import time
    # (`from model_config import MODEL_PROVIDER`), so we patch the name
    # in the storage_processor module's namespace -- patching model_config
    # alone would not flow through.
    monkeypatch.setattr(storage_processor_mod, "MODEL_PROVIDER", provider, raising=True)
    monkeypatch.setattr(storage_processor_mod, "config", config, raising=True)

    sp = _build_processor_without_ctor(monkeypatch)

    seen_calls = []

    def fake_capture_and_fanout(task_id, fn, **kwargs):
        seen_calls.append({"task_id": task_id, "fn": fn, "kwargs": kwargs})
        if task_id == "T049":
            return _make_fake_response({
                "action": "deposit",
                "items": [{"name": "torch", "quantity": 1}],
                "container": "backpack",
            })
        raise AssertionError(f"Unexpected task_id: {task_id}")

    monkeypatch.setattr(storage_processor_mod, "capture_and_fanout",
                        fake_capture_and_fanout, raising=True)

    result = sp.process_storage_description(
        description="put my torch in the backpack",
        character_name="TestHero",
    )
    return result, seen_calls, sp


# --------------------------------------------------------------------------
# The four provider parameterisations
# --------------------------------------------------------------------------

EXPECTED = {
    "openai":   ("STORAGE_PROCESSOR_T049_GPT5MINI",                 "gpt-5-mini"),
    "gemini":   ("STORAGE_PROCESSOR_T049_GEMINI_FLASHLITE_MINIMAL", "gemini-3.1-flash-lite-preview"),
    "lmstudio": ("STORAGE_PROCESSOR_T049_LMSTUDIO",                 "local-model"),
    "legacy":   ("STORAGE_PROCESSOR_T049_LEGACY",                   "gpt-4.1-mini-2025-04-14"),
}


@pytest.mark.parametrize("provider", list(EXPECTED.keys()))
def test_t049_routes_through_provider_aware_router(provider, monkeypatch):
    cfg_name, expected_model = EXPECTED[provider]

    # Sanity: the named config dict exists and has the expected model string.
    assert hasattr(config, cfg_name), \
        f"model_config.{cfg_name} must be defined for T049 routing"
    assert getattr(config, cfg_name)["model"] == expected_model

    _result, calls, sp = _run_processor(provider, monkeypatch)

    # T049 must have been captured-and-fanned-out.
    task_ids = [c["task_id"] for c in calls]
    assert "T049" in task_ids, "T049 capture call missing"
    t049 = next(c for c in calls if c["task_id"] == "T049")

    # T049 must invoke the router, NOT the raw OpenAI client.
    from core.ai import api_client
    assert t049["fn"] is api_client.create_completion, (
        f"T049 must call api_client.create_completion, got {t049['fn']!r}"
    )

    # The router must be handed the right model string for this provider.
    assert t049["kwargs"]["model"] == expected_model, (
        f"provider={provider}: expected model={expected_model}, "
        f"got {t049['kwargs'].get('model')!r}"
    )

    # Temperature stays at the callsite (rule from CLAUDE.md).
    assert t049["kwargs"].get("temperature") == 0.1, (
        "T049 must preserve temperature=0.1 at the callsite"
    )

    # Provider-specific params (reasoning_effort / thinking_level) must be
    # forwarded -- but only those that are part of the config dict, never
    # synthesised, never injected by the router.
    cfg = getattr(config, cfg_name)
    for k, v in cfg.items():
        if k == "model":
            continue
        assert t049["kwargs"].get(k) == v, (
            f"provider={provider}: expected {k}={v}, "
            f"got {t049['kwargs'].get(k)!r}"
        )

    # The raw OpenAI client must NOT have been called for T049.
    assert not sp.client.chat.completions.create.called, (
        "T049 must not invoke the raw OpenAI client -- it must go through "
        "api_client.create_completion."
    )


def test_t049_passes_router_function_not_raw_client(monkeypatch):
    """Strict regression guard: the function-reference handed to
    capture_and_fanout() for T049 must be api_client.create_completion,
    NOT a method of a raw OpenAI client instance.

    This test would have caught the original XS-4 bug directly: pre-fix
    the wrapper sees fn = <bound method of OpenAI client>, post-fix it
    sees fn = <function api_client.create_completion>.
    """
    from core.ai import api_client

    monkeypatch.setattr(storage_processor_mod, "MODEL_PROVIDER", "openai", raising=True)
    monkeypatch.setattr(storage_processor_mod, "config", config, raising=True)

    sp = _build_processor_without_ctor(monkeypatch)

    fn_for_t049 = []

    def fake_capture_and_fanout(task_id, fn, **kwargs):
        if task_id == "T049":
            fn_for_t049.append(fn)
            return _make_fake_response({
                "action": "deposit",
                "items": [{"name": "torch", "quantity": 1}],
                "container": "backpack",
            })
        raise AssertionError(f"Unexpected task_id: {task_id}")

    monkeypatch.setattr(storage_processor_mod, "capture_and_fanout",
                        fake_capture_and_fanout, raising=True)

    sp.process_storage_description(
        description="put my torch in the backpack",
        character_name="TestHero",
    )

    assert len(fn_for_t049) == 1, "T049 capture call missing"
    assert fn_for_t049[0] is api_client.create_completion, (
        "T049 must hand api_client.create_completion to capture_and_fanout; "
        f"got {fn_for_t049[0]!r} -- this likely means the raw OpenAI client "
        "is being used (XS-4 regression)."
    )


def test_t049_capture_config_registered():
    """T049 should be registered in TASK_CAPTURE_CONFIGS so capture-and-fanout
    uses the per-callsite variants instead of falling back to tier defaults."""
    assert "T049" in model_config.TASK_CAPTURE_CONFIGS, (
        "T049 must be registered in TASK_CAPTURE_CONFIGS so capture testing "
        "uses the STORAGE_PROCESSOR_T049_* variants for this callsite."
    )
    openai_var, gemini_var = model_config.TASK_CAPTURE_CONFIGS["T049"]
    assert openai_var == "STORAGE_PROCESSOR_T049_GPT5MINI"
    assert gemini_var == "STORAGE_PROCESSOR_T049_GEMINI_FLASHLITE_MINIMAL"
