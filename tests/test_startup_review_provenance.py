"""Offline startup replay: real schema/NQL, scripted model verdicts, no networking.

The synthetic authored fixture is the 2026-10-03 17:21:20.595263 response from
desktop-game-001. Only the fictional wire object is retained, not its capture,
request history, credentials, world settings or provider metadata.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import types

import pytest

ROOT = Path(os.environ.get("NEQ_STARTUP_TEST_ROOT", Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / "fixtures" / "startup-authored-alden.json"


@pytest.fixture
def wizard(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network and operator credential access forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(ROOT))
    for name in list(os.environ):
        if any(word in name.upper() for word in ("API_KEY", "TOKEN", "SECRET")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NEQ_MULTI_MODEL_CAPTURE", "0")
    monkeypatch.setenv("NQL_APPLY_BINARY", str(ROOT / "bin" /
                       ("nql-apply.exe" if os.name == "nt" else "nql-apply")))
    keyring = types.ModuleType("keyring")
    keyring.get_keyring = lambda: keyring
    keyring.get_password = forbidden
    keyring.set_password = forbidden
    keyring.delete_password = forbidden
    monkeypatch.setitem(sys.modules, "keyring", keyring)
    spec = importlib.util.spec_from_file_location("config", ROOT / "config_template.py")
    config = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "config", config)
    spec.loader.exec_module(config)
    config.OPENAI_API_KEY = "offline-provenance-no-network"
    config.GEMINI_API_KEY = ""
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    (tmp_path / "prompts" / "leveling").mkdir(parents=True)
    shutil.copy2(ROOT / "prompts" / "leveling" / "leveling_info.txt",
                 tmp_path / "prompts" / "leveling" / "leveling_info.txt")
    from utils import startup_wizard
    monkeypatch.setattr(startup_wizard.api_client, "create_completion", forbidden)
    monkeypatch.setattr(startup_wizard, "capture_and_fanout", forbidden)
    return startup_wizard


@pytest.fixture
def authored():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_captured_author_replays_through_real_normalization(wizard, authored):
    original = copy.deepcopy(authored)
    assert authored["character"]["equipment_effects"] == []
    assert "savingThrowBonuses" not in authored["character"]
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    assert authored == original
    assert candidate["character"]["armorClass"] == 18
    assert candidate["character"]["maxHitPoints"] == 12
    assert candidate["character"]["equipment_effects"]
    assert candidate["character"]["savingThrowBonuses"]["constitution"] == 4
    engine = provenance["engine_projection"]
    assert engine["applied"] is True
    assert engine["armorClass"] == 18
    assert engine["equipment_effects"]["entries"] == candidate["character"]["equipment_effects"]
    from core.nql import stats
    totals = stats.totals(engine["status"])
    assert totals["save:constitution"] == candidate["character"]["savingThrowBonuses"]["constitution"]
    assert provenance["mechanics_notes"] == []
    # Repeated projection, including a sheet already carrying identical totals.
    repeated, repeated_provenance = wizard._prepare_startup_proposal(authored)
    stable, stable_provenance = wizard._prepare_startup_proposal(candidate)
    assert repeated == stable == candidate
    assert repeated_provenance["engine_projection"] == engine
    assert stable_provenance["engine_projection"] == engine
    assert authored == original


@pytest.mark.parametrize("failure", ["unavailable", "gaps"])
def test_failed_or_incomplete_projection_has_no_engine_certificate(wizard, authored, monkeypatch, failure):
    from core.nql import armor_class
    projection = armor_class.Projection(
        copy.deepcopy(authored["character"]), failure == "gaps",
        reason="offline unavailable" if failure == "unavailable" else "",
        gaps=["unknown armor"] if failure == "gaps" else [])
    monkeypatch.setattr(armor_class, "project", lambda sheet: projection)
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    assert provenance["engine_projection"]["applied"] is False
    assert "status" not in provenance["engine_projection"]
    assert "equipment_effects" not in provenance["engine_projection"]
    assert candidate["character"]["equipment_effects"] == []
    assert "savingThrowBonuses" not in candidate["character"]


def test_narrow_engine_certificate_does_not_claim_other_effects(wizard, authored):
    effect = {"name": "Unverified damage boost", "type": "bonus", "target": "damage",
              "value": 99, "description": "Unverified", "source": "author"}
    authored["character"]["equipment_effects"] = [effect]
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    assert effect in candidate["character"]["equipment_effects"]
    assert effect not in provenance["engine_projection"]["equipment_effects"]["entries"]
    assert provenance["engine_projection"]["equipment_effects"]["selector"] == {"target": "AC"}


def run_interview(wizard, authored, monkeypatch, *, review, stop_after_rejection=False):
    from utils.capture.live_provider_call import LiveProviderSuperseded
    proposal = copy.deepcopy(authored)
    proposal["confirmation"]["player_message_index"] = 0
    original = copy.deepcopy(proposal)
    conversation = [{"role": "user", "content": "I approve Alden's complete current build."}]
    commits = []
    author_requests = []
    reviewer_requests = []
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "_commit_startup_build", lambda c, m, s, **k: commits.append(copy.deepcopy(s)))

    def model(messages, *args, **kwargs):
        if kwargs.get("startup_phase") == "startup_review":
            payload = json.loads(messages[1]["content"])
            reviewer_requests.append(copy.deepcopy(payload))
            return json.dumps(review(payload))
        author_requests.append(copy.deepcopy(messages))
        if len(author_requests) > 1 and stop_after_rejection:
            raise LiveProviderSuperseded("test-only stop after observed rejection")
        return json.dumps(proposal)

    monkeypatch.setattr(wizard, "get_ai_response", model)
    if stop_after_rejection:
        with pytest.raises(LiveProviderSuperseded):
            wizard.ai_character_interview(conversation, {"name": "The_Thornwood_Watch"})
        result = None
    else:
        result = wizard.ai_character_interview(conversation, {"name": "The_Thornwood_Watch"})
    assert proposal == original
    return result, conversation, commits, author_requests, reviewer_requests


def test_actual_interview_reviews_both_sources_and_publishes_canonical(wizard, authored, monkeypatch):
    def review(payload):
        assert payload["authored_proposal"]["character"]["equipment_effects"] == []
        assert "savingThrowBonuses" not in payload["authored_proposal"]["character"]
        assert payload["proposal"]["character"]["equipment_effects"]
        assert payload["proposal"]["character"]["savingThrowBonuses"]
        assert payload["normalization_provenance"]["engine_projection"]["applied"]
        assert "startup_mechanics" not in payload["committed_facts"]  # scalar notes are empty
        return {"version": 1, "accepted": True, "feedback": "Both sources reviewed.",
                "needs_player_clarification": False}

    result, conversation, commits, authors, reviewers = run_interview(wizard, authored, monkeypatch, review=review)
    assert len(authors) == len(reviewers) == len(commits) == 1
    assert result == commits[0] == reviewers[0]["proposal"]["character"]
    assert wizard._startup_progress(conversation)["phase"] == "approved"


@pytest.mark.parametrize("defect", ["narration", "mechanics", "identity", "author_saves", "author_effects"])
@pytest.mark.parametrize("needs_clarification", [False, True])
def test_negative_review_retains_authorship_and_never_commits(wizard, authored, monkeypatch, defect, needs_clarification):
    if defect == "narration":
        authored["narration"] = "You have arrived and your character was saved."
    elif defect == "mechanics":
        authored["character"]["hitPoints"] = authored["character"]["maxHitPoints"] = 99
    elif defect == "identity":
        authored["character"]["name"] = "Unapproved replacement"
    elif defect == "author_saves":
        authored["character"]["savingThrowBonuses"] = {"strength": 99}
    else:
        authored["character"]["equipment_effects"] = [{
            "name": "Authored AC", "type": "bonus", "target": "AC", "value": 99,
            "description": "Invented", "source": "author"}]

    def review(payload):
        assert payload["normalization_provenance"]["engine_projection"]["applied"]
        if defect == "mechanics":
            assert payload["proposal"]["character"]["maxHitPoints"] == 99
            assert payload["normalization_provenance"]["hit_points"]["expected_maximum"] == 12
        if defect == "author_saves":
            assert payload["authored_proposal"]["character"]["savingThrowBonuses"]["strength"] == 99
            assert payload["proposal"]["character"]["savingThrowBonuses"]["strength"] == 5
        return {"version": 1, "accepted": False, "feedback": "Rejected " + defect,
                "needs_player_clarification": needs_clarification}

    result, conversation, commits, authors, reviewers = run_interview(
        wizard, authored, monkeypatch, review=review, stop_after_rejection=True)
    assert result is None and commits == []
    assert len(reviewers) == 1 and len(authors) == 2
    correction = next(json.loads(m["content"]) for m in authors[1]
                      if m["role"] == "system" and '"rejected_proposal"' in m["content"])
    assert correction["rejected_proposal"] == reviewers[0]["authored_proposal"]
    assert correction["canonical_candidate"] == reviewers[0]["proposal"]
    assert correction["normalization_provenance"] == reviewers[0]["normalization_provenance"]
    assert correction["needs_player_clarification"] is needs_clarification
    if needs_clarification:
        assert correction["instruction"] == "Propose a continue_interview question; do not finalize."
    assert not any(m["role"] == "assistant" for m in conversation)


@pytest.mark.parametrize("defect", ["approval", "index", "schema"])
def test_invalid_consent_or_schema_cannot_reach_review(wizard, authored, monkeypatch, defect):
    if defect == "approval":
        authored["confirmation"]["whole_build_approved"] = False
    elif defect == "index":
        # run_interview uses 0; intercept parsing's reference instead.
        monkeypatch.setattr(wizard, "_latest_player_index", lambda messages: 99)
    else:
        authored["character"]["spellcasting"]["ability"] = None
    result, conversation, commits, authors, reviewers = run_interview(
        wizard, authored, monkeypatch, review=lambda p: pytest.fail("Review must not run"),
        stop_after_rejection=True)
    assert result is None and not commits and not reviewers
    assert len(authors) == 2


def test_fenced_json_uses_real_startup_parser_without_changing_probe(wizard, authored):
    from utils.startup_contract import parse_startup_response
    assert parse_startup_response("```json\n" + json.dumps(authored) + "\n```",
                                  latest_user_index=12) == authored


def test_network_is_forbidden(wizard):
    with pytest.raises(AssertionError, match="forbidden"):
        socket.create_connection(("openrouter.ai", 443))


def test_superseded_review_cannot_publish(wizard, authored, monkeypatch):
    from utils.capture.live_provider_call import LiveProviderSuperseded
    proposal = copy.deepcopy(authored)
    proposal["confirmation"]["player_message_index"] = 0
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "_commit_startup_build", lambda *a, **k: pytest.fail("No commit after cancellation"))

    def model(messages, *args, **kwargs):
        if kwargs.get("startup_phase") == "startup_review":
            kwargs["live_scope"].request_supersession("offline-cancellation")
            return json.dumps({"version": 1, "accepted": True, "feedback": "Reviewed.",
                               "needs_player_clarification": False})
        return json.dumps(proposal)

    monkeypatch.setattr(wizard, "get_ai_response", model)
    conversation = [{"role": "user", "content": "I approve the complete build."}]
    with pytest.raises(LiveProviderSuperseded):
        wizard.ai_character_interview(conversation, {"name": "The_Thornwood_Watch"})
    assert not any(m["role"] == "assistant" for m in conversation)


def test_continue_interview_never_projects_or_commits(wizard, monkeypatch):
    monkeypatch.setattr(wizard, "startup_mechanics", lambda *a, **k: pytest.fail("No projection of an interview"))
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "_commit_startup_build", lambda *a, **k: pytest.fail("No character commit"))
    monkeypatch.setattr("builtins.input", lambda *a: "cancel")

    def model(messages, *args, **kwargs):
        if kwargs.get("startup_phase") == "startup_review":
            payload = json.loads(messages[1]["content"])
            assert payload["authored_proposal"] == payload["proposal"]
            assert payload["normalization_provenance"] == {}
            return json.dumps({"version": 1, "accepted": True, "feedback": "Valid question.",
                               "needs_player_clarification": False})
        return json.dumps({"version": 1, "decision": "continue_interview", "narration": "What is your name?",
                           "confirmation": {"whole_build_approved": False, "player_message_index": None},
                           "character": None})

    monkeypatch.setattr(wizard, "get_ai_response", model)
    with pytest.raises(wizard.StartupCancelled):
        wizard.ai_character_interview([], {"name": "The_Thornwood_Watch"})


def test_invalid_review_verdict_is_repaired_without_changing_sources(wizard, authored, monkeypatch):
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    calls = []

    def model(messages, *args, **kwargs):
        calls.append(copy.deepcopy(messages))
        return json.dumps({"version": 1, "accepted": True, "feedback": "Reviewed.",
                           "needs_player_clarification": len(calls) == 1})

    monkeypatch.setattr(wizard, "get_ai_response", model)
    review = wizard._review_startup_response(
        [], candidate, {"character_saved": False}, authored_proposal=authored,
        normalization_provenance=provenance, live_scope=None)
    assert review["accepted"] is True and len(calls) == 2
    assert calls[0][1] == calls[1][1]
    assert "invalid structure" in calls[1][-1]["content"]

def test_declared_module_entry_bypasses_provider_after_main_integration(wizard, monkeypatch):
    entry = {'areaId': 'AREA01', 'locationId': 'ROOM01', 'areaName': 'Fixture',
             'locationName': 'Entry', 'weather': '', 'politicalClimate': ''}
    monkeypatch.setattr(wizard, '_declared_starting_location', lambda name: entry)
    # The fixture forbids network/provider calls; declared entries must retain
    # public main's deterministic bypass even with provenance/recovery changes.
    assert wizard.get_ai_starting_location({'moduleName': 'Fixture'}) == entry
