# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""One atomic commit boundary for an accepted response's resource changes.

AI adapters prepare complete participant images before entering this module.
This module deterministically combines compatible images that started from the
same snapshot, rejects contradictory finals, and gives the shared transaction
coordinator every character and storage participant at once.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

from core.managers.character_transfer import PreparedCharacterAction
from core.managers.storage_transaction import StorageMutationPlan
from updates.update_character_info import _character_image_hash
from utils.enhanced_logger import warning
from utils.inventory_integrity import (
    large_resource_increase_advisories,
    quarantine_malformed_ammunition,
)
from utils.state_transaction import ParticipantKind, StateTransactionCoordinator


class ResourceResponseTransactionError(RuntimeError):
    """Prepared response images cannot be combined without guessing."""


_MISSING = object()


def _same(left: Any, right: Any) -> bool:
    return left == right and type(left) is type(right)


def _merge_value(base: Any, accumulated: Any, candidate: Any, path: str) -> Any:
    """Three-way merge deterministic, independently prepared final images.

    A candidate that leaves a value unchanged contributes nothing. Repeated
    identical finals deduplicate. Disjoint mapping fields combine. Competing
    final values fail closed so model prose can never choose transaction math.
    """
    if _same(candidate, base):
        return copy.deepcopy(accumulated)
    if _same(accumulated, base):
        return copy.deepcopy(candidate)
    if _same(accumulated, candidate):
        return copy.deepcopy(accumulated)

    if all(isinstance(value, dict) for value in (base, accumulated, candidate)):
        merged: Dict[str, Any] = {}
        keys = set(base) | set(accumulated) | set(candidate)
        for key in keys:
            base_value = base.get(key, _MISSING)
            current_value = accumulated.get(key, _MISSING)
            candidate_value = candidate.get(key, _MISSING)
            child = f"{path}.{key}" if path else str(key)
            result = _merge_value(
                base_value,
                current_value,
                candidate_value,
                child,
            )
            if result is not _MISSING:
                merged[key] = result
        return merged

    if base is _MISSING:
        if accumulated is _MISSING:
            return copy.deepcopy(candidate)
        if candidate is _MISSING or _same(accumulated, candidate):
            return copy.deepcopy(accumulated)
    elif accumulated is _MISSING and candidate is _MISSING:
        return _MISSING

    raise ResourceResponseTransactionError(
        "prepared response has conflicting final values at %s" % (path or "<root>")
    )


@dataclass
class _MergedParticipant:
    path: str
    kind: ParticipantKind
    existed: bool
    before: Any
    after: Any


def _add_candidate(
    participants: Dict[str, _MergedParticipant],
    *,
    path: str,
    kind: ParticipantKind,
    existed: bool,
    before: Any,
    after: Any,
) -> None:
    canonical = os.path.realpath(os.path.abspath(os.path.normpath(path)))
    existing = participants.get(canonical)
    if existing is None:
        participants[canonical] = _MergedParticipant(
            canonical,
            kind,
            existed,
            copy.deepcopy(before),
            copy.deepcopy(after),
        )
        return
    if existing.kind != kind:
        raise ResourceResponseTransactionError(
            "prepared response assigned incompatible participant kinds"
        )
    if existing.existed != existed or not _same(existing.before, before):
        raise ResourceResponseTransactionError(
            "prepared response participants do not share one pre-image"
        )
    existing.after = _merge_value(
        existing.before,
        existing.after,
        after,
        os.path.basename(canonical),
    )


def _identity(participants: Iterable[_MergedParticipant]) -> str:
    facts = []
    for participant in sorted(participants, key=lambda item: item.path):
        encoded = json.dumps(
            participant.after,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        facts.append(
            "%s:%s:%s"
            % (
                participant.path,
                participant.kind.value,
                hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            )
        )
    return hashlib.sha256("|".join(facts).encode("utf-8")).hexdigest()


def execute_resource_response_transaction(
    character_actions: Tuple[PreparedCharacterAction, ...],
    storage_plans: Tuple[StorageMutationPlan, ...],
) -> Dict[str, Any]:
    """Commit all prepared resource images from one accepted response once."""
    participants: Dict[str, _MergedParticipant] = {}
    for prepared in tuple(character_actions):
        if not isinstance(prepared, PreparedCharacterAction):
            raise TypeError("response character actions must be prepared")
        plan = prepared.plan
        if _character_image_hash(plan.pre_image) != plan.pre_image_hash:
            raise ResourceResponseTransactionError(
                "character plan pre-image hash mismatch"
            )
        _add_candidate(
            participants,
            path=plan.canonical_path,
            kind=ParticipantKind.CHARACTER,
            existed=True,
            before=plan.pre_image,
            after=plan.post_image,
        )

    for plan in tuple(storage_plans):
        if not isinstance(plan, StorageMutationPlan):
            raise TypeError("response storage plans must be prepared")
        if plan.character_path:
            _add_candidate(
                participants,
                path=plan.character_path,
                kind=ParticipantKind.CHARACTER,
                existed=True,
                before=plan.character_before,
                after=plan.character_after,
            )
        _add_candidate(
            participants,
            path=plan.storage_path,
            kind=ParticipantKind.STORAGE,
            existed=plan.storage_existed,
            before=plan.storage_before,
            after=plan.storage_after,
        )

    changed = [
        participant
        for participant in participants.values()
        if not participant.existed or not _same(participant.before, participant.after)
    ]
    if not changed:
        return {"success": True, "transaction_id": None, "participant_count": 0}

    coordinator = StateTransactionCoordinator(workspace_root=".")
    coordinator_participants = []
    for participant in changed:
        before = (
            coordinator.snapshot(participant.before)
            if participant.existed
            else coordinator.snapshot(exists=False)
        )
        coordinator_participants.append(
            coordinator.participant(
                participant.path,
                participant.kind,
                before,
                coordinator.snapshot(participant.after),
            )
        )
    transaction = coordinator.build_plan(
        transaction_key="response-%s" % _identity(changed),
        operation="resource_response",
        participants=coordinator_participants,
        rollback_failure_code="resource_response_rolled_back",
    )
    result = coordinator.execute(transaction, timeout_seconds=30.0)
    for participant in changed:
        if participant.kind != ParticipantKind.CHARACTER:
            continue
        try:
            quarantined = quarantine_malformed_ammunition(
                participant.before,
                participant.path,
            )
            if quarantined:
                warning(
                    "INVENTORY: Preserved malformed legacy ammunition before repair",
                    category="character_validation",
                )
        except Exception as exc:
            warning(
                "INVENTORY: Could not preserve malformed ammunition forensic: %s" % exc,
                category="character_validation",
            )
        for advisory in large_resource_increase_advisories(
            participant.before,
            participant.after,
        ):
            warning(
                "INVENTORY: %s" % advisory.replace(":", " "),
                category="character_updates",
            )
    return {
        "success": True,
        "transaction_id": result.transaction_id,
        "participant_count": len(changed),
    }
