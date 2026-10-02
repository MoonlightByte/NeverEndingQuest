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


# Fight declaration --------------------------------------------------------

def _unique_id(place: str, slug_text: str, taken: set) -> str:
    base = "occ:%s/%s" % (place.split(":", 1)[1], slug_text)
    ident, n = base, 2
    while ident in taken:
        ident, n = "%s-%d" % (base, n), n + 1
    return ident


def declare_encounter(encounter_id: str, *, root: str = ".") -> Optional[Dict[str, Any]]:
    """Give every enemy of a freshly built encounter its occupant before the
    fight: the ID the DM declared (when the document holds it at the place),
    else the present group of its type at the place, else a new occupant
    created for the free name in one request. Writes the stamped IDs into
    the encounter file. Never stops the fight: an unknown ID is dropped and
    settled like a free name; an engine refusal leaves the enemy to the
    combat-end type match."""
    try:
        path = os.path.join(root, "modules", "encounters", "encounter_%s.json" % encounter_id)
        encounter = safe_read_json(path)
        if not isinstance(encounter, dict):
            return None
        tracker = safe_read_json(os.path.join(root, "party_tracker.json")) or {}
        module = tracker.get("module") or ""
        location_id = str(encounter.get("encounterId") or encounter_id).rsplit("-E", 1)[0]
        place = place_id(module, location_id)
        current = request(view=(place,), root=root)
        if not current or not current.get("ok"):
            return current
        live = current.get("live_state") or _load(root) or {}
        at_place = [o for o in live.get("occupants") or [] if o.get("location") == place]
        here_ids = {o["id"] for o in at_place}
        taken = {o["id"] for o in live.get("occupants") or []}
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for o in at_place:
            if o.get("kind") == "creatures" and o.get("count") != 0:
                by_type.setdefault(str(o.get("type") or "").lower(), []).append(o)
        changed = False
        to_create: Dict[str, Dict[str, Any]] = {}  # slug -> {"id", "name", "creatures"}
        for creature in encounter.get("creatures") or []:
            if creature.get("type") != "enemy":
                continue
            declared = creature.get("occupantId")
            if declared in here_ids:
                continue
            if declared:
                info("OCCUPANTS: %s: declared occupant %s is not at %s; settled by type"
                     % (encounter_id, declared, place), category="location_transitions")
                creature.pop("occupantId", None)
                changed = True
            slug_text = _type_slug(creature)
            present = by_type.get(slug_text)
            if present:
                creature["occupantId"] = present[0]["id"]
                changed = True
                continue
            if not slug_text:
                continue
            entry = to_create.get(slug_text)
            if entry is None:
                from utils.roster_conversion import base_name
                ident = _unique_id(place, slug_text, taken)
                taken.add(ident)
                entry = to_create[slug_text] = {"id": ident, "name": base_name(str(creature.get("name") or slug_text)), "creatures": []}
            entry["creatures"].append(creature)
        if to_create:
            from utils.roster_conversion import q
            lines = []
            for slug_text, entry in to_create.items():
                lines.append('create occupant %s named %s at %s { creatures %d; attitude hostile; type %s; };'
                             % (q(entry["id"]), q(entry["name"]), q(place), len(entry["creatures"]), q(slug_text)))
            response = request("\n".join(lines), "encounter:%s" % encounter_id, view=(place,), root=root)
            if response and response.get("ok"):
                for entry in to_create.values():
                    for creature in entry["creatures"]:
                        creature["occupantId"] = entry["id"]
                changed = True
                info("OCCUPANTS: %s: created %s at %s for the free-name fight"
                     % (encounter_id, ", ".join(e["id"] for e in to_create.values()), place),
                     category="location_transitions")
            else:
                warning("OCCUPANTS: %s: the engine refused the free-name occupants (%s); the fight runs "
                        "and its end is matched by type" % (encounter_id, (response or {}).get("error")),
                        category="location_transitions")
        if changed and not safe_write_json(path, encounter):
            warning("OCCUPANTS: %s: encounter file could not be rewritten with occupant IDs"
                    % encounter_id, category="location_transitions")
        return current
    except Exception as exc:  # fail forward
        warning("OCCUPANTS: declaration for %s skipped (%s)" % (encounter_id, exc),
                category="location_transitions")
        return None


# DM context ---------------------------------------------------------------

