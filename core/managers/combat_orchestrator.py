# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Agentic combat turn orchestration with deterministic commit boundaries."""

from collections.abc import Mapping
from copy import deepcopy
import json
import logging
import random
import re
import time
from types import MappingProxyType

from core.ai.combat_diagnostics import record_combat_diagnostic
from core.combat import (
    CombatIntentError,
    CombatPlayerInputRequired,
    PersistedPrerollSource,
    resolve_effect_clock_window,
    resolve_claimed_window,
)
from core.combat.attacks import attack_sequence, is_flat_attack
from core.combat.bonus_actions import (
    OFF_HAND_ATTACK,
    bonus_action_names,
    bonus_action_options,
    bonus_action_problem,
    bonus_name_refused,
)
from core.combat.pipeline import CombatBonusAttackRollRequired, _intent_for_actor, _ordered_intents
from core.combat.resolver import (
    _action_entries,
    declared_heal,
    feature_heal_key,
    intent_feature_name,
    pool_heal_options,
    spent_heal_pool,
    open_player_spell_attack,
    open_player_spell_save,
    open_player_weapon_attack,
    player_spell_attack_entry,
    player_spell_save_entry,
    player_great_weapon,
    player_weapon_attack_dice,
    player_ammunition_refusal,
    player_weapon_attack_entry,
    player_weapon_attack_score,
    spell_attack_violations,
    attack_row,
    sent_row_lists,
    stale_row_refs,
    validate_intent,
    weapon_attack_sheet_entry,
)
from core.managers.combat_state import (
    combatant_by_id,
    ensure_combat_state,
    is_turn_eligible,
    normalize_npc_voice_intents,
    resolve_creature_controller,
    valid_pending_delivery,
)
from core.managers.combat_transaction import (
    CombatPreconditionChanged,
    append_pending_player_input,
    live_exchanges,
    mark_pending_game_roll,
    apply_staged_turn,
    claim_turn,
    enter_effect_clock,
    inspect_recovery,
    record_delivery_narration,
    record_narration_attempt,
    record_pending_player_request,
    stage_events,
    write_pending_stats,
    write_weapon_attack,
)
from utils.encoding_utils import normalize_typography_deep, safe_json_load
from utils.capture.live_provider_call import LiveProviderCompletedError
from utils.transient_filesystem import ReadOnlySaveStop


_LOGGER = logging.getLogger(__name__)


class CombatTurnPaused(RuntimeError):
    """No mutation occurred; the same durable turn may be retried or resumed.
    ``player_message`` is the DM's words; ``card`` is a code-issued roll's dice
    record, shown as a system record under ``card_id`` (#1118, D-1118-8 D)."""

    def __init__(self, technical_message, player_message=None, card=None, card_id=None):
        super().__init__(technical_message)
        self.player_message = player_message
        self.card = card
        self.card_id = card_id


def _phase_paused(technical_message, record):
    """The pause for an open code-issued roll phase: the DM's lead and its card."""
    return CombatTurnPaused(technical_message, player_message=record.get("lead") or None,
                            card=record.get("card"), card_id=record.get("cardId"))


def _batch_targets(batch):
    """(actorId, combatantId) for every id an intent batch targets: each
    intent's targetId and targets[], and its bonusAction's targetId and
    targets[]. Typed fields only."""
    out = []
    intents = batch.get("intents") if isinstance(batch, dict) else None
    for intent in intents if isinstance(intents, list) else []:
        if not isinstance(intent, dict):
            continue
        actor_id = intent.get("actorId")
        bonus = intent.get("bonusAction")
        for part in (intent, bonus if isinstance(bonus, dict) else {}):
            if isinstance(part.get("targetId"), str):
                out.append((actor_id, part["targetId"]))
            targets = part.get("targets")
            for entry in targets if isinstance(targets, list) else []:
                if isinstance(entry, dict) and isinstance(entry.get("combatantId"), str):
                    out.append((actor_id, entry["combatantId"]))
    return out


def _ensure_targeted_sheets(encounter_path, encounter, batch, characters,
                            character_paths, pending, invocation_claim=None):
    """#1447: a ``statsPending`` observer (a present person with no sheet
    yet) that this batch targets gets its sheet before anything validates
    or resolves the batch: the existing load_or_create_npc (T035 when no
    sheet exists), once per creature per fight. Its stats are written to
    the encounter and the sheet joins ``characters`` and
    ``character_paths``. Returns (encounter, names built). When the build
    fails the intent is corrected; the creature stays an observer."""
    from core.generators.combat_builder import _roll_initiative, load_or_create_npc

    built = []
    for actor_id, target_id in _batch_targets(batch):
        creature = combatant_by_id(encounter, target_id)
        if not isinstance(creature, dict) or creature.get("statsPending") is not True:
            continue
        name = creature.get("name")
        if creature.get("sheetBuildFailedAt") is None:
            loaded = None
            try:
                loaded = load_or_create_npc(name)
            except Exception as exc:
                _LOGGER.warning("Sheet build for %s failed: %s", name, exc)
            if loaded:
                sheet, sheet_path = loaded
                stats = {
                    "currentHitPoints": sheet.get("hitPoints", 10),
                    "maxHitPoints": sheet.get("maxHitPoints", 10),
                    "armorClass": sheet.get("armorClass", 10),
                    "initiative": _roll_initiative(sheet, sheet_backed=True),
                }
                encounter = write_pending_stats(
                    encounter_path, pending["turnId"], target_id, stats, sheet_path,
                    invocation_claim=invocation_claim,
                )
                character_paths[name] = str(sheet_path)
                characters[name] = safe_json_load(str(sheet_path)) or deepcopy(sheet)
                built.append(name)
                continue
            encounter = write_pending_stats(
                encounter_path, pending["turnId"], target_id,
                invocation_claim=invocation_claim,
            )
        raise CombatIntentError(
            "%s (%s) can't be acted on right now: no character sheet could be made "
            "for them. Leave them out of targetId, targets and bonusAction this "
            "turn; keep the rest of the batch. For the player, ask with a "
            "requiresPlayerInput choice instead of choosing for them." % (name, target_id),
            actor_id,
            {"retryable": True},
        )
    return encounter, built


def _load_characters(character_paths, context_sheets=None):
    characters = deepcopy(context_sheets or {})
    for name, path in (character_paths or {}).items():
        value = safe_json_load(path)
        if not isinstance(value, dict):
            raise CombatTurnPaused("Could not load character state for %s" % name)
        characters[name] = value
    return characters


def _fresh_rolls(encounter):
    cache = encounter.get("preroll_cache") or {}
    return PersistedPrerollSource(cache.get("rolls", ""), encounter)


def _all_non_player(encounter, actor_ids):
    actors = [combatant_by_id(encounter, actor_id) for actor_id in actor_ids]
    state = encounter.get("combatState") or {}
    return bool(actors) and all(
        actor and resolve_creature_controller(actor, state) == "actor_agent"
        for actor in actors
    )


def _window_kind(encounter, actor_ids):
    actors = [combatant_by_id(encounter, actor_id) for actor_id in (actor_ids or [])]
    if not actors:
        return "clock"
    state = encounter.get("combatState") or {}
    return (
        "player"
        if any(
            actor and resolve_creature_controller(actor, state) == "human"
            for actor in actors
        )
        else "npc"
    )


def _is_human_controlled(encounter, actor):
    return bool(actor) and resolve_creature_controller(
        actor,
        (encounter or {}).get("combatState") or {},
    ) == "human"


def _immutable_voice_intents(npc_voice_intents):
    """Copy once at the coordinator boundary, then reuse unchanged on retries."""
    if not npc_voice_intents:
        # No advisory this turn (a solo party, or no companion lines) is the
        # normal case, not a malformed envelope.
        return MappingProxyType({})
    canonical_voice_intents, _replaced, _residual = normalize_typography_deep(
        npc_voice_intents
    )
    normalized = normalize_npc_voice_intents(canonical_voice_intents)
    if normalized is None:
        _LOGGER.warning("Combat voice advisory envelope was invalid and omitted")
        return MappingProxyType({})
    actors = {
        actor_id: MappingProxyType(dict(row))
        for actor_id, row in normalized["actors"].items()
    }
    return MappingProxyType(
        {
            "contractVersion": normalized["contractVersion"],
            "sourceBeatId": normalized["sourceBeatId"],
            "actors": MappingProxyType(actors),
        }
    )


def _diagnostic_context_counts(spell_references):
    if not isinstance(spell_references, dict):
        return 0, 0
    candidates = spell_references.get("capabilityCandidates") or {}
    candidate_count = sum(
        len(values) for values in candidates.values() if isinstance(values, list)
    ) if isinstance(candidates, dict) else 0
    rule_count = len(spell_references.get("ruleReferences") or []) + len(
        spell_references.get("spellReferences") or {}
    )
    return candidate_count, rule_count


def _provider_failure_class(exc):
    message = str(exc).lower()
    class_name = exc.__class__.__name__
    if class_name == "CombatAgentContractError":
        if "stale" in message or "actor order" in message:
            return "stale_state_or_actor_order"
        if "json" in message or "object" in message:
            return "response_parse_error"
        return "response_contract_error"
    return "provider_error"


def _resolution_failure_class(exc):
    if isinstance(exc, CombatIntentError):
        if isinstance(getattr(exc, "feedback", None), dict) and exc.feedback.get(
            "rulesDrift"
        ):
            return "rules_drift_reject"
        return "intent_validation_error"
    return "mechanical_resolution_error"


def _rendered_rows(rows):
    """K1: legalRows [{rowRef, name}] as correction text, or ''."""
    if not isinstance(rows, list):
        return ""
    return ", ".join(
        "%s %s" % (json.dumps(row.get("rowRef"), sort_keys=True), json.dumps(row.get("name")))
        for row in rows if isinstance(row, dict) and isinstance(row.get("rowRef"), dict)
    )


def _intent_correction(exc, batch=None):
    """Build narrow retry guidance from a deterministic intent rejection."""
    feedback = (
        getattr(exc, "feedback", {})
        if isinstance(getattr(exc, "feedback", None), dict)
        else {}
    )
    instruction = "Return a corrected full ordered intent batch."
    legal_actions = feedback.get("legalActions")
    save_ability = feedback.get("saveAbility")
    if isinstance(save_ability, dict) and save_ability.get("name"):
        # MS-a: the rejected entry is a listed save ability, not an attack
        # roll; the correction gives the adjudicated shape, not a bite.
        conditions = [
            str(name)
            for name in (save_ability.get("conditions") or [])
            if isinstance(name, str) and name
        ]
        instruction = (
            "Return a corrected full ordered intent batch. For the rejected "
            "actor, %r is a save ability, not a known attack: resubmit it "
            "with mode 'adjudicated', abilityRow %s, ability %r, save {type:%r, dc:%s, "
            "halfOnSave:%s}, targets [{combatantId, hpDelta}] (hpDelta 0 when "
            "it only imposes conditions; code rolls its listed damage dice)"
            % (
                save_ability["name"],
                json.dumps(save_ability.get("rowRef"), sort_keys=True),
                save_ability["name"],
                save_ability.get("type"),
                save_ability.get("dc"),
                "true" if save_ability.get("halfOnSave") else "false",
            )
        )
        if conditions:
            instruction += (
                " and effects [{op:'add', owner or combatantId, "
                "applyOn:'failedSave', effect:{name:%r, conditions:%s}}]"
                % (save_ability["name"], json.dumps(conditions))
            )
        instruction += "; or choose a listed known attack (its rowRef as abilityRow) instead."
    elif feedback.get("recharging"):
        # MS-b: the ability waits for its recharge die; name the rest.
        rendered = _rendered_rows(feedback.get("legalRows"))
        instruction = (
            "Return a corrected full ordered intent batch. For the rejected "
            "actor, %r is recharging (it returns on a d6 at the start of that "
            "actor's turn; the creature's recharge record shows it as spent): "
            "do not declare it this turn. Use another listed action%s or a "
            "defensive action."
            % (feedback.get("recharging"), (" (%s)" % rendered) if rendered else "")
        )
    elif _rendered_rows(feedback.get("legalRows")):
        # K1: the row is named by its listed rowRef, never by its name.
        instruction = (
            "Return a corrected full ordered intent batch. For the rejected "
            "known attack, set abilityRow to exactly one listed rowRef from "
            "legalRows (%s) and ability to that row's name; ability is display "
            "text, never an ability score or skill."
        ) % _rendered_rows(feedback.get("legalRows"))
    elif isinstance(legal_actions, list) and legal_actions:
        rendered = [
            str(action).strip()
            for action in legal_actions
            if isinstance(action, str) and action.strip()
        ]
        if rendered:
            instruction = (
                "Return a corrected full ordered intent batch. For the rejected "
                "known attack, set ability to exactly one of legalActions "
                "(%s); ability is the listed weapon/action name, never an "
                "ability score or skill."
            ) % ", ".join(rendered)
    if isinstance(feedback.get("playerChargeRefusal"), list) and feedback["playerChargeRefusal"]:
        # H3b: the player keeps agency over a refused item use.
        items = ", ".join(
            "%s (%s)" % (r.get("name"), r.get("reason"))
            for r in feedback["playerChargeRefusal"] if isinstance(r, dict)
        )
        instruction = (
            "Return a corrected full ordered intent batch. The rules engine "
            "refused the PLAYER's item use: %s. Nothing was spent. Never choose "
            "another action for the player and never resolve a null action: "
            "return the player's intent with empty targets, resources and "
            "effects and requiresPlayerInput {kind:'choice', prompt} where the "
            "prompt narrates the attempt failing (the item flares with no effect "
            "or stays dark, and the bearer remembers it is spent) and asks what "
            "they do instead. If the refusal is only the count and the item's "
            "text costs less per use (one casting, all its darts or targets "
            "included), you may instead re-declare the SAME item use at that "
            "per-use cost. Keep every other intent exactly as given."
            % items
        )
    resource_refusals = feedback.get("playerResourceRefusal")
    if isinstance(resource_refusals, list) and resource_refusals:
        # #671: the player's spend the rules engine refused, by the numbers.
        spends = ", ".join(
            "%s %s, %s left" % (r.get("kind"), r.get("name"), r.get("before")) if r.get("max") is None
            else "%s %s, %s of %s left" % (r.get("kind"), r.get("name"), r.get("before"), r.get("max"))
            for r in resource_refusals if isinstance(r, dict)
        )
        instruction = (
            "Return a corrected full ordered intent batch. The rules engine "
            "refused the PLAYER's spend: %s. Nothing was spent. Never choose "
            "another action for the player and never resolve a null action: "
            "return the player's intent with empty targets, resources and "
            "effects and requiresPlayerInput {kind:'choice', prompt} saying it "
            "cannot be used and asking what they do instead. Keep every other "
            "intent exactly as given."
            % spends
        )
    limits = feedback.get("featureHealLimits")
    option_rows = [r for r in limits if isinstance(r, dict) and "options" in r] if isinstance(limits, list) else []
    if option_rows:
        # F1: the spent pool's options, by name (or Divine Spark's one other target).
        instruction += (
            " For the rejected actor, %s. Heal only as that allows, naming the option in featureName, "
            "or spend nothing; for the player, return the intent with empty targets, resources and "
            "effects and requiresPlayerInput {kind:'choice', prompt} saying so and asking what they do "
            "instead." % _feature_heal_option_fact(option_rows[0])
        )
    elif isinstance(limits, list) and limits:
        # #669: the typed limits of a class-feature heal, by the numbers.
        rendered = "; ".join(
            "%s at most %s (HP %s/%s)" % (r.get("combatantId"), r.get("allowed"), r.get("hpBefore"), r.get("max"))
            if r.get("combatantId") is not None else "no target named, so at most 0"
            for r in limits if isinstance(r, dict)
        )
        feature = next((r.get("ability") for r in limits if isinstance(r, dict) and r.get("ability")), "the feature")
        instruction += (
            " For the rejected actor, %s restores only creatures at or below half their HP maximum, and none "
            "above half: %s. A target whose limit is 0 cannot be chosen. If no target can be healed, spend "
            "nothing; for the player, return the intent with empty targets, resources and effects and "
            "requiresPlayerInput {kind:'choice', prompt} saying so and asking what they do instead."
            % (feature, rendered)
        )
    removals = feedback.get("removalRefusals")
    if isinstance(removals, list) and removals:
        # #725: why each remove op was refused, and the one re-rule.
        named = []
        for refusal in removals:
            if not isinstance(refusal, dict):
                continue
            if refusal.get("reason") == "mustUseOwner":
                # Refused before any match was tried, so the effect may be real:
                # ask to resend it with the owner, not to drop it (review-946-r0).
                named.append("a remove op for %s uses owner %r, never combatantId: resend it with "
                             "owner %r and the same effect or condition."
                             % (refusal.get("combatantId"), refusal.get("owner"), refusal.get("owner")))
            else:
                current = ", ".join(str(name) for name in refusal.get("currentEffects") or [] if name)
                named.append("%s has no effect or condition named %r (current effects: %s): there is "
                             "nothing to remove; drop that remove op."
                             % (refusal.get("owner") or refusal.get("combatantId"),
                                refusal.get("reference"), current or "none"))
        if named:
            instruction += (
                " " + " ".join(named) + " Keep the rest of the action as given. If your next "
                "batch still carries a remove op for this actor that cannot be matched, code drops "
                "it as ruled and resolves the rest."
            )
    keep_targets = feedback.get("keepTargets")
    if isinstance(keep_targets, list) and keep_targets:
        # R1: the stated hit stays; only playerRoll is corrected.
        instruction += (
            " Keep the rejected actor's targets and hpDelta exactly as given (%s); correct only "
            "playerRoll." % json.dumps(keep_targets, sort_keys=True)
        )
    bonus_names = feedback.get("bonusActionNames")
    bonus_problem = feedback.get("bonusActionProblem")
    if isinstance(bonus_names, list) and isinstance(bonus_problem, str):
        # R2: the rejected actor's typed Bonus Actions (bonusActionNames) and
        # what was wrong with the one given.
        if feedback.get("bonusActionNameRefused") is True:
            instruction += (
                " For the rejected actor, bonusAction.featureName must be exactly one of %s; otherwise "
                "leave bonusAction out and keep the Action as given."
                % (", ".join(repr(str(name)) for name in bonus_names) or "none (it has no Bonus Action)")
            )
        else:
            instruction += (
                " For the rejected actor, correct only its bonusAction (%s) and keep the Action as given."
                % bonus_problem
            )
    if feedback.get("multiRollRequest"):
        instruction += (
            " requiresPlayerInput must ask for exactly one next roll or "
            "choice. Ask only for the earliest unresolved roll and use one "
            "exact spellName; a later pass may request the next roll."
        )
    legal_targets = feedback.get("legalTargets")
    if isinstance(legal_targets, list):
        rendered_targets = [
            str(target).strip()
            for target in legal_targets
            if isinstance(target, str) and target.strip()
        ]
        if rendered_targets:
            instruction += (
                " For the rejected actor, targetId must be exactly one of "
                "legalTargets (%s), or choose a non-attack action."
                % ", ".join(rendered_targets)
            )
            if feedback.get("targetDown") is True:
                instruction += (
                    " The creatures list shows HP at the start of this window;"
                    " code resolves your intents in order with this round's"
                    " dice, so the rejected target is at 0 HP by the time the"
                    " rejected actor acts BECAUSE of the earlier intents in"
                    " your own batch. That is not a contradiction of creatures"
                    " and not a reason to move any other actor: redirecting"
                    " earlier attacks onto the legal target changes the"
                    " projection and drops that target instead, which repeats"
                    " this rejection. Keep every earlier intent exactly as"
                    " given and change only the rejected actor."
                )
        else:
            instruction += (
                " No legalTargets remain; the rejected actor must choose a "
                "non-attack action."
            )
    correction = {
        "error": str(exc),
        "actorId": getattr(exc, "actor_id", None),
        "details": feedback,
        "instruction": instruction,
    }
    intents = batch.get("intents") if isinstance(batch, dict) else None
    rejected_actor_id = getattr(exc, "actor_id", None)
    if isinstance(intents, list) and isinstance(rejected_actor_id, str):
        rejected_index = next(
            (
                index
                for index, intent in enumerate(intents)
                if isinstance(intent, dict)
                and intent.get("actorId") == rejected_actor_id
            ),
            None,
        )
        if rejected_index:
            validated_prefix = [
                deepcopy(intent)
                for intent in intents[:rejected_index]
                if isinstance(intent, dict)
            ]
            if len(validated_prefix) == rejected_index:
                correction["validatedIntents"] = validated_prefix
                correction["instruction"] += (
                    " Reuse validatedIntents unchanged for those earlier "
                    "actors; correct the rejected actor and regenerate only "
                    "the unvalidated remainder."
                )
    return correction


