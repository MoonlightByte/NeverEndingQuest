#!/usr/bin/env python3
"""Shared character-sheet contract helpers.

These helpers provide two related services:
- robust JSON object extraction from noisy model responses
- deterministic repair of character/NPC sheets before validation or runtime use
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.file_operations import safe_read_json, safe_write_json
from utils.enhanced_logger import info, warning


STARTUP_ARRAY_DEFAULTS = {
    "condition_affected": [],
    "temporaryEffects": [],
    "injuries": [],
    "equipment_effects": [],
    "feats": [],
    "ammunition": [],
}

STARTUP_OBJECT_DEFAULTS = {
    "currency": {"gold": 10, "silver": 0, "copper": 0},
}

RUNTIME_ARRAY_DEFAULTS = {
    "condition_affected": [],
    "temporaryEffects": [],
    "injuries": [],
    "equipment_effects": [],
    "feats": [],
    "equipment": [],
    "ammunition": [],
    "attacksAndSpellcasting": [],
    "savingThrows": [],
    "skills": [],
    "languages": [],
    "damageVulnerabilities": [],
    "damageResistances": [],
    "damageImmunities": [],
    "conditionImmunities": [],
    "classFeatures": [],
    "racialTraits": [],
}

RUNTIME_OBJECT_DEFAULTS = {
    "abilities": {
        "strength": 10,
        "dexterity": 10,
        "constitution": 10,
        "intelligence": 10,
        "wisdom": 10,
        "charisma": 10,
    },
    "senses": {
        "darkvision": 0,
        "passivePerception": 10,
    },
    "proficiencies": {
        "armor": [],
        "weapons": [],
        "tools": [],
    },
    "spellcasting": {
        "ability": "N/A",
        "spellSaveDC": 0,
        "spellAttackBonus": 0,
        "spells": {
            "cantrips": [],
            "level1": [],
            "level2": [],
            "level3": [],
            "level4": [],
            "level5": [],
            "level6": [],
            "level7": [],
            "level8": [],
            "level9": [],
        },
        "spellSlots": {
            "level1": {"current": 0, "max": 0},
            "level2": {"current": 0, "max": 0},
            "level3": {"current": 0, "max": 0},
            "level4": {"current": 0, "max": 0},
            "level5": {"current": 0, "max": 0},
            "level6": {"current": 0, "max": 0},
            "level7": {"current": 0, "max": 0},
            "level8": {"current": 0, "max": 0},
            "level9": {"current": 0, "max": 0},
        },
        "preparedSpells": [],
    },
    "currency": {"gold": 0, "silver": 0, "copper": 0},
    "backgroundFeature": {
        "name": "Unknown",
        "description": "",
        "source": "",
    },
}

RUNTIME_SCALAR_DEFAULTS = {
    "character_role": "player",
    "character_type": "player",
    "type": "player",
    "name": "Unknown",
    "size": "Medium",
    "level": 1,
    "race": "Unknown",
    "class": "Unknown",
    "alignment": "neutral",
    "background": "Unknown",
    "status": "alive",
    "condition": "none",
    "hitPoints": 1,
    "maxHitPoints": 1,
    "armorClass": 10,
    "initiative": 0,
    "speed": 30,
    "proficiencyBonus": 2,
    "experience_points": 0,
    "exp_required_for_next_level": 300,
    "personality_traits": "",
    "ideals": "",
    "bonds": "",
    "flaws": "",
}


def extract_json_object(text: Optional[str]) -> Optional[str]:
    """Extract the first JSON object from a model response.

    Handles:
    - raw JSON
    - fenced JSON
    - prose wrapped around a single JSON object
    """
    stripped = (text or "").strip()
    if not stripped:
        return None

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    if start == -1:
        return None

    decoder = json.JSONDecoder()
    try:
        _, end = decoder.raw_decode(stripped[start:])
        return stripped[start : start + end].strip()
    except json.JSONDecodeError:
        return None


def repair_required_ammunition_field(character_data: Any) -> Tuple[Any, List[str]]:
    """Ensure the top-level ammunition field exists for write-path validation."""
    if not isinstance(character_data, dict):
        return character_data, ["non_dict_input"]

    repaired = copy.deepcopy(character_data)
    changes: List[str] = []
    if "ammunition" not in repaired or repaired["ammunition"] is None:
        repaired["ammunition"] = []
        changes.append("ammunition=default_list")
    elif not isinstance(repaired["ammunition"], list):
        repaired["ammunition"] = []
        changes.append("ammunition=coerced_list")

    return repaired, changes


def _ensure_list(data: Dict[str, Any], field: str, default: List[Any], changes: List[str]) -> None:
    if field not in data or data[field] is None:
        data[field] = copy.deepcopy(default)
        changes.append(f"{field}=default_list")
    elif not isinstance(data[field], list):
        data[field] = copy.deepcopy(default)
        changes.append(f"{field}=coerced_list")


def _ensure_list_of_dicts(
    data: Dict[str, Any],
    field: str,
    template: Dict[str, Any],
    changes: List[str],
) -> None:
    value = data.get(field)
    if value is None or not isinstance(value, list):
        data[field] = []
        changes.append(f"{field}=default_list")
        return

    repaired_items = []
    mutated = False
    for item in value:
        if isinstance(item, dict):
            repaired_item = copy.deepcopy(item)
            for key, default_value in template.items():
                if key not in repaired_item or repaired_item[key] is None:
                    repaired_item[key] = copy.deepcopy(default_value)
                    mutated = True
                elif key in {"quantity", "attackBonus", "damageBonus"} and (
                    not isinstance(repaired_item[key], int) or isinstance(repaired_item[key], bool)
                ):
                    repaired_item[key] = copy.deepcopy(default_value)
                    mutated = True
                elif key in {"name", "item_name", "item_type", "damageDice", "damageType", "type", "description", "source"} and not isinstance(repaired_item[key], str):
                    repaired_item[key] = copy.deepcopy(default_value)
                    mutated = True
            repaired_items.append(repaired_item)
            continue

        mutated = True
        repaired_item = copy.deepcopy(template)
        if "name" in repaired_item:
            repaired_item["name"] = str(item)
        if "item_name" in repaired_item:
            repaired_item["item_name"] = str(item)
        repaired_items.append(repaired_item)

    if mutated:
        data[field] = repaired_items
        changes.append(f"{field}=repaired_items")


def _ensure_object(data: Dict[str, Any], field: str, default: Dict[str, Any], changes: List[str]) -> None:
    if field not in data or data[field] is None:
        data[field] = copy.deepcopy(default)
        changes.append(f"{field}=default_object")
    elif not isinstance(data[field], dict):
        data[field] = copy.deepcopy(default)
        changes.append(f"{field}=coerced_object")


def _ensure_scalar(data: Dict[str, Any], field: str, default: Any, changes: List[str]) -> None:
    value = data.get(field)
    expected_type = type(default)
    if field not in data or value is None:
        data[field] = copy.deepcopy(default)
        changes.append(f"{field}=default_scalar")
    elif expected_type is str and not isinstance(value, str):
        data[field] = copy.deepcopy(default)
        changes.append(f"{field}=coerced_scalar")
    elif expected_type is int and (not isinstance(value, int) or isinstance(value, bool)):
        data[field] = copy.deepcopy(default)
        changes.append(f"{field}=coerced_scalar")
    elif expected_type is float and not isinstance(value, (int, float)):
        data[field] = copy.deepcopy(default)
        changes.append(f"{field}=coerced_scalar")


def _ensure_numeric_minimum(data: Dict[str, Any], field: str, minimum: int, changes: List[str]) -> None:
    value = data.get(field)
    if not isinstance(value, int) or value < minimum:
        data[field] = minimum
        changes.append(f"{field}=min_{minimum}")


def repair_character_sheet(
    character_data: Any,
    *,
    mode: str = "runtime",
    character_role: Optional[str] = None,
    character_type: Optional[str] = None,
) -> Tuple[Any, List[str]]:
    """Repair a character sheet deterministically.

    Args:
        character_data: Parsed sheet object.
        mode: "startup" or "runtime".
        character_role: Optional explicit role override for runtime repair.

    Returns:
        (repaired_data, changes)
    """
    if not isinstance(character_data, dict):
        return character_data, ["non_dict_input"]

    repaired = copy.deepcopy(character_data)
    changes: List[str] = []

    if mode == "runtime":
        role = (
            character_role
            or character_type
            or repaired.get("character_role")
            or repaired.get("character_type")
            or "player"
        )
        for field, default in RUNTIME_SCALAR_DEFAULTS.items():
            if field in {"character_role", "character_type", "type"}:
                _ensure_scalar(repaired, field, role, changes)
            else:
                _ensure_scalar(repaired, field, default, changes)

        # Keep the role/type fields aligned for runtime formatting.
        if repaired.get("character_role") is None:
            repaired["character_role"] = role
            changes.append("character_role=role")
        if repaired.get("character_type") is None:
            repaired["character_type"] = role
            changes.append("character_type=role")
        if repaired.get("type") is None:
            repaired["type"] = role
            changes.append("type=role")

        for field, default in RUNTIME_ARRAY_DEFAULTS.items():
            _ensure_list(repaired, field, default, changes)

        _ensure_list_of_dicts(
            repaired,
            "equipment",
            {
                "item_name": "Unknown Item",
                "item_type": "miscellaneous",
                "description": "",
                "quantity": 1,
            },
            changes,
        )
        _ensure_list_of_dicts(
            repaired,
            "ammunition",
            {
                "name": "Unknown Ammunition",
                "quantity": 1,
                "description": "",
            },
            changes,
        )
        _ensure_list_of_dicts(
            repaired,
            "attacksAndSpellcasting",
            {
                "name": "Unknown Attack",
                "attackBonus": 0,
                "damageDice": "1d4",
                "damageBonus": 0,
                "damageType": "bludgeoning",
                "type": "melee",
                "description": "",
            },
            changes,
        )
        _ensure_list_of_dicts(
            repaired,
            "classFeatures",
            {"name": "Unknown Feature", "description": "", "source": ""},
            changes,
        )
        _ensure_list_of_dicts(
            repaired,
            "racialTraits",
            {"name": "Unknown Trait", "description": "", "source": ""},
            changes,
        )
        _ensure_list_of_dicts(
            repaired,
            "temporaryEffects",
            {"name": "Unknown Effect", "description": "", "source": ""},
            changes,
        )
        _ensure_list_of_dicts(
            repaired,
            "feats",
            {"name": "Unknown Feat", "description": "", "source": ""},
            changes,
        )

        for field, default in RUNTIME_OBJECT_DEFAULTS.items():
            _ensure_object(repaired, field, default, changes)

        # Nested runtime-safe structures.
        if "passivePerception" not in repaired["senses"]:
            repaired["senses"]["passivePerception"] = 10
            changes.append("senses.passivePerception=default_scalar")
        elif not isinstance(repaired["senses"]["passivePerception"], int) or isinstance(repaired["senses"]["passivePerception"], bool):
            repaired["senses"]["passivePerception"] = 10
            changes.append("senses.passivePerception=coerced_scalar")

        _ensure_object(repaired, "proficiencies", RUNTIME_OBJECT_DEFAULTS["proficiencies"], changes)
        for nested_field, nested_default in RUNTIME_OBJECT_DEFAULTS["proficiencies"].items():
            _ensure_list(repaired["proficiencies"], nested_field, nested_default, changes)

        _ensure_object(repaired, "currency", RUNTIME_OBJECT_DEFAULTS["currency"], changes)
        for nested_field, nested_default in RUNTIME_OBJECT_DEFAULTS["currency"].items():
            _ensure_scalar(repaired["currency"], nested_field, nested_default, changes)

        _ensure_object(repaired, "abilities", RUNTIME_OBJECT_DEFAULTS["abilities"], changes)
        for nested_field, nested_default in RUNTIME_OBJECT_DEFAULTS["abilities"].items():
            _ensure_scalar(repaired["abilities"], nested_field, nested_default, changes)

        if isinstance(repaired.get("skills"), dict):
            for skill, bonus in list(repaired["skills"].items()):
                if not isinstance(bonus, int) or isinstance(bonus, bool):
                    repaired["skills"][skill] = 0
                    changes.append(f"skills.{skill}=coerced_scalar")

        _ensure_object(repaired, "spellcasting", RUNTIME_OBJECT_DEFAULTS["spellcasting"], changes)
        spells = repaired["spellcasting"].get("spells")
        if not isinstance(spells, dict):
            repaired["spellcasting"]["spells"] = copy.deepcopy(RUNTIME_OBJECT_DEFAULTS["spellcasting"]["spells"])
            changes.append("spellcasting.spells=default_object")
        else:
            for key, default_list in RUNTIME_OBJECT_DEFAULTS["spellcasting"]["spells"].items():
                if key not in spells or spells[key] is None:
                    spells[key] = copy.deepcopy(default_list)
                    changes.append(f"spellcasting.spells.{key}=default_list")
                elif not isinstance(spells[key], list):
                    spells[key] = copy.deepcopy(default_list)
                    changes.append(f"spellcasting.spells.{key}=coerced_list")

        slots = repaired["spellcasting"].get("spellSlots")
        if not isinstance(slots, dict):
            repaired["spellcasting"]["spellSlots"] = copy.deepcopy(RUNTIME_OBJECT_DEFAULTS["spellcasting"]["spellSlots"])
            changes.append("spellcasting.spellSlots=default_object")
        else:
            for level, slot_default in RUNTIME_OBJECT_DEFAULTS["spellcasting"]["spellSlots"].items():
                if level not in slots or not isinstance(slots[level], dict):
                    slots[level] = copy.deepcopy(slot_default)
                    changes.append(f"spellcasting.spellSlots.{level}=default_object")
                else:
                    for nested_field, nested_default in slot_default.items():
                        if nested_field not in slots[level] or not isinstance(slots[level][nested_field], int):
                            slots[level][nested_field] = nested_default
                            changes.append(f"spellcasting.spellSlots.{level}.{nested_field}=default_scalar")

        return repaired, changes

    # Startup mode: narrow, deterministic repair for stable mechanical defaults.
    for field, default in STARTUP_ARRAY_DEFAULTS.items():
        _ensure_list(repaired, field, default, changes)

    for field, default in STARTUP_OBJECT_DEFAULTS.items():
        _ensure_object(repaired, field, default, changes)
        for nested_field, nested_default in default.items():
            _ensure_scalar(repaired[field], nested_field, nested_default, changes)

    _ensure_numeric_minimum(repaired, "proficiencyBonus", 2, changes)
    _ensure_numeric_minimum(repaired, "experience_points", 0, changes)
    if "exp_required_for_next_level" not in repaired or not isinstance(repaired["exp_required_for_next_level"], int):
        repaired["exp_required_for_next_level"] = 300
        changes.append("exp_required_for_next_level=default_scalar")

    return repaired, changes


def repair_startup_character_sheet(character_data: Any) -> Tuple[Any, List[str]]:
    """Repair a startup character sheet with startup-safe defaults."""
    return repair_character_sheet(character_data, mode="startup")


def repair_runtime_character_sheet(
    character_data: Any,
    *,
    character_role: Optional[str] = None,
    character_type: Optional[str] = None,
) -> Tuple[Any, List[str]]:
    """Repair a runtime character sheet so read-time consumers cannot crash."""
    return repair_character_sheet(
        character_data,
        mode="runtime",
        character_role=character_role,
        character_type=character_type,
    )


def normalize_for_startup(character_data: Any) -> Tuple[Any, List[str]]:
    """Backward-compatible alias for startup repair."""
    return repair_startup_character_sheet(character_data)


def normalize_for_runtime(
    character_data: Any,
    *,
    character_role: Optional[str] = None,
    character_type: Optional[str] = None,
) -> Tuple[Any, List[str]]:
    """Backward-compatible alias for runtime repair."""
    return repair_runtime_character_sheet(
        character_data,
        character_role=character_role,
        character_type=character_type,
    )


def repair_and_persist_character(
    character_file_path: str,
    character_type: str = "player",
) -> Optional[Tuple[Dict[str, Any], List[str]]]:
    """Load a character file, repair it, and persist fixes back to disk.

    This is the startup repair function that ensures legacy characters
    are fixed permanently, not just in-memory.

    Args:
        character_file_path: Absolute or relative path to character JSON file
        character_type: "player" or "npc" for role-specific defaults

    Returns:
        Tuple of (repaired_data, list_of_changes) if successful
        None if file doesn't exist or is invalid JSON
    """
    # Load character file
    if not os.path.exists(character_file_path):
        return None

    character_data = safe_read_json(character_file_path)
    if not character_data:
        return None

    # Run repair (runtime mode - comprehensive repairs for game execution)
    repaired_data, raw_changes = normalize_for_runtime(character_data, character_type=character_type)

    # Extract field names from changes (e.g., "ammunition=default_list" -> "ammunition")
    changes = [change.split("=", 1)[0] for change in raw_changes]

    # Only persist if there were actual changes
    if changes:
        if not safe_write_json(character_file_path, repaired_data):
            # Write failed, but still return in-memory repair
            warning(
                f"REPAIR: Could not persist repairs to {character_file_path}",
                category="character_repair",
            )
        else:
            info(
                f"REPAIR: Persisted {len(changes)} fixes to {character_file_path}: {', '.join(raw_changes)}",
                category="character_repair",
            )

    return repaired_data, changes
