# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""SRD 5.2.1 class progression as data (L1).

Everything a level-up settles without a choice comes from ``data/srd/progression.json``
(parsed from the SRD PDF, machine-checked): eligibility, proficiency bonus, hit die and
fixed gain, spell slot maxima, cantrip and prepared counts, the features a level grants,
feature pool sizes from the class table columns, and the choice points the level opens.
Nothing here reads prose from a sheet and nothing here calls a model.

Numbers derived from the sheet's typed fields (skill bonuses, save DC, attack bonus,
passive perception) are recomputed from ability scores and the new proficiency bonus.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "data", "srd", "progression.json")
_TABLES: Optional[Dict[str, Any]] = None
_SUBCLASSES: Optional[Dict[str, Any]] = None
_SUBCLASS_DATA = os.path.join(os.path.dirname(_DATA), "subclasses.json")

SKILL_ABILITY = {
    "athletics": "strength", "acrobatics": "dexterity", "sleight_of_hand": "dexterity", "stealth": "dexterity",
    "arcana": "intelligence", "history": "intelligence", "investigation": "intelligence", "nature": "intelligence",
    "religion": "intelligence", "animal_handling": "wisdom", "insight": "wisdom", "medicine": "wisdom",
    "perception": "wisdom", "survival": "wisdom", "deception": "charisma", "intimidation": "charisma",
    "performance": "charisma", "persuasion": "charisma",
}
ABILITY_CAP = 20
# Class table columns that size a feature's use pool, mapped to the feature that owns the pool.
POOL_COLUMNS = {
    "Rages": ("Rage", "longRest"),
    "Channel Divinity": ("Channel Divinity", "shortRest"),
    "Focus Points": ("Monk's Focus", "shortRest"),
    "Sorcery Points": ("Font of Magic", "longRest"),
    "Bardic Inspiration": ("Bardic Inspiration", "longRest"),
    "Wild Shape": ("Wild Shape", "shortRest"),
}


def tables() -> Dict[str, Any]:
    global _TABLES
    if _TABLES is None:
        with open(_DATA, "r", encoding="utf-8") as handle:
            _TABLES = json.load(handle)
    return _TABLES


def subclasses() -> Dict[str, Any]:
    global _SUBCLASSES
    if _SUBCLASSES is None:
        with open(_SUBCLASS_DATA, "r", encoding="utf-8") as handle:
            _SUBCLASSES = json.load(handle)
    return _SUBCLASSES


def _feature_key(name: Any) -> str:
    return str(name).split("(")[0].strip().lower()


def subclass_options(cls: str) -> List[str]:
    entry = (subclasses().get("classes") or {}).get(cls) or {}
    return [sc["name"] for sc in entry.get("subclasses") or []]


def infer_subclass(sheet: Dict[str, Any], cls: str) -> Optional[str]:
    """The subclass whose features the sheet already carries (typed feature names), or None.

    The sheet's ``subclass`` field wins when present. Otherwise every classFeatures
    name is looked up in the SRD feature index for this class; the subclass with
    the most matches is the answer, ties or no matches give None.
    """
    recorded = sheet.get("subclass")
    if isinstance(recorded, str) and recorded.strip():
        return recorded.strip()
    index = subclasses().get("feature_index") or {}
    keyed = {_feature_key(name): rows for name, rows in index.items()}
    votes: Dict[str, int] = {}
    for feature in sheet.get("classFeatures") or []:
        if not isinstance(feature, dict):
            continue
        for row in keyed.get(_feature_key(feature.get("name")), []):
            if row.get("class") == cls:
                votes[row["subclass"]] = votes.get(row["subclass"], 0) + 1
    if not votes:
        return None
    best = sorted(votes.items(), key=lambda kv: -kv[1])
    if len(best) > 1 and best[0][1] == best[1][1]:
        return None
    return best[0][0]


def subclass_features(cls: str, subclass: Optional[str], level: int) -> List[str]:
    entry = (subclasses().get("classes") or {}).get(cls) or {}
    for sc in entry.get("subclasses") or []:
        if sc["name"] == subclass:
            return list((sc.get("features_by_level") or {}).get(str(level), []))
    return []


def class_key(sheet: Dict[str, Any]) -> Optional[str]:
    name = str(sheet.get("class") or "").strip().lower()
    return name if name in tables()["classes"] else None


def modifier(score: Any) -> int:
    return (int(score) - 10) // 2 if type(score) is int else 0


def proficiency_bonus(level: int) -> int:
    return int(tables()["proficiency_bonus"][str(level)])


def xp_threshold(level: int) -> int:
    return int(tables()["xp_thresholds"][str(level)])


@dataclass
class Eligibility:
    ok: bool
    reason: str = ""
    current_level: int = 0
    new_level: int = 0


