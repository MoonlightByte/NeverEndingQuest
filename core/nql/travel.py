# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The engine's party follows the tracker (C10a).

The world declares a map (utils/travel_map.py); the document holds the
party, where each member is and the places visited. The tracker stays the
source of truth for position: after NEQ commits a move, the engine party is
brought in line by value (NQL docs/WORLD_MAP.md, LIVE_STATE.md):

- A committed in-module move is walked along the path NEQ committed, one
  hop per ``travel party to``, so every place on it is marked visited. A
  single hop is always legal (the departure counts as visited; the end may
  be unvisited or a hazard). The request id is ``realign:<checkpoint>``;
  a longer path is split over ``realign:<checkpoint>:<n>`` within the
  engine's work bound. When the party is not all at the path's start, the
  same request first moves each member there.
- A request id already in the document's ``requests`` is skipped (a
  resume). A refused walk applies nothing; the party is then moved with
  ``move`` under ``realign:<checkpoint>:move`` (its own id: the refused
  walk is not on record, and the resume must not reuse the id).
- Every other change of place (the startup wizard, a module switch, a
  restore) walked nothing: ``move`` marks nothing, under a fresh
  ``align:<random id>``.
- Membership changes only through ``join party`` / ``leave party``; a member
  that left stays declared until its leave is applied (travel_map.lines).

Never a gate on play: an engine that is unavailable or refuses leaves the
tracker as it is, with a warning, and the next call aligns again.
"""
import os
import uuid
from typing import Any, Dict, List, Optional

from utils.enhanced_logger import info, warning
from utils.file_operations import safe_read_json
from utils import travel_map

# The engine's work bound per request (WORLD_MAP.md): a hop costs a move per
# member plus its time; membership edits and the start moves take the rest.
UNITS = 128


def _members(tracker: Dict[str, Any]) -> List[str]:
    from utils.roster_conversion import ACTOR
    return [i for i, _ in travel_map.party_members(tracker) if i != ACTOR]


def _membership(live: Dict[str, Any], members: List[str]) -> List[str]:
    party = list((live.get("map") or {}).get("party") or [])
    out = ["leave party %s;" % travel_map.q(i) for i in party if i not in members]
    out += ["join party %s;" % travel_map.q(i) for i in members if i not in party]
    return out


def _moves(live: Dict[str, Any], members: List[str], place: str, source_place: Optional[str]) -> List[str]:
    """`move` for each member not at place. A member the document does not
    hold yet takes the source's place this call (travel_map.lines)."""
    at = {c.get("id"): c.get("location") for c in live.get("characters") or [] if isinstance(c, dict)}
    return ["move %s to %s;" % (travel_map.q(i), travel_map.q(place))
            for i in members if at.get(i, source_place) != place]


def align_actions(live: Dict[str, Any], tracker: Dict[str, Any]) -> List[str]:
    """The join / leave / move lines that bring the document's party to the
    tracker's members and place, or [] when it is there (or has no map)."""
    if not isinstance(live.get("map"), dict):
        return []
    members = _members(tracker)
    here = travel_map.tracker_place(tracker)
    out = _membership(live, members)
    if here in set(live.get("places") or []):
        out += _moves(live, members, here, here)
    return out


def _stops(checkpoint: Optional[Dict[str, Any]], here: Optional[str],
           places: Optional[set]) -> Optional[List[str]]:
    """The committed path as engine places, when it still ends at the
    tracker's place and every stop is in places (not checked when None);
    else None."""
    checkpoint = checkpoint or {}
    path = checkpoint.get("path")
    module = str(checkpoint.get("module_name") or "").replace(" ", "_")
    if not isinstance(path, list) or len(path) < 2 or not module:
        return None
    stops: List[str] = []
    for loc in path:
        place = "loc:%s/%s" % (module, loc)
        if not stops or stops[-1] != place:
            stops.append(place)
    if len(stops) < 2 or stops[-1] != here or (places is not None and any(p not in places for p in stops)):
        return None
    return stops


