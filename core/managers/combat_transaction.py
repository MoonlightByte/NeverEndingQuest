# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Crash-recoverable persistence for deterministic combat turns.

The encounter file is the transaction journal.  A turn claim is persisted
before model work, resolved events are persisted before mechanical writes,
and every character/resource/effect write is absolute and replay-safe.  The
encounter receipt and cursor are committed last.
"""

from contextlib import contextmanager
from copy import deepcopy
import re

from core.combat import (
    apply_resolution,
    check_invariants,
    ensure_agentic_roll_reserve,
    resolution_from_event,
)
from core.effects.lifecycle import enter_combat_effect, exit_combat_effect
from core.effects.effective import effective_sheet
from core.managers.combat_state import (
    CombatStateConflict,
    begin_turn,
    commit_turn,
    ensure_combat_state,
    recovery_action,
    stage_turn_events,
    valid_pending_delivery,
)
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.path_transaction_lock import path_transaction_lock


class CombatTransactionError(RuntimeError):
    """The turn could not be safely persisted without risking state drift."""


@contextmanager
def completion_lease(encounter_path, timeout_seconds=5.0):
    """Serialize and persist one idempotent combat-completion step.

    The caller performs one external side effect, records its receipt in
    ``combatState.completion``, and exits the context. If the side effect
    raises, no receipt is written and reconnect can safely retry it. Lock
    ordering is combat lease before module-refresh lock; callers must never
    acquire these in the reverse order.
    """
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        ensure_combat_state(encounter)
        yield encounter
        _write_object(encounter_path, encounter, "combat completion receipt")


def _load_object(path, label):
    value = safe_json_load(path)
    if not isinstance(value, dict):
        raise CombatTransactionError("Could not load %s from %s" % (label, path))
    return value


def _write_object(path, value, label):
    if not safe_write_json(path, value):
        raise CombatTransactionError("Could not persist %s to %s" % (label, path))


def _project_character_effect_stats(encounter, name, character):
    """Refresh the encounter's character cache from an effective sheet."""
    rendered = effective_sheet(character)
    for creature in encounter.get("creatures", []) or []:
        if (
            not isinstance(creature, dict)
            or creature.get("type") not in ("player", "npc")
            or creature.get("name") != name
        ):
            continue
        for sheet_field, encounter_field in (
            ("hitPoints", "currentHitPoints"),
            ("maxHitPoints", "maxHitPoints"),
            ("armorClass", "armorClass"),
        ):
            value = rendered.get(sheet_field)
            if isinstance(value, (int, float)):
                creature[encounter_field] = int(value)


def _bounded_player_text(value, limit=12000):
    return str(value or "").strip()[:limit]


def claim_turn(
    encounter_path,
    actor_ids,
    turn_id=None,
    player_input=None,
    timeout_seconds=5.0,
):
    """Persist a turn claim before requesting or resolving any intent."""
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        pending = begin_turn(
            encounter,
            actor_ids,
            turn_id=turn_id,
            expected_revision=state["revision"],
        )
        initial_input = _bounded_player_text(player_input)
        if initial_input:
            pending["playerExchanges"] = [{"playerInput": initial_input}]
        state.pop("pauseReason", None)
        if state.get("pipelineMode") == "agentic":
            ensure_agentic_roll_reserve(encounter, actor_ids)
        _write_object(encounter_path, encounter, "turn claim")
        return deepcopy(encounter), deepcopy(pending)


def append_pending_player_input(
    encounter_path,
    turn_id,
    player_input,
    timeout_seconds=5.0,
):
    """Durably add one clarification/roll to an unresolved player turn."""
    rendered = _bounded_player_text(player_input)
    if not rendered:
        return
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        pending = state.get("pendingTurn")
        if not isinstance(pending, dict) or pending.get("turnId") != turn_id:
            raise CombatTransactionError("The pending player turn changed")
        if pending.get("stage") != "intent_pending":
            raise CombatTransactionError("The pending player turn is already staged")
        exchanges = pending.get("playerExchanges")
        if not isinstance(exchanges, list):
            exchanges = []
        exchanges = [item for item in exchanges if isinstance(item, dict)][-7:]
        if not exchanges or exchanges[-1].get("playerInput") != rendered:
            exchanges.append({"playerInput": rendered})
        pending["playerExchanges"] = exchanges[-8:]
        _write_object(encounter_path, encounter, "pending player clarification")