def _asked_slot_level(encounter, batch, actor_id, request):
    """#942: the slot level a player's roll request asks its dice at, read as
    the roll audit reads it (the own slot the cast spends, then its typed
    slotLevel); None for anything but a cast, or no level."""
    from core.ai import srd_roll_contracts
    actor = combatant_by_id(encounter, actor_id) if isinstance(actor_id, str) else None
    intents = batch.get("intents") if isinstance(batch, dict) else None
    intent = next((item for item in intents or []
                   if isinstance(item, dict) and item.get("actorId") == actor_id), None)
    if actor is None or intent is None or intent.get("action") != "cast":
        return None
    level = srd_roll_contracts._slot_level(intent, request if isinstance(request, dict) else {},
                                           actor.get("name"))
    return level if type(level) is int and 1 <= level <= 9 else None


def _asked_save_dc(request):
    """Item 10 (r2): the typed dc of a player save request, or None."""
    if not isinstance(request, dict) or str(request.get("phase") or "").strip().lower() != "save":
        return None
    dc = request.get("dc")
    return dc if type(dc) is int and dc > 0 else None


def _check_asked_save_dc(batch, corrected_actors):
    """Item 10 (r2): the player's save is scored at the DC it was asked at
    (playerRoll.requestedDc, typed when the request was made). A save.dc that
    differs goes back once per actor as a correction naming the asked DC;
    after that the engine scores the asked DC and journals the difference."""
    for intent in (batch.get("intents") if isinstance(batch, dict) else None) or []:
        if not isinstance(intent, dict) or intent.get("actorId") in corrected_actors:
            continue
        roll = intent.get("playerRoll")
        asked = roll.get("requestedDc") if isinstance(roll, dict) else None
        save = intent.get("save")
        if type(asked) is not int or not isinstance(save, dict) or save.get("dc") == asked:
            continue
        raise CombatIntentError(
            "the player's save was asked at DC %d; set save.dc to %d (not %r)" % (asked, asked, save.get("dc")),
            intent.get("actorId"),
            {"askedSaveDc": asked, "retryable": True},
        )


def _check_asked_slot_level(encounter, pending, batch):
    """#942 (D-942-1 A): the roll the player just answered was asked at a slot
    level (the previous exchange's requestedSlotLevel), so the human's cast
    spends an own slot of that level; another level is a correction and the
    player's dice stay. An exchange saved without the field checks nothing."""
    from core.ai import srd_roll_contracts
    exchanges = live_exchanges(pending)
    previous = exchanges[-2] if len(exchanges) >= 2 and isinstance(exchanges[-2], dict) else {}
    asked = previous.get("requestedSlotLevel")
    if type(asked) is not int:
        return
    for intent in (batch.get("intents") if isinstance(batch, dict) else None) or []:
        if not isinstance(intent, dict) or intent.get("action") != "cast":
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        if not _is_human_controlled(encounter, actor):
            continue
        spent = srd_roll_contracts._spent_slot_level(intent, actor.get("name"))
        if spent is not None and spent != asked:
            raise CombatIntentError(
                "the player's dice for %s were rolled for a level%d slot; spend a level%d slot, "
                "not level%d" % (intent.get("ability") or "the spell", asked, asked, spent),
                intent.get("actorId"), {"askedSlotLevel": asked})


def _check_answered_roll_faces(encounter_path, encounter, pending, batch, voice_intents=None, reply=None):
    """3b (D-KW-8): the faces of the roll the player just answered are a typed
    field, playerRoll={phase, faces: one list per die term}; code never reads
    them from the player's sentence. The model copies the player's numbers;
    when the game rolled them (#877) code writes them from the stored faces.
    When the player asked the game to roll in their own words, the model
    returns playerRoll={gameRolls: true}: code rolls the request's typed dice
    once, records them, and returns _GAME_ROLL_RERULE so T096 rules again with
    them (#1118, D-1118-1). They are checked against the typed request (the
    previous exchange's requestedRoll): a wrong shape is a correction, a face
    the die cannot show asks the player again, and a playerRoll with no typed
    request behind it is dropped. The engine scores a checked save (resolver)."""
    exchanges = live_exchanges(pending)
    previous = exchanges[-2] if len(exchanges) >= 2 and isinstance(exchanges[-2], dict) else {}
    last = exchanges[-1] if exchanges and isinstance(exchanges[-1], dict) else {}
    terms = (_roll_die_terms(previous.get("requestedRoll"))
             if previous.get("dmRequest") and not last.get("dmRequest") else None)
    phase = previous.get("requestedPhase")
    phase = phase.strip().lower() if isinstance(phase, str) else None
    for intent in (batch.get("intents") if isinstance(batch, dict) else None) or []:
        if not isinstance(intent, dict):
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        if not terms or not _is_human_controlled(encounter, actor):
            intent.pop("playerRoll", None)
            continue
        if last.get("rolledBy") == "game" and isinstance(last.get("rolledFaces"), list):
            intent["playerRoll"] = {"phase": phase, "faces": deepcopy(last["rolledFaces"])}
        roll = intent.get("playerRoll")
        if roll is None:
            continue
        if isinstance(roll, dict) and roll.get("gameRolls") is True and "rolledBy" in last:
            # An answer already marked as rolled is never rolled again: with
            # its faces they were filled above; without them it is dropped.
            intent.pop("playerRoll", None)
            continue
        if isinstance(roll, dict) and roll.get("gameRolls") is True:
            # #1118 (D-1118-1): the typed answer that the game rolls this
            # request. It is rolled once: an answered request (rolledBy above)
            # already holds its faces. When the mark writes nothing, the turn
            # changed on disk since it was loaded: T096 rules again from it too,
            # never from this ruling made without the dice.
            faces = _roll_terms(terms)
            if mark_pending_game_roll(encounter_path, pending.get("turnId"), last.get("playerInput"), faces):
                _show_game_roll(previous, faces)
            return _GAME_ROLL_RERULE
        faces = roll.get("faces") if isinstance(roll, dict) else None
        shaped = (
            isinstance(faces, list)
            and len(faces) == len(terms)
            and all(
                isinstance(group, list) and len(group) == count and all(type(face) is int for face in group)
                for group, (count, _sides) in zip(faces, terms)
            )
        )
        labelled = phase is None or str(roll.get("phase") or "").strip().lower() == phase
        hit = _stated_hit(intent)
        if (shaped and not labelled and hit
                and all(1 <= face <= sides for group, (_count, sides) in zip(faces, terms) for face in group)):
            # R1: the requested faces are there and the intent states a hit;
            # only the phase label is wrong, so the hit stands as answered.
            record_combat_diagnostic(
                record_type="window_outcome",
                callsite="T096",
                outcome="answered_roll_phase_relabelled",
                encounter_id=encounter.get("encounterId"),
                turn_id=pending.get("turnId"),
                revision=(encounter.get("combatState") or {}).get("revision"),
                round_number=(encounter.get("combatState") or {}).get("round"),
                window_kind="player",
                actor_count=len(pending.get("actorIds") or []),
            )
        elif not (shaped and labelled):
            feedback = {"playerRoll": {"requestedRoll": previous.get("requestedRoll"), "phase": phase}}
            if hit and phase == "damage":
                # R1: a damage roll answers a hit already ruled; the correction
                # is about playerRoll only, so the stated hit rides along and a
                # retry that drops it can be held to it.
                feedback["keepTargets"] = hit
            raise CombatIntentError(
                "playerRoll must hold the player's faces for the requested %s%s: the phase and one "
                "list of integers per die term, in order"
                % (previous.get("requestedRoll"), " (%s)" % phase if phase else ""),
                intent.get("actorId"),
                feedback,
            )
        for group, (_count, sides) in zip(faces, terms):
            if all(1 <= face <= sides for face in group):
                continue
            # C2b (#1118, D-1118-4 A): the typed request is kept (re-stored
            # first, as the player saw it); the DM says the numbers do not fit
            # and asks again in its own words, which then replace the shown ask.
            restore = dict(
                requested_die=previous.get("requestedDie"),
                requested_phase=previous.get("requestedPhase"),
                npc_voice_intents=voice_intents,
                requested_roll=previous.get("requestedRoll"),
                requested_slot_level=previous.get("requestedSlotLevel"),
                requested_dc=previous.get("requestedDc"),
                timeout_seconds=None,
            )
            message = str(previous.get("dmRequest") or "").strip()
            record_pending_player_request(encounter_path, pending.get("turnId"), message, **restore)
            asked = {"label": phase or "roll", "phase": phase,
                     "dice": [{"count": count, "sides": die} for count, die in terms], "eachDie": False}
            reworded = _open_roll_reply(encounter, pending, str(last.get("playerInput") or ""), asked, reply,
                                        follow_up=False, unfitting=True)
            if reworded is not None:
                message = reworded
                record_pending_player_request(encounter_path, pending.get("turnId"), message, **restore)
            record_combat_diagnostic(
                record_type="window_outcome",
                callsite="T096",
                outcome="player_roll_rejected",
                encounter_id=encounter.get("encounterId"),
                turn_id=pending.get("turnId"),
                revision=(encounter.get("combatState") or {}).get("revision"),
                round_number=(encounter.get("combatState") or {}).get("round"),
                window_kind="player",
                actor_count=len(pending.get("actorIds") or []),
            )
            raise CombatTurnPaused(
                "Player supplied a face outside the typed roll request",
                player_message=message,
            )
        roll["phase"] = phase
        roll["requestedRoll"] = previous.get("requestedRoll")
        asked_dc = previous.get("requestedDc")
        if phase == "save" and type(asked_dc) is int:
            # Item 10 (r2): the save is scored at the DC it was asked at.
            roll["requestedDc"] = asked_dc
        else:
            roll.pop("requestedDc", None)


def _stated_hit(intent):
    """R1: copies of the intent's targets that take damage (an int hpDelta
    below 0), or None."""
    targets = intent.get("targets") if isinstance(intent, dict) else None
    hit = [
        deepcopy(target)
        for target in (targets if isinstance(targets, list) else [])
        if isinstance(target, dict) and type(target.get("hpDelta")) is int and target["hpDelta"] < 0
    ]
    return hit or None


def _keep_stated_hit(batch, correction):
    """R1 (never lose a stated hit): a damage roll's playerRoll correction
    carries the hit the rejected intent stated (keepTargets, set only for a
    damage request). A retry that answers it with no hit for that actor is
    asked once more; a second such retry gets the model's own earlier hit
    back instead of committing the answered damage on nobody."""
    details = correction.get("details") if isinstance(correction, dict) else None
    if not isinstance(details, dict):
        return
    keep = details.get("keepTargets")
    asked = details.get("playerRoll")
    actor_id = correction.get("actorId")
    if not keep or not isinstance(asked, dict) or not isinstance(actor_id, str):
        return
    for intent in (batch.get("intents") if isinstance(batch, dict) else None) or []:
        if not isinstance(intent, dict) or intent.get("actorId") != actor_id or _stated_hit(intent):
            continue
        if not details.get("keptHitAsked"):
            raise CombatIntentError(
                "the answered %s damage roll belongs to the hit stated before the correction: keep "
                "this intent's targets and hpDelta exactly as given and correct only playerRoll"
                % (asked.get("requestedRoll") or "requested"),
                actor_id,
                {"playerRoll": deepcopy(asked), "keepTargets": deepcopy(keep), "keptHitAsked": True},
            )
        intent["targets"] = deepcopy(keep)
        record_combat_diagnostic(
            record_type="window_outcome",
            callsite="T096",
            outcome="answered_roll_hit_kept",
        )


def _reconcile_validated_prefix(batch, correction):
    """#435: the intents the last correction validated are kept as validated.

    A corrected batch takes the correction's validatedIntents (by actorId) in
    their validated order, then the model's intents for every other actor in
    the model's order: a validated actor the model changed or dropped gets its
    validated intent back. Only the latest correction locks; the rejected
    actor and the remainder stay the model's. The batch is then validated
    and resolved in full as before."""
    validated = correction.get("validatedIntents") if isinstance(correction, dict) else None
    intents = batch.get("intents") if isinstance(batch, dict) else None
    if not isinstance(validated, list) or not validated or not isinstance(intents, list):
        return batch
    if not all(isinstance(intent, dict) and isinstance(intent.get("actorId"), str) for intent in validated):
        return batch
    locked = {intent["actorId"] for intent in validated}
    remainder = [
        intent for intent in intents
        if not (isinstance(intent, dict) and intent.get("actorId") in locked)
    ]
    reconciled = [deepcopy(intent) for intent in validated] + remainder
    if reconciled != intents:
        _LOGGER.info("#435: kept %d validated intent(s) from the correction", len(validated))
    batch = dict(batch)
    batch["intents"] = reconciled
    return batch


