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

# E2E gates 2e / W3: when a module operation is refused because the module
# lifecycle needs recovery (a leftover build transaction, or a stray file such
# as desktop.ini under modules/.module_transactions), the player deserves an
# actionable reason instead of the fully-generic message above. This is a
# CURATED, player-safe string selected by the whitelisted `recovery_required`
# flag -- it never carries raw internal/provider error text.
MODULE_RECOVERY_FAILURE_MESSAGE = (
    "That action could not be completed: the module system needs to finish "
    "recovering from a previous interrupted build. No changes were made. "
    "Restart the game to let recovery run; if it persists, clear leftover "
    "files under modules/.module_transactions (they are safe to remove)."
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
