# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure effective-stat overlays for declarative effects."""

from copy import deepcopy

from core.effects.model import canonical_stat


def _live_effects(sheet):
    if not isinstance(sheet, dict):
        return []
    return [
        effect
        for effect in sheet.get("temporaryEffects", []) or []
        if isinstance(effect, dict)
        and effect.get("authoredBy") in ("engine", "classifier")
        and isinstance(effect.get("modifiers", []), list)
    ]


def modifier_total(sheet, stat):
    canonical = canonical_stat(stat)
    if canonical is None:
        return 0
    total = 0
    for effect in _live_effects(sheet):
        for modifier in effect.get("modifiers", []):
            if not isinstance(modifier, dict):
                continue
            if canonical_stat(modifier.get("stat")) == canonical:
                value = modifier.get("value")
                if type(value) in (int, float):
                    total += int(value)
            if (
                canonical == "maxHitPoints"
                and canonical_stat(modifier.get("stat")) == "hitPoints"
                and modifier.get("affectsMax") is True
            ):
                value = modifier.get("value")
                if type(value) in (int, float):
                    total += int(value)
    return total


def _get_path(data, path):
    current = data
    parts = path.split(".")
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_path(data, path, value):
    current = data
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def effective_sheet(sheet):
    """Return a copy with declarative numeric modifiers rendered into fields."""
    result = deepcopy(sheet or {})
    paths = set()
    for effect in _live_effects(sheet):
        for modifier in effect.get("modifiers", []):
            canonical = canonical_stat(modifier.get("stat")) if isinstance(modifier, dict) else None
            if canonical and canonical not in (
                "attackRolls",
                "damageRolls",
                "abilityChecks",
                "savingThrows",
                "initiative",
                "spellSaveDC",
                "spellAttackBonus",
            ) and not canonical.startswith(("savingThrow.", "abilityCheck.")):
                paths.add(canonical)
            if canonical == "hitPoints" and modifier.get("affectsMax") is True:
                paths.add("maxHitPoints")
    for path in paths:
        base = _get_path(sheet, path)
        if type(base) in (int, float):
            _set_path(result, path, int(base) + modifier_total(sheet, path))
    current_hp = result.get("hitPoints")
    maximum_hp = result.get("maxHitPoints")
    if type(current_hp) is int and type(maximum_hp) is int:
        result["hitPoints"] = max(0, min(current_hp, maximum_hp))
    return result


def storage_delta_from_effective(sheet, delta):
    """Translate T079 effective numeric values back to stored base values."""
    result = deepcopy(delta or {})
    for path in ("armorClass", "speed", "hitPoints", "maxHitPoints"):
        if type(result.get(path)) in (int, float):
            result[path] = int(result[path]) - modifier_total(sheet, path)
    abilities = result.get("abilities")
    if isinstance(abilities, dict):
        for ability, value in list(abilities.items()):
            if type(value) in (int, float):
                abilities[ability] = int(value) - modifier_total(
                    sheet, "abilities.%s" % ability
                )
    return result
