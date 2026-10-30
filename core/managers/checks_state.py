"""Pending checks and their results between DM turns (C2a).

A rollCheck for the player character waits here until the player's answer
gives its dice (or lets the game roll), across turns if need be (#1118 item 4);
engine-rolled checks land as results at once. Every result is handed to the DM Note of the next DM turn
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
def add_pending(entry: Dict[str, Any]) -> bool:
    """Queue ``entry``; False, with nothing written, when the same check (character, stat, dc and mode) waits."""
    state = load_checks_state()
    same = ("characterName", "stat", "dc", "mode")
    if any(isinstance(p, dict) and all(p.get(k) == entry.get(k) for k in same) for p in state["pending"]):
        return False
    state["pending"].append(entry)
    write_checks_state(state)
    return True


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
def complete_pending(entry: Dict[str, Any], line: str) -> bool:
    """Remove a check only when its result can be saved in the same write.

    An EOF, process restart or failed write leaves the pending check available.
    False, with nothing written, when the check at the head of the queue is no
    longer ``entry`` (a Load or Reset changed it): nothing is applied.
    """
    state = load_checks_state()
    if not state['pending'] or state['pending'][0] != entry:
        return False
    state['pending'].pop(0)
    state['results'].append(line)
    write_checks_state(state)
    return True


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


# #1122: an updatePlot the engine refused during a travel, told to the DM once.
# Queued under its request id; handed out like the check results above.

@_locked
def add_quest_note(request_id: str, text: str) -> None:
    state = load_checks_state()
    notes = state.get("questNotes") if isinstance(state.get("questNotes"), list) else []
    delivered = state.get("questDelivered") if isinstance(state.get("questDelivered"), dict) else {}
    known = {n.get("requestId") for n in notes + list(delivered.get("notes") or []) if isinstance(n, dict)}
    if request_id in known:
        return
    state["questNotes"] = notes + [{"requestId": request_id, "text": text}]
    write_checks_state(state)


@_locked
def consume_quest_notes(turn_marker: Any = None) -> List[str]:
    """The quest notes for the DM turn starting now, with consume_results' rule:
    handed again while the next note is built for the same marker, cleared once
    a later turn's note is built."""
    state = load_checks_state()
    notes = [n for n in state.get("questNotes") or [] if isinstance(n, dict)]
    delivered = state.get("questDelivered")
    again: List[Dict[str, Any]] = []
    if isinstance(delivered, dict) and delivered.get("turn") == turn_marker and turn_marker is not None:
        again = [n for n in delivered.get("notes") or [] if isinstance(n, dict)]
    handed = again + notes
    if handed or delivered is not None or "questNotes" in state:
        state.pop("questNotes", None)
        if handed:
            state["questDelivered"] = {"turn": turn_marker, "notes": handed}
        else:
            state.pop("questDelivered", None)
        write_checks_state(state)
    return [str(n.get("text") or "") for n in handed]


# #1472: the Hit Die offer after a short rest. One open offer per character
# under its own key; it lives until it is spent, a newer rest replaces or
# ends it, or the clock moves past the end of its rest turn. Delivery (the
# REST line in each DM Note) never closes it.

def rest_offers() -> List[Dict[str, Any]]:
    offers = load_checks_state().get("restOffers")
    return [dict(o) for o in offers if isinstance(o, dict)] if isinstance(offers, list) else []


def _write_offers(state: Dict[str, Any], offers: List[Dict[str, Any]]) -> None:
    state["restOffers"] = offers
    write_checks_state(state)


@_locked
def open_rest_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    """Open ``offer`` for its character, replacing an older one; give it the next restId."""
    state = load_checks_state()
    serial = state.get("restSerial") if type(state.get("restSerial")) is int else 0
    state["restSerial"] = serial + 1
    offer = dict(offer, restId=f"rest:{serial + 1}:{offer['characterId']}")
    others = [o for o in rest_offers() if o.get("characterId") != offer["characterId"]]
    _write_offers(state, others + [offer])
    return offer


@_locked
def close_rest_offers(character_id: Any = None, rest_id: Any = None) -> None:
    """Close the offers of ``character_id`` (or the one ``rest_id``); with neither, every offer."""
    state = load_checks_state()
    offers = rest_offers()
    kept = [o for o in offers
            if (character_id is not None and o.get("characterId") != character_id)
            or (rest_id is not None and o.get("restId") != rest_id)]
    if len(kept) != len(offers):
        _write_offers(state, kept)


@_locked
def settle_rest_offers(tick: Any, stamp: bool = True) -> List[Dict[str, Any]]:
    """The open offers at ``tick`` (the clock now), after stamping and closing.

    An unstamped offer is stamped with ``tick`` when the clock is still within
    its rest turn (``restTick`` plus the time the rest turn's later actions
    declared); an offer whose clock has moved past that, stamped or not, closes.
    An unreadable clock closes every offer: the rest's end cannot be shown.
    ``stamp`` False (inside a turn, whose later actions may still move the
    clock) closes but never stamps.
    """
    state = load_checks_state()
    offers = rest_offers()
    kept = []
    for offer in offers:
        limit = offer.get("tick") if type(offer.get("tick")) is int else _rest_turn_end(offer)
        if type(tick) is not int or limit is None or tick > limit:
            continue
        kept.append(dict(offer, tick=tick) if offer.get("tick") is None and stamp else offer)
    if kept != offers:
        _write_offers(state, kept)
    return kept


def _rest_turn_end(offer: Dict[str, Any]) -> Any:
    rest_tick, grace = offer.get("restTick"), offer.get("graceSeconds")
    if type(rest_tick) is not int or type(grace) is not int or grace < 0:
        return None
    return rest_tick + grace


# #1118 item 3: a short rest held for the player's hit-die answer. At most one,
# under its own top-level key: older builds keep an unknown key untouched and
# never read it as a pending check.

def pending_rest() -> Dict[str, Any] | None:
    entry = load_checks_state().get("pendingRest")
    return dict(entry) if isinstance(entry, dict) else None


@_locked
def hold_rest(entry: Dict[str, Any]) -> None:
    state = load_checks_state()
    state["pendingRest"] = entry
    write_checks_state(state)


@_locked
def take_pending_rest(entry: Dict[str, Any]) -> bool:
    """Remove ``entry`` before its rest is applied; False when the held rest changed (nothing is applied)."""
    state = load_checks_state()
    if state.get("pendingRest") != entry:
        return False
    del state["pendingRest"]
    write_checks_state(state)
    return True


@_locked
def close_pending_rest() -> Dict[str, Any] | None:
    """Close the held rest, if any, with no die spent; returns it."""
    state = load_checks_state()
    entry = state.pop("pendingRest", None)
    if entry is None:
        return None
    write_checks_state(state)
    return entry if isinstance(entry, dict) else None


@_locked
def close_pending_checks() -> List[Dict[str, Any]]:
    """Close every pending check with no result line (combat began; #1118 item 4); returns them."""
    state = load_checks_state()
    closed = state["pending"]
    if not closed:
        return []
    state["pending"] = []
    write_checks_state(state)
    return [entry for entry in closed if isinstance(entry, dict)]
