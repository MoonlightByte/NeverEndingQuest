# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Agentic combat turn orchestration with deterministic commit boundaries."""

from copy import deepcopy

from core.combat import (
    CombatIntentError,
    CombatPlayerInputRequired,
    PersistedPrerollSource,
    resolve_claimed_window,
)
from core.managers.combat_state import combatant_by_id, ensure_combat_state
from core.managers.combat_transaction import (
    apply_staged_turn,
    claim_turn,
    inspect_recovery,
    stage_events,
)
from utils.encoding_utils import safe_json_load


class CombatTurnPaused(RuntimeError):
    """No mutation occurred; the same durable turn may be retried or resumed."""


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
    return bool(actors) and all(actor and actor.get("type") != "player" for actor in actors)


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


def execute_agentic_turn(
    encounter_path,
    actor_ids,
    character_paths,
    context_sheets,
    player_input,
    spell_references=None,
    max_intent_attempts=3,
    intent_provider=None,
    narrator=None,
):
    """Choose, resolve, commit, then narrate one persisted actor window.

    The call is restart-safe. A staged turn is replayed without any provider;
    an un-staged claim regenerates intents against the same revision. Provider
    exhaustion during a player window pauses without consuming the player's
    turn. NPC-only windows fall back to deterministic defend events.
    """
    if intent_provider is None or narrator is None:
        from core.ai.combat_agent import (
            narrate_committed_events,
            request_intent_batch,
        )
        intent_provider = intent_provider or request_intent_batch
        narrator = narrator or narrate_committed_events

    # Reject the wrong pipeline before recovery inspection can become a turn
    # claim. This keeps the public coordinator safe even when called outside
    # combat_manager's persisted-mode guard.
    encounter = safe_json_load(encounter_path)
    if not isinstance(encounter, dict):
        raise CombatTurnPaused("Could not load the combat encounter")
    ensure_combat_state(encounter)
    if (encounter.get("combatState") or {}).get("pipelineMode") != "agentic":
        raise CombatTurnPaused("Cannot run the agentic pipeline on a legacy combat encounter")

    recovery = inspect_recovery(encounter_path)
    if recovery["action"] == "apply_staged_events":
        pending = recovery["pendingTurn"]
        persisted_events = deepcopy(pending.get("events", []))
        committed, characters = apply_staged_turn(
            encounter_path,
            character_paths,
            pending.get("turnId"),
        )
        narration, used_fallback = narrator(committed, persisted_events, player_input)
        return {
            "encounter": committed,
            "characters": characters,
            "events": persisted_events,
            "narration": narration,
            "narrationFallback": used_fallback,
            "recovered": True,
        }

    if recovery["action"] == "regenerate_intent":
        pending = recovery["pendingTurn"]
        encounter = safe_json_load(encounter_path)
        if not isinstance(encounter, dict):
            raise CombatTurnPaused("Could not reload the pending encounter")
        if actor_ids and list(actor_ids) != pending.get("actorIds"):
            raise CombatTurnPaused("Requested actors do not match the pending turn")
    else:
        encounter, pending = claim_turn(encounter_path, actor_ids)

    characters = _load_characters(character_paths, context_sheets)
    correction = None
    events = None
    roll_consumption = None
    last_error = None
    for _attempt in range(max(1, int(max_intent_attempts))):
        try:
            batch = intent_provider(
                encounter,
                characters,
                pending,
                player_input,
                spell_references=spell_references,
                correction=correction,
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
            break
        except CombatPlayerInputRequired as exc:
            request = exc.feedback.get("request", {})
            raise CombatTurnPaused(
                "Player input required before this turn can resolve: %s" % request
            ) from exc
        except (CombatIntentError, IndexError, ValueError) as exc:
            last_error = exc
            correction = {
                "error": str(exc),
                "actorId": getattr(exc, "actor_id", None),
                "details": getattr(exc, "feedback", {}),
                "instruction": "Return a corrected full ordered intent batch.",
            }

    if events is None:
        if not _all_non_player(encounter, pending.get("actorIds", [])):
            raise CombatTurnPaused(
                "The combat intent model could not safely resolve the player's turn: %s"
                % last_error
            )
        fallback_batch = _defend_batch(encounter, pending)
        rolls = _fresh_rolls(encounter)
        events, _preview_encounter, _preview_characters = resolve_claimed_window(
            encounter,
            characters,
            pending,
            fallback_batch,
            rolls,
        )
        roll_consumption = rolls.consumption()

    stage_events(
        encounter_path,
        pending["turnId"],
        events,
        roll_consumption=roll_consumption,
    )
    committed, committed_characters = apply_staged_turn(
        encounter_path,
        character_paths,
        pending["turnId"],
    )
    narration, used_fallback = narrator(committed, events, player_input)
    return {
        "encounter": committed,
        "characters": committed_characters,
        "events": events,
        "narration": narration,
        "narrationFallback": used_fallback,
        "recovered": False,
    }
