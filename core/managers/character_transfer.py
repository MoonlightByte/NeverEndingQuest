# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Atomic adapter for concrete character-to-character transfer deltas."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from core.managers.effects_runtime import prepare_character_with_effects
from updates.update_character_info import (
    CharacterMutationPlan,
    execute_character_mutation_plans,
)


_DENOMINATIONS = {"gold": 100, "silver": 10, "copper": 1}
_OWNERSHIP_LOCAL_FIELDS = {"equipped"}


class CharacterTransferError(RuntimeError):
    """A character batch could not be applied without guessing."""


@dataclass(frozen=True)
class PreparedCharacterAction:
    index: int
    action: Mapping[str, Any]
    changes: str
    plan: CharacterMutationPlan


@dataclass(frozen=True)
class AssetDelta:
    family: str
    name: str
    quantity: int
    metadata: str

    @property
    def lookup_key(self) -> Tuple[str, str]:
        return self.family, self.name


def _normalized_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _strict_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CharacterTransferError(f"{label} must be a nonnegative integer")
    return value


def _currency_value(sheet: Mapping[str, Any]) -> int:
    currency = sheet.get("currency") or {}
    if not isinstance(currency, dict):
        raise CharacterTransferError("currency must be an object")
    total = 0
    for denomination, multiplier in _DENOMINATIONS.items():
        total += (
            _strict_nonnegative_int(
                currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            * multiplier
        )
    return total


def _rows_by_name(
    sheet: Mapping[str, Any],
    field: str,
    name_field: str,
) -> Dict[str, Mapping[str, Any]]:
    rows = sheet.get(field) or []
    if not isinstance(rows, list):
        raise CharacterTransferError(f"{field} must be an array")
    indexed: Dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise CharacterTransferError(f"{field} contains a non-object row")
        name = _normalized_name(row.get(name_field))
        if not name:
            raise CharacterTransferError(f"{field} contains an unnamed row")
        if name in indexed:
            raise CharacterTransferError(f"{field} contains ambiguous duplicate names")
        _strict_nonnegative_int(row.get("quantity", 1), f"{field}.{name}.quantity")
        indexed[name] = row
    return indexed


def _mechanical_metadata(row: Mapping[str, Any], name_field: str) -> str:
    metadata = copy.deepcopy(dict(row))
    metadata.pop("quantity", None)
    for field in _OWNERSHIP_LOCAL_FIELDS:
        metadata.pop(field, None)
    metadata[name_field] = _normalized_name(metadata.get(name_field))
    return json.dumps(
        metadata,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _row_deltas(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    family: str,
    field: str,
    name_field: str,
) -> List[AssetDelta]:
    old = _rows_by_name(before, field, name_field)
    new = _rows_by_name(after, field, name_field)
    deltas = []
    for name in sorted(set(old) | set(new)):
        old_row = old.get(name)
        new_row = new.get(name)
        old_quantity = int(old_row.get("quantity", 1)) if old_row else 0
        new_quantity = int(new_row.get("quantity", 1)) if new_row else 0
        quantity = new_quantity - old_quantity
        if not quantity:
            continue
        identity_row = old_row if quantity < 0 else new_row
        deltas.append(
            AssetDelta(
                family=family,
                name=name,
                quantity=quantity,
                metadata=_mechanical_metadata(identity_row, name_field),
            )
        )
    return deltas


def concrete_asset_deltas(plan: CharacterMutationPlan) -> Tuple[AssetDelta, ...]:
    """Project only final concrete transfer-relevant before/after facts."""
    deltas: List[AssetDelta] = []
    currency_delta = _currency_value(plan.post_image) - _currency_value(plan.pre_image)
    if currency_delta:
        deltas.append(AssetDelta("currency", "currency", currency_delta, "currency"))
    deltas.extend(
        _row_deltas(
            plan.pre_image,
            plan.post_image,
            family="equipment",
            field="equipment",
            name_field="item_name",
        )
    )
    deltas.extend(
        _row_deltas(
            plan.pre_image,
            plan.post_image,
            family="ammunition",
            field="ammunition",
            name_field="name",
        )
    )
    return tuple(deltas)


def _candidate_components(
    prepared: Sequence[PreparedCharacterAction],
) -> Tuple[Tuple[int, ...], ...]:
    deltas = {item.index: concrete_asset_deltas(item.plan) for item in prepared}
    edges = {item.index: set() for item in prepared}
    by_lookup: Dict[Tuple[str, str], List[Tuple[int, AssetDelta]]] = {}
    for index, values in deltas.items():
        for delta in values:
            by_lookup.setdefault(delta.lookup_key, []).append((index, delta))
    for values in by_lookup.values():
        negative = {index for index, delta in values if delta.quantity < 0}
        positive = {index for index, delta in values if delta.quantity > 0}
        for left in negative:
            for right in positive:
                if left != right:
                    edges[left].add(right)
                    edges[right].add(left)

    components = []
    remaining = set(edges)
    while remaining:
        start = min(remaining)
        stack = [start]
        component = set()
        while stack:
            index = stack.pop()
            if index in component:
                continue
            component.add(index)
            stack.extend(edges[index] - component)
        remaining -= component
        if len(component) >= 2 and any(edges[index] for index in component):
            components.append(tuple(sorted(component)))
    return tuple(sorted(components, key=lambda value: value[0]))


def _validate_transfer_component(
    component: Sequence[PreparedCharacterAction],
) -> Optional[str]:
    paths = [item.plan.canonical_path for item in component]
    if len(paths) != len(set(paths)):
        return "a transfer resolves more than once to the same character"

    grouped: Dict[Tuple[str, str], List[AssetDelta]] = {}
    for item in component:
        for delta in concrete_asset_deltas(item.plan):
            grouped.setdefault(delta.lookup_key, []).append(delta)
    transfer_keys = {
        key
        for key, values in grouped.items()
        if any(value.quantity < 0 for value in values)
        and any(value.quantity > 0 for value in values)
    }
    if not transfer_keys:
        return "no complementary transfer facts remain"
    for key in sorted(transfer_keys):
        values = grouped[key]
        if sum(value.quantity for value in values) != 0:
            return f"{key[0]} {key[1]} is not conserved"
        if key[0] != "currency":
            outgoing = {value.metadata for value in values if value.quantity < 0}
            incoming = {value.metadata for value in values if value.quantity > 0}
            if outgoing != incoming or len(outgoing) != 1:
                return f"{key[0]} {key[1]} has ambiguous mechanical identity"
    return None


def _action_changes(action: Mapping[str, Any]) -> str:
    parameters = action.get("parameters") or {}
    changes = parameters.get("changes")
    if not changes or not isinstance(changes, (str, dict)):
        raise CharacterTransferError("updateCharacterInfo requires useful changes")
    return changes if isinstance(changes, str) else json.dumps(changes)


def _action_character(action: Mapping[str, Any], party: Mapping[str, Any]) -> str:
    parameters = action.get("parameters") or {}
    name = parameters.get("characterName") or parameters.get("npcName")
    if not name:
        name = next(iter(party.get("partyMembers") or []), None)
    if not name:
        raise CharacterTransferError("updateCharacterInfo has no character")
    return str(name)


def _prepare_actions(
    indexed_actions: Sequence[Tuple[int, Mapping[str, Any]]],
    party: Mapping[str, Any],
    correction: Optional[str] = None,
) -> Tuple[PreparedCharacterAction, ...]:
    prepared = []
    for index, action in indexed_actions:
        changes = _action_changes(action)
        request = changes
        if correction:
            request = (
                f"{changes}\n\nJOINT TRANSFER CORRECTION (one final attempt): "
                f"{correction}. Return the exact final values needed so every "
                "transferred item, ammunition unit, and copper-equivalent coin "
                "removed from one named character is added to another. Preserve "
                "the item's complete mechanical metadata."
            )
        plan = prepare_character_with_effects(
            _action_character(action, party),
            request,
            party,
        )
        if not isinstance(plan, CharacterMutationPlan):
            raise CharacterTransferError(
                f"character update preparation failed at action {index}"
            )
        prepared.append(PreparedCharacterAction(index, action, changes, plan))
    return tuple(prepared)


def process_character_update_batch(
    indexed_actions: Sequence[Tuple[int, Mapping[str, Any]]],
    party_tracker_data: Mapping[str, Any],
) -> Dict[str, Any]:
    """Prepare original indexed actions and atomically commit transfer components."""
    try:
        prepared = _prepare_actions(indexed_actions, party_tracker_data)
        return commit_prepared_character_actions(prepared, party_tracker_data)
    except Exception as exc:
        return _character_batch_failure(exc)


def prepare_character_actions(
    indexed_actions: Sequence[Tuple[int, Mapping[str, Any]]],
    party_tracker_data: Mapping[str, Any],
) -> Tuple[PreparedCharacterAction, ...]:
    """Public preparation seam used by adjacent atomic adapters."""
    return _prepare_actions(indexed_actions, party_tracker_data)


def _character_batch_failure(exc: Exception) -> Dict[str, Any]:
    return {
        "status": "error",
        "success": False,
        "response_data": {
            "error_message": (
                "The character transfer or inventory update could not be "
                "verified, so no unsafe partial transfer was applied."
            ),
            "failure_code": "character_transfer_unverified",
        },
        "diagnostic": str(exc),
    }


def commit_prepared_character_actions(
    prepared: Sequence[PreparedCharacterAction],
    party_tracker_data: Mapping[str, Any],
) -> Dict[str, Any]:
    """Commit a previously prepared subset with the same A1 graph rules."""
    try:
        prepared = tuple(prepared)
        by_index = {item.index: item for item in prepared}
        components = _candidate_components(prepared)

        corrected_components = {}
        for indices in components:
            component = tuple(by_index[index] for index in indices)
            mismatch = _validate_transfer_component(component)
            if mismatch:
                corrected = _prepare_actions(
                    tuple((item.index, item.action) for item in component),
                    party_tracker_data,
                    correction=mismatch,
                )
                mismatch = _validate_transfer_component(corrected)
                if mismatch:
                    raise CharacterTransferError(
                        f"transfer correction failed safely: {mismatch}"
                    )
                corrected_components[indices] = corrected

        units = []
        claimed = set()
        for indices in components:
            component = corrected_components.get(
                indices,
                tuple(by_index[index] for index in indices),
            )
            units.append((min(indices), component, "character_transfer"))
            claimed.update(indices)
        for item in prepared:
            if item.index not in claimed:
                units.append((item.index, (item,), "character_update"))

        from utils.state_transaction import TransactionStalePlanError

        for _index, unit, operation in sorted(units, key=lambda value: value[0]):
            try:
                execute_character_mutation_plans(
                    tuple(item.plan for item in unit),
                    operation=operation,
                )
            except TransactionStalePlanError:
                # Leases are already released by the coordinator. Re-run all
                # model preparation once against the new snapshots, then
                # revalidate the concrete component before the final attempt.
                refreshed = _prepare_actions(
                    tuple((item.index, item.action) for item in unit),
                    party_tracker_data,
                )
                if operation == "character_transfer":
                    mismatch = _validate_transfer_component(refreshed)
                    if mismatch:
                        indices = tuple(sorted(item.index for item in unit))
                        if indices in corrected_components:
                            raise CharacterTransferError(
                                "stale transfer still violates conservation"
                            )
                        refreshed = _prepare_actions(
                            tuple((item.index, item.action) for item in unit),
                            party_tracker_data,
                            correction=mismatch,
                        )
                        if _validate_transfer_component(refreshed):
                            raise CharacterTransferError(
                                "stale transfer correction failed safely"
                            )
                execute_character_mutation_plans(
                    tuple(item.plan for item in refreshed),
                    operation=operation,
                )

        rest_kinds = {
            (
                "long_rest"
                if "long rest" in item.changes.casefold()
                else "short_rest" if "short rest" in item.changes.casefold() else None
            )
            for item in prepared
        }
        for rest_kind in sorted(value for value in rest_kinds if value):
            from core.managers.effects_runtime import process_effect_lifecycle

            process_effect_lifecycle(rest_kind=rest_kind)
        return {
            "status": "continue",
            "success": True,
            "needs_update": bool(prepared),
            "committed_indices": [item.index for item in prepared],
        }
    except Exception as exc:
        return _character_batch_failure(exc)
