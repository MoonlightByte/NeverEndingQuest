# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Deterministic Mechanics Precheck
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Deterministic guardrails for explicit mechanics contradictions in
updateCharacterInfo changes before LLM validation.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Tuple


CharacterLoader = Callable[[str], Optional[Dict[str, Any]]]


_HP_PATTERNS = [
    re.compile(r"\bHP\s*(-?\d+)\s*->\s*(-?\d+)\b", re.IGNORECASE),
    re.compile(r"\bhit\s*points?\s*(-?\d+)\s*->\s*(-?\d+)\b", re.IGNORECASE),
]
_HP_EXPLICIT_VALUE_PATTERN = re.compile(
    r"\bHP\s*(?:now|to|=|:)?\s*(-?\d+)\b(?!\s*->)",
    re.IGNORECASE,
)
_SLOT_RATIO_PATTERN = re.compile(r"slots?\s*(?:to|:)\s*(-?\d+)\s*/\s*(-?\d+)", re.IGNORECASE)
_REMOVE_PATTERN = re.compile(
    r"\bremov(?:e|ed)\s+(\d+)\s+([a-zA-Z][a-zA-Z0-9\-\' ]+?)\s+from\s+(?:inventory|equipment|pack)\b",
    re.IGNORECASE,
)
_UNCONSCIOUS_PATTERN = re.compile(r"\bunconscious\b", re.IGNORECASE)
_UNCONSCIOUS_NEGATION_PATTERN = re.compile(r"\bnot\s+unconscious\b", re.IGNORECASE)
_CANTRIP_SLOT_SPEND_PATTERNS = [
    re.compile(
        r"\bcantrip\b.*\b(?:expen(?:d|ded)|spen(?:d|t)|use(?:d)?|consum(?:e|ed)|deduct(?:ed)?)\b.*\bspell\s+slots?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:expen(?:d|ded)|spen(?:d|t)|use(?:d)?|consum(?:e|ed)|deduct(?:ed)?)\b.*\bspell\s+slots?\b.*\bcantrip\b",
        re.IGNORECASE,
    ),
]
_CANTRIP_SLOT_NEGATION_PATTERN = re.compile(
    r"\b(?:no|without)\s+(?:expending\s+)?(?:a\s+)?spell\s+slots?\b",
    re.IGNORECASE,
)
_SLOT_SPEND_PATTERN = re.compile(
    r"\b(?:expen(?:d|ded)|spen(?:d|t)|use(?:d)?|consum(?:e|ed)|deduct(?:ed)?)\s+"
    r"(?:(\d+|one|two|three|four|five|six|seven|eight|nine|a|an)\s+)?"
    r"(?:(\d+)(?:st|nd|rd|th)?[-\s]*level|level\s*(\d+)|lvl\s*(\d+))\s+spell\s+slots?\b",
    re.IGNORECASE,
)
_AMMO_SPEND_PATTERN = re.compile(
    r"\b(?:fired?|shoots?|shot|loosed?|spen(?:d|t)|use(?:d)?|consum(?:e|ed))\s+"
    r"(\d+)\s+([a-zA-Z][a-zA-Z0-9\-\' ]{1,40}?)(?:\s+(?:at|into|toward|towards|on|from)\b|[\.,;!]|$)",
    re.IGNORECASE,
)
_REST_DURATION_PATTERN = re.compile(
    r"\b(short|long)\s+rest(?:ed|ing)?(?:\s+for)?\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)

_NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}


def _normalize_token(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]", "", value.lower())
    if cleaned.endswith("s") and len(cleaned) > 1:
        return cleaned[:-1]
    return cleaned


def _extract_hp_targets(changes: str) -> List[int]:
    targets: List[int] = []
    for pattern in _HP_PATTERNS:
        for match in pattern.finditer(changes):
            try:
                targets.append(int(match.group(2)))
            except (TypeError, ValueError):
                continue
    return targets


def _extract_hp_explicit_values(changes: str) -> List[int]:
    values: List[int] = []
    for match in _HP_EXPLICIT_VALUE_PATTERN.finditer(changes):
        try:
            values.append(int(match.group(1)))
        except (TypeError, ValueError):
            continue
    return values


def _extract_slot_ratios(changes: str) -> List[Tuple[int, int]]:
    ratios: List[Tuple[int, int]] = []
    for match in _SLOT_RATIO_PATTERN.finditer(changes):
        try:
            ratios.append((int(match.group(1)), int(match.group(2))))
        except (TypeError, ValueError):
            continue
    return ratios


def _extract_removals(changes: str) -> List[Tuple[int, str]]:
    removals: List[Tuple[int, str]] = []
    for match in _REMOVE_PATTERN.finditer(changes):
        try:
            quantity = int(match.group(1))
        except (TypeError, ValueError):
            continue
        item_name = match.group(2).strip()
        if item_name:
            removals.append((quantity, item_name))
    return removals


