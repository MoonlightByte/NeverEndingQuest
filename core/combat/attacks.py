# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Deterministic, backward-compatible attack-sequence selection."""

import re


MAX_MULTIATTACK_SWINGS = 8
DEFAULT_UNKNOWN_MULTIATTACK_SWINGS = 2
_DAMAGE_DICE = re.compile(
    r"^\s*[1-9]\d*d(?:4|6|8|10|12|20|100)(?:\s*[+-]\s*\d+)?\s*$", re.I
)


def action_entries(sheet):
    """Return the first supported action-list shape from a character/stat block."""
    for field in ("attacksAndSpellcasting", "actions", "attacks"):
        entries = (sheet or {}).get(field)
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    return []


def is_multiattack_marker(entry):
    return (
        isinstance(entry, dict)
        and str(entry.get("name") or "").strip().casefold() == "multiattack"
    )


def is_executable_attack(entry):
    """True only when code has enough persisted data to roll attack and damage."""
    if not isinstance(entry, dict) or is_multiattack_marker(entry):
        return False
    return bool(_DAMAGE_DICE.fullmatch(str(entry.get("damageDice") or "")))


def executable_attack_names(sheet):
    return [
        entry.get("name")
        for entry in action_entries(sheet)
        if is_executable_attack(entry) and entry.get("name")
    ]


def _find(entries, name):
    wanted = str(name or "").strip().casefold()
    return next(
        (
            entry
            for entry in entries
            if is_executable_attack(entry)
            and str(entry.get("name") or "").strip().casefold() == wanted
        ),
        None,
    )


def _explicit_sequence(sheet, marker, override):
    value = override
    if value is None:
        value = (sheet or {}).get("multiattackSequence")
    if value is None and marker:
        value = marker.get("multiattackSequence", marker.get("sequence"))
    return value if isinstance(value, list) else None


def _expand_sequence(entries, specification):
    if not specification:
        return None
    result = []
    for item in specification:
        if isinstance(item, str):
            name, count = item, 1
        elif isinstance(item, dict):
            name, count = item.get("name"), item.get("count", 1)
        else:
            return None
        if type(count) is not int or not 1 <= count <= MAX_MULTIATTACK_SWINGS:
            return None
        entry = _find(entries, name)
        if entry is None:
            return None
        result.extend([entry] * count)
        if len(result) >= MAX_MULTIATTACK_SWINGS:
            return result[:MAX_MULTIATTACK_SWINGS]
    return result or None


def _explicit_count(sheet, marker, override):
    values = (
        override,
        (sheet or {}).get("numAttacks"),
        marker.get("numAttacks") if marker else None,
        marker.get("attackCount") if marker else None,
    )
    for value in values:
        if type(value) is int:
            return max(1, min(MAX_MULTIATTACK_SWINGS, value))
    return None


def attack_sequence(
    sheet,
    selected_name=None,
    num_attacks=None,
    sequence=None,
):
    """Return an exact or safely bounded sequence of executable attack rows.

    Precision fields are additive and optional for old modules. When an old
    stat block contains only a blank Multiattack marker, two swings is the
    measured SRD-default fallback. Code fills distinct attacks in sheet order
    so a weak model cannot double its highest-damage choice. Repetition is used
    only when no distinct executable row remains.
    """
    entries = action_entries(sheet)
    executable = [entry for entry in entries if is_executable_attack(entry)]
    if not executable:
        return []
    marker = next((entry for entry in entries if is_multiattack_marker(entry)), None)

    exact = _expand_sequence(
        executable,
        _explicit_sequence(sheet, marker, sequence),
    )
    if exact:
        return exact

    count = _explicit_count(sheet, marker, num_attacks)
    if count is None:
        count = DEFAULT_UNKNOWN_MULTIATTACK_SWINGS if marker else 1

    selected = _find(executable, selected_name) or executable[0]
    result = [selected]
    for entry in executable:
        if len(result) >= count:
            break
        if entry is not selected:
            result.append(entry)
    cursor = 0
    while len(result) < count:
        result.append(executable[cursor % len(executable)])
        cursor += 1
    return result
