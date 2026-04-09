# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Narrator Location Exclusivity Guard
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Deterministic contradiction-class checks for narrator location truth:
- metadata-first location-exclusive present-scene leakage
- legacy Thornwood NC01/NC05 fallback (migration safety)
- unsupported route-blocking narration on authored adjacent exits
"""

import re
from typing import Any, Dict, List, Optional


_THORNWOOD_MODULE_ALIASES = {
    "the_thornwood_watch",
    "the thornwood watch",
    "thornwood_watch",
    "thornwood",
}

_NC05_PRESENT_PATTERNS = [
    r"\bmalarok\b.{0,48}\b(?:stands?|waits?|looms?|faces?|confronts?)\b",
    r"\b(?:stands?|waits?|looms?|faces?|confronts?)\b.{0,32}\bmalarok\b",
    r"\bmalarok\b.{0,40}\bbefore you\b",
    r"\b(?:you|the party)\b.{0,40}\bsee\b.{0,24}\bmalarok\b",
    r"\bvoidstone\b.{0,50}\b(?:altar|shard|confrontation)\b.{0,36}\b(?:before you|in front of you|in this chamber|right here|at your feet)\b",
    r"\b(?:altar|voidstone)\b.{0,48}\b(?:before you|in front of you|in this chamber|right here|at your feet)\b",
]

_FORESHADOW_PATTERNS = [
    r"\bdeeper\s+ahead\b",
    r"\bin\s+the\s+distance\b",
    r"\bdistant\b",
    r"\byou\s+sense\b",
    r"\byou\s+feel\b",
    r"\bwhispers?\b",
    r"\bseems?\s+to\s+come\s+from\b",
    r"\bsomewhere\s+ahead\b",
]

_PRESENT_SCENE_VERB_PATTERN = (
    r"(?:stands?|waits?|looms?|faces?|confronts?|appears?|emerges?|is(?:\s+here)?)"
)

_STRONG_PRESENT_MARKERS = [
    "before you",
    "in front of you",
    "in this chamber",
    "right here",
    "at your feet",
    "stands before",
    "faces you",
]

_BLOCKER_PATTERNS = [
    r"\bblocked\b",
    r"\bimpassable\b",
    r"\bsealed\b",
    r"\bcannot\s+proceed\b",
    r"\bcan\'?t\s+proceed\b",
    r"\bno\s+(?:way|path|route|passage)\b",
    r"\broute\s+is\s+closed\b",
    r"\bpath\s+is\s+closed\b",
]

_ROUTE_CONTEXT_PATTERNS = [
    r"\bpath\b",
    r"\broute\b",
    r"\bpassage\b",
    r"\bexit\b",
    r"\btunnel\b",
    r"\bway\s+to\b",
    r"\btoward(?:s)?\b",
]

_BLOCKER_METADATA_KEYS = {
    "blockedRoutes",
    "blockedRouteIds",
    "blockedExits",
    "routeBlocks",
    "blockedPaths",
}

_BLOCKER_HINT_PATTERNS = [
    r"\bblocked\b",
    r"\bsealed\b",
    r"\bimpassable\b",
    r"\bcollaps(?:e|ed|ing)\b",
    r"\bcave\s*in\b",
    r"\bobstruct(?:ed|ion)\b",
]


def _normalize_text(value: str) -> str:
    """Normalize free text for deterministic regex checks."""
    lowered = str(value or "").lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _normalize_alias(value: str) -> str:
    """Normalize anchor aliases for token-boundary matching."""
    return _normalize_text(value)


def _contains_any_pattern(normalized_text: str, patterns: List[str]) -> bool:
    """Return True if any regex pattern matches normalized_text."""
    return any(re.search(pattern, normalized_text) for pattern in patterns)


def _has_explicit_transition_to_location(
    response_json: Dict[str, Any], location_id: str
) -> bool:
    """Return True if actions explicitly transition/update location to location_id."""
    target_id = str(location_id or "").strip().upper()
    if not target_id:
        return False

    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return False

    for action in actions:
        if not isinstance(action, dict):
            continue
        action_name = str(action.get("action", "") or "").strip()
        parameters = action.get("parameters", {})
        if not isinstance(parameters, dict):
            continue

        if action_name == "transitionLocation":
            if (
                str(parameters.get("newLocation", "") or "").strip().upper()
                == target_id
            ):
                return True
        elif action_name == "updatePartyTracker":
            if (
                str(parameters.get("currentLocationId", "") or "").strip().upper()
                == target_id
            ):
                return True
            world_conditions = parameters.get("worldConditions", {})
            if isinstance(world_conditions, dict):
                if (
                    str(world_conditions.get("currentLocationId", "") or "")
                    .strip()
                    .upper()
                    == target_id
                ):
                    return True

    return False


def _alias_to_regex(alias: str) -> str:
    """Convert normalized alias into safe whitespace-flexible regex."""
    parts = [re.escape(part) for part in alias.split() if part]
    return r"\s+".join(parts)


def _contains_alias(normalized_narration: str, normalized_alias: str) -> bool:
    """Return True when normalized alias appears as full-token phrase."""
    if not normalized_alias:
        return False
    padded_text = f" {normalized_narration} "
    padded_alias = f" {normalized_alias} "
    return padded_alias in padded_text


def _has_strong_present_context(normalized_narration: str) -> bool:
    """Return True if narration contains high-confidence present-scene markers."""
    return any(marker in normalized_narration for marker in _STRONG_PRESENT_MARKERS)


def _alias_has_present_scene_claim(
    normalized_narration: str, normalized_alias: str
) -> bool:
    """Return True when alias is narrated as physically present in current scene."""
    if not _contains_alias(normalized_narration, normalized_alias):
        return False

    alias_regex = _alias_to_regex(normalized_alias)
    if not alias_regex:
        return False

    patterns = [
        rf"\b{alias_regex}\b.{{0,40}}\b{_PRESENT_SCENE_VERB_PATTERN}\b",
        rf"\b{_PRESENT_SCENE_VERB_PATTERN}\b.{{0,28}}\b{alias_regex}\b",
        rf"\b{alias_regex}\b.{{0,40}}\b(?:before you|in front of you|in this chamber|right here|at your feet)\b",
        rf"\b(?:you|the party)\b.{{0,24}}\bsee\b.{{0,40}}\b{alias_regex}\b",
        rf"\b{alias_regex}\b.{{0,16}}\b(?:is|are)\b.{{0,16}}\b(?:here|present)\b",
    ]
    return _contains_any_pattern(normalized_narration, patterns)


def _extract_scene_authority_from_location(
    location_entry: Dict[str, Any],
    fallback_location_id: str,
) -> List[Dict[str, Any]]:
    """Extract normalized anchor records from a location dict."""
    if not isinstance(location_entry, dict):
        return []

    location_id = (
        str(
            location_entry.get("id")
            or location_entry.get("locationId")
            or fallback_location_id
            or ""
        )
        .strip()
        .upper()
    )
    if not location_id:
        return []

    location_name = str(location_entry.get("name", "") or "").strip()
    scene_authority = location_entry.get("sceneAuthority")
    if not isinstance(scene_authority, dict):
        scene_authority = location_entry.get("scene_authority")
    if not isinstance(scene_authority, dict):
        return []

    anchors = scene_authority.get("presentSceneAnchors", [])
    if not isinstance(anchors, list):
        return []

    records: List[Dict[str, Any]] = []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        anchor_id = str(anchor.get("anchorId", "") or "").strip()
        aliases_raw = anchor.get("aliases", [])
        if not anchor_id or not isinstance(aliases_raw, list):
            continue

        aliases = []
        seen_aliases = set()
        for alias_value in aliases_raw:
            normalized_alias = _normalize_alias(str(alias_value or ""))
            if not normalized_alias or normalized_alias in seen_aliases:
                continue
            seen_aliases.add(normalized_alias)
            aliases.append(normalized_alias)

        if not aliases:
            continue

        records.append(
            {
                "location_id": location_id,
                "location_name": location_name,
                "anchor_id": anchor_id,
                "aliases": aliases,
                "foreshadow_allowed": bool(anchor.get("foreshadowAllowed", True)),
            }
        )

    return records


def _build_scene_authority_anchor_index(
    module_locations: Optional[List[Dict[str, Any]]],
    current_location_data: Optional[Dict[str, Any]],
    current_location_id: str,
) -> List[Dict[str, Any]]:
    """Build module-local scene authority anchor index from authored metadata."""
    records: List[Dict[str, Any]] = []
    seen_keys = set()

    for location in module_locations or []:
        for record in _extract_scene_authority_from_location(location, ""):
            dedupe_key = (record.get("location_id", ""), record.get("anchor_id", ""))
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            records.append(record)

    for record in _extract_scene_authority_from_location(
        current_location_data or {}, current_location_id
    ):
        dedupe_key = (record.get("location_id", ""), record.get("anchor_id", ""))
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        records.append(record)

    return records


def _evaluate_metadata_exclusivity_decision(
    response_json: Dict[str, Any],
    current_location_id: str,
    module_locations: Optional[List[Dict[str, Any]]],
    current_location_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate location-exclusivity using authored sceneAuthority metadata."""
    current_id = str(current_location_id or "").strip().upper()
    if not current_id:
        return {"valid": True, "reason": "", "reconciliation": "none"}

    anchor_records = _build_scene_authority_anchor_index(
        module_locations=module_locations,
        current_location_data=current_location_data,
        current_location_id=current_id,
    )
    if not anchor_records:
        return {"valid": True, "reason": "", "reconciliation": "none"}

    narration = _normalize_text(response_json.get("narration", ""))
    if not narration:
        return {"valid": True, "reason": "", "reconciliation": "metadata_checked"}

    has_foreshadow_hint = _contains_any_pattern(narration, _FORESHADOW_PATTERNS)
    has_strong_present_context = _has_strong_present_context(narration)

    for record in anchor_records:
        owner_location_id = str(record.get("location_id", "") or "").strip().upper()
        if not owner_location_id or owner_location_id == current_id:
            continue

        if _has_explicit_transition_to_location(response_json, owner_location_id):
            continue

        aliases = (
            record.get("aliases", []) if isinstance(record.get("aliases"), list) else []
        )
        if not aliases:
            continue

        alias_matched = False
        present_scene_claim = False
        for alias in aliases:
            if not _contains_alias(narration, alias):
                continue
            alias_matched = True
            if _alias_has_present_scene_claim(narration, alias):
                present_scene_claim = True
                break

        if not alias_matched:
            continue

        if not present_scene_claim:
            continue

        if (
            bool(record.get("foreshadow_allowed", True))
            and has_foreshadow_hint
            and not has_strong_present_context
        ):
            continue

        anchor_id = str(record.get("anchor_id", "") or "anchor")
        owner_name = str(record.get("location_name", "") or owner_location_id)
        return {
            "valid": False,
            "reason": (
                "Location exclusivity violation: scene anchor "
                f"'{anchor_id}' belongs to location '{owner_name}' ({owner_location_id}) "
                f"but was instantiated as present while currentLocationId is {current_id}. "
                "Use foreshadowing only, or add a valid transition before present-scene claims."
            ),
            "reconciliation": "hard_fail",
        }

    return {"valid": True, "reason": "", "reconciliation": "metadata_checked"}


