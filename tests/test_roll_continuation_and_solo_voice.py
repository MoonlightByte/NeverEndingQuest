"""Player roll continuation and empty companion batch regressions (no providers)."""
import ast
from pathlib import Path
from unittest.mock import Mock
import pytest
from core.managers import checks_runtime, checks_state, roll_prompt
from core.npc import voice_context, voice_service

@pytest.fixture
def check_world(tmp_path, monkeypatch):
    monkeypatch.setattr(checks_state, "CHECKS_STATE_PATH", str(tmp_path / "modules" / "checks_state.json"))
    monkeypatch.setattr(checks_runtime, "_resolve_character", lambda name: (name, "player", "hero.json", {}))
    yield
    roll_prompt.publish(None)

@pytest.mark.parametrize("typed,expected", [("", None), ("15", [15])])
def test_roll_persists_once_and_returns_for_narration(check_world, monkeypatch, typed, expected):
    entry = {"characterName": "Hero", "stat": "perception", "faces": 1, "dc": 12}
    checks_state.add_pending(entry)
    resolve = Mock(return_value=checks_runtime.checks.CheckResult(True, "perception", "Hero", faces=[15]))
    monkeypatch.setattr(checks_runtime.checks, "resolve", resolve)
    monkeypatch.setattr(checks_runtime.checks, "describe", lambda result: "Hero Perception: 15 +4 = 19")
    read = Mock(return_value=typed)
    assert checks_runtime.take_player_rolls(read) == ["Hero Perception: 15 +4 = 19"]
    assert resolve.call_args.kwargs["faces"] == expected
    read.assert_called_once()
    assert roll_prompt.current() is None
    assert checks_runtime.take_player_rolls(read) == []
    resolve.assert_called_once()
    assert checks_state.consume_results(4) == ["Hero Perception: 15 +4 = 19"]
    assert checks_state.consume_results(4) == ["Hero Perception: 15 +4 = 19"]
    assert checks_state.consume_results(5) == []

def test_invalid_dice_and_interruption_preserve_pending(check_world, monkeypatch):
    entry = {"characterName": "Hero", "stat": "perception", "faces": 2, "netMode": "advantage"}
    checks_state.add_pending(entry)
    resolve = Mock()
    monkeypatch.setattr(checks_runtime.checks, "resolve", resolve)
    with pytest.raises(EOFError):
        checks_runtime.take_player_rolls(Mock(side_effect=["25 2", EOFError()]))
    assert checks_state.pending_checks() == [entry]
    assert roll_prompt.current() is None
    resolve.assert_not_called()

def test_actual_main_roll_branch_does_not_read_another_command():
    tree = ast.parse((Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "completed_checks")
    output = Mock()
    read = Mock(side_effect=AssertionError("Roll must continue without another input"))
    env = {"completed_checks": ["Hero rolled 6 +4 = 10"], "display_dm_narration": output, "input": read}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "main-roll-boundary", "exec"), env)
    assert "submitted check" in env["user_input_text"]
    output.assert_not_called()
    read.assert_not_called()

@pytest.mark.parametrize("roster", [[], None])
def test_solo_skips_service_and_recall(monkeypatch, roster):
    service = Mock(side_effect=AssertionError("No companion service for solo play"))
    monkeypatch.setattr(voice_context, "_default_service", service)
    result = voice_context.run_ooc_voice_stage(party_tracker_data={"partyNPCs": roster}, player_name="Hero", raw_input="Look", location_data={"npcs": ["Mayor"]}, conversation_prefix=[], path_manager=None)
    assert result.results == ()
    service.assert_not_called()

def test_ineligible_roster_skips_voice_dispatch(monkeypatch):
    service = Mock()
    monkeypatch.setattr(voice_context, "build_ooc_packets_for_turn", lambda **kwargs: ())
    handle = Mock(side_effect=AssertionError("No dispatch for empty eligible packets"))
    monkeypatch.setattr(voice_context, "PreparedOocVoiceHandle", handle)
    result = voice_context.run_ooc_voice_stage(party_tracker_data={"partyNPCs": [{"name": "Ally"}]}, player_name="Hero", raw_input="Look", location_data={}, conversation_prefix=[], path_manager=None, service=service)
    assert result.results == ()
    handle.assert_not_called()

@pytest.mark.parametrize("has_result", [False, True])
def test_completion_status_requires_actual_voice_result(has_result):
    handle = voice_service.VoiceBatchHandle(service=Mock(), batch_id="batch", npc_ids=(), futures={}, immediate=(), candidate_count=0, counters={}, scopes={}, parent_scope=None, batch_started=0, provider="test", completion_required=True, batch_mode="OUT_OF_COMBAT")
    if has_result:
        handle._collected = [object()]
    handle._finalize = Mock(return_value="batch")
    emit = Mock()
    assert handle.collect_to_completion(emit) == "batch"
    assert emit.call_count == int(has_result)



@pytest.mark.parametrize("typed,faces", [("", [7]), ("18", [18]), ("2 18", [2, 18]), ("", [4, 19])])
def test_accepted_roll_is_a_natural_player_reply_once(check_world, monkeypatch, typed, faces):
    from web import shared_state
    checks_state.add_pending({"characterName": "Hero", "stat": "perception", "faces": len(faces), "dc": 12, "netMode": "advantage"})
    result = checks_runtime.checks.CheckResult(True, "perception", "Hero", faces=faces)
    monkeypatch.setattr(checks_runtime.checks, "resolve", lambda *a, **kw: result)
    monkeypatch.setattr(checks_runtime.checks, "describe", lambda r: "Resolved check")
    output = Mock()
    monkeypatch.setattr(shared_state, "emit_player_output", output)
    checks_runtime.take_player_rolls(lambda p: typed)
    checks_runtime.take_player_rolls(lambda p: pytest.fail("Already submitted"))
    expected = "I rolled " + " and ".join(f"{f} on a d20" for f in faces) + "."
    output.assert_called_once_with({"type": "user-input", "content": expected})
