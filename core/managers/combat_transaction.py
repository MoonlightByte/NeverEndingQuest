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
import os
import re
import uuid

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
    combat_provenance,
    combatant_by_id,
    resolve_creature_controller,
)
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.path_transaction_lock import path_transaction_lock
from utils.state_transaction import (
    JsonSnapshot,
    ParticipantKind,
    StateTransactionCoordinator,
    TransactionBusyError,
)


class CombatTransactionError(RuntimeError):
    """The turn could not be safely persisted without risking state drift."""


class CombatLeaseBusy(CombatTransactionError):
    """A combat participant is busy; retry without entering recovery mode."""

    retryable = True


class CombatPreconditionChanged(CombatTransactionError):
    """A staged turn was safely returned to intent resolution after drift."""

    retryable = True


def _combat_coordinator(encounter_path, character_paths):
    paths = [encounter_path] + list((character_paths or {}).values())
    directories = [
        os.path.dirname(os.path.realpath(os.path.abspath(os.fspath(path))))
        for path in paths
    ]
    try:
        workspace_root = os.path.commonpath(directories)
    except ValueError as exc:
        raise CombatTransactionError(
            "Combat participants do not share a filesystem root"
        ) from exc
    return StateTransactionCoordinator(
        workspace_root=workspace_root,
        journal_root=".combat-lease-journals",
    )


def _combat_lease_participants(coordinator, encounter_path, character_paths):
    participants = [
        coordinator.lease_participant(encounter_path, ParticipantKind.ENCOUNTER)
    ]
    seen = {participants[0].canonical_path.replace("\\", "/").casefold()}
    for path in (character_paths or {}).values():
        participant = coordinator.lease_participant(path, ParticipantKind.CHARACTER)
        identity = participant.canonical_path.replace("\\", "/").casefold()
        if identity in seen:
            continue
        seen.add(identity)
        participants.append(participant)
    return participants


@contextmanager
def _combat_leases(
    encounter_path,
    character_paths,
    timeout_seconds,
):
    coordinator = _combat_coordinator(encounter_path, character_paths)
    participants = _combat_lease_participants(
        coordinator,
        encounter_path,
        character_paths,
    )
    try:
        with coordinator.ordered_leases(
            participants,
            timeout_seconds=timeout_seconds,
        ):
            yield
    except TransactionBusyError as exc:
        raise CombatLeaseBusy(
            "Combat state is busy; retry the preserved action"
        ) from exc


def _json_fingerprint(value):
    try:
        return JsonSnapshot(True, value).digest
    except (TypeError, ValueError) as exc:
        raise CombatTransactionError(
            "Combat character state could not be fingerprinted"
        ) from exc


def _changed_field_projection(sheet, field_names):
    return {
        name: {
            "exists": name in sheet,
            "value": deepcopy(sheet.get(name)) if name in sheet else None,
        }
        for name in field_names
    }


def _character_fingerprints(
    character_paths,
    character_preconditions,
    character_postconditions,
):
    expected_names = set((character_paths or {}).keys())
    before = character_preconditions or {}
    after = character_postconditions or {}
    if any(not isinstance(name, str) or not name for name in expected_names):
        raise CombatTransactionError("Combat character roster names are invalid")
    if not expected_names.issubset(before) or not expected_names.issubset(after):
        raise CombatTransactionError(
            "Combat character fingerprints do not cover the canonical roster"
        )
    fingerprints = {}
    for name in sorted(expected_names):
        if not isinstance(before.get(name), dict) or not isinstance(
            after.get(name), dict
        ):
            raise CombatTransactionError(
                "Combat character fingerprint source is invalid"
            )
        changed_fields = sorted(
            field
            for field in set(before[name]).union(after[name])
            if before[name].get(field) != after[name].get(field)
            or (field in before[name]) != (field in after[name])
        )
        fingerprints[name] = {
            "before": _json_fingerprint(before[name]),
            "after": _json_fingerprint(after[name]),
            "changedFields": changed_fields,
            "changedBefore": _json_fingerprint(
                _changed_field_projection(before[name], changed_fields)
            ),
            "changedAfter": _json_fingerprint(
                _changed_field_projection(after[name], changed_fields)
            ),
        }
    return fingerprints


