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
from utils.enhanced_logger import warning


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


def _character_resource_signature(character: Mapping[str, Any]):
    equipment = _inventory_rows(character, "character")
    equipment_names = {
        _normalized_name(row.get("item_name")) for row in equipment
    }
    ammunition_rows = _ammunition(character, "character")
    ammunition_names = {
        _normalized_name(row.get("name") or row.get("item_name"))
        for row in ammunition_rows
    }
    ammunition = {}
    for name in ammunition_names:
        for key, quantity in _ammunition_counts(
            copy.deepcopy(dict(character)), "character", name
        ).items():
            ammunition[key] = ammunition.get(key, 0) + quantity
    return (
        _asset_counts(
            copy.deepcopy(dict(character)),
            {"contents": []},
            equipment_names,
        ),
        _currency(copy.deepcopy(dict(character)), "character"),
        ammunition,
    )


def _storage_owned_keys(operations: Sequence[Mapping[str, Any]]):
    """Return the concrete character-resource keys owned by this request."""
    equipment = set()
    currency = set()
    ammunition = set()
    for operation in operations:
        action = operation.get("action")
        if action in {"store_item", "retrieve_item"}:
            equipment.update(
                _normalized_name(name)
                for name, _quantity in _requested_items(operation)
            )
        elif action in {"store_currency", "retrieve_currency"}:
            currency.add(operation.get("denomination"))
        elif action in {"store_ammunition", "retrieve_ammunition"}:
            ammunition.add(_normalized_name(operation.get("ammunition_name")))
    return (
        frozenset(value for value in equipment if value),
        frozenset(value for value in currency if value in _DENOMINATIONS),
        frozenset(value for value in ammunition if value),
    )


def _group_resource_rows(
    character: Mapping[str, Any],
    field: str,
    name_field: str,
):
    rows = character.get(field) or []
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise StorageTransactionError(f"character {field} is malformed")
    grouped = {}
    for index, row in enumerate(rows):
        name = _normalized_name(row.get(name_field))
        if not name:
            # An unrelated legacy row may itself be what the validator repairs.
            # Keep it observable without making that old defect a prerequisite
            # for an otherwise safe storage operation.
            name = f"__unnamed_{index}"
        grouped.setdefault(name, []).append(copy.deepcopy(row))
    return grouped


def _storage_owned_projection(
    character: Mapping[str, Any],
    owned_keys,
):
    """Project exact post-image facts for only storage-owned resource keys."""
    equipment_names, denominations, ammunition_names = owned_keys
    equipment = _group_resource_rows(character, "equipment", "item_name")
    ammunition = _group_resource_rows(character, "ammunition", "name")
    raw_currency = character.get("currency") or {}
    if not isinstance(raw_currency, dict):
        raise StorageTransactionError("character currency is malformed")
    return (
        {
            name: equipment.get(name, [])
            for name in sorted(equipment_names)
        },
        {
            denomination: copy.deepcopy(raw_currency.get(denomination, 0))
            for denomination in sorted(denominations)
        },
        {
            name: ammunition.get(name, [])
            for name in sorted(ammunition_names)
        },
    )


def _storage_owned_delta_signature(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    owned_keys,
):
    """Prove validator merging is neutral to the already-conserved delta."""
    return (
        _storage_owned_projection(before, owned_keys),
        _storage_owned_projection(after, owned_keys),
    )


