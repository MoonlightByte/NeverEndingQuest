"""#1342: per-call reissue limits and the per-turn generation ceiling.

A fake child process plays each failure phase; no SDK, network or key.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.capture import live_provider_call as lpc  # noqa: E402
from utils.provider_errors import classify_provider_error  # noqa: E402

FAKE_CHILD = str(Path(__file__).with_name("fake_reissue_child.py"))
CONNECT = {"kind": "error", "disposition": "retryable_transport", "phases": ["connecting"]}
RECEIVING = {"kind": "error", "disposition": "retryable_http", "error_code": "server_error",
             "phases": ["acknowledged", "receiving"]}
OK = {"kind": "success", "phases": ["acknowledged", "receiving", "done"]}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    real_popen = subprocess.Popen
    count = tmp_path / "count"
    delays = []

    def popen(command, **kwargs):
        assert command[-1] == "--provider-child"
        kwargs["stderr"] = open(tmp_path / "child.err", "ab")
        return real_popen([sys.executable, FAKE_CHILD], **kwargs)

    def run(plan, scope=None, task_id="T067"):
        (tmp_path / "plan.json").write_text(json.dumps(plan))
        monkeypatch.setenv("NEQ_FAKE_CHILD_PLAN", str(tmp_path / "plan.json"))
        monkeypatch.setenv("NEQ_FAKE_CHILD_COUNT", str(count))
        if count.exists():
            count.unlink()
        scope = scope if scope is not None else lpc.LiveTurnScope()
        try:
            return lpc.call_live_provider(
                task_id, [{"role": "user", "content": "x"}],
                {"_request_provider": "openai", "model": "m"},
                scope=scope, status_emit=lambda _m: None,
            )
        finally:
            run.generations = int(count.read_text()) if count.exists() else 0

    monkeypatch.setattr(lpc.subprocess, "Popen", popen)
    # The real rebuild imports the provider client (and config); the envelope suffices.
    monkeypatch.setattr(lpc, "_reconstruct_response", lambda envelope: envelope)
    monkeypatch.setattr(lpc, "_interruptible_wait",
                        lambda seconds, *a, **k: delays.append(seconds))
    run.delays = delays
    return run


def _limit(excinfo):
    return excinfo.value.envelope["error_class"]


def test_free_reissues_end_after_six(fake):
    with pytest.raises(lpc.LiveProviderCompletedError) as excinfo:
        fake([CONNECT])
    assert _limit(excinfo) == "reissue_limit"
    assert fake.generations == lpc._FREE_REISSUE_LIMIT + 1


def test_billed_reissues_end_after_two(fake):
    with pytest.raises(lpc.LiveProviderCompletedError) as excinfo:
        fake([RECEIVING])
    assert _limit(excinfo) == "reissue_limit"
    assert fake.generations == lpc._BILLED_REISSUE_LIMIT + 1


def test_empty_answer_is_billed(fake):
    with pytest.raises(lpc.LiveProviderCompletedError):
        fake([{"kind": "error", "disposition": "empty", "phases": ["acknowledged"]}])
    assert fake.generations == lpc._BILLED_REISSUE_LIMIT + 1


def test_mixed_failures_then_success_returns(fake):
    response = fake([CONNECT] * 5 + [RECEIVING] * 2 + [OK])
    assert response["content"] == "ok"
    assert fake.generations == 8


def test_rate_limit_429_uses_backoff_not_sixty_seconds(fake):
    with pytest.raises(lpc.LiveProviderCompletedError) as excinfo:
        fake([{"kind": "error", "disposition": "retryable_http", "http_status": 429,
               "error_class": "RateLimitError", "phases": ["sent"]}])
    assert fake.delays and max(fake.delays) <= lpc._MAX_BACKOFF_SECONDS
    refusal = classify_provider_error(excinfo.value)
    assert refusal["category"] == "reissue_limit" and refusal["retryable"] is False


def test_bad_key_401_stops_at_once(fake):
    # #240 pinned: a deterministic refusal is one generation and no wait.
    with pytest.raises(lpc.LiveProviderCompletedError) as excinfo:
        fake([{"kind": "error", "disposition": "deterministic", "http_status": 401,
               "error_class": "AuthenticationError", "phases": ["acknowledged"]}])
    assert fake.generations == 1 and fake.delays == []
    assert classify_provider_error(excinfo.value)["category"] == "authentication_failed"


def test_quota_429_stops_at_once(fake):
    with pytest.raises(lpc.LiveProviderCompletedError) as excinfo:
        fake([{"kind": "error", "disposition": "deterministic", "http_status": 429,
               "error_code": "insufficient_quota", "phases": ["acknowledged"]}])
    assert fake.generations == 1
    assert classify_provider_error(excinfo.value)["category"] == "insufficient_quota"


def test_turn_ceiling_raises_before_spawning(fake):
    scope = lpc.LiveTurnScope()
    scope.provider_generations = lpc._TURN_GENERATION_CEILING
    with pytest.raises(lpc.LiveProviderCompletedError) as excinfo:
        fake([OK], scope=scope)
    assert _limit(excinfo) == "turn_call_ceiling"
    assert fake.generations == 0
    refusal = classify_provider_error(excinfo.value)
    assert refusal["category"] == "turn_call_ceiling" and refusal["retryable"] is False


def test_turn_ceiling_counts_reissues_across_calls(fake):
    scope = lpc.LiveTurnScope()
    for _ in range(3):
        with pytest.raises(lpc.LiveProviderCompletedError):
            fake([CONNECT], scope=scope)  # 7 generations each
    assert scope.provider_generations == 21
    with pytest.raises(lpc.LiveProviderCompletedError) as excinfo:
        fake([CONNECT], scope=scope)
    assert _limit(excinfo) == "turn_call_ceiling"
    assert fake.generations == 3 and scope.provider_generations == 24


def test_advisory_scope_counts_against_its_turn():
    parent = lpc.LiveTurnScope()
    child = lpc.AdvisoryProviderScope(parent=parent, beat_id="b")
    for _ in range(lpc._TURN_GENERATION_CEILING):
        assert child.claim_provider_generation()
    assert not parent.claim_provider_generation()


def test_combat_refusal_line_names_the_saved_fight():
    from utils.provider_errors import account_refusal_message

    for bound in ("reissue_limit", "turn_call_ceiling"):
        line = account_refusal_message(bound, "openai", "combat")
        assert "The fight is saved as it stands" in line
        assert "load your game to continue the fight" in line


def test_combat_round_trip_keeps_the_committed_round(tmp_path, monkeypatch):
    # T11: a ceiling or reissue limit raised by a combat round's T096 call
    # (state from desktop run L10, round 2). The committed round is unchanged;
    # only the pending-turn claim is recorded, kept for resume (#1087).
    from core.managers import combat_orchestrator

    state = json.loads((ROOT / "tests/fixtures/reissue_combat/l10_round2.json").read_text())
    monkeypatch.chdir(tmp_path)
    encounter = "modules/encounters/encounter_RO03-E1.json"
    for bound in ("turn_call_ceiling", "reissue_limit"):
        for name, data in state.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(json.dumps(data))
        before = json.loads((tmp_path / encounter).read_text())
        party = (tmp_path / "party_tracker.json").read_bytes()
        sheet = (tmp_path / "characters/mira_willowmere.json").read_bytes()
        def intent_provider(*_args, **_kwargs):
            raise lpc.LiveProviderCompletedError("T096", lpc._limit_envelope(bound, "T096", {}))
        with pytest.raises(lpc.LiveProviderCompletedError):
            combat_orchestrator.execute_agentic_turn(
                encounter, ["cmb-player-mira-willowmere-1", "cmb-enemy-giant-rat-1"],
                {"cmb-player-mira-willowmere-1": "characters/mira_willowmere.json"}, {},
                "I kick the rat away.", intent_provider=intent_provider,
                narrator=lambda *_a, **_k: None)
        after = json.loads((tmp_path / encounter).read_text())
        pending = after["combatState"]["pendingTurn"]
        assert before["combatState"]["pendingTurn"] is None
        after["combatState"].update(pendingTurn=None, phase=before["combatState"]["phase"])
        assert after == before
        assert pending["round"] == 2 and pending["baseRevision"] == before["combatState"]["revision"]
        assert (tmp_path / "party_tracker.json").read_bytes() == party
        assert (tmp_path / "characters/mira_willowmere.json").read_bytes() == sheet
        refusal = classify_provider_error(lpc.LiveProviderCompletedError(
            "T096", lpc._limit_envelope(bound, "T096", {})))
        from utils.provider_errors import account_refusal_message

        line = account_refusal_message(refusal["category"], refusal["provider"], "combat")
        assert "The fight is saved as it stands" in line
