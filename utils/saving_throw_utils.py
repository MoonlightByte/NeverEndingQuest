# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Utility - Saving throw normalization and fallback helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from typing import Any, Dict, Iterable, Set


ABILITY_KEYS = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)


_ABILITY_ALIASES: Dict[str, str] = {
    "str": "strength",
    "strength": "strength",
    "dex": "dexterity",
    "dexterity": "dexterity",
    "con": "constitution",
    "constitution": "constitution",
    "int": "intelligence",
    "intelligence": "intelligence",
    "wis": "wisdom",
    "wisdom": "wisdom",
    "cha": "charisma",
    "charisma": "charisma",
}


_CLASS_ALIAS_MAP: Dict[str, str] = {
    "thief": "rogue",
}


_CLASS_SAVING_THROW_DEFAULTS: Dict[str, Set[str]] = {
    "barbarian": {"strength", "constitution"},
    "bard": {"dexterity", "charisma"},
    "cleric": {"wisdom", "charisma"},
    "druid": {"intelligence", "wisdom"},
    "fighter": {"strength", "constitution"},
    "monk": {"strength", "dexterity"},
    "paladin": {"wisdom", "charisma"},
    "ranger": {"strength", "dexterity"},
    "rogue": {"dexterity", "intelligence"},
    "sorcerer": {"constitution", "charisma"},
    "warlock": {"wisdom", "charisma"},
    "wizard": {"intelligence", "wisdom"},
}


def _tokenize_alpha(value: str) -> str:
    """Return lowercase letters only for tolerant matching."""
    return "".join(ch for ch in value.lower().strip() if ch.isalpha())


def normalize_saving_throw_proficiencies(saving_throws: Any) -> Set[str]:
    """Normalize saving throw values into canonical ability keys."""
    if not isinstance(saving_throws, Iterable) or isinstance(saving_throws, (str, bytes, dict)):
        return set()

    normalized: Set[str] = set()
    for entry in saving_throws:
        if not isinstance(entry, str):
            continue
        token = _tokenize_alpha(entry)
        canonical = _ABILITY_ALIASES.get(token)
        if canonical:
            normalized.add(canonical)
    return normalized


def _normalize_class_name(class_name: Any) -> str:
    """Normalize class token with basic alias support."""
    if not isinstance(class_name, str):
        return ""

    class_token = _tokenize_alpha(class_name)
    if class_token in _CLASS_SAVING_THROW_DEFAULTS:
        return class_token

    class_token = _CLASS_ALIAS_MAP.get(class_token, class_token)
    if class_token in _CLASS_SAVING_THROW_DEFAULTS:
        return class_token

    return ""


def get_class_fallback_saving_throws(class_name: Any) -> Set[str]:
    """Return deterministic class-based fallback saving throw proficiencies."""
    class_token = _normalize_class_name(class_name)
    if not class_token:
        return set()
    return set(_CLASS_SAVING_THROW_DEFAULTS.get(class_token, set()))


def get_effective_saving_throw_proficiencies(saving_throws: Any, class_name: Any) -> Set[str]:
    """Return normalized proficiencies or class fallback when empty."""
    normalized = normalize_saving_throw_proficiencies(saving_throws)
    if normalized:
        return normalized
    return get_class_fallback_saving_throws(class_name)
