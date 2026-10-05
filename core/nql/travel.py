# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The engine's party and the in-module move authority (C10a, C10b).

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

C10b, the engine leads (Q5 rule A: the party stops at every place it has
not visited, and moves freely through visited places with no hostile
present):

- ``engine_route`` answers whether a proposed in-module move may go, from
  the map view of the party's first member: approved (the destination is
  reachable through visited places), a halt at a hostile place on the way,
  or an unvisited stop (the first unvisited place on NEQ's own route, and
  the unvisited places reachable now, for the DM to choose from).
- An engine-approved move is committed after the tracker write with
  ``travel party to`` under ``travel:<checkpoint>``; the engine marks the
  departure and the arrival. A refusal, or a trip that ends elsewhere (the
  world changed after review), moves the party to the tracker's place
  under ``realign:<checkpoint>:move``, with a warning.

C11, travel time: route ticks are seconds at SRD normal pace
(utils/travel_map.py), so an engine-approved move's trip time is a time in
game minutes (``minutes``). Its travel-owned updateTime is at least the
SRD fast-pace time (``floor_minutes``); without one it is the normal-pace
time; a larger DM estimate stands as added time (``timed_deferred``). The
committing trip's own ticks are compared with the approved time.

C12, across modules (engine follows; owner O4/O5): a module switch travels
over the join of its two modules (utils/module_joins.py), whose route is
declared only in the switch's own requests:

- ``crossing``, at staging: the first crossing between two modules proposes
  the join, from the place the party leaves to the place it arrives at, its
  time the DM's updateTime; a later crossing reads the engine's time to the
  target over the join (the map view) and applies C11's floor to the DM's
  updateTime.
- ``realign``, after the tracker is published: the party travels ``travel
  party to`` under ``travel:<checkpoint>``, and the join is recorded once
  the trip is on record. A refusal or a trip that ends elsewhere moves the
  party, as in-module, and records nothing. The engine never refuses the
  switch itself.

J2, the journal (core/nql/journal.py): the request that moves the party
for a transition records its ``departure`` at the origin, before the first
``travel party to`` (the trip, the walk's first part, or the fallback
move). Its ``arrival`` at the tracker's place goes in the request that
brings the clock to the approved arrival (game_clock.apply_staged), or
after the move when the transition has no deferred updateTime. A journal
fault never stops the move.