def _resource_quantity_ledger(character: Mapping[str, Any]):
    """Track all asset quantities while allowing metadata-only normalization."""
    equipment = {}
    for index, row in enumerate(character.get("equipment") or []):
        if not isinstance(row, dict):
            raise StorageTransactionError("character equipment is malformed")
        name = _normalized_name(row.get("item_name")) or f"__unnamed_{index}"
        equipment[name] = equipment.get(name, 0) + _strict_quantity(
            row.get("quantity", 1),
            f"equipment.{name}.quantity",
        )

    ammunition = {}
    for index, row in enumerate(character.get("ammunition") or []):
        if not isinstance(row, dict):
            raise StorageTransactionError("character ammunition is malformed")
        name = _normalized_name(row.get("name")) or f"__unnamed_{index}"
        ammunition[name] = ammunition.get(name, 0) + _strict_quantity(
            row.get("quantity"),
            f"ammunition.{name}.quantity",
        )

    raw_currency = character.get("currency") or {}
    if not isinstance(raw_currency, dict):
        raise StorageTransactionError("character currency is malformed")
    copper_total = 0
    for denomination, multiplier in (
        ("gold", 100),
        ("silver", 10),
        ("copper", 1),
    ):
        value = raw_currency.get(denomination, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StorageTransactionError("character currency is malformed")
        copper_total += value * multiplier
    return equipment, ammunition, copper_total


def _coexisting_normalization_advisories(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
):
    """Describe validator repairs that can safely ride the atomic commit."""
    advisories = []
    resource_fields = {"equipment", "currency", "ammunition"}
    for field in sorted(set(before) | set(after)):
        if field not in resource_fields and before.get(field) != after.get(field):
            advisories.append(f"storage_coexisting_normalization:{field}")

    before_currency = before.get("currency") or {}
    after_currency = after.get("currency") or {}
    if isinstance(before_currency, dict) and isinstance(after_currency, dict):
        for denomination in sorted(set(before_currency) | set(after_currency)):
            if before_currency.get(denomination) != after_currency.get(denomination):
                advisories.append(
                    f"storage_coexisting_normalization:currency.{denomination}"
                )

    for field, name_field in (
        ("equipment", "item_name"),
        ("ammunition", "name"),
    ):
        old_rows = _group_resource_rows(before, field, name_field)
        new_rows = _group_resource_rows(after, field, name_field)
        for name in sorted(set(old_rows) | set(new_rows)):
            if old_rows.get(name, []) != new_rows.get(name, []):
                advisories.append(
                    f"storage_coexisting_normalization:{field}.{name}"
                )
        if old_rows == new_rows and before.get(field) != after.get(field):
            advisories.append(f"storage_coexisting_normalization:{field}.order")
    return tuple(sorted(set(advisories)))


def _apply_storage_operation(
    operation: Dict[str, Any],
    character: Optional[Dict[str, Any]],
    storage: Dict[str, Any],
    location: Tuple[str, str, str, str],
    timestamp: str,
    selected_storage_id: Optional[str],
):
    """Apply one validated operation to in-memory images only."""
    action = operation["action"]
    location_id = location[0]
    if action == "create_storage":
        if selected_storage_id:
            raise StorageTransactionError(
                "one storage request cannot create or target multiple containers"
            )
        container = _new_container(operation, location, timestamp)
        storage["playerStorage"].append(container)
        storage["lastUpdated"] = timestamp
        return (
            container["id"],
            f"Created {container['deviceType']} at {container['locationName']}",
            (),
        )

    if character is None:
        raise StorageTransactionError("character inventory is unavailable")
    operation_storage_id = operation.get("storage_id")
    if operation_storage_id and selected_storage_id and (
        operation_storage_id != selected_storage_id
    ):
        raise StorageTransactionError(
            "one storage request cannot target multiple containers"
        )
    storage_id = operation_storage_id or selected_storage_id
    if storage_id:
        container = _find_container(storage, storage_id, location_id)
    elif action in {"store_item", "store_currency", "store_ammunition"}:
        container = _new_container(operation, location, timestamp)
        storage["playerStorage"].append(container)
        storage_id = container["id"]
    else:
        raise StorageTransactionError("retrieval requires a storage container")

    container_before = copy.deepcopy(container)
    character_before = copy.deepcopy(character)
    identity_advisories = ()
    if action in {"store_item", "retrieve_item"}:
        character_rows = _inventory_rows(character, "character")
        storage_rows = _inventory_rows(container, "storage")
        character_rows, character_identity_advisories = consolidate_equipment_rows(
            character_rows
        )
        storage_rows, storage_identity_advisories = consolidate_equipment_rows(
            storage_rows
        )
        character["equipment"] = character_rows
        container["contents"] = storage_rows
        identity_advisories = tuple(
            sorted(set(character_identity_advisories + storage_identity_advisories))
        )
        requested = _requested_items(operation)
        names = {_normalized_name(name) for name, _quantity in requested}
        conserved_before = _asset_counts(character_before, container_before, names)
        source_rows, destination_rows = (
            (character_rows, storage_rows)
            if action == "store_item"
            else (storage_rows, character_rows)
        )
        source_label, destination_label = (
            ("character", "storage")
            if action == "store_item"
            else ("storage", "character")
        )
        for name, quantity in requested:
            source = _remove_item(source_rows, name, quantity, source_label)
            _add_item(destination_rows, source, quantity, destination_label)
        if conserved_before != _asset_counts(character, container, names):
            raise StorageTransactionError(
                "storage resource identity or quantity was not conserved"
            )
        verb = "Stored" if action == "store_item" else "Retrieved"
        log_action = "store_items" if action == "store_item" and len(requested) > 1 else (
            "retrieve_items" if len(requested) > 1 else action
        )
        detail = [{"item": name, "quantity": quantity} for name, quantity in requested]
        item_text = ", ".join(f"{quantity} {name}" for name, quantity in requested)
    elif action in {"store_currency", "retrieve_currency"}:
        denomination = operation.get("denomination")
        if denomination not in _DENOMINATIONS:
            raise StorageTransactionError("currency denomination is invalid")
        quantity = _strict_quantity(operation.get("quantity"), "currency quantity")
        character_currency = _currency(character, "character")
        storage_currency = _currency(container, "storage")
        conserved_before = {
            name: _currency(character_before, "character")[name]
            + _currency(container_before, "storage")[name]
            for name in _DENOMINATIONS
        }
        source, destination = (
            (character_currency, storage_currency)
            if action == "store_currency"
            else (storage_currency, character_currency)
        )
        if source[denomination] < quantity:
            label = "character" if action == "store_currency" else "storage"
            raise StorageTransactionError(
                f"{label} only has {source[denomination]} {denomination}, "
                f"but {quantity} were requested"
            )
        source[denomination] -= quantity
        destination[denomination] += quantity
        conserved_after = {
            name: _currency(character, "character")[name]
            + _currency(container, "storage")[name]
            for name in _DENOMINATIONS
        }
        if conserved_before != conserved_after:
            raise StorageTransactionError(
                "storage resource identity or quantity was not conserved"
            )
        verb = "Stored" if action == "store_currency" else "Retrieved"
        log_action = action
        detail = {"denomination": denomination, "quantity": quantity}
        item_text = f"{quantity} {denomination}"
    else:
        name = operation.get("ammunition_name")
        if not isinstance(name, str) or not name.strip():
            raise StorageTransactionError("ammunition request has no useful name")
        quantity = _strict_quantity(operation.get("quantity"), "ammunition quantity")
        character_ammunition = _ammunition(character, "character")
        storage_ammunition = _ammunition(container, "storage")
        conserved_name = _normalized_name(name)
        ammunition_before = {}
        for counts in (
            _ammunition_counts(character_before, "character", conserved_name),
            _ammunition_counts(container_before, "storage", conserved_name),
        ):
            for key, count_quantity in counts.items():
                ammunition_before[key] = ammunition_before.get(key, 0) + count_quantity
        source_rows, destination_rows = (
            (character_ammunition, storage_ammunition)
            if action == "store_ammunition"
            else (storage_ammunition, character_ammunition)
        )
        source_label, destination_label = (
            ("character", "storage")
            if action == "store_ammunition"
            else ("storage", "character")
        )
        source = _remove_ammunition(source_rows, name, quantity, source_label)
        _add_ammunition(destination_rows, source, quantity, destination_label)
        ammunition_after = {}
        for counts in (
            _ammunition_counts(character, "character", conserved_name),
            _ammunition_counts(container, "storage", conserved_name),
        ):
            for key, count_quantity in counts.items():
                ammunition_after[key] = ammunition_after.get(key, 0) + count_quantity
        if ammunition_before != ammunition_after:
            raise StorageTransactionError(
                "storage resource identity or quantity was not conserved"
            )
        verb = "Stored" if action == "store_ammunition" else "Retrieved"
        log_action = action
        detail = {"ammunition": source.get("name"), "quantity": quantity}
        item_text = f"{quantity} {source.get('name')}"

    container["lastAccessed"] = timestamp
    container.setdefault("accessLog", []).append(
        {
            "character": operation["character"],
            "action": log_action,
            "items" if isinstance(detail, list) else "resource": detail,
            "timestamp": timestamp,
        }
    )
    storage["lastUpdated"] = timestamp
    preposition = "in" if action.startswith("store_") else "from"
    return (
        storage_id,
        f"{verb} {item_text} {preposition} {container['deviceName']}",
        identity_advisories,
    )


def prepare_storage_mutation_set(
    operations: Sequence[Mapping[str, Any]],
    *,
    character_working_image: Optional[Mapping[str, Any]] = None,
) -> StorageMutationPlan:
    """Prepare a complete storage intent as one all-or-nothing transaction."""
    operations = tuple(copy.deepcopy(dict(operation)) for operation in operations)
    if not operations or len(operations) > 32:
        raise StorageTransactionError(
            "a storage operation set must contain between 1 and 32 operations"
        )
    for operation in operations:
        _validate_operation(operation)
    characters = {operation.get("character") for operation in operations}
    if len(characters) != 1 or None in characters:
        raise StorageTransactionError(
            "one storage request must use one authoritative character"
        )

    timestamp = datetime.now().isoformat()
    location = _location()
    storage_path = os.path.normcase(os.path.realpath("player_storage.json"))
    storage_existed, loaded_storage = _load_storage(storage_path)
    storage_before = copy.deepcopy(loaded_storage) if storage_existed else None
    storage_after = copy.deepcopy(loaded_storage)
    needs_character = any(
        operation["action"] != "create_storage" for operation in operations
    )
    character_path = None
    character_before = None
    character_after = None
    if needs_character:
        character_path = _character_path(next(iter(characters)))
        character_before = safe_json_load(character_path)
        if not isinstance(character_before, dict):
            raise StorageTransactionError("character inventory is unavailable")
        if character_working_image is None:
            character_after = copy.deepcopy(character_before)
        else:
            if not isinstance(character_working_image, Mapping):
                raise StorageTransactionError(
                    "staged character inventory is unavailable"
                )
            expected_name = str(next(iter(characters))).strip().casefold()
            supplied_name = str(character_working_image.get("name") or "").strip().casefold()
            if not supplied_name or supplied_name != expected_name:
                raise StorageTransactionError(
                    "staged character inventory identity does not match"
                )
            character_after = copy.deepcopy(dict(character_working_image))

    selected_storage_id = None
    messages = []
    advisories = []
    for operation in operations:
        selected_storage_id, message, operation_advisories = _apply_storage_operation(
            operation,
            character_after,
            storage_after,
            location,
            timestamp,
            selected_storage_id,
        )
        messages.append(message)
        advisories.extend(operation_advisories)

    if character_after is not None:
        storage_owned_keys = _storage_owned_keys(operations)
        storage_mutated_character = copy.deepcopy(character_after)
        validated_character, validator_advisories = _validate_character_candidate(
            storage_mutated_character
        )
        if _storage_owned_delta_signature(
            character_before,
            storage_mutated_character,
            storage_owned_keys,
        ) != _storage_owned_delta_signature(
            character_before,
            validated_character,
            storage_owned_keys,
        ):
            raise StorageTransactionError(
                "character validation changed storage-owned resources"
            )
        if _resource_quantity_ledger(
            storage_mutated_character
        ) != _resource_quantity_ledger(validated_character):
            raise StorageTransactionError(
                "character validation changed unrelated resource quantities"
            )
        normalization_advisories = _coexisting_normalization_advisories(
            storage_mutated_character,
            validated_character,
        )
        for advisory in normalization_advisories:
            warning(f"INVENTORY: {advisory}", category="storage_operations")
        character_after = validated_character
        advisories.extend(validator_advisories)
        advisories.extend(normalization_advisories)

    exported_operation = (
        operations[0]
        if len(operations) == 1
        else {"operations": list(operations)}
    )
    return StorageMutationPlan(
        exported_operation,
        character_path,
        copy.deepcopy(character_before),
        character_after,
        storage_path,
        storage_existed,
        storage_before,
        storage_after,
        "; ".join(messages),
        tuple(sorted(set(advisories))),
    )


def prepare_storage_mutation(
    operation: Mapping[str, Any],
    *,
    character_working_image: Optional[Mapping[str, Any]] = None,
) -> StorageMutationPlan:
    """Prepare one backward-compatible storage operation without writing."""
    return prepare_storage_mutation_set(
        (operation,),
        character_working_image=character_working_image,
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
    operation_name = plan.operation.get("action")
    if operation_name is None and isinstance(plan.operation.get("operations"), list):
        operation_name = "batch"
    transaction = coordinator.build_plan(
        transaction_key=f"storage-{identity}",
        operation=f"storage_{operation_name or 'mutation'}",
        participants=participants,
        rollback_failure_code="storage_rolled_back",
    )
    return coordinator.execute(transaction, timeout_seconds=30.0)


def execute_item_storage_operation(operation: Mapping[str, Any]) -> Dict[str, Any]:
    """Prepare, commit, and boundedly re-prepare once on a stale snapshot."""
    failed_stage = "storage_prepare"
    try:
        for attempt in range(2):
            operation_set = operation.get("operations")
            plan = (
                prepare_storage_mutation_set(operation_set)
                if isinstance(operation_set, list)
                else prepare_storage_mutation(operation)
            )
            try:
                failed_stage = "storage_commit"
                execute_storage_plan(plan)
                return {
                    "success": True,
                    "message": plan.message,
                    "advisories": list(plan.advisories),
                }
            except TransactionStalePlanError:
                if attempt == 0:
                    failed_stage = "storage_stale_reprepare"
                    continue
                raise
    except Exception as exc:
        return {
            "success": False,
            "error": "Storage changed before the item transfer could be verified.",
            "failure_code": "storage_transfer_unverified",
            "diagnostic": str(exc),
            "exception_class": type(exc).__name__,
            "failed_stage": failed_stage,
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


def _currency_deltas(before: Mapping[str, Any], after: Mapping[str, Any]):
    before_currency = _currency(copy.deepcopy(dict(before)), "character")
    after_currency = _currency(copy.deepcopy(dict(after)), "character")
    return tuple(
        (denomination, after_currency[denomination] - before_currency[denomination])
        for denomination in _DENOMINATIONS
        if after_currency[denomination] != before_currency[denomination]
    )


def _asset_delta_shape(delta):
    return delta.family, delta.name, delta.quantity


def _storage_operation_delta_signature(operation: Mapping[str, Any]):
    """Project exact character-side item/ammunition deltas from T049 output."""
    operations = operation.get("operations")
    operations = operations if isinstance(operations, list) else [operation]
    totals = {}
    for item in operations:
        if not isinstance(item, Mapping):
            continue
        action = item.get("action")
        if action in {"store_item", "retrieve_item"}:
            sign = -1 if action == "store_item" else 1
            for name, quantity in _requested_items(item):
                key = ("equipment", _normalized_name(name))
                totals[key] = totals.get(key, 0) + sign * quantity
        elif action in {"store_ammunition", "retrieve_ammunition"}:
            sign = -1 if action == "store_ammunition" else 1
            name = _normalized_name(item.get("ammunition_name"))
            quantity = item.get("quantity")
            if name and type(quantity) is int and quantity > 0:
                key = ("ammunition", name)
                totals[key] = totals.get(key, 0) + sign * quantity
        elif action in {"store_currency", "retrieve_currency"}:
            sign = -1 if action == "store_currency" else 1
            name = _normalized_name(item.get("denomination"))
            quantity = item.get("quantity")
            if name in _DENOMINATIONS and type(quantity) is int and quantity > 0:
                key = ("currency", name)
                totals[key] = totals.get(key, 0) + sign * quantity
    return {key: quantity for key, quantity in totals.items() if quantity}


def _storage_operation_coverage_error(
    operation,
    required_deltas,
    *,
    storage_available=None,
):
    """Require T049 operations to cover every paired character asset delta."""
    required = {}
    for family, name, quantity in required_deltas:
        if family not in {"equipment", "ammunition", "currency"} or not quantity:
            continue
        key = (family, _normalized_name(name))
        required[key] = required.get(key, 0) + quantity
    required = {key: value for key, value in required.items() if value}
    if not required:
        return None
    actual = _storage_operation_delta_signature(operation)
    missing = [
        (family, name, quantity)
        for (family, name), quantity in sorted(required.items())
        if actual.get((family, name)) != quantity
    ]
    if not missing:
        return None
    labels = ", ".join(
        "%s %s %s%d" % (
            family,
            name,
            "" if quantity < 0 else "+",
            quantity,
        )
        for family, name, quantity in missing
    )
    actual_labels = ", ".join(
        "%s %s %s%d" % (
            family,
            name,
            "" if quantity < 0 else "+",
            quantity,
        )
        for (family, name), quantity in sorted(actual.items())
    ) or "none"
    available = storage_available or {}
    available_labels = ", ".join(
        f"{family} {name} available {quantity}"
        for (family, name), quantity in sorted(available.items())
    ) or "none"
    return (
        "storage operation set does not cover the character-side resource "
        f"deltas ({labels}). Current storage-operation signed deltas: "
        f"{actual_labels}. Canonical storage availability: {available_labels}. "
        "Return one complete operations[] array containing "
        "every required create/store/retrieve operation in this turn"
    )


def _ownership_local_equipment_changes(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
):
    def equipped_by_name(sheet):
        rows = sheet.get("equipment") or []
        if not isinstance(rows, list):
            raise StorageTransactionError("character equipment is malformed")
        result = {}
        for row in rows:
            if not isinstance(row, dict):
                raise StorageTransactionError("character equipment is malformed")
            name = _normalized_name(row.get("item_name"))
            if name in result:
                raise StorageTransactionError(
                    "character contains ambiguous duplicate item names"
                )
            result[name] = row.get("equipped", False)
        return result

    old = equipped_by_name(before)
    new = equipped_by_name(after)
    return {
        name
        for name in set(old) & set(new)
        if old[name] != new[name]
    }


def _combine_storage_owned_character_delta(storage_plan, character_action):
    """Return one atomic plan for an exact duplicate storage mutation.

    ``None`` means the character action does not touch the storage resource.
    An overlapping but non-identical mutation is unsafe and raises instead of
    allowing either independent action to commit.
    """
    if storage_plan.character_path is None:
        return None
    character_plan = character_action.plan
    if storage_plan.character_path != character_plan.canonical_path:
        return None

    from core.managers.character_transfer import (
        concrete_asset_deltas,
        concrete_asset_deltas_between,
    )

    storage_deltas = concrete_asset_deltas_between(
        storage_plan.character_before,
        storage_plan.character_after,
    )
    character_deltas = tuple(concrete_asset_deltas(character_plan))
    storage_keys = {delta.lookup_key for delta in storage_deltas}
    character_keys = {delta.lookup_key for delta in character_deltas}
    if not storage_keys & character_keys:
        return None
    if storage_plan.character_before != character_plan.pre_image:
        raise StorageTransactionError(
            "storage and character updates do not share one character snapshot"
        )

    if sorted(_asset_delta_shape(delta) for delta in storage_deltas) != sorted(
        _asset_delta_shape(delta) for delta in character_deltas
    ):
        raise StorageTransactionError(
            "storage and character actions overlap without identical resource deltas"
        )
    storage_metadata = {
        _asset_delta_shape(delta): delta.metadata
        for delta in storage_deltas
        if delta.family != "currency"
    }
    character_metadata = {
        _asset_delta_shape(delta): delta.metadata
        for delta in character_deltas
        if delta.family != "currency"
    }
    metadata_advisories = tuple(
        sorted(
            "storage_sibling_metadata_canonicalized:%s:%s" % (family, name)
            for (family, name, _quantity), metadata in storage_metadata.items()
            if character_metadata.get((family, name, _quantity)) != metadata
        )
    )
    if any(delta.family == "currency" for delta in storage_deltas):
        if _currency_deltas(
            storage_plan.character_before, storage_plan.character_after
        ) != _currency_deltas(character_plan.pre_image, character_plan.post_image):
            raise StorageTransactionError(
                "storage and character actions use different currency denominations"
            )
    storage_equipped_changes = _ownership_local_equipment_changes(
        storage_plan.character_before,
        storage_plan.character_after,
    )
    character_equipped_changes = _ownership_local_equipment_changes(
        character_plan.pre_image,
        character_plan.post_image,
    )
    if character_equipped_changes - storage_equipped_changes:
        raise StorageTransactionError(
            "character action includes an unrelated equip or unequip mutation"
        )

    combined_character = copy.deepcopy(storage_plan.character_after)
    storage_owned_fields = _changed_top_level(
        storage_plan.character_before,
        storage_plan.character_after,
    )
    for field in _changed_top_level(
        character_plan.pre_image,
        character_plan.post_image,
    ) - storage_owned_fields:
        if field in character_plan.post_image:
            combined_character[field] = copy.deepcopy(character_plan.post_image[field])
        else:
            combined_character.pop(field, None)
    for advisory in metadata_advisories:
        warning(f"INVENTORY: {advisory}", category="storage_operations")
    return replace(
        storage_plan,
        character_after=combined_character,
        advisories=tuple(
            sorted(set(storage_plan.advisories + metadata_advisories))
        ),
    )


def _storage_sibling_correction(storage_plan):
    """Build deterministic facts for the one bounded T079 sibling repair."""
    from core.managers.character_transfer import concrete_asset_deltas_between

    storage_available = {}
    storage_before = storage_plan.storage_before or {}
    operation_set = storage_plan.operation.get("operations")
    operations = (
        operation_set if isinstance(operation_set, list) else [storage_plan.operation]
    )
    target_storage_ids = {
        operation.get("storage_id")
        for operation in operations
        if isinstance(operation, dict) and operation.get("storage_id")
    }
    for container in storage_before.get("playerStorage") or []:
        if not isinstance(container, dict):
            continue
        if target_storage_ids and container.get("id") not in target_storage_ids:
            continue
        for row in container.get("contents") or []:
            if isinstance(row, dict):
                key = ("equipment", _normalized_name(row.get("item_name")))
                storage_available[key] = storage_available.get(key, 0) + row.get(
                    "quantity", 1
                )
        for row in container.get("ammunition") or []:
            if isinstance(row, dict):
                key = ("ammunition", _normalized_name(row.get("name")))
                storage_available[key] = storage_available.get(key, 0) + row.get(
                    "quantity", 0
                )
        currency = container.get("currency") or {}
        if isinstance(currency, dict):
            for denomination in _DENOMINATIONS:
                key = ("currency", denomination)
                storage_available[key] = storage_available.get(key, 0) + currency.get(
                    denomination, 0
                )

    facts = []
    before_currency = storage_plan.character_before.get("currency") or {}
    after_currency = storage_plan.character_after.get("currency") or {}
    for denomination, denomination_delta in _currency_deltas(
        storage_plan.character_before,
        storage_plan.character_after,
    ):
        source_available = (
            storage_available.get(("currency", denomination), 0)
            if denomination_delta > 0
            else before_currency.get(denomination, 0)
        )
        facts.append(
            f"currency {denomination}: authoritative source available "
            f"{source_available}, character current "
            f"{before_currency.get(denomination, 0)}, "
            f"{'receives' if denomination_delta > 0 else 'removes'} "
            f"{abs(denomination_delta)}, required signed delta "
            f"{denomination_delta:+d}, required ABSOLUTE final "
            f"{after_currency.get(denomination, 0)}"
        )
    for delta in concrete_asset_deltas_between(
        storage_plan.character_before,
        storage_plan.character_after,
    ):
        if delta.family == "currency":
            continue
        before_quantity = 0
        final_quantity = 0
        field, name_field = (
            ("equipment", "item_name")
            if delta.family == "equipment"
            else ("ammunition", "name")
        )
        for row in storage_plan.character_before.get(field) or []:
            if _normalized_name(row.get(name_field)) == delta.name:
                before_quantity = row.get("quantity", 1)
                break
        for row in storage_plan.character_after.get(field) or []:
            if _normalized_name(row.get(name_field)) == delta.name:
                final_quantity = row.get("quantity", 1)
                break
        direction = "receives" if delta.quantity > 0 else "removes"
        available_quantity = (
            storage_available.get((delta.family, delta.name), 0)
            if delta.quantity > 0
            else before_quantity
        )
        facts.append(
            f"{delta.family} {delta.name}: authoritative source available "
            f"{available_quantity}, character current {before_quantity}, "
            f"{direction} {abs(delta.quantity)}, required signed delta "
            f"{delta.quantity:+d}, required final {final_quantity}"
        )
    return (
        "The validated storage operation is authoritative for its resource "
        "movement. Rewrite this character update once so its resource fields "
        "match every deterministic fact below exactly, while preserving any "
        "unrelated same-turn changes. Do not substitute names, families, signs, "
        "quantities, or final values. Currency objects use the required absolute "
        "denomination finals; ammunition quantities use the required signed "
        "delta.\n- "
        + "\n- ".join(facts)
    )


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
    required_deltas=(),
    character_working_image=None,
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

    processed = process_storage_request(
        description,
        str(character),
        required_deltas=required_deltas,
    )
    if not processed.get("success"):
        raise StorageTransactionError(
            processed.get("error") or "storage operation preparation failed"
        )
    operation = processed.get("operation")
    if not isinstance(operation, dict):
        raise StorageTransactionError("storage processor returned no operation")
    coverage_error = _storage_operation_coverage_error(
        operation,
        required_deltas,
    )
    if coverage_error and not processed.get("coverage_unresolved"):
        raise StorageTransactionError(coverage_error)
    if operation.get("action") == "view_storage":
        return index, operation, None
    def mark_coverage_unresolved(plan):
        if plan is None or not processed.get("coverage_unresolved"):
            return plan
        return replace(
            plan,
            advisories=tuple(
                sorted(set(plan.advisories + ("storage_coverage_unresolved",)))
            ),
        )

    operations = operation.get("operations")
    if isinstance(operations, list) and any(
        item.get("action") == "view_storage" for item in operations
    ):
        raise StorageTransactionError(
            "view_storage cannot be mixed with storage mutations"
        )

    def prepare(working_image=None):
        if isinstance(operations, list):
            return prepare_storage_mutation_set(
                operations,
                character_working_image=working_image,
            )
        return prepare_storage_mutation(
            operation,
            character_working_image=working_image,
        )

    try:
        plan = prepare()
    except StorageTransactionError as exc:
        unavailable = "not available in character" in str(exc).casefold()
        if not unavailable or not isinstance(character_working_image, Mapping):
            raise
        plan = prepare(character_working_image)
        plan = replace(
            plan,
            advisories=tuple(
                sorted(set(plan.advisories + ("storage_staged_source",)))
            ),
        )
    return index, operation, mark_coverage_unresolved(plan)


def validate_required_storage_sibling(
    response_data,
    action_prediction,
    party_tracker_data,
):
    """Reject a storage-classified resource change with no storage action.

    The existing action predictor already runs before the main DM call. This
    guard consumes that result without adding another classifier call. It
    prepares concrete character deltas only for the exceptional missing-
    sibling shape; paired storage responses and non-storage turns do no extra
    work here.
    """
    if not isinstance(response_data, dict) or not isinstance(
        action_prediction, dict
    ):
        return True, ""
    reason = str(action_prediction.get("reason") or "").casefold()
    if not action_prediction.get("requires_actions") or "storag" not in reason:
        return True, ""
    actions = response_data.get("actions")
    if not isinstance(actions, list):
        return True, ""
    if any(
        isinstance(action, dict)
        and action.get("action") == "storageInteraction"
        for action in actions
    ):
        return True, ""
    character_actions = tuple(
        (index, action)
        for index, action in enumerate(actions)
        if isinstance(action, dict)
        and action.get("action") == "updateCharacterInfo"
    )
    if not character_actions:
        return True, ""

    from core.managers.character_transfer import (
        concrete_asset_deltas,
        prepare_character_actions,
    )

    prepared = prepare_character_actions(character_actions, party_tracker_data)
    changed = sorted(
        {
            (delta.family, delta.name)
            for item in prepared
            for delta in concrete_asset_deltas(item.plan)
            if delta.quantity != 0
        }
    )
    if not changed:
        return True, ""
    families = ", ".join(
        f"{family} {name}" if name != "currency" else "currency"
        for family, name in changed
    )
    return (
        False,
        "This storage-related response changes "
        f"{families} on a character but omits storageInteraction. "
        "Return the complete storageInteraction sibling so the storage "
        "transaction can own and atomically conserve the resource.",
    )


def process_adjacent_storage_fee_groups(
    prepared_character_actions,
    indexed_storage_actions,
    party_tracker_data,
):
    """Prepare storage-owned deltas and fees for the response transaction.

    This function deliberately performs no durable write.  Its returned plans
    join every remaining character image at the response-level commit boundary.
    """
    from core.managers.character_transfer import (
        _candidate_components,
        concrete_asset_deltas,
    )

    prepared_character_actions = tuple(prepared_character_actions)
    indexed_storage_actions = tuple(indexed_storage_actions)
    transfer_claimed = {
        index
        for component in _candidate_components(prepared_character_actions)
        for index in component
    }
    handled_characters = set()
    handled_storage = set()
    messages = []
    response_storage_plans = []
    storage_indices = {index for index, _action in indexed_storage_actions}
    prepared_storage = {}
    corrected_storage_siblings = set()
    action_indices = tuple(
        sorted(
            {item.index for item in prepared_character_actions}
            | {index for index, _action in indexed_storage_actions}
        )
    )
    failed_stage = "storage_pairing"

    def required_deltas_for(indexed_storage):
        storage_index, storage_action = indexed_storage
        parameters = storage_action.get("parameters") or {}
        character_name = parameters.get("characterName")
        if not character_name:
            character_name = next(
                iter(party_tracker_data.get("partyMembers") or []),
                None,
            )
        matching = [
            item
            for item in asset_mutations
            if item.index not in transfer_claimed
            and item.plan.character_name == character_name
        ]
        adjacent = [item for item in matching if abs(item.index - storage_index) == 1]
        if adjacent:
            matching = adjacent
        elif len(indexed_storage_actions) != 1:
            matching = []
        return tuple(
            sorted(
                _asset_delta_shape(delta)
                for item in matching
                for delta in concrete_asset_deltas(item.plan)
                if delta.family in {"equipment", "ammunition"}
                and delta.quantity
            )
        )

    def prepare_storage(indexed_storage, fallback_character=None):
        storage_index = indexed_storage[0]
        if storage_index not in prepared_storage:
            parameters = indexed_storage[1].get("parameters") or {}
            character_name = parameters.get("characterName") or fallback_character
            candidates = [
                item
                for item in prepared_character_actions
                if item.plan.character_name == character_name
            ]
            working_image = (
                candidates[0].plan.post_image if len(candidates) == 1 else None
            )
            prepared_storage[storage_index] = _prepare_response_storage_action(
                indexed_storage,
                party_tracker_data,
                fallback_character=fallback_character,
                required_deltas=required_deltas_for(indexed_storage),
                character_working_image=working_image,
            )
        return prepared_storage[storage_index]

    def correct_storage_sibling(item, storage_plan):
        if item.index in corrected_storage_siblings:
            raise StorageTransactionError(
                "storage sibling correction failed safely"
            )
        from core.managers.character_transfer import _prepare_actions

        corrected = _prepare_actions(
            ((item.index, item.action),),
            party_tracker_data,
            correction=_storage_sibling_correction(storage_plan),
        )
        if len(corrected) != 1:
            raise StorageTransactionError(
                "storage sibling correction returned an invalid batch"
            )
        corrected_storage_siblings.add(item.index)
        return corrected[0]

    try:
        failed_stage = "storage_pairing"
        asset_mutations = [
            item
            for item in prepared_character_actions
            if concrete_asset_deltas(item.plan)
        ]
        for indexed_storage in sorted(
            indexed_storage_actions, key=lambda value: value[0]
        ):
            if not asset_mutations:
                break
            storage_index = indexed_storage[0]
            failed_stage = "storage_prepare"
            _index, _operation, storage_plan = prepare_storage(indexed_storage)
            if storage_plan is None:
                continue
            failed_stage = "storage_pairing"
            exact = []
            overlapping_transfer = False
            for item in asset_mutations:
                if item.index in handled_characters:
                    continue
                if (
                    (
                        item.index in transfer_claimed
                        or "storage_staged_source" in storage_plan.advisories
                    )
                    and storage_plan.character_path == item.plan.canonical_path
                ):
                    import model_config
                    from core.managers.resource_transaction_planning import (
                        storage_overlap_has_complete_planning_packet,
                    )

                    if storage_overlap_has_complete_planning_packet(
                        prepared_character_actions,
                        (storage_plan,),
                        provider=model_config.get_provider(),
                    ):
                        overlapping_transfer = True
                        continue
                try:
                    combined = _combine_storage_owned_character_delta(
                        storage_plan,
                        item,
                    )
                except StorageTransactionError as sibling_error:
                    if str(sibling_error) not in {
                        "storage and character actions overlap without identical resource deltas",
                        "storage and character actions use different currency denominations",
                    }:
                        raise
                    item = correct_storage_sibling(item, storage_plan)
                    combined = _combine_storage_owned_character_delta(
                        storage_plan,
                        item,
                    )
                if (
                    combined is None
                    and "storage_coverage_unresolved" in storage_plan.advisories
                    and storage_plan.character_path == item.plan.canonical_path
                ):
                    item = correct_storage_sibling(item, storage_plan)
                    combined = _combine_storage_owned_character_delta(
                        storage_plan,
                        item,
                    )
                    if combined is None:
                        raise StorageTransactionError(
                            "storage sibling correction did not cover the "
                            "authoritative storage movement"
                        )
                if combined is None:
                    continue
                if item.index in transfer_claimed:
                    overlapping_transfer = True
                    continue
                exact.append((item, combined))
            if overlapping_transfer:
                # Preserve every independently prepared action and the storage
                # plan for the bounded T105 graph.  Nothing is merged or
                # claimed at this early one-action pairing seam.
                continue
            if len(exact) > 1:
                raise StorageTransactionError(
                    "storage mutation overlaps an ambiguous character transfer"
                )
            if not exact:
                continue
            character_action, combined = exact[0]
            response_storage_plans.append(combined)
            handled_characters.add(character_action.index)
            handled_storage.add(storage_index)
            messages.append(combined.message)

        eligible = [
            item
            for item in prepared_character_actions
            if item.index not in transfer_claimed
            and item.index not in handled_characters
            if _changed_top_level(item.plan.pre_image, item.plan.post_image)
            <= {"currency"}
            and _currency_copper(item.plan.post_image)
            < _currency_copper(item.plan.pre_image)
        ]
        unambiguous_fee_indices = {
            item.index
            for item in eligible
            if sum(
                abs(item.index - index) == 1
                for index in storage_indices - handled_storage
            )
            == 1
        }
        for indexed_storage in sorted(
            indexed_storage_actions, key=lambda value: value[0]
        ):
            storage_index = indexed_storage[0]
            if storage_index in handled_storage:
                continue
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
            failed_stage = "storage_fee_prepare"
            _index, _operation, storage_plan = prepare_storage(
                indexed_storage,
                fee_action.plan.character_name,
            )
            if storage_plan is None:
                continue
            combined = _combine_storage_fee(storage_plan, fee_action)
            if combined is None:
                continue
            response_storage_plans.append(combined)
            handled_characters.add(fee_action.index)
            handled_storage.add(storage_index)
            messages.append(combined.message)

        # A storage mutation without a duplicate character sibling still joins
        # this response transaction.  Read-only views remain in other_actions.
        for indexed_storage in sorted(
            indexed_storage_actions, key=lambda value: value[0]
        ):
            storage_index = indexed_storage[0]
            if storage_index in handled_storage:
                continue
            failed_stage = "storage_prepare"
            _index, _operation, storage_plan = prepare_storage(indexed_storage)
            if storage_plan is None:
                continue
            response_storage_plans.append(storage_plan)
            handled_storage.add(storage_index)
            messages.append(storage_plan.message)
        return {
            "success": True,
            "remaining_character_actions": tuple(
                item
                for item in prepared_character_actions
                if item.index not in handled_characters
            ),
            "handled_storage_indices": frozenset(handled_storage),
            "storage_plans": tuple(response_storage_plans),
            "messages": tuple(messages),
        }
    except Exception as exc:
        return _storage_batch_failure(
            exc,
            stage=failed_stage,
            action_indices=action_indices,
        )


def _storage_batch_failure(
    exc: Exception,
    *,
    stage: str = "storage_batch",
    action_indices=(),
):
    """Return one internal failure envelope for boundary telemetry."""
    indices = sorted(
        {
            value
            for value in action_indices
            if type(value) is int and 0 <= value <= 4096
        }
    )
    return {
        "success": False,
        "error": "Storage and character changes could not be committed together.",
        "failure_code": "storage_batch_unverified",
        "diagnostic": str(exc),
        "exception_class": type(exc).__name__,
        "failed_stage": stage,
        "action_indices": indices,
    }
