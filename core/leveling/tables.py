# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""SRD 5.2.1 class progression as data (L1).

Everything a level-up settles without a choice comes from ``data/srd/progression.json``
(parsed from the SRD PDF, machine-checked): eligibility, proficiency bonus, hit die and
fixed gain, spell slot maxima, cantrip and prepared counts, the features a level grants,
feature use pools (maximum and rest refresh) from the class's use_pools, and the choice
points the level opens.
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


_VARIANTS: Optional[Dict[str, str]] = None


def _table_variants() -> Dict[str, str]:
    """{casefolded class table row: its use pool's feature}, from the typed
    ``table_names`` of data/srd/progression.json: the table prints "Action
    Surge (one use)" for the Action Surge pool. Whole values; nothing is cut."""
    global _VARIANTS
    if _VARIANTS is None:
        _VARIANTS = {str(row).strip().casefold(): pool["feature"]
                     for entry in tables()["classes"].values() for pool in entry.get("use_pools") or []
                     for row in pool.get("table_names") or []}
    return _VARIANTS


def _feature_key(feature: Any) -> str:
    """A feature's identity as the SRD tables match it, trimmed and casefolded.

    A classFeatures entry answers with its typed ``srd_name`` when T125 has
    named its SRD feature (a decorated legacy name such as "Channel Divinity
    (2/rest)"), else with its whole name; a string is its own whole value. A
    class table row listed in a pool's ``table_names`` is that pool's feature.
    No name is cut (keyword validation V4)."""
    if isinstance(feature, dict):
        typed = feature.get("srd_name")
        feature = typed if isinstance(typed, str) and typed.strip() else feature.get("name")
    key = str(feature if feature is not None else "").strip().casefold()
    pool = _table_variants().get(key)
    return pool.strip().casefold() if pool else key


def srd_feature_names(cls: str) -> List[str]:
    """Every SRD feature name a sheet of this class can carry: the class
    table's features at every level, its subclasses' features and its use
    pools. The closed list T125 names a legacy feature from."""
    names: List[str] = []
    entry = tables()["classes"].get(cls) or {}
    for level_names in (entry.get("features_by_level") or {}).values():
        names.extend(level_names)
    for subclass in ((subclasses().get("classes") or {}).get(cls) or {}).get("subclasses") or []:
        for level_names in (subclass.get("features_by_level") or {}).values():
            names.extend(level_names)
    names.extend(pool["feature"] for pool in entry.get("use_pools") or [] if pool.get("feature"))
    seen = set()
    return [n for n in names if isinstance(n, str) and not (n in seen or seen.add(n))]


def unnamed_features(sheet: Dict[str, Any]) -> List[int]:
    """Indexes of the classFeatures entries whose SRD identity is unsettled:
    no ``srd_name`` key yet and a whole name that is not an SRD feature of the
    sheet's class. Empty for a sheet without an SRD class."""
    cls = class_key(sheet)
    if cls is None:
        return []
    known = {_feature_key(name) for name in srd_feature_names(cls)}
    return [
        index for index, feature in enumerate(sheet.get("classFeatures") or [])
        if isinstance(feature, dict) and "srd_name" not in feature
        and isinstance(feature.get("name"), str) and _feature_key(feature["name"]) not in known
    ]


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
        for row in keyed.get(_feature_key(feature), []):
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


def pact_slot_set(cls: str, level: int) -> Optional[Tuple[str, int]]:
    """A pact caster's slots at ``level`` as one set, (levelN, count); None for other classes."""
    pact = tables()["classes"][cls].get("pact_slots_by_level")
    if not pact:
        return None
    row = pact[str(level)]
    return f"level{int(row['slot_level'])}", int(row["slots"])


