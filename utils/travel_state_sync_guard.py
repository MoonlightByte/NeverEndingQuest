# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Travel State Sync Guard - Deterministic travel narration/state validation
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Ensures clear travel-intent narration does not drift from persisted location state.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


_MOVEMENT_COMMITMENT_PATTERNS = [
    r"\b(?:you|we|party)\s+travel(?:s|ed|ing)?\b",
    r"\b(?:you|we|party)\s+journey(?:s|ed|ing)?\b",
    r"\b(?:you|we|party)\s+head(?:s|ed|ing)?\b",
    r"\b(?:you|we|party)\s+move(?:s|d|ing)?\b",
    r"\b(?:you|we|party)\s+walk(?:s|ed|ing)?\b",
    r"\b(?:you|we|party)\s+run(?:s|ning)?\b",
    r"\b(?:you|we|party)\s+proceed(?:s|ed|ing)?\b",
    r"\b(?:you|we|party)\s+enter(?:s|ed|ing)?\b",
    r"\b(?:you|we|party)\s+descend(?:s|ed|ing)?\b",
    r"\b(?:you|we|party)\s+climb(?:s|ed|ing)?\b",
    r"\b(?:you|we|party)\s+follow(?:s|ed|ing)?\b",
    r"\barriv(?:e|es|ed|ing)\b",
    r"\breach(?:es|ed|ing)?\b",
    r"\bemerge(?:s|d|ing)?\b",
    r"\bstep(?:s|ped|ping)?\s+(?:into|through|up|down)\b",
]


_BLOCKER_OR_ABORT_PATTERNS = [
    r"\bblocked\b",
    r"\bcannot\b",
    r"\bcan't\b",
    r"\bunable\b",
    r"\bimpassable\b",
    r"\bno\s+(?:path|way|route)\b",
    r"\bdead\s+end\b",
    r"\bsealed\b",
    r"\bloops?\b",
    r"\bback\s+where\s+(?:you|we)\s+started\b",
    r"\bremain(?:s|ed)?\s+(?:at|here)\b",
    r"\bstill\s+(?:at|here)\b",
]


_CLARIFICATION_PATTERNS = [
    r"\bwhich\s+(?:path|way|route|direction)\b",
    r"\bwhere\s+(?:do|would)\s+(?:you|we)\b",
    r"\bchoose\s+(?:a|the)?\s*(?:path|route|direction|destination)\b",
    r"\bclarify\b",
    r"\bdo\s+you\s+want\s+to\b",
]


def _normalize_text(value: str) -> str:
    """Normalize freeform text to lowercase alphanumeric tokens."""
    lowered = value.lower().strip()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _contains_any_pattern(text: str, patterns: List[str]) -> bool:
    """Return True when any regex pattern matches text."""
    return any(re.search(pattern, text) for pattern in patterns)


def _has_transition_location_action(response_json: Dict[str, Any]) -> bool:
    """Return True if response actions include transitionLocation."""
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return False

    for action in actions:
        if isinstance(action, dict) and action.get("action") == "transitionLocation":
            return True
    return False


def _extract_location_mentions(normalized_narration: str, known_location_names: List[str]) -> Set[str]:
    """Return normalized known location names explicitly mentioned in narration."""
    mentions: Set[str] = set()
    padded_narration = f" {normalized_narration} "
    for location_name in known_location_names:
        normalized_name = _normalize_text(location_name)
        if not normalized_name or len(normalized_name) < 3:
            continue
        if f" {normalized_name} " in padded_narration:
            mentions.add(normalized_name)
    return mentions


def _is_current_location_blocker_or_clarifier(normalized_narration: str) -> bool:
    """Return True if narration explicitly blocks/defers movement."""
    if _contains_any_pattern(normalized_narration, _BLOCKER_OR_ABORT_PATTERNS):
        return True

    if _contains_any_pattern(normalized_narration, _CLARIFICATION_PATTERNS):
        return True

    return False


def evaluate_travel_state_sync_guard(
    response_json: Dict[str, Any],
    is_travel_intent: bool,
    current_location_name: str,
    known_location_names: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Validate travel narration/state sync for clear travel-intent turns.

    Returns:
        (True, "") when guard passes.
        (False, reason) when deterministic contradiction is detected.
    """
    if not is_travel_intent:
        return True, ""

    if _has_transition_location_action(response_json):
        return True, ""

    narration = str(response_json.get("narration", "") or "")
    normalized_narration = _normalize_text(narration)

    location_names = list(known_location_names or [])
    if current_location_name:
        location_names.append(current_location_name)

    mentions = _extract_location_mentions(normalized_narration, location_names)
    normalized_current = _normalize_text(current_location_name)
    current_mentioned = bool(normalized_current and normalized_current in mentions)
    non_current_mentions = sorted(name for name in mentions if name != normalized_current)

    if _is_current_location_blocker_or_clarifier(normalized_narration) and not non_current_mentions:
        return True, ""

    movement_commitment = _contains_any_pattern(normalized_narration, _MOVEMENT_COMMITMENT_PATTERNS)
    if not movement_commitment:
        return True, ""

    if current_mentioned and non_current_mentions:
        return (
            False,
            "travel state sync guard: contradictory mixed-location travel narration without transitionLocation",
        )

    return (
        False,
        "travel state sync guard: clear travel narration requires transitionLocation action or explicit current-location blocker/clarifier",
    )