def _apply_trusted_spell_durations(batch, spell_references, now_scalar=None):
    """Overlay exact fixed SRD durations onto matching provider effects.

    The provider still chooses whether an effect exists and its targets. This
    only prevents a spell listed in spellActionIndex from silently degrading to
    the resolver's encounter-only default when the model omits duration fields.
    """
    if (
        not isinstance(batch, dict)
        or not isinstance(spell_references, dict)
        or type(now_scalar) is not int
    ):
        return batch
    from core.effects.clock import display_iso_from_scalar, fixed_duration_seconds
    from core.effects.lifecycle import enter_combat_effect

    # Every spell on a window actor's sheet is listed there, so a cast keeps
    # its fixed SRD duration whether or not the player's words named it.
    references = spell_references.get("spellActionIndex")
    if not isinstance(references, list):
        return batch
    trusted = {}
    for reference in references:
        if not isinstance(reference, dict):
            continue
        name = reference.get("name")
        parsed = fixed_duration_seconds(reference.get("duration"))
        if isinstance(name, str) and name.strip() and parsed:
            trusted[name.strip().casefold()] = (
                parsed,
                reference.get("duration").strip(),
            )
    if not trusted:
        return batch

    def trusted_duration(effect_name):
        # The effect name is matched only as a whole value. A display name
        # such as "Aid (2nd-level)" takes its duration from the intent's
        # typed spell fields below, never from reading the name (D-KW-7).
        if not isinstance(effect_name, str):
            return None
        return trusted.get(effect_name.strip().casefold())

    normalized = deepcopy(batch)
    for intent in normalized.get("intents") or []:
        if not isinstance(intent, dict):
            continue
        intent_duration = None
        for field in ("spellName", "spell", "ability", "action"):
            value = intent.get(field)
            if not isinstance(value, str):
                continue
            intent_duration = trusted.get(value.strip().casefold())
            if intent_duration:
                break
        for operation in intent.get("effects") or []:
            if (
                not isinstance(operation, dict)
                or operation.get("op") != "add"
                or not isinstance(operation.get("effect"), dict)
            ):
                continue
            effect = operation["effect"]
            name = effect.get("name")
            duration = trusted_duration(name) or intent_duration
            if not duration:
                continue
            (duration_kind, duration_seconds), display_duration = duration
            effect["durationKind"] = duration_kind
            effect["duration"] = display_duration
            effect["expiration"] = display_iso_from_scalar(
                now_scalar + duration_seconds
            )
            operation["effect"] = enter_combat_effect(effect, now_scalar)
    return normalized


def _set_combat_retry_status():
    try:
        from core.managers.status_manager import status_manager

        status_manager.update_status("The DM is checking the ruling...", is_processing=True)
    except Exception:
        pass


def _require_current_invocation(invocation_claim):
    if invocation_claim is None:
        return
    from core.combat.invocation import require_current_invocation

    require_current_invocation(invocation_claim)


def _same_item_spent(events, refusals):
    """True when the resolved events spend, through the engine, an item the
    player's refused use named (the same owner and item, by value)."""
    wanted = {(r.get("owner"), r.get("name")) for r in refusals or [] if isinstance(r, dict)}
    return any(
        isinstance(resource, dict) and resource.get("kind") == "charges" and resource.get("engine") is True
        and (resource.get("owner"), resource.get("name")) in wanted
        for event in events or [] if isinstance(event, dict)
        for resource in event.get("resources") or []
    )


def _feature_heal_option_fact(row):
    """F1: a refused pool heal's rule, said plainly: the pool's options the
    actor has, none, or Divine Spark's one other target."""
    if row.get("target"):
        return "%s heals exactly one other creature, never the caster" % row.get("ability")
    if row.get("options"):
        return "%s heals only as %s" % (row.get("pool"), " or ".join(row["options"]))
    return "%s has no heal option" % row.get("pool")


def _same_feature_used(events, limits):
    """#669: True when the resolved events still use the class feature the
    refused heal named, by the same actor (the typed featureName, else the
    ability, read by feature_heal_key as the resolver matched it), or (F1)
    still spend the refused pool."""
    wanted = {(r.get("actorId"), feature_heal_key(r.get("ability")))
              for r in limits or [] if isinstance(r, dict)}
    pools = {(r.get("actorId"), feature_heal_key(r.get("pool")))
             for r in limits or [] if isinstance(r, dict) and r.get("pool")}
    return any(
        isinstance(event, dict)
        and ((event.get("actorId"), feature_heal_key(intent_feature_name(event.get("intent")))) in wanted
             or any((event.get("actorId"), feature_heal_key(resource.get("name"))) in pools
                    for resource in event.get("resources") or []
                    if isinstance(resource, dict) and resource.get("kind") == "featureUse"))
        for event in events or []
    )


def _pause_for_refused_feature_heal(encounter_path, pending, limits, voice_intents):
    """#669: the player's feature heal broke its typed limit and the correction
    chose another action instead of asking. Record the DM's question on the
    pending turn and pause, as H3b does for a refused item use."""
    parts = []
    for limit in limits or []:
        if not isinstance(limit, dict):
            continue
        _LOGGER.info("FH: paused for the player: %s limited to %s for %s",
                     limit.get("ability"), limit.get("allowed"), limit.get("combatantId"))
        if "options" in limit:
            parts.append(_feature_heal_option_fact(limit))
            continue
        if limit.get("combatantId") is None:
            parts.append("%s has no target it can heal" % limit.get("ability"))
            continue
        parts.append("%s can restore at most %s to that target (HP %s of %s)" % (
            limit.get("ability"), limit.get("allowed"), limit.get("hpBefore"), limit.get("max")))
    message = "%s. Nothing was spent. What do you do instead?" % (
        "; ".join(parts) or "That healing cannot be used that way")
    record_pending_player_request(
        encounter_path,
        pending.get("turnId"),
        message,
        npc_voice_intents=voice_intents,
    )
    raise CombatTurnPaused(
        "The player's feature heal broke its limit; waiting for the player's choice",
        player_message=message,
    )


def _pause_for_refused_item(encounter_path, pending, refusals, voice_intents):
    """H3b fail-safe: the player's item use was refused and the correction did
    not ask the player. Record the DM's question on the pending turn and pause:
    nothing is staged, the round does not fire, and the player chooses again."""
    facts = {
        "short": "it does not hold enough charges for that",
        "destroyed": "it was destroyed when its last charge was spent",
        "clock": "its charges cannot be counted right now (the game clock could not be read)",
        "unavailable": "the rules engine is not answering right now",
    }
    parts = []
    for refusal in refusals or []:
        if not isinstance(refusal, dict) or not refusal.get("name"):
            continue
        _LOGGER.info("H3b: paused for the player: %s refused (%s)", refusal.get("name"), refusal.get("reason"))
        parts.append("Your %s does not answer: %s" % (
            refusal["name"], facts.get(refusal.get("fact"), "it cannot be used right now")))
    message = "%s. Nothing was spent. What do you do instead?" % (
        "; ".join(parts) or "That item cannot be used right now")
    record_pending_player_request(
        encounter_path,
        pending.get("turnId"),
        message,
        npc_voice_intents=voice_intents,
    )
    raise CombatTurnPaused(
        "The player's item use was refused; waiting for the player's choice",
        player_message=message,
    )


def _pause_for_refused_resource(encounter_path, pending, refusals, voice_intents):
    """#671 fail-safe: the player's spell slot, feature use, item or ammunition
    (#968) was refused (none left) and the correction did not ask the player. Record the code's question
    on the pending turn and pause: nothing is staged, the round does not fire,
    and the player chooses again."""
    parts = []
    for refusal in refusals or []:
        if not isinstance(refusal, dict) or not refusal.get("name"):
            continue
        _LOGGER.info("#671: paused for the player: %s %s refused (%s of %s)", refusal.get("kind"),
                     refusal.get("name"), refusal.get("before"), refusal.get("max"))
        name = str(refusal["name"])
        count = ("%s of %s" % (refusal.get("before"), refusal.get("max"))
                 if refusal.get("max") is not None else "%s left" % refusal.get("before"))
        level = name[len("level"):] if refusal.get("kind") == "spellSlot" and name.startswith("level") else ""
        # Review-966 F11: name the sheet the pool belongs to when it is not the
        # actor's own. F8: a pool with some left says how much the spend needs.
        owner = refusal.get("owner")
        actor = refusal.get("actor")
        other = isinstance(owner, str) and isinstance(actor, str) and owner != actor
        before, need = refusal.get("before"), refusal.get("need")
        short = type(before) is int and before > 0 and type(need) is int
        if refusal.get("kind") in ("item", "ammunition"):
            # #968: a potion or arrows, by count; another sheet's stock is named. An engine
            # refusal of a stock the sheet shows (before >= need) reads as none left.
            who = "%s has" % owner if other else "You have"
            if short and before < need:
                parts.append("%s only %s %s left; this needs %s" % (who, before, name, need))
            else:
                parts.append("%s no %s left" % (who, name))
        elif level.isdigit():
            who = "%s has" % owner if other else "You have"
            if short:
                parts.append("%s only %s level %s spell slot%s left (%s); this needs %s"
                             % (who, before, level, "" if before == 1 else "s", count, need))
            else:
                parts.append("%s no level %s spell slot left (%s)" % (who, level, count))
        else:
            pool = "%s's %s" % (owner, name) if other else name
            if short:
                parts.append("%s has only %s left (%s); this needs %s" % (pool, before, count, need))
            else:
                parts.append("%s has no uses left (%s)" % (pool, count))
    message = "%s. Nothing was spent. What do you do instead?" % (
        "; ".join(parts) or "That cannot be used right now")
    record_pending_player_request(
        encounter_path,
        pending.get("turnId"),
        message,
        npc_voice_intents=voice_intents,
    )
    raise CombatTurnPaused(
        "The player's spend was refused; waiting for the player's choice",
        player_message=message,
    )


def _typed_roll(request):
    """The full typed dice of a roll request ("1d8+1d6"), or None."""
    if not isinstance(request, dict) or request.get("kind") != "roll":
        return None
    terms = _roll_die_terms(request.get("die"))
    return "+".join("%dd%d" % term for term in terms) if terms else None


def _request_text(request):
    if not isinstance(request, dict):
        return "I need one more detail before resolving that action. What do you do?"
    prompt = request.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    reason = request.get("reason")
    die = request.get("die")
    if isinstance(reason, str) and reason.strip() and isinstance(die, str) and die.strip():
        return "Please roll %s for %s." % (die.strip(), reason.strip())
    if isinstance(reason, str) and reason.strip():
        return "I need one more choice before resolving that action: %s." % reason.strip()
    return "I need one more detail before resolving that action. What do you do?"


def _authoritative_requested_die(request):
    """The request's typed main die (#853): the first term of its die, so
    "1d8+1d6" stores "1d8". Its phase is typed beside it and checked against
    it (_validate_roll_request_phase); the request text is never read."""
    if not isinstance(request, dict):
        return None
    return str(request.get("die") or "").strip().lower().split("+", 1)[0].strip() or None


def _composed_player_input(pending, fallback):
    """Render the complete retained action/clarification chain for T096."""
    exchanges = pending.get("playerExchanges") if isinstance(pending, dict) else None
    if not isinstance(exchanges, list) or not exchanges:
        return str(fallback or "")
    lines = []
    live_seen = False
    for index, exchange in enumerate(exchanges):
        if not isinstance(exchange, dict):
            continue
        if exchange.get("withdrawn") is True:
            # #1118 r4: the typed withdrawal; its asks and rolls are moot.
            withdrawn_text = str(exchange.get("playerInput") or "").strip()
            if withdrawn_text:
                lines.append("Withdrawn player action: %s" % withdrawn_text)
            continue
        player_text = str(exchange.get("playerInput") or "").strip()
        request_text = str(exchange.get("dmRequest") or "").strip()
        if player_text:
            if not lines:
                label = "Original player action"
            elif not live_seen:
                label = "Player action"
            else:
                label = "Player follow-up"
            lines.append("%s: %s" % (label, player_text))
        if exchange.get("rolledBy") == "game" and isinstance(exchange.get("rolledFaces"), list):
            # #1118: the game's roll is a record beside the player's own words.
            asked = exchanges[index - 1] if index and isinstance(exchanges[index - 1], dict) else {}
            lines.append(_game_roll_line(asked, exchange["rolledFaces"]))
        if request_text:
            asked_dc = exchange.get("requestedDc")
            if type(asked_dc) is int and asked_dc > 0:
                request_text = "%s (save DC %d)" % (request_text, asked_dc)
            lines.append("DM requested: %s" % request_text)
        live_seen = live_seen or bool(player_text or request_text)
    return "\n".join(lines) or str(fallback or "")


def _pending_actor_names(encounter, pending):
    pending_ids = set((pending or {}).get("actorIds") or [])
    return [
        creature.get("name")
        for creature in encounter.get("creatures", []) or []
        if isinstance(creature, dict)
        and creature.get("combatantId") in pending_ids
        and isinstance(creature.get("name"), str)
    ]


def _audit_batch_spell_roll_requests(batch, encounter, characters):
    """Audit player spell dice without blocking unverified rule profiles."""
    from core.ai.srd_roll_contracts import audit_spell_roll_request

    audits = []
    for intent in (batch or {}).get("intents", []) or []:
        if not isinstance(intent, dict) or not isinstance(
            intent.get("requiresPlayerInput"), dict
        ):
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        if not isinstance(actor, dict) or not _is_human_controlled(encounter, actor):
            continue
        audit = audit_spell_roll_request(
            intent,
            (characters or {}).get(actor.get("name")) or {},
        )
        audits.append(audit)
        # Numeric spell modifiers (including class-feature modifiers) are
        # deliberately not enforced here. The verified sidecar owns only dice
        # count, sides, and level scaling; broader feature enforcement remains
        # a future typed-contract task.
        if audit.get("status") == "rules_drift_reject":
            raise CombatIntentError(
                (
                    "%s requested %s for %s/%s; verified SRD guidance requires %s"
                    % (
                        audit.get("spellName") or "Spell",
                        audit.get("actual") or "unknown dice",
                        audit.get("contractKey") or "unknown_spell",
                        audit.get("phase") or "unknown_phase",
                        audit.get("expected") or "the typed contract dice",
                    )
                ),
                intent.get("actorId"),
                {"rulesDrift": audit},
            )
    return audits


def _sheet_item_and_action_names(sheet):
    """The whole names of everything the sheet lists as an item or action,
    case-folded: equipment item names and the attack/action rows the engine
    scores."""
    names = set()
    for item in (sheet or {}).get("equipment", []) or []:
        if isinstance(item, dict):
            names.add(str(item.get("item_name") or item.get("name") or "").strip().casefold())
    for entry in _action_entries(sheet or {}):
        if isinstance(entry, dict):
            names.add(str(entry.get("name") or "").strip().casefold())
    names.discard("")
    return names


def _validate_player_weapon_question(batch, encounter, characters):
    """#263 (item 4): a player question about a weapon names it in the typed
    weaponName, the exact item or action name from the player's sheet. A name
    the sheet does not list goes back to the model as a correction instead of
    reaching the player. A request with no weaponName (an improvised or
    picked-up weapon) is the model's adjudication and is not checked. Neither
    the request's wording nor the player's words are read."""
    for intent in (batch or {}).get("intents", []) or []:
        if not isinstance(intent, dict):
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        request = intent.get("requiresPlayerInput")
        if (
            not isinstance(actor, dict)
            or not _is_human_controlled(encounter, actor)
            or not isinstance(request, dict)
        ):
            continue
        weapon = request.get("weaponName")
        if not isinstance(weapon, str) or not weapon.strip():
            continue
        names = _sheet_item_and_action_names((characters or {}).get(actor.get("name")))
        if weapon.strip().casefold() in names:
            continue
        raise CombatIntentError(
            (
                "The sheet has no %s; ask about the weapon the player is actually "
                "using, or leave weaponName out if the player is using something "
                "not on their sheet."
            )
            % weapon.strip(),
            intent.get("actorId"),
            {"retryable": True, "issue": "263", "weaponName": weapon.strip()},
        )


def _validate_flat_damage_request(batch, encounter, characters):
    """#1337: a flat-damage row (damageDice "flat", such as an Unarmed Strike)
    has no damage die; the engine scores its damage. A player damage roll
    asked for the attack the intent's abilityRow names goes back to the model
    as a correction. A spell's request (spellName) is not checked. Runs
    before the last attempt only: there the useless ask passes and the engine
    still scores the flat damage. The request's wording is never read."""
    for intent in (batch or {}).get("intents", []) or []:
        if not isinstance(intent, dict):
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        request = intent.get("requiresPlayerInput")
        if (
            not isinstance(actor, dict)
            or not _is_human_controlled(encounter, actor)
            or not isinstance(request, dict)
            or request.get("kind") != "roll"
            or _roll_request_purpose(request) != "damage"
            or (isinstance(request.get("spellName"), str) and request["spellName"].strip())
        ):
            continue
        entry = attack_row(
            (characters or {}).get(actor.get("name")), intent.get("abilityRow"), actor.get("combatantId")
        )
        if not is_flat_attack(entry):
            continue
        raise CombatIntentError(
            (
                "%s deals flat damage that the engine scores; do not ask for a "
                "damage roll. Resolve the attack with the d20 you have."
            )
            % (entry.get("name") or "This attack"),
            intent.get("actorId"),
            {"retryable": True, "issue": "1337", "abilityRow": intent.get("abilityRow")},
        )


