# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Validation Routing Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Helpers for deterministic validation routing decisions.
"""

from typing import Any, Dict, List, Tuple


HIGH_RISK_ACTIONS = {
    "createEncounter",
    "transitionLocation",
    "updatePartyTracker",
    "moveBackgroundNPC",
    "updatePartyNPCs",
    "createNewModule",
    "restoreGame",
    "deleteSave",
    "updateEncounter",
    "levelUp",
    "exitGame",
}

LOW_RISK_SKIP_ACTIONS = {
    "updateTime",
    "saveGame",
    "listSaves",
}


def _extract_action_names(response_json: Dict[str, Any]) -> List[str]:
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return []

    action_names: List[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_name = action.get("action")
        if isinstance(action_name, str) and action_name.strip():
            action_names.append(action_name.strip())
    return action_names


def should_compress_validation_context(
    total_chars: int,
    compression_enabled: bool,
    threshold_chars: int,
) -> bool:
    """Return True when validation context should be compressed."""
    should_compress, _reason = get_validation_compression_decision(
        total_chars=total_chars,
        compression_enabled=compression_enabled,
        threshold_chars=threshold_chars,
    )
    return should_compress


def get_validation_compression_decision(
    total_chars: int,
    compression_enabled: bool,
    threshold_chars: int,
) -> Tuple[bool, str]:
    """Return compression decision with deterministic reason code."""
    if not compression_enabled:
        return (False, "compression_disabled")
    if threshold_chars <= 0:
        return (True, "threshold_disabled")
    if total_chars >= threshold_chars:
        return (True, "at_or_above_threshold")
    return (False, "below_threshold")


def should_skip_llm_validation(
    response_json: Dict[str, Any],
    deterministic_passed: bool,
) -> Tuple[bool, str]:
    """Conservative skip decision for low-risk turns.

    Returns (should_skip, reason).
    """
    if not deterministic_passed:
        return (False, "deterministic_failed")

    action_names = _extract_action_names(response_json)
    if not action_names:
        return (True, "narration_only")

    for action_name in action_names:
        if action_name in HIGH_RISK_ACTIONS:
            return (False, f"high_risk_action:{action_name}")

    for action_name in action_names:
        if action_name not in LOW_RISK_SKIP_ACTIONS:
            return (False, f"non_low_risk_action:{action_name}")

    return (True, "low_risk_actions_only")


def build_validation_routing_telemetry(
    skip_llm_validation: bool,
    skip_reason: str,
    used_validation_compression: bool,
    compression_reason: str,
    validation_payload_chars: int,
) -> Dict[str, Any]:
    """Build normalized validation routing telemetry payload."""
    return {
        "skip_llm_validation": bool(skip_llm_validation),
        "skip_reason": str(skip_reason),
        "used_validation_compression": bool(used_validation_compression),
        "compression_reason": str(compression_reason),
        "validation_payload_chars": int(validation_payload_chars),
    }
