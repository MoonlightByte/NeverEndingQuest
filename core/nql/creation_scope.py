# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Engine-scoped creation facts (D-CREATE-COST-4, #193 Part 5).

The creation author (T092) declares the player's intent as typed fields: the
class, species and background keys and, for each choice the current scope
issued, the picked option keys. This module answers with only that intent's
rules, read from the data files at each call (never from prose):

- ``creation_scope(intent)``: the scope item appended to the interview.
  Before a class is named it carries a menu (each class, species and
  background with one line built from typed fields); once named, that
  class's, species' and background's facts, and every level-1 choice the
  intent opens, each under an engine-issued choice id with its count and
  typed options. ``considering`` keys add facts only (no ids), for options
  the player asks about without choosing.
- ``issued_points(intent)``: the choice ids the intent opens, with their
  points; ``choice_problems(intent)`` the typed refusals of an intent's picks
  (an id not issued, an option not offered, more picks than the count);
  ``open_choice_ids(intent)`` the issued ids still short of their count.
- ``scope_id(scope)``: the scope's identity, a hash of its canonical JSON.

Spell options are spell_repository.json keys; the lists come from the
leveling resolver (``core.leveling.choices.resolve_options``) with an empty
sheet. Choice ids are ``<class>.<feature>.<name>`` slugs; names repeat inside
a class (two Skill Proficiencies points for the Bard), so the feature is part
of the id, and a positional suffix separates any id that still repeats.
"""
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core.leveling import choices as leveling_choices

SCOPE_PURPOSE = "startup_creation_scope"
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
ORIGINS_PATH = os.path.join(_DATA, "srd_character_origins.json")
CHOICES_PATH = os.path.join(_DATA, "srd", "choices.json")
PROGRESSION_PATH = os.path.join(_DATA, "srd", "progression.json")
CATALOG_PATH = os.path.join(_DATA, "srd", "item_catalog.json")
SPELLS_PATH = os.path.join(_DATA, "spell_repository.json")

SHEET_REPRESENTATION = (
    "SRD 5.2.1 backgrounds have no background feature: a background raises ability scores "
    "(background_ability_scores_rule) and grants an Origin feat, skills, a tool and equipment. "
    "Put the species name in race and the background name in background. Record the background's "
    "Origin feat in feats as {\"name\": \"<feat name>\", \"description\": \"<its text here>\", "
    "\"source\": \"<background> background (SRD 5.2.1)\"}, and set backgroundFeature to exactly "
    "{\"name\": \"Origin feat: <feat name>\", \"description\": \"<the same text>\", "
    "\"source\": \"<background> background (SRD 5.2.1)\"}. Other feats, such as a Human's "
    "Versatile Origin feat, also go in feats with their source. A chosen Fighting Style goes in "
    "classFeatures, not feats, as {\"name\": \"Fighting Style: <style name>\", \"description\": "
    "\"<its text here>\", \"source\": \"<class> level <level>\"}, the name level-up writes. "
    "Record the class's level-1 order choice as one classFeatures entry named exactly "
    "\"Divine Order: <option>\" or \"Primal Order: <option>\".")


def _load(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


class _Data:
    """The data files for one call; None when any cannot be read."""

    def __init__(self) -> None:
        self.origins = _load(ORIGINS_PATH)
        self.choices = _load(CHOICES_PATH)
        self.progression = (_load(PROGRESSION_PATH) or {})
        items = _load(CATALOG_PATH) or {}
        self.catalog = {e["id"]: e["name"] for e in items.get("entries") or []}
        self.items = items.get("entries") or []
        repo = _load(SPELLS_PATH) or {}
        self.spell_key = {v["name"]: k for k, v in repo.items()
                          if k != "_metadata" and isinstance(v, dict) and v.get("name")}
        self.spell_name = {k: n for n, k in self.spell_key.items()}
        self.ok = bool(self.origins and self.choices and self.catalog and self.spell_key)
        # The skills, tools and languages, as the keys every pick of one uses.
        self.proficiencies = frozenset(
            name for source in ("skills:all", "tools:all", "languages:all")
            for name in leveling_choices.resolve_options(source, {}, "", 1) or []) if self.ok else frozenset()

    def classes(self) -> Dict[str, Any]:
        return self.choices["choice_points"]

    def species(self) -> Dict[str, Dict[str, Any]]:
        return {s["key"]: s for s in self.origins["species"]}

    def backgrounds(self) -> Dict[str, Dict[str, Any]]:
        return {b["key"]: b for b in self.origins["backgrounds"]}


def class_keys() -> List[str]:
    d = _Data()
    return sorted(d.classes()) if d.ok else []


def species_keys() -> List[str]:
    d = _Data()
    return sorted(d.species()) if d.ok else []


def background_keys() -> List[str]:
    d = _Data()
    return sorted(d.backgrounds()) if d.ok else []


# --- typed options (moved from utils/startup_prompt_builder.py; the whole reference keeps using them) ---

def typed_options(option_items: Dict[str, Any], catalog: Dict[str, str], flags: bool = False) -> Dict[str, Any]:
    """A starting-package choice's typed options, whole: each option's key, its items (catalog ids with
    the catalog's printed names, choose_one ids, uncatalogued keys, slots) and its coins. The game's own
    fields for an uncatalogued item (item_type, description) stay in the data. With flags (the engine
    scope, D-ALLCLASS-1 after dplay-AC-wizard), each item says whether starting_equipment.equipped can
    name it (a catalog item or a choose_one slot) and the data's authored aliases, when it has them."""
    def item(entry):
        typed = {k: v for k, v in entry.items() if k not in ("item_type", "description", "aliases")}
        if entry.get("catalog_id") in catalog:
            typed["name"] = catalog[entry["catalog_id"]]
        if isinstance(entry.get("choose_one"), list):
            typed["choose_one"] = [{"catalog_id": i, "name": catalog.get(i)} for i in entry["choose_one"]]
        if flags:
            typed["equippable"] = entry.get("catalog_id") in catalog or isinstance(entry.get("choose_one"), list)
            if entry.get("aliases"):
                typed["aliases"] = list(entry["aliases"])
        return typed
    return {key: {"items": [item(e) for e in option.get("items") or []], "coins": option.get("coins")}
            for key, option in option_items.items()}


def level_1_choices(choice_points: Dict[str, Any], catalog: Dict[str, str],
                    flags: bool = False) -> List[Dict[str, Any]]:
    """A new character's level-1 choices for one class (multiclass-only entries omitted)."""
    out = []
    for point in choice_points.get("1", []):
        if point.get("applies") == "multiclass":
            continue
        entry = {"name": point["name"], "count": point["count"]}
        if isinstance(point.get("option_source"), list):
            entry["options"] = point["option_source"]
        if isinstance(point.get("option_items"), dict):
            entry["option_items"] = typed_options(point["option_items"], catalog, flags=flags)
        # A class order's typed grants (Protector, Warden) and the choices an option opens
        # (Thaumaturge's and Magician's extra cantrip), as choices.json carries them.
        for key in ("option_grants", "then"):
            if isinstance(point.get(key), dict):
                entry[key] = point[key]
        entry["text"] = point.get("evidence")
        entry["page"] = point.get("source", {}).get("page")
        out.append(entry)
    return out


def level_1_features(progression_class: Any) -> Dict[str, Any]:
    """A class's fixed level-1 feature names and level-1 class-table values, or nothing."""
    if not isinstance(progression_class, dict):
        return {}
    features = (progression_class.get("features_by_level") or {}).get("1")
    if not isinstance(features, list):
        return {}
    table = {column: values["1"] for column, values in (progression_class.get("table_columns") or {}).items()
             if isinstance(values, dict) and "1" in values}
    return {"features": list(features), "class_table_at_level_1": table}


# --- choice points and their ids ---

def _resolved(point: Dict[str, Any], cls: str, d: _Data) -> Dict[str, Any]:
    """One choice point's typed options: a list of option keys (spells as repository keys), the package
    options, or a free pick the host cannot enumerate."""
    source = point.get("option_source")
    if isinstance(point.get("option_items"), dict):
        return {"option_keys": sorted(point["option_items"]),
                "options": typed_options(point["option_items"], d.catalog, flags=True)}
    if isinstance(source, str) and source.startswith("spells:"):
        if "spellbook" in source:
            # The prepared spells come from this character's own spellbook picks (an empty sheet resolves
            # nothing at creation); the id of the pick they come from is set by the caller.
            return {"from_spellbook": True}
        names = leveling_choices.resolve_options(source, {}, cls, 1, point.get("filters")) or []
        keys = [d.spell_key[n] for n in names if n in d.spell_key]
        return {"option_keys": keys, "options": [{"key": k, "name": d.spell_name[k]} for k in keys]}
    if isinstance(source, list):
        return {"option_keys": [str(x) for x in source]}
    if leveling_choices.free_pick(source):
        return {"free_pick": True}
    if isinstance(source, str) and source.split(":", 1)[0] == "languages":
        known = set(d.choices["languages"].get("known") or [])
        known.update(((d.choices["class_traits"].get(cls) or {}).get("languages") or {}).get("granted") or [])
        names = leveling_choices.resolve_options(source, {}, cls, 1) or []
        return {"option_keys": [n for n in names if n not in known]}
    names = leveling_choices.resolve_options(source, {}, cls, 1, point.get("filters"))
    if not names and point.get("filters"):
        # A filter that reads the sheet (proficient, no_expertise) has no sheet at creation: the
        # unfiltered list is offered, and section 2 judges the requirement (nql-eb S1).
        names = leveling_choices.resolve_options(source, {}, cls, 1)
    return {"option_keys": list(names)} if names is not None else {"free_pick": True}


def _section_of(point: Dict[str, Any]) -> str:
    """The reviewer section a choice belongs to, from typed fields (r3 section 4.2): a starting package is S4;
    spells and invocations (the spells reference form, the cantrip and prepared kinds) are S3; the
    background's ability split is S1; skills, tools, languages, masteries, styles and orders are S2."""
    head = str(point.get("option_source") or "").split(":", 1)[0]
    if isinstance(point.get("option_items"), dict):
        return "S4"
    if point.get("kind") in ("cantrip", "prepared_spells") or head in ("spells", "invocations"):
        return "S3"
    if point.get("kind") == "ability_scores":
        return "S1"
    return "S2"


def _point_entry(cid: str, point: Dict[str, Any], cls: str, d: _Data, section: Optional[str] = None) -> Dict[str, Any]:
    entry = {"id": cid, "kind": point.get("kind"), "name": point["name"], "feature": point.get("feature"),
             "count": point["count"], "section": section or _section_of(point)}
    entry.update(_resolved(point, cls, d))
    for key in ("option_grants",):
        if isinstance(point.get(key), dict):
            entry[key] = point[key]
    if point.get("evidence"):
        entry["text"] = point["evidence"]
    if (point.get("source") or {}).get("page"):
        entry["page"] = point["source"]["page"]
    return entry


def _unique(ids: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    out = []
    for i in ids:
        seen[i] = seen.get(i, 0) + 1
        out.append(i if seen[i] == 1 else "%s.%d" % (i, seen[i]))
    return out


def _class_points(cls: str, d: _Data) -> List[Tuple[str, Dict[str, Any]]]:
    points = [p for p in d.classes()[cls].get("1", []) if p.get("applies") != "multiclass"]
    ids = _unique(["%s.%s.%s" % (cls, _slug(p.get("feature") or "class"), _slug(p["name"])) for p in points])
    return list(zip(ids, points))


def _feat_spell_points(background: Dict[str, Any], d: _Data) -> List[Tuple[str, Dict[str, Any]]]:
    """The spell picks of a background's Origin feat when its feat_ref names a spell list (Magic
    Initiate (Cleric)): the feat's choice whose then carries that list, keyed by feat and list."""
    ref = background.get("feat_ref") or {}
    spell_list = ref.get("spell_list")
    feat = next((f for f in d.choices["feats"] if f.get("key") == ref.get("feat_key")), None)
    if not spell_list or feat is None:
        return []
    subs = next(((c.get("then") or {}).get(spell_list) for c in feat.get("choices") or []
                 if spell_list in (c.get("then") or {})), None) or []
    # The feat's other picks (its spellcasting ability); the list choice itself is fixed by the background.
    subs = list(subs) + [c for c in feat.get("choices") or [] if not c.get("then")]
    return [("feat.%s.%s.%s" % (_slug(feat["key"]), _slug(spell_list), _slug(sub["name"])), sub) for sub in subs]


def _ability_options(background: Dict[str, Any]) -> List[str]:
    """The background's ability increases as option keys: "+2 <ability>, +1 <ability>" for each ordered pair
    of its three abilities, and "+1 each" (background_ability_scores_rule)."""
    abilities = list(background.get("ability_keys") or [])
    pairs = ["+2 %s, +1 %s" % (a, b) for a in abilities for b in abilities if a != b]
    return pairs + ["+1 each"] if len(abilities) == 3 else []


def background_tool_id(background: Dict[str, Any]) -> str:
    """The id of a background's tool pick (tool_choice): background.<key>.<slug(the tool category)>, e.g.
    background.soldier.gaming-set."""
    tool = background.get("tool_choice") or {}
    category = str(tool.get("option_source") or "").partition("category=")[2]
    return "background.%s.%s" % (background["key"], _slug(tool.get("name") or category or "tool"))


def issued_points(intent: Dict[str, Any], data: Optional[_Data] = None) -> Dict[str, Dict[str, Any]]:
    """Every choice id the intent opens, with its typed entry, in order: the class's level-1 points and the
    sub-picks of the options the intent took; the background feat's spell picks; the standard languages
    once a species is named."""
    d = data if data is not None else _Data()
    if not d.ok:
        return {}
    intent = intent or {}
    picks = intent.get("choices") or {}
    out: Dict[str, Dict[str, Any]] = {}
    cls = intent.get("class_key")
    if cls in d.classes():
        points = _class_points(cls, d)
        # A point whose options are another point's picks names that point's key (options_from).
        by_key = {point["key"]: cid for cid, point in points if point.get("key")}
        for cid, point in points:
            entry = _point_entry(cid, point, cls, d)
            if point.get("options_from"):
                entry["from_choice"] = by_key.get(point["options_from"])
            out[cid] = entry
            for option, subs in (point.get("then") or {}).items():
                if option in (picks.get(cid) or []):
                    for sub in subs:
                        sid = "%s.%s.%s" % (cid, _slug(option), _slug(sub["name"]))
                        out[sid] = _point_entry(sid, sub, cls, d)
    background = d.backgrounds().get(intent.get("background_key"))
    if background and _ability_options(background):
        bid = "background.%s.ability-scores" % background["key"]
        out[bid] = {"id": bid, "kind": "ability_scores", "name": "Ability Score Increases", "count": 1, "section": "S1",
                    "option_keys": _ability_options(background), "text": d.origins["background_ability_scores_rule"],
                    "page": background.get("page")}
    tool = (background or {}).get("tool_choice")
    if isinstance(tool, dict):
        tid = background_tool_id(background)
        point = {"kind": "tool", "name": tool.get("name") or "Tool Proficiency", "count": int(tool.get("count") or 1),
                 "option_source": tool.get("option_source"), "evidence": background.get("tool_proficiency"),
                 "source": {"page": background.get("page")}}
        out[tid] = _point_entry(tid, point, cls or "", d, "S2")
    out.update(_species_points(intent.get("species_key"), picks, cls or "", d))
    for sid, sub in _feat_spell_points(background, d) if background else []:
        # Every pick of a feat that grants spells is reviewed with the spells (r3 section 4.2: Magic Initiate -> S3).
        out[sid] = _point_entry(sid, sub, background["feat_ref"]["spell_list"].lower(), d, "S3")
    if intent.get("species_key") in d.species():
        known = set(d.choices["languages"].get("known") or [])
        known.update(((d.choices["class_traits"].get(cls) or {}).get("languages") or {}).get("granted") or [])
        standard = [n for n in d.choices["languages"]["standard"] if n not in known]
        out["languages.standard"] = {
            "id": "languages.standard", "kind": "language", "name": "Standard Languages", "count": 2, "section": "S2",
            "option_keys": standard, "text": d.origins["languages_rule"]["passages"][0],
            "page": d.choices["languages"]["source"]["page"]}
    granted = _granted(intent, d)
    if granted:
        # No skill or tool pick (a class's, a species's, a feat's) offers what the background or class already
        # grants (typed set difference).
        for entry in out.values():
            if _is_proficiency(entry, d):
                excluded = [k for k in entry["option_keys"] if k in granted]
                entry["option_keys"] = [k for k in entry["option_keys"] if k not in granted]
                if excluded:
                    # Typed, so a review never asks for them back (all-class B3, dplay-AC-rogue round 6).
                    entry["excluded_granted"] = excluded
    return out


def _granted(intent: Dict[str, Any], d: _Data) -> set:
    """The skills and tools the class and background grant without a pick (typed keys)."""
    background = d.backgrounds().get(intent.get("background_key")) or {}
    traits = d.choices["class_traits"].get(intent.get("class_key")) or {}
    return set(background.get("skill_keys") or []) | set(background.get("tool_keys") or []) | set(
        traits.get("tool_proficiencies") or [])


def _is_proficiency(point: Dict[str, Any], d: _Data) -> bool:
    """A point whose every option is a skill, a tool or a language (Expertise is not one: it needs the skill)."""
    keys = point.get("option_keys")
    return bool(isinstance(keys, list) and keys and point.get("kind") != "expertise"
                and all(k in d.proficiencies for k in keys))


def distinct(picks: Any) -> List[Any]:
    """The picks with a repeated option once (#2095): a repeat fills nothing."""
    out: List[Any] = []
    for pick in picks or []:
        if pick not in out:
            out.append(pick)
    return out


def _elsewhere(intent: Dict[str, Any], issued: Dict[str, Dict[str, Any]], d: _Data) -> Dict[str, Dict[Any, List[str]]]:
    """For each issued skill, tool or language choice: its options another such choice holds, with the holders'
    ids. One with fewer than its count of options left over is not in it: it may repeat one, so that no choice is
    left without enough options (#2095)."""
    points = {cid: point for cid, point in issued.items() if _is_proficiency(point, d)}
    picks = intent.get("choices") or {}
    out = {}
    for cid, point in points.items():
        held: Dict[Any, List[str]] = {}
        for other in points:
            for pick in distinct(picks.get(other)) if other != cid else ():
                held.setdefault(pick, []).append(other)
        if len([k for k in point["option_keys"] if k not in held]) >= point["count"]:
            out[cid] = held
    return out


def repeated_for_room(intent: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """The picks that repeat another choice's because their choice had too few other options."""
    d = _Data()
    issued = issued_points(intent, d)
    ruled = _elsewhere(intent, issued, d) if issued else {}
    picks = intent.get("choices") or {}
    points = [cid for cid in issued if _is_proficiency(issued[cid], d)]
    return [(cid, pick) for cid in points if cid not in ruled for pick in distinct(picks.get(cid))
            if any(pick in (picks.get(other) or []) for other in points if other != cid)]


def _held_skills(intent: Dict[str, Any], issued: Dict[str, Dict[str, Any]], d: _Data) -> set:
    """The skills the build holds: the background's and every skill pick."""
    picks = intent.get("choices") or {}
    return _granted(intent, d) | {p for cid, point in issued.items() if _is_proficiency(point, d)
                                  for p in picks.get(cid) or []}


def _asks_spell_list(feat: Optional[Dict[str, Any]]) -> bool:
    """A feat with a choice whose options bring picks of their own (then): not asked under a species yet (#2104)."""
    return any(sub.get("then") for sub in (feat or {}).get("choices") or [])


def _species_points(key: Any, picks: Dict[str, Any], cls: str, d: _Data) -> Dict[str, Dict[str, Any]]:
    """The species' level-1 choices from its typed grants (D-CREATE-COST-5): species.<key>.<slug(choice)>,
    the size when the species offers two, a lineage's spellcasting ability once the lineage is picked, and
    the sub-picks of a Versatile Origin feat that has them. A feat whose spell list is itself a pick is not offered
    there until that list can be asked (#2102)."""
    species = d.species().get(key)
    grants = (species or {}).get("grants")
    if not isinstance(grants, dict):
        return {}
    page = (grants.get("source") or {}).get("page") or species.get("page")
    out: Dict[str, Dict[str, Any]] = {}
    if grants.get("size_options"):
        sid = "species.%s.size" % key
        out[sid] = {"id": sid, "kind": "size", "name": "Size", "count": 1, "section": "S1",
                    "option_keys": list(grants["size_options"]), "text": species.get("size"), "page": page}
    traits = {t.get("name"): t.get("text") for t in grants.get("traits") or [] if isinstance(t, dict)}
    for choice in grants.get("choices") or []:
        cid = "species.%s.%s" % (key, _slug(choice["name"]))
        if choice.get("options_from"):
            spec = choice["options_from"]
            table = next((t for t in species.get("tables") or [] if t.get("title") == spec.get("table")), {})
            column = (table.get("columns") or []).index(spec["option_column"]) if table else 0
            entry = {"option_keys": [row[column] for row in table.get("rows") or []]}
        elif choice.get("options"):
            entry = {"option_keys": [o["name"] for o in choice["options"]]}
        else:
            entry = _resolved({"option_source": choice.get("option_source")}, cls, d)
        if choice.get("kind") == "feat" and isinstance(entry.get("option_keys"), list):
            unasked = {f.get("name") for f in d.choices["feats"] if _asks_spell_list(f)}
            entry["option_keys"] = [k for k in entry["option_keys"] if k not in unasked]
        out[cid] = dict({"id": cid, "kind": choice.get("kind") or "species_option", "name": choice["name"],
                         "count": 1, "section": "S2", "text": traits.get(choice.get("trait") or choice["name"]),
                         "page": page}, **entry)
        if choice.get("spellcasting_ability") and picks.get(cid):
            aid = "%s.spellcasting-ability" % cid
            out[aid] = {"id": aid, "kind": "ability", "name": "Spellcasting Ability", "count": 1, "section": "S3",
                        "option_keys": list(choice["spellcasting_ability"]), "text": out[cid]["text"], "page": page}
        if choice.get("kind") == "feat":
            for name in picks.get(cid) or []:
                feat = next((f for f in d.choices["feats"] if f.get("name") == name), None)
                if _asks_spell_list(feat):
                    continue  # none of its picks is asked without its list
                for sub in (feat or {}).get("choices") or []:
                    sid = "%s.%s.%s" % (cid, _slug(name), _slug(sub["name"]))
                    out[sid] = _point_entry(sid, sub, cls, d, "S2")
    return out


def choice_problems(intent: Dict[str, Any], data: Optional[_Data] = None,
                    stood: Optional[Dict[str, List[Any]]] = None) -> List[Dict[str, Any]]:
    """The typed refusals of an intent's picks: an id the scope did not issue, an option it does not
    offer, a repeated option, or more picks than the point's count; then (#2095) a skill, tool or language another
    choice already holds; then Expertise in a skill the build does not hold (#2097). A later kind is judged only
    when no earlier one is left, so on the picks that stay. Empty when every pick is in scope.
    stood: the picks that stood before a reply; they win over newly sent ones, and the issued order breaks a tie."""
    d = data if data is not None else _Data()
    issued = issued_points(intent, d)
    problems = []
    for cid, picked in (intent.get("choices") or {}).items():
        point = issued.get(cid)
        if point is None:
            problems.append({"choice_id": cid, "problem": "not_issued"})
            continue
        picked = list(picked or [])
        unique = distinct(picked)
        if len(unique) < len(picked):
            problems.append({"choice_id": cid, "problem": "repeated",
                             "options": distinct(p for p in unique if picked.count(p) > 1)})
            picked = unique
        if len(picked) > point["count"]:
            problems.append({"choice_id": cid, "problem": "too_many", "count": point["count"], "picked": len(picked)})
        allowed = _allowed(point, intent, issued)
        if allowed is not None:
            outside = [p for p in picked if p not in allowed]
            if outside:
                problems.append({"choice_id": cid, "problem": "not_offered", "options": outside})
    return problems or _repeat_problems(intent, issued, d, stood or {}) or _expertise_problems(intent, issued, d)


def _repeat_problems(intent, issued, d, stood) -> List[Dict[str, Any]]:
    picks = intent.get("choices") or {}
    ruled = _elsewhere(intent, issued, d) if issued else {}
    order = {cid: n for n, cid in enumerate(issued)}

    def is_new(cid: str, pick: Any) -> bool:
        return pick not in (stood.get(cid) or [])

    def keeps(other: str, cid: str, pick: Any) -> bool:
        if is_new(other, pick) != is_new(cid, pick):
            return is_new(cid, pick)
        return other in ruled and order[other] < order[cid]  # one that may repeat takes nothing from another

    problems = []
    for cid, held in ruled.items():
        taken = {pick: [o for o in held.get(pick) or [] if keeps(o, cid, pick)] for pick in picks.get(cid) or []}
        lost = [pick for pick, by in taken.items() if by]
        if lost:
            problems.append({"choice_id": cid, "problem": "already_held", "options": lost,
                             "held_by": distinct(o for pick in lost for o in taken[pick])})
    return problems


def _expertise_problems(intent, issued, d) -> List[Dict[str, Any]]:
    picks = intent.get("choices") or {}
    problems = []
    for cid, point in issued.items():
        if point.get("kind") == "expertise" and picks.get(cid):
            missing = [p for p in picks[cid] if p not in _held_skills(intent, issued, d)]
            if missing:
                problems.append({"choice_id": cid, "problem": "skill_not_held", "options": missing})
    return problems


def _available(cid: str, intent: Dict[str, Any], issued: Dict[str, Dict[str, Any]], d: _Data) -> Optional[List[Any]]:
    """A choice's options that its pick would be accepted from now; all of them when too few would be left."""
    allowed = _allowed(issued[cid], intent, issued)
    if allowed is None:
        return None
    if issued[cid].get("kind") == "expertise":
        picks = intent.get("choices") or {}
        if any(len(distinct(picks.get(c))) < p["count"] for c, p in issued.items()
               if _is_proficiency(p, d) and any(k in allowed for k in p["option_keys"])):
            return allowed  # a skill can still be taken
        held = _held_skills(intent, issued, d)
        left = [k for k in allowed if k in held]
        return left if len(left) >= issued[cid]["count"] else allowed
    held = _elsewhere(intent, issued, d).get(cid) or {}
    return [k for k in allowed if k not in held]


# #2090: the ids an interview asks for that no choice id stands for, under the names the request already uses.
# Code constants, only for the log (an id not listed is logged as "other").
ASK_IDS = frozenset((
    "class", "class_key", "species", "species_key", "background", "background_key", "name", "alignment",
    "personality_traits", "ideals", "bonds", "flaws", "backstory", "appearance", "ability_scores",
    "ability_scores.method", "ability_scores.assignment", "background_package", "class_package",
    "starting_equipment.background_package", "starting_equipment.class_package"))


# The ids a claim may name an identity by, beside the schema's own keys (#2090 B3).
MENU_IDS = {"class": "class_key", "class_key": "class_key", "species": "species_key", "species_key": "species_key",
            "background": "background_key", "background_key": "background_key"}


def turn_problems(intent: Dict[str, Any], choice_turn: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The typed contradictions of a response's choice_turn with the intent it leaves (#1325): a refusal under an
    id the scope did not issue or of an option the scope offers, and a question about an issued choice that is
    already full. A refusal under a menu id is a contradiction only when its value is one of that menu's keys and the
    build has none yet (keys only: a name is the author's own words, D-KW-12). A choice the player changes is reopened by sending its id with [], then asked. An ask that names
    no issued choice id (a class, a name, the gear) is a question and never a contradiction: such an id cannot be
    cleared, so refusing it would leave no way to ask (D-CREATE-FLEX-3)."""
    d = _Data()
    issued = issued_points(intent, d)
    picks = intent.get("choices") or {}
    problems = []
    for item in choice_turn.get("refused") or []:
        point = issued.get(item["choice_id"])
        if point is None and item["choice_id"] in MENU_IDS:
            key = MENU_IDS[item["choice_id"]]
            menu = {"class_key": d.classes, "species_key": d.species, "background_key": d.backgrounds}[key]()
            if intent.get(key) is None and item["value"] in menu:
                problems.append({"choice_id": item["choice_id"], "problem": "refused_offered", "value": item["value"]})
            continue
        if point is None:
            problems.append({"choice_id": item["choice_id"], "problem": "refused_not_issued"})
            continue
        allowed = _available(item["choice_id"], intent, issued, d)
        if allowed is not None and item["value"] in allowed:  # a free pick has no list to contradict
            problems.append({"choice_id": item["choice_id"], "problem": "refused_offered", "value": item["value"]})
    for cid in choice_turn.get("asks") or []:
        held = distinct(picks.get(cid))
        if cid in issued and len(held) >= issued[cid]["count"]:
            problems.append({"choice_id": cid, "problem": "asked_not_open", "held": held})
    return problems


def _allowed(point: Dict[str, Any], intent: Dict[str, Any], issued: Dict[str, Dict[str, Any]]) -> Optional[List[str]]:
    if point.get("free_pick"):
        return None
    if point.get("from_spellbook"):
        return list((intent.get("choices") or {}).get(point.get("from_choice")) or [])
    return point.get("option_keys") or []


def open_choice_ids(intent: Dict[str, Any], data: Optional[_Data] = None) -> List[str]:
    """The issued ids whose picks are still short of their count."""
    picks = intent.get("choices") or {}
    return [cid for cid, point in issued_points(intent, data).items() if len(distinct(picks.get(cid))) < point["count"]]


def open_choices(intent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Each open choice with its name, count and option names, from the issued points (desktop L5 turns 5
    and 9: the author asked for a choice without its options, which sat in a scope item turns back). A
    package choice lists each package's items and gold; a free pick names its option source."""
    picks = intent.get("choices") or {}
    d = _Data()
    points = issued_points(intent, d)

    def names(point: Dict[str, Any], keys: List[str]) -> List[str]:
        # A spell option row carries its key and name; the player sees names (#1275).
        named = {o["key"]: o.get("name") or o["key"] for o in point.get("options") or []
                 if isinstance(o, dict) and "key" in o} if isinstance(point.get("options"), list) else {}
        return [named.get(k, k) for k in keys]

    out = []
    for cid, point in points.items():
        if len(distinct(picks.get(cid))) >= point["count"]:
            continue
        entry = {"id": cid, "name": point.get("name"), "count": point["count"],
                 "chosen": list(picks.get(cid) or [])}
        source = points.get(point.get("from_choice") or "")
        if source is not None:
            # Prepared from another pick (a wizard prepares from the spellbook): its options are that
            # choice's picks so far, and the pointer says so.
            entry["from_choice"] = point["from_choice"]
            entry["options"] = names(source, list(picks.get(point["from_choice"]) or []))
        elif isinstance(point.get("options"), dict):
            entry["packages"] = _packages(point["options"], d)
        elif isinstance(point.get("option_keys"), list):
            entry["options"] = names(point, _available(cid, intent, points, d))
        elif point.get("free_pick"):
            entry["free_pick"] = point.get("option_source") or True
        out.append(entry)
    return out


# --- the scope item ---

def _background_tools(background: Dict[str, Any]) -> Dict[str, Any]:
    """A background's tool, typed (dplay-AC-difficult turn 6): the fixed tool keys, or the tool choice's name
    and option source."""
    choice = background.get("tool_choice")
    if isinstance(choice, dict):
        return {"choose": {"name": choice.get("name"), "option_source": choice.get("option_source")}}
    return {"granted": list(background.get("tool_keys") or [])}


def _package_summary(background: Dict[str, Any], d: _Data) -> Dict[str, Any]:
    """A background's starting-equipment options, typed: each option's items (catalog name or uncatalogued
    name, with quantity) and its gold (dplay-AC-difficult turn 6)."""
    return _packages(background.get("equipment_options") or {}, d)


def _item_name(item: Any, d: _Data) -> str:
    """A choose_one entry's name: a catalog id, or an item row (catalog id or uncatalogued name)."""
    if isinstance(item, dict):
        return str(d.catalog.get(item.get("catalog_id")) or item.get("uncatalogued") or item.get("catalog_id"))
    return str(d.catalog.get(item, item))


def _packages(options: Dict[str, Any], d: _Data) -> Dict[str, Any]:
    out = {}
    for key, option in options.items():
        items = []
        for item in option.get("items") or []:
            name = d.catalog.get(item.get("catalog_id")) or item.get("uncatalogued") or item.get("slot")
            if isinstance(item.get("choose_one"), list):
                name = "one of: %s" % ", ".join(_item_name(i, d) for i in item["choose_one"])
            items.append({"name": name, "quantity": item.get("quantity", 1)})
        out[key] = {"items": items, "gp": (option.get("coins") or {}).get("gp", 0)}
    return out


def _menu(d: _Data, *, classes: bool, species: bool, backgrounds: bool) -> Dict[str, Any]:
    menu: Dict[str, Any] = {}
    if classes:
        rows = []
        for key in sorted(d.classes()):
            traits = d.choices["class_traits"][key]
            prog = (d.progression.get("classes") or {}).get(key) or {}
            primary = traits.get("primary_ability") or {}
            abilities = " or ".join(primary.get("any_of") or []) or " and ".join(primary.get("all_of") or [])
            armor = ", ".join(traits.get("armor_training") or []) or "none"
            rows.append({"class_key": key, "name": key.capitalize(),
                         "line": "primary %s; hit die %s; armor training %s; %s" % (
                             abilities, prog.get("hit_die"), armor,
                             "%s caster" % prog["caster_kind"] if prog.get("caster_kind") not in (None, "none")
                             else "no spellcasting")})
        menu["classes"] = rows
    if species:
        menu["species"] = [{"species_key": k, "name": s["name"], "line": "%s; speed %s" % (s.get("size"), s.get("speed"))}
                           for k, s in sorted(d.species().items())]
    if backgrounds:
        menu["backgrounds"] = [{"background_key": k, "name": b["name"],
                                "line": "ability scores %s; feat %s; skills %s" % (
                                    b.get("ability_scores"), b.get("feat"), b.get("skill_proficiencies")),
                                "tools": _background_tools(b), "equipment": _package_summary(b, d)}
                               for k, b in sorted(d.backgrounds().items())]
    return menu


def _class_facts(cls: str, d: _Data) -> Dict[str, Any]:
    traits = d.choices["class_traits"][cls]
    prog = (d.progression.get("classes") or {}).get(cls) or {}
    facts: Dict[str, Any] = {"class_key": cls, "name": cls.capitalize()}
    for key in ("primary_ability", "saving_throws", "armor_training", "weapon_proficiencies",
                "spellcasting_ability", "tool_proficiencies"):
        if key in traits:
            facts[key] = traits[key]
    for key in ("hit_die", "hp_at_first_level", "hp_at_first_level_base", "caster_kind"):
        if key in prog:
            facts[key] = prog[key]
    for key in ("spell_slots_by_level", "pact_slots_by_level", "cantrips_known_by_level", "prepared_spells_by_level"):
        if isinstance(prog.get(key), dict) and prog[key].get("1") is not None:
            facts[key.replace("_by_level", "_at_level_1")] = prog[key]["1"]
    facts["proficiency_bonus_at_level_1"] = (d.progression.get("proficiency_bonus") or {}).get("1")
    facts.update(level_1_features(prog))
    orders = [o for o in d.origins.get("class_order_options") or [] if str(o.get("class")).lower() == cls]
    if orders:
        facts["order_options"] = orders
    facts["always_prepared"] = [a for a in d.choices.get("always_prepared") or []
                                if (a.get("granted_by") or {}).get("class") == cls]
    return facts


def _species_facts(key: str, d: _Data) -> Dict[str, Any]:
    entry = dict(d.species()[key])
    if isinstance(entry.get("grants"), dict):
        # Creation is level 1: the grants above it (#1292, read at level-up) stay out of the scope.
        grants = {k: v for k, v in entry["grants"].items() if k != "traits_by_level"}
        grants["choices"] = [dict(c, options=[{k: v for k, v in o.items() if k not in ("spells_by_level", "spells_by_level_cite")}
                                              for o in c["options"]]) if isinstance(c.get("options"), list) else c
                             for c in grants.get("choices") or []]
        if "choices" not in entry["grants"]:
            del grants["choices"]
        entry["grants"] = grants
    bonuses = [b for b in d.progression.get("hp_bonuses") or []
               if (b.get("granted_by") or {}).get("species_key") == key]
    if bonuses:
        entry["hp_bonuses"] = bonuses
    lineage = [a for a in d.choices.get("always_prepared") or []
               if (a.get("granted_by") or {}).get("species_key") == key]
    if lineage:
        entry["always_prepared"] = lineage
    return entry


def _background_facts(key: str, d: _Data) -> Dict[str, Any]:
    entry = dict(d.backgrounds()[key])
    if isinstance(entry.get("equipment_options"), dict):
        entry["equipment_options"] = typed_options(entry["equipment_options"], d.catalog, flags=True)
    feat_key = (entry.get("feat_ref") or {}).get("feat_key")
    feat = [f for f in d.origins.get("origin_feats") or [] if f.get("key") == feat_key]
    if feat:
        entry["origin_feat"] = feat[0]
    return entry


def _common(cls: Optional[str], d: _Data) -> Dict[str, Any]:
    points = [p for p in d.classes()[cls].get("1", []) if p.get("applies") != "multiclass"] if cls in d.classes() else []
    # Weapon Mastery's options are the weapons reference form; Fighting Style is its own kind.
    mastery = any(str(p.get("option_source") or "").split(":", 1)[0] == "weapons" for p in points)
    styles = any(p.get("kind") == "fighting_style" for p in points)
    common: Dict[str, Any] = {
        "sheet_representation": SHEET_REPRESENTATION,
        "background_ability_scores_rule": d.origins["background_ability_scores_rule"],
        "ability_score_methods": d.origins.get("ability_score_methods"),
        "languages": {"rule": d.origins["languages_rule"], "standard": d.choices["languages"]["standard"],
                      "rare": d.choices["languages"]["rare"]},
        "cantrip_rule": d.origins["cantrip_rule"],
        # Each armor's description opens with its category ("Medium armor. ...").
        "armor": [{"name": e["name"], "description": e["description"]} for e in d.items
                  if e.get("kind") == "armor" and not e.get("magical")],
    }
    weapons = [e for e in d.items if e.get("kind") == "weapon" and not e.get("magical")]
    if mastery:
        common["weapons"] = [{"name": e["name"], "description": e["description"]} for e in weapons]
        common["weapon_mastery_rule"] = d.origins["weapon_mastery_rule"]
        common["weapon_mastery_properties"] = d.origins["weapon_mastery_properties"]
    else:
        listed = set()
        packages = [p.get("option_items") for p in d.classes()[cls].get("1", [])] if cls in d.classes() else []
        packages += [b.get("equipment_options") for b in d.origins["backgrounds"]]
        for options in packages:
            for option in (options or {}).values():
                for item in option.get("items") or []:
                    listed.update([item.get("catalog_id")] + list(item.get("choose_one") or []))
        common["weapons"] = [{"name": e["name"], "description": e["description"]} for e in weapons
                             if e["id"] in listed]
    if styles:
        common["fighting_style_feats"] = d.origins["fighting_style_feats"]
    return common


def _use_text(scope: Dict[str, Any]) -> str:
    parts = []
    if "menu" in scope:
        parts.append("a menu of the %s not yet chosen, one line each" % " and ".join(
            {"classes": "classes", "species": "species", "backgrounds": "backgrounds"}[k] for k in scope["menu"]))
    if "class" in scope:
        parts.append("the chosen class's saving throws, armor and weapon training, hit die and level-1 hit points, "
                     "spellcasting ability, fixed level-1 features and class-table values, order options and "
                     "always-prepared spells")
    if "species" in scope:
        parts.append("the chosen species' traits")
    if "background" in scope:
        parts.append("the chosen background, its Origin feat and its typed equipment options")
    if scope.get("choices"):
        parts.append("every open level-1 choice under its choice id, with its count and typed options "
                     "(spells by spell-repository key)")
    if "considering" in scope:
        parts.append("the facts of the options the player is considering")
    parts.append("the sheet representation, the ability score methods and background rule, the languages, "
                 "the cantrip rule, the armor table and the weapons that apply")
    return ("This is the engine's SRD 5.2.1 creation scope for the player's current choices: " + "; ".join(parts)
            + ". Use these facts instead of remembered rules. A fact of these kinds that is absent here is not "
              "part of this character's options; for anything else, your general knowledge of the game applies. "
              "Record the player's choices in intent, picking options by the keys given here.")


def creation_scope(intent: Optional[Dict[str, Any]], data: Optional[_Data] = None) -> Optional[Dict[str, Any]]:
    """The scope item for a typed intent, or None when a data file cannot be read."""
    d = data if data is not None else _Data()
    if not d.ok:
        return None
    intent = intent or {}
    cls = intent.get("class_key") if intent.get("class_key") in d.classes() else None
    sp = intent.get("species_key") if intent.get("species_key") in d.species() else None
    bg = intent.get("background_key") if intent.get("background_key") in d.backgrounds() else None
    scope: Dict[str, Any] = {"task_purpose": SCOPE_PURPOSE, "ruleset": "SRD 5.2.1",
                             "attribution": d.choices["sources"]["attribution"],
                             "intent": {"class_key": cls, "species_key": sp, "background_key": bg}}
    if not (cls and sp and bg):
        scope["menu"] = _menu(d, classes=not cls, species=not sp, backgrounds=not bg)
    if cls:
        scope["class"] = _class_facts(cls, d)
    if sp:
        scope["species"] = _species_facts(sp, d)
    if bg:
        scope["background"] = _background_facts(bg, d)
    issued = issued_points(intent, d)
    if issued:
        scope["choices"] = list(issued.values())
    considering = intent.get("considering") or {}
    looked = {}
    for k in considering.get("class_keys") or []:
        if k in d.classes() and k != cls:
            looked.setdefault("classes", []).append(_class_facts(k, d))
    for k in considering.get("species_keys") or []:
        if k in d.species() and k != sp:
            looked.setdefault("species", []).append(_species_facts(k, d))
    for k in considering.get("background_keys") or []:
        if k in d.backgrounds() and k != bg:
            looked.setdefault("backgrounds", []).append(_background_facts(k, d))
    if looked:
        scope["considering"] = looked
    scope["common"] = _common(cls, d)
    scope["use"] = _use_text(scope)
    scope["scope_id"] = scope_id(scope)
    return scope


def scope_id(scope: Dict[str, Any]) -> str:
    """The scope's identity: sha256 of its canonical JSON without the id, first 16 hex digits."""
    body = {k: v for k, v in scope.items() if k != "scope_id"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _slot_ids(value) -> List[str]:
    """Every package slot id (a holy symbol's form, a gaming set) under one scope value."""
    if isinstance(value, dict):
        found = [value["slot"]] if isinstance(value.get("slot"), str) else []
        for child in value.values():
            found.extend(_slot_ids(child))
        return found
    if isinstance(value, list):
        return [slot for child in value for slot in _slot_ids(child)]
    return []


def unanswered_required(scope: Dict[str, Any], intent: Dict[str, Any], starting_equipment=None) -> List[Dict[str, Any]]:
    """What a finalize still needs that no choice id stands for (C4-switch-r2): the ability score method and
    assignment while intent lacks them, the background's package, and every slot of a chosen (or not yet
    chosen) package. A starting_equipment the author records as the player gives picks (D-CREATE-COST-5
    amendment 2) answers what it already holds. Typed entries only; a finalize refuses while a starting_equipment
    entry remains (D-ALLCLASS-4: the engine is the only gate). A slot entry names the choice id of the package that holds it (D-ALLCLASS-2): a class package
    pick is intent, only its slot is starting_equipment; a background slot has no package choice id (None)."""
    missing = []
    scores = (intent or {}).get("ability_scores") or {}
    for key in ("method", "assignment"):
        if not scores.get(key):
            missing.append({"id": "ability_scores." + key})
    equipment = starting_equipment if isinstance(starting_equipment, dict) else {}
    picked = {pick.get("slot") for pick in equipment.get("slot_picks") or [] if isinstance(pick, dict)}
    if (scope.get("background") or {}).get("equipment_options") and not equipment.get("background_package"):
        missing.append({"id": "starting_equipment.background_package"})
    slots = {slot: None for slot in _slot_ids({k: scope.get(k) for k in ("class", "background")})}
    for choice in scope.get("choices") or []:
        for slot in _slot_ids(choice):
            slots[slot] = choice.get("id")
    choices = (intent or {}).get("choices") or {}
    for slot in sorted(slots):
        package = slots[slot]
        # A slot id is <owner>.<package key>.<slot>; a slot of a package not chosen is not needed.
        chosen = (choices.get(package) or [None])[0] if package else equipment.get("background_package")
        if slot in picked or (chosen and slot.split(".")[1] != chosen):
            continue
        missing.append({"id": "starting_equipment.slot:" + slot, "package_choice_id": package})
    return missing
