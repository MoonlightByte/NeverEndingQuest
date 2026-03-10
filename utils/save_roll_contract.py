# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Save/Roll Contract Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Deterministic helpers for lightweight requestRoll payload validation and
concentration DC calculation.
"""

from typing import Any, Dict, Tuple


ALLOWED_REQUEST_ROLL_TYPES = {
    "saving_throw",
    "ability_check",
    "skill_check",
}

ALLOWED_ADVANTAGE_VALUES = {
    "normal",
    "advantage",
    "disadvantage",
}


def calculate_concentration_dc(damage: int) -> int:
    """Return 5e concentration DC: max(10, floor(damage / 2))."""
    if not isinstance(damage, int):
        raise TypeError("damage must be an integer")
    if damage < 0:
        raise ValueError("damage must be >= 0")
    return max(10, damage // 2)


def validate_request_roll_parameters(parameters: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate requestRoll payload contract.

    Returns:
        (True, "") when valid.
        (False, "reason") when invalid.
    """
    if not isinstance(parameters, dict):
        return False, "parameters must be an object"

    required_fields = ["characterName", "rollType", "dc", "reason"]
    for field_name in required_fields:
        if field_name not in parameters:
            return False, f"missing required field: {field_name}"

    character_name = parameters.get("characterName")
    if not isinstance(character_name, str) or not character_name.strip():
        return False, "characterName must be a non-empty string"

    roll_type = parameters.get("rollType")
    if roll_type not in ALLOWED_REQUEST_ROLL_TYPES:
        return False, "rollType must be saving_throw, ability_check, or skill_check"

    dc_value = parameters.get("dc")
    if not isinstance(dc_value, int) or dc_value < 0:
        return False, "dc must be an integer >= 0"

    reason = parameters.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return False, "reason must be a non-empty string"

    if roll_type in ("saving_throw", "ability_check"):
        ability = parameters.get("ability")
        if not isinstance(ability, str) or not ability.strip():
            return False, "ability is required for saving_throw and ability_check"

    if roll_type == "skill_check":
        skill = parameters.get("skill")
        if not isinstance(skill, str) or not skill.strip():
            return False, "skill is required for skill_check"

    advantage = parameters.get("advantage")
    if advantage is not None and advantage not in ALLOWED_ADVANTAGE_VALUES:
        return False, "advantage must be normal, advantage, or disadvantage"

    return True, ""