def eligibility(sheet: Dict[str, Any], requested_level: Any = None) -> Eligibility:
    """Exactly one level at a time, gated by the XP table; the sheet's XP is cumulative."""
    level = sheet.get("level")
    if type(level) is not int or not 1 <= level < 20:
        return Eligibility(False, f"level {level!r} cannot advance", level or 0, 0)
    new_level = level + 1
    if requested_level not in (None, "", new_level):
        return Eligibility(False, f"only one level at a time: {level} -> {new_level}, not {requested_level!r}",
                           level, new_level)
    if class_key(sheet) is None:
        return Eligibility(False, f"class {sheet.get('class')!r} is not an SRD class", level, new_level)
    xp = sheet.get("experience_points")
    if type(xp) is not int or xp < xp_threshold(new_level):
        return Eligibility(False, f"{xp!r} XP is below the {xp_threshold(new_level)} needed for level {new_level}",
                           level, new_level)
    return Eligibility(True, "", level, new_level)


def slot_maxima(cls: str, level: int) -> Dict[str, int]:
    """spellSlots maxima at ``level`` as {levelN: max}; pact casters map pact slots onto their slot level."""
    c = tables()["classes"][cls]
    out = {f"level{n}": 0 for n in range(1, 10)}
    if c.get("spell_slots_by_level"):
        out.update({k: int(v) for k, v in c["spell_slots_by_level"][str(level)].items()})
    elif c.get("pact_slots_by_level"):
        pact = c["pact_slots_by_level"][str(level)]
        out[f"level{int(pact['slot_level'])}"] = int(pact["slots"])
    return out


def hit_die(cls: str) -> int:
    return int(str(tables()["classes"][cls]["hit_die"]).lstrip("d"))


def fixed_hp_gain(cls: str) -> int:
    return int(tables()["classes"][cls]["hp_per_level_average"])


def features_gained(cls: str, level: int) -> List[str]:
    return list(tables()["classes"][cls]["features_by_level"].get(str(level), []))


def pool_sizes(cls: str, level: int) -> Dict[str, Tuple[int, str]]:
    """{feature name: (max uses, refreshOn)} for every table column that sizes a pool at this level."""
    columns = tables()["classes"][cls].get("table_columns") or {}
    out: Dict[str, Tuple[int, str]] = {}
    for column, (feature, refresh) in POOL_COLUMNS.items():
        rows = columns.get(column)
        if isinstance(rows, dict) and str(level) in rows:
            value = rows[str(level)]
            try:
                out[feature] = (int(str(value).split()[0]), refresh)
            except (TypeError, ValueError):
                continue
    return out


def spell_counts(cls: str, level: int) -> Dict[str, Optional[int]]:
    c = tables()["classes"][cls]
    cantrips = (c.get("cantrips_known_by_level") or {}).get(str(level))
    prepared = (c.get("prepared_spells_by_level") or {}).get(str(level))
    return {"cantrips": int(cantrips) if cantrips is not None else None,
            "prepared": int(prepared) if prepared is not None else None}


def choice_points(sheet: Dict[str, Any], cls: str, new_level: int) -> List[Dict[str, Any]]:
    """The choices this level opens, in the order to settle them.

    Typed and enumerable: the model chooses among options the tables list; it never
    decides whether a choice exists. Option lists that live outside this file
    (spells) are referenced by source so the packet builder can fill them.
    """
    from core.leveling import choices as srd_choices

    c = tables()["classes"][cls]
    points: List[Dict[str, Any]] = []
    if sheet.get("character_type") == "player":
        points.append({"id": "hit_points", "kind": "hit_points",
                       "prompt": f"Roll your d{hit_die(cls)} for hit points, or take the fixed {fixed_hp_gain(cls)}.",
                       "options": ["fixed", "roll"], "die": hit_die(cls), "fixed": fixed_hp_gain(cls)})
    # Every other choice this level opens comes from the SRD choices data (kinds
    # asi_or_feat, subclass, fighting_style, expertise, skill, epic_boon,
    # other_named), with option lists resolved against the sheet. A subclass pick
    # is skipped when the sheet's features already identify the subclass.
    for point in srd_choices.data_choice_points(sheet, cls, new_level):
        if point["kind"] == "subclass" and infer_subclass(sheet, cls) is not None:
            continue
        points.append(point)
    counts_now, counts_before = spell_counts(cls, new_level), spell_counts(cls, new_level - 1)
    if counts_now["cantrips"] and counts_now["cantrips"] != counts_before["cantrips"]:
        points.append({"id": "cantrips", "kind": "cantrips", "count": counts_now["cantrips"],
                       "prompt": f"You now know {counts_now['cantrips']} cantrips; name the new one(s).",
                       "source": f"spells:class={cls},level=0"})
    if counts_now["prepared"] and counts_now["prepared"] != counts_before["prepared"]:
        top = max([int(k[5:]) for k, v in slot_maxima(cls, new_level).items() if v] or [0])
        points.append({"id": "prepared_spells", "kind": "prepared_spells", "count": counts_now["prepared"],
                       "prompt": f"You can prepare {counts_now['prepared']} spells now (up to level {top}); "
                                 "name your prepared list or keep it and add.",
                       "source": f"spells:class={cls},max_level={top}"})
    return points


