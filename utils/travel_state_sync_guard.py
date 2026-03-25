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


_SCENE_PRESENCE_PATTERNS = [
    r"\byou\s+(?:are|stand|remain|wait)(?:\s+now)?\s+(?:in|inside|within|at)\b",
    r"\bthe\s+party\s+(?:is|stands|remains)\s+(?:in|inside|within|at)\b",
    r"\bcurrently\s+(?:in|at)\b",
]


_DEPARTURE_PATTERNS = [
    r"\bfrom\b",
    r"\bleave(?:s|s|d|ing)?\b",
    r"\bexit(?:s|ed|ing)?\b",
]


_SCENE_LOCATION_SYNC_VERBS = [
    r"\bhail\b",
    r"\bcall\b",
    r"\bspeak\b",
    r"\btalk\b",
    r"\bask\b",
    r"\bparlay\b",
    r"\bapproach\b",
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
    ambiguous_aliases: Set[str] = set()

    def _register_alias(alias_raw: str, entry: Dict[str, str]) -> None:
        normalized_alias = _normalize_text(alias_raw)
        if not normalized_alias:
            return

        existing_entry = catalog.get(normalized_alias)
        if existing_entry is None:
            catalog[normalized_alias] = dict(entry)
            return

        existing_id = str(existing_entry.get("id", "") or "").strip()
        new_id = str(entry.get("id", "") or "").strip()
        if existing_id and new_id and existing_id != new_id:
            ambiguous_aliases.add(normalized_alias)
            return

        if not existing_id and new_id:
            catalog[normalized_alias] = dict(entry)

    def _alias_candidates(raw_name: str, source_room_title: str = "") -> List[str]:
        aliases = [raw_name]
        room_prefix_stripped = re.sub(r"^room\s+\d+\s*:\s*", "", raw_name, flags=re.IGNORECASE).strip()
        if room_prefix_stripped:
            aliases.append(room_prefix_stripped)

        if source_room_title:
            aliases.append(source_room_title)

        aliases_with_article_variants: List[str] = []
        for alias in aliases:
            aliases_with_article_variants.append(alias)
            alias_normalized = _normalize_text(alias)
            if alias_normalized.startswith("the "):
                aliases_with_article_variants.append(alias[4:].strip())

        normalized_unique = []
        seen_normalized: Set[str] = set()
        for alias in aliases_with_article_variants:
            normalized_alias = _normalize_text(alias)
            if not normalized_alias or normalized_alias in seen_normalized:
                continue
            seen_normalized.add(normalized_alias)
            normalized_unique.append(alias)
        return normalized_unique

    if isinstance(known_locations, list):
        for location in known_locations:
            if not isinstance(location, dict):
                continue
            raw_name = str(location.get("name", "") or "").strip()
            if not raw_name:
                continue

            location_id = str(location.get("id", "") or "").strip()
            area_id = str(location.get("area_id", "") or "").strip()
            area_name = str(location.get("area_name", "") or "").strip()
            source_room_title = str(location.get("source_room_title", "") or "").strip()

            location_entry = {
                "name": raw_name,
                "id": location_id,
                "area_id": area_id,
                "area_name": area_name,
            }

            for alias in _alias_candidates(raw_name, source_room_title):
                _register_alias(alias, location_entry)

    for location_name in known_location_names or []:
        raw_name = str(location_name or "").strip()
        if not raw_name:
            continue

        location_entry = {
            "name": raw_name,
            "id": "",
            "area_id": "",
            "area_name": "",
        }
        for alias in _alias_candidates(raw_name):
            _register_alias(alias, location_entry)

    for ambiguous_alias in ambiguous_aliases:
        if ambiguous_alias in catalog:
            del catalog[ambiguous_alias]

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


def _has_explicit_location_commit_action(response_json: Dict[str, Any]) -> bool:
    """Return True when response already includes explicit location commit action."""
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return False

    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = action.get("action")
        if action_type == "transitionLocation":
            return True
        if action_type == "updatePartyTracker":
            parameters = action.get("parameters", {})
            if isinstance(parameters, dict) and parameters.get("currentLocationId"):
                return True
    return False


def _has_explicit_update_time_action(response_json: Dict[str, Any]) -> bool:
    """Return True when response already includes explicit updateTime."""
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return False

    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action") == "updateTime":
            return True
    return False


def evaluate_scene_plot_location_reconciliation_decision(
    response_json: Dict[str, Any],
    current_location_id: str,
    plot_data: Optional[Dict[str, Any]] = None,
    module_locations: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Infer canonical current location from unique same-turn plot or encounter evidence."""
    if _has_explicit_location_commit_action(response_json):
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    actions = response_json.get("actions", [])
    if not isinstance(actions, list) or not isinstance(plot_data, dict):
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    module_location_index: Dict[str, Dict[str, str]] = {}
    for location in module_locations or []:
        if not isinstance(location, dict):
            continue
        location_id = str(location.get("id", "") or "").strip()
        location_name = str(location.get("name", "") or "").strip()
        if not location_id or not location_name:
            continue
        module_location_index[location_id] = {
            "id": location_id,
            "name": location_name,
            "area_id": str(location.get("area_id", "") or "").strip(),
            "area_name": str(location.get("area_name", "") or "").strip(),
        }

    if not module_location_index:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    plot_location_map: Dict[str, str] = {}
    for plot_point in plot_data.get("plotPoints", []):
        if not isinstance(plot_point, dict):
            continue
        plot_point_id = str(plot_point.get("id", "") or "").strip()
        location_id = str(plot_point.get("location", "") or "").strip()
        if plot_point_id and location_id:
            plot_location_map[plot_point_id] = location_id

    candidate_location_ids: List[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("action", "") or "").strip()
        parameters = action.get("parameters", {})
        if not isinstance(parameters, dict):
            continue

        if action_type == "updatePlot":
            plot_point_id = str(parameters.get("plotPointId", "") or "").strip()
            mapped_location_id = plot_location_map.get(plot_point_id, "")
            if mapped_location_id and mapped_location_id in module_location_index and mapped_location_id != current_location_id:
                candidate_location_ids.append(mapped_location_id)
        elif action_type == "updateEncounter":
            encounter_id = str(parameters.get("encounterId", "") or "").strip()
            encounter_location_id = encounter_id.split("-E", 1)[0].strip() if "-E" in encounter_id else ""
            if encounter_location_id and encounter_location_id in module_location_index and encounter_location_id != current_location_id:
                candidate_location_ids.append(encounter_location_id)

    unique_candidates = sorted(set(candidate_location_ids))
    if len(unique_candidates) != 1:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    destination_id = unique_candidates[0]
    destination_entry = module_location_index.get(destination_id, {})
    destination_name = str(destination_entry.get("name", "") or "").strip()
    if not destination_name:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    inferred_action = {
        "action": "updatePartyTracker",
        "parameters": {
            "currentLocationId": destination_id,
            "currentLocation": destination_name,
            "currentAreaId": str(destination_entry.get("area_id", "") or "").strip(),
            "currentArea": str(destination_entry.get("area_name", "") or "").strip(),
        },
    }
    return {
        "valid": True,
        "inferred_actions": [inferred_action],
        "reconciliation": "scene_plot_location_sync",
    }


def evaluate_narrated_location_arrival_decision(
    response_json: Dict[str, Any],
    current_location_id: str,
    current_area_id: str = "",
    known_location_names: Optional[List[str]] = None,
    module_locations: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Infer party location commit from explicit narrated arrival into one known location."""
    if _has_explicit_location_commit_action(response_json):
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    narration = str(response_json.get("narration", "") or "")
    normalized_narration = _normalize_text(narration)
    if not normalized_narration:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    if not _contains_any_pattern(normalized_narration, _ARRIVAL_PATTERNS):
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    location_catalog = _build_location_catalog(module_locations, known_location_names)
    if not location_catalog:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    mentions = _extract_location_mentions(normalized_narration, list(location_catalog.keys()))
    if len(mentions) != 1:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    candidate_ids: List[str] = []
    for mention in mentions:
        location_entry = location_catalog.get(mention, {})
        location_id = str(location_entry.get("id", "") or "").strip()
        if not location_id or location_id == current_location_id:
            continue
        candidate_ids.append(location_id)

    unique_ids = sorted(set(candidate_ids))
    if len(unique_ids) != 1:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    destination_id = unique_ids[0]
    destination_entry = None
    for _, entry in location_catalog.items():
        if str(entry.get("id", "") or "").strip() == destination_id:
            destination_entry = entry
            break

    if not isinstance(destination_entry, dict):
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    destination_name = str(destination_entry.get("name", "") or "").strip()
    destination_area_id = str(destination_entry.get("area_id", "") or "").strip()
    destination_area_name = str(destination_entry.get("area_name", "") or "").strip()
    if not destination_name:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    inferred_actions: List[Dict[str, Any]] = []
    if not _has_explicit_update_time_action(response_json):
        is_same_area = bool(
            current_area_id
            and destination_area_id
            and current_area_id == destination_area_id
        )
        inferred_actions.append(
            {
                "action": "updateTime",
                "parameters": {
                    "timeEstimate": 10 if is_same_area else 20,
                },
            }
        )

    inferred_action = {
        "action": "updatePartyTracker",
        "parameters": {
            "currentLocationId": destination_id,
            "currentLocation": destination_name,
            "currentAreaId": destination_area_id,
            "currentArea": destination_area_name,
        },
    }
    inferred_actions.append(inferred_action)
    return {
        "valid": True,
        "inferred_actions": inferred_actions,
        "reconciliation": "narrated_location_arrival_sync",
    }


def evaluate_startup_scene_location_recovery_decision(
    conversation_history: List[Dict[str, Any]],
    current_location_id: str,
    current_area_id: str = "",
    known_location_names: Optional[List[str]] = None,
    module_locations: Optional[List[Dict[str, Any]]] = None,
    max_messages: int = 12,
) -> Dict[str, Any]:
    """Recover stale startup location from recent uniquely resolved scene evidence."""
    if not isinstance(conversation_history, list) or not current_location_id:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    location_catalog = _build_location_catalog(module_locations, known_location_names)
    if not location_catalog:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    candidate_location_ids: List[str] = []
    recent_entries: List[Dict[str, Any]] = []

    for entry in reversed(conversation_history):
        if len(recent_entries) >= max_messages:
            break
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "")
        if role not in {"assistant", "user"}:
            continue
        content = entry.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        recent_entries.append(entry)

    if not recent_entries:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    for entry in recent_entries:
        normalized_content = _normalize_text(str(entry.get("content") or ""))
        if not normalized_content:
            continue

        mentions = _extract_location_mentions(normalized_content, list(location_catalog.keys()))
        if len(mentions) != 1:
            continue

        mention = next(iter(mentions))
        location_entry = location_catalog.get(mention, {})
        location_id = str(location_entry.get("id", "") or "").strip()
        if not location_id or location_id == current_location_id:
            continue

        progress_signal = _contains_any_pattern(normalized_content, _PROGRESS_PATTERNS)
        arrival_signal = _contains_any_pattern(normalized_content, _ARRIVAL_PATTERNS)
        presence_signal = _contains_any_pattern(normalized_content, _SCENE_PRESENCE_PATTERNS)
        if progress_signal and not arrival_signal and not presence_signal:
            continue
        if not arrival_signal and not presence_signal:
            continue

        candidate_location_ids.append(location_id)

    unique_candidates = sorted(set(candidate_location_ids))
    if len(unique_candidates) != 1:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    destination_id = unique_candidates[0]
    destination_entry = None
    for _, entry in location_catalog.items():
        if str(entry.get("id", "") or "").strip() == destination_id:
            destination_entry = entry
            break

    if not isinstance(destination_entry, dict):
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    destination_name = str(destination_entry.get("name", "") or "").strip()
    destination_area_id = str(destination_entry.get("area_id", "") or "").strip() or current_area_id
    destination_area_name = str(destination_entry.get("area_name", "") or "").strip()
    if not destination_name:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    inferred_action = {
        "action": "updatePartyTracker",
        "parameters": {
            "currentLocationId": destination_id,
            "currentLocation": destination_name,
            "currentAreaId": destination_area_id,
            "currentArea": destination_area_name,
        },
    }
    return {
        "valid": True,
        "inferred_actions": [inferred_action],
        "reconciliation": "startup_scene_location_recovery",
    }


def _user_addresses_npc_in_scene(user_utterance: str, npc_name: str) -> bool:
    """Return True when the player directly addresses or calls to the NPC."""
    normalized_utterance = _normalize_text(user_utterance)
    normalized_npc_name = _normalize_text(npc_name)
    if not normalized_utterance or not normalized_npc_name:
        return False

    last_token = normalized_npc_name.split()[-1] if normalized_npc_name.split() else ""
    mentions_npc = (
        f" {normalized_npc_name} " in f" {normalized_utterance} " or
        (len(last_token) >= 3 and f" {last_token} " in f" {normalized_utterance} ")
    )
    if not mentions_npc:
        return False
    return _contains_any_pattern(normalized_utterance, _SCENE_LOCATION_SYNC_VERBS)


def evaluate_scene_location_sync_decision(
    response_json: Dict[str, Any],
    user_utterance: str,
    current_location_id: str,
    module_locations: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Infer current-scene location sync from explicit NPC scene interaction."""
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    has_transition = any(isinstance(action, dict) and action.get("action") == "transitionLocation" for action in actions)
    has_location_update = any(
        isinstance(action, dict)
        and action.get("action") == "updatePartyTracker"
        and isinstance(action.get("parameters"), dict)
        and action.get("parameters", {}).get("currentLocationId")
        for action in actions
    )
    if has_transition or has_location_update:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    module_location_map: Dict[str, Dict[str, str]] = {}
    for entry in module_locations or []:
        if not isinstance(entry, dict):
            continue
        location_id = str(entry.get("id", "") or "").strip()
        if not location_id:
            continue
        module_location_map[location_id] = {
            "name": str(entry.get("name", "") or "").strip(),
            "area_id": str(entry.get("area_id", "") or "").strip(),
            "area_name": str(entry.get("area_name", "") or "").strip(),
        }

    candidate_targets: List[Tuple[str, str]] = []
    for action in actions:
        if not isinstance(action, dict) or action.get("action") != "moveBackgroundNPC":
            continue
        parameters = action.get("parameters", {})
        if not isinstance(parameters, dict):
            continue
        target_location_id = str(parameters.get("currentLocation", "") or "").strip()
        npc_name = str(parameters.get("npcName", "") or "").strip()
        if not target_location_id or not npc_name or target_location_id == current_location_id:
            continue
        if target_location_id not in module_location_map:
            continue
        if not _user_addresses_npc_in_scene(user_utterance, npc_name):
            continue
        candidate_targets.append((target_location_id, npc_name))

    unique_target_ids = sorted({target_id for target_id, _ in candidate_targets})
    if len(unique_target_ids) != 1:
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    target_id = unique_target_ids[0]
    target_entry = module_location_map.get(target_id, {})
    if not target_entry.get("name"):
        return {"valid": True, "inferred_actions": [], "reconciliation": "none"}

    inferred_action = {
        "action": "updatePartyTracker",
        "parameters": {
            "currentLocationId": target_id,
            "currentLocation": target_entry.get("name", ""),
            "currentAreaId": target_entry.get("area_id", ""),
            "currentArea": target_entry.get("area_name", ""),
        },
    }
    return {
        "valid": True,
        "inferred_actions": [inferred_action],
        "reconciliation": "scene_location_sync",
    }


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