def _validate_feature_names(batch, encounter, characters):
    """8b: a heal paid with a class feature's pooled use (POOL_HEALS) names
    its option in the typed featureName, exactly as the actor's featureNames
    list it (the options its sheet qualifies for). A missing or unlisted name
    goes back to the model as a correction; the ability's wording is not
    read. A pool with no option for the actor is the resolver's refusal."""
    for intent in (batch or {}).get("intents", []) or []:
        if not isinstance(intent, dict):
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        sheet = (characters or {}).get((actor or {}).get("name"))
        pool, _spends = spent_heal_pool(encounter, intent)
        if pool is None or not any(declared_heal(entry) > 0 for entry in intent.get("targets") or []
                                   if isinstance(entry, dict)):
            continue
        options = [option["name"] for option in pool_heal_options(sheet, pool)]
        name = intent.get("featureName")
        if not options or (isinstance(name, str) and name.strip() in options):
            continue
        raise CombatIntentError(
            "%s pays for this heal: set featureName to %s, the option used"
            % (pool, " or ".join(repr(option) for option in options)),
            intent.get("actorId"),
            {"retryable": True, "featureNames": options},
        )


def _validate_bonus_actions(batch, encounter, characters):
    """R2: an intent's typed bonusAction names one of the actor's
    bonusActionNames (its sheet's class features whose SRD activation is a
    Bonus Action), checked before any roll is asked. While the intent still
    asks the player for a roll, the checks that need the answer wait (R3:
    Second Wind at full hit points and the Off-hand Attack are checked now)."""
    for intent in (batch or {}).get("intents", []) or []:
        if not isinstance(intent, dict) or intent.get("bonusAction") is None:
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        sheet = (characters or {}).get((actor or {}).get("name"))
        bonus = intent["bonusAction"]
        names = bonus_action_names(sheet)
        problem = bonus_action_problem(sheet, bonus, intent=intent, encounter=encounter,
                                       asking=isinstance(intent.get("requiresPlayerInput"), dict))
        if problem:
            from core.combat.bonus_actions import item_bonus_refusal
            refusal = item_bonus_refusal(sheet, bonus)
            extra = {"playerResourceRefusal": [refusal]} if refusal else {}
            raise CombatIntentError(
                problem,
                intent.get("actorId"),
                {"violations": [problem], "bonusActionNames": names, "bonusActionProblem": problem,
                 "bonusActionNameRefused": bonus_name_refused(sheet, bonus),
                 "bonusActionOptions": bonus_action_options(sheet, bonus), "retryable": True, **extra},
            )


def _check_sent_rows(batch, sent_rows, encounter, characters):
    """K1 (2.1): each abilityRow names the row sent at that position in this
    request; a row that changed since (a value compare, no digest) is
    corrected with the actor's current rows."""
    for actor_id, problem, rows in stale_row_refs(batch, sent_rows, encounter, characters):
        raise CombatIntentError(
            problem, actor_id, {"violations": [problem], "legalRows": rows, "retryable": True})


def _validate_attack_count(batch, encounter, characters):
    """R3 (F3): the player's attack states no more attacks than the sheet's
    Attack action makes with that weapon (attack_sequence: Extra Attack, a
    typed count). A second weapon's swing is the Off-hand Attack bonusAction,
    not a second attack of the Action."""
    for intent in (batch or {}).get("intents", []) or []:
        if not isinstance(intent, dict) or intent.get("action") != "attack":
            continue
        attacks = intent.get("attacks")
        actor = combatant_by_id(encounter, intent.get("actorId"))
        if type(attacks) is not int or attacks <= 1 or actor is None or not _is_human_controlled(encounter, actor):
            continue
        sheet = (characters or {}).get(actor.get("name"))
        allowed = len(attack_sequence(sheet or {},
                                      selected=attack_row(sheet, intent.get("abilityRow"), actor.get("combatantId")),
                                      num_attacks=actor.get("numAttacks"), sequence=actor.get("multiattackSequence")))
        if attacks <= allowed:
            continue
        problem = "%s's Attack action makes %d attack%s this turn; attacks %d is more." % (
            actor.get("name") or actor.get("combatantId"), allowed, "" if allowed == 1 else "s", attacks)
        if OFF_HAND_ATTACK in bonus_action_names(sheet):
            problem += (" The swing with the other Light weapon in hand is the bonus action: set attacks to %d and "
                        "put it in bonusAction {featureName:'%s', abilityRow: that weapon's listed rowRef, "
                        "ability: its name, targetId}." % (allowed, OFF_HAND_ATTACK))
        else:
            problem += " Set attacks to %d." % allowed
        raise CombatIntentError(
            problem,
            intent.get("actorId"),
            {"violations": [problem], "attackCount": {"stated": attacks, "allowed": allowed}, "retryable": True},
        )


def _validate_player_input_request_ownership(batch, encounter):
    """A player roll request with phase 'save' names the creature making the
    save in the typed saverId. The player is only asked for their own save:
    another creature's save goes in the intent's save field, where code rolls
    it. Nothing is read from the request's wording."""
    for intent in (batch or {}).get("intents", []) or []:
        if not isinstance(intent, dict):
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        request = intent.get("requiresPlayerInput")
        if (
            not isinstance(actor, dict)
            or not _is_human_controlled(encounter, actor)
            or not isinstance(request, dict)
            or request.get("kind") != "roll"
            or str(request.get("phase") or "").strip().lower() != "save"
        ):
            continue
        saver = request.get("saverId")
        if not isinstance(saver, str) or not saver.strip():
            raise CombatIntentError(
                "a requiresPlayerInput roll with phase 'save' must set saverId, the "
                "combatantId of the creature making the save",
                intent.get("actorId"),
                {"requestOwnership": "missing_saver"},
            )
        if saver.strip() == actor.get("combatantId"):
            continue
        creature = combatant_by_id(encounter, saver.strip())
        name = str((creature or {}).get("name") or saver.strip())
        raise CombatIntentError(
            (
                "requiresPlayerInput cannot ask the player to make %s's "
                "saving throw; declare the target save in the intent so "
                "code rolls it, and ask only for any player-owned damage roll"
            )
            % name,
            intent.get("actorId"),
            {
                "requestOwnership": "non_player_save",
                "nonPlayerCombatantId": saver.strip(),
            },
        )


# #853: the labels a non-spell player roll may name; a spell names its own
# typed phase (data/srd_spell_roll_contracts.json).
_ROLL_PHASES = ("attack", "damage", "healing", "save", "check")
_ROLL_TERM = re.compile(r"(\d*)d(4|6|8|10|12|20|100)")


def _roll_die_terms(die):
    """``[(count, sides), ...]`` for a typed die such as "1d8" or "1d8+1d6"
    (rider dice join the main die with +, main die first), or None."""
    terms = []
    for part in str(die or "").strip().lower().split("+"):
        match = _ROLL_TERM.fullmatch(part.strip())
        if match is None:
            return None
        terms.append((int(match.group(1) or 1), int(match.group(2))))
    return terms


def _spell_phase_purpose(spell_name, phase):
    """The typed purpose of a spell's contract phase, or None."""
    try:
        from core.ai import srd_roll_contracts

        key = srd_roll_contracts._canonical_key(spell_name)
        contracts = srd_roll_contracts.load_spell_roll_contracts().get("contracts") or {}
    except Exception:
        return None
    contract = contracts.get(key) if key else None
    phases = contract.get("phases") if isinstance(contract, dict) else None
    for entry in phases if isinstance(phases, list) else []:
        if isinstance(entry, dict) and entry.get("id") == phase:
            return entry.get("purpose")
    return None


def _roll_request_purpose(request):
    """The typed purpose of a player roll request (#853): the spell's
    contract phase purpose when a spell is named, else the plain label,
    else None. The phase is read stripped and casefolded; the request text
    is never read."""
    if not isinstance(request, dict):
        return None
    phase = request.get("phase").strip().casefold() if isinstance(request.get("phase"), str) else ""
    spell = request.get("spellName").strip() if isinstance(request.get("spellName"), str) else ""
    # A spell names its contract phase; a plain label keeps its own rule
    # even with a spell named (an ambiguous contract has no phases).
    return ((_spell_phase_purpose(spell, phase) if spell else None)
            or (phase if phase in _ROLL_PHASES else None))


def _validate_roll_request_phase(batch, encounter):
    """#853: a player roll request names its phase and its die as typed
    fields, and the two agree: an attack's main die is 1d20 (2d20 with
    advantage or disadvantage), and damage or healing never uses a d20. The
    phase is kept casefolded. The request text is never read."""
    for intent in (batch or {}).get("intents", []) or []:
        if not isinstance(intent, dict):
            continue
        actor = combatant_by_id(encounter, intent.get("actorId"))
        request = intent.get("requiresPlayerInput")
        if (
            not isinstance(actor, dict)
            or not _is_human_controlled(encounter, actor)
            or not isinstance(request, dict)
            or request.get("kind") != "roll"
        ):
            continue
        phase = request.get("phase").strip().casefold() if isinstance(request.get("phase"), str) else ""
        if phase and request.get("phase") != phase:
            request["phase"] = phase
        spell = request.get("spellName").strip() if isinstance(request.get("spellName"), str) else ""
        terms = _roll_die_terms(request.get("die"))
        purpose = _roll_request_purpose(request)
        problem = None
        if not phase:
            problem = ("requiresPlayerInput roll needs phase: the spell's typed phase, "
                       "or 'attack', 'damage', 'healing', 'save' or 'check'")
        elif not spell and phase not in _ROLL_PHASES:
            problem = ("requiresPlayerInput phase %r must be 'attack', 'damage', 'healing', 'save' or 'check'"
                       % phase)
        elif terms is None:
            problem = ("requiresPlayerInput roll needs die: dice only, such as '1d20', '2d6' or "
                       "'1d8+1d6' (main die first), with no flat bonus")
        elif purpose == "attack" and (
            terms[0][1] != 20 or terms[0][0] not in (1, 2) or any(sides == 20 for _count, sides in terms[1:])
        ):
            problem = ("requiresPlayerInput phase %r is an attack roll: its main die must be 1d20 "
                       "(2d20 with advantage or disadvantage), not %s" % (phase, request.get("die")))
        elif purpose in ("damage", "healing") and any(sides == 20 for _count, sides in terms):
            problem = "requiresPlayerInput phase %r cannot use a d20 (%s)" % (phase, request.get("die"))
        if problem:
            raise CombatIntentError(
                problem,
                intent.get("actorId"),
                {"rollRequest": {"phase": phase or None, "die": request.get("die"),
                                 "spellName": spell or None}},
            )


# Item 3: the player's plain melee weapon swing, or (D-HC-1) ammunition shot.
# Code holds the dice (the DM's
# lead asks, a dice card records them; the terminal line is the [ROLL] tag),
# takes bare typed numbers on the fast path (D-KW-1/D-KW-2; the tray sentence
# is D-KW-2's exact generated form until the typed tray payload ships, D-KW-14's
# sunset, #1116), and scores the swing; any other
# answer is read by T126 (#1118).
_ROLL_NUMBERS = re.compile(r"^\s*(\d{1,3})(?:[\s,]+(\d{1,3}))?\s*$")
# #879: a Great Weapon Fighting swing takes each damage die (a critical 2d6 is 4).
_FACE_LIST = re.compile(r"^\s*\d{1,3}(?:[\s,]+\d{1,3})*\s*$")
# #249: the browser cannot send a blank line, so "roll" asks the game to roll,
# and its dice tray inserts a whole sentence ("I rolled a 14 on a d20.", or
# "I rolled a 5 on a d8 and a 3 on a d8. My damage dice add up to 8.").
_LET_THE_GAME_ROLL = {"roll", "roll for me", "you roll"}


def _lets_the_game_roll(text):
    """The exact words that ask the game to roll (#249, #830, #877)."""
    return isinstance(text, str) and text.strip().rstrip(".!").casefold() in _LET_THE_GAME_ROLL


# #1118: the typed re-rule value of _check_answered_roll_faces: the game
# rolled the open request's dice, so T096 rules the turn again with them.
_GAME_ROLL_RERULE = "game_roll_rerule"


def _roll_terms(terms):
    """The game's faces for typed die terms [(count, sides), ...]: one list
    per term, in order (#877). The one roller for a request the game rolls."""
    rng = random.SystemRandom()
    return [[rng.randint(1, sides) for _ in range(count)] for count, sides in terms]


def _game_roll_line(request, faces):
    """The record of the game's roll for a DM request, from typed fields only
    (the request exchange's requestedRoll, or a code phase's requestedDie, and
    requestedPhase; its prose is never read): "Game roll for the DM's request (damage): 4 and 2 on the
    2d6." T096 reads it beside the player's words and the player sees it as
    a system card (#1118)."""
    terms = _roll_die_terms((request or {}).get("requestedRoll") or (request or {}).get("requestedDie")) or []
    if len(terms) != len(faces):
        terms = [None] * len(faces)
    parts = []
    for group, term in zip(faces, terms):
        rolled = " and ".join(str(face) for face in group)
        if term is not None:
            count, sides = term
            rolled = "%s on the %s" % (rolled, "d%d" % sides if count == 1 else "%dd%d" % (count, sides))
        parts.append(rolled)
    phase = (request or {}).get("requestedPhase")
    asked = " (%s)" % phase.strip() if isinstance(phase, str) and phase.strip() else ""
    return "Game roll for the DM's request%s: %s." % (asked, " and ".join(parts))


def _show_game_roll(request, faces):
    """Show the player the game's roll at once, as a system card (#1118)."""
    from core.managers.checks_runtime import _show_check_receipt

    _show_check_receipt(_game_roll_line(request, faces))


def _game_roll_answer(pending, text):
    """#877: the answer to the open typed roll request when the player types
    the exact D-KW-1 line: the faces per die term, rolled by _roll_terms.
    "answered" when the last exchange already holds the game's roll and
    the DM has not asked again (a resumed turn re-sending "roll"). None
    for any other line, or when no typed request is open: the line then
    goes to the DM as today. It writes no sentence for the player."""
    if not _lets_the_game_roll(text):
        return None
    exchanges = live_exchanges(pending)
    if not exchanges:
        return None
    last = exchanges[-1]
    if last.get("rolledBy") == "game" and not last.get("dmRequest"):
        return "answered"
    terms = _roll_die_terms(last.get("requestedRoll")) if last.get("dmRequest") else None
    if not terms:
        return None
    return _roll_terms(terms)
_TRAY_DIE = r"a (\d{1,3}) on a d(\d{1,3})"
_TRAY_SENTENCE = re.compile(
    r"^\s*I rolled %s(?:(?:, | and )%s)*\.(?: My damage dice add up to \d{1,4}\.)?\s*$" % (_TRAY_DIE, _TRAY_DIE),
    re.IGNORECASE,
)


def _tray_faces(text, record, entry):
    """The typed values a dice-tray sentence carries for the open phase,
    "invalid" when its dice are not the ones asked for, None when the text is
    not a tray sentence."""
    if not _TRAY_SENTENCE.match(text):
        return None
    dice = [(int(face), int(die)) for face, die in re.findall(_TRAY_DIE, text, re.IGNORECASE)]
    count, sides = player_weapon_attack_dice(record, entry)
    wanted = 20 if record.get("phase") == "attack" else sides
    if len(dice) != count or any(die != wanted or not 1 <= face <= die for face, die in dice):
        return "invalid"
    return [face for face, _die in dice]


_DUPLICATE_SUFFIX_RE = re.compile(r"_(\d+)\b")


def _spoken_name(name):
    """A combatant name as the player reads it: the engine keeps duplicate
    monsters apart as "Bandit Sentry_2"; the request says "Bandit Sentry 2"."""
    return _DUPLICATE_SUFFIX_RE.sub(r" \1", str(name or ""))


_ENGINE_LABEL_RE = re.compile(r" \([^()]*\)$")


def _spoken_weapon(record, entry):
    """The weapon as the player reads it (#860): genesis labels an engine row
    "Longsword (Strength)" to keep a weapon's attacks apart; the request says
    "Longsword". record["ability"] keeps the row's full name (K1: the row
    itself is found by record["abilityRow"])."""
    name = str(record.get("ability") or "")
    if isinstance(entry, dict) and entry.get("engine") is True:
        return _ENGINE_LABEL_RE.sub("", name)
    return name


def _wants_each_die(record, count):
    """#879 (owner D-879-1): a Great Weapon Fighting damage roll of two or more
    dice asks for each die; the flag was read when the damage was asked for."""
    return (record.get("phase") == "damage" and record.get("greatWeapon") is True
            and not isinstance(record.get("spell"), dict) and count >= 2)


