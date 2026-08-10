# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure effect operations and duration planning."""

from copy import deepcopy
import math

from core.effects.clock import display_iso_from_scalar, scalar_from_display_iso
from core.effects.effective import effective_sheet
from core.effects.model import effect_identity, normalize_effect, validate_effect


def _apply_resource_operations(sheet, operations):
    for operation in operations or []:
        stat = operation.get("stat") if isinstance(operation, dict) else None
        if stat != "hitPoints":
            continue
        before = int(sheet.get(stat, 0) or 0)
        after = before + int(operation.get("delta", 0) or 0)
        minimum = int(operation.get("minimum", 0) or 0)
        maximum = operation.get("maximum")
        after = max(minimum, after)
        if type(maximum) is int:
            after = min(maximum, after)
        sheet[stat] = after


def apply_effect_ops(sheet, operations):
    """Apply idempotent add/remove operations to one copied character sheet."""
    result = deepcopy(sheet or {})
    effects = result.setdefault("temporaryEffects", [])
    if not isinstance(effects, list):
        raise ValueError("temporaryEffects must be an array")
    for operation in operations or []:
        if not isinstance(operation, dict) or operation.get("op") not in ("add", "remove"):
            raise ValueError("effect operation must be add or remove")
        if operation["op"] == "add":
            effect = normalize_effect(operation.get("effect"), default_author="engine")
            problems = validate_effect(effect, require_managed=True)
            if problems:
                raise ValueError("invalid effect: %s" % "; ".join(problems))
            identity = effect_identity(effect)
            index = next(
                (i for i, current in enumerate(effects) if effect_identity(current) == identity),
                None,
            )
            if index is None:
                effects.append(effect)
                _apply_resource_operations(result, effect.get("onApply", []))
            else:
                effects[index] = effect
        else:
            effect_id = operation.get("effectId")
            identity = operation.get("identity")
            name = operation.get("name")
            retained = []
            for current in effects:
                remove = False
                if isinstance(current, dict):
                    if effect_id and current.get("effectId") == effect_id:
                        remove = True
                    elif identity and effect_identity(current) == tuple(identity):
                        remove = True
                    elif not effect_id and not identity and name and current.get("name") == name:
                        remove = True
                if not remove:
                    retained.append(current)
                else:
                    _apply_resource_operations(result, current.get("onRemove", []))
            effects[:] = retained
    # Current HP is a consumed resource. Removing a maximum-HP effect never
    # subtracts a symmetric amount; it only clamps current HP to the newly
    # derived maximum, preserving damage and healing that occurred meanwhile.
    rendered = effective_sheet(result)
    current_hp = result.get("hitPoints")
    maximum_hp = rendered.get("maxHitPoints")
    if type(current_hp) is int and type(maximum_hp) is int:
        result["hitPoints"] = max(0, min(current_hp, maximum_hp))
    return result


def plan_expirations(sheets, now_scalar):
    """Return deterministic remove operations for expired wall-clock effects."""
    planned = []
    for owner, sheet in (sheets or {}).items():
        if not isinstance(sheet, dict):
            continue
        for effect in sheet.get("temporaryEffects", []) or []:
            if not isinstance(effect, dict) or effect.get("roundsRemaining") is not None:
                continue
            expiration = effect.get("expiration")
            if not isinstance(expiration, str) or not expiration.strip():
                continue
            try:
                deadline = scalar_from_display_iso(expiration)
            except ValueError as exc:
                if effect.get("authoredBy") in ("engine", "classifier"):
                    raise ValueError(
                        "managed effect %s for %s has an invalid expiration"
                        % (effect.get("name"), owner)
                    ) from exc
                continue
            if now_scalar >= deadline:
                planned.append(
                    {
                        "owner": owner,
                        "op": "remove",
                        "effectId": effect.get("effectId"),
                        "identity": effect_identity(effect),
                        "name": effect.get("name"),
                        "reason": "expired",
                        "effect": deepcopy(effect),
                    }
                )
    return planned


def plan_rest_clears(owner, sheet, rest_kind):
    planned = []
    for effect in (sheet or {}).get("temporaryEffects", []) or []:
        if not isinstance(effect, dict):
            continue
        effect_rest = effect.get("restKind")
        should_remove = (
            rest_kind == "long_rest" and effect_rest in ("short_rest", "long_rest")
        ) or (rest_kind == "short_rest" and effect_rest == "short_rest")
        if should_remove:
            planned.append(
                {
                    "owner": owner,
                    "op": "remove",
                    "effectId": effect.get("effectId"),
                    "identity": effect_identity(effect),
                    "name": effect.get("name"),
                    "reason": rest_kind,
                    "effect": deepcopy(effect),
                }
            )
    return planned


def enter_combat_effect(effect, now_scalar):
    """Switch one wall-clock effect to the combat-round clock."""
    result = deepcopy(effect)
    expiration = result.get("expiration")
    if result.get("roundsRemaining") is not None:
        if not result.get("tickTrigger"):
            result["tickTrigger"] = "end_of_round"
        return result
    if not expiration:
        return result
    try:
        remaining = max(0, scalar_from_display_iso(expiration) - int(now_scalar))
    except (TypeError, ValueError):
        return result
    result["roundsRemaining"] = int(math.ceil(remaining / 6.0))
    result["durationKind"] = "rounds"
    result.setdefault("created", {})["priorExpiration"] = expiration
    result.pop("expiration", None)
    if not result.get("tickTrigger"):
        result["tickTrigger"] = "end_of_round"
    return result


def exit_combat_effect(effect, now_scalar):
    """Switch one combat-round effect back to the world-time clock."""
    result = deepcopy(effect)
    if result.get("durationKind") == "encounter":
        return None
    rounds = result.get("roundsRemaining")
    if type(rounds) is not int:
        return result
    if rounds <= 0:
        return None
    result["expiration"] = display_iso_from_scalar(int(now_scalar) + rounds * 6)
    result["durationKind"] = "minutes"
    result.pop("roundsRemaining", None)
    result.pop("tickTrigger", None)
    return result