def move_pact_slots(slots: Dict[str, Any], cls: str, level: int) -> List[str]:
    """Write a pact caster's slots as one set, in place (#704, H4-Q4 a).

    Pact slots change slot level as the class advances (level 1, then 2 from
    Warlock 3, ...), so the set is moved, not grown beside the old level: the
    table's level gets the table's count, every other level's maximum becomes 0,
    and the unspent slots move with the set (capped at the count), so no level
    keeps a current above its maximum. Returns one note per level changed."""
    target = pact_slot_set(cls, level)
    if target is None or not isinstance(slots, dict):
        return []
    key, count = target
    notes: List[str] = []
    carried = 0
    for other in sorted(slots):
        slot = slots[other]
        if other == key or not isinstance(slot, dict):
            continue
        maximum = slot.get("max") if type(slot.get("max")) is int else 0
        current = slot.get("current") if type(slot.get("current")) is int else 0
        if maximum or current:
            carried += current
            slot.update({"current": 0, "max": 0})
            notes.append(f"spellSlots {other} {current}/{maximum} -> 0/0 (pact slots are {key} at "
                         f"{cls.capitalize()} level {level})")
    slot = slots.get(key) if isinstance(slots.get(key), dict) else {}
    maximum = slot.get("max") if type(slot.get("max")) is int else 0
    current = slot.get("current") if type(slot.get("current")) is int else 0
    moved = {"current": min(current + carried, count), "max": count}
    if (current, maximum) != (moved["current"], moved["max"]):
        notes.append(f"spellSlots {key} {current}/{maximum} -> {moved['current']}/{count} (SRD "
                     f"{cls.capitalize()} level {level} pact slots)")
        slots[key] = dict(slot, **moved)
    return notes


def hit_die(cls: str) -> int:
    return int(str(tables()["classes"][cls]["hit_die"]).lstrip("d"))


def fixed_hp_gain(cls: str) -> int:
    return int(tables()["classes"][cls]["hp_per_level_average"])


def features_gained(cls: str, level: int) -> List[str]:
    return list(tables()["classes"][cls]["features_by_level"].get(str(level), []))


@dataclass(frozen=True)
class Pool:
    """A feature's use pool at one class level: its maximum, the rest that
    refreshes it, and how many uses a Short Rest regains when it regains only
    some (None: a Short Rest, if it refreshes the pool, refills it)."""
    max: int
    refresh_on: str
    short_rest_regain: Optional[int] = None
    follows_ability: bool = field(default=False, compare=False)

    def usage(self, current: Optional[int] = None) -> Dict[str, Any]:
        """The sheet's classFeatures[].usage for this pool."""
        out: Dict[str, Any] = {"current": self.max if current is None else current, "max": self.max,
                               "refreshOn": self.refresh_on}
        if self.short_rest_regain is not None:
            out["shortRestRegain"] = self.short_rest_regain
        return out


def _pool_maximum(maximum: Dict[str, Any], columns: Dict[str, Any], level: int,
                  abilities: Dict[str, Any]) -> Optional[int]:
    """A use_pools maximum resolved from its typed kind; None when it does not resolve."""
    if "column" in maximum:
        rows = columns.get(maximum["column"])
        value = rows.get(str(level)) if isinstance(rows, dict) else None
        try:
            return int(str(value).split()[0])
        except (TypeError, ValueError, IndexError):
            return None
    if "by_level" in maximum:
        steps = [(int(at), n) for at, n in maximum["by_level"].items() if int(at) <= level]
        return int(max(steps)[1]) if steps else None
    if "fixed" in maximum:
        return int(maximum["fixed"])
    if "ability_modifier" in maximum:
        score = (abilities or {}).get(str(maximum["ability_modifier"]).lower())
        return max(int(maximum.get("minimum", 0)), modifier(score))
    if "class_level_times" in maximum:
        return int(maximum["class_level_times"]) * level
    return None


def use_pools_at(cls: str, level: int, abilities: Optional[Dict[str, Any]] = None) -> Dict[str, Pool]:
    """{feature name: Pool} for every use pool the class has at ``level``. The refresh
    is the class table's row in effect at that level (a pool's rest can change as the
    class advances, e.g. Bardic Inspiration from level 5). A Short Rest that regains
    "one" use is a partial regain of 1; "all" refills; none leaves a Long Rest pool."""
    c = tables()["classes"][cls]
    columns = c.get("table_columns") or {}
    out: Dict[str, Pool] = {}
    for pool in c.get("use_pools") or []:
        if int(pool["level"]) > level:
            continue
        maximum = _pool_maximum(pool.get("maximum") or {}, columns, level, abilities or {})
        if maximum is None:
            continue
        rows = [row for row in pool.get("refresh") or [] if int(row["from_level"]) <= level]
        short_rest = max(rows, key=lambda row: int(row["from_level"])).get("short_rest") if rows else None
        out[pool["feature"]] = Pool(maximum, "shortRest" if short_rest in ("one", "all") else "longRest",
                                    1 if short_rest == "one" else None,
                                    "ability_modifier" in (pool.get("maximum") or {}))
    return out


def pool_key(feature: Any) -> str:
    """A feature as pools match it: its SRD identity (``_feature_key``). A
    decorated legacy name ("Channel Divinity (2/rest)") reaches its pool
    through the typed ``srd_name`` T125 gave it, never by cutting the name."""
    return _feature_key(feature)