@dataclass
class Settled:
    """Everything the tables settle for one level-up, before choices and before the engine."""
    cls: str
    new_level: int
    proficiency_bonus: int
    hp_gain_fixed: int
    hit_die: int
    slot_targets: Dict[str, int]
    features: List[str]
    pools: Dict[str, Tuple[int, str]]
    spell_counts: Dict[str, Optional[int]]
    exp_required_for_next_level: int
    choice_points: List[Dict[str, Any]] = field(default_factory=list)
    subclass: Optional[str] = None


def features_for(cls: str, subclass: Optional[str], level: int) -> List[str]:
    """Class features at ``level`` with the subclass's own features in place of the placeholder."""
    out = []
    for name in features_gained(cls, level):
        if name == "Subclass feature" or name.endswith(" Subclass"):
            out.extend(subclass_features(cls, subclass, level) or [name])
        else:
            out.append(name)
    return out


def settle(sheet: Dict[str, Any], new_level: int) -> Settled:
    cls = class_key(sheet)
    if cls is None:
        raise ValueError("not an SRD class")
    subclass = infer_subclass(sheet, cls)
    return Settled(
        cls=cls, new_level=new_level, proficiency_bonus=proficiency_bonus(new_level),
        hp_gain_fixed=fixed_hp_gain(cls), hit_die=hit_die(cls), slot_targets=slot_maxima(cls, new_level),
        features=features_for(cls, subclass, new_level), pools=pool_sizes(cls, new_level), subclass=subclass,
        spell_counts=spell_counts(cls, new_level),
        exp_required_for_next_level=xp_threshold(new_level + 1) if new_level < 20 else xp_threshold(20),
        choice_points=choice_points(sheet, cls, new_level),
    )


def hp_gain(sheet: Dict[str, Any], cls: str, method: str, roll: Optional[int] = None) -> Tuple[int, str]:
    """(gain, how) with the constitution modifier; a roll must be within the die; minimum 1 per level."""
    con = modifier((sheet.get("abilities") or {}).get("constitution"))
    if method == "roll":
        die = hit_die(cls)
        if type(roll) is not int or not 1 <= roll <= die:
            raise ValueError(f"a d{die} roll must be a whole number from 1 to {die}")
        return max(1, roll + con), f"rolled {roll} + {con} Con"
    return max(1, fixed_hp_gain(cls) + con), f"fixed {fixed_hp_gain(cls)} + {con} Con"


def derived_numbers(sheet: Dict[str, Any], new_level: int, abilities: Dict[str, int]) -> Dict[str, Any]:
    """Skill bonuses, saves-dependent values, DC and attack bonus from scores and the new proficiency.

    A skill's proficiency multiplier (0, 1 or 2) is read back from the stored bonus
    against the old proficiency bonus, then reapplied with the new one.
    """
    old_pb = sheet.get("proficiencyBonus") if type(sheet.get("proficiencyBonus")) is int else proficiency_bonus(sheet.get("level", 1))
    new_pb = proficiency_bonus(new_level)
    old_abilities = sheet.get("abilities") or {}
    skills: Dict[str, int] = {}
    for skill, bonus in (sheet.get("skills") or {}).items():
        ability = SKILL_ABILITY.get(str(skill).lower())
        if ability is None or type(bonus) is not int:
            skills[skill] = bonus
            continue
        old_mod = modifier(old_abilities.get(ability))
        times = 0 if old_pb == 0 else max(0, min(2, round((bonus - old_mod) / old_pb)))
        skills[skill] = modifier(abilities.get(ability)) + times * new_pb
    out: Dict[str, Any] = {"proficiencyBonus": new_pb, "skills": skills}
    if "perception" in {str(k).lower() for k in skills}:
        key = next(k for k in skills if str(k).lower() == "perception")
        senses = dict(sheet.get("senses") or {})
        senses["passivePerception"] = 10 + skills[key]
        out["senses"] = senses
    if "initiative" in sheet:
        out["initiative"] = modifier(abilities.get("dexterity"))
    casting = sheet.get("spellcasting") if isinstance(sheet.get("spellcasting"), dict) else None
    if casting and casting.get("ability"):
        mod = modifier(abilities.get(str(casting["ability"]).lower()))
        out["spellSaveDC"] = 8 + new_pb + mod
        out["spellAttackBonus"] = new_pb + mod
    return out


def apply_asi(abilities: Dict[str, int], increases: Dict[str, int]) -> Tuple[Dict[str, int], str]:
    """+2 to one ability or +1 to two, never above 20. Returns (new abilities, reason if refused)."""
    if not isinstance(increases, dict) or not increases:
        return abilities, "an Ability Score Improvement names one ability +2 or two abilities +1"
    total = sum(increases.values())
    if total != 2 or any(type(v) is not int or v < 1 for v in increases.values()) or len(increases) > 2:
        return abilities, "an Ability Score Improvement is +2 to one ability or +1 to two"
    out = dict(abilities)
    for name, inc in increases.items():
        key = str(name).lower()
        if key not in out:
            return abilities, f"unknown ability {name!r}"
        if out[key] + inc > ABILITY_CAP:
            return abilities, f"{key} cannot rise above {ABILITY_CAP}"
        out[key] += inc
    return out, ""