def present_roster(place_view: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The present occupants of a place for the DM context: the IDs a fight
    or a story outcome is declared with."""
    out = []
    for o in place_view.get("present") or []:
        entry: Dict[str, Any] = {"id": o.get("id"), "name": o.get("name"), "kind": o.get("kind"),
                                 "attitude": o.get("attitude")}
        if "count" in o:
            entry["count"] = o["count"]
        elif o.get("range"):
            entry["count"] = "%d to %d" % (o["range"].get("min", 0), o["range"].get("max", 0))
        out.append(entry)
    return out


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
    present = present_roster(here)
    describe(present, module, location_id, root=root)
    out: Dict[str, Any] = {"rosterRecord": record, "occupants": present}
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


# DM story outcomes --------------------------------------------------------
#
# The DM declares what the story made of an occupant with a typed action by
# its ID (resolveOccupant, setOccupantAttitude, moveOccupant, returnOccupant);
# T067 owns the interpretation and T065 validates it. The host turns the
# action into one engine line and relays a refusal as a correction naming the
# present IDs, never as a stop. A party join or leave (updatePartyNPCs) keeps
# the person's occupant in step.

DM_ACTIONS = ("resolveOccupant", "setOccupantAttitude", "moveOccupant", "returnOccupant")
OUTCOMES = ("defeated", "fled", "surrendered", "departed", "joined", "died")
ATTITUDES = ("friendly", "indifferent", "hostile")
REASON_BYTES = 200


def _reason(text: Any) -> str:
    text = " ".join(str(text or "").split())
    while len(text.encode("utf-8")) > REASON_BYTES:
        text = text[:-1]
    return text.strip()


def _members(value: Any) -> Tuple[Optional[int], str]:
    """An optional member count: (n, "") or (None, problem)."""
    if value in (None, ""):
        return None, ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None, "count must be a whole number of members"
    if n < 1:
        return None, "count must be at least 1"
    return n, ""


def dm_action_line(action_type: str, parameters: Any, module: str) -> Tuple[str, str]:
    """The engine line for one typed DM action: (line, "") or ("", problem)."""
    from utils.roster_conversion import q
    p = parameters if isinstance(parameters, dict) else {}
    oid = str(p.get("occupantId") or "").strip()
    if not oid.startswith("occ:"):
        return "", "occupantId must be an id from the location data's occupants list"
    if action_type == "resolveOccupant":
        outcome = str(p.get("outcome") or "").strip().lower()
        if outcome not in OUTCOMES:
            return "", "outcome must be one of %s" % ", ".join(OUTCOMES)
        n, problem = _members(p.get("count"))
        if problem:
            return "", problem
        reason = _reason(p.get("reason"))
        if outcome == "departed" and not reason:
            return "", "a departed outcome needs a reason (why they left)"
        line = "resolve occupant %s as %s" % (q(oid), outcome)
        if n is not None:
            line += " by %d" % n
        if reason:
            line += " because %s" % q(reason)
        return line + ";", ""
    if action_type == "setOccupantAttitude":
        attitude = str(p.get("attitude") or "").strip().lower()
        if attitude not in ATTITUDES:
            return "", "attitude must be one of %s" % ", ".join(ATTITUDES)
        return "set occupant %s attitude %s;" % (q(oid), attitude), ""
    if action_type == "moveOccupant":
        location_id = str(p.get("locationId") or "").strip()
        if not location_id:
            return "", "locationId must be a location id of this module"
        return "move occupant %s to %s;" % (q(oid), q(place_id(module, location_id))), ""
    if action_type == "returnOccupant":
        outcome = str(p.get("outcome") or "").strip().lower()
        if outcome not in OUTCOMES:
            return "", "outcome must be one of %s" % ", ".join(OUTCOMES)
        n, problem = _members(p.get("count"))
        if problem:
            return "", problem
        reason = _reason(p.get("reason"))
        line = "return occupant %s from %s" % (q(oid), outcome)
        if reason:
            line += " %s" % q(reason)
        if n is not None:
            line += " by %d" % n
        return line + ";", ""
    return "", "unknown occupant action %s" % action_type


def _present_lines(here: Optional[Dict[str, Any]]) -> str:
    entries = present_roster(here or {})
    if not entries:
        return "none"
    return "; ".join("%s (%s, %s, %s)" % (e["id"], e["name"], e.get("count", "?"), e.get("attitude"))
                     for e in entries)


def correction(action_type: str, problem: str, here: Optional[Dict[str, Any]]) -> str:
    """The message that sends a refused occupant action back to the DM."""
    return (
        "Occupant Error: %s was refused: %s. Nothing changed in the roster record. "
        "Present occupants at this location: %s. Later actions from this response have not "
        "executed. Do not repeat earlier completed actions; issue the action again with an id "
        "and values from this list, or narrate the outcome without it."
        % (action_type, problem, _present_lines(here))
    )


def _here(root: str, place: str) -> Optional[Dict[str, Any]]:
    views = view([place], root=root)
    return views[0] if views else None


def apply_dm_action(action_type: str, parameters: Any, request_id: str, module: str,
                    location_id: str, *, root: str = ".") -> Dict[str, Any]:
    """Send one typed DM action to the engine. Returns {"ok": bool,
    "correction": text or None}: a refusal comes back as a correction for
    the DM; an unavailable engine is logged and the turn goes on."""
    place = place_id(module, location_id)
    try:
        line, problem = dm_action_line(action_type, parameters, module)
        if problem:
            return {"ok": False, "correction": correction(action_type, problem, _here(root, place))}
        if action_type == "moveOccupant":
            current = request(view=(place,), root=root)
            if not current or not current.get("ok"):
                return {"ok": False, "correction": None}
            target = place_id(module, str((parameters or {}).get("locationId") or "").strip())
            if target not in ((current.get("live_state") or {}).get("places") or []):
                here = (current.get("locations") or [None])[0]
                return {"ok": False, "correction": correction(
                    action_type, "locationId %s is not a location of this module"
                    % (parameters or {}).get("locationId"), here)}
        response = request(line, request_id, view=(place,), root=root)
        if response is None:
            return {"ok": False, "correction": None}
        if response.get("ok"):
            if response.get("historical"):
                debug("OCCUPANTS: %s already applied" % request_id, category="location_transitions")
            else:
                info("OCCUPANTS: %s applied: %s" % (request_id, line), category="location_transitions")
            return {"ok": True, "correction": None}
        fault = response.get("fault") or {}
        if fault.get("code") == "E_NO_CHANGE":
            info("OCCUPANTS: %s changes nothing (%s); taken as applied" % (request_id, line),
                 category="location_transitions")
            return {"ok": True, "correction": None}
        problem = str(fault.get("message") or response.get("error") or "the engine refused it")
        warning("OCCUPANTS: %s refused: %s (%s)" % (request_id, problem, line),
                category="location_transitions")
        return {"ok": False, "correction": correction(action_type, problem, _here(root, place))}
    except Exception as exc:  # fail forward
        warning("OCCUPANTS: %s skipped (%s)" % (action_type, exc), category="location_transitions")
        return {"ok": False, "correction": None}


def _person_matches(occupant: Dict[str, Any], want: str) -> bool:
    from utils.roster_conversion import slug
    if occupant.get("kind") != "person":
        return False
    names = [occupant.get("name")] + list(occupant.get("aliases") or [])
    return any(slug(n) == want for n in names if n)


def settle_person(live: Dict[str, Any], module: str, place: str, npc_name: str) -> Optional[Dict[str, Any]]:
    """The present person occupant a name settles on: by slug equality with
    its name or an alias, at this place first, else the module's only one."""
    from utils.roster_conversion import slug
    want = slug(npc_name)
    prefix = "loc:%s/" % (module or "").replace(" ", "_")
    present = [o for o in live.get("occupants") or []
               if o.get("count") != 0 and str(o.get("location") or "").startswith(prefix)
               and _person_matches(o, want)]
    here = [o for o in present if o.get("location") == place]
    if here:
        return here[0]
    if len(present) == 1:
        return present[0]
    return None


def party_change(operation: str, npc_name: str, module: str, location_id: str, request_id: str,
                 *, reason: Any = None, root: str = ".") -> Optional[Dict[str, Any]]:
    """Keep a companion's occupant in step with updatePartyNPCs: an add
    resolves the person present here as joined; a remove brings the person
    back at this place (return from joined, moved here when the record is
    elsewhere) or creates one. Never stops the roster change."""
    try:
        from utils.roster_conversion import q, slug
        place = place_id(module, location_id)
        current = request(view=(place,), root=root)
        if not current or not current.get("ok"):
            return None
        live = current.get("live_state") or _load(root) or {}
        why = _reason(reason)
        if operation == "add":
            person = settle_person(live, module, place, npc_name)
            if person is None:
                debug("OCCUPANTS: no present person occupant for companion %s; nothing to resolve"
                      % npc_name, category="location_transitions")
                return None
            line = "resolve occupant %s as joined%s;" % (q(person["id"]), " because %s" % q(why) if why else "")
        elif operation == "remove":
            want = slug(npc_name)
            prefix = "loc:%s/" % (module or "").replace(" ", "_")
            back = None
            for o in live.get("occupants") or []:
                if not str(o.get("location") or "").startswith(prefix) or not _person_matches(o, want):
                    continue
                entry = next((e for e in o.get("tally") or [] if e.get("outcome") == "joined"), None)
                if entry is not None:
                    back = (o, entry)
                    break
            if back is not None:
                o, entry = back
                line = "return occupant %s from joined%s;" % (q(o["id"]), " %s" % q(entry["reason"]) if entry.get("reason") else "")
                if o.get("location") != place:
                    line += "\nmove occupant %s to %s;" % (q(o["id"]), q(place))
            else:
                taken = {o["id"] for o in live.get("occupants") or []}
                ident = _unique_id(place, want, taken)
                line = "create occupant %s named %s at %s { person; attitude friendly; };" % (q(ident), q(npc_name), q(place))
        else:
            return None
        response = request(line, request_id, view=(place,), root=root)
        if response is None:
            return None
        if response.get("ok"):
            info("OCCUPANTS: %s (%s %s): %s" % (request_id, operation, npc_name, line.replace("\n", " ")),
                 category="location_transitions")
        else:
            warning("OCCUPANTS: %s (%s %s) refused: %s" % (request_id, operation, npc_name, response.get("error")),
                    category="location_transitions")
        return response
    except Exception as exc:  # fail forward
        warning("OCCUPANTS: party change for %s skipped (%s)" % (npc_name, exc), category="location_transitions")
        return None


def legacy_move(parameters: Any, module: str, location_id: str, *, root: str = ".") -> Dict[str, Any]:
    """The retired moveBackgroundNPC action: forwarded to moveOccupant when
    it names an occupant (by id, or a present person by name) and a
    destination, else answered with a correction that lists the ids."""
    p = parameters if isinstance(parameters, dict) else {}
    place = place_id(module, location_id)
    try:
        current = request(view=(place,), root=root)
        here = (current.get("locations") or [None])[0] if current and current.get("ok") else None
        live = (current or {}).get("live_state") or {}
        oid = str(p.get("occupantId") or "").strip()
        if not oid and p.get("npcName"):
            person = settle_person(live, module, place, str(p.get("npcName")))
            oid = person["id"] if person else ""
        destination = str(p.get("locationId") or p.get("newLocation") or "").strip()
        if oid and destination:
            return {"forward": {"occupantId": oid, "locationId": destination}, "correction": None}
        problem = ("it is retired; say what became of the occupant with resolveOccupant "
                   "(occupantId, outcome, reason), setOccupantAttitude (occupantId, attitude) or "
                   "moveOccupant (occupantId, locationId)")
        if p.get("npcName") and not oid:
            problem = "no present occupant here is named %s; %s" % (p.get("npcName"), problem)
        return {"forward": None, "correction": correction("moveBackgroundNPC", problem, here)}
    except Exception as exc:  # fail forward
        warning("OCCUPANTS: moveBackgroundNPC forwarding skipped (%s)" % exc, category="location_transitions")
        return {"forward": None, "correction": None}


# Readers on the view ------------------------------------------------------
#
# From P4-f on, nothing reads a location's authored `monsters`/`npcs` lists
# for state: who is at a place comes from the engine's locations view. The
# authored entry is joined to a present occupant by its id (the slug the
# seeding gave it) only for its description text.

_ROSTER_CACHE: Dict[Tuple[str, str], Tuple[Any, Dict[str, Dict[str, Any]]]] = {}
_AUTHORED_CACHE: Dict[str, Tuple[Tuple[str, ...], Dict[str, Dict[str, Dict[str, Any]]]]] = {}


def _stamp(root: str):
    try:
        st = os.stat(document_path(root))
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _authored(root: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """{module: {location_id: authored location}} from the masters (the
    played file when a master is missing), read once per set of modules."""
    from utils import roster_conversion
    modules = tuple(roster_conversion.installed_modules(root))
    hit = _AUTHORED_CACHE.get(os.path.abspath(root))
    if hit and hit[0] == modules:
        return hit[1]
    game = roster_conversion.Game(root, list(modules))
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for module in modules:
        out[module] = {}
        for loc_id, (_, loc) in game.played[module].items():
            out[module][loc_id] = loc
        for loc_id, (_, loc) in game.masters[module].items():
            out[module][loc_id] = loc
    _AUTHORED_CACHE[os.path.abspath(root)] = (modules, out)
    return out


def _authored_entry(location: Optional[Dict[str, Any]], occupant_id: str) -> Optional[Dict[str, Any]]:
    """The authored monsters/npcs entry an occupant id names: the slug at the
    end of the id (with -N for the Nth repeat at the place), by value."""
    if not isinstance(location, dict) or not occupant_id:
        return None
    from utils.roster_conversion import slug
    import re
    tail = occupant_id.rsplit("/", 1)[-1]
    m = re.match(r"^(.*?)(?:-(\d+))?$", tail)
    want, nth = m.group(1), int(m.group(2) or 1)
    seen = 0
    for field in ("monsters", "npcs"):
        for entry in location.get(field) or []:
            if isinstance(entry, dict) and slug(entry.get("name") or "") == want:
                seen += 1
                if seen == nth:
                    return entry
    return None


def describe(present: List[Dict[str, Any]], module: str, location_id: str, *, root: str = ".") -> None:
    """Attach the authored description (and disposition text) to each present
    occupant entry in place, when its authored entry exists."""
    try:
        location = _authored(root).get((module or "").replace(" ", "_"), {}).get(location_id)
    except Exception:
        location = None
    for entry in present:
        authored = _authored_entry(location, str(entry.get("id") or ""))
        if not authored:
            continue
        for key in ("description", "disposition", "role"):
            if isinstance(authored.get(key), str) and authored[key].strip():
                entry[key] = authored[key]
        if isinstance(authored.get("attitude"), str) and authored["attitude"].strip() \
                and authored["attitude"].strip().lower() not in ATTITUDES:
            entry["attitudeText"] = authored["attitude"]


def record_lines(place_view: Dict[str, Any]) -> List[str]:
    """One line per group with a tally at the place (resolved or partly)."""
    record: List[str] = []
    for occupant in list(place_view.get("resolved") or []) + list(place_view.get("present") or []):
        if occupant.get("tally"):
            left = occupant.get("count")
            text = "%s: %s" % (occupant.get("name"), _tally_text(occupant))
            if isinstance(left, int) and left > 0:
                text += "; %d still here" % left
            record.append(text)
    return record


def place_summary(place_view: Dict[str, Any], module: str, location_id: str, *, root: str = ".") -> Dict[str, Any]:
    present = present_roster(place_view)
    describe(present, module, location_id, root=root)
    return {
        "present": present,
        "people": [e["name"] for e in present if e.get("kind") == "person"],
        "hostile": any(e.get("kind") == "creatures" and e.get("attitude") == "hostile" for e in present),
        "hostiles": [e["name"] for e in present if e.get("kind") == "creatures" and e.get("attitude") == "hostile"],
        "rosterRecord": record_lines(place_view),
    }


def module_roster(module: str, *, root: str = ".") -> Optional[Dict[str, Dict[str, Any]]]:
    """Every place of the module from one engine call: {location_id:
    {present, people, hostile, hostiles, rosterRecord}}. Cached until the
    document changes. None when the engine or the document is unavailable
    (callers fall back to nothing present, never to the authored lists)."""
    module = (module or "").replace(" ", "_")
    key = (os.path.abspath(root), module)
    stamp = _stamp(root)
    hit = _ROSTER_CACHE.get(key)
    if hit and stamp is not None and hit[0] == stamp:
        return hit[1]
    try:
        _, places, _ = _world(root)
        prefix = "loc:%s/" % module
        mine = [p[0] if isinstance(p, tuple) else p for p in places]
        mine = [p for p in mine if str(p).startswith(prefix)]
        if not mine:
            return None
        response = request(view=tuple(mine), root=root)
        if not response or not response.get("ok"):
            return None
        out: Dict[str, Dict[str, Any]] = {}
        for v in response.get("locations") or []:
            place = str((v.get("location") or {}).get("id") or "")
            if "/" not in place:
                continue
            loc_id = place.split("/", 1)[1]
            out[loc_id] = place_summary(v, module, loc_id, root=root)
        _ROSTER_CACHE[key] = (_stamp(root), out)
        return out
    except Exception as exc:  # fail forward
        warning("OCCUPANTS: module roster for %s unavailable (%s)" % (module, exc),
                category="location_transitions")
        return None


def place_roster(module: str, location_id: str, *, root: str = ".") -> Optional[Dict[str, Any]]:
    roster = module_roster(module, root=root)
    if roster is None:
        return None
    return roster.get(location_id) or {"present": [], "people": [], "hostile": False, "hostiles": [], "rosterRecord": []}
