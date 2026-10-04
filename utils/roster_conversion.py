# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""One-time conversion of a game's location rosters into engine occupants.

The rules engine (bin/nql-apply) keeps every location's monster groups and
people as "occupants": where they are, how many are left and how each one
left (defeated, fled, surrendered, departed with a reason, joined, died).
Its record lives in live_state.json at the game root. A game that already
has history (fights on record, monsters removed from the played files,
people who moved or joined the party) needs that record built once from
what already happened. This module does that: it reads the authored masters,
the played area files, the encounter files, party_tracker.json and
journal.json, decides what became of every authored entry by the rules
below, has the engine apply those decisions and write the first live state,
and writes a report of every decision for review.

It reads the game and writes only into the output directory. Every name
match it makes is one-time and listed in the report; runtime code never
matches names.

Rules, per authored monster group: (1) beaten in a fight at its place: the
beaten members are resolved with their outcome, the rest stay present, or
depart when the played file no longer lists them; (2) still in the played
file with no fight: present, with the played count when it is lower;
(3) gone from the played file with no fight: departed with a default reason,
or joined when it shares a party member's name. Per authored person: beaten
in a fight: resolved; authored at the same place under a monster's name:
goes the way the monster went; listed: present; gone: joined when it shares
a party name, moved when exactly one other place lists it, otherwise present
again. Entries in play that nothing authored: party members are dropped, a
name authored elsewhere in the module stays that one occupant, anything else
is created.

Usage:

  python3 utils/roster_conversion.py <game root> <out dir>
      [--nql-apply <binary>] [--modules Keep_of_Doom,The_Thornwood_Watch]
      [--lower Shadows_of_Frostmere] [--overrides overrides.json]

Outputs: seed.nql (the world: every place and the authored seeds),
conversion.nql (the typed actions, one block per request), live_state.json
(written by the engine), report.md and report.json (every decision with its
rule, evidence and flags). The overrides file maps an occupant ID to
{"present": true} or {"reason": "<text>"} for a departure.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys
import unicodedata

DEFAULT_REASON = "left before the engine took over; not recorded"
MAX_OPS = 128
ACTOR = "char:roster-conversion"
STYLE_GUESS = "old-style file: the manner is not recorded, fled is a guess"
NOT_MODULES = ("conversation_history", "encounters", "campaign_archives", "campaign_summaries", "logs")


# Names --------------------------------------------------------------------

def slug(name):
    """The monster file slug combat_builder uses (normalize_character_name),
    and the last part of an occupant ID."""
    from updates.update_character_info import normalize_character_name
    return normalize_character_name(name or "") or "unnamed"