def _roll_card(record, entry):
    """The dice card of the open phase (#1118, D-1118-8 D): a record of what is
    rolled, for what, and what code already scored; never an ask (the DM's
    lead asks). Also stores record["dice"]."""
    count, sides = player_weapon_attack_dice(record, entry)
    record["dice"] = "%dd%d" % (count, sides)
    if record.get("phase") == "attack":
        why = (
            " (%s from %s)" % (record.get("mode"), ", ".join(record.get("modeSources") or []))
            if count == 2 else ""
        )
        card = "%s attack on %s: %dd20%s" % (
            _phase_weapon(record, entry), _spoken_name(record.get("targetName")), count, why,
        )
        main = record.get("mainSwing") if isinstance(record.get("mainSwing"), dict) else {}
        if record.get("bonusAttack") is True and type(main.get("attackTotal")) is int:
            # R3: the Action's code-scored swing comes first.
            card = "%s %s, %s vs AC %s. %s" % (
                main.get("spokenWeapon") or main.get("ability"),
                "critical hit" if main.get("critical") else "hit" if main.get("hit") else "miss",
                main.get("attackTotal"), main.get("targetAC"), card)
        return card
    spell = record.get("spell") if isinstance(record.get("spell"), dict) else {}
    if spell.get("type") == "save":
        # #723: the saves are scored first; the card states each one.
        save = spell.get("save") or {}
        verdicts = []
        for result in save.get("results") or []:
            verdicts.append("%s %s (%s save %s vs DC %s%s)" % (
                _spoken_name(result.get("name")), "succeeds" if result.get("success") else "fails",
                str(save.get("type") or "").capitalize(), result.get("total"), save.get("dc"),
                {"half": ", half damage", "none": ", no damage"}.get(result.get("effect"), ""),
            ))
        return "%s: %s. Damage: %dd%d, the total" % (record.get("ability"), "; ".join(verdicts), count, sides)
    hit = (
        "critical hit" if record.get("critical")
        else "hit, %s vs AC %s," % (record.get("attackTotal"), record.get("targetAC"))
    )
    what = "each die" if _wants_each_die(record, count) else "the total"
    return "%s %s on %s. Damage: %dd%d, %s" % (
        _phase_weapon(record, entry), hit, _spoken_name(record.get("targetName")), count, sides, what,
    )


def _phase_weapon(record, entry):
    """The weapon the open phase names; R3: the Off-hand Attack says so."""
    weapon = _spoken_weapon(record, entry)
    return "Off-hand %s" % weapon if record.get("bonusAttack") is True else weapon


def _roll_lead(record, key):
    """The DM's own words for this request (#860): T096's typed rollLead or
    hitLead on the stored intent of this actor, or "" when there is none."""
    batch = record.get("batch") if isinstance(record.get("batch"), dict) else {}
    for intent in batch.get("intents") or []:
        if isinstance(intent, dict) and intent.get("actorId") == record.get("actorId"):
            value = intent.get(key)
            return value.strip() if isinstance(value, str) else ""
    return ""


def _phase_lead(record):
    """The DM's own words for the open phase (#860): T096's rollLead or hitLead.
    R3: the Off-hand Attack has none; its card is the ask."""
    if record.get("bonusAttack") is True:
        return ""
    spell = record.get("spell") if isinstance(record.get("spell"), dict) else {}
    key = "hitLead" if record.get("phase") == "damage" and spell.get("type") != "save" else "rollLead"
    return _roll_lead(record, key)


def _join_ask(lead, card):
    """The ask as one text, for T096's dmRequest and T126's ``asked``."""
    return "%s %s" % (lead, card) if lead else card


def _weapon_attack_prompt(record, entry):
    """Write the open phase's ask on the record: the DM's ``lead``, the dice
    ``card`` under a fresh ``cardId``, and ``prompt``, their join (#1118,
    D-1118-8 D: the DM asks, code keeps the dice). Returns the prompt."""
    from core.managers.checks_runtime import new_message_id

    record["lead"] = _phase_lead(record)
    record["card"] = _roll_card(record, entry)
    record["cardId"] = new_message_id()
    record["prompt"] = _join_ask(record["lead"], record["card"])
    return record["prompt"]


def _rebuild_ask(record, entry):
    """A phase saved before #1118 has only ``prompt``: its lead and card are
    rebuilt from typed fields (never by splitting the prompt); it has no
    cardId until the next write that sets one."""
    if isinstance(record.get("card"), str):
        return
    record["lead"] = _phase_lead(record)
    record["card"] = _roll_card(record, entry)


def _fitting_values(values, record, entry):
    """The values when they fit the open phase's dice, else "invalid": each die,
    each d20, or one total (#879). The one fit compare for typed numbers and
    T126's faces."""
    count, sides = player_weapon_attack_dice(record, entry)
    if _wants_each_die(record, count):
        fits = len(values) == count and all(1 <= value <= sides for value in values)
    elif record.get("phase") == "attack":
        fits = len(values) == count and all(1 <= value <= 20 for value in values)
    else:
        fits = len(values) == 1 and count <= values[0] <= count * sides
    return list(values) if fits else "invalid"


def _parse_weapon_roll(text, record, entry):
    """[] for a blank line or "roll" (the game rolls), the typed values when
    they fit the open phase, "invalid" for numbers that do not, None for
    anything else."""
    if text is None:
        return None
    if not text.strip() or _lets_the_game_roll(text):
        return []
    count, _sides = player_weapon_attack_dice(record, entry)
    if _wants_each_die(record, count):
        if not _FACE_LIST.match(text):
            return _tray_faces(text, record, entry)
        return _fitting_values([int(value) for value in re.findall(r"\d+", text)], record, entry)
    match = _ROLL_NUMBERS.match(text)
    if not match:
        return _tray_faces(text, record, entry)
    return _fitting_values([int(group) for group in match.groups() if group is not None], record, entry)


def _roll_already_answered(pending):
    """True when an earlier exchange this turn carries the typed request for a
    d20 (``requestedDie`` "d20", "1d20" or "2d20") and the player has answered
    it. The request text is never read (#852)."""
    exchanges = live_exchanges(pending)
    for exchange in exchanges[:-1]:
        if not isinstance(exchange, dict):
            continue
        count, marker, sides = str(exchange.get("requestedDie") or "").strip().lower().partition("d")
        if marker and sides == "20" and (count == "" or count.isdigit()):
            return True
    return False


def _request_is_the_swings(request):
    """#880: True when the code-issued roll may supersede the intent's own
    request: none, a roll with no phase, or a roll whose typed purpose is
    the swing's attack or damage. Any other roll, or a choice, is the
    model's to ask (Second Wind's heal before the swing)."""
    if not request:
        # None or an empty object: the pipeline reads both as no request.
        return True
    if not isinstance(request, dict) or request.get("kind") != "roll":
        return False
    phase = request.get("phase")
    if not (isinstance(phase, str) and phase.strip()):
        return True
    return _roll_request_purpose(request) in ("attack", "damage")


def _player_weapon_takeover(encounter, characters, pending, batch):
    """(record, entry) when the window opens with the human player's plain
    melee weapon swing or ammunition shot (D-HC-1), a cast of a recorded spell attack (#672) or of a
    recorded save spell, save first (#723); None keeps today's path. The other
    intents are checked the way resolution checks them, so a bad one still
    goes to the normal correction before any roll is asked for."""
    actor_ids = pending.get("actorIds") or []
    state = encounter.get("combatState") or {}
    first = combatant_by_id(encounter, actor_ids[0]) if actor_ids else None
    if first is None or resolve_creature_controller(first, state) != "human":
        return None
    if _roll_already_answered(pending):
        # #249: this turn already asked the player for a d20 (the model's own
        # request, or a code phase that fell back) and has the answer; asking
        # again would throw that die away, so the model keeps the window.
        return None
    intents = _ordered_intents(batch, state.get("revision"))
    intent = intents[0] if intents and isinstance(intents[0], dict) else None
    if intent is None or intent.get("actorId") != actor_ids[0] or intent.get("mode") != "adjudicated":
        return None
    if not _request_is_the_swings(intent.get("requiresPlayerInput")):
        # #880: the intent carries another roll or a choice; the model's
        # path shows it, and the swing is asked for after it.
        return None
    entry = player_weapon_attack_entry(encounter, characters, intent)
    spell = None
    record = None
    refusal = player_ammunition_refusal(encounter, characters, intent) if entry is None else None
    if refusal is not None:
        # D-HC-1: a shot with no ammunition of its typed kind left is refused
        # with the typed #968 record, so the model asks what the player does
        # instead; it never falls to a spend by the ammunition's name.
        raise CombatIntentError(
            "overspend rejected: %s ammunition for %s (none left)"
            % (refusal.get("owner"), refusal.get("ability")),
            intent.get("actorId"),
            {"violations": ["overspend rejected: %s ammunition for %s (none left)"
                            % (refusal.get("owner"), refusal.get("ability"))],
             "playerResourceRefusal": [refusal], "retryable": True},
        )
    if entry is None:
        spell = player_spell_attack_entry(encounter, characters, intent)
        if spell is None:
            save_spell = player_spell_save_entry(encounter, characters, intent)
            # The saves are scored now from a fresh copy of the persisted
            # prerolls (nothing is consumed until the window commits).
            record = (open_player_spell_save(encounter, characters, intent, save_spell, _fresh_rolls(encounter))
                      if save_spell is not None else None)
            if record is None:
                return None
        elif spell_attack_violations(encounter, characters, intent, spell):
            # A cast whose slot or effects would not resolve keeps today's
            # path, where the normal correction answers it.
            return None
    for index, actor_id in enumerate(actor_ids[1:], start=1):
        other = _intent_for_actor(intents, index, actor_id)
        actor = combatant_by_id(encounter, actor_id)
        if actor is None or not is_turn_eligible(actor):
            continue
        other["stateVersion"] = state.get("revision")
        mode = other.get("mode", "known")
        valid, rejection = validate_intent(encounter, characters, other, strict=mode == "known")
        if not valid:
            raise CombatIntentError(rejection.get("reason", "Intent rejected"), actor_id, dict(rejection))
    if len(intents) != len(actor_ids):
        raise CombatIntentError("Intent batch contains actors outside the claimed window")
    if record is not None:
        entry = weapon_attack_sheet_entry(encounter, characters, record)
    elif spell is not None:
        record = open_player_spell_attack(encounter, characters, intent, spell, _fresh_rolls(encounter))
        entry = weapon_attack_sheet_entry(encounter, characters, record)
    else:
        record = open_player_weapon_attack(encounter, characters, intent, entry, _fresh_rolls(encounter))
    record["batch"] = deepcopy(batch)
    for stored in record["batch"].get("intents") or []:
        # Code asks for this swing's dice; the model's own request (if any)
        # is superseded by the code-issued roll phase.
        if isinstance(stored, dict) and stored.get("actorId") == record["actorId"]:
            stored.pop("requiresPlayerInput", None)
    if record.get("ready") is not True:
        record["prompt"] = _weapon_attack_prompt(record, entry)
    return record, entry


def _phase_kind(record):
    """The diagnostics name of a code-issued roll phase."""
    spell = record.get("spell") if isinstance(record, dict) else None
    if isinstance(spell, dict):
        return "spell_save" if spell.get("type") == "save" else "spell_attack"
    if isinstance(record, dict) and record.get("bonusAttack") is True:
        return "off_hand_attack"
    return "weapon_attack"


def _open_off_hand_phase(encounter_path, encounter, characters, pending, batch, signal, main_swing=None,
                         voice_intents=None):
    """R3: the code-issued roll phase for the player's Off-hand Attack (owner:
    code asks its d20, then its damage, after the Action). It stores the batch
    the Action resolved from and the Action's completed code swing (if any),
    so the window resolves from the dice with no second model pass. Returns
    the open phase record (its lead, card and cardId)."""
    request = signal.request
    phase_intent = {"actorId": signal.actor_id, "ability": request.get("ability"),
                    "abilityRow": deepcopy(request.get("abilityRow")), "targetId": request.get("targetId")}
    entry = weapon_attack_sheet_entry(encounter, characters, phase_intent)
    record = open_player_weapon_attack(encounter, characters, phase_intent, entry, _fresh_rolls(encounter))
    record["bonusAttack"] = True
    record["batch"] = deepcopy(batch)
    if isinstance(main_swing, dict):
        record["mainSwing"] = {key: deepcopy(value) for key, value in main_swing.items()
                               if key not in ("batch", "prompt", "dice", "lead", "card", "cardId")}
        record["mainSwing"]["spokenWeapon"] = _spoken_weapon(
            main_swing, weapon_attack_sheet_entry(encounter, characters, main_swing))
    record["prompt"] = _weapon_attack_prompt(record, entry)
    write_weapon_attack(
        encounter_path,
        pending.get("turnId"),
        record,
        player_message=record["prompt"],
        requested_die=record.get("dice"),
        npc_voice_intents=voice_intents,
        requested_phase=record.get("phase"),
        timeout_seconds=None,
    )
    record_combat_diagnostic(
        record_type="window_outcome",
        callsite="T096",
        outcome="off_hand_attack_opened",
        encounter_id=encounter.get("encounterId"),
        turn_id=pending.get("turnId"),
        revision=(encounter.get("combatState") or {}).get("revision"),
        round_number=(encounter.get("combatState") or {}).get("round"),
        window_kind="player",
        actor_count=len(pending.get("actorIds") or []),
    )
    return record


def _resolve_ready_phase(encounter_path, encounter, characters, pending):
    """Item 3: resolve the window from a completed code-issued roll phase,
    with the batch the model gave when the phase opened (no second T096
    pass). Returns (pending, events, roll_consumption, preview_characters);
    events is None after a fallback, when the model rules the window."""
    ready_attack = pending.get("weaponAttack")
    try:
        rolls = _fresh_rolls(encounter)
        events, _preview_encounter, preview_characters = resolve_claimed_window(
            encounter,
            characters,
            pending,
            deepcopy(ready_attack.get("batch")),
            rolls,
        )
        roll_consumption = rolls.consumption()
        record_combat_diagnostic(
            record_type="window_outcome",
            callsite="T096",
            outcome="%s_scored" % _phase_kind(ready_attack),
            encounter_id=encounter.get("encounterId"),
            turn_id=pending.get("turnId"),
            revision=(encounter.get("combatState") or {}).get("revision"),
            round_number=(encounter.get("combatState") or {}).get("round"),
            window_kind="player",
            actor_count=len(pending.get("actorIds") or []),
        )
        return pending, events, roll_consumption, preview_characters
    except CombatBonusAttackRollRequired as signal:
        # R3: the Action's swing is scored; code asks the Off-hand Attack's dice.
        record = _open_off_hand_phase(
            encounter_path, encounter, characters, pending, ready_attack.get("batch"), signal,
            main_swing=ready_attack,
        )
        raise _phase_paused("Code-issued off-hand roll is waiting for the player", record)
    except (CombatIntentError, IndexError, TypeError, ValueError):
        # Fail forward: the stored batch no longer resolves, so the model
        # rules the window from the exchanges, which keep the typed faces.
        pending = write_weapon_attack(encounter_path, pending.get("turnId"), None)
        record_combat_diagnostic(
            record_type="window_outcome",
            callsite="T096",
            outcome="%s_fallback" % _phase_kind(ready_attack),
            encounter_id=encounter.get("encounterId"),
            turn_id=pending.get("turnId"),
            revision=(encounter.get("combatState") or {}).get("revision"),
            round_number=(encounter.get("combatState") or {}).get("round"),
            window_kind="player",
            actor_count=len(pending.get("actorIds") or []),
        )
        return pending, None, None, None


def _phase_request(record, entry):
    """The typed open roll of a code phase, as T126 and the re-ask read it."""
    count, sides = player_weapon_attack_dice(record, entry)
    phase = record.get("phase")
    return {"label": _phase_weapon(record, entry), "phase": phase,
            "dice": [{"count": count, "sides": 20 if phase == "attack" else sides}],
            "eachDie": _wants_each_die(record, count)}


def _main_swing_facts(record):
    """R3: the Action's scored, uncommitted swing at the off-hand phase, as typed facts."""
    main = record.get("mainSwing") if record.get("bonusAttack") is True else None
    if not isinstance(main, dict):
        return None
    return {"weapon": main.get("spokenWeapon") or main.get("ability"),
            "target": _spoken_name(main.get("targetName")), "hit": main.get("hit") is True,
            "critical": main.get("critical") is True, "attackTotal": main.get("attackTotal"),
            "targetAC": main.get("targetAC")}


def _phase_diagnostic(encounter, pending, callsite, outcome, **extra):
    record_combat_diagnostic(
        record_type="window_outcome",
        callsite=callsite,
        outcome=outcome,
        encounter_id=encounter.get("encounterId"),
        turn_id=pending.get("turnId"),
        revision=(encounter.get("combatState") or {}).get("revision"),
        round_number=(encounter.get("combatState") or {}).get("round"),
        window_kind="player",
        actor_count=len(pending.get("actorIds") or []),
        **extra,
    )