def _character_value_preconditions(
    character_paths,
    character_preconditions,
    character_postconditions,
):
    """Record only represented changed values for the typed combat route."""
    before = character_preconditions or {}
    after = character_postconditions or {}
    records = []
    mutation_index = 0
    for name in sorted((character_paths or {})):
        if not isinstance(before.get(name), dict) or not isinstance(after.get(name), dict):
            raise CombatTransactionError(
                "Combat value preconditions do not cover the canonical roster"
            )
        for field in sorted(set(before[name]).union(after[name])):
            before_exists = field in before[name]
            after_exists = field in after[name]
            before_value = deepcopy(before[name].get(field)) if before_exists else None
            after_value = deepcopy(after[name].get(field)) if after_exists else None
            if before_exists == after_exists and before_value == after_value:
                continue
            records.append(
                {
                    "mutationIndex": mutation_index,
                    "recordRef": str(character_paths[name]),
                    "ownerName": name,
                    "fieldPath": field,
                    "beforeExists": before_exists,
                    "beforeValue": before_value,
                    "afterExists": after_exists,
                    "afterValue": after_value,
                }
            )
            mutation_index += 1
    return records


def _value_at_record(character, record):
    exists = record["fieldPath"] in character
    value = deepcopy(character.get(record["fieldPath"])) if exists else None
    return exists, value


def _value_precondition_conflicts(records, characters):
    conflicts = []
    applied = []
    for record in records or []:
        character = characters.get(record.get("ownerName"))
        if not isinstance(character, dict):
            raise CombatTransactionError("Typed combat value owner is unavailable")
        current_exists, current_value = _value_at_record(character, record)
        before = (record.get("beforeExists"), record.get("beforeValue"))
        after = (record.get("afterExists"), record.get("afterValue"))
        current = (current_exists, current_value)
        if current == after:
            applied.append(record["mutationIndex"])
        elif current != before:
            conflicts.append(
                {
                    "recordRef": record["recordRef"],
                    "fieldPath": record["fieldPath"],
                    "beforeValue": deepcopy(record.get("beforeValue")),
                    "afterValue": deepcopy(record.get("afterValue")),
                    "currentValue": current_value,
                }
            )
    return conflicts, applied


def enter_recovery_conflict(encounter, pending, conflicts, applied_subset):
    """Persist the deterministic neither-before-nor-after recovery route."""
    state = ensure_combat_state(encounter)
    atom_id = "combat-atom:%s:0" % pending.get("turnId")
    state["recoveryConflict"] = {
        "conflictId": "combat-conflict:%s" % pending.get("turnId"),
        "parentTurnId": str(pending.get("turnId")),
        "atomId": atom_id,
        "appliedMutationIndexes": sorted(set(applied_subset)),
        "conflicts": deepcopy(conflicts),
        "status": "pending",
        "playerMessage": "Combat recovery needs attention -- Load or Reset",
    }
    pending["stage"] = "recovery_conflict"
    atoms = pending.get("atoms")
    if not isinstance(atoms, list) or not atoms:
        atoms = [{
            "atomId": atom_id,
            "parentTurnId": str(pending.get("turnId")),
            "sequence": 0,
            "kind": "mechanical_resolution",
            "actorId": (pending.get("actorIds") or ["combat-clock"])[0],
            "status": "recovery_conflict",
            "rollIds": [],
            "eventIds": [str(event.get("eventId")) for event in pending.get("events", [])],
            "appliedMutationIndexes": sorted(set(applied_subset)),
            "receiptCommitted": False,
            "mutations": [],
        }]
        pending["atoms"] = atoms
    atoms[0]["status"] = "recovery_conflict"
    atoms[0]["appliedMutationIndexes"] = sorted(set(applied_subset))
    state["phase"] = "recovery_required"
    state["pauseReason"] = "combat_value_conflict"
    return state["recoveryConflict"]


