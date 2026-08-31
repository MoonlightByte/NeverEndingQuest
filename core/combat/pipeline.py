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
from core.managers.combat_state import (
    combatant_by_id,
    combat_provenance,
    is_combatant_targetable,
    is_turn_eligible,
    resolve_creature_controller,
)


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


def _recover_stale_known_target(original_encounter, current_encounter, actor, intent):
    """Repair only a target invalidated by an earlier event in this batch.

    The provider made its whole ordered proposal from the original snapshot.
    A later non-player attack can therefore name a target that was legal when
    proposed but was defeated by an earlier resolved intent. If exactly one
    opposing target remains, retargeting is unambiguous. Otherwise Defend is
    the conservative no-call fallback. Pre-existing bad targets and player
    actions still reject normally.
    """
    if combat_provenance(original_encounter) == "typed":
        return intent, None
    if (
        actor.get("type") == "player"
        or intent.get("mode", "known") != "known"
        or intent.get("action") != "attack"
        or not intent.get("targetId")
    ):
        return intent, None
    target_id = intent["targetId"]
    original_target = combatant_by_id(original_encounter, target_id)
    current_target = combatant_by_id(current_encounter, target_id)
    if (
        not is_combatant_targetable(original_target)
        or is_combatant_targetable(current_target)
        or original_target.get("faction") == actor.get("faction")
    ):
        return intent, None

    legal_targets = [
        creature.get("combatantId")
        for creature in current_encounter.get("creatures", [])
        if is_combatant_targetable(creature)
        and creature.get("faction") != actor.get("faction")
    ]
    normalization = {
        "kind": "staleBatchTargetFallback",
        "actorId": actor.get("combatantId"),
        "fromTargetId": target_id,
    }
    if len(legal_targets) == 1:
        recovered = deepcopy(intent)
        recovered["targetId"] = legal_targets[0]
        normalization["action"] = "retarget"
        normalization["toTargetId"] = legal_targets[0]
        return recovered, normalization

    recovered = {
        "actorId": actor.get("combatantId"),
        "mode": "known",
        "action": "defend",
        "description": (
            "The planned target fell earlier in this turn window, so the "
            "combatant takes a defensive stance."
        ),
    }
    normalization["action"] = "defend"
    normalization["remainingLegalTargets"] = len(legal_targets)
    return recovered, normalization


def _record_character_state_after(event, before, after):
    """Attach absolute post-event character fields needed for crash replay.

    Character files are persisted before the encounter receipt. If a process
    dies between those writes, replay starts with already-updated sheets and
    an old encounter journal. Effect onApply/onRemove deltas are intentionally
    idempotent and will not run twice, so the staged event also records the
    final consumed HP/status values that replay must converge to.
    """
    snapshots = event.setdefault("characterStateAfter", {})
    for name in sorted(set(before or {}).union(after or {})):
        old_sheet = (before or {}).get(name)
        new_sheet = (after or {}).get(name)
        if not isinstance(old_sheet, dict) or not isinstance(new_sheet, dict):
            continue
        snapshot = dict(snapshots.get(name) or {})
        for field in ("hitPoints", "status"):
            if old_sheet.get(field) != new_sheet.get(field):
                snapshot[field] = deepcopy(new_sheet.get(field))
        if snapshot:
            snapshots[name] = snapshot
    if not snapshots:
        event.pop("characterStateAfter", None)


