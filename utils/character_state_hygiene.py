# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Character State Hygiene - deterministic life-state normalization.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from typing import Any, Dict, List


def _coerce_int(value: Any, default: int = 0) -> int:
    """Convert a value to int with safe fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_conditions(raw_conditions: Any) -> List[str]:
    """Return lowercase, deduped conditions preserving order."""
    if not isinstance(raw_conditions, list):
        return []

    normalized: List[str] = []
    seen = set()
    for condition in raw_conditions:
        condition_text = str(condition or "").strip().lower()
        if not condition_text or condition_text in seen:
            continue
        normalized.append(condition_text)
        seen.add(condition_text)
    return normalized


def normalize_life_state_fields(character_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize HP, status, condition, and death-save coherence."""
    if not isinstance(character_data, dict):
        return character_data

    current_hp = _coerce_int(character_data.get("hitPoints", 0), 0)
    status = str(character_data.get("status") or "alive").strip().lower()
    condition = str(character_data.get("condition") or "none").strip().lower()
    if condition == "normal":
        condition = "none"

    conditions = _normalize_conditions(character_data.get("condition_affected", []))

    death_saves_raw = character_data.get("deathSaves")
    if isinstance(death_saves_raw, dict):
        successes = max(0, min(_coerce_int(death_saves_raw.get("successes", 0), 0), 3))
        failures = max(0, min(_coerce_int(death_saves_raw.get("failures", 0), 0), 3))
    else:
        successes = max(0, min(_coerce_int(character_data.get("deathSaveSuccesses", 0), 0), 3))
        failures = max(0, min(_coerce_int(character_data.get("deathSaveFailures", 0), 0), 3))

    if current_hp > 0:
        status = "alive"
        successes = 0
        failures = 0
        conditions = [entry for entry in conditions if entry != "unconscious"]
        if condition == "unconscious":
            condition = conditions[0] if conditions else "none"
        elif condition == "none" and conditions:
            condition = conditions[0]
    elif failures >= 3:
        status = "dead"
        condition = "none"
        conditions = []
    else:
        status = "unconscious"
        condition = "unconscious"
        if "unconscious" not in conditions:
            conditions.append("unconscious")

    if condition != "none" and condition not in conditions:
        conditions.insert(0, condition)
    if condition == "none" and conditions:
        condition = conditions[0]

    character_data["status"] = status
    character_data["condition"] = condition
    character_data["condition_affected"] = conditions
    character_data["deathSaves"] = {
        "successes": successes,
        "failures": failures,
    }
    return character_data
