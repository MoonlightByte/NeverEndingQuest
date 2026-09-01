# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Agentic combat turn orchestration with deterministic commit boundaries."""

from collections.abc import Mapping
from copy import deepcopy
import logging
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
from core.managers.combat_state import (
    combatant_by_id,
    ensure_combat_state,
    normalize_npc_voice_intents,
    resolve_creature_controller,
    valid_pending_delivery,
)
from core.managers.combat_transaction import (
    CombatPreconditionChanged,
    append_pending_player_input,
    apply_staged_turn,
    claim_turn,
    enter_effect_clock,
    inspect_recovery,
    record_delivery_narration,
    record_narration_attempt,
    record_pending_player_request,
    stage_events,
)
from utils.encoding_utils import safe_json_load


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
    normalized = normalize_npc_voice_intents(npc_voice_intents)
    if normalized is None:
        complete_envelope = (
            isinstance(npc_voice_intents, Mapping)
            and all(
                key in npc_voice_intents
                for key in ("contractVersion", "sourceBeatId", "actors")
            )
            and isinstance(npc_voice_intents.get("contractVersion"), str)
            and isinstance(npc_voice_intents.get("sourceBeatId"), str)
            and isinstance(npc_voice_intents.get("actors"), Mapping)
        )
        if complete_envelope:
            _LOGGER.warning(
                "Complete combat voice advisory envelope was invalid and omitted"
            )
            return MappingProxyType({})
        # Preserve the pre-envelope public call shape for custom callers and
        # tests. It may advise T096, but without a versioned source beat it is
        # deliberately ineligible for transaction persistence or T097 replay.
        try:
            legacy_rows = dict(npc_voice_intents or {})
        except (TypeError, ValueError):
            legacy_rows = {}
        actors = {}
        for actor_id, row in legacy_rows.items():
            if not isinstance(actor_id, str) or not isinstance(row, dict):
                continue
            if not isinstance(row.get("npcName"), str):
                continue
            if not isinstance(row.get("thought"), str):
                continue
            actors[actor_id] = MappingProxyType(dict(row))
        return MappingProxyType(
            {"actors": MappingProxyType(actors)} if actors else {}
        )
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
    if isinstance(legal_actions, list) and legal_actions:
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


def _player_request_message(request):
    if not isinstance(request, dict):
        return "I need one more detail before resolving that action. What do you do?"
    prompt = request.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        rendered = prompt.strip()
        # Some models put the later damage die in the structured `die` field
        # while correctly asking for the attack first in prose.  Make the
        # primary roll explicit in both the player message and the durable
        # fallback parser so a missing legacy requestedDie cannot flip phases.
        if _authoritative_requested_die(request) == "d20" and not re.search(
            r"\b(?:\d+)?d20\b", rendered, flags=re.IGNORECASE
        ):
            rendered = re.sub(
                r"\broll\s+(?:a|an|your)\s+"
                r"((?:melee|ranged|spell)\s+)?attack(?:\s+roll)?\b",
                r"Roll d20 for the \1attack roll",
                rendered,
                count=1,
                flags=re.IGNORECASE,
            )
        return rendered
    reason = request.get("reason")
    die = request.get("die")
    if isinstance(reason, str) and reason.strip() and isinstance(die, str) and die.strip():
        return "Please roll %s for %s." % (die.strip(), reason.strip())
    if isinstance(reason, str) and reason.strip():
        return "I need one more choice before resolving that action: %s." % reason.strip()
    return "I need one more detail before resolving that action. What do you do?"


def _authoritative_requested_die(request):
    """Prefer the primary d20 when a combined prompt also names damage dice."""
    if not isinstance(request, dict):
        return None
    structured = str(request.get("die") or "").strip().lower()
    prompt = str(request.get("prompt") or "").strip().lower()
    if "roll" in prompt and re.search(
        r"\b(?:melee|ranged|spell)\s+attack(?:\s+roll)?\b|"
        r"(?<!sneak\s)\battack\s+roll\b|"
        r"\broll(?:\s+an?|\s+your)?\s+attack\b",
        prompt,
    ):
        return "d20"
    return structured or None


