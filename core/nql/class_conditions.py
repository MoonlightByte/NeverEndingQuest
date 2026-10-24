# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Per-character class conditions for the engine world (NUM-H3b).

From the sheet's typed ``class``, ``classes``, ``level`` and
``proficiencies.weapons`` and the SRD pack's typed records, this module names
the Condition instances a character holds:

- ``srd:unarmed-strike``: every character (attack_features.nql);
- ``prof:weapon:<slug>``: each base catalog weapon the character is proficient
  with, the union of the primary class's rules (choices.json
  ``class_traits.<class>.weapon_proficiencies``) and the sheet's
  ``proficiencies.weapons`` in a fixed vocabulary ("simple", "martial", their
  printed long forms "simple weapons" and "martial weapons" (#896), or a base
  catalog weapon's exact name, casefolded); anything else is a note;
- the Monk's Martial Arts types for the die in progression.json's "Martial
  Arts" column at its Monk level (choices ``martial_arts.condition_types``);
- ``feature:unarmored-defense:<class>``: the class's non-subclass
  ``ac_formulas`` entry (Barbarian, Monk). The engine gates the defense terms
  by slot (``unless slot``, NQL 7316e58), so the instance does not depend on
  what the sheet wears. A sheet with two such classes keeps its primary
  class's only (SRD: Unarmored Defense cannot be gained twice), with a note;
- ``feature:ac-formula:<class>:<feature>`` (#1433): any other ``ac_formulas``
  entry (a subclass or later-level base AC such as the Draconic Sorcerer's
  Draconic Resilience), when the sheet's primary class is that class at a
  typed single-class level at least the formula's and its subclass
  (``core.leveling.tables.infer_subclass``) is the formula's. Genesis declares
  the type and its alternative defense recipe only in a world where a sheet
  holds it.

It also writes the defense derive's Unarmored Defense terms from
``ac_formulas``. Missing or unreadable data means no terms and no instances
(the world as before). No prose is read and no model is called.

What this module reports goes to ``notes``, not to the genesis gaps: none of
it bears on defense (the derive terms come from the typed formula), so it
must not stop a projection from certifying AC.
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from core.leveling import tables
from core.nql import item_catalog

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "srd")
PROGRESSION_PATH = os.path.join(_DIR, "progression.json")
CHOICES_PATH = os.path.join(_DIR, "choices.json")

UNARMED_STRIKE = "srd:unarmed-strike"
UNARMORED_DEFENSE_PREFIX = "feature:unarmored-defense:"
AC_FORMULA_PREFIX = "feature:ac-formula:"
AC_FORMULA_RECIPE_PREFIX = "ac-feature:"
WEAPON_CATEGORIES = {"simple": "Simple", "martial": "Martial",
                     "simple weapons": "Simple", "martial weapons": "Martial"}
_ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")

_CACHE: Dict[str, Any] = {}


def _load(path: str) -> Optional[Dict[str, Any]]:
    """The JSON document at ``path``, read once and re-read when it changes; None when missing or unreadable."""
    try:
        st = os.stat(path)
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    hit = _CACHE.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError):
        doc = None
    doc = doc if isinstance(doc, dict) else None
    _CACHE[path] = (stamp, doc)
    return doc


def _classes(doc: Optional[Dict[str, Any]], key: str) -> Dict[str, Any]:
    value = (doc or {}).get(key)
    return value if isinstance(value, dict) else {}


def class_names(sheet: Dict[str, Any]) -> List[str]:
    """The sheet's classes, casefolded, primary (``class``) first, without repeats."""
    names = [sheet.get("class")]
    for entry in sheet.get("classes") or []:
        names.append(entry.get("name") or entry.get("class") if isinstance(entry, dict) else entry)
    out: List[str] = []
    for name in names:
        if isinstance(name, str) and name.strip() and name.strip().casefold() not in out:
            out.append(name.strip().casefold())
    return out


def unarmored_formulas() -> List[Tuple[str, List[str], bool]]:
    """(class, abilities other than Dexterity, shield allowed) for each non-subclass
    Unarmored Defense formula in progression.json ``ac_formulas``, in class order."""
    out: List[Tuple[str, List[str], bool]] = []
    for cls, record in _classes(_load(PROGRESSION_PATH), "classes").items():
        for formula in (record or {}).get("ac_formulas") or [] if isinstance(record, dict) else []:
            if not isinstance(formula, dict) or formula.get("subclass") or formula.get("level") != 1:
                continue
            shape = formula.get("formula") or {}
            abilities = [str(a).casefold() for a in shape.get("abilities") or []]
            if shape.get("base") != 10 or shape.get("while") != "no armor" or "dexterity" not in abilities:
                continue
            extra = [a for a in abilities if a != "dexterity"]
            if not extra or any(a not in _ABILITIES for a in extra):
                continue
            out.append((cls, extra, shape.get("shield") == "allowed"))
    return out


def _slug(text: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in text.casefold()).split())


