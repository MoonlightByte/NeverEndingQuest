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
    r"\bmake\s+(?:your|our)\s+way\b",
]


_ARRIVAL_PATTERNS = [
    r"\barriv(?:e|es|ed|ing)\b",
    r"\breach(?:es|ed|ing)?\b",
    r"\bemerge(?:s|d|ing)?\b",
    r"\benter(?:s|ed|ing)?\b",
    r"\bstep(?:s|ped|ping)?\s+(?:into|through|up|down)\b",
]


_PROGRESS_PATTERNS = [
    r"\btoward(?:s)?\b",
    r"\bon\s+(?:the\s+)?way\s+to\b",
    r"\bmaking\s+(?:your|our)\s+way\s+to\b",
    r"\bheading\s+to\b",
    r"\btravel(?:s|ed|ing)?\s+to\b",
]


_DEPARTURE_PATTERNS = [
    r"\bfrom\b",
    r"\bleave(?:s|s|d|ing)?\b",
    r"\bexit(?:s|ed|ing)?\b",
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


def _build_location_catalog(known_locations: Optional[List[Dict[str, Any]]], known_location_names: Optional[List[str]]) -> Dict[str, Dict[str, str]]:
    """Build normalized location catalog keyed by normalized location name."""
    catalog: Dict[str, Dict[str, str]] = {}

    if isinstance(known_locations, list):
        for location in known_locations:
            if not isinstance(location, dict):
                continue
            raw_name = str(location.get("name", "") or "").strip()
            normalized_name = _normalize_text(raw_name)
            if not normalized_name:
                continue

            location_id = str(location.get("id", "") or "").strip()
            area_id = str(location.get("area_id", "") or "").strip()

            catalog[normalized_name] = {
                "name": raw_name,
                "id": location_id,
                "area_id": area_id,
            }

    for location_name in known_location_names or []:
        raw_name = str(location_name or "").strip()
        normalized_name = _normalize_text(raw_name)
        if not normalized_name:
            continue
        if normalized_name not in catalog:
            catalog[normalized_name] = {
                "name": raw_name,
                "id": "",
                "area_id": "",
            }

    return catalog


def _is_topology_safe_destination(
    destination_id: str,
    current_location_id: str,
    adjacent_location_ids: Optional[List[str]],
    reachable_location_ids: Optional[List[str]],
) -> bool:
    """Return True when destination is resolvable and topology-safe."""
    if not destination_id:
        return False

    if current_location_id and destination_id == current_location_id:
        return False

    adjacent_ids = set(adjacent_location_ids or [])
    if adjacent_ids and destination_id in adjacent_ids:
        return True

    reachable_ids = set(reachable_location_ids or [])
    if reachable_ids and destination_id in reachable_ids:
        return True

    return False


def evaluate_travel_state_sync_decision(
    response_json: Dict[str, Any],
    is_travel_intent: bool,
    current_location_name: str,
    current_location_id: str = "",
    known_location_names: Optional[List[str]] = None,
    known_locations: Optional[List[Dict[str, Any]]] = None,
    adjacent_location_ids: Optional[List[str]] = None,
    reachable_location_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Evaluate travel state sync and return reconcile-first decision details."""
    if not is_travel_intent:
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [],
            "reconciliation": "none",
        }

    if _has_transition_location_action(response_json):
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [],
            "reconciliation": "explicit_transition",
        }

    narration = str(response_json.get("narration", "") or "")
    normalized_narration = _normalize_text(narration)
    movement_commitment = _contains_any_pattern(normalized_narration, _MOVEMENT_COMMITMENT_PATTERNS)

    if not movement_commitment:
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [],
            "reconciliation": "none",
        }

    normalized_current_name = _normalize_text(current_location_name)
    location_catalog = _build_location_catalog(known_locations, known_location_names)
    known_names = list(location_catalog.keys())
    mentions = _extract_location_mentions(normalized_narration, known_names)

    current_mentioned = bool(normalized_current_name and normalized_current_name in mentions)
    non_current_mentions = sorted(name for name in mentions if name != normalized_current_name)

    arrival_signal = _contains_any_pattern(normalized_narration, _ARRIVAL_PATTERNS)
    progress_signal = _contains_any_pattern(normalized_narration, _PROGRESS_PATTERNS)
    departure_signal = _contains_any_pattern(normalized_narration, _DEPARTURE_PATTERNS)

    if current_mentioned and len(non_current_mentions) == 1 and arrival_signal and not departure_signal:
        return {
            "valid": False,
            "reason": "travel state sync guard: contradictory mixed-location travel narration without resolvable movement progression",
            "inferred_actions": [],
            "reconciliation": "none",
        }

    if _is_current_location_blocker_or_clarifier(normalized_narration) and not non_current_mentions:
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [],
            "reconciliation": "blocker_or_clarifier",
        }

    if not non_current_mentions:
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [],
            "reconciliation": "none",
        }

    if len(non_current_mentions) > 1:
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [],
            "reconciliation": "ambiguous_destination",
        }

    destination_normalized = non_current_mentions[0]
    destination_entry = location_catalog.get(destination_normalized, {})
    destination_id = str(destination_entry.get("id", "") or "").strip()
    destination_name = str(destination_entry.get("name", "") or "").strip() or destination_normalized

    if normalized_current_name and destination_normalized == normalized_current_name:
        return {
            "valid": False,
            "reason": "travel state sync guard: same-location travel commit is not allowed",
            "inferred_actions": [],
            "reconciliation": "none",
        }

    if not _is_topology_safe_destination(
        destination_id=destination_id,
        current_location_id=current_location_id,
        adjacent_location_ids=adjacent_location_ids,
        reachable_location_ids=reachable_location_ids,
    ):
        return {
            "valid": False,
            "reason": f"travel state sync guard: destination '{destination_name}' is not topology-safe from current location",
            "inferred_actions": [],
            "reconciliation": "none",
        }

    if arrival_signal:
        inferred_transition = {
            "action": "transitionLocation",
            "parameters": {
                "newLocation": destination_id,
            },
        }
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [inferred_transition],
            "reconciliation": "arrival_autocommit",
        }

    if progress_signal or movement_commitment:
        progress_payload = {
            "mode": "in_transit",
            "targetLocationId": destination_id,
            "targetLocationName": destination_name,
            "sourceLocationId": current_location_id,
            "sourceLocationName": current_location_name,
        }
        inferred_update_time = {
            "action": "updateTime",
            "parameters": {
                "timeEstimate": 10,
            },
        }
        inferred_progress = {
            "action": "updatePartyTracker",
            "parameters": {
                "worldConditions": {
                    "travelProgress": progress_payload,
                },
            },
        }
        return {
            "valid": True,
            "reason": "",
            "inferred_actions": [inferred_update_time, inferred_progress],
            "reconciliation": "progress_in_transit",
        }

    return {
        "valid": True,
        "reason": "",
        "inferred_actions": [],
        "reconciliation": "none",
    }


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
    current_location_id: str = "",
    known_location_names: Optional[List[str]] = None,
    known_locations: Optional[List[Dict[str, Any]]] = None,
    adjacent_location_ids: Optional[List[str]] = None,
    reachable_location_ids: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Validate travel narration/state sync for clear travel-intent turns.

    Returns:
        (True, "") when guard passes.
        (False, reason) when deterministic contradiction is detected.
    """
    decision = evaluate_travel_state_sync_decision(
        response_json=response_json,
        is_travel_intent=is_travel_intent,
        current_location_name=current_location_name,
        current_location_id=current_location_id,
        known_location_names=known_location_names,
        known_locations=known_locations,
        adjacent_location_ids=adjacent_location_ids,
        reachable_location_ids=reachable_location_ids,
    )
    return bool(decision.get("valid", True)), str(decision.get("reason", "") or "")
