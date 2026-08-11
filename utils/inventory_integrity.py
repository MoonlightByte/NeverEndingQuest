# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Deterministic inventory identity, resource bounds, and repair forensics."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


DEFAULT_QUARANTINE_ROOT = os.path.join(
    "modules", ".runtime_quarantine", "ammunition"
)
DEFAULT_QUARANTINE_LIMIT = 64
_OWNERSHIP_LOCAL_FIELDS = {"equipped"}
_NONSTACKABLE_FIELDS = {
    "charges",
    "effects",
    "instance_id",
    "item_id",
    "serial",
    "attuned",
    "requires_attunement",
}


class InventoryIntegrityError(ValueError):
    """Inventory state cannot be changed without guessing or losing value."""


def normalize_inventory_name(value: Any) -> str:
    """Return the shared case/whitespace-insensitive lookup identity."""
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def strict_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InventoryIntegrityError(f"{label} must be a nonnegative integer")
    return value


def inventory_metadata(
    row: Mapping[str, Any],
    name_field: str = "item_name",
    *,
    omit_ownership_local: bool = True,
) -> str:
    """Canonical mechanical identity; display spelling is lookup-only."""
    value = copy.deepcopy(dict(row))
    value.pop("quantity", None)
    if omit_ownership_local:
        for field in _OWNERSHIP_LOCAL_FIELDS:
            value.pop(field, None)
    value[name_field] = normalize_inventory_name(value.get(name_field))
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def is_stackable_equipment(row: Mapping[str, Any]) -> bool:
    """Return true only when a row explicitly demonstrates fungibility."""
    if row.get("equipped") is True or row.get("magical") is True:
        return False
    if any(field in row for field in _NONSTACKABLE_FIELDS):
        return False
    if row.get("stackable") is True:
        return True
    quantity = row.get("quantity", 1)
    return (
        isinstance(quantity, int)
        and not isinstance(quantity, bool)
        and quantity > 1
    )


def consolidate_equipment_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], Tuple[str, ...]]:
    """Combine only provably identical stackable rows; retain ambiguity intact."""
    if not isinstance(rows, list):
        raise InventoryIntegrityError("equipment must be an array")
    result: List[Dict[str, Any]] = []
    candidates: Dict[Tuple[str, str], int] = {}
    identities_by_name: Dict[str, set] = {}
    seen_names = set()
    advisories = set()
    for index, original in enumerate(rows):
        if not isinstance(original, dict):
            raise InventoryIntegrityError(f"equipment[{index}] must be an object")
        row = copy.deepcopy(original)
        name = normalize_inventory_name(row.get("item_name"))
        if not name:
            raise InventoryIntegrityError(f"equipment[{index}] has no useful name")
        quantity = strict_nonnegative_int(
            row.get("quantity", 1), f"equipment[{index}].quantity"
        )
        metadata = inventory_metadata(row, omit_ownership_local=False)
        identities = identities_by_name.setdefault(name, set())
        if identities and metadata not in identities:
            advisories.add(f"equipment_identity_ambiguous:{name}")
        identities.add(metadata)
        key = (name, metadata)
        existing_index = candidates.get(key)
        if (
            existing_index is not None
            and is_stackable_equipment(result[existing_index])
            and is_stackable_equipment(row)
        ):
            result[existing_index]["quantity"] = (
                strict_nonnegative_int(
                    result[existing_index].get("quantity", 1),
                    f"equipment.{name}.quantity",
                )
                + quantity
            )
            continue
        if existing_index is not None:
            advisories.add(f"equipment_identity_ambiguous:{name}")
        elif name in seen_names:
            advisories.add(f"equipment_identity_ambiguous:{name}")
        result.append(row)
        seen_names.add(name)
        if is_stackable_equipment(row):
            candidates[key] = len(result) - 1
    return result, tuple(sorted(advisories))


