# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Location rosters through the rules engine: the live_state document.

The engine (bin/nql-apply) keeps every location's monster groups and people
as occupants: where they are, how many are left and how each one left
(defeated, fled, surrendered, departed with a reason, joined, died). The
record is ``live_state.json`` at the game root, written only by the engine
and passed back whole on every call (NQL docs/LIVE_STATE.md). The world
source for each call is rebuilt from the installed modules' authored masters
(``areas/*_BU.json``) by utils/roster_conversion.py, so a place the document
does not hold yet (a newly installed module) takes its seeds, and a place it
holds keeps what play made of it.

Three entry points for the host:

- ``resolve_combat(encounter_id)`` after a fight: every enemy of the
  encounter file that is down, fled or yielded is resolved on its occupant,
  by the typed fields the combat engine wrote (``status``, ``resolution``),
  never by prose. One deterministic request per completed fight, so a retry
  after a crash is answered as already applied.
- ``location_record(location_id)`` for the DM context: what became of each
  group at the place (the engine's tally) in place of the per-fight
  encounter entries, and the module's groups at large (fled or departed)
  only when there are any.
- ``request(actions, request_id)`` for typed occupant actions, with the
  fail-forward ladder of LIVE_STATE.md: a refusal naming a place the world
  dropped declares it again; a damaged document retries with its ``.bak``;
  a document refused twice is set aside and re-created from the seeds, and
  the loss is logged. The game never stops over the document.

The document is created on the first call: through the conversion rules
when the game has fights on record (the report lands in
``modules/logs/roster_conversion/``), else bare from the seeds.
"""
import glob
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from utils.enhanced_logger import debug, info, warning
from utils.file_operations import safe_read_json, safe_write_json
from core.nql import apply

DOCUMENT = "live_state.json"
CONVERSION_DIR = os.path.join("modules", "logs", "roster_conversion")
TIMEOUT = 60

# A creature's typed end in the fight -> the occupant outcome.
RESOLUTION_OUTCOME = {"fled": "fled", "yielded": "surrendered"}


def document_path(root: str = ".") -> str:
    return os.path.join(root, DOCUMENT)


def _modules(root: str) -> List[str]:
    from utils import roster_conversion
    return roster_conversion.installed_modules(root)


def _world(root: str):
    """The world source and the places it declares, from the masters."""
    from utils import roster_conversion
    modules = _modules(root)
    game = roster_conversion.Game(root, modules)
    for module in modules:
        if not game.masters[module]:
            warning(
                "OCCUPANTS: module %s has no authored masters (areas/*_BU.json); "
                "its places come from the played files with no seeds" % module,
                category="location_transitions",
            )
    notes: List[Tuple[str, str]] = []
    seed_list = roster_conversion.seeds(game, notes)
    for kind, text in notes:
        debug("OCCUPANTS: seed note (%s): %s" % (kind, text), category="location_transitions")
    world, places = roster_conversion.world_source(game, seed_list)
    return world, places, game


def _load(root: str) -> Optional[Dict[str, Any]]:
    data = safe_read_json(document_path(root))
    return data if isinstance(data, dict) and data.get("format") == "nql-live-state" else None


def _write(root: str, live: Dict[str, Any]) -> None:
    if not safe_write_json(document_path(root), live):
        warning("OCCUPANTS: live_state.json could not be written; the engine's "
                "next answer will carry the same document again", category="location_transitions")


def _create(root: str, world: str, places: List[str]) -> Optional[Dict[str, Any]]:
    """The first document: conversion when fights are on record, else seeds."""
    encounters = glob.glob(os.path.join(root, "modules", "encounters", "encounter_*.json"))
    if encounters:
        from utils import roster_conversion
        out = os.path.join(root, CONVERSION_DIR)
        try:
            problems, live, _ = roster_conversion.run(root, out)
            info("OCCUPANTS: live_state.json created by conversion of %d encounter files; "
                 "report at %s (%d expectation problems)" % (len(encounters), out, len(problems)),
                 category="location_transitions")
            return live
        except SystemExit as exc:
            warning("OCCUPANTS: conversion refused (%s); the document starts from the seeds "
                    "and the fights on record are not reflected" % exc, category="location_transitions")
        except Exception as exc:  # fail forward: a bad file must not stop play
            warning("OCCUPANTS: conversion failed (%s); the document starts from the seeds"
                    % exc, category="location_transitions")
    response = apply.call({"world": world, "new_live_state": True}, timeout=TIMEOUT)
    if not response.get("ok"):
        warning("OCCUPANTS: the engine refused the world source: %s" % response.get("error"),
                category="location_transitions")
        return None
    info("OCCUPANTS: live_state.json created from the seeds of %d places" % len(places),
         category="location_transitions")
    return response.get("live_state")


def _actor_of(world: str) -> Dict[str, str]:
    from utils import roster_conversion
    return {"kind": "character", "id": roster_conversion.ACTOR}


def _call(world: str, live: Dict[str, Any], actions: Optional[str], request_id: Optional[str],
          view: List[str]) -> Dict[str, Any]:
    body: Dict[str, Any] = {"world": world, "live_state": live}
    if actions:
        body.update({"actions": actions, "actor": _actor_of(world), "request": request_id})
    if view:
        body["locations"] = list(view)
    return apply.call(body, timeout=TIMEOUT)


def _set_aside(root: str) -> None:
    path = document_path(root)
    aside = "%s.refused-%d" % (path, int(time.time()))
    try:
        os.replace(path, aside)
        warning("OCCUPANTS: the document was refused twice and set aside as %s; a new one "
                "starts from the seeds. Lost: every roster change since the game began "
                "that the conversion rules cannot recover from the files" % aside,
                category="location_transitions")
    except OSError as exc:
        warning("OCCUPANTS: could not set the refused document aside (%s)" % exc,
                category="location_transitions")


def request(actions: Optional[str] = None, request_id: Optional[str] = None, *,
            view: Tuple[str, ...] = (), root: str = ".") -> Optional[Dict[str, Any]]:
    """One engine call on the document. Returns the response (ok or a refusal
    of the actions, which the caller reconciles), or None when the engine is
    unavailable or the document could not be made. Writes the next document
    when it changed."""
    try:
        world, places, _ = _world(root)
        live = _load(root)
        if live is None:
            live = _create(root, world, places)
            if live is None:
                return None
            _write(root, live)
        tried_bak = False
        recreated = False
        redeclared: set = set()
        on_disk = live
        while True:
            response = _call(world, live, actions, request_id, list(view))
            if response.get("ok"):
                # Written when the engine changed it, or when the file holds
                # a refused document and this one (the .bak) is good.
                if response.get("live_state") != on_disk:
                    _write(root, response["live_state"])
                return response
            fault = response.get("fault") or {}
            if response.get("phase") != "live_state":
                return response
            subject = fault.get("subject")
            if fault.get("field") == "place" and subject and subject not in redeclared:
                # The source dropped a place the document holds (a module
                # removed or renamed): declare it again, bare, and keep the
                # document and its record.
                redeclared.add(subject)
                warning("OCCUPANTS: the world no longer declares %s; declared again"
                        % subject, category="location_transitions")
                world += 'location "%s" named "%s";\n' % (subject, subject)
                continue
            bak = safe_read_json(document_path(root) + ".bak")
            if not tried_bak and isinstance(bak, dict) and bak != live:
                tried_bak = True
                warning("OCCUPANTS: the document was refused (%s); retrying with the "
                        "previous one" % response.get("error"), category="location_transitions")
                live = bak
                continue
            if recreated:
                warning("OCCUPANTS: the re-created document was refused too (%s)"
                        % response.get("error"), category="location_transitions")
                return None
            recreated = True
            _set_aside(root)
            live = _create(root, world, places)
            if live is None:
                return None
            _write(root, live)
            on_disk = live
    except apply.EngineUnavailable as exc:
        warning("OCCUPANTS: engine unavailable (%s); the roster record is not updated this turn"
                % exc, category="location_transitions")
        return None


def view(places: List[str], root: str = ".") -> List[Dict[str, Any]]:
    """The locations view for these places (each: location, present, resolved)."""
    response = request(view=tuple(places), root=root)
    if not response or not response.get("ok"):
        return []
    return response.get("locations") or []


def place_id(module: str, location_id: str) -> str:
    return "loc:%s/%s" % ((module or "").replace(" ", "_"), location_id)


# Combat end ---------------------------------------------------------------

def creature_outcome(creature: Dict[str, Any]) -> Optional[str]:
    """How an enemy left the fight, from the typed fields the combat engine
    wrote, or None while it stands."""
    status = str(creature.get("status") or "").lower()
    hp = creature.get("currentHitPoints")
    hp = hp if isinstance(hp, int) else 0
    if status in ("dead", "unconscious") or (status and hp <= 0 and status != "alive"):
        return "defeated"
    if status == "defeated":
        return RESOLUTION_OUTCOME.get(str(creature.get("resolution") or "").lower(), "defeated")
    if status == "alive" and hp <= 0:
        return "defeated"
    return None


def _present_groups(live: Dict[str, Any], place: str) -> List[Dict[str, Any]]:
    out = []
    for occupant in live.get("occupants") or []:
        if occupant.get("location") != place or occupant.get("kind") != "creatures":
            continue
        if occupant.get("count") == 0:
            continue
        out.append(occupant)
    return out


def _type_slug(creature: Dict[str, Any]) -> str:
    slug = creature.get("monsterType")
    if isinstance(slug, str) and slug.strip():
        return slug.strip().lower()
    return ""


def combat_actions(live: Dict[str, Any], place: str, creatures: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    """The typed actions that record this fight's enemies on their occupants,
    and the enemies no occupant matched. An enemy names its occupant by
    ``occupantId`` or by its typed slug equal to a present group's type at
    the place (value equality, never a name match)."""
    groups = _present_groups(live, place)
    by_id = {g["id"]: g for g in groups}
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for g in groups:
        by_type.setdefault(str(g.get("type") or "").lower(), []).append(g)
    recorded = {str(o.get("type") or "").lower() for o in live.get("occupants") or []
                if o.get("location") == place and o.get("count") == 0}
    tallies: Dict[str, Dict[str, int]] = {}
    unmatched: List[str] = []
    for creature in creatures:
        if creature.get("type") != "enemy":
            continue
        outcome = creature_outcome(creature)
        if outcome is None:
            continue
        occupant = by_id.get(creature.get("occupantId"))
        if occupant is None:
            candidates = by_type.get(_type_slug(creature)) or []
            # The first group of that type that still has room for one more.
            occupant = next((g for g in candidates if _room(g, tallies.get(g["id"], {}))), None)
        if occupant is None:
            if _type_slug(creature) in recorded:
                # Its group is already fully resolved here (the conversion
                # recorded this fight, or a retry after the record was written).
                continue
            unmatched.append(str(creature.get("name")))
            continue
        tally = tallies.setdefault(occupant["id"], {})
        tally[outcome] = tally.get(outcome, 0) + 1
    lines: List[str] = []
    for oid, tally in tallies.items():
        occupant = by_id[oid]
        total = sum(tally.values())
        if "count" not in occupant:
            # An uncounted group is counted first, within its range, by what
            # the fight showed; the engine refuses a resolve on an uncounted group.
            rng = occupant.get("range") or {}
            size = total
            if isinstance(rng.get("min"), int) and isinstance(rng.get("max"), int):
                size = min(max(total, rng["min"]), rng["max"])
            lines.append('count occupant "%s" as %d;' % (oid, size))
            present = size
        else:
            present = int(occupant.get("count") or 0)
        left = present
        for outcome in ("defeated", "surrendered", "fled"):
            n = min(tally.get(outcome, 0), left)
            if n <= 0:
                continue
            lines.append('resolve occupant "%s" as %s%s;' % (oid, outcome, "" if n == left else " by %d" % n))
            left -= n
    return "\n".join(lines), unmatched


def _room(occupant: Dict[str, Any], tally: Dict[str, int]) -> bool:
    used = sum(tally.values())
    if "count" in occupant:
        return used < int(occupant.get("count") or 0)
    rng = occupant.get("range") or {}
    return used < int(rng.get("max") or 1000000000)


def resolve_combat(encounter_id: str, *, root: str = ".") -> Optional[Dict[str, Any]]:
    """Record a completed fight on the occupants of its place. Reads the
    encounter file's typed creature fields; never stops the game."""
    try:
        encounter = safe_read_json(os.path.join(root, "modules", "encounters", "encounter_%s.json" % encounter_id))
        if not isinstance(encounter, dict):
            debug("OCCUPANTS: no encounter file for %s; nothing to record" % encounter_id,
                  category="location_transitions")
            return None
        tracker = safe_read_json(os.path.join(root, "party_tracker.json")) or {}
        world_conditions = tracker.get("worldConditions") or {}
        module = tracker.get("module") or ""
        location_id = str(encounter.get("encounterId") or encounter_id).rsplit("-E", 1)[0]
        if not location_id:
            location_id = world_conditions.get("currentLocationId") or ""
        place = place_id(module, location_id)
        completion = ((encounter.get("combatState") or {}).get("completion") or {})
        record_id = completion.get("recordId") or encounter.get("combatCompletionId") or "0"
        request_id = "combat-end:%s:%s" % (encounter_id, record_id)
        # The document first, so the actions see the groups present now.
        current = request(view=(place,), root=root)
        if not current or not current.get("ok"):
            return current
        live = current.get("live_state") or _load(root) or {}
        actions, unmatched = combat_actions(live, place, encounter.get("creatures") or [])
        if unmatched:
            info("OCCUPANTS: %s: no occupant at %s for enemies %s (free-name fight; recorded in "
                 "the encounter summary only)" % (encounter_id, place, ", ".join(unmatched)),
                 category="location_transitions")
        if not actions:
            return current
        response = request(actions, request_id, view=(place,), root=root)
        if response is None:
            return None
        if not response.get("ok"):
            warning("OCCUPANTS: %s: the engine refused the combat record (%s); the fight stays "
                    "in the encounter summary only" % (encounter_id, response.get("error")),
                    category="location_transitions")
        elif response.get("historical"):
            debug("OCCUPANTS: %s already recorded" % request_id, category="location_transitions")
        else:
            info("OCCUPANTS: %s recorded: %s" % (request_id, actions.replace("\n", " ")),
                 category="location_transitions")
        return response
    except Exception as exc:  # fail forward
        warning("OCCUPANTS: combat record for %s skipped (%s)" % (encounter_id, exc),
                category="location_transitions")
        return None


# DM context ---------------------------------------------------------------

def _tally_text(occupant: Dict[str, Any]) -> str:
    parts = []
    for entry in occupant.get("tally") or []:
        text = "%d %s" % (entry.get("count", 0), entry.get("outcome"))
        if entry.get("reason"):
            text += " (%s)" % entry["reason"]
        parts.append(text)
    return ", ".join(parts)


def location_record(location_id: str, module: str, *, root: str = ".") -> Optional[Dict[str, Any]]:
    """What the engine records for this place, for the DM context: one line
    per group with a tally (resolved, or partly), and the module's groups at
    large (fled or departed elsewhere) when there are any. None when the
    engine or the document is unavailable."""
    place = place_id(module, location_id)
    response = request(view=(place,), root=root)
    if not response or not response.get("ok"):
        return None
    views = response.get("locations") or []
    if not views:
        return None
    here = views[0]
    record: List[str] = []
    for occupant in list(here.get("resolved") or []) + list(here.get("present") or []):
        if occupant.get("tally"):
            left = occupant.get("count")
            text = "%s: %s" % (occupant.get("name"), _tally_text(occupant))
            if isinstance(left, int) and left > 0:
                text += "; %d still here" % left
            record.append(text)
    out: Dict[str, Any] = {"rosterRecord": record}
    at_large: List[str] = []
    prefix = "loc:%s/" % (module or "").replace(" ", "_")
    from utils.roster_conversion import DEFAULT_REASON
    for occupant in (response.get("live_state") or {}).get("occupants") or []:
        if occupant.get("location") == place or not str(occupant.get("location", "")).startswith(prefix):
            continue
        # At large: fled, or departed for a stated reason. A conversion
        # departure with the default reason is an unknown, not a threat.
        gone = [e for e in occupant.get("tally") or []
                if e.get("outcome") == "fled"
                or (e.get("outcome") == "departed" and e.get("reason") != DEFAULT_REASON)]
        if gone:
            at_large.append("%s (%s) from %s: %s" % (
                occupant.get("name"), occupant.get("id"),
                str(occupant.get("location")).split("/", 1)[1],
                ", ".join("%d %s%s" % (e.get("count", 0), e.get("outcome"),
                                       " (%s)" % e["reason"] if e.get("reason") else "") for e in gone)))
    if at_large:
        out["atLarge"] = at_large
    return out
