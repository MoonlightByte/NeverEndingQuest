# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Tracked Transfer Runtime Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


def _normalize_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("'", "")
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _normalize_item_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:a|an|the)\s+", "", text)
    return text


def _is_tracked_item_label(item_name: str) -> bool:
    tokens = [token for token in _normalize_item_name(item_name).split() if token]
    return len(tokens) >= 2


def _extract_single_inventory_op_signature(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(action, dict) or action.get("action") != "updateCharacterInfo":
        return None

    params = action.get("parameters", {})
    if not isinstance(params, dict):
        return None

    character_name = str(params.get("characterName") or "").strip()
    if not character_name:
        return None

    ops = params.get("ops")
    if not isinstance(ops, list) or len(ops) != 1:
        return None

    op = ops[0]
    if not isinstance(op, dict):
        return None

    op_type = str(op.get("op") or op.get("type") or "").strip().lower()
    if op_type not in {"inventory_add", "inventory_remove"}:
        return None

    item_name = str(op.get("item_name") or op.get("name") or op.get("item") or "").strip()
    if not item_name:
        return None

    quantity_raw = op.get("quantity", 1)
    try:
        quantity = int(quantity_raw)
    except (TypeError, ValueError):
        return None
    if quantity <= 0:
        return None

    return {
        "op_type": op_type,
        "character_name": character_name,
        "item_name": item_name,
        "quantity": quantity,
        "action": action,
    }


def extract_atomic_tracked_transfer_pairs(
    actions: List[Dict[str, Any]],
    valid_character_names: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract add/remove transfer pairs that should be processed atomically."""
    normalized_valid_names: Set[str] = {
        _normalize_name(name) for name in valid_character_names if isinstance(name, str) and name.strip()
    }
    if not normalized_valid_names:
        return ([], list(actions))

    signatures: List[Tuple[int, Dict[str, Any]]] = []
    for index, action in enumerate(actions):
        signature = _extract_single_inventory_op_signature(action)
        if signature is None:
            continue
        if _normalize_name(signature["character_name"]) not in normalized_valid_names:
            continue
        if not _is_tracked_item_label(signature["item_name"]):
            continue
        signatures.append((index, signature))

    add_pool: Dict[Tuple[str, int], List[Tuple[int, Dict[str, Any]]]] = {}
    remove_pool: Dict[Tuple[str, int], List[Tuple[int, Dict[str, Any]]]] = {}
    for index, signature in signatures:
        key = (_normalize_item_name(signature["item_name"]), int(signature["quantity"]))
        if signature["op_type"] == "inventory_add":
            add_pool.setdefault(key, []).append((index, signature))
        else:
            remove_pool.setdefault(key, []).append((index, signature))

    transfer_pairs: List[Dict[str, Any]] = []
    consumed_indexes: Set[int] = set()

    for key, remove_entries in remove_pool.items():
        add_entries = add_pool.get(key, [])
        if not add_entries:
            continue

        for remove_index, remove_signature in remove_entries:
            if remove_index in consumed_indexes:
                continue

            selected_add: Optional[Tuple[int, Dict[str, Any]]] = None
            for add_index, add_signature in add_entries:
                if add_index in consumed_indexes:
                    continue
                if _normalize_name(add_signature["character_name"]) == _normalize_name(remove_signature["character_name"]):
                    continue
                selected_add = (add_index, add_signature)
                break

            if selected_add is None:
                continue

            add_index, add_signature = selected_add
            consumed_indexes.add(remove_index)
            consumed_indexes.add(add_index)
            transfer_pairs.append(
                {
                    "item_name": remove_signature["item_name"],
                    "quantity": remove_signature["quantity"],
                    "giver_name": remove_signature["character_name"],
                    "receiver_name": add_signature["character_name"],
                    "remove_action": remove_signature["action"],
                    "add_action": add_signature["action"],
                }
            )

    remaining_actions = [action for index, action in enumerate(actions) if index not in consumed_indexes]
    return (transfer_pairs, remaining_actions)


def execute_atomic_transfer_pair(
    pair: Dict[str, Any],
    apply_update_fn: Callable[[Dict[str, Any]], Any],
    load_state_fn: Callable[[str], Optional[Dict[str, Any]]],
    save_state_fn: Callable[[str, Dict[str, Any]], bool],
) -> Dict[str, Any]:
    """Execute a transfer pair atomically with rollback on failure."""
    giver_name = str(pair.get("giver_name") or "").strip()
    receiver_name = str(pair.get("receiver_name") or "").strip()
    if not giver_name or not receiver_name:
        return {"ok": False, "error": "Atomic transfer missing giver or receiver."}

    giver_snapshot = load_state_fn(giver_name)
    receiver_snapshot = load_state_fn(receiver_name)
    if not isinstance(giver_snapshot, dict) or not isinstance(receiver_snapshot, dict):
        return {
            "ok": False,
            "error": f"Atomic transfer snapshot unavailable for giver={giver_name} receiver={receiver_name}.",
        }

    snapshots = {
        giver_name: giver_snapshot,
        receiver_name: receiver_snapshot,
    }

    def _rollback() -> None:
        for character_name, state_payload in snapshots.items():
            save_state_fn(character_name, state_payload)

    add_result = apply_update_fn(pair.get("add_action", {}))
    if isinstance(add_result, dict) and add_result.get("status") == "error":
        _rollback()
        return {
            "ok": False,
            "error": str(add_result.get("error_message") or "Atomic transfer receiver update failed."),
        }

    remove_result = apply_update_fn(pair.get("remove_action", {}))
    if isinstance(remove_result, dict) and remove_result.get("status") == "error":
        _rollback()
        return {
            "ok": False,
            "error": str(remove_result.get("error_message") or "Atomic transfer giver update failed."),
        }

    return {"ok": True, "needs_update": True}
