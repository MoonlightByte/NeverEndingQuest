"""Tests for T5-5 (CH-H1): retry on JSON parse failures in character builders.

Pre-fix bug:
- `npc_builder.generate_npc()` (npc_builder.py ~lines 153-182) called the AI
  exactly once. On `json.JSONDecodeError` or `jsonschema.ValidationError`, it
  printed an error and returned None. The caller in `combat_builder.py` then
  failed the entire encounter build with no retry.
- `monster_builder.generate_monster()` had the same single-shot pattern.

Fix:
- Wrap the AI call + parse + validate sequence in a retry loop bounded by
  `model_config.MAX_VALIDATION_RETRIES` (default 1 -> 2 total attempts).
- On JSONDecodeError or ValidationError: log a warning and continue to the
  next attempt.
- On exhaustion of retries: print the final error and return None
  (preserving the original failure contract for downstream callers).
- A successful parse+validate on any attempt returns the data immediately.

These tests verify, for BOTH builders:
  1. Invalid JSON on the first call followed by a valid response on the
     retry -> the builder returns the validated data and capture_and_fanout
     was called twice.
  2. Persistent invalid JSON across all attempts -> returns None and
     capture_and_fanout was called (MAX_VALIDATION_RETRIES + 1) times.
  3. (Regression) A successful first call -> capture_and_fanout is called
     exactly once (the retry loop must not perform extra work on success).

We mock `capture_and_fanout` at the module level so no real API calls are
made. The mock returns a fake response object shaped like
`response.choices[0].message.content`.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import npc_builder as npc_mod
from core.generators import monster_builder as mon_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(content: str):
    """Build a minimal stand-in for OpenAI's ChatCompletion response."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


# Minimal schema that any dict satisfies. We rely on json.loads itself
# raising for the JSON-error tests, and on a sentinel "bad" key for the
# ValidationError tests (handled separately via a stricter schema).
_PERMISSIVE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
}


def _valid_npc_payload() -> dict:
    # Keep keys simple; the permissive schema accepts any object.
    return {"name": "Test NPC", "type": "Humanoid"}


def _valid_monster_payload() -> dict:
    return {"name": "Test Monster", "type": "Beast"}


# We have to neutralise three side-effects in generate_npc/generate_monster
# so the JSON-parse retry is the only variable under test:
#   - load_prompt() reads a system prompt file from disk
#   - the MODEL_PROVIDER branch picks a config attribute off `config`
#   - repair_required_ammunition_field mutates the parsed dict (npc only)
@pytest.fixture
def patched_npc_env(monkeypatch):
    monkeypatch.setattr(
        npc_mod, "load_prompt", lambda _p: "stub system prompt",
        raising=True,
    )
    # Force the "legacy" branch and stub the config attribute it reads.
    monkeypatch.setattr(
        "model_config.MODEL_PROVIDER", "legacy", raising=False,
    )
    monkeypatch.setattr(
        npc_mod.config, "NPC_BUILD_LEGACY",
        {"model": "stub-model"}, raising=False,
    )
    # repair_required_ammunition_field returns (data, warnings). Make it
    # a pass-through so it does not interfere with the parsed payload.
    monkeypatch.setattr(
        npc_mod, "repair_required_ammunition_field",
        lambda d: (d, []), raising=True,
    )
    return monkeypatch


@pytest.fixture
def patched_monster_env(monkeypatch):
    monkeypatch.setattr(
        "model_config.MODEL_PROVIDER", "legacy", raising=False,
    )
    monkeypatch.setattr(
        mon_mod.config, "MONSTER_BUILD_LEGACY",
        {"model": "stub-model"}, raising=False,
    )
    return monkeypatch


# ---------------------------------------------------------------------------
# Test 1: npc_builder retries once on bad JSON, succeeds on the second call
# ---------------------------------------------------------------------------

def test_npc_builder_retries_on_invalid_json_then_succeeds(patched_npc_env):
    """First AI call returns un-parseable JSON; the second returns a valid
    payload. generate_npc must succeed on the retry and capture_and_fanout
    must have been invoked exactly twice."""

    valid_json = json.dumps(_valid_npc_payload())
    side_effects = [
        _fake_response("this is not json {{{"),  # raises JSONDecodeError
        _fake_response(valid_json),
    ]
    fake_cf = mock.Mock(side_effect=side_effects)

    with mock.patch.object(npc_mod, "capture_and_fanout", fake_cf):
        result = npc_mod.generate_npc(
            "Test NPC",
            _PERMISSIVE_SCHEMA,
            npc_race="Human",
            npc_class="Fighter",
            npc_level=2,
        )

    assert result is not None, (
        "generate_npc should return parsed data after a retry on bad JSON; "
        "got None which means the retry loop did not run."
    )
    assert result.get("name") == "Test NPC", (
        f"Returned data must be the parsed retry payload; got {result!r}"
    )
    assert fake_cf.call_count == 2, (
        "capture_and_fanout must be called twice (1 failure + 1 retry); "
        f"got {fake_cf.call_count} calls."
    )