def _evaluate_legacy_thornwood_exclusivity_decision(
    response_json: Dict[str, Any], current_location_id: str
) -> Dict[str, Any]:
    """Legacy Thornwood safeguard kept during metadata migration."""
    current_id = str(current_location_id or "").strip().upper()
    if current_id != "NC01":
        return {"valid": True, "reason": "", "reconciliation": "none"}

    if _has_explicit_transition_to_location(response_json, "NC05"):
        return {"valid": True, "reason": "", "reconciliation": "explicit_transition"}

    narration = _normalize_text(response_json.get("narration", ""))
    if not narration:
        return {"valid": True, "reason": "", "reconciliation": "none"}

    has_nc05_present_anchor = _contains_any_pattern(narration, _NC05_PRESENT_PATTERNS)
    if not has_nc05_present_anchor:
        return {"valid": True, "reason": "", "reconciliation": "none"}

    if _contains_any_pattern(narration, _FORESHADOW_PATTERNS):
        if not _has_strong_present_context(narration):
            return {"valid": True, "reason": "", "reconciliation": "foreshadow_only"}

    return {
        "valid": False,
        "reason": (
            "Location exclusivity violation: NC05 finale scene content was narrated as "
            "present while currentLocationId is NC01. Use foreshadowing only, or add a "
            "valid transition to NC05 before present-scene claims."
        ),
        "reconciliation": "hard_fail",
    }