def _extract_ammo_spends(changes: str) -> List[Tuple[int, str]]:
    spends: List[Tuple[int, str]] = []
    for match in _AMMO_SPEND_PATTERN.finditer(changes):
        try:
            quantity = int(match.group(1))
        except (TypeError, ValueError):
            continue
        item_name = match.group(2).strip()
        if quantity > 0 and item_name:
            spends.append((quantity, item_name))
    return spends


def _resolve_quantity_token(quantity_token: Optional[str]) -> int:
    if quantity_token is None:
        return 1
    token = quantity_token.strip().lower()
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token, 1)


def _extract_slot_spends(changes: str) -> List[Tuple[int, int]]:
    spends: List[Tuple[int, int]] = []
    for match in _SLOT_SPEND_PATTERN.finditer(changes):
        quantity = _resolve_quantity_token(match.group(1))
        level_token = match.group(2) or match.group(3) or match.group(4)
        try:
            level = int(level_token)
        except (TypeError, ValueError):
            continue
        if quantity > 0 and level > 0:
            spends.append((quantity, level))
    return spends


def _has_explicit_unconscious_state(changes: str) -> bool:
    if not _UNCONSCIOUS_PATTERN.search(changes):
        return False
    if _UNCONSCIOUS_NEGATION_PATTERN.search(changes):
        return False
    return True


def _has_explicit_cantrip_slot_spend(changes: str) -> bool:
    if "cantrip" not in changes.lower():
        return False
    if _CANTRIP_SLOT_NEGATION_PATTERN.search(changes):
        return False
    for pattern in _CANTRIP_SLOT_SPEND_PATTERNS:
        if pattern.search(changes):
            return True
    return False


def _duration_to_minutes(duration_value: int, duration_unit: str) -> int:
    unit = duration_unit.lower()
    if unit.startswith("hour") or unit.startswith("hr"):
        return duration_value * 60
    return duration_value


def _extract_rest_durations_from_text(text: str) -> List[Tuple[str, int]]:
    rest_durations: List[Tuple[str, int]] = []
    for match in _REST_DURATION_PATTERN.finditer(text):
        rest_type = match.group(1).strip().lower()
        try:
            duration_raw = int(match.group(2))
        except (TypeError, ValueError):
            continue
        duration_minutes = _duration_to_minutes(duration_raw, match.group(3))
        rest_durations.append((rest_type, duration_minutes))
    return rest_durations


def _lookup_known_item_quantity(character_data: Dict[str, Any], item_name: str) -> Optional[int]:
    target = _normalize_token(item_name)

    ammunition = character_data.get("ammunition", [])
    for entry in ammunition:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", ""))
        quantity = entry.get("quantity", 0)
        if _normalize_token(name) == target:
            try:
                return int(quantity)
            except (TypeError, ValueError):
                return 0

    equipment = character_data.get("equipment", [])
    for entry in equipment:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("item_name") or entry.get("name") or "")
        quantity = entry.get("quantity", 1)
        if _normalize_token(name) == target:
            try:
                return int(quantity)
            except (TypeError, ValueError):
                return 0

    return None


def _lookup_known_ammo_quantity(character_data: Dict[str, Any], item_name: str) -> Optional[int]:
    target = _normalize_token(item_name)
    ammunition = character_data.get("ammunition", [])
    for entry in ammunition:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", ""))
        if _normalize_token(name) != target:
            continue
        quantity = entry.get("quantity", 0)
        try:
            return int(quantity)
        except (TypeError, ValueError):
            return 0
    return None


def _lookup_known_spell_slot_current(character_data: Dict[str, Any], level: int) -> Optional[int]:
    spellcasting = character_data.get("spellcasting")
    if not isinstance(spellcasting, dict):
        return None

    spell_slots = spellcasting.get("spellSlots") or spellcasting.get("spell_slots")
    if not isinstance(spell_slots, dict):
        return None

    candidate_keys = [
        f"level{level}",
        f"level_{level}",
        f"lvl{level}",
        str(level),
    ]
    for key in candidate_keys:
        if key not in spell_slots:
            continue
        slot_data = spell_slots.get(key)
        if isinstance(slot_data, dict):
            current_value = slot_data.get("current")
        else:
            current_value = slot_data
        if current_value is None:
            return None
        try:
            return int(str(current_value))
        except (TypeError, ValueError):
            return None
    return None


def _extract_rest_duration_from_parameters(parameters: Dict[str, Any]) -> Optional[int]:
    if not isinstance(parameters, dict):
        return None

    duration_minutes = parameters.get("durationMinutes")
    if isinstance(duration_minutes, int):
        return duration_minutes

    duration_hours = parameters.get("durationHours")
    if isinstance(duration_hours, int):
        return duration_hours * 60

    duration_text = parameters.get("duration")
    if isinstance(duration_text, str):
        durations = _extract_rest_durations_from_text(duration_text)
        if durations:
            return durations[0][1]

    return None


def _default_character_loader(character_name: str) -> Optional[Dict[str, Any]]:
    try:
        from utils.pc_manager import get_character_state

        return get_character_state(character_name)
    except Exception:
        return None