def record_pending_player_request(
    encounter_path,
    turn_id,
    player_message,
    requested_die=None,
    timeout_seconds=5.0,
):
    """Persist the DM's bounded question beside the action it clarifies."""
    rendered = _bounded_player_text(player_message, limit=4000)
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        pending = state.get("pendingTurn")
        if not isinstance(pending, dict) or pending.get("turnId") != turn_id:
            raise CombatTransactionError("The pending player turn changed")
        exchanges = pending.get("playerExchanges")
        if not isinstance(exchanges, list) or not exchanges:
            exchanges = [{"playerInput": ""}]
        exchanges[-1]["dmRequest"] = rendered
        die = str(requested_die or "").strip().lower()
        if re.fullmatch(r"(?:\d+)?d(?:4|6|8|10|12|20|100)", die):
            exchanges[-1]["requestedDie"] = die
        pending["playerExchanges"] = exchanges[-8:]
        _write_object(encounter_path, encounter, "pending player request")


def stage_events(
    encounter_path,
    turn_id,
    events,
    roll_consumption=None,
    delivery_context=None,
    timeout_seconds=5.0,
):
    """Persist fully resolved events before applying any of their effects."""
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        pending = stage_turn_events(encounter, turn_id, events)
        context = delivery_context if isinstance(delivery_context, dict) else {}
        pending["deliveryContext"] = {
            "historyInput": str(context.get("historyInput") or "")[:24000],
            "displayPrefix": str(context.get("displayPrefix") or "")[:4000],
        }
        if isinstance(roll_consumption, dict):
            encounter.setdefault("preroll_cache", {})["consumed"] = deepcopy(
                roll_consumption
            )
        _write_object(encounter_path, encounter, "staged combat events")
        return deepcopy(encounter), deepcopy(pending)


def record_delivery_narration(
    encounter_path,
    delivery_id,
    narration,
    used_fallback,
    timeout_seconds=5.0,
):
    """Persist generated prose for a committed turn before history delivery.

    Mechanics have already committed when this receipt exists. Persisting the
    narration means a reconnect can reuse the same wording without another
    provider call. The receipt remains pending until conversation history has
    durably recorded its delivery marker.
    """
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        delivery = state.get("pendingDelivery")
        if not isinstance(delivery, dict):
            if str(delivery_id) in state.get("deliveredDeliveryIds", []):
                return deepcopy(encounter)
            raise CombatStateConflict("No committed combat narration is pending")
        if not valid_pending_delivery(delivery):
            raise CombatStateConflict(
                "Committed combat narration receipt is invalid"
            )
        if delivery.get("deliveryId") != str(delivery_id):
            raise CombatStateConflict("Combat narration delivery ID does not match")
        existing = delivery.get("narration")
        if isinstance(existing, str) and existing.strip():
            return deepcopy(encounter)
        rendered = str(narration or "").strip()
        if not rendered:
            raise CombatTransactionError("Committed combat narration was empty")
        delivery["narration"] = rendered
        delivery["narrationFallback"] = bool(used_fallback)
        _write_object(encounter_path, encounter, "combat narration receipt")
        return deepcopy(encounter)


