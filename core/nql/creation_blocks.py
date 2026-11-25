# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The character under construction, block by block (D-CREATE-FLEX-1..3, #2090).

A reply names only what it adds or changes. Each block (an identity key, the picks of one choice id, the ability
scores, a package, a slot, what is worn, one creative field) is checked alone, with the same rules the finalize
uses, and kept; the rest stays as it was. Three layers:

- ``held``: what the last published turn left;
- ``standing``: held plus what this turn's replies have populated so far;
- the reply itself.

Absent keeps the standing value. null or "" goes back to the held value. A value replaces; a list replaces its
list and [] clears it. Nothing here reads prose: only typed keys and ids, compared whole.

Slot picks and worn items named before their package WAIT: they are stored with the others and become filled when
the package they belong to is known. Nothing marks a waiting id; ``checked`` derives it on every read, and only
what ``checked`` returns is filled.
"""
import copy
from typing import Any, Dict, List, NamedTuple, Optional

from core.nql import creation_build, creation_scope, item_catalog, startup_rows
from core.nql.creation_scope import _Data, _class_points
from core.nql.startup_rows import _package_items

IDENTITY = ("class_key", "species_key", "background_key")
PACKAGES = ("background_package", "class_package")
NEXT_LIMIT = 3


def empty() -> Dict[str, Any]:
    return {"intent": dict({key: None for key in IDENTITY}, choices={}, ability_scores=None,
                           considering={"class_keys": [], "species_keys": [], "background_keys": []}),
            "starting_equipment": {"background_package": None, "class_package": None, "slot_picks": [], "equipped": []},
            "creative": {}}


class Merge(NamedTuple):
    standing: Dict[str, Any]          # the blocks after this reply
    problems: List[Dict[str, Any]]    # what this reply sent that the engine refuses, by block id
    unwritten: List[str]              # creative fields this reply sent that were not written
    aside: List[str]                  # blocks sent before what they belong to, and not kept
    dropped: Dict[str, List[Any]]     # what stood and no longer belongs, by block id
    leftovers: Dict[str, List[Any]]   # what this reply sent for a choice the build has left, not kept


class _Facts:
    """The data one merge reads, once."""

    def __init__(self) -> None:
        self.d = _Data()
        records = startup_rows.package_records()
        self.classes = records.classes if records else {}
        self.backgrounds = records.backgrounds if records else {}
        # Each slot: who can own it and in which package, with its item entry.
        self.slots: Dict[str, List[tuple]] = {}
        for kind, owners in (("class", self.classes),
                             ("background", {k: b["equipment_options"] for k, b in self.backgrounds.items()})):
            for owner, options in owners.items():
                for package, option in options.items():
                    for slot, item in startup_rows.package_slots(_package_items(option, kind)).items():
                        self.slots.setdefault(slot, []).append((kind, owner, package, item))
        self.ok = self.d.ok and records is not None

    def options(self, kind: str, intent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if kind == "class":
            return self.classes.get(intent.get("class_key"))
        return (self.backgrounds.get(intent.get("background_key")) or {}).get("equipment_options")

    def class_package_id(self, cls: Any) -> Optional[str]:
        """The choice id that is the class's starting package (its typed shape, not its name)."""
        if not self.d.ok or cls not in self.d.classes():
            return None
        return next((cid for cid, point in _class_points(cls, self.d) if isinstance(point.get("option_items"), dict)), None)