def validate_deterministic_mechanics_precheck(
    response_json: Dict[str, Any],
    party_tracker_data: Optional[Dict[str, Any]] = None,
    character_loader: Optional[CharacterLoader] = None,
) -> Tuple[bool, str]:
    """Validate explicit mechanics contradictions in updateCharacterInfo actions.

    This check is intentionally bounded. It only rejects explicit, parseable
    contradictions and fails open for ambiguous or unparseable text.
    """
    del party_tracker_data

    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return True, ""

    loader = character_loader or _default_character_loader

    narration = response_json.get("narration")
    if isinstance(narration, str):
        for rest_type, duration_minutes in _extract_rest_durations_from_text(narration):
            if rest_type == "short" and duration_minutes < 60:
                return False, (
                    f"Deterministic mechanics precheck failed: short rest duration {duration_minutes} minutes "
                    f"is below minimum 60 minutes."
                )
            if rest_type == "long" and duration_minutes < 480:
                return False, (
                    f"Deterministic mechanics precheck failed: long rest duration {duration_minutes} minutes "
                    f"is below minimum 480 minutes."
                )

    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action") == "rest":
            parameters = action.get("parameters", {})
            if not isinstance(parameters, dict):
                continue
            rest_type = str(parameters.get("type", "")).strip().lower()
            duration_minutes = _extract_rest_duration_from_parameters(parameters)
            if duration_minutes is None:
                continue
            if rest_type == "short" and duration_minutes < 60:
                return False, (
                    f"Deterministic mechanics precheck failed: short rest duration {duration_minutes} minutes "
                    f"is below minimum 60 minutes."
                )
            if rest_type == "long" and duration_minutes < 480:
                return False, (
                    f"Deterministic mechanics precheck failed: long rest duration {duration_minutes} minutes "
                    f"is below minimum 480 minutes."
                )
            continue

        if action.get("action") != "updateCharacterInfo":
            continue

        parameters = action.get("parameters", {})
        if not isinstance(parameters, dict):
            continue

        character_name = str(parameters.get("characterName", "")).strip()
        changes = parameters.get("changes")
        if not character_name or not isinstance(changes, str):
            continue

        character_data = loader(character_name)
        if not isinstance(character_data, dict):
            # Fail-open: cannot verify this character deterministically.
            continue

        max_hp = character_data.get("maxHitPoints")
        try:
            max_hp_value = int(max_hp) if max_hp is not None else None
        except (TypeError, ValueError):
            max_hp_value = None

        for target_hp in _extract_hp_targets(changes):
            if target_hp < 0:
                return False, f"Deterministic mechanics precheck failed: HP target below 0 for {character_name}."
            if max_hp_value is not None and target_hp > max_hp_value:
                return False, (
                    f"Deterministic mechanics precheck failed: HP target {target_hp} exceeds "
                    f"maxHitPoints {max_hp_value} for {character_name}."
                )

        if _has_explicit_unconscious_state(changes):
            explicit_hp_values = _extract_hp_targets(changes) + _extract_hp_explicit_values(changes)
            for explicit_hp in explicit_hp_values:
                if explicit_hp > 0:
                    return False, (
                        f"Deterministic mechanics precheck failed: Explicit unconscious state conflicts "
                        f"with HP {explicit_hp} above 0 for {character_name}."
                    )

        if _has_explicit_cantrip_slot_spend(changes):
            return False, (
                f"Deterministic mechanics precheck failed: Cantrip slot spend contradiction for {character_name}."
            )

        for spend_qty, level in _extract_slot_spends(changes):
            known_current = _lookup_known_spell_slot_current(character_data, level)
            if known_current is None:
                continue
            if spend_qty > known_current:
                return False, (
                    f"Deterministic mechanics precheck failed: Spell-slot underflow for level {level} "
                    f"({spend_qty} spent, {known_current} available) for {character_name}."
                )

        for current_slots, max_slots in _extract_slot_ratios(changes):
            if current_slots < 0 or max_slots < 0:
                return False, (
                    f"Deterministic mechanics precheck failed: Negative spell-slot ratio "
                    f"{current_slots}/{max_slots} for {character_name}."
                )
            if current_slots > max_slots:
                return False, (
                    f"Deterministic mechanics precheck failed: Spell-slot ratio "
                    f"{current_slots}/{max_slots} is invalid for {character_name}."
                )

        for remove_qty, item_name in _extract_removals(changes):
            known_qty = _lookup_known_item_quantity(character_data, item_name)
            if known_qty is None:
                # Fail-open when deterministic item matching is unavailable.
                continue
            if remove_qty > known_qty:
                return False, (
                    f"Deterministic mechanics precheck failed: Removed {remove_qty} {item_name} but "
                    f"only {known_qty} known for {character_name}."
                )

        for spend_qty, ammo_name in _extract_ammo_spends(changes):
            known_ammo_qty = _lookup_known_ammo_quantity(character_data, ammo_name)
            if known_ammo_qty is None:
                # Fail-open when ammunition match cannot be established.
                continue
            if spend_qty > known_ammo_qty:
                return False, (
                    f"Deterministic mechanics precheck failed: Spent {spend_qty} {ammo_name} but "
                    f"only {known_ammo_qty} tracked for {character_name}."
                )

    return True, ""