_DROP_ROLL = object()


def _open_roll_reply(encounter, pending, line, request, reply, *, follow_up, unfitting=False,
                     reader_unavailable=False, main_swing=None, allow_drop=False):
    """Item 2 (#1118, D-1118-4 A): the re-ask in the DM's own words. One
    words-only T096 call (correction openRollReply) answers the player's line
    and asks again for the same open roll; code keeps the request, and only
    the player intent's requiresPlayerInput prompt is used. Returns that text,
    stripped, or None: the caller then shows the stored request again. Where
    the caller allows it (the main-hand code phase), the DM may instead give
    the roll up with the typed dropRoll on the player's intent: _DROP_ROLL is
    returned and the caller acts on it as on a T126 decline (#1118 r4). A
    dropRoll the caller did not allow returns None."""
    from core.combat.invocation import InvocationSupersededError
    from utils.capture.live_provider_call import LiveProviderSuperseded

    if not isinstance(reply, dict) or reply.get("intent_provider") is None:
        return None
    open_reply = dict(request)
    if unfitting:
        open_reply["unfitting"] = True
    if reader_unavailable:
        open_reply["readerUnavailable"] = True
    if main_swing:
        open_reply["mainSwing"] = main_swing
    if allow_drop:
        open_reply["dropAllowed"] = True
    provider_input = _composed_player_input(pending, line)
    if follow_up:
        # A code phase never stores the line it is answering.
        provider_input = "\n".join(part for part in (provider_input, "Player follow-up: %s" % line) if part)
    kwargs = {"spell_references": reply.get("spell_references"),
              "correction": {"openRollReply": open_reply}}
    voice_actors = (reply.get("voice_intents") or {}).get("actors", {})
    if voice_actors:
        kwargs["npc_voice_intents"] = voice_actors
    try:
        _require_current_invocation(reply.get("invocation_claim"))
        batch = reply["intent_provider"](encounter, reply.get("characters"), pending, provider_input, **kwargs)
        _require_current_invocation(reply.get("invocation_claim"))
    except (InvocationSupersededError, ReadOnlySaveStop, LiveProviderSuperseded, LiveProviderCompletedError):
        raise
    except Exception as exc:
        _LOGGER.warning("Open-roll reply failed; the stored request is shown again: %s", type(exc).__name__)
        _phase_diagnostic(encounter, pending, "T096", "open_roll_reply_failed", error_code=exc.__class__.__name__)
        return None
    text = None
    ignored = 0
    for intent in (batch.get("intents") if isinstance(batch, dict) else None) or []:
        if (isinstance(intent, dict) and intent.get("dropRoll") is True
                and _is_human_controlled(encounter, combatant_by_id(encounter, intent.get("actorId")))):
            if allow_drop:
                _phase_diagnostic(encounter, pending, "T096", "open_roll_dropped")
                return _DROP_ROLL
            # A contract defect: dropRoll without dropAllowed (the off-hand
            # dice, D-1118-9 D; a DM-requested roll). The
            # roll stays open and the stored request is shown again: a reply
            # written as a drop never reaches the player.
            _phase_diagnostic(encounter, pending, "T096", "open_roll_drop_ignored")
            return None
        ask = intent.get("requiresPlayerInput") if isinstance(intent, dict) else None
        if (text is None and isinstance(ask, dict) and ask.get("kind") == "roll"
                and isinstance(ask.get("prompt"), str) and ask["prompt"].strip()
                and _is_human_controlled(encounter, combatant_by_id(encounter, intent.get("actorId")))):
            text = ask["prompt"].strip()
        else:
            ignored += 1
    if ignored:
        _phase_diagnostic(encounter, pending, "T096", "open_roll_reply_intent_ignored", intents=ignored)
    if text is None:
        _LOGGER.warning("Open-roll reply carried no prompt; the stored request is shown again")
        _phase_diagnostic(encounter, pending, "T096", "open_roll_reply_failed", error_code="missing_prompt")
    return text


def _advance_weapon_attack(encounter_path, encounter, characters, pending, text, voice_intents, reply=None):
    """Take the player's answer for the open code phase. Returns (pending, ask):
    ask is the record of the phase now open (its lead, card and cardId), None
    when the swing is ready to score; pending is None when the line goes back
    to the model as a new plan (C1: a declined roll, or no reader).

    The fast path (a blank line, the D-KW-1 line, the dice tray sentence, bare
    numbers) calls no model; any other line is read by T126 (#1118). Numbers
    that do not fit, and any line that is not an answer, keep the phase open
    and get the DM's words-only reply (item 2), so the window is never re-ruled
    (F4)."""
    from core.ai.roll_answer import read_roll_answer, request_payload
    from core.managers.checks_runtime import _show_check_receipt, new_message_id

    record = deepcopy(pending["weaponAttack"])
    # K1 (P-3): a row changed since the phase opened closes it like a row that is gone.
    entry = weapon_attack_sheet_entry(encounter, characters, record, check_open=True)
    off_hand = record.get("bonusAttack") is True
    if entry is None:
        write_weapon_attack(encounter_path, pending.get("turnId"), None, timeout_seconds=None)
        return None, None
    _rebuild_ask(record, entry)
    request = _phase_request(record, entry)
    values = _parse_weapon_roll(text, record, entry)
    reader_unavailable = False
    kind = None
    if values is None and isinstance(text, str):
        answer = read_roll_answer(request_payload(request["label"], request["phase"], request["dice"],
                                                  request["eachDie"], record.get("prompt"), text))
        kind = answer.get("kind")
        if answer.get("readerUnavailable"):
            reader_unavailable = True
            _phase_diagnostic(encounter, pending, "T126", answer["readerUnavailable"])
        if kind == "let_game_roll":
            values = []
        elif kind == "faces":
            faces = answer.get("values") or []
            values = _fitting_values(faces[0], record, entry) if len(faces) == 1 else "invalid"
        elif off_hand:
            # R3, D-1118-9 D: the off-hand dice stay open on any other line.
            values = "other"
        elif kind == "decline" or reader_unavailable:
            # C1: the line is a new plan, or could not be read: it goes back to
            # T096 to rule, so a failing reader never walls the player at the
            # roll (D-1118-7 A as clarified under D-KW-16, D-1118-9 D).
            values = None
        else:
            values = "other"
    if values is None and off_hand:
        raise _phase_paused("Code-issued off-hand roll is waiting for the player", record)
    if values is None:
        write_weapon_attack(encounter_path, pending.get("turnId"), None, timeout_seconds=None,
                            withdraw=kind == "decline")
        return None, None
    if values in ("invalid", "other"):
        lead = _open_roll_reply(
            encounter, pending, text or "", request, reply, follow_up=True,
            unfitting=values == "invalid", reader_unavailable=reader_unavailable,
            main_swing=_main_swing_facts(record),
            allow_drop=not off_hand,
        )
        if lead is _DROP_ROLL:
            # The DM's typed dropRoll: as a T126 decline, the line goes back
            # to T096 as a new plan and nothing is scored; the drop reply's
            # own words are never shown, only the new plan's turn speaks.
            write_weapon_attack(encounter_path, pending.get("turnId"), None, timeout_seconds=None,
                                withdraw=True)
            return None, None
        if lead is None:
            # The stored request again; a card with no lead beside it is its
            # own new record each time, so every line gets a visible answer.
            raise CombatTurnPaused(
                "Code-issued roll is waiting for the player",
                player_message=record.get("lead") or None, card=record.get("card"),
                card_id=record.get("cardId") if record.get("lead") else None,
            )
        record["lead"] = lead
        record["prompt"] = _join_ask(lead, record["card"])
        record.setdefault("cardId", new_message_id())
        write_weapon_attack(
            encounter_path, pending.get("turnId"), record,
            player_message=record["prompt"], requested_die=record.get("dice"),
            npc_voice_intents=voice_intents, requested_phase=record.get("phase"),
            timeout_seconds=None,
        )
        raise _phase_paused("Code-issued roll is waiting for the player", record)
    phase = record["phase"]
    count, sides = player_weapon_attack_dice(record, entry)
    rolled = None
    game_card = None
    if values:
        source = "player"
    else:
        die = 20 if phase == "attack" else sides
        values = _roll_terms([(count, die)])[0]
        source, rolled = "game", [list(values)]
        game_card = "Game roll for your %s %s: %s on %dd%d." % (
            _phase_weapon(record, entry), phase, " and ".join(str(value) for value in values), count, die)
    if phase == "attack":
        record["faces"][phase] = values
    else:
        # #879: the total stays an int (spell and older readers); the faces are
        # kept beside it whenever they are known (tray, game roll, each die).
        record["faces"][phase] = sum(values)
        if len(values) == count:
            record["faces"]["damageFaces"] = list(values)
    record["sources"][phase] = source
    is_open = False
    if phase == "attack":
        hit, critical, kept, total, ac = player_weapon_attack_score(encounter, characters, record, entry)
        record.update({"hit": hit, "critical": critical, "attackKept": kept,
                       "attackTotal": total, "targetAC": ac})
        # #1350: a flat row has no damage die; its hit is ready for the engine.
        if hit and not is_flat_attack(entry):
            record["phase"] = "damage"
            if not isinstance(record.get("spell"), dict):
                record["greatWeapon"] = player_great_weapon(encounter, characters, record, entry)
            _weapon_attack_prompt(record, entry)
            is_open = True
    if not is_open:
        record["ready"] = True
        for key in ("prompt", "dice", "lead", "card", "cardId"):
            record.pop(key, None)
    # The player's own words are the answer; a game roll is typed beside them.
    pending = write_weapon_attack(
        encounter_path, pending.get("turnId"), record,
        player_message=record["prompt"] if is_open else None,
        requested_die=record["dice"] if is_open else None,
        answer=(text or "").strip(), rolled_faces=rolled,
        npc_voice_intents=voice_intents,
        requested_phase=record.get("phase") if is_open else None,
        timeout_seconds=None,
    )
    if game_card is not None:
        _show_check_receipt(game_card)
    return pending, (record if is_open else None)


def _defend_batch(encounter, pending):
    revision = (encounter.get("combatState") or {}).get("revision")
    return {
        "stateVersion": revision,
        "intents": [
            {
                "actorId": actor_id,
                "mode": "known",
                "action": "defend",
                "description": "The combatant takes a defensive stance.",
            }
            for actor_id in pending.get("actorIds", [])
        ],
    }


def _deterministic_narration(events):
    """Return a truthful last-resort narration from already-committed events."""
    descriptions = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        description = (event.get("intent") or {}).get("description")
        if not description:
            description = (event.get("outcome") or {}).get("description")
        if isinstance(description, str) and description.strip():
            descriptions.append(description.strip())
    if descriptions:
        return " ".join(descriptions)
    return "The committed combat actions resolve, and the battle continues."


def _deliver_committed_turn(
    encounter_path,
    encounter,
    events,
    narrator,
    fallback_player_input,
    deterministic_narration=None,
    narration_diagnostics=None,
    characters=None,
    max_narration_attempts=3,
    invocation_claim=None,
):
    """Generate, validate, persist, and return a pending narration receipt."""
    from core.combat.invocation import InvocationSupersededError
    from core.ai.combat_narration import (
        build_scene_dossier,
        party_scene_time,
        progressive_narration_feedback,
    )

    state = ensure_combat_state(encounter)
    delivery = state.get("pendingDelivery")
    if not valid_pending_delivery(delivery):
        raise CombatTurnPaused("Committed combat events have no delivery receipt")
    history_input = str(
        delivery.get("historyInput") or fallback_player_input or ""
    )
    narration = delivery.get("narration")
    used_fallback = delivery.get("narrationFallback")
    if not isinstance(narration, str) or not narration.strip():
        dossier = build_scene_dossier(
            encounter, events, characters, scene_time=party_scene_time()
        )
        voice_envelope = normalize_npc_voice_intents(
            delivery.get("npcVoiceIntents")
        )
        if voice_envelope is not None:
            dossier["npcVoiceIntents"] = voice_envelope["actors"]
        elif delivery.get("npcVoiceIntents") is not None:
            _LOGGER.warning(
                "Committed combat voice advisory was invalid and was omitted"
            )
            record_combat_diagnostic(
                record_type="window_outcome",
                callsite="T097",
                outcome="voice_advisory_invalid",
                encounter_id=encounter.get("encounterId"),
                turn_id=delivery.get("turnId"),
                revision=state.get("revision"),
                round_number=state.get("round"),
                actor_count=len(events or []),
            )
        attempts = list(delivery.get("narrationAttempts") or [])
        max_attempts = max(3, min(int(max_narration_attempts or 3), 12))
        if deterministic_narration:
            narration = deterministic_narration
            used_fallback = True
        else:
            def _is_completed_invalid_attempt(attempt):
                if not isinstance(attempt, dict):
                    return False
                status = attempt.get("status")
                violations = set(attempt.get("violations") or [])
                if status == "rejected":
                    return True
                if status == "parse_error":
                    return "response_parse_error" in violations
                if status == "contract_error":
                    return bool(
                        violations.intersection(
                            {
                                "response_contract_error",
                                "narration_coverage_error",
                            }
                        )
                    )
                return False

            completed_attempts = [
                attempt
                for attempt in attempts
                if _is_completed_invalid_attempt(attempt)
            ]
            request_number = 0
            while (
                (not isinstance(narration, str) or not narration.strip())
                and len(completed_attempts) < max_attempts
            ):
                request_number += 1
                model_attempt = len(completed_attempts) + 1
                record_attempt = len(attempts) + 1
                if request_number > 1 or model_attempt > 1:
                    _set_combat_retry_status()
                correction = (
                    progressive_narration_feedback(completed_attempts[-1], dossier)
                    if completed_attempts
                    else None
                )
                if isinstance(narration_diagnostics, dict):
                    narration_diagnostics.clear()
                disposition = "completed_invalid"
                try:
                    _require_current_invocation(invocation_claim)
                    narrated = narrator(
                        encounter,
                        events,
                        history_input,
                        scene_dossier=dossier,
                        correction=correction,
                        attempt=model_attempt,
                    )
                    _require_current_invocation(invocation_claim)
                    if isinstance(narrated, tuple):
                        candidate, narrator_fallback = narrated
                    else:
                        candidate, narrator_fallback = narrated, False
                    candidate = str(candidate or "").strip()
                    if narrator_fallback or not candidate:
                        attempt_status = "contract_error"
                        failure_class = "response_contract_error"
                        error_code = "EmptyNarrationCandidate"
                        lint = {
                            "reject": [failure_class],
                            "warnings": [],
                        }
                    else:
                        narration = candidate
                        used_fallback = False
                        record_combat_diagnostic(
                            record_type="call_attempt",
                            callsite="T097",
                            outcome=(
                                "narration_success"
                                if model_attempt == 1
                                else "narration_corrected"
                            ),
                            provider=(narration_diagnostics or {}).get("provider"),
                            model=(narration_diagnostics or {}).get("model"),
                            encounter_id=encounter.get("encounterId"),
                            turn_id=delivery.get("turnId"),
                            revision=(encounter.get("combatState") or {}).get("revision"),
                            round_number=(encounter.get("combatState") or {}).get("round"),
                            window_kind=_window_kind(
                                encounter,
                                [
                                    event.get("actorId")
                                    for event in events
                                    if isinstance(event, dict)
                                ],
                            ),
                            actor_count=len(events or []),
                            attempt=model_attempt,
                            correction=model_attempt > 1,
                            elapsed_ms=(narration_diagnostics or {}).get("elapsed_ms"),
                            committed_events=len(events or []),
                        )
                        break
                except (InvocationSupersededError, ReadOnlySaveStop, LiveProviderCompletedError):
                    # A completed refusal ends the fight window; the delivery
                    # stays pending and is narrated on resume (#1087).
                    raise
                except Exception as exc:
                    candidate = str(getattr(exc, "candidate", "") or "")
                    failure_class = str(
                        getattr(exc, "failure_class", "unexpected_internal_error")
                    )
                    if failure_class == "provider_error":
                        disposition = "provider_retry"
                    elif failure_class == "response_parse_error":
                        attempt_status = "parse_error"
                    elif failure_class in {
                        "response_contract_error",
                        "narration_coverage_error",
                    }:
                        attempt_status = "contract_error"
                    else:
                        disposition = "internal_retry"
                    error_code = exc.__class__.__name__
                    lint = {
                        "reject": [failure_class],
                        "warnings": [],
                    }
                if disposition != "completed_invalid":
                    record_combat_diagnostic(
                        record_type="call_attempt",
                        callsite="T097",
                        outcome=failure_class,
                        provider=(narration_diagnostics or {}).get("provider"),
                        model=(narration_diagnostics or {}).get("model"),
                        encounter_id=encounter.get("encounterId"),
                        turn_id=delivery.get("turnId"),
                        revision=(encounter.get("combatState") or {}).get("revision"),
                        round_number=(encounter.get("combatState") or {}).get("round"),
                        window_kind=_window_kind(
                            encounter,
                            [
                                event.get("actorId")
                                for event in events
                                if isinstance(event, dict)
                            ],
                        ),
                        actor_count=len(events or []),
                        attempt=model_attempt,
                        correction=model_attempt > 1,
                        elapsed_ms=(narration_diagnostics or {}).get("elapsed_ms"),
                        failure_class=failure_class,
                        error_code=error_code,
                        committed_events=len(events or []),
                        violation_codes=lint["reject"],
                    )
                    continue
                _require_current_invocation(invocation_claim)
                try:
                    encounter = record_narration_attempt(
                        encounter_path,
                        delivery["deliveryId"],
                        record_attempt,
                        attempt_status,
                        candidate=candidate,
                        violations=lint["reject"],
                        warnings=lint["warnings"],
                        invocation_claim=invocation_claim,
                    )
                except CombatPreconditionChanged:
                    # Preserve the invocation-owner terminal when a destructive
                    # request wins the race into the transaction authority.
                    _require_current_invocation(invocation_claim)
                    raise
                delivery = (encounter.get("combatState") or {}).get(
                    "pendingDelivery"
                ) or delivery
                attempts = list(delivery.get("narrationAttempts") or [])
                completed_attempts = [
                    attempt
                    for attempt in attempts
                    if _is_completed_invalid_attempt(attempt)
                ]
                record_combat_diagnostic(
                    record_type="call_attempt",
                    callsite="T097",
                    outcome=failure_class,
                    provider=(narration_diagnostics or {}).get("provider"),
                    model=(narration_diagnostics or {}).get("model"),
                    encounter_id=encounter.get("encounterId"),
                    turn_id=delivery.get("turnId"),
                    revision=(encounter.get("combatState") or {}).get("revision"),
                    round_number=(encounter.get("combatState") or {}).get("round"),
                    window_kind=_window_kind(
                        encounter,
                        [
                            event.get("actorId")
                            for event in events
                            if isinstance(event, dict)
                        ],
                    ),
                    actor_count=len(events or []),
                    attempt=model_attempt,
                    correction=model_attempt > 1,
                    elapsed_ms=(narration_diagnostics or {}).get("elapsed_ms"),
                    failure_class=failure_class,
                    error_code=error_code,
                    committed_events=len(events or []),
                    violation_codes=lint["reject"],
                )
            if not isinstance(narration, str) or not narration.strip():
                narration = "The committed combat result is safely recorded."
                used_fallback = True
                record_combat_diagnostic(
                    record_type="window_outcome",
                    callsite="T097",
                    outcome="narration_fallback",
                    encounter_id=encounter.get("encounterId"),
                    turn_id=delivery.get("turnId"),
                    revision=(encounter.get("combatState") or {}).get("revision"),
                    round_number=(encounter.get("combatState") or {}).get("round"),
                    window_kind=_window_kind(
                        encounter,
                        [
                            event.get("actorId")
                            for event in events
                            if isinstance(event, dict)
                        ],
                    ),
                    actor_count=len(events or []),
                    committed_events=len(events or []),
                    deterministic_fallback=True,
                )
        _require_current_invocation(invocation_claim)
        try:
            encounter = record_delivery_narration(
                encounter_path,
                delivery["deliveryId"],
                narration,
                used_fallback,
                invocation_claim=invocation_claim,
            )
        except CombatPreconditionChanged:
            # A true transaction conflict remains a transaction fault. A
            # superseded claim must reach the invocation owner unchanged.
            _require_current_invocation(invocation_claim)
            raise
        delivery = (encounter.get("combatState") or {}).get("pendingDelivery") or delivery
    return {
        "encounter": encounter,
        "events": deepcopy(events),
        "narration": str(delivery.get("narration") or narration),
        "narrationFallback": bool(delivery.get("narrationFallback")),
        "deliveryId": delivery.get("deliveryId"),
        "historyInput": history_input,
        "displayPrefix": str(delivery.get("displayPrefix") or ""),
    }


