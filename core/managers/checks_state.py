"""Pending checks and their results between DM turns (C2a).

A rollCheck for the player character waits here until the roll prompt takes
the player's dice (or lets the game roll); engine-rolled checks land as
results at once. Every result is handed to the DM Note of the next DM turn
and then cleared. Lives beside effects_state.json; a new game starts empty.
"""
from copy import deepcopy
import os
import threading
from functools import wraps
from typing import Any, Dict, List

from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json

CHECKS_STATE_PATH = os.path.join("modules", "checks_state.json")
_lock = threading.RLock()


def _locked(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        with _lock:
            return fn(*args, **kwargs)
    return run


def _empty() -> Dict[str, Any]:
    return {"schemaVersion": 1, "pending": [], "results": [], "delivered": None}


def load_checks_state() -> Dict[str, Any]:
    value = safe_json_load(CHECKS_STATE_PATH)
    if not isinstance(value, dict):
        return _empty()
    state = deepcopy(value)
    state.setdefault("schemaVersion", 1)
    if not isinstance(state.get("pending"), list):
        state["pending"] = []
    if not isinstance(state.get("results"), list):
        state["results"] = []
    return state


def write_checks_state(state: Dict[str, Any]) -> bool:
    os.makedirs(os.path.dirname(CHECKS_STATE_PATH), exist_ok=True)
    if not safe_write_json(CHECKS_STATE_PATH, state):
        raise OSError('Could not persist pending checks')
    return True


@_locked
def add_pending(entry: Dict[str, Any]) -> None:
    state = load_checks_state()
    state["pending"].append(entry)
    write_checks_state(state)


@_locked
def add_result(line: str) -> None:
    state = load_checks_state()
    state["results"].append(line)
    write_checks_state(state)


def pending_checks() -> List[Dict[str, Any]]:
    return list(load_checks_state()["pending"])


@_locked
def pop_pending() -> Dict[str, Any] | None:
    state = load_checks_state()
    if not state["pending"]:
        return None
    entry = state["pending"].pop(0)
    write_checks_state(state)
    return entry


@_locked
def complete_pending(entry: Dict[str, Any], line: str) -> None:
    """Remove a check only when its result can be saved in the same write.

    An EOF, process restart or failed write leaves the pending check available.
    Refuse to consume a different campaign's check after a lifecycle change.
    """
    state = load_checks_state()
    if not state['pending'] or state['pending'][0] != entry:
        raise RuntimeError('Pending check changed before completion')
    state['pending'].pop(0)
    state['results'].append(line)
    write_checks_state(state)


@_locked
def consume_results(turn_marker: Any = None) -> List[str]:
    """The result lines for the DM turn starting now; cleared once that turn is known to have landed.

    ``turn_marker`` identifies the turn the note is built for (the count of DM
    replies so far). The lines handed to a turn stay on disk as ``delivered``;
    when the next note is built for the same marker (that turn never produced
    a reply: a stall, a crash, a kill), they are handed over again, so a scored
    check is never lost with the turn that was told about it.
    """
    state = load_checks_state()
    delivered = state.get("delivered")
    again: List[str] = []
    if isinstance(delivered, dict) and delivered.get("turn") == turn_marker and turn_marker is not None:
        again = [line for line in delivered.get("lines") or [] if isinstance(line, str)]
    lines = again + list(state["results"])
    if lines or delivered is not None:
        state["results"] = []
        state["delivered"] = {"turn": turn_marker, "lines": lines} if lines else None
        write_checks_state(state)
    return lines


def delivered_for_turn(turn_marker: Any) -> List[str]:
    """The result lines handed to the DM turn ``turn_marker`` (#594): the
    checks this turn's DM note reported as scored. [] for any other turn, so
    a ``delivered`` left from an earlier turn never counts."""
    delivered = load_checks_state().get("delivered")
    if turn_marker is None or not isinstance(delivered, dict) or delivered.get("turn") != turn_marker:
        return []
    return [line for line in delivered.get("lines") or [] if isinstance(line, str)]
