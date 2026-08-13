# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Bounded planning and deterministic staging for complex resource responses.

The planner may arrange only fact identifiers extracted from already-prepared
actions. It never supplies quantities or final balances. Code owns arithmetic,
underflow checks, duplicate validation, canonical participant identity, and the
final in-memory images consumed by the atomic response transaction.
"""

from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from core.managers.character_transfer import PreparedCharacterAction
from core.managers.storage_transaction import StorageMutationPlan
from updates.update_character_info import _field_change_facts
from utils.enhanced_logger import warning
from utils.inventory_integrity import inventory_metadata, normalize_inventory_name


class ResourceTransactionPlanningError(RuntimeError):
    """A complex resource operation could not be compiled without guessing."""


class ResourceTransactionProviderError(ResourceTransactionPlanningError):
    """The bounded T105 provider calls failed before a plan was returned."""


@dataclass(frozen=True)
class ResourceRoutingDecision:
    requires_planning: bool
    score: int
    threshold: int
    provider: str
    model_family: str
    inputs: Mapping[str, Any]


@dataclass(frozen=True)
class ResourceFact:
    fact_id: str
    action_index: int
    participant_id: str
    path: Optional[str]
    family: str
    name: str
    quantity: int
    direction: str
    current_quantity: Optional[int]
    changes: str
    row: Optional[Mapping[str, Any]] = None
    canonical_edge: bool = False

    def packet(self) -> Dict[str, Any]:
        value = {
            "fact_id": self.fact_id,
            "source_action_index": self.action_index,
            "participant": self.participant_id,
            "family": self.family,
            "name": self.name,
            "direction": self.direction,
            "requested_quantity": abs(self.quantity),
            "action_fact": self.changes,
        }
        if self.current_quantity is not None:
            value["current_quantity"] = self.current_quantity
        if self.row is not None:
            key = (
                "accepted_operation"
                if self.participant_id.startswith("storage:")
                else "canonical_row"
            )
            value[key] = copy.deepcopy(dict(self.row))
        return value


@dataclass(frozen=True)
class ResourceLedgerParticipant:
    """One participant in a response-scoped resource operation ledger.

    Persistent participants own an in-memory pre-image that may later be handed
    to the existing atomic response coordinator.  External actors close a
    conservation edge for the duration of one response only; they deliberately
    have neither a path nor an image that could be persisted.
    """

    participant_id: str
    kind: str
    path: Optional[str] = None
    pre_image: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class ResourceOperationFact:
    """A single ordered resource delta, including temporary custody."""

    fact_id: str
    participant_id: str
    family: str
    name: str
    quantity: int
    row: Optional[Mapping[str, Any]] = None
    requires_fact_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RehearsedResourceOperationLedger:
    """Deterministic result of rehearsing an operation ledger in memory."""

    persistent_images: Mapping[str, Mapping[str, Any]]
    external_deltas: Mapping[Tuple[str, str, str], int]
    completed_fact_ids: Tuple[str, ...]
    stage_evidence: Tuple[Mapping[str, Mapping[str, Any]], ...]


@dataclass(frozen=True)
class PlannedResourceTransaction:
    character_actions: Tuple[PreparedCharacterAction, ...]
    storage_plans: Tuple[StorageMutationPlan, ...]
    decision: ResourceRoutingDecision
    plan: Optional[Mapping[str, Any]]
    planner_calls: int
    advisories: Tuple[str, ...] = ()
    non_character_deltas: Tuple[Tuple[str, str, str, int], ...] = ()


_DENOMINATIONS = ("gold", "silver", "copper")
_RESOURCE_FIELDS = ("equipment", "ammunition", "currency")
_LEDGER_PARTICIPANT_KINDS = {
    "persistent_character",
    "persistent_storage",
    "external_actor",
}


def _safe_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")
    return normalized[:40] or "resource"


def _strict_quantity(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResourceTransactionPlanningError(f"{label} is not nonnegative")
    return value


def _rows(sheet: Mapping[str, Any], field: str, name_field: str):
    values = sheet.get(field) or []
    if not isinstance(values, list) or not all(isinstance(row, dict) for row in values):
        raise ResourceTransactionPlanningError(f"{field} is malformed")
    result = {}
    for row in values:
        name = normalize_inventory_name(row.get(name_field))
        if not name or name in result:
            raise ResourceTransactionPlanningError(
                f"{field} has an ambiguous canonical identity"
            )
        result[name] = row
    return result


def _character_facts(
    prepared: Sequence[PreparedCharacterAction],
) -> Tuple[ResourceFact, ...]:
    facts = []
    for position, item in enumerate(prepared):
        before = item.plan.pre_image
        after = item.plan.post_image
        participant = f"character:{item.plan.character_name}"
        before_currency = before.get("currency") or {}
        after_currency = after.get("currency") or {}
        if not isinstance(before_currency, dict) or not isinstance(
            after_currency, dict
        ):
            raise ResourceTransactionPlanningError("currency is malformed")
        for denomination in _DENOMINATIONS:
            old = _strict_quantity(
                before_currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            new = _strict_quantity(
                after_currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            delta = new - old
            if delta:
                facts.append(
                    ResourceFact(
                        f"C{position}A{item.index}-currency-{denomination}",
                        item.index,
                        participant,
                        item.plan.canonical_path,
                        "currency",
                        denomination,
                        delta,
                        "in" if delta > 0 else "out",
                        old,
                        item.changes,
                    )
                )
        for family, field, name_field in (
            ("equipment", "equipment", "item_name"),
            ("ammunition", "ammunition", "name"),
        ):
            old_rows = _rows(before, field, name_field)
            new_rows = _rows(after, field, name_field)
            for name in sorted(set(old_rows) | set(new_rows)):
                old = (
                    _strict_quantity(
                        old_rows[name].get("quantity", 1),
                        f"{field}.{name}.quantity",
                    )
                    if name in old_rows
                    else 0
                )
                new = (
                    _strict_quantity(
                        new_rows[name].get("quantity", 1),
                        f"{field}.{name}.quantity",
                    )
                    if name in new_rows
                    else 0
                )
                delta = new - old
                if not delta:
                    continue
                row = old_rows[name] if delta < 0 else new_rows[name]
                facts.append(
                    ResourceFact(
                        f"C{position}A{item.index}-{family}-{_safe_part(name)}",
                        item.index,
                        participant,
                        item.plan.canonical_path,
                        family,
                        name,
                        delta,
                        "in" if delta > 0 else "out",
                        old,
                        item.changes,
                        copy.deepcopy(row),
                    )
                )
    collapsed = []
    by_resource = {}
    for fact in facts:
        key = (fact.path, fact.participant_id, fact.family, fact.name)
        existing = by_resource.get(key)
        if existing is None:
            by_resource[key] = fact
            collapsed.append(fact)
            continue
        same_final = (
            existing.current_quantity == fact.current_quantity
            and existing.quantity == fact.quantity
        )
        same_row = json.dumps(
            existing.row,
            sort_keys=True,
            default=str,
        ) == json.dumps(fact.row, sort_keys=True, default=str)
        if same_final and same_row:
            continue
        raise ResourceTransactionPlanningError(
            f"same-participant {fact.family} {fact.name} facts propose "
            "competing finals"
        )
    facts = collapsed
    identifiers = [fact.fact_id for fact in facts]
    if len(identifiers) != len(set(identifiers)):
        raise ResourceTransactionPlanningError("resource fact identifiers collide")
    return tuple(facts)


def _storage_facts(storage_plans: Sequence[StorageMutationPlan]):
    facts = []
    for plan_index, plan in enumerate(storage_plans):
        operation_set = plan.operation.get("operations")
        operations = (
            operation_set if isinstance(operation_set, list) else [plan.operation]
        )
        for operation_index, operation in enumerate(operations):
            action = str(operation.get("action") or "storage_mutation")
            family = (
                "currency"
                if "currency" in action
                else (
                    "ammunition"
                    if "ammunition" in action
                    else "equipment" if "item" in action else "storage"
                )
            )
            name = str(
                operation.get("denomination")
                or operation.get("ammunition_name")
                or operation.get("item_name")
                or operation.get("storage_id")
                or action
            )
            raw_quantity = operation.get("quantity", 1)
            quantity = (
                raw_quantity
                if isinstance(raw_quantity, int) and not isinstance(raw_quantity, bool)
                else 1
            )
            direction = "out" if action.startswith("retrieve_") else "in"
            facts.append(
                ResourceFact(
                    f"S{plan_index}-{operation_index}-{_safe_part(action)}",
                    -1,
                    f"storage:{plan_index}",
                    plan.storage_path,
                    family,
                    normalize_inventory_name(name) or _safe_part(name),
                    quantity if direction == "in" else -quantity,
                    direction,
                    None,
                    action,
                    copy.deepcopy(operation),
                )
            )
    return tuple(facts)


def build_resource_transaction_packet(
    prepared: Sequence[PreparedCharacterAction],
    storage_plans: Sequence[StorageMutationPlan],
):
    facts = _character_facts(prepared) + _storage_facts(storage_plans)
    return {
        "facts": [fact.packet() for fact in facts],
        "constraints": {
            "reference_fact_ids_only": True,
            "arithmetic_is_code_owned": True,
            "all_facts_must_be_staged_or_exact_duplicates": True,
        },
    }, facts


def route_resource_transaction(
    prepared: Sequence[PreparedCharacterAction],
    storage_plans: Sequence[StorageMutationPlan],
    *,
    provider: str,
) -> ResourceRoutingDecision:
    _packet, facts = build_resource_transaction_packet(prepared, storage_plans)
    paths = [item.plan.canonical_path for item in prepared]
    repeated = len(paths) != len(set(paths))
    participants = {fact.participant_id for fact in facts}
    families = {fact.family for fact in facts}
    has_storage = bool(storage_plans)
    has_character = bool(prepared)
    directions = {fact.direction for fact in facts if fact.family != "storage"}
    transfer_shape = len(participants) > 1 and directions == {"in", "out"}
    unmatched_transfer_facts = 0
    if transfer_shape:
        for fact in facts:
            if fact.family == "storage":
                continue
            opposite = "out" if fact.direction == "in" else "in"
            if not any(
                other.fact_id != fact.fact_id
                and other.participant_id != fact.participant_id
                and other.family == fact.family
                and other.name == fact.name
                and other.direction == opposite
                for other in facts
            ):
                unmatched_transfer_facts += 1
    inputs = {
        "participant_count": len(participants),
        "asset_family_count": len(families),
        "fact_count": len(facts),
        "repeated_participant": repeated,
        "storage_sibling": has_storage and has_character,
        "transfer_shape": transfer_shape,
        "unmatched_transfer_fact_count": unmatched_transfer_facts,
    }
    score = 0
    score += 1 if len(facts) > 1 else 0
    score += 3 if repeated else 0
    score += 2 if len(participants) > 1 else 0
    score += 2 if len(families) > 1 else 0
    score += 2 if has_storage and has_character else 0
    score += 2 if transfer_shape else 0
    score += 3 if unmatched_transfer_facts else 0
    from model_config import (
        RESOURCE_PLAN_T105_COMPLEXITY_THRESHOLDS,
        RESOURCE_PLAN_T105_GEMINI_FLASH_LOW,
        RESOURCE_PLAN_T105_GPT54MINI_LOW,
        RESOURCE_PLAN_T105_LEGACY,
        RESOURCE_PLAN_T105_LMSTUDIO,
    )

    threshold = RESOURCE_PLAN_T105_COMPLEXITY_THRESHOLDS.get(
        provider,
        RESOURCE_PLAN_T105_COMPLEXITY_THRESHOLDS["legacy"],
    )
    model_config = {
        "legacy": RESOURCE_PLAN_T105_LEGACY,
        "openai": RESOURCE_PLAN_T105_GPT54MINI_LOW,
        "gemini": RESOURCE_PLAN_T105_GEMINI_FLASH_LOW,
        "lmstudio": RESOURCE_PLAN_T105_LMSTUDIO,
    }.get(provider, RESOURCE_PLAN_T105_LEGACY)
    return ResourceRoutingDecision(
        requires_planning=bool(facts) and score >= threshold,
        score=score,
        threshold=threshold,
        provider=provider,
        model_family=str(model_config.get("model") or "unknown"),
        inputs=inputs,
    )


def storage_overlap_has_complete_planning_packet(
    prepared: Sequence[PreparedCharacterAction],
    storage_plans: Sequence[StorageMutationPlan],
    *,
    provider: str,
) -> bool:
    """Return whether an overlap is a complete, conserved T105 candidate.

    This is the fail-safe escape from the legacy one-action/one-storage pairing
    seam.  It performs no provider call and cannot relax an incomplete packet:
    every exact resource identity must balance across the supplied character
    and storage facts before the overlap may reach the bounded planner.
    """
    try:
        _packet, facts = build_resource_transaction_packet(prepared, storage_plans)
        if not any(fact.participant_id.startswith("storage:") for fact in facts):
            return False
        if not any(fact.participant_id.startswith("character:") for fact in facts):
            return False
        totals = {}
        for fact in facts:
            if fact.family not in _RESOURCE_FIELDS:
                continue
            key = (fact.family, fact.name)
            totals[key] = totals.get(key, 0) + fact.quantity
        if not totals or any(quantity != 0 for quantity in totals.values()):
            return False
        return route_resource_transaction(
            prepared,
            storage_plans,
            provider=provider,
        ).requires_planning
    except ResourceTransactionPlanningError:
        return False


def _duplicate_equivalent(left: ResourceFact, right: ResourceFact) -> bool:
    if (
        left.participant_id,
        left.family,
        left.name,
        left.quantity,
    ) != (
        right.participant_id,
        right.family,
        right.name,
        right.quantity,
    ):
        return False
    if left.family == "currency":
        return True
    return json.dumps(left.row, sort_keys=True, default=str) == json.dumps(
        right.row, sort_keys=True, default=str
    )


def _validate_plan(value: Any, facts: Sequence[ResourceFact]):
    if not isinstance(value, dict) or set(value) != {
        "stages",
        "edges",
        "duplicates",
    }:
        raise ResourceTransactionPlanningError(
            "planner returned an invalid top-level shape"
        )
    fact_map = {fact.fact_id: fact for fact in facts}
    participant_paths = {}
    path_participants = {}
    for fact in facts:
        if fact.path is None:
            continue
        participant_paths.setdefault(fact.participant_id, set()).add(fact.path)
        path_participants.setdefault(fact.path, set()).add(fact.participant_id)
    if any(len(paths) != 1 for paths in participant_paths.values()) or any(
        len(participants) != 1 for participants in path_participants.values()
    ):
        raise ResourceTransactionPlanningError(
            "planner input has ambiguous participant identities"
        )
    duplicates = {}
    raw_duplicates = value.get("duplicates")
    if not isinstance(raw_duplicates, list):
        raise ResourceTransactionPlanningError("planner duplicates must be an array")
    for duplicate in raw_duplicates:
        if not isinstance(duplicate, dict) or set(duplicate) != {
            "fact_id",
            "canonical_fact_id",
        }:
            raise ResourceTransactionPlanningError("planner duplicate shape is invalid")
        fact_id = duplicate["fact_id"]
        canonical = duplicate["canonical_fact_id"]
        if (
            fact_id not in fact_map
            or canonical not in fact_map
            or fact_id == canonical
            or fact_id in duplicates
            or not _duplicate_equivalent(fact_map[fact_id], fact_map[canonical])
        ):
            raise ResourceTransactionPlanningError(
                "planner marked non-identical facts as duplicates"
            )
        duplicates[fact_id] = canonical
    if any(canonical in duplicates for canonical in duplicates.values()):
        raise ResourceTransactionPlanningError("planner duplicate chains are forbidden")

    raw_stages = value.get("stages")
    if not isinstance(raw_stages, list) or not raw_stages:
        raise ResourceTransactionPlanningError("planner returned no stages")
    staged = []
    expected_stage = 1
    for stage in raw_stages:
        if not isinstance(stage, dict) or set(stage) != {
            "stage",
            "fact_ids",
            "confidence",
        }:
            raise ResourceTransactionPlanningError("planner stage shape is invalid")
        if (
            stage["stage"] != expected_stage
            or not isinstance(stage["fact_ids"], list)
            or stage["confidence"] != "high"
        ):
            raise ResourceTransactionPlanningError("planner stages are not sequential")
        expected_stage += 1
        for fact_id in stage["fact_ids"]:
            if fact_id not in fact_map or fact_id in duplicates or fact_id in staged:
                raise ResourceTransactionPlanningError("planner staged an invalid fact")
            staged.append(fact_id)
    if set(staged) | set(duplicates) != set(fact_map):
        raise ResourceTransactionPlanningError(
            "planner did not classify every observed fact exactly once"
        )

    edge_members = set()
    edges = {}
    raw_edges = value.get("edges")
    if not isinstance(raw_edges, list):
        raise ResourceTransactionPlanningError("planner edges must be an array")
    for edge in raw_edges:
        if not isinstance(edge, dict) or set(edge) != {
            "edge_id",
            "source_fact_ids",
            "destination_fact_ids",
            "authority",
            "confidence",
        }:
            raise ResourceTransactionPlanningError("planner edge shape is invalid")
        edge_id = edge["edge_id"]
        sources = edge["source_fact_ids"]
        destinations = edge["destination_fact_ids"]
        if (
            not isinstance(edge_id, str)
            or not edge_id
            or edge_id in edges
            or not isinstance(sources, list)
            or not isinstance(destinations, list)
            or len(sources) != 1
            or len(destinations) != 1
            or edge["authority"] not in {"source", "destination"}
            or edge["confidence"] != "high"
        ):
            raise ResourceTransactionPlanningError(
                "planner edges require one source and one destination"
            )
        source_id, destination_id = sources[0], destinations[0]
        if (
            source_id not in staged
            or destination_id not in staged
            or source_id in edge_members
            or destination_id in edge_members
        ):
            raise ResourceTransactionPlanningError(
                "planner edge references are invalid"
            )
        source, destination = fact_map[source_id], fact_map[destination_id]
        if (
            source.quantity >= 0
            or destination.quantity <= 0
            or source.family != destination.family
            or (
                source.name != destination.name
                and source.family not in {"equipment", "ammunition"}
            )
            or source.participant_id == destination.participant_id
            or source.family == "storage"
        ):
            raise ResourceTransactionPlanningError(
                "planner edge directions are invalid"
            )
        edge_members.update((source_id, destination_id))
        edges[edge_id] = (source_id, destination_id, edge["authority"])
    return tuple(staged), duplicates, edges


def _apply_row_fact(sheet: Dict[str, Any], fact: ResourceFact, quantity: int):
    field, name_field = (
        ("equipment", "item_name")
        if fact.family == "equipment"
        else ("ammunition", "name")
    )
    rows = copy.deepcopy(sheet.get(field) or [])
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and normalize_inventory_name(row.get(name_field)) == fact.name
    ]
    if len(matches) > 1:
        raise ResourceTransactionPlanningError(
            f"{fact.family} {fact.name} has ambiguous rows"
        )
    if quantity < 0:
        if not matches:
            raise ResourceTransactionPlanningError(
                f"{fact.family} {fact.name} is unavailable"
            )
        row = matches[0]
        current = _strict_quantity(
            row.get("quantity", 1), f"{fact.family}.{fact.name}.quantity"
        )
        final = current + quantity
        if final < 0:
            raise ResourceTransactionPlanningError(
                f"{fact.family} {fact.name} would underflow"
            )
        if final == 0:
            rows.remove(row)
        else:
            row["quantity"] = final
    else:
        if matches:
            row = matches[0]
            current = _strict_quantity(
                row.get("quantity", 1), f"{fact.family}.{fact.name}.quantity"
            )
            if fact.canonical_edge:
                if not isinstance(fact.row, Mapping) or inventory_metadata(
                    row, name_field
                ) != inventory_metadata(fact.row, name_field):
                    raise ResourceTransactionPlanningError(
                        f"{fact.family} {fact.name} receiver identity is ambiguous"
                    )
                canonical = copy.deepcopy(dict(fact.row))
                canonical["quantity"] = current + quantity
                if fact.family == "equipment":
                    canonical["equipped"] = False
                rows[rows.index(row)] = canonical
            else:
                row["quantity"] = current + quantity
        else:
            if not isinstance(fact.row, Mapping):
                raise ResourceTransactionPlanningError(
                    f"{fact.family} {fact.name} has no candidate row"
                )
            row = copy.deepcopy(dict(fact.row))
            row["quantity"] = quantity
            if fact.canonical_edge and fact.family == "equipment":
                row["equipped"] = False
            rows.append(row)
    sheet[field] = rows


def _apply_fact(sheet: Dict[str, Any], fact: ResourceFact, quantity: int):
    if fact.family == "currency":
        currency = copy.deepcopy(sheet.get("currency") or {})
        if not isinstance(currency, dict):
            raise ResourceTransactionPlanningError("currency is malformed")
        current = _strict_quantity(currency.get(fact.name, 0), f"currency.{fact.name}")
        final = current + quantity
        if final < 0:
            raise ResourceTransactionPlanningError(
                f"currency {fact.name} would underflow"
            )
        currency[fact.name] = final
        sheet["currency"] = currency
        return
    if fact.family in {"equipment", "ammunition"}:
        _apply_row_fact(sheet, fact, quantity)


def _ledger_fact(operation: ResourceOperationFact, path: Optional[str]):
    name = normalize_inventory_name(operation.name)
    return ResourceFact(
        fact_id=operation.fact_id,
        action_index=-1,
        participant_id=operation.participant_id,
        path=path,
        family=operation.family,
        name=name,
        quantity=operation.quantity,
        direction="in" if operation.quantity > 0 else "out",
        current_quantity=None,
        changes="operation_ledger",
        row=copy.deepcopy(operation.row),
        canonical_edge=operation.family in {"equipment", "ammunition"},
    )


def _apply_ledger_operation(
    image: Dict[str, Any],
    participant: ResourceLedgerParticipant,
    operation: ResourceOperationFact,
):
    """Apply one operation to a private image without writing any file."""
    fact = _ledger_fact(operation, participant.path)
    if participant.kind == "persistent_character":
        _apply_fact(image, fact, operation.quantity)
        return
    if participant.kind != "persistent_storage":
        raise ResourceTransactionPlanningError(
            "external actors cannot receive a persistent resource image"
        )
    if operation.family == "equipment":
        proxy = copy.deepcopy(image)
        proxy["equipment"] = copy.deepcopy(image.get("contents") or [])
        _apply_fact(proxy, fact, operation.quantity)
        image["contents"] = proxy["equipment"]
        return
    _apply_fact(image, fact, operation.quantity)


def rehearse_resource_operation_ledger(
    participants: Sequence[ResourceLedgerParticipant],
    operations: Sequence[ResourceOperationFact],
    stages: Sequence[Sequence[str]],
) -> RehearsedResourceOperationLedger:
    """Validate and rehearse an ordered, conserved ledger entirely in memory.

    The operation list is intentionally separate from net-final character
    deltas.  An actor may therefore receive and later pass on the same asset in
    one response without that temporary custody disappearing from the plan.
    """
    participant_map = {}
    path_owners = {}
    images = {}
    for participant in participants:
        if (
            not isinstance(participant.participant_id, str)
            or not participant.participant_id.strip()
            or participant.participant_id in participant_map
            or participant.kind not in _LEDGER_PARTICIPANT_KINDS
        ):
            raise ResourceTransactionPlanningError(
                "operation ledger has an invalid participant identity"
            )
        participant_map[participant.participant_id] = participant
        if participant.kind == "external_actor":
            if participant.path is not None or participant.pre_image is not None:
                raise ResourceTransactionPlanningError(
                    "external actors cannot own persistent state"
                )
            continue
        if (
            not isinstance(participant.path, str)
            or not participant.path
            or not isinstance(participant.pre_image, Mapping)
            or participant.path in path_owners
        ):
            raise ResourceTransactionPlanningError(
                "operation ledger has an invalid persistent participant"
            )
        path_owners[participant.path] = participant.participant_id
        images[participant.participant_id] = copy.deepcopy(dict(participant.pre_image))

    operation_map = {}
    conservation = {}
    for operation in operations:
        name = normalize_inventory_name(operation.name)
        if (
            not isinstance(operation.fact_id, str)
            or not operation.fact_id
            or operation.fact_id in operation_map
            or operation.participant_id not in participant_map
            or operation.family not in _RESOURCE_FIELDS
            or not name
            or isinstance(operation.quantity, bool)
            or not isinstance(operation.quantity, int)
            or operation.quantity == 0
            or not isinstance(operation.requires_fact_ids, tuple)
            or len(operation.requires_fact_ids) != len(set(operation.requires_fact_ids))
        ):
            raise ResourceTransactionPlanningError(
                "operation ledger contains a malformed fact"
            )
        if operation.family == "currency" and name not in _DENOMINATIONS:
            raise ResourceTransactionPlanningError(
                "operation ledger contains an invalid denomination"
            )
        if operation.family in {"equipment", "ammunition"} and not isinstance(
            operation.row, Mapping
        ):
            raise ResourceTransactionPlanningError(
                "operation ledger asset fact has no canonical row"
            )
        operation_map[operation.fact_id] = operation
        key = (operation.family, name)
        conservation[key] = conservation.get(key, 0) + operation.quantity
    if not operation_map:
        raise ResourceTransactionPlanningError("operation ledger contains no facts")
    if any(total != 0 for total in conservation.values()):
        raise ResourceTransactionPlanningError(
            "operation ledger is not conserved by exact resource identity"
        )
    for operation in operations:
        if any(
            dependency == operation.fact_id or dependency not in operation_map
            for dependency in operation.requires_fact_ids
        ):
            raise ResourceTransactionPlanningError(
                "operation ledger contains an invalid dependency"
            )

    completed = []
    completed_set = set()
    evidence = []
    external_deltas = {}
    if not isinstance(stages, Sequence) or not stages:
        raise ResourceTransactionPlanningError("operation ledger has no stages")
    for stage in stages:
        if (
            not isinstance(stage, Sequence)
            or isinstance(stage, (str, bytes))
            or not stage
        ):
            raise ResourceTransactionPlanningError(
                "operation ledger has a malformed stage"
            )
        stage_ids = tuple(stage)
        if len(stage_ids) != len(set(stage_ids)):
            raise ResourceTransactionPlanningError(
                "operation ledger repeats a fact in one stage"
            )
        for fact_id in stage_ids:
            operation = operation_map.get(fact_id)
            if operation is None or fact_id in completed_set:
                raise ResourceTransactionPlanningError(
                    "operation ledger stages an invalid fact"
                )
            if not set(operation.requires_fact_ids).issubset(completed_set):
                raise ResourceTransactionPlanningError(
                    "operation ledger dependency is not available before use"
                )
            participant = participant_map[operation.participant_id]
            if participant.kind == "external_actor":
                key = (
                    participant.participant_id,
                    operation.family,
                    normalize_inventory_name(operation.name),
                )
                external_deltas[key] = external_deltas.get(key, 0) + operation.quantity
            else:
                _apply_ledger_operation(
                    images[participant.participant_id], participant, operation
                )
            completed.append(fact_id)
            completed_set.add(fact_id)
        evidence.append(copy.deepcopy(images))
    if completed_set != set(operation_map):
        raise ResourceTransactionPlanningError(
            "operation ledger did not stage every fact exactly once"
        )

    persistent_images = {
        participant.path: copy.deepcopy(images[participant.participant_id])
        for participant in participants
        if participant.kind != "external_actor"
    }
    return RehearsedResourceOperationLedger(
        persistent_images=persistent_images,
        external_deltas=external_deltas,
        completed_fact_ids=tuple(completed),
        stage_evidence=tuple(evidence),
    )


def _stage_character_images(
    prepared: Sequence[PreparedCharacterAction],
    facts: Sequence[ResourceFact],
    staged: Sequence[str],
    edges,
):
    fact_map = _effective_edge_fact_map(facts, edges)
    original_fact_map = {fact.fact_id: fact for fact in facts}
    edge_quantities = {}
    for source_id, destination_id, authority in edges.values():
        source, destination = fact_map[source_id], fact_map[destination_id]
        amount = (
            abs(source.quantity) if authority == "source" else abs(destination.quantity)
        )
        edge_quantities[source_id] = -amount
        edge_quantities[destination_id] = amount

    by_path = {}
    for item in prepared:
        existing = by_path.get(item.plan.canonical_path)
        if existing is None:
            by_path[item.plan.canonical_path] = copy.deepcopy(item.plan.pre_image)
        elif existing != item.plan.pre_image:
            raise ResourceTransactionPlanningError(
                "staged participant pre-images do not match"
            )
    canonical_advisories = {}
    for fact_id in staged:
        fact = fact_map[fact_id]
        if fact.path not in by_path:
            continue  # Storage facts are already deterministic prepared plans.
        quantity = edge_quantities.get(fact_id, fact.quantity)
        _apply_fact(by_path[fact.path], fact, quantity)
        original = original_fact_map[fact_id]
        if fact.canonical_edge and (
            fact.name != original.name or fact.row != original.row
        ):
            canonical_advisories.setdefault(fact.path, set()).add(
                f"transfer_metadata_canonicalized:{fact.name}"
            )

    result = []
    for item in prepared:
        post_image = copy.deepcopy(item.plan.post_image)
        final_resources = by_path[item.plan.canonical_path]
        for field in _RESOURCE_FIELDS:
            if field in final_resources:
                post_image[field] = copy.deepcopy(final_resources[field])
            else:
                post_image.pop(field, None)
        plan = replace(
            item.plan,
            post_image=post_image,
            field_facts=tuple(_field_change_facts(item.plan.pre_image, post_image)),
            advisories=tuple(
                sorted(
                    set(item.plan.advisories)
                    | canonical_advisories.get(item.plan.canonical_path, set())
                )
            ),
        )
        result.append(replace(item, plan=plan))
    for advisories in canonical_advisories.values():
        for advisory in sorted(advisories):
            warning(f"INVENTORY: {advisory}", category="character_updates")
    return tuple(result)


def _reconcile_staged_images(
    prepared: Sequence[PreparedCharacterAction],
    staged_images: Sequence[PreparedCharacterAction],
    facts: Sequence[ResourceFact],
    staged: Sequence[str],
    edges,
    non_character_deltas=(),
):
    """Prove staged finals exactly equal code-owned ledger arithmetic."""
    fact_map = _effective_edge_fact_map(facts, edges)
    effective_facts = tuple(fact_map[fact.fact_id] for fact in facts)
    edge_quantities = {}
    for source_id, destination_id, authority in edges.values():
        source = fact_map[source_id]
        destination = fact_map[destination_id]
        amount = (
            abs(source.quantity) if authority == "source" else abs(destination.quantity)
        )
        edge_quantities[source_id] = -amount
        edge_quantities[destination_id] = amount
        if edge_quantities[source_id] + edge_quantities[destination_id] != 0:
            raise ResourceTransactionPlanningError(
                "planned transfer edge is not conserved"
            )

    expected = {}
    for fact_id in staged:
        fact = fact_map[fact_id]
        if fact.path is None or fact.participant_id.startswith("storage:"):
            continue
        key = (fact.path, fact.family, fact.name)
        expected[key] = expected.get(key, 0) + edge_quantities.get(
            fact_id, fact.quantity
        )
    expected = {key: value for key, value in expected.items() if value}

    one_per_path = {}
    for item in staged_images:
        existing = one_per_path.get(item.plan.canonical_path)
        if existing is not None:
            for field in _RESOURCE_FIELDS:
                if existing.plan.post_image.get(field) != item.plan.post_image.get(
                    field
                ):
                    raise ResourceTransactionPlanningError(
                        "staged participant has conflicting resource finals"
                    )
            continue
        one_per_path[item.plan.canonical_path] = item
    actual = {}
    for item in one_per_path.values():
        for fact in _character_facts((item,)):
            key = (fact.path, fact.family, fact.name)
            actual[key] = actual.get(key, 0) + fact.quantity
    actual = {key: value for key, value in actual.items() if value}
    if actual != expected:
        raise ResourceTransactionPlanningError(
            "staged resource finals do not match code-owned ledger arithmetic"
        )

    original_paths = {item.plan.canonical_path for item in prepared}
    if set(one_per_path) != original_paths:
        raise ResourceTransactionPlanningError(
            "staged resource participants changed during planning"
        )

    from core.managers.character_transfer import (
        _batch_transfer_shape_mismatch,
        _candidate_components,
        _validate_transfer_component,
    )

    shape_mismatch = _batch_transfer_shape_mismatch(staged_images)
    if shape_mismatch:
        raise ResourceTransactionPlanningError(shape_mismatch)
    by_index = {item.index: item for item in staged_images}
    for component_indices in _candidate_components(staged_images):
        component = tuple(by_index[index] for index in component_indices)
        component_paths = {item.plan.canonical_path for item in component}
        mismatch = _validate_transfer_component(
            component,
            accepted_noncharacter_deltas=tuple(
                value
                for value in non_character_deltas
                if value[0] in component_paths
            ),
        )
        if mismatch:
            raise ResourceTransactionPlanningError(mismatch)

    edge_members = {
        fact_id
        for source_id, destination_id, _authority in edges.values()
        for fact_id in (source_id, destination_id)
    }
    for fact_id in staged:
        fact = fact_map[fact_id]
        if fact.participant_id.startswith("storage:"):
            continue
        opposite = "out" if fact.direction == "in" else "in"
        has_counterpart = any(
            other.fact_id != fact_id
            and other.participant_id != fact.participant_id
            and other.family == fact.family
            and other.name == fact.name
            and other.direction == opposite
            for other in effective_facts
        )
        if has_counterpart and fact_id not in edge_members:
            raise ResourceTransactionPlanningError(
                "planner omitted a complementary resource-transfer edge"
            )


def _effective_edge_fact_map(facts: Sequence[ResourceFact], edges):
    """Apply only T105-classified canonical source identity to receivers."""
    fact_map = {fact.fact_id: fact for fact in facts}
    effective = dict(fact_map)
    for source_id, destination_id, _authority in edges.values():
        source = fact_map[source_id]
        destination = fact_map[destination_id]
        if source.family not in {"equipment", "ammunition"}:
            continue
        if not isinstance(source.row, Mapping):
            raise ResourceTransactionPlanningError(
                "planned transfer source has no canonical row"
            )
        effective[destination_id] = replace(
            destination,
            name=source.name,
            row=copy.deepcopy(source.row),
            canonical_edge=True,
        )
    return effective


def _non_character_edge_deltas(
    facts: Sequence[ResourceFact],
    edges,
) -> Tuple[Tuple[str, str, str, int], ...]:
    """Project character deltas paired to storage/external graph participants."""
    fact_map = _effective_edge_fact_map(facts, edges)
    result = []
    for source_id, destination_id, authority in edges.values():
        source = fact_map[source_id]
        destination = fact_map[destination_id]
        participants = (source.participant_id, destination.participant_id)
        character_position = next(
            (
                index
                for index, participant in enumerate(participants)
                if participant.startswith("character:")
            ),
            None,
        )
        if character_position is None or all(
            participant.startswith("character:") for participant in participants
        ):
            continue
        character = source if character_position == 0 else destination
        amount = (
            abs(source.quantity) if authority == "source" else abs(destination.quantity)
        )
        result.append(
            (
                str(character.path),
                character.family,
                character.name,
                -amount if character.direction == "out" else amount,
            )
        )
    return tuple(sorted(result))


def plan_and_stage_resource_transaction(
    prepared: Sequence[PreparedCharacterAction],
    storage_plans: Sequence[StorageMutationPlan],
    *,
    provider: str,
    planner: Optional[Callable[..., Mapping[str, Any]]] = None,
) -> PlannedResourceTransaction:
    started = time.monotonic()
    prepared = tuple(prepared)
    storage_plans = tuple(storage_plans)
    decision = route_resource_transaction(
        prepared,
        storage_plans,
        provider=provider,
    )
    if not decision.requires_planning:
        _record_routing(
            decision, planner_calls=0, outcome="simple_complete", started=started
        )
        return PlannedResourceTransaction(
            prepared, storage_plans, decision, None, 0, (), ()
        )
    packet, facts = build_resource_transaction_packet(prepared, storage_plans)
    if planner is None:
        from core.ai.resource_transaction_planner import request_transaction_plan

        planner = request_transaction_plan

    failure = None
    failure_kind = "validation"
    for attempt in range(2):
        try:
            value = planner(
                packet,
                correction=failure if failure_kind == "validation" else None,
            )
            staged, _duplicates, edges = _validate_plan(value, facts)
            non_character_deltas = _non_character_edge_deltas(facts, edges)
            characters = _stage_character_images(prepared, facts, staged, edges)
            _reconcile_staged_images(
                prepared,
                characters,
                facts,
                staged,
                edges,
                non_character_deltas,
            )
            _record_routing(
                decision,
                planner_calls=attempt + 1,
                outcome="planned_complete",
                started=started,
            )
            return PlannedResourceTransaction(
                characters,
                storage_plans,
                decision,
                copy.deepcopy(value),
                attempt + 1,
                ("resource_transaction_planned",),
                non_character_deltas,
            )
        except Exception as exc:
            from core.ai.api_client import ProviderCallError

            if isinstance(exc, ProviderCallError):
                failure = "planner provider call failed"
                failure_kind = "provider"
            else:
                failure = (
                    str(exc)
                    if isinstance(exc, ResourceTransactionPlanningError)
                    else "previous planner response failed deterministic validation"
                )
                failure_kind = "validation"
            if attempt:
                _record_routing(
                    decision,
                    planner_calls=2,
                    outcome=(
                        "planner_provider_failed_closed"
                        if failure_kind == "provider"
                        else "planning_failed_closed"
                    ),
                    started=started,
                )
                error_type = (
                    ResourceTransactionProviderError
                    if failure_kind == "provider"
                    else ResourceTransactionPlanningError
                )
                if failure_kind == "provider":
                    message = "bounded transaction planner provider call failed safely"
                else:
                    message = (
                        "bounded transaction planning failed safely: %s" % failure
                    )
                raise error_type(message) from exc
    raise ResourceTransactionPlanningError("transaction planning did not complete")


def _record_routing(decision, *, planner_calls: int, outcome: str, started: float):
    from core.managers.resource_transaction_diagnostics import record_resource_routing

    record_resource_routing(
        provider=decision.provider,
        model_family=decision.model_family,
        route="complex_t105" if decision.requires_planning else "simple_deterministic",
        score=decision.score,
        threshold=decision.threshold,
        participant_count=decision.inputs.get("participant_count", 0),
        asset_family_count=decision.inputs.get("asset_family_count", 0),
        fact_count=decision.inputs.get("fact_count", 0),
        planner_calls=planner_calls,
        outcome=outcome,
        elapsed_ms=(time.monotonic() - started) * 1000,
    )