def _validate_character_fingerprints(pending, characters, character_paths):
    fingerprints = pending.get("characterPreconditions")
    if fingerprints is None:
        # Backward compatibility for a turn staged by an older release. Its
        # absolute event values retain the prior crash-replay behavior.
        return True
    expected_names = set((character_paths or {}).keys())
    if not isinstance(fingerprints, dict) or set(fingerprints) != expected_names:
        raise CombatTransactionError(
            "Staged combat character fingerprints are invalid"
        )
    for name in expected_names:
        record = fingerprints.get(name)
        if not isinstance(record, dict) or set(record) != {
            "before",
            "after",
            "changedFields",
            "changedBefore",
            "changedAfter",
        }:
            raise CombatTransactionError(
                "Staged combat character fingerprint record is invalid"
            )
        changed_fields = record.get("changedFields")
        if (
            not isinstance(changed_fields, list)
            or changed_fields != sorted(set(changed_fields))
            or any(not isinstance(field, str) for field in changed_fields)
        ):
            raise CombatTransactionError(
                "Staged combat changed-field fingerprint is invalid"
            )
        allowed = {
            record.get("before"),
            record.get("after"),
            record.get("changedBefore"),
            record.get("changedAfter"),
        }
        if any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in allowed
        ):
            raise CombatTransactionError(
                "Staged combat character fingerprint is invalid"
            )
        current = _json_fingerprint(characters[name])
        if current in {record["before"], record["after"]}:
            continue
        # A process may die after writing this character but before committing
        # the encounter. A later unrelated transaction can then alter another
        # top-level field. Only an exact match for the fields combat changed
        # proves the combat post-image was already applied; an empty/no-op
        # projection cannot prove that and deliberately pauses instead.
        if (
            changed_fields
            and record["changedBefore"] != record["changedAfter"]
            and _json_fingerprint(
                _changed_field_projection(characters[name], changed_fields)
            )
            == record["changedAfter"]
        ):
            continue
        return False
    return True


def _return_stale_turn_to_intent(encounter, characters):
    state = ensure_combat_state(encounter)
    pending = state.get("pendingTurn")
    if not isinstance(pending, dict):
        raise CombatTransactionError("The stale combat turn is no longer pending")
    for name, character in characters.items():
        _project_character_effect_stats(encounter, name, character)
    pending["stage"] = "intent_pending"
    pending["events"] = []
    pending["retryReason"] = "character_state_changed"
    pending.pop("characterPreconditions", None)
    state["phase"] = "resolving_turn"
    state.pop("pauseReason", None)


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
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
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


@contextmanager
def _invocation_commit_authority(invocation_claim):
    """Fence one mutation against concurrent Load/Reset supersession."""
    if invocation_claim is None:
        yield
        return
    from core.combat.invocation import invocation_is_current
    from core.managers.campaign_manager import _party_module_transition_lock

    with _party_module_transition_lock():
        if not invocation_is_current(invocation_claim):
            raise CombatPreconditionChanged(
                "The combat invocation was superseded before mutation"
            )
        yield


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


def _initial_intent_dependencies(encounter, actor_ids):
    state = ensure_combat_state(encounter)
    dependencies = []
    for actor_id in actor_ids or []:
        dependencies.append({
            "recordRef": "encounter:%s" % encounter.get("encounterId"),
            "fieldPath": "combatState.controllers.%s" % actor_id,
            "value": deepcopy((state.get("controllers") or {}).get(actor_id)),
        })
    return dependencies


