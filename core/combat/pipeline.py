# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Pure orchestration of one claimed combat actor window.

The provider chooses ordered intents.  This module validates and resolves one
actor at a time against the result of every prior actor, so a batched model
decision can never become a batched or stale mutation.
"""

from copy import deepcopy

from core.combat.bonus_actions import (
    OFF_HAND_ATTACK,
    bonus_action_names,
    bonus_action_options,
    bonus_action_problem,
    bonus_name_refused,
    bonus_record,
    bonus_subintent,
    drop_bonus_spend,
    off_hand_damage_rule,
)
from core.combat.events import make_event_id, validate_event
from core.combat.resolver import (
    attack_row,
    json_ref,
    apply_encounter_effect_ticks,
    apply_effect_ticks,
    apply_resolution,
    end_dodge,
    plan_effect_ticks,
    resolve_adjudicated,
    resolve_intent,
    resolve_player_spell_attack,
    resolve_player_spell_save,
    resolve_player_weapon_attack,
    stage_dodge,
    validate_intent,
    _living_opponent_ids,
)
from core.managers.combat_state import (
    combatant_by_id,
    bystanders_attacked,
    combat_provenance,
    has_left_fight,
    join_as_hostile,
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


class CombatBonusAttackRollRequired(Exception):
    """R3: the player's Off-hand Attack is valid and its Action resolved, but
    its dice are not in yet; code asks them with a roll line (owner ruling)
    and resolves the stored batch when they are. ``request`` holds the typed
    ability and targetId."""

    def __init__(self, actor_id, request):
        super().__init__("The player's Off-hand Attack needs its dice")
        self.actor_id = actor_id
        self.request = request


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


def _defend_for_fled_target(current_encounter, actor, intent):
    """#1379: on a typed encounter, a non-player known attack whose target
    left the fight earlier in this batch (flee or yield) becomes Defend when
    no opponent remains for the actor; the T096 contract already rules the
    same ("If no valid opponent would remain, use defend"). Any other case is
    the model's: the intent goes on to the normal correction. Only typed
    fields are read."""
    if (
        actor.get("type") == "player"
        or intent.get("mode", "known") != "known"
        or intent.get("action") != "attack"
        or not intent.get("targetId")
    ):
        return intent, None
    target = combatant_by_id(current_encounter, intent["targetId"])
    if not has_left_fight(target) or _living_opponent_ids(current_encounter, actor):
        return intent, None
    recovered = {
        "actorId": actor.get("combatantId"),
        "mode": "known",
        "action": "defend",
        "description": "The combatant takes a defensive stance.",
    }
    return recovered, {
        "kind": "targetLeftFightDefend",
        "actorId": actor.get("combatantId"),
        "fromTargetId": intent["targetId"],
        "action": "defend",
    }


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
        for field in ("hitPoints", "temporaryHitPoints", "status"):
            if old_sheet.get(field) != new_sheet.get(field):
                snapshot[field] = deepcopy(new_sheet.get(field))
        if snapshot:
            snapshots[name] = snapshot
    if not snapshots:
        event.pop("characterStateAfter", None)


def _record_draw_applied(event, after):
    """NUM-B2: record on the staged event whether the swing's draw (NUM-B,
    BQ1) landed on the owner's sheet, by the guard apply_resolution uses. The
    narrator states a draw only when it did."""
    hands = event.get("hands")
    draw = hands.get("draw") if isinstance(hands, dict) else None
    if not isinstance(draw, dict):
        return
    sheet = (after or {}).get(hands.get("owner"))
    rows = sheet.get("equipment") if isinstance(sheet, dict) else None
    index = draw.get("index")
    draw["applied"] = bool(
        isinstance(rows, list) and type(index) is int and 0 <= index < len(rows)
        and isinstance(rows[index], dict) and rows[index].get("item_name") == draw.get("item_name")
        and rows[index].get("equipped") is True
    )


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


def _raise_bonus_problem(sheet, bonus, actor_id, problem):
    """The typed correction for a bonusAction that cannot be ruled as given."""
    if problem:
        from core.combat.bonus_actions import item_bonus_refusal
        refusal = item_bonus_refusal(sheet, bonus)
        extra = {"playerResourceRefusal": [refusal]} if refusal else {}
        raise CombatIntentError(
            problem,
            actor_id,
            {"violations": [problem], "bonusActionNames": bonus_action_names(sheet),
             "bonusActionProblem": problem, "bonusActionNameRefused": bonus_name_refused(sheet, bonus),
             "bonusActionOptions": bonus_action_options(sheet, bonus), "retryable": True, **extra},
        )


def _resolve_off_hand(encounter, characters, actor, controller, bonus, event_id, roll_source, phase):
    """R3: the Off-hand Attack, after the Action (SRD Light: "later on the
    same turn"). A target already down is not attacked (nothing is spent). The
    player's swing is scored by code from the faces of its completed roll phase;
    with none yet, CombatBonusAttackRollRequired asks for them. Another actor's
    swing is rolled by code. The row's damage leaves out the ability modifier
    unless the Two-Weapon Fighting style keeps it. Returns (record, encounter,
    characters)."""
    from core.nql import hands

    actor_id = actor.get("combatantId")
    record = {"featureName": OFF_HAND_ATTACK, "ability": bonus.get("ability"), "targetId": bonus.get("targetId"),
              "description": str(bonus.get("description") or OFF_HAND_ATTACK), "order": "afterAction",
              "outcome": {"targets": []}, "resources": []}
    target = combatant_by_id(encounter, bonus.get("targetId"))
    if target is None or not is_combatant_targetable(target) or int(target.get("currentHitPoints", 0) or 0) <= 0:
        record["notTaken"] = "targetDown"
        return record, encounter, characters
    sheet = (characters or {}).get(actor.get("name"))
    # K1 (F2, F6): the weapon is the row bonusAction.abilityRow names in the
    # actor's own list, resolved on the unadjusted sheet; a miss is retryable.
    ref = bonus.get("abilityRow")
    weapon = attack_row(sheet, ref, actor_id)
    if weapon is None:
        problem = ("the Off-hand Attack's bonusAction.abilityRow %s names no attack row of this actor; give the "
                   "other Light weapon's listed rowRef" % json_ref(ref))
        raise CombatIntentError(problem, actor_id, {"violations": [problem], "retryable": True})
    record["ability"] = weapon.get("name")
    if controller == "human" and not (isinstance(phase, dict) and phase.get("ready") is True):
        raise CombatBonusAttackRollRequired(
            actor_id, {"ability": weapon.get("name"), "abilityRow": deepcopy(ref), "targetId": bonus.get("targetId")})
    rows = hands.light_melee_rows(sheet)
    row = (rows or {}).get(weapon.get("name"))
    if row is None:
        problem = "the Off-hand Attack's weapon is no longer a Light melee weapon in hand"
        raise CombatIntentError(problem, actor_id, {"violations": [problem]})
    rule = off_hand_damage_rule(sheet, row)
    scoring = dict(characters)
    if rule["removed"]:
        # F3: the scoring copy's row at the same position is lowered in place,
        # so the position still names it.
        scoring[actor.get("name")] = adjusted = deepcopy(sheet)
        entry = attack_row(adjusted, ref, actor_id)
        entry["damageBonus"] = int(entry.get("damageBonus", 0) or 0) - rule["removed"]
    sub = {"actorId": actor_id, "action": "attack", "ability": weapon.get("name"), "abilityRow": deepcopy(ref),
           "targetId": bonus.get("targetId"), "description": record["description"]}
    if controller == "human":
        resolution = resolve_player_weapon_attack(encounter, scoring, sub, phase, "%s-B" % event_id, roll_source)
    else:
        resolution = resolve_intent(encounter, scoring, sub, roll_source, "%s-B" % event_id)
    if resolution.get("violations"):
        feedback = {"violations": ["bonusAction: %s" % v for v in resolution["violations"]], "retryable": True}
        raise CombatIntentError("; ".join(feedback["violations"]), actor_id, feedback)
    event = resolution["event"]
    problems = validate_event(event)
    if problems:
        raise CombatIntentError("; ".join(problems), actor_id, {"violations": problems})
    next_encounter, next_characters = apply_resolution(encounter, characters, resolution)
    record["outcome"] = deepcopy(event.get("outcome") or {"targets": []})
    record["rolls"] = deepcopy(event.get("rolls") or [])
    record["damageRule"] = rule
    return record, next_encounter, next_characters


def _resolve_bonus_action(encounter, characters, actor, controller, intent, bonus, event_id, roll_source,
                          clamp_feature_heals=False):
    """R2: the actor's typed Bonus Action, resolved and applied before its
    Action (owner: bonus action first). Returns (record, encounter,
    characters); the record rides on the actor's one event."""
    actor_id = actor.get("combatantId")
    sheet = (characters or {}).get(actor.get("name"))
    _raise_bonus_problem(sheet, bonus, actor_id, bonus_action_problem(sheet, bonus, encounter=encounter, actor_id=actor_id))
    if "item" in bonus:
        from core.combat.bonus_actions import resolve_item_bonus
        from core.nql.apply import EngineUnavailable
        try:
            return resolve_item_bonus(encounter, characters, actor, intent, bonus, event_id)
        except (ValueError, EngineUnavailable) as error:
            raise CombatIntentError(str(error), actor_id, {"retryable": True}) from error
    sub = bonus_subintent(intent, bonus, actor.get("name"))
    sub["stateVersion"] = intent.get("stateVersion")
    resolution = resolve_adjudicated(
        encounter,
        characters,
        sub,
        roll_source,
        "%s-B" % event_id,
        clamp_feature_heals=clamp_feature_heals,
    )
    if resolution.get("violations"):
        feedback = {"violations": ["bonusAction: %s" % v for v in resolution["violations"]], "retryable": True}
        if controller == "human" and resolution.get("resourceRefusals"):
            # #671 / T5: the player's feature use has none left; the player keeps the choice.
            feedback["playerResourceRefusal"] = deepcopy(resolution["resourceRefusals"])
        if resolution.get("featureHealLimits"):
            feedback["featureHealLimits"] = deepcopy(resolution["featureHealLimits"])
            feedback["featureHealPlayer"] = controller == "human"
        raise CombatIntentError("; ".join(feedback["violations"]), actor_id, feedback)
    problems = validate_event(resolution.get("event"))
    if problems:
        raise CombatIntentError("; ".join(problems), actor_id, {"violations": problems})
    next_encounter, next_characters = apply_resolution(encounter, characters, resolution)
    return bonus_record(bonus, resolution["event"]), next_encounter, next_characters


def resolve_claimed_window(encounter, characters, pending_turn, batch, roll_source, clamp_feature_heals=False,
                           drop_removals_for=()):
    """Resolve a provider batch sequentially and return staged events.

    The batch must contain one ordered intent per claimed actor. Actors
    defeated by an earlier event still consume their matching intent, but no
    event is resolved for them. Every still-eligible actor produces one event.
    ``mode='known'`` uses the deterministic weapon/stance resolver;
    ``mode='adjudicated'`` uses the bounded general outcome contract.
    ``clamp_feature_heals`` (#669): the batch is a correction of a feature heal
    over its typed limit; a heal still over it is clamped and journaled.
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
                end_dodge(skipped_event, actor)
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
        if stale_target_normalization is None and combat_provenance(encounter) == "typed":
            intent, stale_target_normalization = _defend_for_fled_target(
                next_encounter, actor, intent
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
        if controller != "human" and intent.get("requiresPlayerInput"):
            # Only the human's actor can answer a roll request. An NPC intent
            # that carries one would otherwise commit its declared values
            # (a heal of 0) while still spending the resource. Send it back
            # as a correction: the model rolls the NPC's dice in the ruling.
            raise CombatIntentError(
                "%s is not the player: requiresPlayerInput cannot be answered "
                "for an NPC or enemy. Remove it and supply the final hpDelta, "
                "resources, and effects for this action, rolling its dice in "
                "the ruling." % (actor.get("name") or actor_id),
                actor_id,
                {"retryable": True},
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
        before_characters = next_characters
        bonus = intent.pop("bonusAction", None)
        bonus_done = None
        bonus_spend_dropped = []
        off_hand = isinstance(bonus, dict) and bonus.get("featureName") == OFF_HAND_ATTACK
        if off_hand:
            # R3: checked now against the Action; resolved after it.
            off_sheet = (next_characters or {}).get(actor.get("name"))
            _raise_bonus_problem(off_sheet, bonus, actor_id,
                                 bonus_action_problem(off_sheet, bonus, intent=intent, encounter=next_encounter))
        elif bonus is not None:
            bonus_done, next_encounter, next_characters = _resolve_bonus_action(
                next_encounter, next_characters, actor, controller, intent, bonus, event_id,
                roll_source, clamp_feature_heals,
            )
            # The bonus action's own use, listed again on the Action, is the
            # same spend: it is not taken twice.
            bonus_spend_dropped = drop_bonus_spend(intent, bonus_done, actor.get("name"))
        weapon_attack = pending_turn.get("weaponAttack")
        off_hand_phase = None
        if (
            isinstance(weapon_attack, dict)
            and weapon_attack.get("bonusAttack") is True
            and weapon_attack.get("actorId") == actor_id
        ):
            # R3: the open phase is the Off-hand Attack's; the Action's own
            # code-scored swing (if any) rides on it, already complete.
            off_hand_phase = weapon_attack
            weapon_attack = weapon_attack.get("mainSwing")
        no_outcome = None
        if (
            isinstance(weapon_attack, dict)
            and weapon_attack.get("ready") is True
            and weapon_attack.get("actorId") == actor_id
        ):
            # Item 3: the player's swing, scored by code from the faces the
            # completed roll phase holds (never from a model-written field);
            # #672: a recorded spell attack, the same way; #723: a recorded
            # save spell, save first.
            if isinstance(weapon_attack.get("spell"), dict) and weapon_attack["spell"].get("type") == "save":
                resolution = resolve_player_spell_save(
                    next_encounter,
                    next_characters,
                    intent,
                    weapon_attack,
                    event_id,
                    roll_source,
                )
            elif isinstance(weapon_attack.get("spell"), dict):
                resolution = resolve_player_spell_attack(
                    next_encounter,
                    next_characters,
                    intent,
                    weapon_attack,
                    event_id,
                    roll_source,
                )
            else:
                resolution = resolve_player_weapon_attack(
                    next_encounter,
                    next_characters,
                    intent,
                    weapon_attack,
                    event_id,
                    roll_source,
                )
        elif intent.get("action") in ("flee", "yield"):
            # Leaving the fight is the same act in either mode (#466): a
            # player's flee/yield arrives adjudicated and must not be dropped.
            resolution = resolve_intent(
                next_encounter,
                next_characters,
                intent,
                roll_source,
                event_id,
            )
        elif mode == "known":
            resolution = resolve_intent(
                next_encounter,
                next_characters,
                intent,
                roll_source,
                event_id,
            )
        elif mode == "adjudicated":
            target = combatant_by_id(next_encounter, intent.get("targetId"))
            if (
                intent.get("action") == "attack"
                and target is not None
                and target.get("combatantId") != actor_id
                and not intent.get("targets")
                and not intent.get("effects")
            ):
                # #839: a companion's or enemy's attack with no outcome spent
                # an arrow, rolled nothing and left the narrator guessing.
                # D-HC-2: the same check for the player's attack, whose ruling
                # states hit or miss from the player's rolls, or asks for the
                # next one. The player's typed refusals (charge, resource,
                # feature heal) are raised first, below: a shot with an empty
                # quiver gets the engine's refusal, not a request for an outcome.
                if controller == "human":
                    remedy = (
                        "From the player's rolls, give targets [{combatantId, hpDelta}] "
                        "(hpDelta 0 on a miss), or set requiresPlayerInput for the roll it "
                        "still needs (the damage dice after a hit)."
                    )
                else:
                    remedy = (
                        "Declare it with mode 'known', the listed weapon/action row's rowRef as "
                        "abilityRow and its name as ability so code rolls it, or roll it in the "
                        "ruling and give targets "
                        "[{combatantId, hpDelta}] (hpDelta 0 on a miss)."
                    )
                no_outcome = CombatIntentError(
                    "%s's attack on %s states no outcome. %s"
                    % (actor.get("name") or actor_id, target.get("name") or target.get("combatantId"), remedy),
                    actor_id,
                    {"retryable": True},
                )
                if controller != "human":
                    raise no_outcome
            resolution = resolve_adjudicated(
                next_encounter,
                next_characters,
                intent,
                roll_source,
                event_id,
                clamp_feature_heals=clamp_feature_heals,
                # #725: this actor's refused remove op was re-ruled once.
                drop_refused_removals=actor_id in drop_removals_for,
            )
        else:
            raise CombatIntentError("Unknown intent mode %r" % mode, actor_id)

        if stale_target_normalization:
            resolution["event"].setdefault("normalizations", []).append(
                stale_target_normalization
            )
        for draw in pending_turn.get("rechargeRolls") or []:
            # MS-b: the claim's recharge draws ride on the actor's own event so
            # the narrator and the log can state them.
            if isinstance(draw, dict) and draw.get("actorId") == actor_id:
                resolution["event"].setdefault("rechargeRolls", []).append(deepcopy(draw))
        # Item 2: the actor's own turn ends its earlier Dodge; the typed
        # dodge action (either mode) starts a new one. defend stays empty.
        end_dodge(resolution["event"], actor, resolution)
        if intent.get("action") == "dodge":
            stage_dodge(next_encounter, resolution)

        if controller == "human" and resolution.get("chargeRefusals"):
            # H3b: the player chose to use an item that cannot pay for it.
            # The player keeps agency: the DM narrates the failed use and
            # asks for another action; the round does not fire. The
            # orchestrator pauses for the player if the correction does not.
            refusals = deepcopy(resolution["chargeRefusals"])
            raise CombatIntentError(
                "; ".join(resolution["violations"]),
                actor_id,
                {"violations": list(resolution["violations"]),
                 "playerChargeRefusal": refusals, "retryable": True},
            )
        if controller == "human" and resolution.get("resourceRefusals"):
            # #671: the player's spell slot or feature use has none left. The
            # player keeps agency, as H3b: the correction asks the player.
            raise CombatIntentError(
                "; ".join(resolution["violations"]),
                actor_id,
                {"violations": list(resolution["violations"]),
                 "playerResourceRefusal": deepcopy(resolution["resourceRefusals"]), "retryable": True},
            )
        if controller == "human" and resolution.get("featureHealUnspent"):
            # #669: the corrected batch still spends the player's feature on
            # a heal that restores nothing. Nothing is committed; the
            # orchestrator pauses for the player's choice.
            raise CombatIntentError(
                "feature heal limit: the corrected intent still restores nothing",
                actor_id,
                {"violations": ["feature heal limit: the corrected intent still restores nothing"],
                 "featureHealLimits": deepcopy(resolution["featureHealUnspent"]),
                 "featureHealPlayer": True, "retryable": True},
            )
        if no_outcome is not None:
            raise no_outcome
        if resolution.get("violations"):
            feedback = {"violations": list(resolution["violations"])}
            if resolution.get("featureHealLimits"):
                # #669: the typed limits the correction names; a player's
                # actor keeps the choice (the orchestrator pauses for it).
                feedback["featureHealLimits"] = deepcopy(resolution["featureHealLimits"])
                feedback["featureHealPlayer"] = controller == "human"
                feedback["retryable"] = True
            if resolution.get("removalRefusals"):
                # #725: the typed removal refusals the correction names.
                feedback["removalRefusals"] = deepcopy(resolution["removalRefusals"])
            raise CombatIntentError(
                "; ".join(resolution["violations"]),
                actor_id,
                feedback,
            )
        if bonus_done is not None:
            resolution["event"]["bonusAction"] = bonus_done
            if bonus_spend_dropped:
                resolution["event"].setdefault("normalizations", []).append(
                    {"kind": "bonusActionSpendNotRepeated", "actorId": actor_id,
                     "resources": deepcopy(bonus_spend_dropped)})
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
        _record_character_state_after(
            resolution["event"],
            before_characters,
            next_characters,
        )
        _record_draw_applied(resolution["event"], next_characters)
        if off_hand:
            resolution["event"]["bonusAction"], next_encounter, next_characters = _resolve_off_hand(
                next_encounter, next_characters, actor, controller, bonus, event_id, roll_source, off_hand_phase,
            )
        snapshot_problems = validate_event(resolution.get("event"))
        if snapshot_problems:
            raise CombatIntentError(
                "; ".join(snapshot_problems),
                actor_id,
                {"violations": snapshot_problems},
            )
        if controller == "human":
            # #1415: an observer the player attacked joins the fight as a
            # hostile; the record is replayed at commit (apply_staged_turn).
            for joined_id in bystanders_attacked(next_encounter, resolution["event"]):
                resolution["event"].setdefault("normalizations", []).append(
                    {"kind": "bystanderJoinedHostile", "combatantId": joined_id, "by": actor_id}
                )
                join_as_hostile(next_encounter, joined_id, by=actor_id)
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