def resolve_effect_clock_window(encounter, characters, pending_turn):
    """Build one provider-free event when no living combatant can act."""
    if not isinstance(pending_turn, dict) or pending_turn.get("clockOnly") is not True:
        raise CombatIntentError("A persisted clock-only turn is required")
    state = encounter.get("combatState") or {}
    if pending_turn.get("baseRevision") != state.get("revision"):
        raise CombatIntentError("Effect-clock turn no longer matches combat revision")
    ticks = plan_effect_ticks(
        characters,
        "end_of_round",
        encounter=encounter,
        created_in_round=pending_turn.get("round", state.get("round", 1)),
    )
    if not ticks:
        # If every timed effect was created during this same round, the first
        # boundary must advance without decrementing it. Rejecting that legal
        # zero-tick boundary would permanently pause a fight immediately after
        # a control effect landed. With no end-of-round candidate at all, keep
        # the existing stable pause rather than spinning on an indefinite
        # incapacitation.
        future_ticks = plan_effect_ticks(
            characters,
            "end_of_round",
            encounter=encounter,
        )
        if not future_ticks:
            raise CombatIntentError(
                "All living combatants are incapacitated, but no timed effect can advance"
            )
    event = {
        "eventId": make_event_id(
            encounter.get("encounterId", "encounter"),
            pending_turn.get("round", state.get("round", 1)),
            pending_turn.get("turnId"),
            0,
        ),
        "actorId": "combat-clock",
        "stateVersion": state.get("revision"),
        "intent": {"action": "advanceEffectClock"},
        "outcome": {
            "kind": "effectClock",
            "description": (
                "Every living combatant is temporarily unable to act; "
                + (
                    "timed effects advance to the next round."
                    if ticks
                    else "the round ends without shortening effects created this round."
                )
            ),
            "targets": [],
        },
        "resources": [],
        "effects": [],
        "effectTicks": ticks,
    }
    resolution = {
        "event": event,
        "charDeltas": {},
        "creatureDeltas": {},
        "effectOps": [],
        "violations": [],
    }
    next_encounter, next_characters = apply_resolution(
        encounter,
        characters,
        resolution,
    )
    _record_character_state_after(event, characters, next_characters)
    problems = validate_event(event)
    if problems:
        raise CombatIntentError(
            "; ".join(problems),
            "combat-clock",
            {"violations": problems},
        )
    return [event], next_encounter, next_characters


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
        if not actor:
            continue
        if not is_turn_eligible(actor):
            # A living actor can become incapacitated from an earlier event in
            # this same ordered batch. Persist an explicit no-mutation event so
            # staging can prove the claimed initiative position was consumed,
            # narration can explain the skipped action, and any end-of-round
            # ticks attach to a durable event. Defeated actors remain omitted.
            if (
                is_combatant_targetable(actor)
                and actor.get("effectIncapacitated") is True
            ):
                skipped_event = {
                    "eventId": make_event_id(
                        next_encounter.get("encounterId", "encounter"),
                        pending_turn.get("round", state.get("round", 1)),
                        pending_turn.get("turnId"),
                        sequence,
                    ),
                    "actorId": actor_id,
                    "stateVersion": revision,
                    "intent": {
                        "action": "skipTurn",
                        "reason": "effectIncapacitated",
                    },
                    "outcome": {
                        "kind": "skipped",
                        "description": "%s is incapacitated and cannot act."
                        % actor.get("name", "The combatant"),
                        "targets": [],
                    },
                    "resources": [],
                    "effects": [],
                    "normalizations": [
                        {
                            "kind": "actorIncapacitatedEarlierInBatch",
                            "actorId": actor_id,
                        }
                    ],
                }
                skipped_problems = validate_event(skipped_event)
                if skipped_problems:
                    raise CombatIntentError(
                        "; ".join(skipped_problems),
                        actor_id,
                        {"violations": skipped_problems},
                    )
                events.append(skipped_event)
            continue
        intent, stale_target_normalization = _recover_stale_known_target(
            encounter,
            next_encounter,
            actor,
            intent,
        )
        intent["stateVersion"] = revision
        mode = intent.get("mode", "known")
        controller = resolve_creature_controller(
            actor,
            next_encounter.get("combatState"),
        )
        if controller == "human" and mode != "adjudicated":
            raise CombatIntentError(
                "Player actions must be adjudicated from the submitted action and player-provided rolls",
                actor_id,
            )
        if controller == "human" and intent.get("requiresPlayerInput"):
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

        if stale_target_normalization:
            resolution["event"].setdefault("normalizations", []).append(
                stale_target_normalization
            )

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
        before_characters = next_characters
        next_encounter, next_characters = apply_resolution(
            next_encounter,
            next_characters,
            resolution,
        )
        _record_character_state_after(
            resolution["event"],
            before_characters,
            next_characters,
        )
        snapshot_problems = validate_event(resolution.get("event"))
        if snapshot_problems:
            raise CombatIntentError(
                "; ".join(snapshot_problems),
                actor_id,
                {"violations": snapshot_problems},
            )
        events.append(resolution["event"])

    if intent_index != len(intents):
        raise CombatIntentError("Intent batch contains actors outside the claimed window")

    state = next_encounter.get("combatState") or {}
    acted_after = set(state.get("actedThisRound") or []).union(
        pending_turn.get("skippedActorIds") or [],
        pending_turn.get("actorIds") or [],
    )
    targetable_after = {
        creature.get("combatantId")
        for creature in next_encounter.get("creatures", [])
        if is_combatant_targetable(creature)
    }
    if events and targetable_after and targetable_after.issubset(acted_after):
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
            before_ticks = next_characters
            next_characters = apply_effect_ticks(next_characters, effect_ticks)
            next_encounter = apply_encounter_effect_ticks(
                next_encounter,
                effect_ticks,
            )
            _record_character_state_after(
                events[-1],
                before_ticks,
                next_characters,
            )
            tick_snapshot_problems = validate_event(events[-1])
            if tick_snapshot_problems:
                raise CombatIntentError(
                    "; ".join(tick_snapshot_problems),
                    events[-1].get("actorId"),
                    {"violations": tick_snapshot_problems},
                )
    return events, next_encounter, next_characters
