# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure effect operations and duration planning."""

from copy import deepcopy
import math

from core.effects.clock import display_iso_from_scalar, scalar_from_display_iso
from core.effects.effective import effective_sheet
from core.effects.model import effect_identity, normalize_effect, validate_effect

# SRD conditions whose definition includes Incapacitated (a creature that
# cannot take actions); an effect stating one of them incapacitates.
INCAPACITATING_CONDITIONS = ("incapacitated", "paralyzed", "petrified", "stunned", "unconscious")


def combat_effect_states(effects):
    """The SRD condition names stated by the live combat-born effects, in order of first mention.

    Only effects a fight created (they carry ``sourceEncounterId``) count: a
    condition the DM wrote on the sheet outside a fight is a fact the DM
    states and ends, never a function of an effect.
    """
    from core.nql.srd_stats import STATE_NAMES

    names = []
    for effect in effects or []:
        if not isinstance(effect, dict) or not effect.get("sourceEncounterId"):
            continue
        for item in effect.get("conditions") or []:
            name = str(item).strip().casefold() if isinstance(item, str) else ""
            if name in STATE_NAMES and name not in names:
                names.append(name)
    return names


def effect_incapacitates(effect):
    """True when the effect says so or states an SRD condition that includes Incapacitated."""
    if not isinstance(effect, dict):
        return False
    if effect.get("incapacitates") is True:
        return True
    return any(
        isinstance(item, str) and item.strip().casefold() in INCAPACITATING_CONDITIONS
        for item in effect.get("conditions") or []
    )


def sync_condition_states(listed, before_effects, after_effects):
    """The condition list after an effect operation: a function of the effects, replay-safe.

    Names the combat effects stated before and no longer state leave the
    list; names they state now are on it. Every other entry (the DM's own,
    the engine's unconscious hold) is kept as it was.
    """
    before = combat_effect_states(before_effects)
    after = combat_effect_states(after_effects)
    kept = [c for c in (listed or []) if isinstance(c, str)]
    result = [c for c in kept if not (c.casefold() in before and c.casefold() not in after)]
    for name in after:
        if name not in [c.casefold() for c in result]:
            result.append(name)
    return result


def _sync_sheet_states(before_effects, result):
    """Write the combat effects' conditions onto the sheet's condition_affected / condition."""
    names = sync_condition_states(result.get("condition_affected"), before_effects, result.get("temporaryEffects"))
    if names != [c for c in (result.get("condition_affected") or []) if isinstance(c, str)]:
        result["condition_affected"] = names
        # The engine's roll-mode labels describe the old states; its next
        # status request writes the current ones back.
        result.pop("rollModes", None)
    current = result.get("condition")
    if ("condition" in result or names) and not (
        isinstance(current, str) and current.casefold() in [n.casefold() for n in names]
    ):
        result["condition"] = names[0] if names else "none"


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


def _live_name(effect):
    if not isinstance(effect, dict) or effect.get("authoredBy") not in ("engine", "classifier"):
        return None
    name = " ".join(str(effect.get("name") or "").split()).casefold()
    return name or None


def _same_live_name(current, proposed):
    """Typed name equality between two runtime-managed effect records."""
    name = _live_name(current)
    return name is not None and name == _live_name(proposed)


def _engine_holds(effect):
    """True when the engine holds this effect (its numbers, if any, and its clock)."""
    from core.nql import genesis

    return bool(
        isinstance(effect, dict)
        and effect.get("authoredBy") in genesis.EFFECT_AUTHORS
        and isinstance(effect.get("effectId"), str)
        and effect.get("effectId")
        and genesis.effect_engine_modifiers(effect) is not None
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
    before_effects = deepcopy(effects)
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
                # The same spell or effect already active on this character
                # does not stack (SRD, combining magical effects): a second
                # record of the same name replaces the first. This also keeps
                # a cast that arrives as two change notes from becoming two
                # effects. Legacy display records are never matched.
                index = next(
                    (i for i, current in enumerate(effects)
                     if _same_live_name(current, effect)),
                    None,
                )
            effect.pop(genesis.EFFECT_ENGINE_OWNED, None)
            effect.pop(genesis.EFFECT_EXPIRES_TICK, None)
            if index is None:
                effects.append(effect)
                if not (engine and _engine_holds(effect)):
                    # The engine applies onApply for the effects it holds,
                    # after the condition line, in the same request.
                    _apply_resource_operations(result, effect.get("onApply", []))
            else:
                current = effects[index] if isinstance(effects[index], dict) else {}
                if current.get(genesis.EFFECT_ENGINE_OWNED) is True and (
                    current.get("modifiers") == effect.get("modifiers")
                ):
                    # Same numbers: the engine already holds them; the record
                    # keeps its ownership and takes the newer expiry.
                    from core.nql import effects as nql_effects

                    effect[genesis.EFFECT_ENGINE_OWNED] = True
                    tick = nql_effects._expires_tick(effect)
                    if tick is not None:
                        effect[genesis.EFFECT_EXPIRES_TICK] = tick
                    elif genesis.EFFECT_EXPIRES_TICK in current:
                        effect[genesis.EFFECT_EXPIRES_TICK] = current[genesis.EFFECT_EXPIRES_TICK]
                elif engine and current.get(genesis.EFFECT_ENGINE_OWNED) is True and _engine_holds(current):
                    # Different numbers: the engine ends the old instance and
                    # applies the new one in the same request.
                    removed_owned.append(current)
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
    # A fight's effect that states an SRD condition puts it on the sheet
    # (CSb), before the engine request so genesis declares the state and
    # the engine prices it (speed, save modes, concentration) at once.
    _sync_sheet_states(before_effects, result)
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
    """Return deterministic remove operations for expired wall-clock effects.

    Effects the engine holds (engineOwned with an expiresTick) are not planned
    here: the engine clock ends them (core/nql/effects.advance). Only effects
    without an engine tick still expire by this comparison.
    """
    planned = []
    for owner, sheet in (sheets or {}).items():
        if not isinstance(sheet, dict):
            continue
        for effect in sheet.get("temporaryEffects", []) or []:
            if not isinstance(effect, dict) or effect.get("roundsRemaining") is not None:
                continue
            if effect.get("engineOwned") is True and type(effect.get("expiresTick")) is int:
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
