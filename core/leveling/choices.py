# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Choice points and their option lists from SRD data (L1).

``data/srd/choices.json`` (parsed from the SRD 5.2.1 PDF, machine-checked) lists,
per class and level, every choice the rules open: its kind, the feature that grants
it, how many picks, and where the options come from (a name list or a reference
such as ``feats:qualified`` or ``spells:class=cleric,max_level=3``). This module
resolves those references against the character sheet, the feats table and the
spell repository, so the level-up agent only ever chooses among options the
rules list, and code can check every answer. No prose is read, no model is called.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core.leveling import tables

_DATA = os.path.join(os.path.dirname(tables._DATA), "choices.json")
_CHOICES: Optional[Dict[str, Any]] = None
_SPELLS: Optional[Dict[str, Dict[str, Any]]] = None

# Kinds whose count in the data is an increment; the host asks for the full list
# sized by the class table instead (see tables.choice_points).
TABLE_SIZED_KINDS = ("cantrip", "prepared_spells")


def data() -> Dict[str, Any]:
    global _CHOICES
    if _CHOICES is None:
        with open(_DATA, "r", encoding="utf-8") as handle:
            _CHOICES = json.load(handle)
    return _CHOICES


def spells() -> Dict[str, Dict[str, Any]]:
    """The spell repository keyed by lower-case name and alias."""
    global _SPELLS
    if _SPELLS is None:
        path = os.path.join(os.path.dirname(os.path.dirname(tables._DATA)), "spell_repository.json")
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        out: Dict[str, Dict[str, Any]] = {}
        for key, entry in raw.items():
            if key == "_metadata" or not isinstance(entry, dict) or not entry.get("name"):
                continue
            out[str(entry["name"]).strip().lower()] = entry
            for alias in entry.get("aliases") or []:
                out[str(alias).strip().lower()] = entry
        return_value = out
        _SPELLS = return_value
    return _SPELLS


def spell(name: str) -> Optional[Dict[str, Any]]:
    return spells().get(str(name).strip().lower())


def _names(rows: Any, key: str = "name") -> List[str]:
    return [str(r[key]) for r in rows or [] if isinstance(r, dict) and r.get(key)]


def _held_feature_names(sheet: Dict[str, Any]) -> set:
    return {tables._feature_key(f) for f in sheet.get("classFeatures") or [] if isinstance(f, dict)}


def _held_feats(sheet: Dict[str, Any]) -> List[str]:
    out = []
    for feat in sheet.get("feats") or []:
        out.append(str(feat.get("name") if isinstance(feat, dict) else feat))
    return out


def _skill_multipliers(sheet: Dict[str, Any]) -> Dict[str, int]:
    """{skill key: 0, 1 or 2}. A dict of stored bonuses is read back as proficiency
    times; a list names the proficient skills, and the typed expertise field marks
    expertise (#769)."""
    if isinstance(sheet.get("skills"), list):
        from core.nql import stats
        times: Dict[str, int] = {}
        for name in sheet["skills"]:
            sid = stats.skill_id(name)
            if sid:
                times[sid.replace("-", "_")] = 1
        for sid in stats.expertise_of(sheet)[0]:
            times[sid.replace("-", "_")] = 2
        return times
    pb = sheet.get("proficiencyBonus") if type(sheet.get("proficiencyBonus")) is int else tables.proficiency_bonus(sheet.get("level", 1))
    out: Dict[str, int] = {}
    for skill, bonus in (sheet.get("skills") or {}).items():
        ability = tables.SKILL_ABILITY.get(str(skill).lower())
        if ability is None or type(bonus) is not int or pb == 0:
            continue
        mod = tables.modifier((sheet.get("abilities") or {}).get(ability))
        out[str(skill).lower()] = max(0, min(2, round((bonus - mod) / pb)))
    return out