def record_narration_attempt(
    encounter_path,
    delivery_id,
    attempt,
    status,
    candidate="",
    violations=None,
    warnings=None,
    timeout_seconds=5.0,
):
    """Persist one rejected/error T097 attempt outside the display field.

    The attempt record is correction context only. ``pendingDelivery.narration``
    remains untouched, so web reconnect can never replay a rejected candidate.
    """
    from core.managers.combat_state import NARRATION_ATTEMPT_STATUSES

    status = str(status or "")
    if status not in NARRATION_ATTEMPT_STATUSES:
        raise CombatTransactionError("Unknown combat narration attempt status")
    violation_codes = [
        str(code)
        for code in (violations or [])
        if isinstance(code, str)
    ][:24]
    warning_codes = [
        str(code)
        for code in (warnings or [])
        if isinstance(code, str)
    ][:24]
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        delivery = state.get("pendingDelivery")
        if not valid_pending_delivery(delivery):
            raise CombatStateConflict(
                "Committed combat narration receipt is invalid"
            )
        if delivery.get("deliveryId") != str(delivery_id):
            raise CombatStateConflict("Combat narration delivery ID does not match")
        if isinstance(delivery.get("narration"), str):
            return deepcopy(encounter)
        attempts = list(delivery.get("narrationAttempts") or [])
        expected = len(attempts) + 1
        if type(attempt) is not int or attempt != expected:
            raise CombatStateConflict(
                "Combat narration attempt %r is out of sequence; expected %r"
                % (attempt, expected)
            )
        if len(attempts) >= 12:
            raise CombatTransactionError("Combat narration attempt receipt is full")
        attempts.append(
            {
                "attempt": attempt,
                "status": status,
                "candidate": str(candidate or "")[:12000],
                "violations": violation_codes,
                "warnings": warning_codes,
            }
        )
        delivery["narrationAttempts"] = attempts
        if not valid_pending_delivery(delivery):
            raise CombatTransactionError("Combat narration attempt was not safe to persist")
        _write_object(encounter_path, encounter, "combat narration attempt")
        return deepcopy(encounter)


def acknowledge_delivery(
    encounter_path,
    delivery_id,
    timeout_seconds=5.0,
):
    """Clear a narration receipt only after durable history contains it."""
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        delivery_id = str(delivery_id)
        delivery = state.get("pendingDelivery")
        if not isinstance(delivery, dict):
            if delivery_id in state.get("deliveredDeliveryIds", []):
                return deepcopy(encounter)
            raise CombatStateConflict("No committed combat narration is pending")
        if not valid_pending_delivery(delivery):
            raise CombatStateConflict(
                "Committed combat narration receipt is invalid"
            )
        if delivery.get("deliveryId") != delivery_id:
            raise CombatStateConflict("Combat narration delivery ID does not match")
        delivered = list(state.get("deliveredDeliveryIds") or [])
        if delivery_id not in delivered:
            delivered.append(delivery_id)
        state["deliveredDeliveryIds"] = delivered[-200:]
        state["pendingDelivery"] = None
        state.pop("pauseReason", None)
        _write_object(encounter_path, encounter, "combat narration acknowledgement")
        return deepcopy(encounter)


def inspect_recovery(encounter_path):
    """Read the durable recovery decision without modifying the encounter."""
    encounter = _load_object(encounter_path, "encounter")
    return recovery_action(encounter)


def enter_effect_clock(
    encounter_path,
    character_paths,
    now_scalar,
    timeout_seconds=5.0,
):
    """Idempotently convert world deadlines to combat rounds before a turn."""
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        if state.get("effectsClockEntered"):
            return
        for name, path in (character_paths or {}).items():
            character = _load_object(path, "character %s" % name)
            character["temporaryEffects"] = [
                enter_combat_effect(effect, now_scalar)
                if isinstance(effect, dict)
                else effect
                for effect in character.get("temporaryEffects", []) or []
            ]
            _write_object(path, character, "combat effect clock for %s" % name)
            _project_character_effect_stats(encounter, name, character)
        state["effectsClockEntered"] = True
        state["effectsClockExited"] = False
        state["effectsClockScalar"] = int(now_scalar)
        _write_object(encounter_path, encounter, "combat effect-clock receipt")


def exit_effect_clock(
    encounter_path,
    character_paths,
    now_scalar,
    timeout_seconds=5.0,
):
    """Idempotently return surviving round effects to the world clock."""
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        if state.get("effectsClockExited"):
            return
        for name, path in (character_paths or {}).items():
            character = _load_object(path, "character %s" % name)
            surviving = []
            for effect in character.get("temporaryEffects", []) or []:
                converted = (
                    exit_combat_effect(effect, now_scalar)
                    if isinstance(effect, dict)
                    else effect
                )
                if converted is not None:
                    surviving.append(converted)
            character["temporaryEffects"] = surviving
            _write_object(path, character, "world effect clock for %s" % name)
            _project_character_effect_stats(encounter, name, character)
        state["effectsClockExited"] = True
        state["effectsClockExitScalar"] = int(now_scalar)
        _write_object(encounter_path, encounter, "world effect-clock receipt")