def _walk(root: str, cp: str, stops: List[str], members: List[str], live: Dict[str, Any],
          done: set, here: str) -> str:
    """Send the chain: "walked", "on record" (a resume), "unavailable" or
    "refused"."""
    from core.nql import occupants
    n = len(members)
    # Fixed by party size only, so a resume splits the same way.
    per = max(1, (UNITS - 4 * n - 8) // (n + 2))
    hops = stops[1:]
    membership_sent = False
    sent = False
    for k, start in enumerate(range(0, len(hops), per)):
        rid = "realign:%s" % cp if k == 0 else "realign:%s:%d" % (cp, k)
        if rid in done:
            membership_sent = True
            continue
        actions: List[str] = []
        if not membership_sent:
            actions += _membership(live, members)
            membership_sent = True
        actions += _moves(live, members, stops[start], here)
        actions += ["travel party to %s;" % travel_map.q(p) for p in hops[start:start + per]]
        response = occupants.request("\n".join(actions), rid, root=root, actor=members[0], align=False)
        if response is None:
            return "unavailable"
        if not response.get("ok"):
            fault = response.get("fault") or {}
            warning("TRAVEL: the walk %s was refused (%s: %s); moving the party instead" % (
                rid, fault.get("code") or response.get("error"), fault.get("actual") or fault.get("message")),
                category="location_transitions")
            return "refused"
        live = response.get("live_state") or live
        sent = True
    return "walked" if sent else "on record"


def _align(root: str, rid: str, live: Dict[str, Any], tracker: Dict[str, Any], why: str) -> str:
    """Send the align actions under rid: "aligned", "moved", "unavailable" or "refused"."""
    from core.nql import occupants
    from utils.roster_conversion import ACTOR
    here = travel_map.tracker_place(tracker)
    if here and here not in set(live.get("places") or []):
        warning("TRAVEL: the party's place %s is not declared; its position is not aligned" % here,
                category="location_transitions")
    actions = align_actions(live, tracker)
    if not actions:
        return "aligned"
    response = occupants.request("\n".join(actions), rid, root=root, actor=ACTOR, align=False)
    if response is None:
        return "unavailable"
    if not response.get("ok"):
        fault = response.get("fault") or {}
        warning("TRAVEL: aligning the party (%s) was refused: %s" % (
            rid, fault.get("message") or response.get("error")), category="location_transitions")
        return "refused"
    info("TRAVEL: the engine party follows the tracker (%s, %s): %s" % (why, rid, " ".join(actions)),
         category="location_transitions")
    return "moved"


def align_id() -> str:
    """A fresh request id for an alignment that walked nothing."""
    return "align:%s" % uuid.uuid4().hex


def realign(checkpoint: Optional[Dict[str, Any]] = None, *, root: str = ".") -> Optional[str]:
    """Bring the document's party to the tracker. With the v2 checkpoint of
    a committed in-module move, walk its path; else (or when the walk is
    refused) move. Returns what was done, or None when nothing could be."""
    try:
        from core.nql import occupants
        tracker = safe_read_json(os.path.join(root, "party_tracker.json")) or {}
        members = _members(tracker)
        here = travel_map.tracker_place(tracker)
        # The document as the engine last wrote it. The engine is asked
        # first only when it has no map yet or does not hold a place in
        # play (a module new to the world); a walk already on record then
        # costs no call.
        live = occupants._load(root) or {}
        wanted = set(_stops(checkpoint, here, None) or []) | ({here} if here else set())
        if not isinstance(live.get("map"), dict) or not wanted <= set(live.get("places") or []):
            response = occupants.request(root=root, align=False)
            if not response or not response.get("ok"):
                return None
            live = response.get("live_state") or {}
        if not isinstance(live.get("map"), dict):
            return None
        done = {r.get("id") for r in live.get("requests") or [] if isinstance(r, dict)}
        cp = str((checkpoint or {}).get("operation_id") or "")
        stops = _stops(checkpoint, here, set(live.get("places") or []))
        fallback = "realign:%s:move" % cp if cp else ""
        if stops and members and fallback not in done:
            outcome = _walk(root, cp, stops, members, live, done, here)
            if outcome == "on record":
                # The walk applied before (a resume); anything since moved
                # the party without walking.
                return _align(root, align_id(), live, tracker, "walk on record")
            if outcome == "walked":
                info("TRAVEL: the engine party walked %s (realign:%s)" % (" -> ".join(stops), cp),
                     category="location_transitions")
                return outcome
            if outcome == "unavailable":
                return None
            response = occupants.request(root=root, align=False)
            if not response or not response.get("ok"):
                return None
            live = response.get("live_state") or live
        elif checkpoint is not None and "path" not in checkpoint:
            info("TRAVEL: checkpoint %s has no path; the party is moved, not walked" % cp,
                 category="location_transitions")
        rid = fallback if fallback and fallback not in done else align_id()
        return _align(root, rid, live, tracker, "after a move" if cp else "align")
    except Exception as exc:  # fail forward: the tracker already stands
        warning("TRAVEL: the engine party was not aligned (%s)" % exc, category="location_transitions")
        return None