def pool_feature(features: Any, name: str) -> Optional[Dict[str, Any]]:
    """The classFeatures entry that owns pool ``name``, or None."""
    return next((f for f in features or [] if isinstance(f, dict) and pool_key(f) == pool_key(name)),
                None)


def raise_to_tables(sheet: Dict[str, Any]) -> List[str]:
    """Raise a saved hero's use pools and spell slots that sit below the class
    table for its level, in place; returns one note per change (#704, H4-Q1).

    Raise only: a ``max`` below the table is set to the table, a table pool's
    feature (matched by ``pool_key``) with no usage gets one, and a slot level
    the table grants is added. ``current`` is never changed (an added pool or
    slot starts at 0 until the next rest refills it) and nothing is lowered. A pool whose maximum
    follows an ability is resolved at startup and level-up only (H4-Q2), so here
    it only gains a missing usage. Pact slots are written as one set by
    ``move_pact_slots``, the one place this step lowers a maximum (H4-Q4 a). A
    sheet without an SRD class and a level is unchanged."""
    notes: List[str] = []
    cls = class_key(sheet)
    level = sheet.get("level")
    if cls is None or type(level) is not int or not 1 <= level <= 20:
        return notes
    features = sheet.get("classFeatures") if isinstance(sheet.get("classFeatures"), list) else []
    for name, pool in use_pools_at(cls, level, sheet.get("abilities")).items():
        feature = pool_feature(features, name)
        if feature is None:
            continue
        usage = feature.get("usage")
        if not isinstance(usage, dict):
            feature["usage"] = pool.usage(0)
            notes.append(f"{feature['name']} usage added: 0/{pool.max} {pool.refresh_on} (SRD {sheet.get('class')} "
                         f"level {level})")
        elif not pool.follows_ability and (type(usage.get("max")) is not int or usage["max"] < pool.max):
            notes.append(f"{feature['name']} max {usage.get('max')!r} -> {pool.max} (SRD {sheet.get('class')} "
                         f"level {level})")
            usage["max"] = pool.max
    casting = sheet.get("spellcasting")
    slots = casting.get("spellSlots") if isinstance(casting, dict) else None
    if not isinstance(slots, dict):
        return notes
    if pact_slot_set(cls, level) is not None:
        return notes + move_pact_slots(slots, cls, level)
    for slot_level, n in slot_maxima(cls, level).items():
        slot = slots.get(slot_level)
        if not n or (isinstance(slot, dict) and type(slot.get("max")) is int and slot["max"] >= n):
            continue
        if isinstance(slot, dict):
            notes.append(f"spellSlots {slot_level} max {slot.get('max')!r} -> {n} (SRD {sheet.get('class')} "
                         f"level {level})")
            slot["max"] = n
            if type(slot.get("current")) is not int:
                slot["current"] = 0
        else:
            slots[slot_level] = {"current": 0, "max": n}
            notes.append(f"spellSlots {slot_level} added: 0/{n} (SRD {sheet.get('class')} level {level})")
    return notes


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
    pools: Dict[str, "Pool"]
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
        features=features_for(cls, subclass, new_level), pools=use_pools_at(cls, new_level, sheet.get("abilities")),
        subclass=subclass,
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


def con_increase_hp(before: Any, after: Any, earlier_levels: int) -> int:
    """Hit points a higher Constitution modifier adds for the levels already
    gained (#1045): the SRD maximum changes as though the new modifier had
    applied from level 1. ``before``/``after`` are abilities dicts; never negative."""
    old = modifier((before or {}).get("constitution"))
    new = modifier((after or {}).get("constitution"))
    return max(0, new - old) * max(0, int(earlier_levels))


