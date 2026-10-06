"""Real Socket.IO check submission without a provider or player world."""
from queue import Queue
from unittest.mock import Mock

import pytest

from core.managers import roll_prompt


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import utils.version_checker as vc
    monkeypatch.setattr(vc, "check_for_updates", lambda **kw: ("up_to_date", "0", "0", ""))
    from web import web_interface as web
    monkeypatch.setattr(web, "game_thread", Mock(is_alive=lambda: True))
    monkeypatch.setattr(web, "_web_gameplay_paused", lambda: False)
    queue = Queue()
    monkeypatch.setattr(web, "user_input_queue", queue)
    yield web, queue
    roll_prompt.publish(None)


def received(client, event):
    return next(m["args"][0] for m in client.get_received() if m["name"] == event)


def test_reconnect_typed_roll_and_duplicate_submission(game):
    web, queue = game
    roll_prompt.publish({"characterName": "Hero", "faces": 2, "label": "Strength check",
                         "netMode": "advantage", "reason": "Lift the gate"})
    token = roll_prompt.current()["id"]
    client = web.socketio.test_client(web.app)
    client.emit("request_ui_snapshot", {})
    assert received(client, "ui_state_snapshot")["roll_prompt"]["id"] == token
    client.disconnect()
    client = web.socketio.test_client(web.app)
    try:
        client.emit("user_input", {"input": "I rolled 20"})
        assert queue.empty()
        client.emit("submit_check_roll", {"id": token, "faces": [2, 18]})
        assert queue.get_nowait() == "2 18"
        client.emit("submit_check_roll", {"id": token, "faces": None})
        assert queue.empty()
    finally:
        client.disconnect()


def test_auto_roll_stale_invalid_and_paused(game, monkeypatch):
    web, queue = game
    roll_prompt.publish({"faces": 1})
    token = roll_prompt.current()["id"]
    client = web.socketio.test_client(web.app)
    try:
        for payload in [None, {}, {"id": "old", "faces": None},
                        {"id": token, "faces": [21]}, {"id": token, "faces": [True]},
                        {"id": token, "faces": [1, 2]}]:
            client.emit("submit_check_roll", payload)
            assert queue.empty()
        monkeypatch.setattr(web, "_web_gameplay_paused", lambda: True)
        client.emit("submit_check_roll", {"id": token, "faces": None})
        assert queue.empty()
        monkeypatch.setattr(web, "_web_gameplay_paused", lambda: False)
        client.emit("submit_check_roll", {"id": token, "faces": None})
        assert queue.get_nowait() == ""
    finally:
        client.disconnect()


def test_failed_enqueue_can_retry_and_old_token_cannot_answer_next_check():
    try:
        roll_prompt.publish({"faces": 1})
        token = roll_prompt.current()["id"]
        with pytest.raises(RuntimeError):
            roll_prompt.submit(token, [12], Mock(side_effect=RuntimeError("closed")))
        assert roll_prompt.current()["submitted"] is False
        roll_prompt.publish({"faces": 1})
        queue = Queue()
        with pytest.raises(ValueError):
            roll_prompt.submit(token, [12], queue.put)
        assert queue.empty()
    finally:
        roll_prompt.publish(None)


def test_legacy_numeric_composer_still_resolves_once(game):
    web, queue = game
    roll_prompt.publish({"faces": 2})
    client = web.socketio.test_client(web.app)
    try:
        client.emit("user_input", {"input": "4 17"})
        assert queue.get_nowait() == "4 17"
        client.emit("user_input", {"input": "4 17"})
        assert queue.empty()
    finally:
        client.disconnect()