def _recipe_formula(cls: str, formula: Any) -> Optional[Tuple[str, Optional[str], str, int, int, List[str], bool]]:
    """(class, subclass, feature, level, base, abilities, shield allowed) of a typed ``ac_formulas``
    entry that is a whole base AC while no armor is worn; None for any other shape."""
    if not isinstance(formula, dict):
        return None
    shape = formula.get("formula") if isinstance(formula.get("formula"), dict) else {}
    feature, subclass, level, base = formula.get("feature"), formula.get("subclass"), formula.get("level"), shape.get("base")
    abilities = shape.get("abilities")
    if not (isinstance(feature, str) and feature.strip() and (subclass is None or isinstance(subclass, str) and subclass.strip())
            and type(level) is int and 1 <= level <= 20 and type(base) is int and 0 <= base <= 30
            and shape.get("while") == "no armor" and shape.get("shield") in ("allowed", "not allowed")
            and isinstance(abilities, list) and abilities
            and all(isinstance(a, str) and a.casefold() in _ABILITIES for a in abilities)):
        return None
    return (cls, subclass.strip() if subclass else None, feature.strip(), level, base,
            [a.casefold() for a in abilities], shape.get("shield") == "allowed")


def _recipe_candidates(cls: str, record: Any) -> List[Any]:
    """The class's ``ac_formulas`` entries unarmored_formulas does not take: a subclass's, or a later level's."""
    formulas = (record or {}).get("ac_formulas") if isinstance(record, dict) else None
    return [f for f in formulas or [] if not isinstance(f, dict) or f.get("subclass") or f.get("level") != 1]


def recipe_formulas() -> List[Tuple[str, Optional[str], str, int, int, List[str], bool]]:
    """#1433: every well-formed ac_formulas entry outside Unarmored Defense, in class order."""
    out = []
    for cls, record in _classes(_load(PROGRESSION_PATH), "classes").items():
        for formula in _recipe_candidates(cls, record):
            parsed = _recipe_formula(cls, formula)
            if parsed is not None:
                out.append(parsed)
    return out


def ac_formula_type(cls: str, feature: str) -> str:
    return f"{AC_FORMULA_PREFIX}{cls}:{_slug(feature)}"


def ac_formula_recipe(cls: str, feature: str) -> str:
    return f"{AC_FORMULA_RECIPE_PREFIX}{cls}:{_slug(feature)}"


def recipe_feature(recipe_name: Any) -> Optional[str]:
    """The feature name behind a chosen ``ac-feature:`` defense recipe; None for any other recipe."""
    if not (isinstance(recipe_name, str) and recipe_name.startswith(AC_FORMULA_RECIPE_PREFIX)):
        return None
    for cls, _, feature, _, _, _, _ in recipe_formulas():
        if ac_formula_recipe(cls, feature) == recipe_name:
            return feature
    return None


def _formula_instances(sheet: Dict[str, Any], names: List[str], notes: List[str], cid: str) -> List[str]:
    primary = names[0] if names else None
    out: List[str] = []
    for cls, record in _classes(_load(PROGRESSION_PATH), "classes").items():
        if cls not in names:
            continue
        for formula in _recipe_candidates(cls, record):
            parsed = _recipe_formula(cls, formula)
            if parsed is None:
                notes.append(f"{cid}: {cls} ac_formulas entry {formula.get('feature') if isinstance(formula, dict) else formula!r}"
                             " is not a typed base AC formula; not declared")
                continue
            _, subclass, feature, level, _, _, _ = parsed
            if subclass is not None:
                chosen = tables.infer_subclass(sheet, cls)
                if not (isinstance(chosen, str) and chosen.casefold() == subclass.casefold()):
                    continue
            if cls != primary or len(names) > 1:
                notes.append(f"{cid}: no typed {cls.capitalize()} level on a multiclass sheet; {feature} not declared")
                continue
            sheet_level = sheet.get("level")
            if type(sheet_level) is int and level <= sheet_level <= 20:
                out.append(ac_formula_type(cls, feature))
    return out


