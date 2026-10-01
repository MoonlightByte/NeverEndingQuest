"""Pending checks and their results between DM turns (C2a).

A rollCheck for the player character waits here until the roll prompt takes
the player's dice (or lets the game roll); engine-rolled checks land as
results at once. Every result is handed to the DM Note of the next DM turn
and then cleared. Lives beside effects_state.json; a new game starts empty.
"""
from copy import deepcopy
import os
from typing import Any, Dict, List

from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json

CHECKS_STATE_PATH = os.path.join("modules", "checks_state.json")


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
    return safe_write_json(CHECKS_STATE_PATH, state)


def add_pending(entry: Dict[str, Any]) -> None:
    state = load_checks_state()
    state["pending"].append(entry)
    write_checks_state(state)


def add_result(line: str) -> None:
    state = load_checks_state()
    state["results"].append(line)
    write_checks_state(state)


def pending_checks() -> List[Dict[str, Any]]:
    return list(load_checks_state()["pending"])


def pop_pending() -> Dict[str, Any] | None:
    state = load_checks_state()
    if not state["pending"]:
        return None
    entry = state["pending"].pop(0)
    write_checks_state(state)
    return entry


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
