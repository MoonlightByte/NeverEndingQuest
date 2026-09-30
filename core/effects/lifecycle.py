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


def _engine_holds(effect):
    """True when the engine can hold this effect's armor class / max HP numbers."""
    from core.nql import genesis

    return bool(
        isinstance(effect, dict)
        and effect.get("authoredBy") in genesis.EFFECT_AUTHORS
        and isinstance(effect.get("effectId"), str)
        and effect.get("effectId")
        and genesis.effect_engine_modifiers(effect)
    )


def _reconcile_with_engine(result, removed_owned):
    """Hold pending effects in the engine and end the removed owned ones (E12a).

    The engine writes armorClass, maxHitPoints and hitPoints; a removed
    engineOwned effect is taken off the stored numbers even when the engine
    cannot run, so the sheet never keeps a bonus whose effect ended.
    """
    from core.nql import effects as nql_effects
    from core.nql import genesis
    from utils.enhanced_logger import debug, warning

    outcome = nql_effects.reconcile(result, removed_owned)
    if outcome.ok:
        if outcome.applied or outcome.ended:
            debug(
                "[Effects Engine] %s: applied %s, ended %s"
                % (result.get("name"), outcome.applied, outcome.ended),
                category="effects_tracking",
            )
        return outcome.sheet
    warning(
        "[Effects Engine] %s: sheet numbers left to the overlay: %s"
        % (result.get("name"), outcome.reason),
        category="effects_tracking",
    )
    handled = nql_effects.fallback_unbake(result, removed_owned)
    if handled:
        warning(
            "[Effects Engine] %s: ended effects taken off the stored numbers without the engine: %s"
            % (result.get("name"), handled),
            category="effects_tracking",
        )
    for effect in removed_owned:
        effect.pop(genesis.EFFECT_ENGINE_OWNED, None)
    return result


def apply_effect_ops(sheet, operations, *, engine=True):
    """Apply idempotent add/remove operations to one copied character sheet.

    With ``engine`` true (a durable character sheet) the armor class and
    maximum hit point numbers of the effects go through the rules engine
    (core/nql/effects) and the sheet stores the engine's values. Encounter
    creature records pass ``engine=False`` and keep the read-time overlay.
    """
    from core.nql import genesis

    result = deepcopy(sheet or {})
    effects = result.setdefault("temporaryEffects", [])
    if not isinstance(effects, list):
        raise ValueError("temporaryEffects must be an array")
    removed_owned = []
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
                effect.pop(genesis.EFFECT_ENGINE_OWNED, None)
                effects.append(effect)
                if not (engine and _engine_holds(effect)):
                    # The engine applies onApply for the effects it holds,
                    # after the condition line, in the same request.
                    _apply_resource_operations(result, effect.get("onApply", []))
            else:
                # Same identity: the numbers already on the sheet stay the
                # engine's; the record keeps its ownership marks.
                current = effects[index] if isinstance(effects[index], dict) else {}
                for mark in (genesis.EFFECT_ENGINE_OWNED, genesis.EFFECT_EXPIRES_TICK):
                    if mark in current:
                        effect[mark] = current[mark]
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
                elif engine and current.get(genesis.EFFECT_ENGINE_OWNED) is True and _engine_holds(current):
                    removed_owned.append(current)
                else:
                    _apply_resource_operations(result, current.get("onRemove", []))
            effects[:] = retained
    if engine:
        result = _reconcile_with_engine(result, removed_owned)
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
    result.pop("expiresTick", None)
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
    result["expiresTick"] = int(now_scalar) + rounds * 6
    result["durationKind"] = "minutes"
    result.pop("roundsRemaining", None)
    result.pop("tickTrigger", None)
    return result