def evaluate_location_exclusivity_decision(
    response_json: Dict[str, Any],
    module_name: str,
    current_location_id: str,
    module_locations: Optional[List[Dict[str, Any]]] = None,
    current_location_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate location-exclusive present-scene claims.

    Runtime prefers authored sceneAuthority metadata when available and preserves
    the legacy Thornwood NC01/NC05 guard as migration-safe fallback.
    """
    metadata_decision = _evaluate_metadata_exclusivity_decision(
        response_json=response_json,
        current_location_id=current_location_id,
        module_locations=module_locations,
        current_location_data=current_location_data,
    )
    if not bool(metadata_decision.get("valid", True)):
        return metadata_decision

    module_key = str(module_name or "").strip().lower()
    if module_key in _THORNWOOD_MODULE_ALIASES:
        legacy_decision = _evaluate_legacy_thornwood_exclusivity_decision(
            response_json=response_json,
            current_location_id=current_location_id,
        )
        if not bool(legacy_decision.get("valid", True)):
            return legacy_decision
        if metadata_decision.get("reconciliation") != "none":
            return metadata_decision
        return legacy_decision

    return metadata_decision


def _extract_adjacent_location_ids(
    current_location_data: Optional[Dict[str, Any]],
) -> List[str]:
    """Return normalized authored adjacent location ids from location data."""
    if not isinstance(current_location_data, dict):
        return []
    raw_values = current_location_data.get("connectivity", [])
    if not isinstance(raw_values, list):
        return []
    adjacent_ids: List[str] = []
    for value in raw_values:
        location_id = str(value or "").strip().upper()
        if location_id:
            adjacent_ids.append(location_id)
    return adjacent_ids


def _has_transition_to_adjacent(
    response_json: Dict[str, Any], adjacent_ids: List[str]
) -> bool:
    """Return True when response explicitly transitions to one authored adjacent id."""
    adjacent_set = {location_id.upper() for location_id in adjacent_ids if location_id}
    if not adjacent_set:
        return False

    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return False

    for action in actions:
        if not isinstance(action, dict):
            continue
        action_name = str(action.get("action", "") or "").strip()
        parameters = action.get("parameters", {})
        if not isinstance(parameters, dict):
            continue

        candidate_id = ""
        if action_name == "transitionLocation":
            candidate_id = str(parameters.get("newLocation", "") or "").strip().upper()
        elif action_name == "updatePartyTracker":
            candidate_id = (
                str(parameters.get("currentLocationId", "") or "").strip().upper()
            )
            if not candidate_id:
                world_conditions = parameters.get("worldConditions", {})
                if isinstance(world_conditions, dict):
                    candidate_id = (
                        str(world_conditions.get("currentLocationId", "") or "")
                        .strip()
                        .upper()
                    )

        if candidate_id and candidate_id in adjacent_set:
            return True

    return False


def _has_supported_block_actions(response_json: Dict[str, Any]) -> bool:
    """Return True when response includes deterministic action support for blockers."""
    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return False

    for action in actions:
        if not isinstance(action, dict):
            continue
        action_name = str(action.get("action", "") or "").strip()
        parameters = action.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}

        if action_name in {"createEncounter", "updateEncounter"}:
            return True

        if action_name == "updatePartyTracker":
            if any(key in parameters for key in _BLOCKER_METADATA_KEYS):
                return True

            world_conditions = parameters.get("worldConditions", {})
            if isinstance(world_conditions, dict):
                if any(key in world_conditions for key in _BLOCKER_METADATA_KEYS):
                    return True

    return False


def _has_authored_blocker_metadata(
    current_location_data: Optional[Dict[str, Any]],
) -> bool:
    """Return True when current location metadata explicitly defines route blockers."""
    if not isinstance(current_location_data, dict):
        return False

    for key in _BLOCKER_METADATA_KEYS:
        value = current_location_data.get(key)
        if isinstance(value, (list, dict)) and value:
            return True
        if isinstance(value, bool) and value:
            return True

    transition_hints = current_location_data.get("transition_hints", [])
    if not isinstance(transition_hints, list):
        return False

    for hint in transition_hints:
        if isinstance(hint, str):
            hint_text = _normalize_text(hint)
            if _contains_any_pattern(hint_text, _BLOCKER_HINT_PATTERNS):
                return True
            continue

        if isinstance(hint, dict):
            if bool(hint.get("blocked", False)):
                return True
            text_parts = [
                str(hint.get("type", "") or ""),
                str(hint.get("description", "") or ""),
                str(hint.get("label", "") or ""),
                str(hint.get("reason", "") or ""),
            ]
            hint_text = _normalize_text(" ".join(text_parts))
            if _contains_any_pattern(hint_text, _BLOCKER_HINT_PATTERNS):
                return True

    return False


def evaluate_authored_exit_grounding_decision(
    response_json: Dict[str, Any],
    current_location_id: str,
    current_location_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Reject unsupported route-block narration when authored adjacency allows travel."""
    adjacent_ids = _extract_adjacent_location_ids(current_location_data)
    if not adjacent_ids:
        return {"valid": True, "reason": "", "reconciliation": "none"}

    narration = _normalize_text(response_json.get("narration", ""))
    if not narration:
        return {"valid": True, "reason": "", "reconciliation": "none"}

    has_blocker_claim = _contains_any_pattern(narration, _BLOCKER_PATTERNS)
    if not has_blocker_claim:
        return {"valid": True, "reason": "", "reconciliation": "none"}

    has_route_context = _contains_any_pattern(narration, _ROUTE_CONTEXT_PATTERNS)
    adjacent_id_mentions = any(
        location_id.lower() in narration for location_id in adjacent_ids
    )
    if not has_route_context and not adjacent_id_mentions:
        return {"valid": True, "reason": "", "reconciliation": "none"}

    if _has_transition_to_adjacent(response_json, adjacent_ids):
        return {"valid": True, "reason": "", "reconciliation": "explicit_transition"}

    if _has_supported_block_actions(response_json):
        return {"valid": True, "reason": "", "reconciliation": "action_grounded"}

    if _has_authored_blocker_metadata(current_location_data):
        return {"valid": True, "reason": "", "reconciliation": "metadata_grounded"}

    current_id = str(current_location_id or "").strip().upper() or "UNKNOWN"
    adjacent_str = ", ".join(sorted(set(adjacent_ids)))
    return {
        "valid": False,
        "reason": (
            "Authored-exit grounding violation: narration claims a blocked route from "
            f"{current_id} while authored adjacent exits remain available ({adjacent_str}) "
            "and no deterministic blocker support was provided. Add deterministic blocker "
            "action/metadata, or remove the unsupported blockage claim."
        ),
        "reconciliation": "hard_fail",
    }
