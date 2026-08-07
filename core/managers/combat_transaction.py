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

from core.combat import (
    apply_resolution,
    check_invariants,
    ensure_agentic_roll_reserve,
    resolution_from_event,
)
from core.managers.combat_state import (
    CombatStateConflict,
    begin_turn,
    commit_turn,
    ensure_combat_state,
    recovery_action,
    stage_turn_events,
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


def claim_turn(encounter_path, actor_ids, turn_id=None, timeout_seconds=5.0):
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
        state.pop("pauseReason", None)
        if state.get("pipelineMode") == "agentic":
            ensure_agentic_roll_reserve(encounter, actor_ids)
        _write_object(encounter_path, encounter, "turn claim")
        return deepcopy(encounter), deepcopy(pending)


def stage_events(
    encounter_path,
    turn_id,
    events,
    roll_consumption=None,
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
        if isinstance(roll_consumption, dict):
            encounter.setdefault("preroll_cache", {})["consumed"] = deepcopy(
                roll_consumption
            )
        _write_object(encounter_path, encounter, "staged combat events")
        return deepcopy(encounter), deepcopy(pending)


def inspect_recovery(encounter_path):
    """Read the durable recovery decision without modifying the encounter."""
    encounter = _load_object(encounter_path, "encounter")
    return recovery_action(encounter)


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
        for event in pending.get("events", []):
            resolution = resolution_from_event(next_encounter, next_characters, event)
            next_encounter, next_characters = apply_resolution(
                next_encounter,
                next_characters,
                resolution,
            )
            event_ids.append(str(event["eventId"]))

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
