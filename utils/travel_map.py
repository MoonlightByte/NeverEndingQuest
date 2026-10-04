# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The engine world's map (C10a): the routes NEQ walks, the party and the
places already visited.

The roster and quest world of utils/roster_conversion.py declares a ``map {}``
so the engine holds the party's place and the visited record (NQL
docs/WORLD_MAP.md, LIVE_STATE.md):

- Routes: each world module's links as build_active_module_snapshot resolves
  them (connectivity plus areaConnectivity / areaConnectivityId), the graph
  the route check walks today. A link touching a place the snapshot marks
  invalid is left out, as the route check never crosses one. Every route
  takes TICKS: travel time stays the DM's in C10a, and with equal ticks the
  engine's quickest path is the one with the fewest stops.
- The party: one character per party member, ``char:<slug>`` as the genesis
  world names them, at the tracker's place in the tracker's module; plus
  every member the document's party still holds, until its ``leave party``
  is applied (a held party member the world stops declaring refuses the
  whole call).
- Visited: the tracker's place (when the world declares it; else the party
  stands at a declared place of its module, not marked) and every place
  play has marked. That is ``explorationState`` (written on departure), or
  a summary or gameplay encounter the played file holds that its authored
  master does not; an authored summary is module prose, not a visit (The
  Pumpkin King's Curse authors one for every place). The engine takes the
  party and visited from the source once, the first time the document
  meets a map; after that the document's record stands, and
  core/nql/travel.py keeps it aligned with the tracker.
"""
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

TICKS = 60

# {module dir: (the played area files, [(source id, target id)])}: the links
# are resolved again only when the played area files differ by value.
_ROUTES: Dict[str, Tuple[Any, List[Tuple[str, str]]]] = {}


def q(text):
    return json.dumps(text, ensure_ascii=True)


def member_id(name: str) -> str:
    """The engine id of a party member: the genesis world's."""
    from core.nql.genesis import slug
    return "char:" + slug(name)


def party_members(tracker: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """[(character id, name)] for the tracker's partyMembers, in order, once each."""
    out: List[Tuple[str, str]] = []
    seen = set()
    for entry in (tracker or {}).get("partyMembers") or []:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if not isinstance(name, str) or not name.strip():
            continue
        ident = member_id(name.strip())
        if ident not in seen:
            seen.add(ident)
            out.append((ident, name.strip()))
    return out


def tracker_place(tracker: Optional[Dict[str, Any]]) -> Optional[str]:
    """``loc:<tracker module>/<currentLocationId>``, or None when either is missing."""
    tracker = tracker or {}
    module = str(tracker.get("module") or "").replace(" ", "_")
    loc = (tracker.get("worldConditions") or {}).get("currentLocationId")
    if not module or not isinstance(loc, str) or not loc:
        return None
    return "loc:%s/%s" % (module, loc)


def module_links(game, module: str) -> List[Tuple[str, str]]:
    """The module's directed links between valid places, as the route check
    resolves them (build_active_module_snapshot, without the rosters). The
    result is kept while the played area files Game read are equal by value
    (the snapshot reads the same files; a legacy area file at the module's
    top level is read but not compared)."""
    from utils.path_encounter_analyzer import build_active_module_snapshot

    module_dir = os.path.abspath(game.paths[module])
    key = json.dumps(game.played_areas.get(module) or {}, sort_keys=True)
    hit = _ROUTES.get(module_dir)
    if hit and hit[0] == key:
        return hit[1]
    snapshot = build_active_module_snapshot(module, roster=False, module_dir=module_dir)
    nodes = snapshot.get("nodes") or {}
    invalid = set(snapshot.get("invalid_location_ids") or [])
    links = []
    for source, targets in sorted((snapshot.get("edges") or {}).items()):
        for target in dict.fromkeys(targets):
            if source != target and source in nodes and target in nodes \
                    and source not in invalid and target not in invalid:
                links.append((source, target))
    _ROUTES[module_dir] = (key, links)
    return links


def played_visit(played: Dict[str, Any], master: Optional[Dict[str, Any]]) -> bool:
    """Whether play has marked this place, by value against its master. As
    derive_location_exploration_state reads it, except that an artifact the
    master already holds is authored, not played."""
    state = played.get("explorationState")
    if state is not None:
        return isinstance(state, dict) and set(state) == {"status"} and state.get("status") == "visited"
    master = master or {}
    summary = played.get("adventureSummary")
    if isinstance(summary, str) and summary.strip() and summary != master.get("adventureSummary"):
        return True
    authored = {e.get("encounterId") for e in master.get("encounters") or [] if isinstance(e, dict)}
    return any(isinstance(e, dict) and "encounterId" in e and e.get("encounterId") not in authored
               for e in played.get("encounters") or [])


def lines(game, declared: Iterable[str], held: Optional[Dict[str, Any]] = None,
          notes: Optional[List[Tuple[str, str]]] = None) -> List[str]:
    """The character lines and the map block for world (a). `declared` is
    every place the world declares; `held` is the document's
    {"party": [ids], "characters": {id: place}} when there is a document."""
    declared = list(declared)
    known = set(declared)
    routes: Dict[Tuple[str, str], bool] = {}
    visited: List[str] = []
    for module in game.modules:
        for source, target in module_links(game, module):
            a, b = "loc:%s/%s" % (module, source), "loc:%s/%s" % (module, target)
            if a in known and b in known:
                routes[(a, b)] = True
            elif notes is not None:
                notes.append(("map", "%s -> %s: a place is not declared; no route" % (a, b)))
        masters = game.masters.get(module) or {}
        for loc_id, (_, loc) in sorted((game.played.get(module) or {}).items()):
            place = "loc:%s/%s" % (module, loc_id)
            if place in known and played_visit(loc, (masters.get(loc_id) or (None, None))[1]):
                visited.append(place)

    tracker = game.tracker or {}
    here = tracker_place(tracker)
    # The party's own place is visited only when the world declares it; a
    # stand-in place below is where the party is put, not a place it walked.
    seen_here = [here] if here in known else []
    if here not in known:
        if notes is not None and here:
            notes.append(("map", "the party's place %s is not declared; the party stands at a "
                                 "declared place of its module, not marked visited" % here))
        module = str(tracker.get("module") or "").replace(" ", "_")
        here = next((p for p in declared if p.startswith("loc:%s/" % module)), declared[0] if declared else None)
    if here is None:
        return []

    from utils.roster_conversion import ACTOR
    held = held or {}
    held_places = held.get("characters") or {}
    members = [(i, n) for i, n in party_members(tracker) if i != ACTOR]
    if notes is not None and len(members) < len(party_members(tracker)):
        notes.append(("map", "a party member named like the roster actor (%s) is left out" % ACTOR))
    member_ids = [i for i, _ in members]
    out = ["character %s named %s at %s { }" % (q(i), q(n), q(here)) for i, n in members]
    for ident in held.get("party") or []:
        if isinstance(ident, str) and ident not in member_ids and ident != ACTOR:
            # A member that left the tracker stays declared until its
            # `leave party` is applied (core/nql/travel.py).
            at = held_places.get(ident)
            out.append("character %s named %s at %s { }" % (q(ident), q(ident), q(at if at in known else here)))
            member_ids.append(ident)

    out.append("map {")
    paired = set()
    for a, b in sorted(routes):
        if (a, b) in paired:
            continue
        if (b, a) in routes:
            out.append(" route %s to %s ticks %d both;" % (q(a), q(b), TICKS))
            paired.add((b, a))
        else:
            out.append(" route %s to %s ticks %d;" % (q(a), q(b), TICKS))
        paired.add((a, b))
    for ident in member_ids:
        out.append(" party %s;" % q(ident))
    for place in dict.fromkeys(seen_here + visited):
        out.append(" visited %s;" % q(place))
    out.append("}")
    return out