def hp_bonuses_gained(sheet: Dict[str, Any], cls: str, subclass: Optional[str],
                      new_level: int, picks: Optional[Dict[str, Any]] = None) -> List[Tuple[str, int]]:
    """The hit point maximum increases the SRD hp_bonuses table grants for gaining
    ``new_level`` (#858), from typed facts only: a species trait whose species_key is
    the typed creation record's (``picks``, creation_picks) gives its per_character_level
    every level; a sheet with no record gets none (species_grants_gained reports the gap); a subclass feature of this class whose subclass is ``subclass``
    (casefolded) gives, on reaching its from_class_level, per_class_level for each
    class level so far (the SRD's "increases by 3" at Sorcerer 3), then
    per_class_level each later level. Level 1 is the startup derivation's.
    [(name, amount)]."""
    out: List[Tuple[str, int]] = []
    chosen = str(subclass or "").strip().casefold()
    for entry in tables().get("hp_bonuses") or []:
        if not isinstance(entry, dict) or not str(entry.get("name") or "").strip():
            continue
        granted = entry.get("granted_by") if isinstance(entry.get("granted_by"), dict) else {}
        name = str(entry["name"]).strip()
        if granted.get("kind") == "species trait" and type(entry.get("per_character_level")) is int:
            if picks is not None and granted.get("species_key") == picks.get("species_key"):
                out.append((name, entry["per_character_level"]))
        elif granted.get("kind") == "subclass feature" and type(entry.get("per_class_level")) is int:
            start = entry.get("from_class_level")
            if (granted.get("class") != cls or type(start) is not int or new_level < start
                    or not chosen or str(granted.get("subclass") or "").strip().casefold() != chosen):
                continue
            out.append((name, entry["per_class_level"] * (new_level if new_level == start else 1)))
    return out


_ORIGINS_DATA = os.path.join(os.path.dirname(os.path.dirname(_DATA)), "srd_character_origins.json")
_SPELL_DATA = os.path.join(os.path.dirname(os.path.dirname(_DATA)), "spell_repository.json")
_ORIGINS: Optional[Dict[str, Any]] = None


def _origins() -> Dict[str, Any]:
    global _ORIGINS
    if _ORIGINS is None:
        with open(_ORIGINS_DATA, "r", encoding="utf-8") as handle:
            _ORIGINS = json.load(handle)
    return _ORIGINS


def species_grants_gained(sheet: Dict[str, Any], picks: Optional[Dict[str, Any]],
                          new_level: int) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, str]]]:
    """The species grants that arrive at character level ``new_level`` (#1292): a lineage's or
    legacy's spell (``spells_by_level``: always prepared, cast once per Long Rest without a slot,
    with the lineage's spellcasting-ability pick; SRD p.84/86) and a level trait
    (``traits_by_level``: Draconic Flight, Large Form). ``picks`` is creation_picks(): typed
    choice ids only. With no picks, any species grant at this level (or a species per-level hit
    point bonus, which applies at every level) gives the untyped gap
    {"id": "species.unknown", "where": ...} instead of a guess. ([grants], gap or None)"""
    level = str(new_level)
    species = _origins().get("species") or []
    if picks is None:
        # No typed species without the record (the race text is never read): any species grant at this
        # level, or any species per-level hit point bonus (Dwarven Toughness, hp_bonuses), is a gap.
        per_level = any((e.get("granted_by") or {}).get("kind") == "species trait"
                        and type(e.get("per_character_level")) is int for e in tables().get("hp_bonuses") or [])
        if per_level or any((s.get("grants") or {}).get("traits_by_level", {}).get(level) or any(
                (option.get("spells_by_level") or {}).get(level)
                for choice in (s.get("grants") or {}).get("choices") or [] for option in choice.get("options") or [])
               for s in species):
            return [], {"id": "species.unknown", "where": "species grants cannot be typed without a creation record"}
        return [], None
    entry = next((s for s in species if s.get("key") == picks.get("species_key")), None)
    if entry is None:
        return [], None
    from core.nql.creation_scope import _slug  # the engine's own choice-id issuer (one source of ids)
    grants = entry.get("grants") or {}
    spells = None
    out: List[Dict[str, Any]] = []
    for choice in grants.get("choices") or []:
        cid = "species.%s.%s" % (entry["key"], _slug(choice["name"]))
        picked = picks["choices"].get(cid) or []
        ability = (picks["choices"].get("%s.spellcasting-ability" % cid) or [None])[0]
        for option in [o for o in choice.get("options") or [] if o.get("name") in picked]:
            for key in (option.get("spells_by_level") or {}).get(level) or []:
                if spells is None:
                    with open(_SPELL_DATA, "r", encoding="utf-8") as handle:
                        spells = json.load(handle)
                out.append({"kind": "spell", "spell": key, "name": spells[key]["name"],
                            "level": spells[key]["level"], "ability": ability,
                            "uses": {"maximum": 1, "refresh": ["long_rest"]},
                            "source": "%s: %s" % (choice["name"], option["name"])})
    for trait in (grants.get("traits_by_level") or {}).get(level) or []:
        out.append(dict(trait, kind="trait", source="%s species" % entry["name"]))
    return out, None


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
