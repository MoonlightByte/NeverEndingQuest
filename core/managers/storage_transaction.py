# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Crash-safe item and resource storage mutation adapter.

T049 and T053 finish before this adapter acquires final participant leases.
The coordinator then atomically commits the exact character/storage images or
leaves both unchanged/recoverable. Currency and ammunition use typed fields;
they are never disguised as equipment rows.
"""

from __future__ import annotations

import copy
import os
import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import jsonschema

from core.validation.character_validator import AICharacterValidator
from utils.encoding_utils import safe_json_load
from utils.module_path_manager import ModulePathManager
from utils.inventory_integrity import (
    consolidate_equipment_rows,
    inventory_metadata,
    is_stackable_equipment,
    normalize_inventory_name,
)
from utils.state_transaction import (
    ParticipantKind,
    StateTransactionCoordinator,
    TransactionStalePlanError,
)


class StorageTransactionError(RuntimeError):
    """A storage operation cannot be completed without guessing."""


@dataclass(frozen=True)
class StorageMutationPlan:
    operation: Mapping[str, Any]
    character_path: Optional[str]
    character_before: Optional[Dict[str, Any]]
    character_after: Optional[Dict[str, Any]]
    storage_path: str
    storage_existed: bool
    storage_before: Optional[Dict[str, Any]]
    storage_after: Dict[str, Any]
    message: str
    advisories: Tuple[str, ...] = ()


def _normalized_name(value: Any) -> str:
    return normalize_inventory_name(value)


def _strict_quantity(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StorageTransactionError(f"{label} must be a positive integer")
    return value


def _metadata(row: Mapping[str, Any]) -> str:
    # ``stackable`` records proven split-stack provenance.  It controls whether
    # identical rows may merge, but it is not part of the item's mechanical
    # identity (a ration does not become a different ration after a split).
    value = copy.deepcopy(dict(row))
    value.pop("stackable", None)
    return inventory_metadata(value, "item_name", omit_ownership_local=True)


def _is_stackable(row: Mapping[str, Any]) -> bool:
    return is_stackable_equipment(row)


def _inventory_rows(owner: Mapping[str, Any], label: str) -> list:
    rows = owner.get("equipment") if label == "character" else owner.get("contents")
    if rows is None:
        rows = []
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise StorageTransactionError(f"{label} inventory is malformed")
    return rows


def _unique_named_row(rows: Sequence[Mapping[str, Any]], name: str, label: str):
    normalized = _normalized_name(name)
    matches = [
        row for row in rows if _normalized_name(row.get("item_name")) == normalized
    ]
    if len(matches) > 1:
        raise StorageTransactionError(
            f"{label} contains ambiguous duplicate item names"
        )
    return matches[0] if matches else None


def _remove_item(rows: list, name: str, quantity: int, label: str) -> Dict[str, Any]:
    row = _unique_named_row(rows, name, label)
    if row is None:
        raise StorageTransactionError(f"{name} is not available in {label}")
    available = _strict_quantity(row.get("quantity", 1), f"{label} item quantity")
    if available < quantity:
        raise StorageTransactionError(
            f"{label} has {available} {name}, but {quantity} were requested"
        )
    source = copy.deepcopy(row)
    if available == quantity:
        rows.remove(row)
    else:
        if _is_stackable(row):
            # Both halves came from one row already proven fungible.  Preserve
            # that fact even when either half later has quantity one.
            source["stackable"] = True
            row["stackable"] = True
        row["quantity"] = available - quantity
    return source


def _add_item(rows: list, source: Mapping[str, Any], quantity: int, label: str) -> None:
    name = source.get("item_name")
    if not isinstance(name, str) or not name.strip():
        raise StorageTransactionError("an item is missing its name")
    existing = _unique_named_row(rows, name, label)
    if existing is None:
        new_row = copy.deepcopy(dict(source))
        new_row["quantity"] = quantity
        new_row["equipped"] = False
        rows.append(new_row)
        return
    if _metadata(existing) != _metadata(source):
        raise StorageTransactionError(
            f"{label} has a different item named {name}; identity is ambiguous"
        )
    if not (_is_stackable(existing) and _is_stackable(source)):
        raise StorageTransactionError(f"the unique item {name} cannot be merged")
    existing["quantity"] = (
        _strict_quantity(existing.get("quantity", 1), f"{label} item quantity")
        + quantity
    )


def _requested_items(operation: Mapping[str, Any]) -> Tuple[Tuple[str, int], ...]:
    raw = operation.get("items")
    if raw is None:
        raw = [
            {
                "item_name": operation.get("item_name"),
                "quantity": operation.get("quantity"),
            }
        ]
    if not isinstance(raw, list) or not raw:
        raise StorageTransactionError("storage operation has no items")
    requested = []
    seen = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise StorageTransactionError("storage item request is malformed")
        name = item.get("item_name")
        if not isinstance(name, str) or not name.strip():
            raise StorageTransactionError("storage item request has no useful name")
        key = _normalized_name(name)
        if key in seen:
            raise StorageTransactionError("storage item request repeats an item name")
        seen.add(key)
        requested.append(
            (name, _strict_quantity(item.get("quantity"), f"items[{index}]"))
        )
    return tuple(requested)


_DENOMINATIONS = ("gold", "silver", "copper")


def _currency(owner: Dict[str, Any], label: str) -> Dict[str, int]:
    raw = owner.get("currency")
    if raw is None and label == "storage":
        raw = {}
    if not isinstance(raw, dict):
        raise StorageTransactionError(f"{label} currency is malformed")
    normalized = {}
    for denomination in _DENOMINATIONS:
        value = raw.get(denomination, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StorageTransactionError(f"{label} currency is malformed")
        normalized[denomination] = value
    owner["currency"] = normalized
    return normalized


def _ammunition(owner: Dict[str, Any], label: str) -> list:
    raw = owner.get("ammunition")
    if raw is None:
        raw = []
    if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
        raise StorageTransactionError(f"{label} ammunition is malformed")
    for row in raw:
        name = row.get("name")
        quantity = row.get("quantity")
        description = row.get("description")
        if (
            not isinstance(name, str)
            or not name.strip()
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity < 1
            or not isinstance(description, str)
        ):
            raise StorageTransactionError(f"{label} ammunition is malformed")
    owner["ammunition"] = raw
    return raw


def _ammunition_counts(owner: Dict[str, Any], label: str, normalized_name: str):
    counts = {}
    for row in _ammunition(owner, label):
        if _normalized_name(row.get("name")) != normalized_name:
            continue
        key = (normalized_name, row.get("description"))
        counts[key] = counts.get(key, 0) + row["quantity"]
    return counts


def _unique_ammunition(rows: Sequence[Mapping[str, Any]], name: str, label: str):
    normalized = _normalized_name(name)
    matches = [row for row in rows if _normalized_name(row.get("name")) == normalized]
    if len(matches) > 1:
        raise StorageTransactionError(f"{label} has ambiguous duplicate ammunition")
    return matches[0] if matches else None


def _remove_ammunition(rows: list, name: str, quantity: int, label: str):
    row = _unique_ammunition(rows, name, label)
    if row is None:
        raise StorageTransactionError(f"{name} is not available in {label}")
    available = _strict_quantity(row.get("quantity"), f"{label} ammunition quantity")
    if available < quantity:
        raise StorageTransactionError(
            f"{label} only has {available} {row.get('name')}, but {quantity} were requested"
        )
    source = copy.deepcopy(row)
    if available == quantity:
        rows.remove(row)
    else:
        row["quantity"] = available - quantity
    return source


def _add_ammunition(rows: list, source: Mapping[str, Any], quantity: int, label: str):
    name = source.get("name")
    existing = _unique_ammunition(rows, str(name or ""), label)
    if existing is None:
        row = copy.deepcopy(dict(source))
        row["quantity"] = quantity
        rows.append(row)
        return
    if existing.get("description") != source.get("description"):
        raise StorageTransactionError(
            f"{label} has different ammunition named {name}; identity is ambiguous"
        )
    existing["quantity"] = _strict_quantity(
        existing.get("quantity"), f"{label} ammunition quantity"
    ) + quantity


def _load_storage(path: str) -> Tuple[bool, Dict[str, Any]]:
    if not os.path.exists(path):
        return False, {"version": "1.0.0", "lastUpdated": "", "playerStorage": []}
    value = safe_json_load(path)
    if not isinstance(value, dict) or not isinstance(value.get("playerStorage"), list):
        raise StorageTransactionError("player storage file is malformed")
    return True, value


def _location() -> Tuple[str, str, str, str]:
    party = safe_json_load("party_tracker.json")
    if not isinstance(party, dict):
        raise StorageTransactionError("party location is unavailable")
    world = party.get("worldConditions") or {}
    location_id = world.get("currentLocationId")
    if not isinstance(location_id, str) or not location_id.strip():
        raise StorageTransactionError("current location identity is unavailable")
    return (
        location_id,
        str(world.get("currentLocation") or "Unknown Location"),
        str(world.get("currentAreaId") or "UNKNOWN"),
        str(world.get("currentArea") or "Unknown Area"),
    )


def _find_container(storage: Mapping[str, Any], storage_id: str, location_id: str):
    matches = [
        item
        for item in storage.get("playerStorage", [])
        if isinstance(item, dict) and item.get("id") == storage_id
    ]
    if len(matches) != 1:
        raise StorageTransactionError(
            "storage container identity is missing or ambiguous"
        )
    container = matches[0]
    if container.get("locationId") != location_id:
        raise StorageTransactionError(
            "storage container is not at the current location"
        )
    _inventory_rows(container, "storage")
    return container


def _new_container(operation: Mapping[str, Any], location, timestamp: str):
    location_id, location_name, area_id, area_name = location
    storage_type = operation.get("storage_type") or "chest"
    storage_id = f"storage_{uuid.uuid4().hex[:8]}"
    return {
        "id": storage_id,
        "deviceType": storage_type,
        "deviceName": operation.get("storage_name")
        or f"{str(storage_type).title()} at {location_name}",
        "locationId": location_id,
        "locationName": location_name,
        "areaId": area_id,
        "areaName": area_name,
        "contents": [],
        "currency": {"gold": 0, "silver": 0, "copper": 0},
        "ammunition": [],
        "createdBy": operation["character"],
        "createdDate": timestamp,
        "accessibility": "party",
        "lastAccessed": timestamp,
        "accessLog": [
            {
                "character": operation["character"],
                "action": "create",
                "timestamp": timestamp,
            }
        ],
    }


def _validate_operation(operation: Mapping[str, Any]) -> None:
    schema = safe_json_load("schemas/storage_action_schema.json")
    if not isinstance(schema, dict):
        raise StorageTransactionError("storage action schema is unavailable")
    try:
        jsonschema.validate(dict(operation), schema)
    except jsonschema.ValidationError as exc:
        raise StorageTransactionError(
            f"storage action is invalid: {exc.message}"
        ) from exc
    if operation.get("action") not in {
        "create_storage",
        "store_item",
        "retrieve_item",
        "store_currency",
        "retrieve_currency",
        "store_ammunition",
        "retrieve_ammunition",
    }:
        raise StorageTransactionError("operation is not a mutating storage action")


def _character_path(character: str) -> str:
    party = safe_json_load("party_tracker.json") or {}
    module = str(party.get("module") or "").replace(" ", "_") or None
    path = ModulePathManager(module).get_character_path(character)
    return os.path.normcase(os.path.realpath(path))


def _validate_character_candidate(candidate: Dict[str, Any]):
    validator = AICharacterValidator()
    result = validator.validate_and_correct_character_with_result(candidate)
    advisories = []
    if not result.success:
        advisories.append("character_validator_failed_open")
    if not isinstance(result.data, dict):
        raise StorageTransactionError("character validator returned invalid data")
    return copy.deepcopy(result.data), tuple(advisories)


def _asset_counts(character, container, names):
    counts = {}
    for label, rows in (
        ("character", _inventory_rows(character, "character")),
        ("storage", _inventory_rows(container, "storage")),
    ):
        del label
        for row in rows:
            name = _normalized_name(row.get("item_name"))
            if name not in names:
                continue
            quantity = _strict_quantity(
                row.get("quantity", 1), "conserved item quantity"
            )
            key = (name, _metadata(row))
            counts[key] = counts.get(key, 0) + quantity
    return counts


def prepare_storage_mutation(operation: Mapping[str, Any]) -> StorageMutationPlan:
    """Prepare exact participant images; perform no final state write."""
    operation = copy.deepcopy(dict(operation))
    _validate_operation(operation)
    action = operation["action"]
    timestamp = datetime.now().isoformat()
    location = _location()
    location_id = location[0]
    storage_path = os.path.normcase(os.path.realpath("player_storage.json"))
    storage_existed, loaded_storage = _load_storage(storage_path)
    storage_before = copy.deepcopy(loaded_storage) if storage_existed else None
    storage_after = copy.deepcopy(loaded_storage)

    if action == "create_storage":
        container = _new_container(operation, location, timestamp)
        storage_after["playerStorage"].append(container)
        storage_after["lastUpdated"] = timestamp
        return StorageMutationPlan(
            operation,
            None,
            None,
            None,
            storage_path,
            storage_existed,
            storage_before,
            storage_after,
            f"Created {container['deviceType']} at {container['locationName']}",
        )

    character_path = _character_path(operation["character"])
    character_before = safe_json_load(character_path)
    if not isinstance(character_before, dict):
        raise StorageTransactionError("character inventory is unavailable")
    character_after = copy.deepcopy(character_before)

    storage_id = operation.get("storage_id")
    if storage_id:
        container = _find_container(storage_after, storage_id, location_id)
    elif action in {"store_item", "store_currency", "store_ammunition"}:
        container = _new_container(operation, location, timestamp)
        storage_after["playerStorage"].append(container)
    else:
        raise StorageTransactionError("retrieval requires a storage container")

    container_before = copy.deepcopy(container)
    identity_advisories = ()
    conserved_before = None
    if action in {"store_item", "retrieve_item"}:
        character_rows = _inventory_rows(character_after, "character")
        storage_rows = _inventory_rows(container, "storage")
        character_rows, character_identity_advisories = consolidate_equipment_rows(
            character_rows
        )
        storage_rows, storage_identity_advisories = consolidate_equipment_rows(
            storage_rows
        )
        character_after["equipment"] = character_rows
        container["contents"] = storage_rows
        identity_advisories = tuple(
            sorted(set(character_identity_advisories + storage_identity_advisories))
        )
        requested = _requested_items(operation)
        names = {_normalized_name(name) for name, _quantity in requested}
        conserved_before = ("items", _asset_counts(character_before, container_before, names))
        if action == "store_item":
            for name, quantity in requested:
                source = _remove_item(character_rows, name, quantity, "character")
                _add_item(storage_rows, source, quantity, "storage")
            verb = "Stored"
            log_action = "store_items" if len(requested) > 1 else "store_item"
        else:
            for name, quantity in requested:
                source = _remove_item(storage_rows, name, quantity, "storage")
                _add_item(character_rows, source, quantity, "character")
            verb = "Retrieved"
            log_action = "retrieve_items" if len(requested) > 1 else "retrieve_item"
        detail = [{"item": name, "quantity": quantity} for name, quantity in requested]
        item_text = ", ".join(f"{quantity} {name}" for name, quantity in requested)
    elif action in {"store_currency", "retrieve_currency"}:
        denomination = operation.get("denomination")
        if denomination not in _DENOMINATIONS:
            raise StorageTransactionError("currency denomination is invalid")
        quantity = _strict_quantity(operation.get("quantity"), "currency quantity")
        character_currency = _currency(character_after, "character")
        storage_currency = _currency(container, "storage")
        conserved_before = (
            "currency",
            {
                name: _currency(copy.deepcopy(character_before), "character")[name]
                + _currency(copy.deepcopy(container_before), "storage")[name]
                for name in _DENOMINATIONS
            },
        )
        source, destination = (
            (character_currency, storage_currency)
            if action == "store_currency"
            else (storage_currency, character_currency)
        )
        if source[denomination] < quantity:
            label = "character" if action == "store_currency" else "storage"
            raise StorageTransactionError(
                f"{label} only has {source[denomination]} {denomination}, but {quantity} were requested"
            )
        source[denomination] -= quantity
        destination[denomination] += quantity
        verb = "Stored" if action == "store_currency" else "Retrieved"
        log_action = action
        detail = {"denomination": denomination, "quantity": quantity}
        item_text = f"{quantity} {denomination}"
    else:
        name = operation.get("ammunition_name")
        if not isinstance(name, str) or not name.strip():
            raise StorageTransactionError("ammunition request has no useful name")
        quantity = _strict_quantity(operation.get("quantity"), "ammunition quantity")
        character_ammunition = _ammunition(character_after, "character")
        storage_ammunition = _ammunition(container, "storage")
        conserved_name = _normalized_name(name)
        ammunition_before = {}
        for counts in (
            _ammunition_counts(
                copy.deepcopy(character_before), "character", conserved_name
            ),
            _ammunition_counts(
                copy.deepcopy(container_before), "storage", conserved_name
            ),
        ):
            for key, count_quantity in counts.items():
                ammunition_before[key] = (
                    ammunition_before.get(key, 0) + count_quantity
                )
        conserved_before = ("ammunition", ammunition_before)
        source_rows, destination_rows = (
            (character_ammunition, storage_ammunition)
            if action == "store_ammunition"
            else (storage_ammunition, character_ammunition)
        )
        source = _remove_ammunition(source_rows, name, quantity, "character" if action == "store_ammunition" else "storage")
        _add_ammunition(destination_rows, source, quantity, "storage" if action == "store_ammunition" else "character")
        verb = "Stored" if action == "store_ammunition" else "Retrieved"
        log_action = action
        detail = {"ammunition": source.get("name"), "quantity": quantity}
        item_text = f"{quantity} {source.get('name')}"

    character_after, validator_advisories = _validate_character_candidate(
        character_after
    )
    advisories = tuple(sorted(set(identity_advisories + validator_advisories)))
    if conserved_before[0] == "items":
        conserved_after = _asset_counts(character_after, container, names)
    elif conserved_before[0] == "currency":
        conserved_after = {
            name: _currency(copy.deepcopy(character_after), "character")[name]
            + _currency(copy.deepcopy(container), "storage")[name]
            for name in _DENOMINATIONS
        }
    else:
        conserved_after = {}
        for counts in (
            _ammunition_counts(
                copy.deepcopy(character_after), "character", conserved_name
            ),
            _ammunition_counts(copy.deepcopy(container), "storage", conserved_name),
        ):
            for key, count_quantity in counts.items():
                conserved_after[key] = conserved_after.get(key, 0) + count_quantity
    if conserved_before[1] != conserved_after:
        raise StorageTransactionError("storage resource identity or quantity was not conserved")

    container["lastAccessed"] = timestamp
    container.setdefault("accessLog", []).append(
        {
            "character": operation["character"],
            "action": log_action,
            "items" if isinstance(detail, list) else "resource": detail,
            "timestamp": timestamp,
        }
    )
    storage_after["lastUpdated"] = timestamp
    preposition = "in" if action.startswith("store_") else "from"
    message = f"{verb} {item_text} {preposition} {container['deviceName']}"
    return StorageMutationPlan(
        operation,
        character_path,
        copy.deepcopy(character_before),
        character_after,
        storage_path,
        storage_existed,
        storage_before,
        storage_after,
        message,
        advisories,
    )


def execute_storage_plan(plan: StorageMutationPlan):
    coordinator = StateTransactionCoordinator(workspace_root=".")
    participants = []
    if plan.character_path:
        participants.append(
            coordinator.participant(
                plan.character_path,
                ParticipantKind.CHARACTER,
                coordinator.snapshot(plan.character_before),
                coordinator.snapshot(plan.character_after),
            )
        )
    storage_before = (
        coordinator.snapshot(plan.storage_before)
        if plan.storage_existed
        else coordinator.snapshot(exists=False)
    )
    participants.append(
        coordinator.participant(
            plan.storage_path,
            ParticipantKind.STORAGE,
            storage_before,
            coordinator.snapshot(plan.storage_after),
        )
    )
    identity = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "|".join(
            f"{item.canonical_path}:{item.pre_hash}:{item.post_hash}"
            for item in participants
        ),
    ).hex
    transaction = coordinator.build_plan(
        transaction_key=f"storage-{identity}",
        operation=f"storage_{plan.operation['action']}",
        participants=participants,
        rollback_failure_code="storage_rolled_back",
    )
    return coordinator.execute(transaction, timeout_seconds=30.0)


def execute_item_storage_operation(operation: Mapping[str, Any]) -> Dict[str, Any]:
    """Prepare, commit, and boundedly re-prepare once on a stale snapshot."""
    try:
        for attempt in range(2):
            plan = prepare_storage_mutation(operation)
            try:
                execute_storage_plan(plan)
                return {
                    "success": True,
                    "message": plan.message,
                    "advisories": list(plan.advisories),
                }
            except TransactionStalePlanError:
                if attempt == 0:
                    continue
                raise
    except Exception as exc:
        return {
            "success": False,
            "error": "Storage changed before the item transfer could be verified.",
            "failure_code": "storage_transfer_unverified",
            "diagnostic": str(exc),
        }
    return {"success": False, "error": "Storage transfer did not complete."}


def _currency_copper(sheet: Mapping[str, Any]) -> int:
    currency = sheet.get("currency") or {}
    if not isinstance(currency, dict):
        raise StorageTransactionError("character currency is malformed")
    total = 0
    for denomination, multiplier in (("gold", 100), ("silver", 10), ("copper", 1)):
        value = currency.get(denomination, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StorageTransactionError("character currency is malformed")
        total += value * multiplier
    return total


def _changed_top_level(before: Mapping[str, Any], after: Mapping[str, Any]):
    return {
        key for key in set(before) | set(after) if before.get(key) != after.get(key)
    }


def _combine_storage_fee(storage_plan, fee_action):
    """Combine an actual currency-only decrease with one storage mutation."""
    fee = fee_action.plan
    if _changed_top_level(fee.pre_image, fee.post_image) - {"currency"}:
        return None
    if _currency_copper(fee.post_image) >= _currency_copper(fee.pre_image):
        return None
    if storage_plan.character_path is None:
        return replace(
            storage_plan,
            character_path=fee.canonical_path,
            character_before=copy.deepcopy(fee.pre_image),
            character_after=copy.deepcopy(fee.post_image),
        )
    if storage_plan.character_path != fee.canonical_path:
        return None
    if storage_plan.character_before != fee.pre_image:
        return None
    combined_character = copy.deepcopy(storage_plan.character_after)
    if storage_plan.character_after.get("currency") == storage_plan.character_before.get(
        "currency"
    ):
        combined_character["currency"] = copy.deepcopy(
            fee.post_image.get("currency", {})
        )
    elif storage_plan.operation.get("action") in {
        "store_currency",
        "retrieve_currency",
    }:
        combined_currency = _currency(combined_character, "character")
        fee_before = _currency(copy.deepcopy(fee.pre_image), "character")
        fee_after = _currency(copy.deepcopy(fee.post_image), "character")
        for denomination in _DENOMINATIONS:
            combined_currency[denomination] += (
                fee_after[denomination] - fee_before[denomination]
            )
            if combined_currency[denomination] < 0:
                return None
    else:
        return None
    return replace(storage_plan, character_after=combined_character)


def _prepare_response_storage_action(
    indexed_action,
    party_tracker_data,
    *,
    fallback_character,
):
    index, action = indexed_action
    parameters = action.get("parameters") or {}
    description = parameters.get("description")
    if not isinstance(description, str) or not description.strip():
        raise StorageTransactionError("storage interaction has no useful description")
    character = parameters.get("characterName") or fallback_character
    if not character:
        character = next(iter(party_tracker_data.get("partyMembers") or []), None)
    if not character:
        raise StorageTransactionError("storage interaction has no character")
    from core.managers.storage_processor import process_storage_request

    processed = process_storage_request(description, str(character))
    if not processed.get("success"):
        raise StorageTransactionError(
            processed.get("error") or "storage operation preparation failed"
        )
    operation = processed.get("operation")
    if not isinstance(operation, dict):
        raise StorageTransactionError("storage processor returned no operation")
    if operation.get("action") == "view_storage":
        return index, operation, None
    return index, operation, prepare_storage_mutation(operation)


def process_adjacent_storage_fee_groups(
    prepared_character_actions,
    indexed_storage_actions,
    party_tracker_data,
):
    """Atomically group only adjacent, same-character, concrete fee decreases."""
    from core.managers.character_transfer import (
        _candidate_components,
        prepare_character_actions,
    )

    prepared_character_actions = tuple(prepared_character_actions)
    indexed_storage_actions = tuple(indexed_storage_actions)
    transfer_claimed = {
        index
        for component in _candidate_components(prepared_character_actions)
        for index in component
    }
    eligible = [
        item
        for item in prepared_character_actions
        if item.index not in transfer_claimed
        if _changed_top_level(item.plan.pre_image, item.plan.post_image) <= {"currency"}
        and _currency_copper(item.plan.post_image)
        < _currency_copper(item.plan.pre_image)
    ]
    handled_characters = set()
    handled_storage = set()
    messages = []
    storage_indices = {index for index, _action in indexed_storage_actions}
    unambiguous_fee_indices = {
        item.index
        for item in eligible
        if sum(abs(item.index - index) == 1 for index in storage_indices) == 1
    }
    try:
        for indexed_storage in sorted(
            indexed_storage_actions, key=lambda value: value[0]
        ):
            storage_index = indexed_storage[0]
            adjacent = [
                item
                for item in eligible
                if item.index not in handled_characters
                and item.index in unambiguous_fee_indices
                and abs(item.index - storage_index) == 1
            ]
            if len(adjacent) != 1:
                continue
            fee_action = adjacent[0]
            _index, _operation, storage_plan = _prepare_response_storage_action(
                indexed_storage,
                party_tracker_data,
                fallback_character=fee_action.plan.character_name,
            )
            if storage_plan is None:
                continue
            combined = _combine_storage_fee(storage_plan, fee_action)
            if combined is None:
                continue
            try:
                execute_storage_plan(combined)
            except TransactionStalePlanError:
                refreshed_fee = prepare_character_actions(
                    ((fee_action.index, fee_action.action),),
                    party_tracker_data,
                )[0]
                _index, _operation, refreshed_storage = (
                    _prepare_response_storage_action(
                        indexed_storage,
                        party_tracker_data,
                        fallback_character=refreshed_fee.plan.character_name,
                    )
                )
                if refreshed_storage is None:
                    raise StorageTransactionError(
                        "storage fee operation became read-only"
                    )
                combined = _combine_storage_fee(refreshed_storage, refreshed_fee)
                if combined is None:
                    raise StorageTransactionError(
                        "storage fee no longer has one unambiguous participant"
                    )
                execute_storage_plan(combined)
            handled_characters.add(fee_action.index)
            handled_storage.add(storage_index)
            messages.append(combined.message)
        return {
            "success": True,
            "remaining_character_actions": tuple(
                item
                for item in prepared_character_actions
                if item.index not in handled_characters
            ),
            "handled_storage_indices": frozenset(handled_storage),
            "messages": tuple(messages),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": "Storage fee and item movement could not be committed together.",
            "failure_code": "storage_fee_unverified",
            "diagnostic": str(exc),
        }
