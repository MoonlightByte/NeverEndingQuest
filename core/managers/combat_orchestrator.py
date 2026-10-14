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
from core.combat.pipeline import _intent_for_actor, _ordered_intents
from core.combat.resolver import (
    _action_entries,
    feature_heal_key,
    open_player_spell_attack,
    open_player_spell_save,
    open_player_weapon_attack,
    player_spell_attack_entry,
    player_spell_save_entry,
    player_great_weapon,
    player_weapon_attack_dice,
    player_weapon_attack_entry,
    player_weapon_attack_score,
    spell_attack_violations,
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
    append_pending_game_roll,
    append_pending_player_input,
    apply_staged_turn,
    claim_turn,
    enter_effect_clock,
    inspect_recovery,
    record_delivery_narration,
    record_narration_attempt,
    record_pending_player_request,
    stage_events,
    write_weapon_attack,
)
from utils.encoding_utils import normalize_typography_deep, safe_json_load
from utils.transient_filesystem import ReadOnlySaveStop


_LOGGER = logging.getLogger(__name__)


class CombatTurnPaused(RuntimeError):
    """No mutation occurred; the same durable turn may be retried or resumed."""

    def __init__(self, technical_message, player_message=None):
        super().__init__(technical_message)
        self.player_message = player_message


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
            "with mode 'adjudicated', ability %r, save {type:%r, dc:%s, "
            "halfOnSave:%s}, targets [{combatantId, hpDelta}] (hpDelta 0 when "
            "it only imposes conditions; code rolls its listed damage dice)"
            % (
                save_ability["name"],
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
        instruction += "; or choose a listed known attack instead."
    elif feedback.get("recharging"):
        # MS-b: the ability waits for its recharge die; name the rest.
        rendered = [
            str(action).strip()
            for action in (legal_actions or [])
            if isinstance(action, str) and action.strip()
        ]
        instruction = (
            "Return a corrected full ordered intent batch. For the rejected "
            "actor, %r is recharging (it returns on a d6 at the start of that "
            "actor's turn; the creature's recharge record shows it as spent): "
            "do not declare it this turn. Use another listed action%s or a "
            "defensive action."
            % (feedback.get("recharging"), (" (%s)" % ", ".join(rendered)) if rendered else "")
        )
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
    limits = feedback.get("featureHealLimits")
    if isinstance(limits, list) and limits:
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


def _apply_trusted_spell_durations(batch, spell_references, now_scalar=None):
    """Overlay exact fixed SRD durations onto matching provider effects.

    The provider still chooses whether an effect exists and its targets. This
    only prevents a named, attached SRD spell from silently degrading to the
    resolver's encounter-only default when the model omits duration fields.
    """
    if (
        not isinstance(batch, dict)
        or not isinstance(spell_references, dict)
        or type(now_scalar) is not int
    ):
        return batch
    from core.effects.clock import display_iso_from_scalar, fixed_duration_seconds
    from core.effects.lifecycle import enter_combat_effect

    references = spell_references.get("spellReferences")
    if not isinstance(references, dict):
        return batch
    trusted = {}
    for reference in references.values():
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
        if not isinstance(effect_name, str):
            return None
        normalized_name = effect_name.strip().casefold()
        exact = trusted.get(normalized_name)
        if exact:
            return exact
        # Models commonly keep the exact spell name but append the selected
        # slot level for display (for example, ``Aid (2nd-level)``). Accept
        # only that tightly bounded suffix; do not fuzzy-match unrelated
        # effect prose to a rules reference.
        for reference_name, duration in trusted.items():
            suffix = normalized_name[len(reference_name):]
            if (
                normalized_name.startswith(reference_name)
                and re.fullmatch(
                    r"\s*\(\s*(?:level\s+\d+|\d+(?:st|nd|rd|th)[ -]?level)\s*\)",
                    suffix,
                )
            ):
                return duration
        return None

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


def _same_feature_used(events, limits):
    """#669: True when the resolved events still use the class feature the
    refused heal named, by the same actor (typed ability and actor, both read
    by feature_heal_key, as the resolver matched them)."""
    wanted = {(r.get("actorId"), feature_heal_key(r.get("ability")))
              for r in limits or [] if isinstance(r, dict)}
    return any(
        isinstance(event, dict)
        and (event.get("actorId"), feature_heal_key((event.get("intent") or {}).get("ability"))) in wanted
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


# #877: said after a typed roll request, as the code-issued roll lines say it.
_TYPED_ROLL_SENTENCE = " Type the result, or type roll and the game rolls."


def _player_request_message(request, typed_roll=False):
    """The text shown for the model's request; ``typed_roll`` (a roll
    request with a typed die, #877) adds that the game can roll it."""
    message = _request_text(request)
    return message + _TYPED_ROLL_SENTENCE if typed_roll else message


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
    for index, exchange in enumerate(exchanges):
        if not isinstance(exchange, dict):
            continue
        player_text = str(exchange.get("playerInput") or "").strip()
        request_text = str(exchange.get("dmRequest") or "").strip()
        if player_text:
            label = "Original player action" if not lines else "Player follow-up"
            lines.append("%s: %s" % (label, player_text))
        if request_text:
            lines.append("DM requested: %s" % request_text)
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


# #263: weapon words a player may use to describe an enemy ("the crossbow
# bandit", "the one with the axe"). Plurals are matched by the pattern below.
_WEAPON_WORDS = (
    "battleaxe", "blowgun", "bow", "club", "crossbow", "dagger", "dart", "flail",
    "glaive", "greataxe", "greatclub", "greatsword", "halberd", "hammer", "handaxe",
    "javelin", "lance", "longbow", "longsword", "mace", "maul", "morningstar", "net",
    "pike", "quarterstaff", "rapier", "scimitar", "shortbow", "shortsword", "sickle",
    "sling", "spear", "staff", "sword", "trident", "warhammer", "whip", "axe",
)


def _owned_weapon_text(sheet):
    """Lower-cased names of everything the sheet lists as an item or action."""
    names = []
    for item in (sheet or {}).get("equipment", []) or []:
        if isinstance(item, dict):
            names.append(str(item.get("item_name") or item.get("name") or ""))
    for entry in _action_entries(sheet or {}):
        if isinstance(entry, dict):
            names.append(str(entry.get("name") or ""))
    return " | ".join(names).casefold()


def _validate_player_weapon_question(batch, encounter, characters, pending):
    """#263: send back a player question about a weapon the player never said
    they were using.

    "I shoot the crossbow bandit" names a target. When the model asks the
    player about (or refuses) a crossbow the sheet does not list, and the
    player's words only used it to describe someone, the request goes back to
    the model as a correction instead of reaching the player.
    """
    exchanges = pending.get("playerExchanges") if isinstance(pending, dict) else None
    player_text = ""
    if isinstance(exchanges, list) and exchanges and isinstance(exchanges[-1], dict):
        player_text = str(exchanges[-1].get("playerInput") or "")
    player_text = player_text.split("\n[Inventory Context:", 1)[0].casefold()
    if not player_text:
        return
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
        prompt = str(request.get("prompt") or "").casefold()
        owned = _owned_weapon_text((characters or {}).get(actor.get("name")))
        for word in _WEAPON_WORDS:
            pattern = r"\b%s(?:e?s)?\b" % word
            if not (re.search(pattern, prompt) and re.search(pattern, player_text)):
                continue
            if re.search(r"\b%s\b" % word, owned):
                continue
            if re.search(r"\b(?:my|own)\s+(?:\w+\s+)?%s\b" % word, player_text):
                continue
            if re.search(r"\bwith\s+(?:a|an)\s+(?:\w+\s+)?%s\b" % word, player_text):
                continue
            raise CombatIntentError(
                (
                    "The player did not say they are using a %s: in their words "
                    "\"%s\" the %s describes the target. Do not ask about or refuse "
                    "it. Choose the player's own listed weapon that fits the verb "
                    "(shoot or fire means their ranged weapon) and resolve the action."
                )
                % (word, player_text.strip()[:160], word),
                intent.get("actorId"),
                {"retryable": True, "issue": "263"},
            )


def _validate_player_input_request_ownership(batch, encounter):
    """Reject high-confidence requests that ask the player for another actor's save."""
    creatures = [
        creature
        for creature in (encounter or {}).get("creatures", []) or []
        if isinstance(creature, dict) and not _is_human_controlled(encounter, creature)
    ]
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
        prompt = str(request.get("prompt") or "")
        if not re.search(r"\bsav(?:e|ing throw)\b", prompt, re.IGNORECASE):
            continue
        for creature in creatures:
            name = str(creature.get("name") or "").replace("_", " ").strip()
            if not name:
                continue
            subject_pattern = (
                r"\b(?:the\s+(?:closest|nearest)\s+)?"
                + re.escape(name)
                + r"\b.{0,48}\b(?:must|needs?\s+to|should)\s+"
                r"(?:make|roll)\b"
            )
            if re.search(subject_pattern, prompt.replace("_", " "), re.IGNORECASE):
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
                        "nonPlayerCombatantId": creature.get("combatantId"),
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


# Item 3: the player's plain melee weapon swing. Code asks for the dice (the
# request is the pause narration; the input line is the C2a [ROLL] tag plus
# the dice), takes only bare typed numbers, and scores the swing; any other
# answer goes back to the model's adjudicated path.
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


def _game_roll_answer(pending, text):
    """#877: the answer to the open typed roll request when the player asks
    the game to roll it: (the sentence the DM reads, faces per die term).
    "answered" when the last exchange already holds the game's roll and
    the DM has not asked again (a resumed turn re-sending "roll"). None
    for any other line, or when no typed request is open: the line then
    goes to the DM as today."""
    if not _lets_the_game_roll(text):
        return None
    exchanges = [item for item in (pending or {}).get("playerExchanges") or [] if isinstance(item, dict)]
    if not exchanges:
        return None
    last = exchanges[-1]
    if last.get("rolledBy") == "game" and not last.get("dmRequest"):
        return "answered"
    terms = _roll_die_terms(last.get("requestedRoll")) if last.get("dmRequest") else None
    if not terms:
        return None
    rng = random.SystemRandom()
    faces = [[rng.randint(1, sides) for _ in range(count)] for count, sides in terms]
    parts = ["%s on the %s" % (" and ".join(str(face) for face in term_faces),
                               "d%d" % sides if count == 1 else "%dd%d" % (count, sides))
             for term_faces, (count, sides) in zip(faces, terms)]
    return "The game rolled for me: %s." % " and ".join(parts), faces
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


def _wants_each_die(record, count):
    """#879 (owner D-879-1): a Great Weapon Fighting damage roll of two or more
    dice asks for each die; the flag was read when the damage was asked for."""
    return (record.get("phase") == "damage" and record.get("greatWeapon") is True
            and not isinstance(record.get("spell"), dict) and count >= 2)


def _each_die_example(count, sides):
    """An example of one number per die, e.g. "1 4" for 2d6, "1 4 2 6" for 4d6."""
    return " ".join(str((face - 1) % sides + 1) for face in ([1, 4, 2, 6, 3, 5] * count)[:count])


def _weapon_attack_prompt(record, entry):
    """The request sentence for the open phase; also stores record["dice"]."""
    count, sides = player_weapon_attack_dice(record, entry)
    record["dice"] = "%dd%d" % (count, sides)
    if record.get("phase") == "attack":
        why = (
            " (%s from %s)" % (record.get("mode"), ", ".join(record.get("modeSources") or []))
            if count == 2 else ""
        )
        what = "both results (e.g. 15 3)" if count == 2 else "the result (e.g. 15)"
        return "%s attack against %s: roll %dd20%s and type %s, or type roll and the game rolls." % (
            record.get("ability"), _spoken_name(record.get("targetName")), count, why, what,
        )
    spell = record.get("spell") if isinstance(record.get("spell"), dict) else {}
    if spell.get("type") == "save":
        # #723: the saves are scored first; the request states each one.
        save = spell.get("save") or {}
        verdicts = []
        for result in save.get("results") or []:
            verdicts.append("%s %s (%s save %s vs DC %s%s)" % (
                _spoken_name(result.get("name")), "succeeds" if result.get("success") else "fails",
                str(save.get("type") or "").capitalize(), result.get("total"), save.get("dc"),
                {"half": ", half damage", "none": ", no damage"}.get(result.get("effect"), ""),
            ))
        return "%s: %s. Roll %dd%d for damage and type the total, or type roll and the game rolls." % (
            record.get("ability"), "; ".join(verdicts), count, sides,
        )
    hit = (
        "critical hit" if record.get("critical")
        else "hit (%s vs AC %s)" % (record.get("attackTotal"), record.get("targetAC"))
    )
    what = ("each die (e.g. %s)" % _each_die_example(count, sides)
            if _wants_each_die(record, count) else "the total")
    return "%s %s on %s: roll %dd%d for damage and type %s, or type roll and the game rolls." % (
        record.get("ability"), hit, _spoken_name(record.get("targetName")), count, sides, what,
    )


def _parse_weapon_roll(text, record, entry):
    """[] for a blank line or "roll" (the game rolls), the typed values when
    they fit the open phase, "invalid" for numbers that do not, None for
    anything else."""
    if text is None:
        return None
    if not text.strip() or _lets_the_game_roll(text):
        return []
    count, sides = player_weapon_attack_dice(record, entry)
    if _wants_each_die(record, count):
        if not _FACE_LIST.match(text):
            return _tray_faces(text, record, entry)
        values = [int(value) for value in re.findall(r"\d+", text)]
        return values if len(values) == count and all(1 <= value <= sides for value in values) else "invalid"
    match = _ROLL_NUMBERS.match(text)
    if not match:
        return _tray_faces(text, record, entry)
    values = [int(group) for group in match.groups() if group is not None]
    if record.get("phase") == "attack":
        fits = len(values) == count and all(1 <= value <= 20 for value in values)
    else:
        fits = len(values) == 1 and count <= values[0] <= count * sides
    return values if fits else "invalid"


def _roll_already_answered(pending):
    """True when an earlier exchange this turn carries the typed request for a
    d20 (``requestedDie`` "d20", "1d20" or "2d20") and the player has answered
    it. The request text is never read (#852)."""
    exchanges = pending.get("playerExchanges") if isinstance(pending, dict) else None
    if not isinstance(exchanges, list):
        return False
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
    melee weapon swing, a cast of a recorded spell attack (#672) or of a
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
        # is superseded by the code-issued [ROLL] line.
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
    return "weapon_attack"


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


def _advance_weapon_attack(encounter_path, encounter, characters, pending, text, voice_intents):
    """Take the typed answer for the open phase. Returns (pending, prompt):
    prompt is the next [ROLL] request, None when the swing is ready to score;
    pending is None when the answer is not a roll (the model's path)."""
    record = deepcopy(pending["weaponAttack"])
    entry = weapon_attack_sheet_entry(encounter, characters, record)
    values = _parse_weapon_roll(text, record, entry) if entry is not None else None
    if values is None:
        write_weapon_attack(encounter_path, pending.get("turnId"), None)
        return None, None
    if values == "invalid":
        count, sides = player_weapon_attack_dice(record, entry)
        hint = (
            "Type %d whole number%s between 1 and 20, or type roll to let the game roll. "
            % (count, "s" if count == 2 else "")
            if record.get("phase") == "attack"
            else "Type each of the %dd%d dice (e.g. %s), or type roll to let the game roll. " % (
                count, sides, _each_die_example(count, sides))
            if _wants_each_die(record, count)
            else "Type the total of %dd%d (%d to %d), or type roll to let the game roll. "
            % (count, sides, count, count * sides)
        )
        return pending, hint + record["prompt"]
    phase = record["phase"]
    count, sides = player_weapon_attack_dice(record, entry)
    if values:
        source, answer = "player", text.strip()
    else:
        roller = random.SystemRandom()
        if phase == "attack":
            values = [roller.randint(1, 20) for _ in range(count)]
        else:
            values = [roller.randint(1, sides) for _ in range(count)]
        source, answer = "game", "(the game rolled %s)" % " ".join(str(v) for v in values)
    if phase == "attack":
        record["faces"][phase] = values
    else:
        # #879: the total stays an int (spell and older readers); the faces are
        # kept beside it whenever they are known (tray, game roll, each die).
        record["faces"][phase] = sum(values)
        if len(values) == count:
            record["faces"]["damageFaces"] = list(values)
    record["sources"][phase] = source
    prompt = None
    requested = None
    if phase == "attack":
        hit, critical, kept, total, ac = player_weapon_attack_score(encounter, characters, record, entry)
        record.update({"hit": hit, "critical": critical, "attackKept": kept,
                       "attackTotal": total, "targetAC": ac})
        if hit:
            record["phase"] = "damage"
            if not isinstance(record.get("spell"), dict):
                record["greatWeapon"] = player_great_weapon(encounter, characters, record, entry)
            prompt = _weapon_attack_prompt(record, entry)
            record["prompt"] = prompt
            requested = record["dice"]
    if prompt is None:
        record["ready"] = True
        record.pop("prompt", None)
        record.pop("dice", None)
    pending = write_weapon_attack(
        encounter_path, pending.get("turnId"), record,
        player_message=prompt, requested_die=requested, answer=answer,
        npc_voice_intents=voice_intents,
    )
    return pending, prompt


def _player_roll_contract_error(pending):
    """Reject an explicitly wrong die before spending another provider call."""
    exchanges = pending.get("playerExchanges") if isinstance(pending, dict) else None
    if not isinstance(exchanges, list) or len(exchanges) < 2:
        return None
    previous = exchanges[-2] if isinstance(exchanges[-2], dict) else {}
    current = exchanges[-1] if isinstance(exchanges[-1], dict) else {}
    # #853: a typed request (its phase stored beside the die) is checked
    # against its stored die only; an exchange written before that keeps
    # today's reading of its request text.
    request = "" if isinstance(previous.get("requestedPhase"), str) else str(previous.get("dmRequest") or "")
    answer = str(current.get("playerInput") or "")
    expected_sequence = [
        int(value)
        for value in re.findall(
            r"\b(?:\d+)?d(4|6|8|10|12|20|100)\b",
            request.lower(),
        )
    ]
    expected_sides = set(expected_sequence)
    persisted_primary = re.fullmatch(
        r"(?:\d+)?d(4|6|8|10|12|20|100)",
        str(previous.get("requestedDie") or "").strip().lower(),
    )
    primary_sides = (
        int(persisted_primary.group(1))
        if persisted_primary
        else expected_sequence[0]
        if expected_sequence
        else None
    )
    claimed_sides = {
        int(value)
        for value in re.findall(
            r"\b(?:\d+)?d(4|6|8|10|12|20|100)\b",
            answer.lower(),
        )
    }
    # Extra dice may be volunteered in natural table talk. Require overlap,
    # not a strict subset, while still requiring the primary requested die
    # below (important when a later die is only optional Sneak Attack damage).
    wrong_family = (
        expected_sides
        and claimed_sides
        and not (claimed_sides & expected_sides)
    )
    missing_primary = (
        primary_sides is not None
        and claimed_sides
        and primary_sides not in claimed_sides
    )
    if wrong_family or missing_primary:
        required_sides = (
            {primary_sides} if missing_primary else expected_sides
        )
        expected = "/".join("d%d" % sides for sides in sorted(required_sides))
        return (
            "That die does not match this action. It calls for %s. Please "
            "roll %s and send the result; your turn is still waiting."
            % (expected, expected)
        )
    for value, sides in re.findall(
        r"\b(?:rolled?|got)\s+(\d+)\s+(?:on\s+)?(?:the\s+)?d(4|6|8|10|12|20|100)\b",
        answer.lower(),
    ):
        if int(value) < 1 or int(value) > int(sides):
            return (
                "A d%s result must be between 1 and %s. Please roll it again; "
                "your turn is still waiting."
                % (sides, sides)
            )
    return None


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
        lint_combat_narration,
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
        dossier = build_scene_dossier(encounter, events, characters)
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
                        lint = lint_combat_narration(candidate, dossier)
                        if lint["reject"]:
                            attempt_status = "rejected"
                            failure_class = "narration_lint_reject"
                            error_code = "NarrationIntegrityReject"
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
                                warning_codes=lint["warnings"],
                            )
                            break
                except (InvocationSupersededError, ReadOnlySaveStop):
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
                    outcome=(
                        "narration_lint_reject"
                        if attempt_status == "rejected"
                        else failure_class
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
            # Item 3: the answer to a code-issued [ROLL] line. Only bare typed
            # numbers (or a blank line) are taken; anything else closes the
            # roll phase and goes to the model as a normal follow-up.
            advanced, roll_prompt = _advance_weapon_attack(
                encounter_path,
                encounter,
                _load_characters(character_paths, context_sheets),
                pending,
                weapon_roll_text if weapon_roll_text is not None else player_input,
                None,
            )
            if roll_prompt is not None:
                raise CombatTurnPaused(
                    "Code-issued weapon roll is waiting for the player",
                    player_message=roll_prompt,
                )
            weapon_answered = advanced is not None
            encounter = safe_json_load(encounter_path)
            pending = deepcopy((encounter.get("combatState") or {}).get("pendingTurn"))
        if not weapon_answered and not _all_non_player(encounter, pending.get("actorIds", [])):
            game_roll = _game_roll_answer(pending, player_input)
            if isinstance(game_roll, tuple):
                # #877: the open typed request decides that this line
                # answers it; the game rolls its full dice.
                append_pending_game_roll(
                    encounter_path,
                    pending.get("turnId"),
                    game_roll[0],
                    game_roll[1],
                )
            elif game_roll is None:
                append_pending_player_input(
                    encounter_path,
                    pending.get("turnId"),
                    player_input,
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
    roll_contract_error = None if events is not None else _player_roll_contract_error(pending)
    if roll_contract_error:
        previous_exchange = (
            pending.get("playerExchanges", [])[-2]
            if len(pending.get("playerExchanges", [])) >= 2
            else {}
        )
        record_pending_player_request(
            encounter_path,
            pending.get("turnId"),
            roll_contract_error,
            requested_die=previous_exchange.get("requestedDie"),
            requested_phase=previous_exchange.get("requestedPhase"),
            npc_voice_intents=immutable_voice_intents,
            requested_roll=previous_exchange.get("requestedRoll"),
        )
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
            "Player supplied a die outside the pending roll contract",
            player_message=roll_contract_error,
        )
    if events is None and not _all_non_player(encounter, pending.get("actorIds", [])):
        try:
            from core.ai.combat_agent import build_contextual_spell_payload

            spell_references = build_contextual_spell_payload(
                provider_characters,
                provider_player_input,
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
    feature_heal_limits = None
    feature_heal_player = False
    window_kind = _window_kind(encounter, pending.get("actorIds", []))
    capability_count, rule_count = _diagnostic_context_counts(spell_references)
    attempt_number = 0
    while events is None:
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
        except (InvocationSupersededError, ReadOnlySaveStop):
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

        try:
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
                    raise CombatTurnPaused(
                        "Code-issued weapon roll is waiting for the player",
                        player_message=record["prompt"],
                    )
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
                _validate_player_weapon_question(batch, encounter, characters, pending)
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
            player_message = _player_request_message(request, typed_roll=typed_roll is not None)
            record_pending_player_request(
                encounter_path,
                pending.get("turnId"),
                player_message,
                requested_die=_authoritative_requested_die(request),
                requested_phase=request.get("phase") if isinstance(request, dict) else None,
                npc_voice_intents=immutable_voice_intents,
                requested_roll=typed_roll,
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