def _package_option(facts: _Facts, kind: str, blocks: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    options = facts.options(kind, blocks["intent"]) or {}
    return options.get(blocks["starting_equipment"].get(kind + "_package"))


def _chosen_items(facts: _Facts, blocks: Dict[str, Any]) -> List[tuple]:
    out = []
    for kind in ("class", "background"):
        option = _package_option(facts, kind, blocks)
        if option is not None:
            out += _package_items(option, kind)
    return out


def _bound_pick(facts: _Facts, blocks: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The slot a background's tool choice binds ("same as above"), filled with the player's own tool pick once that
    is known and the chosen package has the slot. Never the other way: a slot's text says nothing about the tool."""
    background = facts.backgrounds.get(blocks["intent"].get("background_key")) or {}
    slot = (background.get("tool_choice") or {}).get("binds_slot")
    if not slot or slot not in startup_rows.package_slots(_chosen_items(facts, blocks)):
        return None
    picks = blocks["intent"]["choices"].get(creation_scope.background_tool_id(background))
    return {"slot": slot, "display_name": picks[0]} if picks else None


def _slot_state(facts: _Facts, blocks: Dict[str, Any], pick: Dict[str, Any]) -> tuple:
    """("filled" | "waiting" | "gone" | "refused", why). gone: its owner is known and is another."""
    slot = pick.get("slot")
    owners = facts.slots.get(slot) if isinstance(slot, str) else None
    if set(pick) not in ({"slot", "catalog_id"}, {"slot", "display_name"}) or not all(isinstance(v, str) for v in pick.values()):
        return "refused", "a slot pick is an object with slot and either catalog_id or display_name"
    if not owners:
        return "refused", "slot_picks names slot %r, which no package has" % slot
    chosen = startup_rows.package_slots(_chosen_items(facts, blocks))
    if slot in chosen:
        problem = startup_rows.slot_pick_problem(slot, chosen[slot], pick)
        return ("refused", problem) if problem else ("filled", None)
    possible, other_owner = [], False
    for kind, owner, package, item in owners:
        named = blocks["intent"].get(kind + "_key")
        if named is not None and named != owner:
            other_owner = True
        elif blocks["starting_equipment"].get(kind + "_package") is None:
            possible.append(item)
    if possible:
        problems = [startup_rows.slot_pick_problem(slot, item, pick) for item in possible]
        return ("refused", problems[0]) if all(problems) else ("waiting", None)
    if other_owner:
        return "gone", None
    return "refused", "slot_picks names slot %r, which the chosen packages do not have" % slot


def _worn_state(facts: _Facts, blocks: Dict[str, Any], item_id: Any, filled: List[Dict[str, Any]]) -> tuple:
    if not isinstance(item_id, str) or item_catalog.entry(item_id) is None:
        return "refused", "equipped lists %r, which the item catalog does not have" % (item_id,)
    if any(_package_option(facts, kind, blocks) is None for kind in ("class", "background")):
        return "waiting", None
    items = _chosen_items(facts, blocks)
    ids = [i["catalog_id"] for _, i in items if isinstance(i.get("catalog_id"), str)
           and not isinstance(i.get("choose_one"), list)]
    ids += [p["catalog_id"] for p in filled if "catalog_id" in p]
    if not startup_rows.outside_items([item_id], ids):
        return "filled", None
    done = {p["slot"] for p in filled}
    for slot, item in startup_rows.package_slots(items).items():
        if slot not in done and item_id in (item.get("choose_one") or []):
            return "waiting", None  # its slot is not picked yet
    return "refused", "equipped lists %r, which the chosen packages do not give" % (item_id,)


def _gear(facts: _Facts, blocks: Dict[str, Any]) -> Dict[str, Any]:
    """The gear blocks sorted by state: filled picks and worn ids, the waiting ones, and the rest."""
    equipment = blocks["starting_equipment"]
    out: Dict[str, Any] = {"slots": [], "worn": [], "waiting_slots": [], "waiting_worn": [], "gone": [], "refused": []}
    bound = _bound_pick(facts, blocks)
    seen = {bound["slot"]} if bound else set()
    out["slots"] += [bound] if bound else []
    for pick in equipment.get("slot_picks") or []:
        if bound and pick.get("slot") == bound["slot"]:
            continue
        state, why = _slot_state(facts, blocks, pick)
        if isinstance(pick.get("slot"), str) and pick["slot"] in seen:
            state, why = "refused", "slot_picks names slot %r twice; give one pick per slot" % pick.get("slot")
        seen.add(pick.get("slot") if isinstance(pick.get("slot"), str) else None)
        if state in ("filled", "waiting"):
            out["slots" if state == "filled" else "waiting_slots"].append(pick)
        else:
            out[state].append(("slot", pick, why))
    for item_id in equipment.get("equipped") or []:
        state, why = _worn_state(facts, blocks, item_id, out["slots"])
        if state in ("filled", "waiting"):
            out["worn" if state == "filled" else "waiting_worn"].append(item_id)
        else:
            out[state].append(("worn", item_id, why))
    return out


def checked(blocks: Dict[str, Any], facts: Optional[_Facts] = None) -> Dict[str, Any]:
    """The same blocks with only what is filled: the waiting slot picks and worn items left out. Everything
    that shows, counts, compares or grants the gear reads this."""
    facts = facts or _Facts()
    gear = _gear(facts, blocks)
    out = copy.deepcopy(blocks)
    out["starting_equipment"].update(slot_picks=copy.deepcopy(gear["slots"]), equipped=list(gear["worn"]))
    return out


def waiting(blocks: Dict[str, Any], facts: Optional[_Facts] = None) -> List[str]:
    gear = _gear(facts or _Facts(), blocks)
    return [p["slot"] for p in gear["waiting_slots"]] + list(gear["waiting_worn"])


def gear_lines(blocks: Dict[str, Any], sheet: Optional[Dict[str, Any]] = None) -> List[str]:
    """The starting gear chosen so far in names, one line per package, slot and what is worn; only filled blocks.
    With the sheet, an item the hand rule would leave carried is said to be."""
    facts = _Facts()
    gear = _gear(facts, blocks)
    picked = {p["slot"]: p for p in gear["slots"]}
    lines = []
    for kind in ("class", "background"):
        option = _package_option(facts, kind, blocks)
        label = "%s package" % kind.capitalize()
        if option is None:
            lines.append("%s: not chosen yet" % label)
            continue
        names = []
        for _, item in _package_items(option, kind):
            slot = item.get("slot") if isinstance(item.get("slot"), str) else None
            pick = picked.get(slot)
            if slot and pick is None:
                name = "%s (not chosen yet)" % (item.get("uncatalogued") or "one of: %s" % ", ".join(
                    facts.d.catalog.get(i, i) for i in item.get("choose_one") or []))
            elif slot:
                name = pick.get("display_name") or facts.d.catalog.get(pick.get("catalog_id"), "")
            else:
                name = facts.d.catalog.get(item.get("catalog_id")) or item.get("uncatalogued") or ""
            count = int(item.get("quantity") or 1)
            names.append("%s x%d" % (name, count) if count > 1 else name)
        gold = int((option.get("coins") or {}).get("gp") or 0)
        lines.append("%s %s: %s" % (label, blocks["starting_equipment"][kind + "_package"], ", ".join(
            [n for n in names if n] + (["%d gold" % gold] if gold else []))))
    worn = [(i, False) for i in gear["worn"]]
    if sheet is not None and worn:
        worn = startup_rows.worn_preview(sheet, _chosen_items(facts, blocks), gear["slots"], gear["worn"])
    names = {full: ", ".join(facts.d.catalog.get(i, i) for i, carried in worn if carried is full) for full in (False, True)}
    return lines + ["Worn or held: %s%s" % (names[False] or "nothing chosen yet",
                                            "; carried (hands full): %s" % names[True] if names[True] else "")]


_METHODS = {"standard_array": "Standard Array", "point_buy": "Point Buy", "random": "Rolled"}


def _class_name(facts: _Facts, key: str) -> str:
    return ((facts.d.progression.get("classes") or {}).get(key) or {}).get("name") or key.capitalize()


def _choice_label(facts: _Facts, intent: Dict[str, Any], cid: str, issued: Dict[str, Dict[str, Any]]) -> str:
    """The choice's name; where two issued choices share it, with where this one comes from."""
    point = issued[cid]
    if [p["name"] for p in issued.values()].count(point["name"]) < 2:
        return point["name"]
    source = point.get("feature")
    if not source and cid.startswith("species."):
        source = facts.d.species()[intent["species_key"]]["name"]
    if not source:
        ref = (facts.d.backgrounds()[intent["background_key"]].get("feat_ref") or {}).get("feat_key")
        source = next((f["name"] for f in facts.d.choices["feats"] if f.get("key") == ref), None)
    return "%s (%s)" % (point["name"], source) if source else point["name"]


def _option_name(facts: _Facts, point: Dict[str, Any], pick: Any) -> str:
    spell = point.get("from_spellbook") or isinstance(point.get("options"), list)
    return facts.d.spell_name.get(pick, str(pick)) if spell else str(pick)


# --- dropping what no longer belongs ---

def _values(blocks: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Every gated block as {block id: values}; the shape a drop is reported in."""
    intent, equipment = blocks["intent"], blocks["starting_equipment"]
    out = {cid: list(picks) for cid, picks in intent["choices"].items()}
    if (intent["ability_scores"] or {}).get("assignment"):
        out["ability_scores.assignment"] = [intent["ability_scores"]["assignment"]]
    if equipment["background_package"] is not None:
        out["starting_equipment.background_package"] = [equipment["background_package"]]
    for pick in equipment["slot_picks"]:
        out["starting_equipment.slot:%s" % pick.get("slot")] = [pick.get("catalog_id") or pick.get("display_name")]
    if equipment["equipped"]:
        out["starting_equipment.equipped"] = list(equipment["equipped"])
    return out


def _lost(before: Dict[str, List[Any]], after: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
    out = {key: [v for v in values if v not in after.get(key, [])] for key, values in before.items()}
    return {key: values for key, values in out.items() if values}


def still_lost(lost: Dict[str, List[Any]], held: Dict[str, Any], standing: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Of what a turn's replies dropped: what the player had when the turn began and has nothing in place of now."""
    was, now = _values(held), _values(standing)
    out = {key: [v for v in values if v in was.get(key, [])] for key, values in lost.items()
           if key not in now or key == "starting_equipment.equipped"}
    return {key: values for key, values in _lost(out, now).items()}


def _switch(facts: _Facts, blocks: Dict[str, Any], key: str, value: Any, held: Dict[str, Any]) -> None:
    """Set an identity key. A change from one value to another drops the gear of the old one and the picks it
    issued; a change back to the held value brings back what the player had under it. Arrival (from null) drops
    nothing."""
    intent, equipment = blocks["intent"], blocks["starting_equipment"]
    old = intent[key]
    if value == old:
        return
    kind = {"class_key": "class", "background_key": "background"}.get(key)
    mine = {slot for slot, owners in facts.slots.items() if any(k == kind for k, _, _, _ in owners)}
    if old is not None:
        if kind:
            equipment[kind + "_package"] = None
            equipment["slot_picks"] = [p for p in equipment["slot_picks"] if p.get("slot") not in mine]
            equipment["equipped"] = []
    before = set(creation_scope.issued_points(intent, facts.d)) if old is not None else set()
    intent[key] = value
    if old is not None:
        after = creation_scope.issued_points(intent, facts.d)
        intent["choices"] = {c: p for c, p in intent["choices"].items() if c not in before or c in after}
    if value is None or value != held["intent"][key]:
        return
    issued = creation_scope.issued_points(held["intent"], facts.d)
    for cid, picks in held["intent"]["choices"].items():
        if cid in issued and cid not in intent["choices"]:
            intent["choices"][cid] = list(picks)
    if kind:
        was = held["starting_equipment"]
        equipment[kind + "_package"] = equipment[kind + "_package"] or was[kind + "_package"]
        have = {p.get("slot") for p in equipment["slot_picks"]}
        equipment["slot_picks"] += [copy.deepcopy(p) for p in was["slot_picks"]
                                    if p.get("slot") in mine and p.get("slot") not in have]
        equipment["equipped"] = equipment["equipped"] or list(was["equipped"])


def _tie_class_package(facts: _Facts, blocks: Dict[str, Any]) -> None:
    """The class package is one block written in two places: its choice id and class_package."""
    cid = facts.class_package_id(blocks["intent"]["class_key"])
    picks = blocks["intent"]["choices"].get(cid) if cid else None
    blocks["starting_equipment"]["class_package"] = picks[0] if picks else None


def _settle(facts: _Facts, blocks: Dict[str, Any], rolled: Optional[List[int]]) -> None:
    """Drop every block the engine would refuse now, until none is left. Used on blocks this reply did not send."""
    intent, equipment = blocks["intent"], blocks["starting_equipment"]
    while True:
        problems = creation_scope.choice_problems(intent, facts.d)
        if not problems:
            break
        _drop_refused(intent["choices"], problems)
    _tie_class_package(facts, blocks)
    for kind in ("class", "background"):
        if equipment[kind + "_package"] is not None and _package_option(facts, kind, blocks) is None:
            equipment[kind + "_package"] = None
    scores = intent["ability_scores"]
    if scores and scores.get("assignment") is not None and creation_build.base_scores(facts.d, scores, rolled)[1]:
        scores["assignment"] = None
    bound = _bound_pick(facts, blocks)
    if bound:  # a pick that stood for the bound slot and is not the tool pick is gone, and reported as dropped
        equipment["slot_picks"] = [p for p in equipment["slot_picks"] if p == bound or p.get("slot") != bound["slot"]]
    while True:
        gear = _gear(facts, blocks)
        if not gear["gone"] and not gear["refused"]:
            break
        equipment["slot_picks"] = gear["slots"] + gear["waiting_slots"]
        equipment["equipped"] = gear["worn"] + gear["waiting_worn"]


def _drop_refused(choices: Dict[str, Any], problems: List[Dict[str, Any]]) -> None:
    """Take the refused picks out. What is no longer offered, repeated or not held goes first; what is left may then
    fit its count. A list that is too long is dropped whole: the engine never chooses among the player's picks."""
    for problem in [p for p in problems if "options" in p] or problems:
        picks = choices.pop(problem["choice_id"], None) or []
        rest = (creation_scope.distinct(picks) if problem["problem"] == "repeated" else
                [p for p in picks if p not in problem["options"]] if "options" in problem else [])
        if rest:
            choices[problem["choice_id"]] = rest


def settle(blocks: Dict[str, Any], *, rolled: Optional[List[int]] = None) -> tuple:
    """(blocks read back from a saved interview as the engine would hold them now, what was dropped). Data that
    cannot be read changes nothing."""
    facts = _Facts()
    out = copy.deepcopy(blocks)
    if facts.ok:
        cls, package = out["intent"]["class_key"], out["starting_equipment"]["class_package"]
        cid = facts.class_package_id(cls)
        picks = out["intent"]["choices"].get(cid) if cid else None
        if picks and package is not None and picks != [package]:
            # An interview saved before the two were one block: neither record can be trusted.
            del out["intent"]["choices"][cid]
        elif cid and not picks and package is not None:
            out["intent"]["choices"][cid] = [package]
        for key, keys in (("class_key", facts.d.classes()), ("species_key", facts.d.species()),
                          ("background_key", facts.d.backgrounds())):
            if out["intent"][key] not in keys:
                out["intent"][key] = None
        _settle(facts, out, rolled)
    return out, _lost(_values(blocks), _values(out))


# --- one reply ---

def merge(held: Dict[str, Any], standing: Dict[str, Any], reply: Dict[str, Any], *, rolled: Optional[List[int]] = None,
          previous=frozenset, alignments: Optional[List[str]] = None) -> Merge:
    """The blocks after this reply. previous(): the choice ids earlier scopes of this interview issued; a pick
    under one the new scope does not issue is a switch's leftover, dropped and never refused."""
    facts = _Facts()
    out = copy.deepcopy(standing)
    intent, equipment = out["intent"], out["starting_equipment"]
    sent = reply.get("intent") or {}
    problems: List[Dict[str, Any]] = []
    aside: List[str] = []
    leftovers: Dict[str, List[Any]] = {}
    lost: Dict[str, List[Any]] = {}
    stood = _values(out)

    for key in IDENTITY:
        if key in sent:
            _switch(facts, out, key, sent[key] if sent[key] else held["intent"][key], held)
    lost.update(_lost(stood, _values(out)))
    if "considering" in sent:
        intent["considering"] = dict(intent["considering"], **copy.deepcopy(sent["considering"]))
    _merge_scores(facts, held, intent, sent, rolled, problems, aside)
    gear = reply.get("starting_equipment") or {}
    _merge_choices(facts, held, out, sent.get("choices") or {}, gear, previous, problems, leftovers, lost)
    _merge_gear(facts, held, out, gear, problems, aside, leftovers)
    if facts.ok:
        now = _values(out)
        _settle(facts, out, rolled)
        for key, values in _lost(now, _values(out)).items():
            lost[key] = lost.get(key, []) + values
    unwritten = _merge_creative(held, out["creative"], reply.get("creative") or {}, alignments)
    return Merge(out, problems, unwritten, aside, lost, leftovers)


def _merge_scores(facts, held, intent, sent, rolled, problems, aside) -> None:
    if "ability_scores" not in sent:
        return
    if sent["ability_scores"] is None:
        intent["ability_scores"] = copy.deepcopy(held["intent"]["ability_scores"])
        return
    now = dict(intent["ability_scores"] or {"method": None, "assignment": None})
    new = sent["ability_scores"]
    if new.get("method") and new["method"] != now.get("method"):
        now = {"method": new["method"], "assignment": None}
    if "assignment" in new:
        if new["assignment"] is None:
            old = held["intent"]["ability_scores"] or {}
            now["assignment"] = copy.deepcopy(old.get("assignment")) if old.get("method") == now["method"] else None
        elif now["method"] is None or (now["method"] == "random" and rolled is None):
            aside.append("ability_scores.assignment")  # no method, or the engine has not rolled yet: a guess
        else:
            trial = {"method": now["method"], "assignment": new["assignment"]}
            refused = creation_build.base_scores(facts.d, trial, rolled)[1] if facts.ok else None
            if refused and _summary_echo(facts, held["intent"], now, new["assignment"]):
                aside.append("ability_scores.summary_echo")  # the shown totals sent back: nothing changed
            elif refused:
                problems.append({"choice_id": "ability_scores.assignment", "problem": "refused", "why": refused["problem"]})
            else:
                now = copy.deepcopy(trial)
    intent["ability_scores"] = now if now["method"] else None


def _summary_echo(facts, held, now, sent) -> bool:
    """Whether a refused assignment is the held base scores with the held background increase added, score for score:
    what the summary shows. Only while the held scores still stand."""
    if not now.get("assignment") or now != held["ability_scores"] or held["background_key"] is None:
        return False
    background = facts.d.backgrounds().get(held["background_key"]) or {}
    picks = held["choices"].get("background.%s.ability-scores" % held["background_key"]) or [None]
    raised = creation_build.raised_scores(background, picks[0], now["assignment"])
    return (raised is not None and isinstance(sent, dict) and sent == raised[0]
            and all(type(v) is int for v in sent.values()))


def _merge_choices(facts, held, out, sent, gear, previous, problems, leftovers, lost) -> None:
    intent, equipment = out["intent"], out["starting_equipment"]
    before = copy.deepcopy(intent["choices"])
    sent = dict(sent)
    # The class package: one block, in the choice id or in class_package.
    cid = facts.class_package_id(intent["class_key"])
    letter = gear.get("class_package") or None
    if cid and letter is not None:
        if cid in sent and list(sent[cid]) != [letter]:
            problems.append({"choice_id": cid, "problem": "two_values", "options": list(sent.pop(cid)) + [letter]})
        else:
            sent[cid] = [letter]
    elif cid and "class_package" in gear and cid not in sent and cid in held["intent"]["choices"]:
        sent[cid] = list(held["intent"]["choices"][cid])  # null: back to held
    # #1368: the background package is recorded only in starting_equipment; its mirror under a choice id is redundant.
    mirror = "background.%s.starting-equipment" % intent["background_key"]
    if mirror in sent and sent[mirror] == [gear.get("background_package") or equipment["background_package"]]:
        del sent[mirror]
    for key, picks in sent.items():
        if picks:
            intent["choices"][key] = creation_scope.distinct(picks)  # a repeat fills nothing: the choice stays open
        else:
            intent["choices"].pop(key, None)
    if not facts.d.ok:
        return
    issued = creation_scope.issued_points(intent, facts.d)
    stray = [k for k in sent if k in intent["choices"] and k not in issued]
    earlier = previous() if stray else ()
    for key in stray:
        if key in earlier:
            leftovers[key] = intent["choices"].pop(key)
            before.pop(key, None)
            sent.pop(key)
    refused: List[Dict[str, Any]] = []
    kept: Dict[str, List[Any]] = {}
    while True:
        found_now = creation_scope.choice_problems(intent, facts.d, before)
        bad: Dict[str, List[Dict[str, Any]]] = {}
        for problem in found_now:
            if problem["choice_id"] in sent:
                bad.setdefault(problem["choice_id"], []).append(problem)
        if found_now and not bad:
            # What stood and cannot stay beside what was sent goes now, so the rest is judged on what is left.
            was = copy.deepcopy(intent["choices"])
            _drop_refused(intent["choices"], found_now)
            for key, values in _lost(was, intent["choices"]).items():
                lost[key] = lost.get(key, []) + values
            continue
        if not bad:
            break
        for key, found in bad.items():  # one id can have two problems (too many, and one not offered)
            kept[key] = _good_part(intent["choices"].pop(key), found, before.get(key) or [])
            refused += [p for p in found if p["problem"] != "too_many"] if kept[key] else found
            if kept[key]:
                intent["choices"][key] = list(kept[key])  # judged again: what is kept can meet a later rule
                continue
            sent.pop(key)
            if key in before:
                intent["choices"][key] = before[key]
    problems += [dict(p, kept=list(kept[p["choice_id"]])) if kept[p["choice_id"]] else p for p in refused]


def _good_part(picks: List[Any], found: List[Dict[str, Any]], stood: List[Any]) -> List[Any]:
    """What is kept of a refused list: the options its choice offers, when they fit its count (a list too long keeps
    none: the engine never chooses among the player's picks) and take nothing the player already had."""
    outside = [o for p in found for o in p.get("options") or []]
    good = [p for p in picks if p not in outside]
    limit = next((p["count"] for p in found if p["problem"] == "too_many"), len(good))
    return good if outside and len(good) <= limit and all(p in good for p in stood) else []


def _merge_gear(facts, held, out, gear, problems, aside, leftovers) -> None:
    intent, equipment = out["intent"], out["starting_equipment"]
    old = held["starting_equipment"]
    if "class_package" in gear and gear["class_package"] and not facts.class_package_id(intent["class_key"]):
        aside.append("starting_equipment.class_package")  # a letter means nothing before its class
    if "background_package" in gear:
        letter = gear["background_package"]
        options = facts.options("background", intent)
        if not letter:
            if old["background_package"] is not None and intent["background_key"] == held["intent"]["background_key"]:
                equipment["background_package"] = old["background_package"]
        elif options is None:
            aside.append("starting_equipment.background_package")
        elif letter not in options:
            problems.append({"choice_id": "starting_equipment.background_package", "problem": "not_offered",
                             "options": [letter], "offered": sorted(options)})
        else:
            equipment["background_package"] = letter
    if not facts.ok:
        return
    _tie_class_package(facts, out)
    for field in ("slot_picks", "equipped"):
        if field not in gear:
            continue
        if gear[field] is None:
            equipment[field] = copy.deepcopy(old[field])
            continue
        before, equipment[field] = equipment[field], copy.deepcopy(gear[field])
        if field == "slot_picks":
            bound = _bound_pick(facts, out)
            other = [p for p in equipment[field] if bound and p.get("slot") == bound["slot"] and p != bound]
            if other:  # the tool pick decides it: the author changes that pick or tells the player
                problems.append({"choice_id": "starting_equipment.slot:%s" % bound["slot"], "problem": "follows_choice",
                                 "follows": creation_scope.background_tool_id(facts.backgrounds[out["intent"]["background_key"]]),
                                 "held": [bound["display_name"]]})
            equipment[field] = [p for p in equipment[field] if p not in other]
        sorted_gear = _gear(facts, out)
        if field == "slot_picks":
            for _, pick, _ in sorted_gear["gone"]:
                equipment[field].remove(pick)
                leftovers["starting_equipment.slot:%s" % pick.get("slot")] = [pick.get("catalog_id") or pick.get("display_name")]
        bad = [(kind, value, why) for kind, value, why in sorted_gear["refused"]
               if (kind == "slot") == (field == "slot_picks")]
        for kind, value, why in bad:
            problems.append({"choice_id": ("starting_equipment.slot:%s" % value.get("slot")) if kind == "slot"
                             else "starting_equipment.equipped", "problem": "refused", "why": why})
        if bad:
            refused = [value for _, value, _ in bad]
            kept = [v for v in equipment[field] if v not in refused]
            if field == "slot_picks":
                # A refused pick leaves the one that stood; the good ones of the same list are kept.
                names = [v.get("slot") for v in refused]
                have = [v["slot"] for v in kept]
                kept += [v for v in before if v["slot"] in names and v["slot"] not in have]
            equipment[field] = kept


def _merge_creative(held, creative, sent, alignments) -> List[str]:
    """Each field alone. Text is kept as sent and never read; a field that is not its type is not written."""
    unwritten = []
    for field, value in sent.items():
        if field not in creation_build.CREATIVE_FIELDS + creation_build.OPTIONAL_CREATIVE_FIELDS:
            unwritten.append(field)
        elif value is None or (isinstance(value, str) and not value.strip()):
            creative.pop(field, None)
            if field in held["creative"]:
                creative[field] = copy.deepcopy(held["creative"][field])
        elif field == "feature_descriptions":
            if isinstance(value, dict) and all(isinstance(v, str) for v in value.values()):
                creative[field] = copy.deepcopy(value)
            else:
                unwritten.append(field)
        elif not isinstance(value, str) or (field == "alignment" and alignments and value not in alignments):
            unwritten.append(field)
        elif field == "name" and _name_refused(value):
            unwritten.append(field)
        else:
            creative[field] = value
    return unwritten


def fold_creative(creative: Dict[str, Any], saved: Dict[str, Any]) -> None:
    """Fold one saved item's details in: text replaces text; a null or empty one changes nothing."""
    _merge_creative({"creative": creative}, creative, {k: v for k, v in saved.items() if v}, None)


def _name_refused(value: str) -> bool:
    from updates.update_character_info import name_refusal
    return bool(name_refusal(value))


# --- what the author and the player are told ---

def needed(blocks: Dict[str, Any], *, facts: Optional[_Facts] = None, scope: Optional[Dict[str, Any]] = None) -> List[str]:
    """What the build still needs, in a fixed order, from the engine's own lists and the name."""
    facts = facts or _Facts()
    full = checked(blocks, facts)
    intent = full["intent"]
    scope = scope if scope is not None else (creation_scope.creation_scope(intent, facts.d) or {})
    out = [key for key in IDENTITY if intent[key] is None]
    out += creation_scope.open_choice_ids(intent, facts.d)
    out += [e["id"] for e in creation_scope.unanswered_required(scope, intent, full["starting_equipment"])]
    return out + ([] if blocks["creative"].get("name") else ["name"])


LIST_LIMIT = 20


def still_needed_lines(blocks: Dict[str, Any]) -> List[str]:
    """What the build still needs, for the player, in names; then what the first of it offers (a longer list is asked
    for). Empty when nothing is needed."""
    facts = _Facts()
    if not facts.ok:
        return []
    intent = checked(blocks, facts)["intent"]
    issued = creation_scope.issued_points(intent, facts.d)
    opened = {entry["id"]: entry for entry in creation_scope.open_choices(intent)}
    package_id = facts.class_package_id(intent["class_key"])
    labels, first = [], None
    for item in needed(blocks, facts=facts):
        offered: List[str] = []
        left = 0
        if item in IDENTITY:
            label = item[:-len("_key")]
            offered = [{"class_key": lambda k: _class_name(facts, k), "species_key": lambda k: facts.d.species()[k]["name"],
                        "background_key": lambda k: facts.d.backgrounds()[k]["name"]}[item](k)
                       for k in {"class_key": facts.d.classes, "species_key": facts.d.species,
                                 "background_key": facts.d.backgrounds}[item]()]
        elif item == package_id or item.startswith("starting_equipment."):
            label = "starting gear"
        elif item.startswith("ability_scores."):
            label = "ability scores"
            offered = list(_METHODS.values()) if item.endswith(".method") else []
        elif item in issued:
            left = issued[item]["count"] - len(opened[item]["chosen"])
            label = _choice_label(facts, intent, item, issued)
            chosen = [_option_name(facts, issued[item], p) for p in opened[item]["chosen"]]
            offered = [o for o in opened[item].get("options") or [] if o not in chosen]
        else:
            label = item  # "name"
        counted = label + (" (%d)" % left if left > 1 else "")
        if counted not in labels:
            labels.append(counted)
        if first is None:
            first = (label, offered)
    if not labels:
        return []
    lines = ["Still needed: %s." % ", ".join(labels)]
    if len(first[1]) > LIST_LIMIT:
        lines.append("Ask for the list of %s." % first[0])
    elif first[1]:
        lines.append("For %s you can choose: %s." % (first[0], ("; " if any("," in o for o in first[1]) else ", ").join(first[1])))
    return lines


def state(blocks: Dict[str, Any]) -> Dict[str, Any]:
    """The request-only item: what is filled, what waits, what is needed, what may be written at finalize, and the
    first few to ask next. Long text and spell picks are listed only as held."""
    facts = _Facts()
    full = checked(blocks, facts)
    intent, equipment = full["intent"], full["starting_equipment"]
    issued = creation_scope.issued_points(intent, facts.d)
    filled: Dict[str, Any] = {k: intent[k] for k in IDENTITY if intent[k] is not None}
    if blocks["creative"].get("name"):
        filled["name"] = blocks["creative"]["name"]
    for cid, picks in intent["choices"].items():
        spell = (issued.get(cid) or {}).get("kind") in ("cantrip", "prepared_spells", "spell_known")
        filled[cid] = "held" if spell or len(picks) > 4 else picks
    if intent["ability_scores"]:
        filled["ability_scores"] = intent["ability_scores"]
    for key in ("background_package", "class_package", "slot_picks", "equipped"):
        if equipment[key]:
            filled["starting_equipment." + key] = equipment[key]
    filled.update({f: "held" for f in blocks["creative"] if f != "name"})
    need = needed(blocks, facts=facts)
    out = {"filled": filled, "needed": need,
           "may_write_at_finalize": [f for f in creation_build.CREATIVE_FIELDS + ("backstory", "appearance")
                                     if f != "name" and f not in blocks["creative"]],
           "next": need[:NEXT_LIMIT]}
    wait = waiting(blocks, facts)
    if wait:
        out["waiting"] = wait
    repeats = creation_scope.repeated_for_room(intent)
    if repeats:
        out["adds_nothing_new"] = {
            "picks": [{"choice_id": cid, "option": pick} for cid, pick in repeats],
            "meaning": "Each is also held by another choice, so it gives the character nothing more; tell the player."}
    return out