def _composed_player_input(pending, fallback):
    """Render the complete retained action/clarification chain for T096."""
    exchanges = pending.get("playerExchanges") if isinstance(pending, dict) else None
    if not isinstance(exchanges, list) or not exchanges:
        return str(fallback or "")
    lines = []
    for index, exchange in enumerate(exchanges[-8:]):
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


def _validate_single_player_input_request(batch, encounter, spell_references=None):
    """Reject one pending request that tries to encode multiple roll phases."""
    trusted_spell_names = {
        str(reference.get("name") or "").strip().casefold()
        for reference in (
            (spell_references or {}).get("spellReferences") or {}
        ).values()
        if isinstance(reference, dict) and str(reference.get("name") or "").strip()
    } if isinstance(spell_references, dict) else set()
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
        dice = {
            value.lower().replace(" ", "")
            for value, sides in re.findall(
                r"\b(\d*d(4|6|8|10|12|20|100)(?:\s*[+-]\s*\d+)?)\b",
                prompt,
                flags=re.IGNORECASE,
            )
            if sides != "20"
        }
        spell_name = str(request.get("spellName") or "").strip().casefold()
        single_trusted_spell = bool(
            spell_name and spell_name in trusted_spell_names
        )
        prompt_spell_names = {
            trusted_name
            for trusted_name in trusted_spell_names
            if re.search(
                r"(?<!\w)%s(?!\w)" % re.escape(trusted_name),
                prompt,
                flags=re.IGNORECASE,
            )
        }
        mentions_another_spell = bool(
            prompt_spell_names - ({spell_name} if spell_name else set())
        )
        if len(dice) > 1 and (
            not single_trusted_spell or mentions_another_spell
        ):
            raise CombatIntentError(
                (
                    "requiresPlayerInput combined multiple dice expressions; "
                    "request only the earliest unresolved player roll"
                ),
                intent.get("actorId"),
                {
                    "multiRollRequest": sorted(dice),
                    "spellName": request.get("spellName"),
                    "mentionedSpells": sorted(prompt_spell_names),
                },
            )


def _player_roll_contract_error(pending):
    """Reject an explicitly wrong die before spending another provider call."""
    exchanges = pending.get("playerExchanges") if isinstance(pending, dict) else None
    if not isinstance(exchanges, list) or len(exchanges) < 2:
        return None
    previous = exchanges[-2] if isinstance(exchanges[-2], dict) else {}
    current = exchanges[-1] if isinstance(exchanges[-1], dict) else {}
    request = str(previous.get("dmRequest") or "")
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
                except InvocationSupersededError:
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
        if not _all_non_player(encounter, pending.get("actorIds", [])):
            append_pending_player_input(
                encounter_path,
                pending.get("turnId"),
                player_input,
            )
            encounter = safe_json_load(encounter_path)
            pending = deepcopy((encounter.get("combatState") or {}).get("pendingTurn"))
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
    provider_player_input = _composed_player_input(pending, player_input)
    roll_contract_error = _player_roll_contract_error(pending)
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
    if not _all_non_player(encounter, pending.get("actorIds", [])):
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
    events = None
    roll_consumption = None
    rules_drift_seen = False
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
        except InvocationSupersededError as exc:
            raise CombatTurnPaused(
                "Combat invocation was superseded",
                player_message=(
                    "That combat response was superseded by Load or Reset. "
                    "The restored game state remains authoritative."
                ),
            ) from exc
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
            _validate_player_input_request_ownership(batch, encounter)
            _validate_single_player_input_request(
                batch,
                encounter,
                spell_references=spell_references,
            )
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
            player_message = _player_request_message(request)
            record_pending_player_request(
                encounter_path,
                pending.get("turnId"),
                player_message,
                requested_die=_authoritative_requested_die(request),
            )
            raise CombatTurnPaused(
                "Combat resolution requires more player input",
                player_message=player_message,
            ) from exc
        except (CombatIntentError, IndexError, TypeError, ValueError) as exc:
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
