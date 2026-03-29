# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Character Ops Routing Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Helpers for classifying additive structured ops payloads.
"""

from typing import Any, Dict, List, Optional


_LEGACY_NESTED_OP_KEYS = {
    "set_hp",
    "hp_delta",
    "spell_slot_delta",
    "inventory_add",
    "inventory_remove",
    "currency_delta",
    "condition_add",
    "condition_remove",
    "feature_usage_delta",
    "feature_usage_set",
    "death_save_failure",
    "death_save_failure_delta",
    "death_save_success",
    "death_save_success_delta",
    "death_saves_set",
}


def _normalize_legacy_nested_op(op: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize legacy one-key nested op wrapper into canonical flat op.

    Example:
      {"inventory_remove": {"item": "Healing Potion", "quantity": 1}}
      -> {"op": "inventory_remove", "item": "Healing Potion", "quantity": 1}
    """
    if "op" in op or "type" in op:
        return op

    if len(op) != 1:
        return op

    op_name, payload = next(iter(op.items()))
    if not isinstance(op_name, str):
        return op

    normalized_name = op_name.strip().lower()
    if normalized_name not in _LEGACY_NESTED_OP_KEYS:
        return op

    normalized_op: Dict[str, Any] = {"op": normalized_name}
    if isinstance(payload, dict):
        normalized_op.update(payload)
        return normalized_op

    # Scalar payload fallback for common wrappers.
    if normalized_name == "hp_delta":
        normalized_op["delta"] = payload
    elif normalized_name == "set_hp":
        normalized_op["value"] = payload
    elif normalized_name == "feature_usage_delta":
        normalized_op["delta"] = payload
    elif normalized_name == "feature_usage_set":
        normalized_op["current"] = payload
    elif normalized_name in ["death_save_failure", "death_save_failure_delta", "death_save_success", "death_save_success_delta"]:
        normalized_op["delta"] = payload
    else:
        return op

    return normalized_op


def normalize_character_ops_payload(ops: Any) -> Optional[List[Dict[str, Any]]]:
    """Normalize ops payload into list[dict] or None.

    Returns:
        None: ops absent
        []: invalid/non-dict ops payload
        list[dict]: normalized ops list
    """
    if ops is None:
        return None
    if not isinstance(ops, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for op in ops:
        if isinstance(op, dict):
            normalized.append(_normalize_legacy_nested_op(op))
    return normalized


def classify_character_update_payload(changes: Any, ops: Any) -> Dict[str, str]:
    """Classify update payload mode and reason.

    Modes:
      - prose_fallback
      - mixed
      - structured_only
      - hard_fail
    """
    has_changes = False
    if isinstance(changes, str):
        has_changes = bool(changes.strip())
    elif isinstance(changes, dict):
        has_changes = True
    elif changes is not None:
        has_changes = bool(str(changes).strip())

    normalized_ops = normalize_character_ops_payload(ops)

    if normalized_ops is None:
        if has_changes:
            return {"mode": "prose_fallback", "reason": "ops_absent"}
        return {"mode": "hard_fail", "reason": "ops_absent_no_changes"}

    if not normalized_ops:
        if has_changes:
            return {"mode": "prose_fallback", "reason": "ops_invalid_with_changes_fallback"}
        return {"mode": "hard_fail", "reason": "ops_invalid_no_fallback"}

    if has_changes:
        return {"mode": "mixed", "reason": "ops_present_with_changes"}

    return {"mode": "structured_only", "reason": "ops_present_no_changes"}