# ---------------------------------------------------------------------------
# Test 2: monster_builder retries once on bad JSON, succeeds on the second
# ---------------------------------------------------------------------------

def test_monster_builder_retries_on_invalid_json_then_succeeds(
        patched_monster_env):
    """Same pattern as test 1 but for generate_monster."""

    valid_json = json.dumps(_valid_monster_payload())
    side_effects = [
        _fake_response("definitely not json"),  # raises JSONDecodeError
        _fake_response(valid_json),
    ]
    fake_cf = mock.Mock(side_effect=side_effects)

    with mock.patch.object(mon_mod, "capture_and_fanout", fake_cf):
        result = mon_mod.generate_monster(
            "Test Monster", _PERMISSIVE_SCHEMA, party_level=3,
        )

    assert result is not None, (
        "generate_monster should return parsed data after a retry on bad "
        "JSON; got None which means the retry loop did not run."
    )
    assert result.get("name") == "Test Monster", (
        f"Returned data must be the parsed retry payload; got {result!r}"
    )
    assert fake_cf.call_count == 2, (
        "capture_and_fanout must be called twice (1 failure + 1 retry); "
        f"got {fake_cf.call_count} calls."
    )


# ---------------------------------------------------------------------------
# Test 3: persistent failure across all attempts -> returns None
# ---------------------------------------------------------------------------

def test_builders_return_none_after_exhausting_retries(
        patched_npc_env, patched_monster_env):
    """When every attempt produces invalid JSON, both builders must return
    None and capture_and_fanout must be called exactly
    (MAX_VALIDATION_RETRIES + 1) times -- never more, never fewer.
    """
    # Read the bound (defaulting to 2 total attempts if unavailable).
    try:
        import model_config
        max_retries = getattr(model_config, "MAX_VALIDATION_RETRIES", 1)
    except Exception:  # pragma: no cover -- defensive
        max_retries = 1
    expected_calls = max_retries + 1

    bad = _fake_response("not json at all")

    # NPC builder
    fake_cf_npc = mock.Mock(return_value=bad)
    with mock.patch.object(npc_mod, "capture_and_fanout", fake_cf_npc):
        result_npc = npc_mod.generate_npc("Test NPC", _PERMISSIVE_SCHEMA)
    assert result_npc is None, (
        "generate_npc must return None when every attempt fails to parse; "
        f"got {result_npc!r}."
    )
    assert fake_cf_npc.call_count == expected_calls, (
        f"generate_npc should call capture_and_fanout exactly "
        f"{expected_calls} times (MAX_VALIDATION_RETRIES+1); got "
        f"{fake_cf_npc.call_count}."
    )

    # Monster builder
    fake_cf_mon = mock.Mock(return_value=bad)
    with mock.patch.object(mon_mod, "capture_and_fanout", fake_cf_mon):
        result_mon = mon_mod.generate_monster(
            "Test Monster", _PERMISSIVE_SCHEMA, party_level=1,
        )
    assert result_mon is None, (
        "generate_monster must return None when every attempt fails to "
        f"parse; got {result_mon!r}."
    )
    assert fake_cf_mon.call_count == expected_calls, (
        f"generate_monster should call capture_and_fanout exactly "
        f"{expected_calls} times (MAX_VALIDATION_RETRIES+1); got "
        f"{fake_cf_mon.call_count}."
    )


# ---------------------------------------------------------------------------
# Test 4 (regression): successful first call -> only one attempt
# ---------------------------------------------------------------------------

def test_builders_call_ai_only_once_on_immediate_success(
        patched_npc_env, patched_monster_env):
    """The retry loop must not perform extra work when the first attempt
    succeeds. Both builders should call capture_and_fanout exactly once."""

    npc_response = _fake_response(json.dumps(_valid_npc_payload()))
    fake_cf_npc = mock.Mock(return_value=npc_response)
    with mock.patch.object(npc_mod, "capture_and_fanout", fake_cf_npc):
        result_npc = npc_mod.generate_npc("Test NPC", _PERMISSIVE_SCHEMA)
    assert result_npc is not None, (
        f"generate_npc should succeed on first attempt; got {result_npc!r}."
    )
    assert fake_cf_npc.call_count == 1, (
        "generate_npc must not invoke the AI more than once when the "
        f"first response parses cleanly; got {fake_cf_npc.call_count} "
        f"calls."
    )

    mon_response = _fake_response(json.dumps(_valid_monster_payload()))
    fake_cf_mon = mock.Mock(return_value=mon_response)
    with mock.patch.object(mon_mod, "capture_and_fanout", fake_cf_mon):
        result_mon = mon_mod.generate_monster(
            "Test Monster", _PERMISSIVE_SCHEMA, party_level=1,
        )
    assert result_mon is not None, (
        f"generate_monster should succeed on first attempt; got "
        f"{result_mon!r}."
    )
    assert fake_cf_mon.call_count == 1, (
        "generate_monster must not invoke the AI more than once when the "
        f"first response parses cleanly; got {fake_cf_mon.call_count} "
        f"calls."
    )
