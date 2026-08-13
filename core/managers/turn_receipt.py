# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Truthful per-response receipts built only from committed runtime facts."""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, Mapping, Sequence


def _deduplicate(values):
    result = []
    seen = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(copy.deepcopy(value))
    return result


class TurnReceiptBuilder:
    """Accumulate only commits that have already crossed a durable boundary."""

    def __init__(self, correlation_id: str, intended_action_indices: Sequence[int]):
        self.correlation_id = str(correlation_id or "unknown")[:64]
        self.intended_action_indices = tuple(
            sorted(
                {
                    value
                    for value in intended_action_indices
                    if type(value) is int and 0 <= value <= 4096
                }
            )
        )
        self._committed = set()
        self._transaction_ids = []
        self._participants = []
        self._resource_deltas = []
        self._advisories = set()

    def record_resource_commit(
        self,
        result: Mapping[str, Any],
        action_indices: Sequence[int],
    ) -> None:
        if not isinstance(result, Mapping) or result.get("success") is not True:
            return
        self._committed.update(
            value
            for value in action_indices
            if type(value) is int and 0 <= value <= 4096
        )
        transaction_id = result.get("transaction_id")
        if isinstance(transaction_id, str) and transaction_id:
            self._transaction_ids.append(transaction_id[:160])
        participants = result.get("participants")
        if isinstance(participants, list):
            self._participants.extend(
                value for value in participants if isinstance(value, dict)
            )
        deltas = result.get("resource_deltas")
        if isinstance(deltas, list):
            self._resource_deltas.extend(
                value for value in deltas if isinstance(value, dict)
            )
        advisories = result.get("advisories")
        if isinstance(advisories, (list, tuple, set, frozenset)):
            self._advisories.update(
                str(value)[:160] for value in advisories if value
            )

    def record_action_commit(self, index: int, result: Any) -> None:
        if type(index) is not int:
            return
        if result is True:
            self._committed.add(index)
            return
        if not isinstance(result, Mapping):
            return
        if result.get("status") == "error" or result.get("success") is False:
            return
        if not (
            result.get("needs_update") is True
            or result.get("state_changed") is True
            or result.get("transaction_id")
        ):
            return
        self._committed.add(index)
        transaction_id = result.get("transaction_id")
        if isinstance(transaction_id, str) and transaction_id:
            self._transaction_ids.append(transaction_id[:160])

    def finalize(self, *, success: bool) -> Dict[str, Any]:
        return {
            "correlationId": self.correlation_id,
            "intendedActionIndices": list(self.intended_action_indices),
            "committedActionIndices": sorted(self._committed),
            "transactionIds": sorted(set(self._transaction_ids)),
            "participants": _deduplicate(self._participants),
            "resourceDeltas": _deduplicate(self._resource_deltas),
            "advisories": sorted(self._advisories),
            "success": bool(success),
        }


def diegetic_failure_correction(action: Mapping[str, Any], receipt: Mapping[str, Any]):
    """Describe the already-known failure outcome without system vocabulary."""
    action_name = str(action.get("action") or "") if isinstance(action, Mapping) else ""
    committed = receipt.get("committedActionIndices") or []
    if committed:
        return (
            "The moment catches before everything can unfold as first described. "
            "What has already changed hands remains so, but the rest of the exchange "
            "does not come together."
        )
    if action_name == "storageInteraction":
        return (
            "Hands pause over the open container, and the exchange does not come "
            "together; its contents remain just where they were."
        )
    if action_name == "updateCharacterInfo":
        return (
            "The exchange falters at the last moment. Every coin and piece of gear "
            "remains where it was, and no bargain is struck."
        )
    return (
        "The moment hangs unresolved, and events do not unfold as first described."
    )