def validate_resource_bounds(sheet: Mapping[str, Any]) -> None:
    """Enforce the resource matrix missing from the permissive JSON schema."""
    equipment = sheet.get("equipment") or []
    if not isinstance(equipment, list):
        raise InventoryIntegrityError("equipment must be an array")
    for index, item in enumerate(equipment):
        if not isinstance(item, dict):
            raise InventoryIntegrityError(f"equipment[{index}] must be an object")
        strict_nonnegative_int(
            item.get("quantity", 1), f"equipment[{index}].quantity"
        )
        charges = item.get("charges")
        if charges is not None:
            if not isinstance(charges, dict):
                raise InventoryIntegrityError(
                    f"equipment[{index}].charges must be an object"
                )
            current = strict_nonnegative_int(
                charges.get("current"), f"equipment[{index}].charges.current"
            )
            maximum = strict_nonnegative_int(
                charges.get("max"), f"equipment[{index}].charges.max"
            )
            if current > maximum:
                raise InventoryIntegrityError(
                    f"equipment[{index}].charges.current exceeds max"
                )

    ammunition = sheet.get("ammunition")
    if ammunition is not None:
        if not isinstance(ammunition, list):
            raise InventoryIntegrityError("ammunition must be an array")
        seen = set()
        for index, item in enumerate(ammunition):
            if not isinstance(item, dict):
                raise InventoryIntegrityError(
                    f"ammunition[{index}] must be an object"
                )
            name = normalize_inventory_name(item.get("name"))
            if not name:
                raise InventoryIntegrityError(
                    f"ammunition[{index}] has no useful name"
                )
            if name in seen:
                raise InventoryIntegrityError(
                    f"ammunition contains duplicate name '{name}'"
                )
            seen.add(name)
            strict_nonnegative_int(
                item.get("quantity"), f"ammunition[{index}].quantity"
            )

    features = sheet.get("classFeatures") or []
    if not isinstance(features, list):
        raise InventoryIntegrityError("classFeatures must be an array")
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise InventoryIntegrityError(f"classFeatures[{index}] must be an object")
        usage = feature.get("usage")
        if usage is None:
            continue
        if not isinstance(usage, dict):
            raise InventoryIntegrityError(
                f"classFeatures[{index}].usage must be an object"
            )
        current = strict_nonnegative_int(
            usage.get("current"), f"classFeatures[{index}].usage.current"
        )
        maximum = strict_nonnegative_int(
            usage.get("max"), f"classFeatures[{index}].usage.max"
        )
        if current > maximum:
            raise InventoryIntegrityError(
                f"classFeatures[{index}].usage.current exceeds max"
            )


def large_resource_increase_advisories(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    currency_threshold_cp: int = 100_000,
    ammunition_threshold: int = 500,
) -> Tuple[str, ...]:
    """Return neutral, nonblocking telemetry for unusually large increases."""
    advisories = []
    multipliers = {"gold": 100, "silver": 10, "copper": 1}

    def currency_total(sheet):
        value = sheet.get("currency") or {}
        if not isinstance(value, dict):
            return 0
        total = 0
        for denomination, multiplier in multipliers.items():
            raw = value.get(denomination, 0)
            if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
                total += raw * multiplier
        return total

    if currency_total(after) - currency_total(before) > currency_threshold_cp:
        advisories.append("large_increase:currency")

    def ammo_totals(sheet):
        totals = {}
        rows = sheet.get("ammunition") or []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = normalize_inventory_name(row.get("name"))
                quantity = row.get("quantity")
                if name and isinstance(quantity, int) and not isinstance(quantity, bool):
                    totals[name] = totals.get(name, 0) + quantity
        return totals

    old_ammo, new_ammo = ammo_totals(before), ammo_totals(after)
    for name in sorted(set(old_ammo) | set(new_ammo)):
        if new_ammo.get(name, 0) - old_ammo.get(name, 0) > ammunition_threshold:
            advisories.append(f"large_increase:ammunition:{name}")
    return tuple(advisories)


def quarantine_malformed_ammunition(
    sheet: Any,
    character_path: str,
    *,
    root: str = DEFAULT_QUARANTINE_ROOT,
    limit: int = DEFAULT_QUARANTINE_LIMIT,
) -> Optional[str]:
    """Preserve a malformed whole ammunition value once before repair overwrites it."""
    if not isinstance(sheet, dict) or "ammunition" not in sheet:
        return None
    payload = sheet.get("ammunition")
    if payload is None or isinstance(payload, list):
        return None
    record = {
        "character": os.path.basename(str(character_path or "unknown")),
        "ammunition": payload,
    }
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    os.makedirs(root, exist_ok=True)
    destination = os.path.join(root, f"{digest}.json")
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return destination
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.unlink(destination)
        except OSError:
            pass
        raise

    if isinstance(limit, int) and limit > 0:
        files = []
        for name in os.listdir(root):
            path = os.path.join(root, name)
            if name.endswith(".json") and os.path.isfile(path):
                files.append((os.path.getmtime(path), name, path))
        for _mtime, _name, path in sorted(files)[: max(0, len(files) - limit)]:
            try:
                os.unlink(path)
            except OSError:
                pass
    return destination