def _freeze_typed_resolution(encounter, pending, events, value_preconditions):
    """Persist the accepted intent/roll/dependency/atom image exactly once."""
    event = events[0] if events else {}
    intent = event.get("intent") or {}
    outcome = event.get("outcome") or {}
    actor_id = str(event.get("actorId") or (pending.get("actorIds") or [""])[0])
    state = ensure_combat_state(encounter)
    scene_revision = int((encounter.get("sceneFacts") or {}).get("revision", 0))
    target_ids = []
    if intent.get("targetId"):
        target_ids.append(str(intent["targetId"]))
    for target in outcome.get("targets") or []:
        target_id = target.get("combatantId") if isinstance(target, dict) else None
        if target_id and str(target_id) not in target_ids:
            target_ids.append(str(target_id))
    dependencies = list(pending.get("intentDependencies") or [])
    if outcome.get("targetAC") is not None and target_ids:
        dependencies.append({
            "recordRef": "encounter:%s" % encounter.get("encounterId"),
            "fieldPath": "creatures.%s.armorClass" % target_ids[0],
            "value": outcome.get("targetAC"),
        })
    for record in value_preconditions or []:
        dependencies.append({
            "recordRef": str(record.get("recordRef")),
            "fieldPath": str(record.get("fieldPath")),
            "value": deepcopy(record.get("beforeValue")),
        })
    roll_topology = []
    for index, roll in enumerate(event.get("rolls") or []):
        if not isinstance(roll, dict):
            continue
        purpose = str(roll.get("purpose") or "other")
        kind = purpose if purpose in {"attack", "damage", "check", "save", "initiative"} else "other"
        roll_topology.append({
            "rollId": "roll:%s:%s" % (event.get("eventId"), index),
            "kind": kind,
            "purpose": purpose,
            "actorId": actor_id,
            "controllerId": str(resolve_creature_controller(
                combatant_by_id(encounter, actor_id), state
            )),
            "die": str(roll.get("die") or ""),
            "modifierSourcePath": None,
            "dcSourcePath": None,
            "status": "persisted",
            "result": roll.get("value") if isinstance(roll.get("value"), int) else None,
        })
    pending["acceptedResolution"] = {
        "resolutionId": "resolution:%s" % pending.get("turnId"),
        "actorId": actor_id,
        "controllerRevision": int(
            ((state.get("controllers") or {}).get(actor_id) or {}).get("revision", 0)
        ),
        "actionKind": str(intent.get("action") or outcome.get("kind") or "other"),
        "capabilityRef": str(intent.get("ability")) if intent.get("ability") else None,
        "mode": str(intent.get("mode")) if intent.get("mode") else None,
        "targetIds": target_ids,
        "semanticPurpose": str(intent.get("description") or intent.get("action") or "resolve combat action"),
        "rulingKind": (
            str(intent.get("rulingKind"))
            if intent.get("rulingKind") in {"supported", "primitive", "improvised"}
            else "supported"
        ),
        "difficultyBand": str(intent.get("difficultyBand")) if intent.get("difficultyBand") else None,
        "successMeaning": str(intent.get("successMeaning") or "apply the accepted event outcome"),
        "failureMeaning": str(intent.get("failureMeaning") or "apply the accepted event outcome"),
        "continuationKind": "commit_atoms_then_deliver",
        "continuationAtomIndex": 0,
        "frozenAtCombatRevision": int(state.get("revision", 0)),
        "frozenAtSceneRevision": scene_revision,
        "rollTopology": roll_topology,
        "dependencyValues": dependencies,
    }
    mutations = [
        {
            "mutationIndex": int(record["mutationIndex"]),
            "recordRef": str(record["recordRef"]),
            "fieldPath": str(record["fieldPath"]),
            "beforeValue": deepcopy(record.get("beforeValue")),
            "afterValue": deepcopy(record.get("afterValue")),
            "applyOrder": int(record["mutationIndex"]),
        }
        for record in value_preconditions or []
    ]
    pending["atoms"] = []
    for sequence, staged_event in enumerate(events or []):
        pending["atoms"].append({
            "atomId": "combat-atom:%s:%s" % (pending.get("turnId"), sequence),
            "parentTurnId": str(pending.get("turnId")),
            "sequence": sequence,
            "kind": str((staged_event.get("outcome") or {}).get("kind") or "mechanical_resolution"),
            "actorId": str(staged_event.get("actorId") or "combat-clock"),
            "status": "staged",
            "rollIds": [item["rollId"] for item in roll_topology] if sequence == 0 else [],
            "eventIds": [str(staged_event.get("eventId"))],
            "appliedMutationIndexes": [],
            "receiptCommitted": False,
            "mutations": mutations if sequence == 0 else [],
        })
    pending["atomCursor"] = 0
    invocation = pending.get("invocation")
    if isinstance(invocation, dict):
        invocation["status"] = "accepted"


