# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Spell Slot Utilities
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Deterministic spell-slot progression helpers for class/level normalization.
"""

from copy import deepcopy
from typing import Any, Dict, Optional, Tuple


FULL_CASTER_CLASSES = {"bard", "cleric", "druid", "sorcerer", "wizard"}
HALF_CASTER_CLASSES = {"paladin", "ranger"}
THIRD_CASTER_CLASSES = {"fighter", "rogue"}
WARLOCK_CLASS = "warlock"


def _empty_spell_slots() -> Dict[str, Dict[str, int]]:
    return {f"level{i}": {"current": 0, "max": 0} for i in range(1, 10)}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_class_name(character_class: Any) -> str:
    return str(character_class or "").strip().lower()


def _has_leveled_spells(character_data: Dict[str, Any]) -> bool:
    spellcasting = character_data.get("spellcasting", {})
    if not isinstance(spellcasting, dict):
        return False

    spells = spellcasting.get("spells", {})
    if not isinstance(spells, dict):
        return False

    for level in range(1, 10):
        level_spells = spells.get(f"level{level}", [])
        if isinstance(level_spells, list) and len(level_spells) > 0:
            return True
    return False


def _is_third_caster_active(character_data: Dict[str, Any]) -> bool:
    spellcasting = character_data.get("spellcasting", {})
    if isinstance(spellcasting, dict):
        ability = str(spellcasting.get("ability", "")).strip().lower()
        if ability and ability != "none":
            return True

    if _has_leveled_spells(character_data):
        return True

    class_features = character_data.get("classFeatures", [])
    if isinstance(class_features, list):
        for feature in class_features:
            if not isinstance(feature, dict):
                continue
            feature_name = str(feature.get("name", "")).strip().lower()
            if "spellcasting" in feature_name or "arcane trickster" in feature_name or "eldritch knight" in feature_name:
                return True

    return False


FULL_CASTER_SLOTS = {
    1: [2, 0, 0, 0, 0, 0, 0, 0, 0],
    2: [3, 0, 0, 0, 0, 0, 0, 0, 0],
    3: [4, 2, 0, 0, 0, 0, 0, 0, 0],
    4: [4, 3, 0, 0, 0, 0, 0, 0, 0],
    5: [4, 3, 2, 0, 0, 0, 0, 0, 0],
    6: [4, 3, 3, 0, 0, 0, 0, 0, 0],
    7: [4, 3, 3, 1, 0, 0, 0, 0, 0],
    8: [4, 3, 3, 2, 0, 0, 0, 0, 0],
    9: [4, 3, 3, 3, 1, 0, 0, 0, 0],
    10: [4, 3, 3, 3, 2, 0, 0, 0, 0],
    11: [4, 3, 3, 3, 2, 1, 0, 0, 0],
    12: [4, 3, 3, 3, 2, 1, 0, 0, 0],
    13: [4, 3, 3, 3, 2, 1, 1, 0, 0],
    14: [4, 3, 3, 3, 2, 1, 1, 0, 0],
    15: [4, 3, 3, 3, 2, 1, 1, 1, 0],
    16: [4, 3, 3, 3, 2, 1, 1, 1, 0],
    17: [4, 3, 3, 3, 2, 1, 1, 1, 1],
    18: [4, 3, 3, 3, 3, 1, 1, 1, 1],
    19: [4, 3, 3, 3, 3, 2, 1, 1, 1],
    20: [4, 3, 3, 3, 3, 2, 2, 1, 1],
}


HALF_CASTER_SLOTS = {
    1: [0, 0, 0, 0, 0],
    2: [2, 0, 0, 0, 0],
    3: [3, 0, 0, 0, 0],
    4: [3, 0, 0, 0, 0],
    5: [4, 2, 0, 0, 0],
    6: [4, 2, 0, 0, 0],
    7: [4, 3, 0, 0, 0],
    8: [4, 3, 0, 0, 0],
    9: [4, 3, 2, 0, 0],
    10: [4, 3, 2, 0, 0],
    11: [4, 3, 3, 0, 0],
    12: [4, 3, 3, 0, 0],
    13: [4, 3, 3, 1, 0],
    14: [4, 3, 3, 1, 0],
    15: [4, 3, 3, 2, 0],
    16: [4, 3, 3, 2, 0],
    17: [4, 3, 3, 3, 1],
    18: [4, 3, 3, 3, 1],
    19: [4, 3, 3, 3, 2],
    20: [4, 3, 3, 3, 2],
}


THIRD_CASTER_SLOTS = {
    1: [0, 0, 0, 0],
    2: [0, 0, 0, 0],
    3: [2, 0, 0, 0],
    4: [3, 0, 0, 0],
    5: [3, 0, 0, 0],
    6: [3, 0, 0, 0],
    7: [4, 2, 0, 0],
    8: [4, 2, 0, 0],
    9: [4, 2, 0, 0],
    10: [4, 3, 0, 0],
    11: [4, 3, 0, 0],
    12: [4, 3, 0, 0],
    13: [4, 3, 2, 0],
    14: [4, 3, 2, 0],
    15: [4, 3, 2, 0],
    16: [4, 3, 3, 0],
    17: [4, 3, 3, 0],
    18: [4, 3, 3, 0],
    19: [4, 3, 3, 1],
    20: [4, 3, 3, 1],
}


WARLOCK_SLOT_INFO = {
    1: (1, 1),
    2: (2, 1),
    3: (2, 2),
    4: (2, 2),
    5: (2, 3),
    6: (2, 3),
    7: (2, 4),
    8: (2, 4),
    9: (2, 5),
    10: (2, 5),
    11: (3, 5),
    12: (3, 5),
    13: (3, 5),
    14: (3, 5),
    15: (3, 5),
    16: (3, 5),
    17: (4, 5),
    18: (4, 5),
    19: (4, 5),
    20: (4, 5),
}


def _build_slots_from_row(row: list[int], width: int = 9) -> Dict[str, Dict[str, int]]:
    slots = _empty_spell_slots()
    for index in range(min(len(row), width)):
        slot_value = int(row[index])
        slots[f"level{index + 1}"] = {"current": slot_value, "max": slot_value}
    return slots


def get_expected_spell_slots(character_data: Dict[str, Any]) -> Optional[Dict[str, Dict[str, int]]]:
    """Return expected spell-slot maxima/current for known class progressions."""
    character_class = _normalize_class_name(character_data.get("class"))
    level = _safe_int(character_data.get("level"), 1)
    level = max(1, min(level, 20))

    if character_class in FULL_CASTER_CLASSES:
        expected = _build_slots_from_row(FULL_CASTER_SLOTS[level], 9)
    elif character_class in HALF_CASTER_CLASSES:
        expected = _build_slots_from_row(HALF_CASTER_SLOTS[level], 5)
    elif character_class == WARLOCK_CLASS:
        expected = _empty_spell_slots()
        slot_count, slot_level = WARLOCK_SLOT_INFO[level]
        expected[f"level{slot_level}"] = {"current": slot_count, "max": slot_count}
    elif character_class in THIRD_CASTER_CLASSES and _is_third_caster_active(character_data):
        expected = _build_slots_from_row(THIRD_CASTER_SLOTS[level], 4)
    else:
        return None

    total_max = sum(entry.get("max", 0) for entry in expected.values())
    if total_max == 0 and _has_leveled_spells(character_data):
        # TABLETOP MODE: Rescue obviously inconsistent creation data where
        # leveled spells exist but slots were initialized to all-zero.
        expected["level1"] = {"current": 2, "max": 2}

    return expected


def normalize_character_spell_slots(character_data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Normalize spell slot structure against class/level expectations.

    Returns:
        (updated_character_data, changed)
    """
    if not isinstance(character_data, dict):
        return character_data, False

    expected_slots = get_expected_spell_slots(character_data)
    if expected_slots is None:
        return character_data, False

    updated = deepcopy(character_data)
    changed = False

    spellcasting = updated.get("spellcasting")
    if not isinstance(spellcasting, dict):
        spellcasting = {}
        updated["spellcasting"] = spellcasting
        changed = True

    spell_slots = spellcasting.get("spellSlots")
    if not isinstance(spell_slots, dict):
        spell_slots = {}
        spellcasting["spellSlots"] = spell_slots
        changed = True

    for level in range(1, 10):
        key = f"level{level}"
        expected = expected_slots.get(key, {"current": 0, "max": 0})
        expected_max = _safe_int(expected.get("max"), 0)

        existing_entry = spell_slots.get(key)
        if not isinstance(existing_entry, dict):
            existing_entry = {}
            changed = True

        existing_current = _safe_int(existing_entry.get("current"), 0)
        existing_max = _safe_int(existing_entry.get("max"), 0)

        if expected_max <= 0:
            normalized_current = 0
        elif existing_max <= 0:
            normalized_current = expected_max
        else:
            normalized_current = max(0, min(existing_current, expected_max))

        normalized_entry = {
            "current": normalized_current,
            "max": expected_max,
        }

        if existing_entry != normalized_entry:
            spell_slots[key] = normalized_entry
            changed = True

    return updated, changed
