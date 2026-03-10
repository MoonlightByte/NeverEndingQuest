# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Validator Truth Pack
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Build compact mechanics-first validation context for touched characters.
"""

import json
from typing import Any, Callable, Dict, List, Optional


CharacterLoader = Callable[[str], Optional[Dict[str, Any]]]


_INVENTORY_KEYWORDS = (
    "inventory",
    "item",
    "equipment",
    "ammo",
    "ammunition",
    "arrow",
    "bolt",
    "potion",
    "coin",
    "gold",
    "silver",
    "copper",
    "buy",
    "sell",
    "trade",
    "loot",
    "remove",
    "add",
)

_NON_INVENTORY_HINTS = (
    "hp",
    "hit point",
    "spell slot",
    "slot",
    "condition",
    "death save",
    "level",
    "exhaustion",
    "stabil",
    "unconscious",
)


def _default_character_loader(character_name: str) -> Optional[Dict[str, Any]]:
    try:
        from utils.pc_manager import get_character_state

        return get_character_state(character_name)
    except Exception:
        return None


def _is_inventory_relevant_change(change_text: str) -> bool:
    lower = change_text.lower()
    if any(keyword in lower for keyword in _INVENTORY_KEYWORDS):
        return True
    if any(keyword in lower for keyword in _NON_INVENTORY_HINTS):
        return False
    # Ambiguous defaults to inventory-included for fail-open safety.
    return True


def _summarize_spell_slots(character_data: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    spell_slots = character_data.get("spellSlots", {})
    summary: Dict[str, Dict[str, int]] = {}
    if isinstance(spell_slots, dict):
        for level, slot_data in spell_slots.items():
            if not isinstance(slot_data, dict):
                continue
            current = slot_data.get("current", 0)
            maximum = slot_data.get("max", 0)
            try:
                summary[str(level)] = {
                    "current": int(current),
                    "max": int(maximum),
                }
            except (TypeError, ValueError):
                continue
    return summary


def _summarize_death_saves(character_data: Dict[str, Any]) -> Dict[str, int]:
    death_saves = character_data.get("deathSaves")
    if isinstance(death_saves, dict):
        successes = death_saves.get("successes", 0)
        failures = death_saves.get("failures", 0)
    else:
        successes = character_data.get("deathSaveSuccesses", 0)
        failures = character_data.get("deathSaveFailures", 0)

    try:
        return {
            "successes": int(successes),
            "failures": int(failures),
        }
    except (TypeError, ValueError):
        return {"successes": 0, "failures": 0}


def _summarize_class_features(character_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    features = character_data.get("classFeatures", [])
    summary: List[Dict[str, Any]] = []
    if not isinstance(features, list):
        return summary

    for feature in features:
        if not isinstance(feature, dict):
            continue
        name = feature.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        item: Dict[str, Any] = {"name": name.strip()}
        for key in ("uses", "maxUses", "currentUses", "recharge"):
            if key in feature:
                item[key] = feature.get(key)
        summary.append(item)
    return summary


def _summarize_inventory(character_data: Dict[str, Any]) -> Dict[str, Any]:
    currency = character_data.get("currency", {})
    if not isinstance(currency, dict):
        currency = {}

    ammunition = character_data.get("ammunition", [])
    ammo_summary: List[Dict[str, Any]] = []
    if isinstance(ammunition, list):
        for ammo in ammunition:
            if not isinstance(ammo, dict):
                continue
            name = ammo.get("name", "Unknown")
            quantity = ammo.get("quantity", 0)
            ammo_summary.append({"name": str(name), "quantity": quantity})

    equipment = character_data.get("equipment", [])
    equipment_summary: List[Dict[str, Any]] = []
    if isinstance(equipment, list):
        for item in equipment[:12]:
            if not isinstance(item, dict):
                continue
            name = item.get("item_name") or item.get("name") or "Unknown"
            quantity = item.get("quantity", 1)
            equipment_summary.append({"name": str(name), "quantity": quantity})

    return {
        "currency": {
            "gold": int(currency.get("gold", 0) or 0),
            "silver": int(currency.get("silver", 0) or 0),
            "copper": int(currency.get("copper", 0) or 0),
        },
        "ammunition": ammo_summary,
        "equipment": equipment_summary,
    }


def build_touched_character_truth_pack(
    response_json: Dict[str, Any],
    character_loader: Optional[CharacterLoader] = None,
) -> List[Dict[str, Any]]:
    """Build compact truth packs for touched updateCharacterInfo actions."""
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return []

    touched_changes: Dict[str, Dict[str, Any]] = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action") != "updateCharacterInfo":
            continue

        params = action.get("parameters", {})
        if not isinstance(params, dict):
            continue

        character_name = str(params.get("characterName", "")).strip()
        changes = params.get("changes")
        if not character_name:
            continue

        if character_name not in touched_changes:
            touched_changes[character_name] = {
                "changes": [],
                "inventory_relevant": False,
            }

        if isinstance(changes, str) and changes.strip():
            touched_changes[character_name]["changes"].append(changes.strip())
            if _is_inventory_relevant_change(changes):
                touched_changes[character_name]["inventory_relevant"] = True

    if not touched_changes:
        return []

    loader = character_loader or _default_character_loader
    truth_packs: List[Dict[str, Any]] = []

    for character_name, meta in touched_changes.items():
        character_data = loader(character_name)
        if not isinstance(character_data, dict):
            continue

        hp = character_data.get("hitPoints", 0)
        max_hp = character_data.get("maxHitPoints", 0)
        conditions = character_data.get("condition_affected", [])
        if not isinstance(conditions, list):
            conditions = []

        pack: Dict[str, Any] = {
            "character_name": str(character_data.get("name") or character_name),
            "hp": int(hp or 0),
            "max_hp": int(max_hp or 0),
            "conditions": [str(cond) for cond in conditions],
            "spell_slots": _summarize_spell_slots(character_data),
            "death_saves": _summarize_death_saves(character_data),
            "class_features": _summarize_class_features(character_data),
            "touched_changes": meta.get("changes", []),
        }

        if meta.get("inventory_relevant", False):
            pack["inventory"] = _summarize_inventory(character_data)

        truth_packs.append(pack)

    return truth_packs


def format_truth_pack_for_validation(truth_packs: List[Dict[str, Any]]) -> str:
    """Format truth packs for validator context."""
    if not truth_packs:
        return ""
    return "\n\nCHARACTER_MECHANICAL_TRUTH_PACK:\n" + json.dumps(
        truth_packs,
        indent=2,
        ensure_ascii=False,
    )