def key(name):
    """The matching key for one-time name matches: letters and spaces, a
    leading "the" and one trailing s dropped, so "Skeletons" matches
    "Skeleton" and "The Drowned King" matches "Drowned King"."""
    s = re.sub(r"[^a-z ]", "", (name or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    return s[:-1] if s.endswith("s") else s


def words(name):
    return set(re.findall(r"[a-z]+", (name or "").lower()))


def base_name(name):
    """An encounter copy "Giant Rat_2" is a "Giant Rat"."""
    return re.sub(r"_\d+$", "", name or "")


def q(text):
    """An NQL string: NQL strings are JSON strings."""
    return json.dumps(text, ensure_ascii=True)


# Reading ------------------------------------------------------------------

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def installed_modules(root):
    """Every module directory under modules/ that has an areas/ folder."""
    out = []
    base = os.path.join(root, "modules")
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name in NOT_MODULES or name.startswith("."):
            continue
        if os.path.isdir(os.path.join(base, name, "areas")):
            out.append(name)
    return out


def world_modules(root, notes=None):
    """The installed modules whose place ids are final, for the engine world
    (LIVE_STATE.md: seed a module only once its place ids are final): those
    the world registry has integrated, by the rule detect_new_modules uses
    (an entry that is not a bare stub), plus the module the party tracker
    names (spaces read as underscores), since play stands there. An
    unreadable registry gives every installed module, as before, with a
    note."""
    from core.generators.module_stitcher import ModuleStitcher

    installed = installed_modules(root)
    try:
        registry = load(os.path.join(root, "modules", "world_registry.json"))
        modules = registry.get("modules") if isinstance(registry, dict) else None
        if not isinstance(modules, dict):
            raise ValueError("no modules table")
    except (OSError, ValueError) as exc:
        if notes is not None:
            notes.append(("registry", "world_registry.json unreadable (%s); every installed "
                                      "module is declared" % exc))
        return installed
    try:
        tracker = load(os.path.join(root, "party_tracker.json"))
        current = str(tracker.get("module") or "").replace(" ", "_") if isinstance(tracker, dict) else ""
    except (OSError, ValueError):
        current = ""
    return [m for m in installed if m == current or (
        m in modules and not ModuleStitcher._is_registry_stub(registry, m))]


class Game:
    def __init__(self, root, modules, paths=None):
        self.root = root
        self.modules = modules
        # Each module's directory: modules/<M> under the root, unless given
        # (a module checked in its publication workspace before it is live).
        self.paths = {m: os.path.join(root, "modules", m) for m in modules}
        self.paths.update(paths or {})
        self.tracker = load(os.path.join(root, "party_tracker.json"))
        journal = os.path.join(root, "journal.json")
        self.journal = load(journal).get("entries", []) if os.path.exists(journal) else []
        # masters[M] and played[M] map a location ID to (area ID, location);
        # played_areas[M] keeps each played area file whole (the map's links
        # are read from them, utils/travel_map.py).
        self.masters, self.played, self.played_areas = {}, {}, {}
        for m in modules:
            self.masters[m], self.played[m], self.played_areas[m] = {}, {}, {}
            for path in sorted(glob.glob(os.path.join(self.paths[m], "areas", "*.json"))):
                name = os.path.basename(path)[:-5]
                master = name.endswith("_BU")
                area = name[:-3] if master else name
                doc = load(path)
                if not master:
                    self.played_areas[m][name] = doc
                for loc in doc.get("locations", []) or []:
                    (self.masters if master else self.played)[m][loc["locationId"]] = (area, loc)
        self.encounters = []
        for path in glob.glob(os.path.join(root, "modules", "encounters", "encounter_*.json")):
            match = re.match(r"encounter_(.+)-E(\d+)\.json$", os.path.basename(path))
            if match:
                self.encounters.append((match.group(1), int(match.group(2)), os.path.basename(path)[:-5], load(path)))
        self.encounters.sort(key=lambda e: (e[0], e[1]))

    def party(self):
        """Personal names of the party: every word of a member's name or ID,
        and the last word of a party NPC's name ("Ranger Thane": Thane)."""
        out = {}
        for member in self.tracker.get("partyMembers", []) or []:
            label = " ".join(w.capitalize() for w in re.split(r"[^A-Za-z]+", member) if w)
            for w in words(member):
                if len(w) >= 3:
                    out[w] = label
        for npc in self.tracker.get("partyNPCs", []) or []:
            ws = re.findall(r"[a-z]+", (npc.get("name") or "").lower())
            if ws:
                out[ws[-1]] = npc["name"]
        return out


def party_match(name, persons):
    for w in sorted(words(name)):
        if w in persons:
            return persons[w]
    return None


def authored_count(entry):
    """(min, max) from a master monster entry, or None when uncounted."""
    for field in ("quantity", "number", "count"):
        v = entry.get(field)
        if isinstance(v, dict) and isinstance(v.get("min"), int) and isinstance(v.get("max"), int):
            return (v["min"], v["max"])
        if isinstance(v, int) and not isinstance(v, bool):
            return (v, v)
    return None


def played_count(entry):
    """The number a played entry records, or None: dice text and ranges are
    no count."""
    for field in ("number", "count", "quantity"):
        v = entry.get(field)
        if isinstance(v, int) and not isinstance(v, bool):
            return v
        if isinstance(v, dict) and v.get("min") == v.get("max") and isinstance(v.get("min"), int):
            return v["min"]
    return None


# Seeds --------------------------------------------------------------------

ATTITUDES = ("friendly", "indifferent", "hostile")


def disposition(entry):
    """(attitude, problem) for an NPC entry: its model-typed disposition when
    that is exactly an engine attitude, else indifferent as before; problem
    names a disposition that is present but not one of the three words."""
    value = entry.get("disposition") if isinstance(entry, dict) else None
    if value in ATTITUDES:
        return value, None
    if value is None:
        return "indifferent", None
    return "indifferent", "disposition %r is not friendly, indifferent or hostile; indifferent" % (value,)


class Seed:
    def __init__(self, module, loc, name, kind, entry, ident):
        self.module, self.loc, self.name, self.kind, self.entry, self.id = module, loc, name, kind, entry, ident
        self.place = "loc:%s/%s" % (module, loc)
        self.range = authored_count(entry) if kind == "creatures" else None
        self.decision = None
        self.aliases = []
        self.attitude, self.attitude_problem = disposition(entry) if kind == "person" else (None, None)

    def declaration(self):
        if self.kind == "person":
            body = "person; attitude %s;" % self.attitude + "".join(" alias %s;" % q(a) for a in self.aliases)
        elif self.range is None:
            body = "creatures; attitude hostile; type %s;" % q(slug(self.name))
        elif self.range[0] == self.range[1]:
            body = "creatures %d; attitude hostile; type %s;" % (self.range[0], q(slug(self.name)))
        else:
            body = "creatures %d to %d; attitude hostile; type %s;" % (self.range[0], self.range[1], q(slug(self.name)))
        return "occupant %s named %s at %s { %s }" % (q(self.id), q(self.name), q(self.place), body)


DECLARATION = "module_declaration.json"


def usable_aliases(name, aliases):
    """The aliases the engine will take for an occupant named name, in order:
    trimmed, non-empty, no control characters, at most 4096 bytes, neither
    the name nor one already kept, at most 16. The engine refuses the whole
    world for any other alias, so the rest are dropped."""
    kept = []
    for a in aliases:
        a = a.strip() if isinstance(a, str) else ""
        if (a and a != name and a not in kept and len(a.encode("utf-8")) <= 4096
                and not any(unicodedata.category(c) == "Cc" for c in a)):
            kept.append(a)
    return kept[:16]


def declared_start(module_dir):
    """The module's declared entry: {"areaId", "locationId"} (bare ids) when
    module_declaration.json in module_dir is a version 1 declaration whose
    start was chosen as the entry (source "entry"), else None. A start the
    build picked as the first location is not an entry and is not used. The
    caller still resolves both ids against the module's files."""
    try:
        data = load(os.path.join(module_dir, DECLARATION))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format") != "neq-module-declaration" or data.get("version") != 1:
        return None
    start = data.get("start")
    if not isinstance(start, dict) or start.get("source") != "entry":
        return None
    area, loc = start.get("areaId"), start.get("locationId")
    if not (isinstance(area, str) and area and isinstance(loc, str) and loc):
        return None
    return {"areaId": area, "locationId": loc}


def declared_beings(game, module, notes):
    """What the module's declaration (written at publication) says about its
    people: ({(home, name): aliases}, {(place, name)} for the same being's
    other appearances). No file means none, and every entry derives as
    before; so does an unreadable file or another format. A being is used
    only when its home and each appearance list exactly one authored NPC of
    that exact name. Home and appearances are bare location ids ("G04"), so
    a re-prefix that rewrites the module's ids rewrites them too."""
    homes, elsewhere = {}, set()
    path = os.path.join(game.paths[module], DECLARATION)
    if not os.path.exists(path):
        return homes, elsewhere
    try:
        data = load(path)
    except (OSError, ValueError) as exc:
        notes.append(("declaration", "%s: %s unreadable (%s); derived as before" % (module, DECLARATION, exc)))
        return homes, elsewhere
    if not isinstance(data, dict) or data.get("format") != "neq-module-declaration" or data.get("version") != 1:
        notes.append(("declaration", "%s: %s is not a version 1 declaration; derived as before" % (module, DECLARATION)))
        return homes, elsewhere
    masters = game.masters[module]

    def authored_once(loc_id, name):
        if loc_id not in masters:
            return False
        npcs = masters[loc_id][1].get("npcs") or []
        return sum(1 for e in npcs if isinstance(e, dict) and (e.get("name") or "").strip() == name) == 1

    for being in data.get("beings") if isinstance(data.get("beings"), list) else []:
        being = being if isinstance(being, dict) else {}
        name, home = being.get("name"), being.get("home")
        appearances = being.get("appearances") if isinstance(being.get("appearances"), list) else []
        if not (isinstance(name, str) and home in appearances
                and all(isinstance(p, str) and authored_once(p, name) for p in appearances)):
            notes.append(("declaration", "%s: being %r does not match the authored NPCs; derived as before" % (module, name)))
            continue
        aliases = being.get("aliases") if isinstance(being.get("aliases"), list) else []
        homes[(home, name)] = usable_aliases(name, aliases)
        elsewhere.update((p, name) for p in appearances if p != home)
    return homes, elsewhere


def seeds(game, notes):
    """Every authored monster and NPC of the masters, in file order, with
    IDs occ:<Module>/<LocationId>/<slug>, -2, -3 for repeats at one place.
    A being the module declares as one figure across places is one person at
    its home, with its aliases; its other appearances are not seeded."""
    out = []
    for m in game.modules:
        homes, elsewhere = declared_beings(game, m, notes)
        for loc_id, (_, loc) in game.masters[m].items():
            used = collections.Counter()
            for field, kind in (("monsters", "creatures"), ("npcs", "person")):
                for entry in loc.get(field) or []:
                    name = entry.get("name") if isinstance(entry, dict) else None
                    if not name or not name.strip():
                        notes.append(("seed", "%s/%s: a %s entry without a name is skipped" % (m, loc_id, field)))
                        continue
                    if kind == "person" and (loc_id, name.strip()) in elsewhere:
                        continue
                    s = slug(name)
                    used[s] += 1
                    ident = "occ:%s/%s/%s" % (m, loc_id, s) + ("" if used[s] == 1 else "-%d" % used[s])
                    seed = Seed(m, loc_id, name.strip(), kind, entry, ident)
                    if kind == "person":
                        seed.aliases = homes.get((loc_id, name.strip()), [])
                        if seed.attitude_problem:
                            notes.append(("seed", "%s: %s" % (ident, seed.attitude_problem)))
                    if kind == "creatures" and seed.range is not None and not (1 <= seed.range[0] <= seed.range[1]):
                        notes.append(("seed", "%s: authored count %r is not a group size; declared uncounted" % (ident, seed.range)))
                        seed.range = None
                    out.append(seed)
    return out


# Fights -------------------------------------------------------------------

def beaten(creature, encounter):
    """How an enemy left a fight, or None while it stands. A guess is
    marked."""
    status = creature.get("status")
    hp = creature.get("currentHitPoints")
    hp = hp if isinstance(hp, int) else 0
    if status == "alive" and hp > 0:
        return None, False
    if status in ("dead", "unconscious") or hp <= 0:
        return "defeated", False
    if status == "defeated":
        resolution = creature.get("resolution")
        if resolution == "fled":
            return "fled", False
        if resolution == "yielded":
            return "surrendered", False
        state = encounter.get("combatState")
        if isinstance(state, dict):
            acts = ((state.get("narrationActivity") or {}).get(creature.get("combatantId")) or {}).get("actions") or []
            if "yield" in acts:
                return "surrendered", False
            if "flee" in acts:
                return "fled", False
            return "defeated", False
        return "fled", True
    return None, False


# Decisions ----------------------------------------------------------------

class Decision:
    def __init__(self, seed_id, name, place, rule, summary):
        self.id, self.name, self.place, self.rule, self.summary = seed_id, name, place, rule, summary
        self.actions = []
        self.evidence = []
        self.flags = []
        self.reason = None
        self.size = None    # the group's size once counted
        self.last = None    # (outcome, reason) when the last members left
        self.expect = None  # (present count or None, {outcome: count})

    def row(self):
        return {"id": self.id, "name": self.name, "place": self.place, "rule": self.rule, "decision": self.summary,
                "reason": self.reason, "actions": self.actions, "evidence": self.evidence, "flags": self.flags}


def resolve(ident, outcome, n=None, reason=None):
    s = "resolve occupant %s as %s" % (q(ident), outcome)
    if n is not None:
        s += " by %d" % n
    if reason:
        s += " because %s" % q(reason)
    return s + ";"


def mentions(game, module, loc_id, name):
    """Journal entries at the place and its played summary that name the
    entry: evidence for the owner, never a rule input."""
    loc = (game.played[module].get(loc_id) or game.masters[module].get(loc_id))[1]
    master = (game.masters[module].get(loc_id) or (None, {}))[1]
    place_names = {loc.get("name"), master.get("name")} - {None}
    texts = []
    for e in game.journal:
        if e.get("location") in place_names:
            texts.append(("journal %s %s" % (e.get("date", ""), e.get("time", "")), e.get("summary") or ""))
    summary = loc.get("adventureSummary")
    for text in summary if isinstance(summary, list) else [summary]:
        if text:
            texts.append(("place summary", text if isinstance(text, str) else json.dumps(text)))
    needles = [name.lower()]
    if key(name) and key(name) != name.lower():
        needles.append(key(name))
    out = []
    for where, text in texts:
        low = text.lower()
        for needle in needles:
            i = low.find(needle)
            if i >= 0:
                lo = max(0, i - 80)
                out.append("%s: ...%s..." % (where, " ".join(text[lo:i + len(needle) + 80].split())))
                break
    return out[:3]


def convert(game, lower=(), overrides=None):
    overrides = dict(overrides or {})
    notes = []
    seed_list = seeds(game, notes)
    persons = game.party()
    lower = set(lower)

    # Where each location ID lives, for encounter files that name no module.
    homes = collections.defaultdict(list)
    for m in game.modules:
        for loc_id in game.masters[m]:
            homes[loc_id].append(m)

    # Enemies of each fight, matched by name to a seed at the fight's place.
    by_place = collections.defaultdict(list)
    for s in seed_list:
        by_place[(s.module, s.loc)].append(s)
    fought = collections.defaultdict(list)  # seed id -> [(encounter, outcome or None, guess)]
    unapplied = []
    for loc_id, _, enc_id, data in game.encounters:
        mods = homes.get(loc_id, [])
        enemies = [c for c in data.get("creatures", []) or [] if c.get("type") == "enemy"]
        if len(mods) != 1:
            why = "place %s is %s" % (loc_id, "in no converted module" if not mods else "in several modules: " + ", ".join(mods))
            unapplied += [{"encounter": enc_id, "enemy": c.get("name"), "why": why} for c in enemies]
            continue
        for c in enemies:
            match = [s for s in by_place[(mods[0], loc_id)] if key(s.name) == key(base_name(c.get("name")))]
            if not match:
                unapplied.append({"encounter": enc_id, "enemy": c.get("name"), "why": "no authored entry of that name at %s/%s" % (mods[0], loc_id)})
                continue
            outcome, guess = beaten(c, data)
            fought[match[0].id].append((enc_id, outcome, guess))

    played = {}  # (module, loc) -> {field: [entries]}
    for m in game.modules:
        for loc_id, (_, loc) in game.played[m].items():
            played[(m, loc_id)] = {f: [e for e in loc.get(f) or [] if isinstance(e, dict) and (e.get("name") or "").strip()] for f in ("monsters", "npcs")}
    claimed = collections.defaultdict(set)  # (module, loc, field) -> indexes matched to a seed

    # Every seed takes its own entry at its own place: first in its own list,
    # then in the other one (a monster the played file lists among the NPCs).
    # NPCs look elsewhere only after that, so a move never takes another
    # seed's entry.
    own, crossed = {s.id: None for s in seed_list}, set()
    for cross in (False, True):
        for s in seed_list:
            if own[s.id] is not None:
                continue
            field = ("monsters" if s.kind == "creatures" else "npcs")
            if cross:
                field = "npcs" if field == "monsters" else "monsters"
            for i, e in enumerate(played.get((s.module, s.loc), {}).get(field, [])):
                if i not in claimed[(s.module, s.loc, field)] and key(e["name"]) == key(s.name):
                    claimed[(s.module, s.loc, field)].add(i)
                    own[s.id] = e
                    if cross:
                        crossed.add(s.id)
                    break

    decisions, made = [], {}
    for s in seed_list:
        twin = next((made[t.id] for t in by_place[(s.module, s.loc)] if t.kind == "creatures" and t.id in made and key(t.name) == key(s.name)), None)
        if s.kind == "creatures":
            d = monster_decision(game, s, fought.get(s.id, []), own[s.id], persons)
        elif twin is not None:
            d = twin_decision(s, twin)
        else:
            d = npc_decision(game, s, fought.get(s.id, []), own[s.id], persons, played, claimed)
        made[s.id] = d
        if s.id in crossed:
            d.flags.append("listed among the %s in play" % ("NPCs" if s.kind == "creatures" else "monsters"))
        twins = [t.id for t in by_place[(s.module, s.loc)] if t is not s and key(t.name) == key(s.name)]
        if twins:
            d.flags.append("the same name is authored again here as " + ", ".join(twins))
        if s.id in overrides:
            apply_override(d, overrides.pop(s.id), notes)
        if s.module in lower:
            d.flags.append("lower confidence: module from the old module builder")
        decisions.append(d)
    for ident in sorted(overrides):
        notes.append(("override", "%s names no seed; not applied" % ident))

    # Played entries no seed took.
    seed_ids = {s.id for s in seed_list}
    authored = {}
    for s in seed_list:
        authored.setdefault((s.module, key(s.name)), s)
    for (m, loc_id), fields in sorted(played.items()):
        place = "loc:%s/%s" % (m, loc_id)
        for field in ("npcs", "monsters"):
            for i, e in enumerate(fields[field]):
                if i in claimed[(m, loc_id, field)]:
                    continue
                name = e["name"].strip()
                who = party_match(name, persons)
                if who:
                    d = Decision(None, name, place, "4", "party member listed at a place: dropped")
                    d.evidence.append("party member: %s" % who)
                elif (m, key(name)) in authored:
                    other = authored[(m, key(name))]
                    d = Decision(other.id, name, place, "7", "listed here too; authored at %s: kept as that one occupant; for a decision" % other.place.split("/", 1)[1])
                    d.flags.append("decision")
                else:
                    ident, n = "occ:%s/%s/%s" % (m, loc_id, slug(name)), 2
                    while ident in seed_ids:
                        ident, n = "occ:%s/%s/%s-%d" % (m, loc_id, slug(name), n), n + 1
                    seed_ids.add(ident)
                    if field == "npcs":
                        d = Decision(ident, name, place, "7", "in play but not authored: created")
                        attitude, problem = disposition(e)
                        if problem:
                            d.evidence.append(problem)
                        d.actions.append("create occupant %s named %s at %s { person; attitude %s; };" % (q(ident), q(name), q(place), attitude))
                        d.size = 1
                    else:
                        c = played_count(e)
                        d = Decision(ident, name, place, "7m", "monster in play but not authored: created")
                        body = "creatures %d;" % c if c else "creatures;"
                        d.actions.append("create occupant %s named %s at %s { %s attitude hostile; type %s; };" % (q(ident), q(name), q(place), body, q(slug(name))))
                        d.size = c or None
                    d.expect = (d.size, {})
                    d.flags.append("listed")
                if m in lower:
                    d.flags.append("lower confidence: module from the old module builder")
                decisions.append(d)

    # The party's place.
    wc = game.tracker.get("worldConditions", {}) or {}
    module = (game.tracker.get("module") or "").replace(" ", "_")
    here = wc.get("currentLocationId")
    if here and module in game.masters and here not in game.masters[module]:
        notes.append(("party", "the party tracker says %s in %s, but %s is not a place of %s; it is a place of %s" % (here, module, here, module, ", ".join(homes.get(here, [])) or "no converted module")))
    return seed_list, decisions, unapplied, notes


def apply_override(d, o, notes):
    """The owner's line: present after all, or another reason for a
    departure with the default one."""
    if o.get("present"):
        d.actions = [a for a in d.actions if a.startswith("count ")]
        d.expect, d.reason = (d.size, {}), None
        d.summary += "; overridden: present"
    elif o.get("reason"):
        r = o["reason"]
        if d.reason != DEFAULT_REASON:
            notes.append(("override", "%s has no default reason to replace; not applied" % d.id))
            return
        if not r.strip() or len(r.encode("utf-8")) > 200 or any(ord(c) < 32 for c in r):
            notes.append(("override", "%s: a reason is text of at most 200 bytes; not applied" % d.id))
            return
        d.actions = [a.replace("because %s" % q(DEFAULT_REASON), "because %s" % q(r)) for a in d.actions]
        d.reason = r
    d.flags.append("override")


def monster_decision(game, s, fights, played, persons):
    lo, hi = s.range or (None, None)
    fixed = lo is not None and lo == hi

    def count_to(d, n):
        d.actions.append("count occupant %s as %d;" % (q(s.id), n))

    c = played_count(played) if played is not None else None
    if fights:
        outcomes = collections.Counter(o for _, o, _ in fights if o)
        last = fights[-1][0]
        standing = sum(1 for e, o, _ in fights if o is None and e == last)
        total = sum(outcomes.values())
        d = Decision(s.id, s.name, s.place, "1", "beaten in a fight at its place")
        d.evidence.append("fights: " + ", ".join(sorted({e for e, _, _ in fights})))
        if any(g for _, _, g in fights):
            d.flags.append(STYLE_GUESS)
        want = max(total + standing, 1)
        if fixed:
            size = hi
        else:
            size = want if lo is None else min(max(want, lo), hi)
            count_to(d, size)
        if want > size:
            d.flags.append("%d in the fights, more than the %d here: the same ones fought again" % (want, size))
        elif want < size and not fixed:
            d.flags.append("%d in the fights, fewer than the authored %d to %d; counted %d" % (want, lo, hi, size))
        left, tally = size, {}
        for outcome in ("defeated", "fled", "surrendered"):
            n = min(outcomes.get(outcome, 0), left)
            if n:
                d.actions.append(resolve(s.id, outcome, None if n == left else n))
                tally[outcome] = n
                left -= n
                if not left:
                    d.last = (outcome, None)
        d.summary += ": %s" % (", ".join("%d %s" % (n, o) for o, n in tally.items()) or "none beaten")
        if played is None and left:
            # Gone from the played file: those the fights left standing went
            # the way of rule 3.
            who = party_match(s.name, persons)
            outcome, d.reason = ("joined", "now in the party as %s" % who) if who else ("departed", DEFAULT_REASON)
            d.actions.append(resolve(s.id, outcome, None, d.reason))
            d.summary += "; the %d left standing are gone from the played file: %s" % (left, outcome)
            tally[outcome], left = tally.get(outcome, 0) + left, 0
            d.last = (outcome, d.reason)
        else:
            d.summary += "; %d still here" % left
        if played is not None and not left:
            d.flags.append("still in the played file; the fight wins")
        d.size, d.expect = size, (left, tally)
        return d
    if played is not None and c != 0:
        d = Decision(s.id, s.name, s.place, "2", "in the played file, no fight: present")
        if fixed:
            size = hi
        elif c:
            size = c if lo is None else min(max(c, lo), hi)
            count_to(d, size)
        else:
            size = None
        present, tally = size, {}
        if size is not None and c is not None and c < size:
            d.actions.append(resolve(s.id, "departed", size - c, DEFAULT_REASON))
            d.reason, present, tally = DEFAULT_REASON, c, {"departed": size - c}
            d.summary += "; the played file has %d of %d" % (c, size)
        elif size is not None and c is not None and c > size:
            d.flags.append("the played file has %d, more than the authored %s; kept %d" % (c, "%d" % hi if fixed else "%d to %d" % (lo, hi), size))
        d.size, d.expect = size, (present, tally)
        return d
    who = party_match(s.name, persons)
    if who:
        d = Decision(s.id, s.name, s.place, "3j", "gone from the played file; shares a party member's name: joined")
        d.reason, outcome = "now in the party as %s" % who, "joined"
    else:
        d = Decision(s.id, s.name, s.place, "3", "gone from the played file, no fight: departed")
        d.reason, outcome = DEFAULT_REASON, "departed"
        d.evidence.extend(mentions(game, s.module, s.loc, s.name))
    size = hi if fixed else (lo if lo is not None else 1)
    if not fixed:
        count_to(d, size)
    d.actions.append(resolve(s.id, outcome, None, d.reason))
    d.size, d.expect, d.last = size, (0, {outcome: size}), (outcome, d.reason)
    return d


def twin_decision(s, twin):
    """An NPC authored at the same place under the same name as a monster is
    that monster described twice: it goes the way the monster went."""
    if twin.last is None:
        d = Decision(s.id, s.name, s.place, "1t", "the NPC side of %s, which is still here: present" % twin.id)
        d.expect = (1, {})
    else:
        outcome, reason = twin.last
        d = Decision(s.id, s.name, s.place, "1t", "the NPC side of %s: %s with it" % (twin.id, outcome))
        d.reason = reason
        d.actions.append(resolve(s.id, outcome, None, reason))
        d.expect = (0, {outcome: 1})
    d.size = 1
    return d


def npc_decision(game, s, fights, played, persons, played_lists, claimed):
    d = None
    who = party_match(s.name, persons)
    beaten_here = [(e, o) for e, o, _ in fights if o]
    if beaten_here:
        enc, outcome = beaten_here[0]
        d = Decision(s.id, s.name, s.place, "1n", "authored person beaten in a fight at the place: %s" % outcome)
        d.evidence.append("fight: %s" % enc)
        d.actions.append(resolve(s.id, outcome))
        d.expect = (0, {outcome: 1})
    elif played is not None:
        d = Decision(s.id, s.name, s.place, "5", "in the played file: present")
        if who:
            d.flags.append("shares a name with party member %s: resolve as joined if the same person" % who)
        d.expect = (1, {})
    elif who:
        d = Decision(s.id, s.name, s.place, "6j", "gone from the played file; shares a party member's name: joined")
        d.reason = "now in the party as %s" % who
        d.actions.append(resolve(s.id, "joined", None, d.reason))
        d.expect = (0, {"joined": 1})
    else:
        # Moved by T014 within its area: the one other place that lists it.
        elsewhere = []
        for (m, loc_id), fields in sorted(played_lists.items()):
            if m == s.module and loc_id != s.loc:
                for i, e in enumerate(fields["npcs"]):
                    if i not in claimed[(m, loc_id, "npcs")] and key(e["name"]) == key(s.name):
                        elsewhere.append((loc_id, i))
        if len(elsewhere) == 1:
            loc_id, i = elsewhere[0]
            claimed[(s.module, loc_id, "npcs")].add(i)
            to = "loc:%s/%s" % (s.module, loc_id)
            d = Decision(s.id, s.name, s.place, "6m", "listed at %s instead: moved there" % to.split("/", 1)[1])
            d.actions.append("move occupant %s to %s;" % (q(s.id), q(to)))
            d.flags.append("listed")
        else:
            d = Decision(s.id, s.name, s.place, "6", "gone from the played file: present again")
            d.flags.append("listed")
            if elsewhere:
                d.flags.append("listed at several other places: " + ", ".join(l for l, _ in elsewhere))
            d.evidence.extend(mentions(game, s.module, s.loc, s.name))
        d.expect = (1, {})
    d.size = 1
    return d


# Output -------------------------------------------------------------------

def world_source(game, seed_list, held=None, notes=None):
    """Every place of the modules, masters first, then any place only the
    played files have; and the map with the party (utils/travel_map.py).
    `held` is the document's party and character places, when there is a
    document."""
    places = []
    for m in game.modules:
        for loc_id, (_, loc) in game.masters[m].items():
            places.append(("loc:%s/%s" % (m, loc_id), loc.get("name") or loc_id))
        for loc_id, (_, loc) in game.played[m].items():
            if loc_id not in game.masters[m]:
                places.append(("loc:%s/%s" % (m, loc_id), loc.get("name") or loc_id))
    wc = game.tracker.get("worldConditions", {}) or {}
    here = None
    for m in game.modules:
        if wc.get("currentLocationId") in game.masters[m]:
            here = "loc:%s/%s" % (m, wc["currentLocationId"])
            break
    lines = ["rules { transfer unequips; wear any; }", 'clock "second" at 0;']
    lines += ["location %s named %s;" % (q(p), q(n)) for p, n in places]
    lines.append("character %s named %s at %s { }" % (q(ACTOR), q("Roster conversion"), q(here or places[0][0])))
    lines += [s.declaration() for s in seed_list]
    # QS: every quest of every module, from the authored plot (the engine's
    # quest record; utils/quest_record.py).
    from utils import quest_record
    lines += quest_record.declaration_lines(game.root, game.modules)
    # C10a: the map, the party at the tracker's place and the visited seed.
    from utils import travel_map
    lines += travel_map.lines(game, [p for p, _ in places], held, notes)
    return "\n".join(lines) + "\n", [p for p, _ in places]


def call(binary, doc):
    from core.nql import apply
    try:
        return apply.call(doc, binary=binary, timeout=None)
    except apply.EngineUnavailable as exc:
        raise SystemExit("nql-apply: %s" % exc)


def run_engine(binary, world, places, actions):
    """The engine writes the first live state: new_live_state, then the
    actions in requests of at most 128 operations."""
    actor = {"kind": "character", "id": ACTOR}
    live, requests = None, []
    chunks = [actions[i:i + MAX_OPS] for i in range(0, len(actions), MAX_OPS)] or [[]]
    for i, chunk in enumerate(chunks, 1):
        doc = {"world": world}
        if live is None:
            doc["new_live_state"] = True
        else:
            doc["live_state"] = live
        if chunk:
            doc.update({"actions": "\n".join(chunk), "actor": actor, "request": "roster-conversion:%d" % i})
            requests.append("\n".join(chunk))
        r = call(binary, doc)
        if not r.get("ok"):
            raise SystemExit("request %d refused: %s %s" % (i, r.get("error"), json.dumps(r.get("fault") or r.get("diagnostics"))[:800]))
        live = r["live_state"]
    view = call(binary, {"world": world, "live_state": live, "locations": places})
    if not view.get("ok") or view.get("live_state") != live:
        raise SystemExit("final view refused: %s" % view.get("error"))
    return live, requests


def verify(decisions, live):
    """Every expectation the decisions state holds in the engine's document."""
    by_id = {o["id"]: o for o in live["occupants"]}
    problems = []
    for d in decisions:
        if d.id is None or d.expect is None:
            continue
        o = by_id.get(d.id)
        if o is None:
            problems.append("%s missing" % d.id)
            continue
        present, tally = d.expect
        got = collections.Counter()
        for t in o.get("tally") or []:
            got[t["outcome"]] += t["count"]
        if present is not None and o.get("count") != present:
            problems.append("%s: present %r, expected %r" % (d.id, o.get("count"), present))
        if dict(got) != {k: v for k, v in tally.items() if v}:
            problems.append("%s: tally %r, expected %r" % (d.id, dict(got), tally))
    return problems


RULE_NAMES = collections.OrderedDict([
    ("1", "monster beaten in a fight at its place"), ("2", "monster in the played file: present"),
    ("3", "monster gone, no fight: departed"), ("3j", "monster gone, shares a party name: joined"),
    ("1n", "NPC beaten in a fight"), ("1t", "NPC authored as a monster too: goes with it"),
    ("4", "party member listed at a place: dropped"),
    ("5", "NPC in the played file: present"), ("6", "NPC gone: present again"),
    ("6j", "NPC shares a party name: joined"), ("6m", "NPC listed elsewhere: moved"),
    ("7", "NPC in play, not authored: created, or one occupant"), ("7m", "monster in play, not authored: created")])


def report(game, lower, seed_list, decisions, unapplied, notes, live, problems):
    counts = collections.Counter(d.rule for d in decisions)
    lines = ["# Roster conversion report", "",
             "Game: `%s`. Modules: %s. Lower confidence: %s." % (os.path.basename(os.path.abspath(game.root)), ", ".join(game.modules), ", ".join(lower) or "none"),
             "", "Every line is one decision the conversion makes; the engine applied all of them",
             "and wrote the first live state. To change a line, add its occupant ID to the",
             "overrides file: `{\"present\": true}` keeps it present, `{\"reason\": \"...\"}`",
             "replaces a departure's reason. Then run the conversion again.", "",
             "## Summary", "", "| Rule | Lines |", "| --- | --- |"]
    for r, name in RULE_NAMES.items():
        if counts.get(r):
            lines.append("| %s: %s | %d |" % (r, name, counts[r]))
    lines += ["", "- Seeds: %d (%d monster groups, %d NPCs)." % (len(seed_list), sum(1 for s in seed_list if s.kind == "creatures"), sum(1 for s in seed_list if s.kind == "person")),
              "- Engine requests: %d; live state revision %d; %d occupants." % (len(live["requests"]), live["revision"], len(live["occupants"])),
              "- Fight enemies not applied: %d." % len(unapplied),
              "- Expectations checked against the engine's document: %s." % ("all hold" if not problems else "%d problems" % len(problems))]
    for p in problems:
        lines.append("  - PROBLEM: %s" % p)
    if notes:
        lines += ["", "## Checks", ""]
        lines += ["- %s: %s" % n for n in notes]
    lines += ["", "## Decisions", ""]
    order = list(RULE_NAMES)
    for m in game.modules:
        rows = [d for d in decisions if d.place.startswith("loc:%s/" % m)]
        if not rows:
            continue
        lines += ["### %s" % m, "", "| Place | Occupant | Name | Rule | Decision | Reason | Notes |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for d in sorted(rows, key=lambda d: (d.place, order.index(d.rule), d.id or "", d.name)):
            note = "; ".join(d.flags + d.evidence)
            lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (d.place.split("/", 1)[1], "`%s`" % d.id if d.id else "", cell(d.name), d.rule, cell(d.summary), cell(d.reason or ""), cell(note)))
        lines.append("")
    if unapplied:
        lines += ["## Fight enemies not applied", "", "| Encounter | Enemy | Why |", "| --- | --- | --- |"]
        for u in unapplied:
            lines.append("| %s | %s | %s |" % (u["encounter"], cell(u["enemy"]), cell(u["why"])))
        lines.append("")
    text = "\n".join(lines) + "\n"
    return text.encode("ascii", "backslashreplace").decode("ascii")


def cell(text):
    return (text or "").replace("|", "/").replace("\n", " ")


def run(root, out, binary=None, modules=None, lower=(), overrides=None):
    """Convert one game and write the outputs. Returns (problems, live_state,
    decisions): problems is empty when every decision holds in the engine's
    document. Callers that need the document in memory read the returned
    value; the file under out is the same document."""
    if binary is None:
        from core.nql import apply
        binary = apply.binary_path()
    # None means every installed module; an empty list is a world with none.
    modules = installed_modules(root) if modules is None else list(modules)
    lower = [m for m in lower if m in modules]
    game = Game(root, modules)
    seed_list, decisions, unapplied, notes = convert(game, lower, overrides or {})
    world, places = world_source(game, seed_list)
    actions = [a for d in decisions for a in d.actions]
    live, requests = run_engine(binary, world, places, actions)
    problems = verify(decisions, live)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "seed.nql"), "w", encoding="ascii", errors="backslashreplace") as f:
        f.write(world)
    with open(os.path.join(out, "conversion.nql"), "w", encoding="ascii", errors="backslashreplace") as f:
        for i, r in enumerate(requests, 1):
            f.write("// request roster-conversion:%d\n%s\n" % (i, r))
    with open(os.path.join(out, "live_state.json"), "w", encoding="utf-8") as f:
        json.dump(live, f, indent=1)
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"decisions": [d.row() for d in decisions], "unapplied": unapplied, "notes": notes, "problems": problems}, f, indent=1)
    with open(os.path.join(out, "report.md"), "w", encoding="ascii") as f:
        f.write(report(game, lower, seed_list, decisions, unapplied, notes, live, problems))
    return problems, live, decisions


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("root")
    ap.add_argument("out")
    ap.add_argument("--nql-apply", default=None, help="the engine binary (default: bin/nql-apply or NQL_APPLY_BINARY)")
    ap.add_argument("--modules", default="", help="comma-separated module names (default: every installed module)")
    ap.add_argument("--lower", default="", help="comma-separated modules flagged lower confidence")
    ap.add_argument("--overrides")
    args = ap.parse_args(argv)
    overrides = load(args.overrides) if args.overrides else {}
    problems, _, _ = run(args.root, args.out, args.nql_apply,
                         [m for m in args.modules.split(",") if m] or None,
                         [m for m in args.lower.split(",") if m], overrides)
    for p in problems:
        print("PROBLEM: %s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