def condition_types() -> List[str]:
    """The Unarmored Defense Condition types every world declares (none without the data)."""
    return [UNARMORED_DEFENSE_PREFIX + cls for cls, _, _ in unarmored_formulas()]


def defense_terms() -> str:
    """The derive's Unarmored Defense terms, each gated on its class's Condition and on
    the slots the formula excludes; empty without the data."""
    terms = []
    for cls, extra, shield_allowed in unarmored_formulas():
        gate = ' unless slot "body"' + ('' if shield_allowed else ' unless slot "shield"')
        for ability in extra:
            terms.append(f' term stat "{ability}" offset -10 divide 2 requires "{UNARMORED_DEFENSE_PREFIX}{cls}"{gate};')
    return "".join(terms)


def _monk_level(sheet: Dict[str, Any], names: List[str], notes: List[str], cid: str) -> Optional[int]:
    if not names or names[0] != "monk":
        if "monk" in names:
            notes.append(f"{cid}: Monk is not the sheet's class and no typed Monk level is recorded; no Martial Arts die declared")
        return None
    if len(names) > 1:
        notes.append(f"{cid}: multiclass sheet has no typed Monk level; no Martial Arts die declared")
        return None
    level = sheet.get("level")
    return level if type(level) is int and 1 <= level <= 20 else None


def _proficient_weapons(sheet: Dict[str, Any], primary: Optional[str], notes: List[str], cid: str) -> List[str]:
    """Base catalog weapon slugs the character is proficient with (HB1: the union)."""
    weapons = [e for e in item_catalog.weapon_entries() if not e.get("weapon_base")]
    by_name = {str(e.get("name", "")).casefold(): e for e in weapons}
    rules: List[Dict[str, Any]] = []
    traits = _classes(_load(CHOICES_PATH), "class_traits")
    if primary and isinstance(traits.get(primary), dict):
        rules.extend(r for r in traits[primary].get("weapon_proficiencies") or [] if isinstance(r, dict))
    named: List[str] = []
    for label in (sheet.get("proficiencies") or {}).get("weapons") or [] if isinstance(sheet.get("proficiencies"), dict) else []:
        key = str(label).strip().casefold()
        if key in WEAPON_CATEGORIES:
            rules.append({"category": WEAPON_CATEGORIES[key]})
        elif key in by_name:
            named.append(by_name[key]["id"])
        else:
            notes.append(f"{cid}: proficiencies.weapons entry {label!r} is not an SRD weapon or category; no proficiency declared")
    out: List[str] = []
    for entry in weapons:
        block = entry.get("weapon") or {}
        props = {p.get("name") for p in block.get("properties") or [] if isinstance(p, dict)}
        if entry["id"] in named or any(
                r.get("category") == block.get("category")
                and (not r.get("property_any") or props & set(r["property_any"])) for r in rules):
            out.append(entry["id"].split("/", 1)[1])
    return out


def instances(sheet: Dict[str, Any], notes: List[str], cid: str, with_pack: bool) -> List[str]:
    """The Condition kinds this character holds, in world order. ``with_pack`` is true
    when the world carries the item pack and attack_features.nql (their types)."""
    names = class_names(sheet)
    primary = names[0] if names else None
    out: List[str] = []
    if with_pack:
        out.append(UNARMED_STRIKE)
        out.extend("prof:weapon:" + slug for slug in _proficient_weapons(sheet, primary, notes, cid))
        level = _monk_level(sheet, names, notes, cid)
        if level is not None:
            traits = _classes(_load(CHOICES_PATH), "class_traits")
            arts = (traits.get("monk") or {}).get("martial_arts") or {}
            column = (((_classes(_load(PROGRESSION_PATH), "classes").get("monk") or {}).get("table_columns") or {})
                      .get(arts.get("column") or "Martial Arts") or {})
            die = column.get(str(level))
            kinds = (arts.get("condition_types") or {}).get(die) if isinstance(die, str) else None
            if kinds:
                out.extend(k for k in kinds if isinstance(k, str))
            else:
                notes.append(f"{cid}: no Martial Arts die for Monk level {level}; none declared")
    ud = [cls for cls, _, _ in unarmored_formulas() if cls in names]
    if ud:
        keep = primary if primary in ud else ud[0]
        out.append(UNARMORED_DEFENSE_PREFIX + keep)
        for other in ud:
            if other != keep:
                notes.append(f"{cid}: Unarmored Defense from {other} not declared; the sheet already has it from {keep}")
    out.extend(_formula_instances(sheet, names, notes, cid))
    return out
