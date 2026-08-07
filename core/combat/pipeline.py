# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure orchestration of one claimed combat actor window.

The provider chooses ordered intents.  This module validates and resolves one
actor at a time against the result of every prior actor, so a batched model
decision can never become a batched or stale mutation.
"""

from copy import deepcopy

from core.combat.events import make_event_id, validate_event
from core.combat.resolver import (
    apply_encounter_effect_ticks,
    apply_effect_ticks,
    apply_resolution,
    plan_effect_ticks,
    resolve_adjudicated,
    resolve_intent,
    validate_intent,
)
from core.managers.combat_state import combatant_by_id, is_turn_eligible


class CombatIntentError(ValueError):
    """A provider-produced intent cannot safely resolve the claimed window."""

    def __init__(self, message, actor_id=None, feedback=None):
        super().__init__(message)
        self.actor_id = actor_id
        self.feedback = feedback or {}


class CombatPlayerInputRequired(CombatIntentError):
    """The player's claimed turn needs a roll or decision before resolution."""


def _ordered_intents(batch, revision):
    if not isinstance(batch, dict):
        raise CombatIntentError("Intent batch must be an object")
    if batch.get("stateVersion") != revision:
        raise CombatIntentError("Intent batch was produced from stale combat state")
    intents = batch.get("intents")
    if not isinstance(intents, list):
        raise CombatIntentError("Intent batch requires an intents array")
    return intents


def _intent_for_actor(intents, index, actor_id):
    if index >= len(intents):
        raise CombatIntentError("Intent batch omitted an eligible actor", actor_id)
    intent = intents[index]
    if not isinstance(intent, dict) or intent.get("actorId") != actor_id:
        raise CombatIntentError(
            "Intent batch does not match the persisted initiative order",
            actor_id,
        )
    return deepcopy(intent)


def resolve_claimed_window(encounter, characters, pending_turn, batch, roll_source):
    """Resolve a provider batch sequentially and return staged events.

    The batch must contain one ordered intent per claimed actor. Actors
    defeated by an earlier event still consume their matching intent, but no
    event is resolved for them. Every still-eligible actor produces one event.
    ``mode='known'`` uses the deterministic weapon/stance resolver;
    ``mode='adjudicated'`` uses the bounded general outcome contract.
    """
    if not isinstance(pending_turn, dict):
        raise CombatIntentError("A persisted pending turn is required")
    state = encounter.get("combatState") or {}
    revision = state.get("revision")
    if pending_turn.get("baseRevision") != revision:
        raise CombatIntentError("Pending turn no longer matches combat revision")
    intents = _ordered_intents(batch, revision)

    next_encounter = deepcopy(encounter)
    next_characters = deepcopy(characters or {})
    events = []
    intent_index = 0
    for sequence, actor_id in enumerate(pending_turn.get("actorIds") or [], start=1):
        intent = _intent_for_actor(intents, intent_index, actor_id)
        intent_index += 1
        actor = combatant_by_id(next_encounter, actor_id)
        if not actor or not is_turn_eligible(actor):
            continue
        intent["stateVersion"] = revision
        mode = intent.get("mode", "known")
        if actor.get("type") == "player" and mode != "adjudicated":
            raise CombatIntentError(
                "Player actions must be adjudicated from the submitted action and player-provided rolls",
                actor_id,
            )
        if actor.get("type") == "player" and intent.get("requiresPlayerInput"):
            raise CombatPlayerInputRequired(
                "The player's turn needs additional input",
                actor_id,
                {"request": deepcopy(intent.get("requiresPlayerInput"))},
            )
        valid, rejection = validate_intent(
            next_encounter,
            next_characters,
            intent,
            strict=mode == "known",
        )
        if not valid:
            raise CombatIntentError(
                rejection.get("reason", "Intent rejected"),
                actor_id,
                dict(rejection),
            )

        event_id = make_event_id(
            next_encounter.get("encounterId", "encounter"),
            pending_turn.get("round", state.get("round", 1)),
            pending_turn.get("turnId"),
            sequence,
        )
        intent.pop("mode", None)
        if mode == "known":
            resolution = resolve_intent(
                next_encounter,
                next_characters,
                intent,
                roll_source,
                event_id,
            )
        elif mode == "adjudicated":
            resolution = resolve_adjudicated(
                next_encounter,
                next_characters,
                intent,
                roll_source,
                event_id,
            )
        else:
            raise CombatIntentError("Unknown intent mode %r" % mode, actor_id)

        if resolution.get("violations"):
            raise CombatIntentError(
                "; ".join(resolution["violations"]),
                actor_id,
                {"violations": list(resolution["violations"])},
            )
        event_problems = validate_event(resolution.get("event"))
        if event_problems:
            raise CombatIntentError(
                "; ".join(event_problems),
                actor_id,
                {"violations": event_problems},
            )
        next_encounter, next_characters = apply_resolution(
            next_encounter,
            next_characters,
            resolution,
        )
        events.append(resolution["event"])

    if intent_index != len(intents):
        raise CombatIntentError("Intent batch contains actors outside the claimed window")

    state = next_encounter.get("combatState") or {}
    acted_after = set(state.get("actedThisRound") or []).union(
        pending_turn.get("actorIds") or []
    )
    eligible_after = {
        creature.get("combatantId")
        for creature in next_encounter.get("creatures", [])
        if is_turn_eligible(creature)
    }
    if events and eligible_after and eligible_after.issubset(acted_after):
        effect_ticks = plan_effect_ticks(
            next_characters,
            "end_of_round",
            encounter=next_encounter,
            created_in_round=pending_turn.get("round", state.get("round", 1)),
        )
        if effect_ticks:
            events[-1]["effectTicks"] = effect_ticks
            tick_problems = validate_event(events[-1])
            if tick_problems:
                raise CombatIntentError(
                    "; ".join(tick_problems),
                    events[-1].get("actorId"),
                    {"violations": tick_problems},
                )
            next_characters = apply_effect_ticks(next_characters, effect_ticks)
            next_encounter = apply_encounter_effect_ticks(
                next_encounter,
                effect_ticks,
            )
    return events, next_encounter, next_characters