def _skill_key(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_")


def feat_qualifies(sheet: Dict[str, Any], feat: Dict[str, Any], new_level: int) -> bool:
    pre = feat.get("prerequisite") or {}
    if pre.get("level") and new_level < int(pre["level"]):
        return False
    if pre.get("feature") and tables._feature_key(pre["feature"]) not in _held_feature_names(sheet):
        return False
    if pre.get("ability_minimum") and pre.get("ability_any_of"):
        scores = sheet.get("abilities") or {}
        if not any(type(scores.get(str(a).lower())) is int and scores[str(a).lower()] >= int(pre["ability_minimum"])
                   for a in pre["ability_any_of"]):
            return False
    if not feat.get("repeatable") and feat.get("name") in _held_feats(sheet):
        return False
    return True


def resolve_options(source: Any, sheet: Dict[str, Any], cls: str, new_level: int,
                    filters: Optional[List[str]] = None) -> Optional[List[str]]:
    """The option names for a choice point, or None when the host has no list (free pick)."""
    filters = filters or []
    if isinstance(source, str) and " | " in source:
        # A union of forms ("skills:all | tools:all"): its options are every part's, or a free pick when
        # any part has no list.
        parts = [resolve_options(part.strip(), sheet, cls, new_level) for part in source.split(" | ")]
        if any(part is None for part in parts):
            return None
        return _apply_filters([n for part in parts for n in part], filters, sheet)
    if isinstance(source, list):
        names = [str(x) for x in source]
    elif not isinstance(source, str):
        return None
    else:
        head, _, rest = source.partition(":")
        args = dict(kv.split("=", 1) for kv in rest.split(",") if "=" in kv) if rest else {}
        flags = {kv for kv in rest.split(",") if "=" not in kv and kv}
        if head == "feats":
            if args.get("category"):
                names = [f["name"] for f in data()["feats"] if f.get("category") == args["category"]]
            elif "qualified" in flags:
                names = [f["name"] for f in data()["feats"] if feat_qualifies(sheet, f, new_level)]
            else:
                return None
        elif head == "subclasses":
            names = tables.subclass_options(args.get("class", cls))
        elif head == "skills":
            names = _names(data()["skills_and_abilities"]["skills"])
        elif head == "languages":
            lang = data().get("languages") or {}
            names = list(lang.get("standard") or []) + list(lang.get("rare") or [])
            names = [n["name"] if isinstance(n, dict) else str(n) for n in names]
        elif head == "invocations":
            names = [i["name"] for i in data().get("invocations") or []
                     if not ((i.get("prerequisite") or {}).get("level") and new_level < int(i["prerequisite"]["level"]))]
        elif head == "metamagic":
            names = _names(data().get("metamagic"))
        elif head == "damage_types":
            names = [d["name"] if isinstance(d, dict) else str(d) for d in data().get("damage_types") or []]
            names = [n for n in names if n != args.get("except")]
        elif head == "spells":
            names = _spell_options(args, flags, sheet, cls, new_level)
        elif head == "weapons":
            # No SRD weapon table on the host yet: offer the weapons the sheet
            # carries as the list, and accept any other named weapon (free pick).
            names = sorted({str(e.get("item_name")) for e in sheet.get("equipment") or []
                            if isinstance(e, dict) and e.get("item_type") == "weapon" and e.get("item_name")})
            return _apply_filters(names, filters, sheet) or None
        elif head == "tools" and isinstance(data().get("tools"), dict):
            # The SRD tool table (pp. 93-94): tools:all, or tools:category=<category>.
            names = [t["name"] for t in data()["tools"].get("entries") or []
                     if not args.get("category") or t.get("category") == args["category"]]
        else:
            return None   # beasts: the agent picks, code accepts a name
    return _apply_filters(names, filters, sheet)


def free_pick(source: Any) -> bool:
    """True when the host cannot enumerate the options, so any named pick is accepted."""
    if isinstance(source, str) and " | " in source:
        return any(free_pick(part.strip()) for part in source.split(" | "))
    head = source.split(":", 1)[0] if isinstance(source, str) else None
    return head in ("weapons", "beasts") or (head == "tools" and not isinstance(data().get("tools"), dict))


def _spell_options(args: Dict[str, str], flags: set, sheet: Dict[str, Any], cls: str, new_level: int) -> List[str]:
    classes = [c.strip().lower() for c in (args.get("class") or cls).split("+")] if "spellbook" not in flags else []
    if "spellbook" in flags:
        casting = sheet.get("spellcasting") if isinstance(sheet.get("spellcasting"), dict) else {}
        known = [n for k, v in (casting.get("spells") or {}).items() if k != "cantrips" for n in (v or [])]
        pool = [spell(n) for n in known]
        pool = [p for p in pool if p]
    else:
        pool = list({id(e): e for e in spells().values()}.values())
    lo = int(args["level"]) if "level" in args else int(args.get("min_level", 1))
    hi = int(args["level"]) if "level" in args else int(args.get("max_level", 9))
    out = set()
    for entry in pool:
        lvl = int(entry.get("level", -1))
        if not lo <= lvl <= hi:
            continue
        if classes and "any" not in classes and not any(c.capitalize() in (entry.get("classes") or []) for c in classes):
            continue
        if args.get("school") and str(entry.get("school", "")).lower() != args["school"].lower():
            continue
        if args.get("ritual") == "yes" and not entry.get("ritual"):
            continue
        out.add(str(entry["name"]))
    return sorted(out)


def _apply_filters(names: List[str], filters: List[str], sheet: Dict[str, Any]) -> List[str]:
    if not filters:
        return names
    mult = _skill_multipliers(sheet)
    held = {tables._feature_key(n) for n in _held_feats(sheet)} | _held_feature_names(sheet)
    out = []
    for name in names:
        key = _skill_key(name)
        if "proficient" in filters and mult.get(key, 0) < 1:
            continue
        if "no_expertise" in filters and mult.get(key, 0) >= 2:
            continue
        if "not_proficient" in filters and mult.get(key, 0) >= 1:
            continue
        if "not_known" in filters and tables._feature_key(name) in held:
            continue
        out.append(name)
    return out


def feat_rule(name: Any) -> Optional[Dict[str, Any]]:
    """A feat's typed ability_score_increase from the SRD feats data, or None (#424)."""
    for feat in data().get("feats") or []:
        if feat.get("name") == name and isinstance(feat.get("ability_score_increase"), dict):
            return feat["ability_score_increase"]
    return None


def apply_feat_increase(abilities: Dict[str, Any], rule: Dict[str, Any], increases: Any,
                        name: str) -> Tuple[Dict[str, Any], str]:
    """(new abilities, reason if refused): the increase the feat's rule allows (#424)."""
    allowed = {str(a).lower() for a in rule.get("abilities") or []}
    shapes = [sorted(int(n) for n in shape) for shape in rule.get("increase_options") or []]
    cap = int(rule.get("maximum") or tables.ABILITY_CAP)
    need = (f"{name} also raises an ability ({', '.join(rule.get('abilities') or [])}; "
            f"{' or '.join('+' + ' and +'.join(str(n) for n in s) for s in shapes)}; max {cap}): answer "
            f'{{"feat": "{name}", "asi": {{"<ability>": n}}}}')
    if not isinstance(increases, dict) or not increases \
            or any(type(v) is not int for v in increases.values()) or sorted(increases.values()) not in shapes:
        return abilities, need
    out = dict(abilities)
    for key, inc in increases.items():
        key = str(key).lower()
        if key not in allowed or type(out.get(key)) is not int:
            return abilities, need
        if out[key] + inc > cap:
            return abilities, f"{key} cannot rise above {cap}"
        out[key] += inc
    return out, ""


def data_choice_points(sheet: Dict[str, Any], cls: str, new_level: int) -> List[Dict[str, Any]]:
    """Typed choice points for this level from the SRD data, options resolved."""
    entries = ((data().get("choice_points") or {}).get(cls) or {}).get(str(new_level)) or []
    points: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    for entry in entries:
        if entry.get("applies") == "multiclass" or entry.get("kind") in TABLE_SIZED_KINDS:
            continue
        if entry.get("subclass") and entry["subclass"] != tables.infer_subclass(sheet, cls):
            continue
        base = re.sub(r"[^a-z0-9]+", "_", str(entry.get("name") or entry["kind"]).lower()).strip("_")
        seen[base] = seen.get(base, 0) + 1
        cid = base if seen[base] == 1 else f"{base}_{seen[base]}"
        options = resolve_options(entry.get("option_source"), sheet, cls, new_level, entry.get("filters"))
        point = {
            "id": cid, "kind": entry["kind"], "name": entry.get("name"), "feature": entry.get("feature"),
            "count": int(entry.get("count") or 1), "options": options,
            "prompt": str(entry.get("evidence") or entry.get("name") or ""),
        }
        if free_pick(entry.get("option_source")):
            point["free_pick"] = True
            point["prompt"] += " (Options listed are what the character carries; any other suitable named choice is accepted.)"
        for key in ("named_option", "recommended", "alternatives", "then", "table_column"):
            if entry.get(key) is not None:
                point[key] = entry[key]
        if entry["kind"] == "asi_or_feat":
            point["abilities"] = dict(sheet.get("abilities") or {})
            point["cap"] = tables.ABILITY_CAP
        points.append(point)
    return points


def order_choice_points(sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The sheet's class choice points at or below its level whose options carry
    typed grants (``option_grants``: Divine Order, Primal Order; #888); [] for an
    unknown class or level."""
    cls = tables.class_key(sheet)
    level = sheet.get("level")
    if cls is None or type(level) is not int:
        return []
    by_level = (data().get("choice_points") or {}).get(cls) or {}
    return [point for n in range(1, level + 1) for point in by_level.get(str(n)) or []
            if isinstance(point, dict) and point.get("name") and isinstance(point.get("option_grants"), dict)
            and isinstance(point.get("option_source"), list)]


def order_options_recorded(sheet: Dict[str, Any], point: Dict[str, Any]) -> List[str]:
    """The options of ``point`` the sheet records by the exact classFeatures name
    "<choice>: <option>" ("Divine Order: Protector"), the form level-up writes."""
    exact = {f"{point['name']}: {option}": option for option in point["option_source"]}
    return [exact[entry["name"]] for entry in sheet.get("classFeatures") or []
            if isinstance(entry, dict) and entry.get("name") in exact]


def order_choice_count(point: Dict[str, Any]) -> int:
    return point["count"] if type(point.get("count")) is int else 1


def _engine_reading(field: str, label: Any) -> set:
    """What the rules engine reads from one proficiency label: armor training
    conditions (core.nql.genesis) or a weapon category (core.nql.class_conditions).
    A label the engine does not know reads as itself."""
    from core.nql.class_conditions import WEAPON_CATEGORIES
    from core.nql.genesis import _ARMOR_TRAINING
    key = str(label).strip().lower()
    if field == "armor":
        return set(_ARMOR_TRAINING.get(key, ())) or {key}
    return {WEAPON_CATEGORIES.get(key, key)}


def apply_order_grants(sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Write the proficiencies a recorded class order grants, in place (#888):
    Divine Order: Protector adds Heavy armor training and Martial weapons, Primal
    Order: Warden adds Medium armor training and Martial weapons. Labels are
    written in the short form the rules engine reads; one whose reading the sheet
    already has (any label, e.g. "Heavy armor") is not added again. Matched by the
    exact classFeatures name only, never by text. Returns one entry per order
    applied: its feature, choice, option, printed grant, SRD page and the labels
    added ([] when all were present)."""
    applied = []
    for point in order_choice_points(sheet):
        chosen = order_options_recorded(sheet, point)
        if len(chosen) != order_choice_count(point):
            continue
        for option in chosen:
            grant = point["option_grants"].get(option)
            if not isinstance(grant, dict):
                continue
            if not isinstance(sheet.get("proficiencies"), dict):
                sheet["proficiencies"] = {}
            proficiencies = sheet["proficiencies"]
            added = []
            for field, labels in (
                    ("armor", [str(a).capitalize() for a in grant.get("armor_training") or []]),
                    ("weapons", [w["category"] for w in grant.get("weapon_proficiencies") or []
                                 if isinstance(w, dict) and w.get("category")])):
                have = proficiencies.get(field) if isinstance(proficiencies.get(field), list) else []
                reads = set()
                for label in have:
                    reads |= _engine_reading(field, label)
                for label in labels:
                    reading = _engine_reading(field, label)
                    if not reading <= reads:
                        have.append(label)
                        reads |= reading
                        added.append(label)
                proficiencies[field] = have
            name = f"{point['name']}: {option}"
            feature = next(e for e in sheet["classFeatures"] if isinstance(e, dict) and e.get("name") == name)
            bare = f"You chose the {option} {point['name']}."
            if not str(feature.get("description") or "").strip() or feature.get("description") == bare:
                feature["description"] = f"You chose the {option} {point['name']}: {grant.get('printed')}."
            applied.append({"feature": name, "choice": point["name"], "option": option,
                            "printed": grant.get("printed"), "page": (grant.get("source") or {}).get("page"),
                            "added": added})
    return applied


def check_pick(point: Dict[str, Any], value: Any, sheet: Dict[str, Any], cls: str, new_level: int) -> Tuple[bool, str]:
    """Validate an agent's answer for a data-driven choice point."""
    kind = point["kind"]
    options = point.get("options")
    if kind == "asi_or_feat" or kind == "epic_boon":
        if isinstance(value, dict) and isinstance(value.get("asi"), dict) and not value.get("feat"):
            if kind == "epic_boon":
                return False, "an Epic Boon is a feat, name it"
            _, why = tables.apply_asi(dict(sheet.get("abilities") or {}), value["asi"])
            return (False, why) if why else (True, "")
        name = value.get("feat") if isinstance(value, dict) else value
        if not isinstance(name, str) or not name.strip():
            return False, "give {asi: {ability: +n}} or {feat: name}"
        if options is not None and name not in options:
            return False, f"{name!r} is not a feat this character qualifies for; options: {options}"
        rule = feat_rule(name)
        if rule is not None:
            _, why = apply_feat_increase(dict(sheet.get("abilities") or {}), rule,
                                         value.get("asi") if isinstance(value, dict) else None, name)
            if why:
                return False, why
        return True, ""
    if kind == "subclass":
        if not isinstance(value, str) or (options and value not in options):
            return False, f"subclass must be one of {options}"
        return True, ""
    # list kinds: fighting_style, expertise, skill, other_named
    picks = value if isinstance(value, list) else [value]
    if not all(isinstance(p, str) and p.strip() for p in picks):
        return False, f"{point['id']} must be a name or a list of names"
    if len(picks) != int(point.get("count") or 1):
        return False, f"{point['id']} needs exactly {point.get('count')} pick(s)"
    if len(set(p.lower() for p in picks)) != len(picks):
        return False, "an option is listed twice"
    if options is not None and not point.get("free_pick"):
        for p in picks:
            if p not in options:
                return False, f"{p!r} is not one of the options for {point['id']}: {options}"
    return True, ""


# --- species damage resistances (#1280) ---

_ORIGINS: Optional[Dict[str, Any]] = None


def _origins() -> Dict[str, Any]:
    global _ORIGINS
    if _ORIGINS is None:
        path = os.path.join(os.path.dirname(os.path.dirname(tables._DATA)), "srd_character_origins.json")
        with open(path, "r", encoding="utf-8") as handle:
            _ORIGINS = json.load(handle)
    return _ORIGINS


def _resistance_options(entry: Dict[str, Any]) -> List[Tuple[Optional[str], List[str]]]:
    """[(option, damage types)] of one species_damage_resistances entry; options_from reads the species table."""
    spec = entry.get("options_from")
    if not spec:
        return [(entry.get("option"), list(entry.get("damage_resistances") or []))]
    species = next((s for s in _origins().get("species") or [] if s.get("key") == entry.get("species_key")), {})
    table = next((t for t in species.get("tables") or [] if t.get("title") == spec.get("table")), None)
    if table is None:
        return []
    oi, ri = table["columns"].index(spec["option_column"]), table["columns"].index(spec["resistance_column"])
    return [(row[oi], [row[ri]]) for row in table["rows"]]


def species_damage_resistances(intent: Any) -> List[Dict[str, Any]]:
    """The species' damage resistance grants for a creation intent {species_key, choices}: the unconditional
    ones, and the ones of the options picked under their typed choice id. Reads only the table and the intent."""
    intent = intent if isinstance(intent, dict) else {}
    key, picks = intent.get("species_key"), intent.get("choices") or {}
    out = []
    for entry in data().get("species_damage_resistances") or []:
        if entry.get("species_key") != key:
            continue
        if not entry.get("choice_id"):
            out.append({"source": entry.get("trait"), "choice_id": None, "option": None,
                        "damage_resistances": list(entry.get("damage_resistances") or [])})
            continue
        chosen = picks.get(entry["choice_id"]) or []
        for option, kinds in _resistance_options(entry):
            if option in chosen:
                out.append({"source": "%s: %s" % (entry.get("choice"), option), "choice_id": entry["choice_id"],
                            "option": option, "damage_resistances": kinds})
    return out


def species_key_for(sheet: Any, intent: Any = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """(species key, untyped gap or None) for the engine's species grants (#1280, B1).

    With a creation intent (a dict; the live interview always passes one) its species_key, never race.
    Without one (a supplied sheet): EXC-COST5-1 (D-KW exception, supplied sheets only): a free-string race
    (char_schema string, frozen) matched exactly against the closed set of canonical species names; a
    non-match grants nothing and records gap species.unknown; never normalised; a typed species_key (the
    headless input record's, passed as the intent) is preferred when present."""
    species = _origins().get("species") or []
    if isinstance(intent, dict):
        key = intent.get("species_key")
        if key in [s.get("key") for s in species]:
            return key, None
        return None, {"id": "species.unknown", "grant": "species grants", "where": "species_key"}
    race = (sheet or {}).get("race")
    key = next((s.get("key") for s in species if s.get("name") == race), None)
    if key is None:
        return None, {"id": "species.unknown", "grant": "species grants", "where": "race"}
    return key, None


def apply_species_resistances(sheet: Dict[str, Any], intent: Any = None) -> List[Dict[str, Any]]:
    """Add the species' granted damage resistances to the sheet in place: each type is appended unless an
    entry equals it (casefolded); nothing is removed or rewritten, and the sheet's own list is never the
    source. The species is species_key_for's (the intent's, or EXC-COST5-1 on a supplied sheet); with no
    species the sheet is untouched and the one untyped gap entry is returned. Returns
    [{source, added, present}]; with no grant the sheet is untouched."""
    key, gap = species_key_for(sheet, intent)
    if gap is not None:
        return [{"source": None, "added": [], "present": [], "untyped": dict(gap, grant="damage resistances")}]
    intent = {"species_key": key, "choices": (intent or {}).get("choices") or {}} if isinstance(intent, dict) \
        else {"species_key": key, "choices": {}}
    found = species_damage_resistances(intent)
    if not found:
        return []
    have = sheet.get("damageResistances") if isinstance(sheet.get("damageResistances"), list) else []
    seen = {x.strip().casefold() for x in have if isinstance(x, str)}
    entries = []
    for grant in found:
        added, present = [], []
        for kind in grant["damage_resistances"]:
            if kind.casefold() in seen:
                present.append(kind)
            else:
                have.append(kind)
                seen.add(kind.casefold())
                added.append(kind)
        entries.append({"source": grant["source"], "added": added, "present": present})
    sheet["damageResistances"] = have
    return entries