def execute_agentic_turn(
    encounter_path,
    actor_ids,
    character_paths,
    context_sheets,
    player_input,
    spell_references=None,
    delivery_context=None,
    max_intent_attempts=3,
    max_narration_attempts=3,
    intent_provider=None,
    narrator=None,
    npc_voice_intents=None,
    invocation_claim=None,
    weapon_roll_text=None,
):
    """Choose, resolve, commit, then narrate one persisted actor window.

    The call is restart-safe. A staged turn is replayed without any provider;
    an un-staged claim regenerates intents against the same revision. Provider
    rejected/provider-failed results visibly continue the same logical turn;
    they never consume the player's turn or invent an NPC fallback action.
    """
    immutable_voice_intents = _immutable_voice_intents(npc_voice_intents)
    from core.combat.invocation import InvocationSupersededError
    narrator_is_default = narrator is None
    narration_diagnostics = {} if narrator_is_default else None
    intent_provider_name = "custom"
    intent_model_name = "custom"
    if intent_provider is None or narrator is None:
        from core.ai.combat_agent import (
            combat_role_identity,
            request_narration_candidate,
            request_intent_batch,
        )
        if intent_provider is None:
            intent_provider = request_intent_batch
            try:
                intent_provider_name, intent_model_name = combat_role_identity("intent")
            except Exception:
                intent_provider_name, intent_model_name = "unknown", "unknown"
        if narrator is None:
            default_narrator = request_narration_candidate

            def _diagnostic_narrator(
                encounter_value,
                events_value,
                input_value,
                scene_dossier=None,
                correction=None,
                attempt=1,
            ):
                return default_narrator(
                    encounter_value,
                    events_value,
                    input_value,
                    scene_dossier,
                    correction=correction,
                    attempt=attempt,
                    diagnostics=narration_diagnostics,
                )

            narrator = _diagnostic_narrator
    if not narrator_is_default:
        custom_narrator = narrator

        def _compatible_custom_narrator(
            encounter_value,
            events_value,
            input_value,
            scene_dossier=None,
            correction=None,
            attempt=1,
        ):
            return custom_narrator(encounter_value, events_value, input_value)

        narrator = _compatible_custom_narrator

    # Reject the wrong pipeline before recovery inspection can become a turn
    # claim. This keeps the public coordinator safe even when called outside
    # combat_manager's persisted-mode guard.
    encounter = safe_json_load(encounter_path)
    if not isinstance(encounter, dict):
        raise CombatTurnPaused("Could not load the combat encounter")
    ensure_combat_state(encounter)
    if (encounter.get("combatState") or {}).get("pipelineMode") != "agentic":
        raise CombatTurnPaused("Cannot run the agentic pipeline on a legacy combat encounter")

    combat_now_scalar = None
    try:
        from core.effects.clock import scalar_from_calendar
        from core.managers.effects_state import campaign_effects_migrated

        if campaign_effects_migrated():
            party = safe_json_load("party_tracker.json") or {}
            combat_now_scalar = scalar_from_calendar(
                party.get("worldConditions") or {}
            )
            enter_effect_clock(
                encounter_path,
                character_paths,
                combat_now_scalar,
            )
            encounter = safe_json_load(encounter_path)
    except Exception as exc:
        raise CombatTurnPaused(
            "Could not establish the recoverable combat effect clock: %s" % exc
        ) from exc

    recovery = inspect_recovery(encounter_path)
    if recovery["action"] == "pause_invalid_delivery":
        raise CombatTurnPaused(
            "Combat recovery is paused because the committed narration "
            "receipt is invalid. Restore a known-good save before continuing."
        )
    if recovery["action"] == "pause_untimed_incapacitation":
        raise CombatTurnPaused(
            "Combat remains paused because every living combatant is "
            "incapacitated and no timed effect can advance. Restore or load "
            "a save before continuing."
        )
    if recovery["action"] == "pause_recovery_conflict":
        raise CombatTurnPaused(
            str(
                (recovery.get("recoveryConflict") or {}).get("playerMessage")
                or "Combat recovery needs attention -- Load or Reset"
            )
        )
    if recovery["action"] == "deliver_committed_events":
        delivery = recovery["pendingDelivery"]
        events = deepcopy(delivery.get("events") or [])
        recovered_characters = _load_characters(character_paths, context_sheets)
        delivered = _deliver_committed_turn(
            encounter_path,
            encounter,
            events,
            narrator,
            player_input,
            narration_diagnostics=narration_diagnostics,
            characters=recovered_characters,
            max_narration_attempts=max_narration_attempts,
            invocation_claim=invocation_claim,
        )
        delivered.update(
            {
                "characters": recovered_characters,
                "recovered": True,
                "recoveredDelivery": True,
            }
        )
        return delivered
    if recovery["action"] == "apply_staged_events":
        pending = recovery["pendingTurn"]
        persisted_events = deepcopy(pending.get("events", []))
        committed, characters = apply_staged_turn(
            encounter_path,
            character_paths,
            pending.get("turnId"),
            invocation_claim=invocation_claim,
        )
        delivered = _deliver_committed_turn(
            encounter_path,
            committed,
            persisted_events,
            narrator,
            player_input,
            narration_diagnostics=narration_diagnostics,
            characters=characters,
            max_narration_attempts=max_narration_attempts,
            invocation_claim=invocation_claim,
        )
        delivered.update({
            "characters": characters,
            "recovered": True,
            "recoveredDelivery": False,
        })
        return delivered

    if recovery["action"] == "regenerate_intent":
        pending = recovery["pendingTurn"]
        encounter = safe_json_load(encounter_path)
        if not isinstance(encounter, dict):
            raise CombatTurnPaused("Could not reload the pending encounter")
        if actor_ids and list(actor_ids) != pending.get("actorIds"):
            raise CombatTurnPaused("Requested actors do not match the pending turn")
        weapon_answered = False
        open_attack = pending.get("weaponAttack")
        if isinstance(open_attack, dict) and open_attack.get("ready") is not True:
            # Item 3, #1118: the answer to a code-issued roll phase. The fast
            # path takes a blank line, the D-KW-1 line and bare numbers; any
            # other line is read by T126 (_advance_weapon_attack).
            phase_characters = _load_characters(character_paths, context_sheets)
            advanced, ask = _advance_weapon_attack(
                encounter_path,
                encounter,
                phase_characters,
                pending,
                weapon_roll_text if weapon_roll_text is not None else player_input,
                None,
                reply={"intent_provider": intent_provider, "characters": phase_characters,
                       "spell_references": spell_references, "invocation_claim": invocation_claim,
                       "voice_intents": immutable_voice_intents},
            )
            if ask is not None:
                raise _phase_paused("Code-issued weapon roll is waiting for the player", ask)
            weapon_answered = advanced is not None
            encounter = safe_json_load(encounter_path)
            pending = deepcopy((encounter.get("combatState") or {}).get("pendingTurn"))
        if not weapon_answered and not _all_non_player(encounter, pending.get("actorIds", [])):
            game_roll = _game_roll_answer(pending, player_input)
            if isinstance(game_roll, list):
                # #877: the open typed request decides that this line
                # answers it; the game rolls its full dice.
                if mark_pending_game_roll(encounter_path, pending.get("turnId"), player_input, game_roll):
                    asked = live_exchanges(pending)[-1]
                    _show_game_roll(asked, game_roll)
            elif game_roll is None:
                append_pending_player_input(
                    encounter_path,
                    pending.get("turnId"),
                    player_input,
                    timeout_seconds=None,
                )
            encounter = safe_json_load(encounter_path)
            pending = deepcopy((encounter.get("combatState") or {}).get("pendingTurn"))
        persisted_voice_intents = normalize_npc_voice_intents(
            pending.get("npcVoiceIntents") if isinstance(pending, dict) else None
        )
        immutable_voice_intents = _immutable_voice_intents(
            persisted_voice_intents
        )
    else:
        initial_player_input = (
            None if _all_non_player(encounter, actor_ids) else player_input
        )
        encounter, pending = claim_turn(
            encounter_path,
            actor_ids,
            player_input=initial_player_input,
            invocation_claim=invocation_claim,
        )

    characters = _load_characters(character_paths, context_sheets)
    persisted_context = (
        delivery_context if isinstance(delivery_context, dict) else {}
    )
    persisted_context.setdefault("historyInput", player_input)
    if pending.get("clockOnly") is True:
        try:
            events, _preview_encounter, _preview_characters = (
                resolve_effect_clock_window(encounter, characters, pending)
            )
        except CombatIntentError as exc:
            raise CombatTurnPaused(str(exc)) from exc
        stage_events(
            encounter_path,
            pending["turnId"],
            events,
            delivery_context=persisted_context,
            character_paths=character_paths,
            character_preconditions=characters,
            character_postconditions=_preview_characters,
            invocation_claim=invocation_claim,
        )
        committed, committed_characters = apply_staged_turn(
            encounter_path,
            character_paths,
            pending["turnId"],
            invocation_claim=invocation_claim,
        )
        delivered = _deliver_committed_turn(
            encounter_path,
            committed,
            events,
            narrator,
            player_input,
            deterministic_narration=(
                "Every combatant is momentarily unable to act. Ongoing "
                "effects run their course as the next round begins."
            ),
            narration_diagnostics=narration_diagnostics,
            characters=committed_characters,
            max_narration_attempts=max_narration_attempts,
            invocation_claim=invocation_claim,
        )
        delivered.update({
            "characters": committed_characters,
            "recovered": False,
            "recoveredDelivery": False,
        })
        return delivered
    provider_characters = characters
    try:
        from core.effects.effective import effective_sheet
        from core.managers.effects_state import campaign_effects_migrated

        if campaign_effects_migrated():
            provider_characters = {
                name: effective_sheet(sheet)
                if isinstance(sheet, dict) and name in (character_paths or {})
                else deepcopy(sheet)
                for name, sheet in characters.items()
            }
    except Exception:
        provider_characters = characters
    events = None
    roll_consumption = None
    _preview_characters = None
    ready_attack = pending.get("weaponAttack")
    if isinstance(ready_attack, dict) and ready_attack.get("ready") is True:
        # Item 3: the swing's dice are in; resolve the window with the batch
        # the model gave when the roll phase opened (no second T096 pass).
        pending, events, roll_consumption, _preview_characters = _resolve_ready_phase(
            encounter_path, encounter, characters, pending,
        )
    provider_player_input = _composed_player_input(pending, player_input)
    if events is None and not _all_non_player(encounter, pending.get("actorIds", [])):
        try:
            from core.ai.combat_agent import build_contextual_spell_payload

            spell_references = build_contextual_spell_payload(
                provider_characters,
                actor_names=_pending_actor_names(encounter, pending),
                encounter_context=(spell_references or {}).get("encounterContext"),
            )
        except Exception:
            # The deterministic enrichment is optional. The durable action
            # chain itself still prevents clarification context loss.
            pass
    correction = None
    rules_drift_seen = False
    player_charge_refusal = None
    player_resource_refusal = None
    feature_heal_limits = None
    feature_heal_player = False
    removal_refused_actors = set()
    asked_dc_corrected = set()
    window_kind = _window_kind(encounter, pending.get("actorIds", []))
    capability_count, rule_count = _diagnostic_context_counts(spell_references)
    attempt_number = 0
    game_roll_rerule = False
    while events is None:
        if game_roll_rerule:
            # #1118: T096 rules again with the game's roll; that pass is not
            # a failed attempt and shows no "checking the ruling" status.
            game_roll_rerule = False
        else:
            attempt_number += 1
            if attempt_number > 1:
                _set_combat_retry_status()
        started = time.monotonic()
        batch = None
        try:
            _require_current_invocation(invocation_claim)
            intent_kwargs = {
                "spell_references": spell_references,
                "correction": correction,
            }
            # T105: pass the immutable NPC-voice advisory map (built once at the
            # coordinator boundary) unchanged on every intent attempt/correction.
            voice_actors = immutable_voice_intents.get("actors", {})
            if voice_actors:
                intent_kwargs["npc_voice_intents"] = voice_actors
            # K1 (P-2): the saved rows behind the lists this request sends (the
            # sent sheets may be their effective views, same positions), kept
            # for the reply's value check.
            sent_rows = sent_row_lists(encounter, characters)
            batch = intent_provider(
                encounter,
                provider_characters,
                pending,
                provider_player_input,
                **intent_kwargs,
            )
            _require_current_invocation(invocation_claim)
            batch = _apply_trusted_spell_durations(
                batch,
                spell_references,
                now_scalar=combat_now_scalar,
            )
            batch = _reconcile_validated_prefix(batch, correction)
        except (InvocationSupersededError, ReadOnlySaveStop, LiveProviderCompletedError):
            # A completed refusal cannot heal by re-sending: it ends the fight
            # window and the pending turn is kept for resume (#1087).
            raise
        except Exception as exc:
            # Keep the same persisted logical operation alive. Provider/network
            # failure is correction input, never authority to invent an NPC
            # action or refuse the player's action after an arbitrary count.
            correction = {
                "error": "Combat intent provider was unavailable: %s" % exc,
                "instruction": "Retry the same full ordered intent batch.",
            }
            failure_class = _provider_failure_class(exc)
            record_combat_diagnostic(
                record_type="call_attempt",
                callsite="T096",
                outcome=failure_class,
                provider=intent_provider_name,
                model=intent_model_name,
                encounter_id=encounter.get("encounterId"),
                turn_id=pending.get("turnId"),
                revision=(encounter.get("combatState") or {}).get("revision"),
                round_number=(encounter.get("combatState") or {}).get("round"),
                window_kind=window_kind,
                actor_count=len(pending.get("actorIds") or []),
                attempt=attempt_number,
                correction=attempt_number > 1,
                elapsed_ms=(time.monotonic() - started) * 1000,
                failure_class=failure_class,
                error_code=exc.__class__.__name__,
                capability_candidates=capability_count,
                rule_references=rule_count,
            )
            continue

        if player_resource_refusal and not any(
            isinstance(intent, dict)
            and _is_human_controlled(encounter, combatant_by_id(encounter, intent.get("actorId")))
            and isinstance(intent.get("requiresPlayerInput"), dict)
            and intent["requiresPlayerInput"].get("kind") == "choice"
            for intent in ((batch.get("intents") if isinstance(batch, dict) else None) or [])
        ):
            # #671 (D-671-1 A): the re-rule after the player's refused spend did
            # not ask the player; code asks, before any takeover, roll request
            # or resolution.
            _pause_for_refused_resource(encounter_path, pending, player_resource_refusal,
                                        immutable_voice_intents)

        try:
            # #1447: a sheetless observer the batch targets gets its sheet
            # (one build per fight) before any check or resolution reads it.
            encounter, built = _ensure_targeted_sheets(
                encounter_path, encounter, batch, characters, character_paths,
                pending, invocation_claim,
            )
            for name in built:
                provider_characters[name] = deepcopy(characters[name])
            # K1 (2.1): a replied row position must still hold the row that was sent.
            _check_sent_rows(batch, sent_rows, encounter, characters)
            # #942: pass 2 spends the slot the answered roll was asked at.
            _check_asked_slot_level(encounter, pending, batch)
            # R1: a retry answering a damage roll's playerRoll correction keeps
            # the stated hit (before the faces check, which re-carries it).
            _keep_stated_hit(batch, correction)
            # 3b: the answered roll's typed faces fit the typed request.
            if _check_answered_roll_faces(
                encounter_path, encounter, pending, batch, immutable_voice_intents,
                reply={"intent_provider": intent_provider, "characters": provider_characters,
                       "spell_references": spell_references, "invocation_claim": invocation_claim,
                       "voice_intents": immutable_voice_intents},
            ) == _GAME_ROLL_RERULE:
                record_combat_diagnostic(
                    record_type="window_outcome",
                    callsite="T096",
                    outcome="game_roll_rerule",
                    provider=intent_provider_name,
                    model=intent_model_name,
                    encounter_id=encounter.get("encounterId"),
                    turn_id=pending.get("turnId"),
                    revision=(encounter.get("combatState") or {}).get("revision"),
                    round_number=(encounter.get("combatState") or {}).get("round"),
                    window_kind=window_kind,
                    actor_count=len(pending.get("actorIds") or []),
                    attempt=attempt_number,
                )
                encounter = safe_json_load(encounter_path)
                if not isinstance(encounter, dict):
                    raise CombatTurnPaused("Could not reload the pending encounter")
                pending = deepcopy((encounter.get("combatState") or {}).get("pendingTurn"))
                provider_player_input = _composed_player_input(pending, player_input)
                correction = None
                game_roll_rerule = True
                continue
            # Item 10 (r2): the answered save keeps the DC it was asked at.
            _check_asked_save_dc(batch, asked_dc_corrected)
            # R2: a bonusAction outside the actor's bonusActionNames is
            # corrected before any roll is asked.
            _validate_bonus_actions(batch, encounter, characters)
            # R3 (F3): a second weapon's swing is the Off-hand Attack, not attacks 2.
            _validate_attack_count(batch, encounter, characters)
            takeover = _player_weapon_takeover(encounter, characters, pending, batch)
            if takeover is not None:
                # Item 3: the player's plain melee swing. Code asks for the
                # d20 now; the dice, not another model pass, finish the window.
                record, _entry = takeover
                written = write_weapon_attack(
                    encounter_path,
                    pending.get("turnId"),
                    record,
                    player_message=record.get("prompt"),
                    requested_die=record.get("dice"),
                    npc_voice_intents=immutable_voice_intents,
                    requested_phase=record.get("phase"),
                    timeout_seconds=None,
                )
                record_combat_diagnostic(
                    record_type="call_attempt",
                    callsite="T096",
                    outcome=(
                        "spell_save_no_damage" if record.get("ready") is True
                        else "%s_opened" % _phase_kind(record)
                    ),
                    provider=intent_provider_name,
                    model=intent_model_name,
                    encounter_id=encounter.get("encounterId"),
                    turn_id=pending.get("turnId"),
                    revision=(encounter.get("combatState") or {}).get("revision"),
                    round_number=(encounter.get("combatState") or {}).get("round"),
                    window_kind=window_kind,
                    actor_count=len(pending.get("actorIds") or []),
                    attempt=attempt_number,
                    correction=attempt_number > 1,
                    elapsed_ms=(time.monotonic() - started) * 1000,
                    capability_candidates=capability_count,
                    rule_references=rule_count,
                    intents=len(batch.get("intents") or []) if isinstance(batch, dict) else None,
                )
                if record.get("ready") is not True:
                    raise _phase_paused("Code-issued weapon roll is waiting for the player", record)
                # #723: every target saved against a spell that does nothing
                # on a save, so no roll is asked: the window resolves now. A
                # fallback sends this batch down today's path below.
                pending, events, roll_consumption, _preview_characters = _resolve_ready_phase(
                    encounter_path, encounter, characters, written,
                )
                if events is not None:
                    continue
            _validate_player_input_request_ownership(batch, encounter)
            if attempt_number < max(2, int(max_intent_attempts or 3)):
                # The last attempt lets a genuine question through rather than
                # leave the player's turn without an answer.
                _validate_player_weapon_question(batch, encounter, characters)
                _validate_flat_damage_request(batch, encounter, characters)
                _validate_feature_names(batch, encounter, characters)
            _validate_roll_request_phase(batch, encounter)
            try:
                roll_audits = _audit_batch_spell_roll_requests(
                    batch,
                    encounter,
                    provider_characters,
                )
            except Exception:
                # The SRD sidecar is a fail-open advisory boundary. Loader,
                # filesystem, or unexpected contract bugs must not enter the
                # model correction budget or prevent an otherwise valid turn.
                roll_audits = [{"status": "rules_contract_unavailable"}]
            for audit in roll_audits:
                audit_status = audit.get("status")
                if audit_status in {
                    "rules_drift_unchecked_ambiguous",
                    "rules_drift_unchecked_no_profile",
                    "rules_contract_unavailable",
                }:
                    record_combat_diagnostic(
                        record_type="window_outcome",
                        callsite="T096",
                        outcome=audit_status,
                        provider=intent_provider_name,
                        model=intent_model_name,
                        encounter_id=encounter.get("encounterId"),
                        turn_id=pending.get("turnId"),
                        revision=(encounter.get("combatState") or {}).get("revision"),
                        round_number=(encounter.get("combatState") or {}).get("round"),
                        window_kind=window_kind,
                        actor_count=len(pending.get("actorIds") or []),
                        rule_references=rule_count,
                        rules_contract_key=audit.get("contractKey"),
                        rules_contract_version=audit.get("version"),
                    )
                elif audit_status == "verified_match" and rules_drift_seen:
                    record_combat_diagnostic(
                        record_type="window_outcome",
                        callsite="T096",
                        outcome="rules_drift_corrected",
                        provider=intent_provider_name,
                        model=intent_model_name,
                        encounter_id=encounter.get("encounterId"),
                        turn_id=pending.get("turnId"),
                        revision=(encounter.get("combatState") or {}).get("revision"),
                        round_number=(encounter.get("combatState") or {}).get("round"),
                        window_kind=window_kind,
                        actor_count=len(pending.get("actorIds") or []),
                        rule_references=rule_count,
                        recovered=True,
                        rules_contract_key=audit.get("contractKey"),
                        rules_contract_version=audit.get("version"),
                    )
            rolls = _fresh_rolls(encounter)
            events, _preview_encounter, _preview_characters = resolve_claimed_window(
                encounter,
                characters,
                pending,
                batch,
                rolls,
                # #669: a correction that still breaks the limit is clamped.
                clamp_feature_heals=feature_heal_limits is not None,
                # #725: an actor whose remove op was refused once has it dropped.
                drop_removals_for=frozenset(removal_refused_actors),
            )
            roll_consumption = rolls.consumption()
            record_combat_diagnostic(
                record_type="call_attempt",
                callsite="T096",
                outcome=(
                    "success_first_attempt"
                    if attempt_number == 1
                    else "success_after_correction"
                ),
                provider=intent_provider_name,
                model=intent_model_name,
                encounter_id=encounter.get("encounterId"),
                turn_id=pending.get("turnId"),
                revision=(encounter.get("combatState") or {}).get("revision"),
                round_number=(encounter.get("combatState") or {}).get("round"),
                window_kind=window_kind,
                actor_count=len(pending.get("actorIds") or []),
                attempt=attempt_number,
                correction=attempt_number > 1,
                elapsed_ms=(time.monotonic() - started) * 1000,
                capability_candidates=capability_count,
                rule_references=rule_count,
                intents=len(batch.get("intents") or []) if isinstance(batch, dict) else None,
            )
            if player_charge_refusal and not _same_item_spent(events, player_charge_refusal):
                # H3b fail-safe: the correction chose an action for the
                # player instead of asking (re-declaring the same item at a
                # cost the engine accepted is the player's own choice).
                # Nothing is staged; the round waits for the player.
                _pause_for_refused_item(encounter_path, pending, player_charge_refusal,
                                        immutable_voice_intents)
            if feature_heal_player and not _same_feature_used(events, feature_heal_limits):
                # #669: the correction chose another action for the player.
                _pause_for_refused_feature_heal(encounter_path, pending, feature_heal_limits,
                                                immutable_voice_intents)
            break
        except CombatBonusAttackRollRequired as signal:
            # R3: the batch resolves up to the player's Off-hand Attack; code
            # asks its dice now and resolves this batch when they are in.
            record = _open_off_hand_phase(
                encounter_path, encounter, characters, pending, batch, signal,
                voice_intents=immutable_voice_intents,
            )
            raise _phase_paused("Code-issued off-hand roll is waiting for the player", record)
        except CombatPlayerInputRequired as exc:
            request = exc.feedback.get("request", {})
            record_combat_diagnostic(
                record_type="call_attempt",
                callsite="T096",
                outcome="player_input_required",
                provider=intent_provider_name,
                model=intent_model_name,
                encounter_id=encounter.get("encounterId"),
                turn_id=pending.get("turnId"),
                revision=(encounter.get("combatState") or {}).get("revision"),
                round_number=(encounter.get("combatState") or {}).get("round"),
                window_kind=window_kind,
                actor_count=len(pending.get("actorIds") or []),
                attempt=attempt_number,
                correction=attempt_number > 1,
                elapsed_ms=(time.monotonic() - started) * 1000,
                capability_candidates=capability_count,
                rule_references=rule_count,
                intents=len(batch.get("intents") or []) if isinstance(batch, dict) else None,
            )
            typed_roll = _typed_roll(request)
            # #1118: the model's own request carries the offer to roll for the player.
            player_message = _request_text(request)
            record_pending_player_request(
                encounter_path,
                pending.get("turnId"),
                player_message,
                requested_die=_authoritative_requested_die(request),
                requested_phase=request.get("phase") if isinstance(request, dict) else None,
                npc_voice_intents=immutable_voice_intents,
                requested_roll=typed_roll,
                requested_slot_level=_asked_slot_level(encounter, batch, exc.actor_id, request),
                requested_dc=_asked_save_dc(request),
            )
            raise CombatTurnPaused(
                "Combat resolution requires more player input",
                player_message=player_message,
            ) from exc
        except (CombatIntentError, IndexError, TypeError, ValueError) as exc:
            refused = (getattr(exc, "feedback", None) or {}).get("playerChargeRefusal") \
                if isinstance(getattr(exc, "feedback", None), dict) else None
            if refused and player_charge_refusal:
                # H3b fail-safe: the correction repeated the refused use.
                _pause_for_refused_item(encounter_path, pending, refused, immutable_voice_intents)
            if refused:
                player_charge_refusal = refused
            resource_refused = (getattr(exc, "feedback", None) or {}).get("playerResourceRefusal") \
                if isinstance(getattr(exc, "feedback", None), dict) else None
            if resource_refused:
                player_resource_refusal = resource_refused
            heal_limits = (getattr(exc, "feedback", None) or {}).get("featureHealLimits") \
                if isinstance(getattr(exc, "feedback", None), dict) else None
            if heal_limits and feature_heal_limits is not None and exc.feedback.get("featureHealPlayer"):
                # #669: the correction repeated a feature use that restores
                # nothing; nothing is staged and the round waits for the player.
                _pause_for_refused_feature_heal(encounter_path, pending, heal_limits,
                                                immutable_voice_intents)
            if heal_limits:
                feature_heal_limits = heal_limits
                feature_heal_player = bool(exc.feedback.get("featureHealPlayer"))
            removal_refusals = (getattr(exc, "feedback", None) or {}).get("removalRefusals") \
                if isinstance(getattr(exc, "feedback", None), dict) else None
            if removal_refusals and isinstance(getattr(exc, "actor_id", None), str):
                # #725 (D-725-1 A): one re-rule per actor per window.
                removal_refused_actors.add(exc.actor_id)
            if ((getattr(exc, "feedback", None) or {}) if isinstance(getattr(exc, "feedback", None), dict)
                    else {}).get("askedSaveDc") is not None and isinstance(getattr(exc, "actor_id", None), str):
                # Item 10: one correction per actor; then the engine scores the asked DC.
                asked_dc_corrected.add(exc.actor_id)
            correction = _intent_correction(exc, batch=batch)
            failure_class = _resolution_failure_class(exc)
            rules_drift = (
                getattr(exc, "feedback", {}).get("rulesDrift")
                if isinstance(getattr(exc, "feedback", None), dict)
                else {}
            ) or {}
            if failure_class == "rules_drift_reject":
                rules_drift_seen = True
            record_combat_diagnostic(
                record_type="call_attempt",
                callsite="T096",
                outcome=failure_class,
                provider=intent_provider_name,
                model=intent_model_name,
                encounter_id=encounter.get("encounterId"),
                turn_id=pending.get("turnId"),
                revision=(encounter.get("combatState") or {}).get("revision"),
                round_number=(encounter.get("combatState") or {}).get("round"),
                window_kind=window_kind,
                actor_count=len(pending.get("actorIds") or []),
                attempt=attempt_number,
                correction=attempt_number > 1,
                elapsed_ms=(time.monotonic() - started) * 1000,
                failure_class=failure_class,
                error_code=exc.__class__.__name__,
                capability_candidates=capability_count,
                rule_references=rule_count,
                intents=len(batch.get("intents") or []) if isinstance(batch, dict) else None,
                rules_contract_key=rules_drift.get("contractKey"),
                rules_contract_version=rules_drift.get("version"),
            )
            try:
                from core.ai.srd_reference import corrective_rule_references

                references = corrective_rule_references(
                    batch,
                    getattr(exc, "actor_id", None),
                    encounter,
                    provider_characters,
                )
                if references:
                    correction["ruleReferences"] = references
                    correction["instruction"] += (
                        " Apply the attached SRD guidance only to the named rule."
                    )
            except Exception:
                # Reference guidance is optional. A loader/matcher problem must
                # never replace the existing safe correction/retry behavior.
                pass

    stage_events(
        encounter_path,
        pending["turnId"],
        events,
        roll_consumption=roll_consumption,
        delivery_context=persisted_context,
        character_paths=character_paths,
        character_preconditions=characters,
        character_postconditions=_preview_characters,
        npc_voice_intents=immutable_voice_intents,
        invocation_claim=invocation_claim,
    )
    committed, committed_characters = apply_staged_turn(
        encounter_path,
        character_paths,
        pending["turnId"],
        invocation_claim=invocation_claim,
    )
    delivered = _deliver_committed_turn(
        encounter_path,
        committed,
        events,
        narrator,
        player_input,
        narration_diagnostics=narration_diagnostics,
        characters=committed_characters,
        max_narration_attempts=max_narration_attempts,
        invocation_claim=invocation_claim,
    )
    delivered.update({
        "characters": committed_characters,
        "recovered": False,
        "recoveredDelivery": False,
    })
    return delivered
