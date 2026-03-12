# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest XP Progression Utilities
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Deterministic helpers for cumulative XP and next-level threshold handling.
"""

from copy import deepcopy
from typing import Any, Dict, Tuple


XP_BY_LEVEL = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_level(level: Any) -> int:
    return max(1, min(_safe_int(level, 1), 20))


def get_min_xp_for_level(level: Any) -> int:
    """Return cumulative minimum XP required to be at the given level."""
    return XP_BY_LEVEL[_normalize_level(level)]


def get_next_level_threshold(level: Any) -> int:
    """Return cumulative XP required to reach the next level."""
    normalized_level = _normalize_level(level)
    if normalized_level >= 20:
        return 0
    return XP_BY_LEVEL[normalized_level + 1]


def get_level_for_xp(xp: Any) -> int:
    """Return the highest level supported by the provided cumulative XP."""
    normalized_xp = max(0, _safe_int(xp, 0))
    resolved_level = 1
    for level, threshold in sorted(XP_BY_LEVEL.items()):
        if normalized_xp >= threshold:
            resolved_level = level
    return resolved_level


def normalize_xp_progression(character_data: Dict[str, Any], preserve_level: bool = True) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Normalize XP and next-level threshold without auto-leveling.

    Args:
        character_data: Character payload to normalize.
        preserve_level: When True, keep the current level and only repair threshold/XP shape.

    Returns:
        Tuple of (updated_character_data, diagnostics)
    """
    if not isinstance(character_data, dict):
        return character_data, {
            "changed": False,
            "ready_to_level": False,
            "threshold_mismatch": False,
            "below_level_floor": False,
        }

    updated = deepcopy(character_data)
    original_level = _normalize_level(updated.get("level", 1))
    current_level = original_level
    current_xp = max(0, _safe_int(updated.get("experience_points", 0), 0))

    if not preserve_level:
        current_level = get_level_for_xp(current_xp)

    expected_threshold = get_next_level_threshold(current_level)
    current_threshold = _safe_int(updated.get("exp_required_for_next_level", expected_threshold), expected_threshold)

    updated["level"] = current_level
    updated["experience_points"] = current_xp
    updated["exp_required_for_next_level"] = expected_threshold

    diagnostics = {
        "changed": (
            original_level != current_level
            or _safe_int(character_data.get("experience_points", 0), 0) != current_xp
            or current_threshold != expected_threshold
        ),
        "ready_to_level": bool(expected_threshold and current_xp >= expected_threshold),
        "threshold_mismatch": current_threshold != expected_threshold,
        "below_level_floor": current_xp < get_min_xp_for_level(current_level),
        "expected_next_level_threshold": expected_threshold,
    }

    return updated, diagnostics