def apply_staged_turn(
    encounter_path,
    character_paths,
    turn_id=None,
    timeout_seconds=5.0,
):
    """Replay staged events, write state, and advance the turn exactly once.

    ``character_paths`` maps exact encounter display names to their canonical
    character JSON files.  Enemies intentionally have no character file;
    duplicate monster display names are distinguished only by combatantId in
    the encounter.
    """
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")

        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        pending = state.get("pendingTurn")
        if not isinstance(pending, dict):
            if turn_id and turn_id in state.get("appliedTurnIds", []):
                return deepcopy(encounter), {}
            raise CombatStateConflict("No staged combat turn is available")
        if turn_id is not None and pending.get("turnId") != turn_id:
            raise CombatStateConflict("The staged turn does not match the requested turn")
        if pending.get("stage") != "events_staged":
            raise CombatStateConflict("The pending turn has no resolved events to apply")
        turn_id = pending["turnId"]

        characters = {}
        for name, path in (character_paths or {}).items():
            characters[name] = _load_object(path, "character %s" % name)

        next_encounter = deepcopy(encounter)
        next_characters = deepcopy(characters)
        event_ids = []
        try:
            for event in pending.get("events", []):
                resolution = resolution_from_event(
                    next_encounter, next_characters, event
                )
                next_encounter, next_characters = apply_resolution(
                    next_encounter,
                    next_characters,
                    resolution,
                )
                event_ids.append(str(event["eventId"]))
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            # Keep the staged journal intact. A missing/misresolved character
            # file must become a recoverable pause, not a permanent raw
            # exception loop or a silently partial commit.
            raise CombatTransactionError(
                "The staged combat turn could not be replayed safely. "
                "Restore the missing character data or a known-good save."
            ) from exc

        violations = check_invariants(next_encounter, next_characters)
        if violations:
            raise CombatTransactionError(
                "Combat invariants rejected the staged turn: %s"
                % "; ".join(violations)
            )

        # Character files are written first.  If the process exits between
        # writes, the staged journal remains and absolute after-values make a
        # subsequent replay converge instead of applying damage/resources
        # twice.  The encounter receipt/cursor is always the final write.
        for name, path in (character_paths or {}).items():
            _write_object(path, next_characters[name], "character %s" % name)

        commit_turn(next_encounter, turn_id, event_ids)
        _write_object(encounter_path, next_encounter, "combat turn commit")
        return deepcopy(next_encounter), deepcopy(next_characters)


def apply_combat_rewards(
    encounter_path,
    character_paths,
    xp_per_character,
    timeout_seconds=5.0,
):
    """Apply end-of-combat XP once, including recovery between file writes."""
    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatTransactionError("Timed out acquiring the combat lease")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        completion = state["completion"]
        if completion.get("rewardsApplied"):
            return deepcopy(encounter)

        pending = completion.get("pendingRewards")
        if not isinstance(pending, dict):
            pending = {}
            for name, path in (character_paths or {}).items():
                character = _load_object(path, "character %s" % name)
                before = int(character.get("experience_points", 0) or 0)
                pending[name] = {
                    "before": before,
                    "after": before + max(0, int(xp_per_character)),
                }
            completion["pendingRewards"] = pending
            _write_object(encounter_path, encounter, "pending combat rewards")

        for name, path in (character_paths or {}).items():
            if name not in pending:
                raise CombatTransactionError(
                    "Reward journal does not cover character %s" % name
                )
            character = _load_object(path, "character %s" % name)
            character["experience_points"] = int(pending[name]["after"])
            _write_object(path, character, "combat reward for %s" % name)

        completion["rewardsApplied"] = True
        completion["pendingRewards"] = None
        _write_object(encounter_path, encounter, "combat reward receipt")
        return deepcopy(encounter)