def _typed_dependency_conflicts(encounter, characters, pending, events):
    """Compare represented mechanics inputs without relying on revision bumps."""
    from core.combat.resolver import _combatant_ac, _resource_snapshot

    state = ensure_combat_state(encounter)
    conflicts = []
    for dependency in pending.get("intentDependencies") or []:
        field_path = str(dependency.get("fieldPath") or "")
        prefix = "combatState.controllers."
        if field_path.startswith(prefix):
            actor_id = field_path[len(prefix):]
            current = deepcopy((state.get("controllers") or {}).get(actor_id))
            if current != dependency.get("value"):
                conflicts.append({
                    "recordRef": dependency.get("recordRef"),
                    "fieldPath": field_path,
                    "beforeValue": deepcopy(dependency.get("value")),
                    "currentValue": current,
                })
    for event in events or []:
        outcome = event.get("outcome") or {}
        intent = event.get("intent") or {}
        target_id = intent.get("targetId")
        if target_id and outcome.get("targetAC") is not None:
            target = combatant_by_id(encounter, target_id)
            current_ac = _combatant_ac(encounter, characters, target)
            if current_ac != outcome.get("targetAC"):
                conflicts.append({
                    "recordRef": "encounter:%s" % encounter.get("encounterId"),
                    "fieldPath": "creatures.%s.armorClass" % target_id,
                    "beforeValue": outcome.get("targetAC"),
                    "currentValue": current_ac,
                })
        for resource in event.get("resources") or []:
            if not isinstance(resource, dict):
                continue
            sheet = characters.get(resource.get("owner"))
            snapshot = _resource_snapshot(
                sheet,
                resource.get("kind"),
                resource.get("name"),
            ) if isinstance(sheet, dict) else None
            current_value = snapshot[0] if snapshot is not None else None
            if current_value != resource.get("before"):
                conflicts.append({
                    "recordRef": "character:%s" % resource.get("owner"),
                    "fieldPath": "resource.%s.%s" % (
                        resource.get("kind"), resource.get("name")
                    ),
                    "beforeValue": resource.get("before"),
                    "currentValue": current_value,
                })
    return conflicts


def _bounded_player_text(value, limit=12000):
    return str(value or "").strip()[:limit]


def _require_active_typed_encounter(encounter, state):
    if combat_provenance(encounter) != "typed":
        return
    activation = state.get("activation")
    if (
        not isinstance(activation, dict)
        or activation.get("status") != "active"
        or not activation.get("trackerActivated")
    ):
        raise CombatPreconditionChanged(
            "Typed combat activation changed before mutation"
        )


def mark_encounter_awaiting_actor(
    encounter_path,
    timeout_seconds=None,
    invocation_claim=None,
):
    """Publish the ready phase from the latest authoritative encounter image."""
    with _invocation_commit_authority(invocation_claim), path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        _require_active_typed_encounter(encounter, state)
        if state.get("phase") == "initializing":
            state["phase"] = "awaiting_actor"
            _write_object(encounter_path, encounter, "combat ready phase")
        return deepcopy(encounter)


