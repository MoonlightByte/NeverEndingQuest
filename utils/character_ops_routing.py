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
            normalized.append(op)
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
