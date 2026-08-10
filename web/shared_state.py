#!/usr/bin/env python3
"""
Shared State Module - Centralized location for cross-module shared objects.
This prevents circular dependencies and ensures single instances.
"""

import queue
import threading

# Single, shared queue for module creation progress
module_progress_queue = queue.Queue()

# Player-facing action failures use one static message. Internal/provider
# details stay in server logs and are never promoted into game output.
SAFE_ACTION_FAILURE_MESSAGE = (
    "That action could not be completed safely. No further actions from "
    "that response were applied."
)

_player_output_sink = None
_player_output_sink_lock = threading.RLock()


def set_player_output_sink(sink):
    """Install the optional player-output sink used by the active frontend."""
    if sink is not None and not callable(sink):
        raise TypeError("player output sink must be callable or None")
    global _player_output_sink
    with _player_output_sink_lock:
        _player_output_sink = sink


def has_player_output_sink():
    """Return whether an active frontend currently owns player delivery."""
    with _player_output_sink_lock:
        return _player_output_sink is not None


def emit_player_output(message):
    """Best-effort output delivery; an absent or failed sink is never fatal."""
    try:
        payload = dict(message)
    except Exception:
        return False
    with _player_output_sink_lock:
        sink = _player_output_sink
    if sink is None:
        return False
    try:
        # ``False`` means the sink could not durably accept the message. None
        # remains a successful legacy sink result; modern sinks return True.
        return sink(payload) is not False
    except Exception:
        return False

print("[SHARED STATE] Module progress queue initialized")