def store_agentic_preroll_cache(
    encounter_path,
    preroll_cache,
    timeout_seconds=None,
    invocation_claim=None,
):
    """Persist only the typed preroll cache against the latest encounter image."""
    with _invocation_commit_authority(invocation_claim), path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        _require_active_typed_encounter(encounter, state)
        encounter["preroll_cache"] = deepcopy(preroll_cache)
        _write_object(encounter_path, encounter, "agentic preroll cache")
        return deepcopy(encounter)


def claim_turn(
    encounter_path,
    actor_ids,
    turn_id=None,
    player_input=None,
    timeout_seconds=5.0,
    invocation_claim=None,
):
    """Persist a turn claim before requesting or resolving any intent."""
    with _invocation_commit_authority(invocation_claim), path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
        encounter = _load_object(encounter_path, "encounter")
        state = ensure_combat_state(encounter)
        pending = begin_turn(
            encounter,
            actor_ids,
            turn_id=turn_id,
            expected_revision=state["revision"],
        )
        if combat_provenance(encounter) == "typed":
            claim = invocation_claim
            pending["invocation"] = {
                "logicalInvocationId": str(
                    getattr(claim, "logical_invocation_id", None)
                    or "combat-invocation:%s" % uuid.uuid4().hex
                ),
                "attemptId": str(
                    getattr(claim, "attempt_id", None)
                    or "combat-attempt:%s" % uuid.uuid4().hex
                ),
                "generation": int(getattr(claim, "generation", 0) or 0),
                "callsite": "T096",
                "encounterId": str(encounter.get("encounterId")),
                "turnId": str(pending.get("turnId")),
                "windowId": "combat-window:%s" % pending.get("turnId"),
                "expectedCombatRevision": int(state.get("revision", 0)),
                "expectedSceneRevision": int(
                    (encounter.get("sceneFacts") or {}).get("revision", 0)
                ),
                "authorizedTransition": "intent_to_resolution",
                "status": "running",
                "supersededReason": None,
            }
            pending["intentDependencies"] = _initial_intent_dependencies(
                encounter, actor_ids
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
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
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
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
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
    character_paths=None,
    character_preconditions=None,
    character_postconditions=None,
    timeout_seconds=5.0,
    invocation_claim=None,
):
    """Persist fully resolved events before applying any of their effects."""
    lease = (
        _combat_leases(encounter_path, character_paths, timeout_seconds)
        if character_paths is not None
        else path_transaction_lock(
            encounter_path,
            suffix=".combat.lock",
            timeout_seconds=timeout_seconds,
        )
    )
    with _invocation_commit_authority(invocation_claim), lease as acquired:
        if character_paths is None and acquired is None:
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
        encounter = _load_object(encounter_path, "encounter")
        fingerprints = None
        value_preconditions = None
        if character_paths is not None:
            if combat_provenance(encounter) == "typed":
                value_preconditions = _character_value_preconditions(
                    character_paths,
                    character_preconditions,
                    character_postconditions,
                )
            else:
                fingerprints = _character_fingerprints(
                    character_paths,
                    character_preconditions,
                    character_postconditions,
                )
            authoritative = {
                name: _load_object(path, "character %s" % name)
                for name, path in character_paths.items()
            }
            if value_preconditions is not None:
                dependency_conflicts = _typed_dependency_conflicts(
                    encounter,
                    authoritative,
                    ensure_combat_state(encounter).get("pendingTurn") or {},
                    events,
                )
                if dependency_conflicts:
                    pending = ensure_combat_state(encounter).get("pendingTurn")
                    if isinstance(pending, dict) and pending.get("turnId") == turn_id:
                        pending["stage"] = "intent_pending"
                        pending["retryReason"] = "mechanics_dependency_changed"
                        pending["dependencyConflicts"] = dependency_conflicts
                        _write_object(
                            encounter_path,
                            encounter,
                            "mechanics dependency reconsideration",
                        )
                    raise CombatPreconditionChanged(
                        "Combat mechanics changed while intent was resolving"
                    )
            stale_values = False
            if value_preconditions is not None:
                conflicts, applied = _value_precondition_conflicts(
                    value_preconditions,
                    authoritative,
                )
                stale_values = bool(conflicts or applied)
            else:
                stale_values = any(
                    _json_fingerprint(authoritative[name])
                    != fingerprints[name]["before"]
                    for name in fingerprints
                )
            if stale_values:
                state = ensure_combat_state(encounter)
                pending = state.get("pendingTurn")
                if isinstance(pending, dict) and pending.get("turnId") == turn_id:
                    for name, character in authoritative.items():
                        _project_character_effect_stats(
                            encounter,
                            name,
                            character,
                        )
                    pending["retryReason"] = "character_state_changed"
                    _write_object(encounter_path, encounter, "stale combat intent receipt")
                raise CombatPreconditionChanged(
                    "Character state changed while combat intent was resolving"
                )
        pending = stage_turn_events(encounter, turn_id, events)
        if fingerprints is not None:
            pending["characterPreconditions"] = fingerprints
            pending.pop("retryReason", None)
        if value_preconditions is not None:
            pending["valuePreconditions"] = value_preconditions
            pending.pop("characterPreconditions", None)
            pending.pop("retryReason", None)
            pending.pop("dependencyConflicts", None)
            _freeze_typed_resolution(
                encounter,
                pending,
                events,
                value_preconditions,
            )
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
    invocation_claim=None,
):
    """Persist generated prose for a committed turn before history delivery.

    Mechanics have already committed when this receipt exists. Persisting the
    narration means a reconnect can reuse the same wording without another
    provider call. The receipt remains pending until conversation history has
    durably recorded its delivery marker.
    """
    with _invocation_commit_authority(invocation_claim), path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
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
    invocation_claim=None,
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
    with _invocation_commit_authority(invocation_claim), path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
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
    invocation_claim=None,
):
    """Clear a narration receipt only after durable history contains it."""
    with _invocation_commit_authority(invocation_claim), path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise CombatLeaseBusy("Combat state is busy; retry the preserved action")
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
    with _combat_leases(
        encounter_path,
        character_paths,
        timeout_seconds,
    ):
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
    with _combat_leases(
        encounter_path,
        character_paths,
        timeout_seconds,
    ):
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
    invocation_claim=None,
):
    """Replay staged events, write state, and advance the turn exactly once.

    ``character_paths`` maps exact encounter display names to their canonical
    character JSON files.  Enemies intentionally have no character file;
    duplicate monster display names are distinguished only by combatantId in
    the encounter.
    """
    with _invocation_commit_authority(invocation_claim), _combat_leases(
        encounter_path,
        character_paths,
        timeout_seconds,
    ):
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

        value_preconditions = pending.get("valuePreconditions")
        if isinstance(value_preconditions, list):
            conflicts, applied_subset = _value_precondition_conflicts(
                value_preconditions,
                characters,
            )
            if conflicts:
                enter_recovery_conflict(
                    encounter,
                    pending,
                    conflicts,
                    applied_subset,
                )
                _write_object(encounter_path, encounter, "combat recovery conflict")
                raise CombatPreconditionChanged(
                    "Combat recovery needs attention -- Load or Reset"
                )
        elif not _validate_character_fingerprints(
            pending,
            characters,
            character_paths,
        ):
            _return_stale_turn_to_intent(encounter, characters)
            _write_object(encounter_path, encounter, "stale combat turn receipt")
            raise CombatPreconditionChanged(
                "Character state changed before the staged combat turn committed"
            )

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
    with _combat_leases(
        encounter_path,
        character_paths,
        timeout_seconds,
    ):
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
