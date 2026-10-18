# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Deterministic, backward-compatible attack-sequence selection."""

import re


DEFAULT_UNKNOWN_MULTIATTACK_SWINGS = 2
_DAMAGE_DICE = re.compile(
    r"^\s*[1-9]\d*d(?:4|6|8|10|12|20|100)(?:\s*[+-]\s*\d+)?\s*$", re.I
)
# Flat damage (NUM-H3c): an engine row such as Unarmed Strike writes "flat" with
# its whole damage in damageBonus. ("0d0" stays the no-roll marker of monster
# save, trait and Multiattack entries, which are not executable attacks.)
FLAT_DAMAGE_DICE = "flat"


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
    return bool(_DAMAGE_DICE.fullmatch(str(entry.get("damageDice") or ""))) or is_flat_attack(entry)


def is_flat_attack(entry):
    """True for a flat-damage row: damageDice exactly "flat"."""
    return isinstance(entry, dict) and str(entry.get("damageDice") or "").strip() == FLAT_DAMAGE_DICE


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


def typed_multiattack_issue(sheet):
    """The reason a stat block's Multiattack is not typed, or None.

    Builders refuse a block this names, so no new block plays the blank-marker
    fallback: a Multiattack entry needs the top-level multiattackSequence, and
    every item names an executable entry, resolved exactly as attack_sequence
    resolves it (_find). Item shape and counts are the schema's
    (mon_schema multiattackSequence).
    """
    entries = action_entries(sheet)
    sequence = (sheet or {}).get("multiattackSequence")
    if sequence is None:
        if any(is_multiattack_marker(entry) for entry in entries):
            return (
                "the Multiattack entry needs a top-level multiattackSequence: "
                "one {name, count} per component attack, naming this monster's "
                "own attack entries"
            )
        return None
    if not isinstance(sequence, list):
        return "multiattackSequence must be a list of {name, count}"
    attacks = [entry.get("name") for entry in entries if is_executable_attack(entry)]
    for index, item in enumerate(sequence):
        name = item.get("name") if isinstance(item, dict) else None
        if _find(entries, name) is None:
            return (
                "multiattackSequence item %d names %r, which is not one of this "
                "monster's attack entries %s" % (index, name, attacks)
            )
    return None


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
        if type(count) is not int or count < 1:
            return None
        entry = _find(entries, name)
        if entry is None:
            return None
        result.extend([entry] * count)
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
            return max(1, value)
    return None


def _warn_unresolved_sequence(sheet, specification):
    """MA-4: a typed sequence combat cannot play is never dropped silently."""
    from utils.enhanced_logger import warning as _warning

    _warning(
        "MA: %s multiattackSequence %r names no playable attack list "
        "(an unknown attack name or a count below 1); the count rules apply"
        % ((sheet or {}).get("name"), specification),
        category="combat",
    )


def attack_sequence(
    sheet,
    selected=None,
    num_attacks=None,
    sequence=None,
):
    """Return the exact typed sequence of executable attack rows, or the count.

    The typed count stands (owner D-MA-3): no swing ceiling. A typed sequence
    that does not resolve is logged, then the count rules below apply.
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

    specification = _explicit_sequence(sheet, marker, sequence)
    exact = _expand_sequence(executable, specification)
    if exact:
        return exact
    if specification:
        _warn_unresolved_sequence(sheet, specification)

    count = _explicit_count(sheet, marker, num_attacks)
    if count is None:
        count = DEFAULT_UNKNOWN_MULTIATTACK_SWINGS if marker else 1

    # K1: the chosen row itself (found by its typed position), never a name.
    selected = next((entry for entry in executable if entry is selected), None) or executable[0]
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
