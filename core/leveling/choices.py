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
    return {tables._feature_key(f.get("name")) for f in sheet.get("classFeatures") or [] if isinstance(f, dict)}


def _held_feats(sheet: Dict[str, Any]) -> List[str]:
    out = []
    for feat in sheet.get("feats") or []:
        out.append(str(feat.get("name") if isinstance(feat, dict) else feat))
    return out


def _skill_multipliers(sheet: Dict[str, Any]) -> Dict[str, int]:
    """{skill key: 0, 1 or 2} read back from the stored bonuses (proficiency times)."""
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
        else:
            return None   # weapons, tools, beasts: the agent picks, code accepts a name
    return _apply_filters(names, filters, sheet)


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
        for key in ("named_option", "recommended", "alternatives", "then", "table_column"):
            if entry.get(key) is not None:
                point[key] = entry[key]
        if entry["kind"] == "asi_or_feat":
            point["abilities"] = dict(sheet.get("abilities") or {})
            point["cap"] = tables.ABILITY_CAP
        points.append(point)
    return points


def check_pick(point: Dict[str, Any], value: Any, sheet: Dict[str, Any], cls: str, new_level: int) -> Tuple[bool, str]:
    """Validate an agent's answer for a data-driven choice point."""
    kind = point["kind"]
    options = point.get("options")
    if kind == "asi_or_feat" or kind == "epic_boon":
        if isinstance(value, dict) and isinstance(value.get("asi"), dict):
            if kind == "epic_boon":
                return False, "an Epic Boon is a feat, name it"
            _, why = tables.apply_asi(dict(sheet.get("abilities") or {}), value["asi"])
            return (False, why) if why else (True, "")
        name = value.get("feat") if isinstance(value, dict) else value
        if not isinstance(name, str) or not name.strip():
            return False, "give {asi: {ability: +n}} or {feat: name}"
        if options is not None and name not in options:
            return False, f"{name!r} is not a feat this character qualifies for; options: {options}"
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
    if options is not None:
        for p in picks:
            if p not in options:
                return False, f"{p!r} is not one of the options for {point['id']}: {options}"
    return True, ""
