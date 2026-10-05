# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""J2: the engine's journal, written in the request that moves the party.

The engine keeps each journal entry as a typed record, atomic with the
request that made it (NQL J1, docs/JOURNAL.md; live_state format v5). NEQ
records a ``departure`` in the request that moves the party, before its
first ``travel party to``, and an ``arrival`` in the request that brings the
clock to the approved arrival (core/nql/game_clock.py), or after the move
when the trip has no time of its own. The engine numbers and stamps each
entry; NEQ names the place (``at``) and the party, and sends no text: the
prose stays in journal.json, keyed by the entry's id.

- An id is ``journal:<module>/<transition operation_id>/<kind>``. The
  operation_id is the transition checkpoint's uuid4, so an id never repeats,
  a resume of the same transition sends the same id, and no character, item,
  place, occupant or quest id begins with ``journal:``.
- An entry is sent only when its place is one the document holds (an
  undeclared place would refuse the whole request, trip or clock with it).
- A journal fault never stops the move or the clock. A refusal at an entry
  (E_JOURNAL, or an entry's line in the compile diagnostics) is sent again
  without the entries, under the same request id (a refused request applies
  and keeps nothing). E_DUPLICATE ``journal`` at an entry's id is read back
  by id: found, the request applied before; not found, the id clashes with
  another record and the entries are left out. Decided from the typed fault,
  never from its message.
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from utils.enhanced_logger import info, warning

KINDS = ("departure", "arrival", "event", "discovery", "note")

# One action of a request: its line, and the entry id when it records one.
Line = Tuple[str, Optional[str]]


def entry_id(module: str, operation_id: str, kind: str) -> str:
    return "journal:%s/%s/%s" % (str(module or "").replace(" ", "_"), operation_id, kind)


def line(entry: str, kind: str, place: Optional[str], live: Optional[Dict[str, Any]]) -> Optional[Line]:
    """The ``record journal`` action for `entry` at `place`, or None (logged)
    when the document does not hold the place. ``with party`` needs a map."""
    live = live or {}
    if not place or place not in set(live.get("places") or []):
        warning("JOURNAL: %s is not recorded: its place %s is not declared" % (entry, place),
                category="location_transitions")
        return None
    party = " with party" if isinstance(live.get("map"), dict) else ""
    return ("record journal %s %s at %s%s;" % (json.dumps(entry), kind, json.dumps(place), party), entry)


def view(ids: List[str], root: str = ".") -> List[Dict[str, Any]]:
    """The engine's entries with these ids ([] when none, or no engine)."""
    from core.nql import occupants
    response = occupants.request(journal_view={"id": list(ids)}, root=root, create=False)
    if not response or not response.get("ok"):
        return []
    return list((response.get("journal") or {}).get("entries") or [])


def _cause(response: Dict[str, Any], lines: List[Line], root: str) -> Optional[str]:
    """Why a request that carried entries was refused: "on record" (an entry
    is held: the request applied before), "entry" (an entry caused it), or
    None (the request's own refusal)."""
    ids = {entry for _, entry in lines if entry}
    fault = response.get("fault") or {}
    if fault.get("code") == "E_DUPLICATE" and fault.get("field") == "journal" and fault.get("subject") in ids:
        return "on record" if view([fault["subject"]], root) else "entry"
    if fault.get("code") == "E_JOURNAL":
        return "entry"
    at, numbers = 1, set()
    for text, entry in lines:
        if entry:
            numbers.add(at)
        at += text.count("\n") + 1
    for item in response.get("diagnostics") or []:
        if isinstance(item, dict) and item.get("source") == "actions.nql" and (
                item.get("code") == "E_JOURNAL" or item.get("line") in numbers):
            return "entry"
    return None


def send(lines: List[Line], request_id: str, *, root: str = ".", resend_on_record: bool = False,
         **options: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """One request of `lines` through occupants.request (align=False).
    Returns (response, how): "sent"; "on record" (an entry is held, so the
    request applied before; with `resend_on_record` the rest is sent again
    instead); or "without" (an entry caused the refusal: the rest was sent
    alone, or nothing when the entries were all of it)."""
    from core.nql import occupants

    def go(parts: List[Line]) -> Optional[Dict[str, Any]]:
        return occupants.request("\n".join(text for text, _ in parts), request_id, root=root,
                                 align=False, **options)
    response = go(lines)
    if response is None or response.get("ok") or not any(entry for _, entry in lines):
        return response, "sent"
    cause = _cause(response, lines, root)
    if cause is None:
        return response, "sent"
    ids = ", ".join(entry for _, entry in lines if entry)
    if cause == "on record" and not resend_on_record:
        info("JOURNAL: %s is on record; request %s applied before" % (ids, request_id),
             category="location_transitions")
        return response, "on record"
    fault = response.get("fault") or {}
    warning("JOURNAL: %s left out of %s (%s %s); the rest goes on" % (
        ids, request_id, cause, fault.get("code") or response.get("error")), category="location_transitions")
    rest = [part for part in lines if not part[1]]
    if not rest:
        return None, "without"
    return go(rest), "without"