Never a gate on play: an engine that is unavailable or refuses leaves the
tracker as it is, with a warning, and the next call aligns again. With the
engine unavailable, the route check stays NEQ's own (snapshot route and
T021).
"""
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from utils.enhanced_logger import info, warning
from utils.file_operations import safe_read_json
from utils import travel_map

# The engine's work bound per request (WORLD_MAP.md): a hop costs a move per
# member plus its time; membership edits and the start moves take the rest.
UNITS = 128

# SRD fast pace: 4 miles an hour against the normal 3, so 3/4 of the time
# (owner Q1/Q2, C11: the DM may travel at fast pace, never faster).
FAST_PACE = (3, 4)


def minutes(ticks: Any) -> Optional[int]:
    """Game minutes for a trip of `ticks` seconds (rounded up), or None."""
    if type(ticks) is not int or ticks < 0:
        return None
    return -(-ticks // 60)


def floor_minutes(travel_minutes: int) -> int:
    """The least travel time at SRD fast pace (rounded up)."""
    return -(-travel_minutes * FAST_PACE[0] // FAST_PACE[1])


def timed_deferred(deferred: List[Any], travel_minutes: Optional[int]) -> List[Any]:
    """The deferred actions of an engine-approved move with its travel time
    applied (C11): the first travel-owned updateTime is raised to the
    fast-pace floor when the DM's estimate is lower (or unreadable), and one
    with the normal-pace time leads when there is none. A larger estimate
    stands (slow pace, terrain, detours). Without engine minutes the list is
    returned as it is (NEQ's own route check: the DM's estimate)."""
    if type(travel_minutes) is not int:
        return deferred
    least = floor_minutes(travel_minutes)
    out = list(deferred or [])
    for index, action in enumerate(out):
        if isinstance(action, dict) and action.get("action") == "updateTime":
            parameters = action.get("parameters") if isinstance(action.get("parameters"), dict) else {}
            try:
                estimate = int(parameters.get("timeEstimate"))
            except (TypeError, ValueError):
                estimate = None
            if estimate is not None and estimate >= least:
                info("TRAVEL: travel time %d min (engine %d min at normal pace, at least %d)"
                     % (estimate, travel_minutes, least), category="location_transitions")
                return out
            out[index] = dict(action, parameters=dict(parameters, timeEstimate=least))
            info("TRAVEL: travel time %d min: the DM's estimate %s is below the fast-pace time "
                 "(engine %d min at normal pace)" % (least, parameters.get("timeEstimate"), travel_minutes),
                 category="location_transitions")
            return out
    info("TRAVEL: travel time %d min (engine, normal pace; the DM gave none)" % travel_minutes,
         category="location_transitions")
    return [{"action": "updateTime", "parameters": {"timeEstimate": travel_minutes}}] + out


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
          done: set, here: str, departure: Optional[Tuple[str, Optional[str]]] = None,
          arrival: Optional[Tuple[str, Optional[str]]] = None) -> str:
    """Send the chain: "walked", "on record" (a resume), "unavailable" or
    "refused". The departure goes in the first part, the arrival after the
    last hop (J2)."""
    from core.nql import journal
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
        lines = [(a, None) for a in actions]
        if k == 0 and departure:
            lines.append(departure)
        lines += [("travel party to %s;" % travel_map.q(p), None) for p in hops[start:start + per]]
        if start + per >= len(hops) and arrival:
            lines.append(arrival)
        response, how = journal.send(lines, rid, root=root, actor=members[0])
        if how == "on record":
            continue
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


def _align(root: str, rid: str, live: Dict[str, Any], tracker: Dict[str, Any], why: str,
           departure: Optional[Tuple[str, Optional[str]]] = None,
           arrival: Optional[Tuple[str, Optional[str]]] = None) -> str:
    """Send the align actions under rid: "aligned", "moved", "unavailable" or
    "refused". A transition's fallback move carries its journal entries, the
    departure before the move and the arrival after it (J2)."""
    from core.nql import journal
    from utils.roster_conversion import ACTOR
    here = travel_map.tracker_place(tracker)
    if here and here not in set(live.get("places") or []):
        warning("TRAVEL: the party's place %s is not declared; its position is not aligned" % here,
                category="location_transitions")
    actions = align_actions(live, tracker)
    lines = ([departure] if departure else []) + [(a, None) for a in actions] + ([arrival] if arrival else [])
    if not lines:
        return "aligned"
    response, how = journal.send(lines, rid, root=root, actor=ACTOR)
    if how == "on record" or (response is None and how == "without"):
        return "aligned"
    if response is None:
        return "unavailable"
    if not response.get("ok"):
        fault = response.get("fault") or {}
        warning("TRAVEL: aligning the party (%s) was refused: %s" % (
            rid, fault.get("message") or response.get("error")), category="location_transitions")
        return "refused"
    if not actions:
        return "aligned"
    info("TRAVEL: the engine party follows the tracker (%s, %s): %s" % (why, rid, " ".join(actions)),
         category="location_transitions")
    return "moved"


def align_id() -> str:
    """A fresh request id for an alignment that walked nothing."""
    return "align:%s" % uuid.uuid4().hex


def _place_ref(value: Any) -> str:
    """A place in a view: its id string, or an object with an id."""
    if isinstance(value, dict):
        return str(value.get("id") or "")
    return str(value or "")


def map_view(root: str = ".", joins: Tuple[Tuple[str, str, int], ...] = ()) -> Optional[Dict[str, Any]]:
    """{"view": the map view of the party's first member, "live": the
    document}, after the document's party is brought to the tracker. None
    when the engine is unavailable, the world has no map or the tracker
    names no party member. `joins`: cross-module routes for this view (C12)."""
    from core.nql import occupants
    tracker = safe_read_json(os.path.join(root, "party_tracker.json")) or {}
    members = _members(tracker)
    if not members:
        return None
    live = occupants._load(root) or {}
    if isinstance(live.get("map"), dict) and align_actions(live, tracker):
        _align(root, align_id(), live, tracker, "before the map view")
    response = occupants.request(root=root, align=False, map_view=(members[0],), joins=joins)
    if not response or not response.get("ok") or not response.get("map"):
        return None
    return {"view": response["map"][0], "live": response.get("live_state") or {}}


def _hostiles(place: str, root: str) -> List[str]:
    """The names of the hostile occupants present at place (locations view)."""
    from core.nql import occupants
    out: List[str] = []
    for loc in occupants.view([place], root=root):
        for occ in loc.get("present") or []:
            if isinstance(occ, dict) and occ.get("attitude") == "hostile":
                out.append(str(occ.get("name") or occ.get("id")))
    return out


def engine_route(module: str, origin_id: str, destination_id: str, path: List[str], *,
                 root: str = ".") -> Optional[Dict[str, Any]]:
    """The engine's verdict on an in-module move (C10b). `path` is NEQ's
    snapshot route (origin to destination, bare location ids), used only to
    name the first unvisited place on the way. Returns None when the engine
    cannot answer (the caller keeps NEQ's own route check), else a dict:

    - {"verdict": "approved", "stops", "ticks", "minutes"}: `minutes` is
      the trip time in game minutes (C11), None if the engine gave none
    - {"verdict": "halt", "stop", "hostiles"}: a place on the way holds a
      present hostile occupant; the trip stops there.
    - {"verdict": "unvisited_stop", "stop", "fresh"}: the way crosses a
      place the party has not visited; `stop` is the first such place on
      NEQ's route (None when the engine cannot reach it), `fresh` every
      unvisited place reachable now (bare ids).
    """
    try:
        return _engine_route(module, origin_id, destination_id, path, root)
    except Exception as exc:  # fail forward: NEQ's own route check decides
        warning("TRAVEL: the engine route check failed (%s); the route check stays NEQ's" % exc,
                category="location_transitions")
        return None


def _engine_route(module: str, origin_id: str, destination_id: str, path: List[str],
                  root: str) -> Optional[Dict[str, Any]]:
    module = (module or "").replace(" ", "_")
    if not module or origin_id == destination_id:
        return None

    def full(loc: str) -> str:
        return "loc:%s/%s" % (module, loc)

    def bare(place: str) -> str:
        prefix = "loc:%s/" % module
        return place[len(prefix):] if place.startswith(prefix) else place

    got = map_view(root)
    if got is None:
        return None
    view, live = got["view"], got["live"]
    here = _place_ref(view.get("location"))
    if here != full(origin_id):
        warning("TRAVEL: the engine party is at %s, not at the move's origin %s; the route check "
                "stays NEQ's" % (here, full(origin_id)), category="location_transitions")
        return None
    reach = {_place_ref(d.get("to")): d for d in view.get("destinations") or [] if isinstance(d, dict)}

    def halt_or(place: str, otherwise: Dict[str, Any]) -> Dict[str, Any]:
        halt = _place_ref(reach[place].get("halts_at"))
        if not halt:
            return otherwise
        return {"verdict": "halt", "stop": bare(halt), "hostiles": _hostiles(halt, root)}

    target = full(destination_id)
    if target in reach:
        entry = reach[target]
        return halt_or(target, {"verdict": "approved", "stops": entry.get("stops"), "ticks": entry.get("ticks"),
                                "minutes": minutes(entry.get("ticks"))})
    visited = set((live.get("map") or {}).get("visited") or [])
    fresh = [bare(p) for p, d in sorted(reach.items())
             if not d.get("visited") and p.startswith("loc:%s/" % module)]
    first = next((loc for loc in list(path)[1:] if full(loc) not in visited), None)
    if first is not None and full(first) in reach:
        return halt_or(full(first), {"verdict": "unvisited_stop", "stop": first, "fresh": fresh})
    return {"verdict": "unvisited_stop", "stop": None, "fresh": fresh}


def crossing(source_module: str, source_location: str, target_module: str, target_location: str,
             clock_action: Dict[str, Any], *, root: str = ".") -> Dict[str, Any]:
    """The join a module switch travels over, and its clock action (C12):
    {"join", "minutes", "clock_action"}. The first crossing between the two
    modules proposes the join (the place the party leaves, the place it
    arrives at, the DM's updateTime); a later one reads the engine's time to
    the target over the recorded join and floors the DM's updateTime
    (``timed_deferred``). "join" is None when the switch cannot be one (it
    then goes as before: the party is moved, not traveled)."""
    none = {"join": None, "minutes": None, "clock_action": clock_action}
    try:
        from utils import module_joins
        join = module_joins.between(source_module, target_module, root)
        if join is None:
            estimate = ((clock_action or {}).get("parameters") or {}).get("timeEstimate")
            join = module_joins.proposed(source_module, source_location, target_module, target_location,
                                         estimate, "")
            if join is None:
                warning("TRAVEL: the switch %s -> %s cannot be joined (estimate %r); the party is moved"
                        % (source_module, target_module, estimate), category="location_transitions")
                return none
            info("TRAVEL: first crossing %s -> %s: the journey takes the DM's %d min"
                 % (module_joins.place(source_module, source_location),
                    module_joins.place(target_module, target_location), join["minutes"]),
                 category="location_transitions")
            return {"join": join, "minutes": join["minutes"], "clock_action": clock_action}
        got = map_view(root, joins=(module_joins.route(join),))
        target = module_joins.place(target_module, target_location)
        found = None
        for entry in (got or {}).get("view", {}).get("destinations") or []:
            if isinstance(entry, dict) and _place_ref(entry.get("to")) == target \
                    and not _place_ref(entry.get("halts_at")):
                found = minutes(entry.get("ticks"))
        if found is None:
            info("TRAVEL: %s is not reachable over the join now; the DM's time stands" % target,
                 category="location_transitions")
            return {"join": join, "minutes": None, "clock_action": clock_action}
        return {"join": join, "minutes": found, "clock_action": timed_deferred([clock_action], found)[0]}
    except Exception as exc:  # fail forward: the switch goes as before
        warning("TRAVEL: the crossing check failed (%s); the party is moved" % exc,
                category="location_transitions")
        return none


def _ends(checkpoint: Dict[str, Any]) -> Tuple[str, str]:
    """The trip's origin and target places. A module switch's target is in
    its target module (C12)."""
    module = str(checkpoint.get("module_name") or "").replace(" ", "_")
    target_module = module
    handoff = checkpoint.get("module_handoff")
    if checkpoint.get("movement_kind") == "cross_module_root" and isinstance(handoff, dict):
        target_module = str((handoff.get("target_projection") or {}).get("module") or "").replace(" ", "_")
    return ("loc:%s/%s" % (module, checkpoint.get("origin_location_id")),
            "loc:%s/%s" % (target_module, checkpoint.get("destination_location_id")))


def _journal(checkpoint: Optional[Dict[str, Any]], live: Dict[str, Any],
             here: Optional[str]) -> Tuple[Optional[Tuple[str, Optional[str]]], Optional[Tuple[str, Optional[str]]]]:
    """J2: the transition's departure line (at its origin) and, when it has
    no deferred updateTime (whose top-up records it at the approved time),
    its arrival line at the tracker's place. (None, None) without a
    checkpoint."""
    from core.nql import journal
    cp = str((checkpoint or {}).get("operation_id") or "")
    if not cp:
        return None, None
    module = str(checkpoint.get("module_name") or "")
    departure = journal.line(journal.entry_id(module, cp, "departure"), "departure", _ends(checkpoint)[0], live)
    deferred = (checkpoint.get("deferred_actions") or {}).get("actions") or []
    if any(isinstance(a, dict) and a.get("family") == "updateTime" for a in deferred):
        return departure, None
    return departure, journal.line(journal.entry_id(module, cp, "arrival"), "arrival", here, live)


def _joins(checkpoint: Optional[Dict[str, Any]]) -> Tuple[Tuple[str, str, int], ...]:
    """The join route a module switch's trip declares, or () (C12)."""
    from utils import module_joins
    join = (checkpoint or {}).get("join")
    return (module_joins.route(join),) if module_joins.valid(join) else ()


def _travel(root: str, checkpoint: Dict[str, Any], members: List[str], live: Dict[str, Any],
            done: set, here: Optional[str]) -> str:
    """Commit an engine-approved move: "traveled", "on record" (a resume),
    "diverged" (the trip, or the tracker, ended elsewhere), "refused" or
    "unavailable". The departure goes before the trip (an old retry is
    refused at it before the trip could run again), the arrival after it
    when the move has no time of its own (J2)."""
    from core.nql import journal
    cp = str(checkpoint.get("operation_id") or "")
    rid = "travel:%s" % cp
    if rid in done:
        return "on record"
    origin, target = _ends(checkpoint)
    if target != here:
        return "diverged"
    departure, arrival = _journal(checkpoint, live, here)
    lines = [(a, None) for a in _membership(live, members) + _moves(live, members, origin, here)]
    lines += ([departure] if departure else []) + [("travel party to %s;" % travel_map.q(target), None)]
    lines += [arrival] if arrival else []
    response, how = journal.send(lines, rid, root=root, actor=members[0], joins=_joins(checkpoint))
    if how == "on record":
        return "on record"
    if response is None:
        return "unavailable"
    if not response.get("ok"):
        fault = response.get("fault") or {}
        warning("TRAVEL: the trip %s was refused (%s: %s); moving the party instead" % (
            rid, fault.get("code") or response.get("error"), fault.get("actual") or fault.get("message")),
            category="location_transitions")
        return "refused"
    after = response.get("live_state") or {}
    end = {c.get("id"): c.get("location") for c in after.get("characters") or [] if isinstance(c, dict)}
    if end.get(members[0]) != target:
        warning("TRAVEL: the trip %s ended at %s, not %s (the world changed after the review); "
                "the party follows the tracker" % (rid, end.get(members[0]), target),
                category="location_transitions")
        return "diverged"
    approved = checkpoint.get("travel_minutes")
    if type(approved) is int:
        # The time is read once, from this committing trip (nql-7d, C11).
        trips = [e.get("trip") for e in (response.get("receipt") or {}).get("events") or []
                 if isinstance(e, dict) and e.get("kind") == "PartyTraveled"]
        took = minutes((trips[-1] or {}).get("ticks")) if trips and isinstance(trips[-1], dict) else None
        if took != approved:
            warning("TRAVEL: the trip %s took %s min, not the approved %d (the world changed after "
                    "the review); the clock keeps the approved time" % (rid, took, approved),
                    category="location_transitions")
    return "traveled"


def realign(checkpoint: Optional[Dict[str, Any]] = None, *, root: str = ".") -> Optional[str]:
    """Bring the document's party to the tracker. With the v2 checkpoint of
    a committed in-module move: an engine-approved move (authority
    "engine") travels; one NEQ's own route check approved walks its path;
    else (or when the trip or walk is refused) move. Returns what was done,
    or None when nothing could be."""
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
        engine = (checkpoint or {}).get("authority") == "engine"
        if engine:
            wanted.add(_ends(checkpoint)[0])
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
        if engine and members and fallback not in done:
            outcome = _travel(root, checkpoint, members, live, done, here)
            if outcome in ("traveled", "on record") and _joins(checkpoint):
                # C12: the engine crossed by the join, so it is kept (a first
                # crossing writes it; a recorded pair is left as it is). A
                # crossing the engine refused records nothing.
                from utils import module_joins
                module_joins.record(checkpoint["join"], root)
            if outcome == "traveled":
                if _joins(checkpoint):
                    info("TRAVEL: the party crossed %s -> %s (travel:%s)" % (_ends(checkpoint) + (cp,)),
                         category="location_transitions")
                    return outcome
                info("TRAVEL: the party traveled %s/%s -> %s (travel:%s)" % (
                    checkpoint.get("module_name"), checkpoint.get("origin_location_id"),
                    checkpoint.get("destination_location_id"), cp), category="location_transitions")
                return outcome
            if outcome == "on record":
                return _align(root, align_id(), live, tracker, "trip on record")
            if outcome == "unavailable":
                return None
            response = occupants.request(root=root, align=False)
            if not response or not response.get("ok"):
                return None
            live = response.get("live_state") or live
        elif stops and members and fallback not in done:
            outcome = _walk(root, cp, stops, members, live, done, here, *_journal(checkpoint, live, here))
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
        elif checkpoint is not None and not engine and "path" not in checkpoint:
            info("TRAVEL: checkpoint %s has no path; the party is moved, not walked" % cp,
                 category="location_transitions")
        if fallback and fallback not in done:
            return _align(root, fallback, live, tracker, "after a move", *_journal(checkpoint, live, here))
        return _align(root, align_id(), live, tracker, "after a move" if cp else "align")
    except Exception as exc:  # fail forward: the tracker already stands
        warning("TRAVEL: the engine party was not aligned (%s)" % exc, category="location_transitions")
        return None
