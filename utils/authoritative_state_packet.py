# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Authoritative State Packet Builder
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.

Builds a narrow, machine-readable packet for narrator and validator truth
surfaces used by the gametest foundation slice.
"""

from typing import Any, Dict, List, Optional

from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug
from utils.module_path_manager import ModulePathManager


def _safe_string(value: Any) -> str:
    """Return a stripped string, or empty string when unavailable."""
    if isinstance(value, str):
        return value.strip()
    return ""


def _safe_list_of_strings(items: Any) -> List[str]:
    """Return list of non-empty strings."""
    if not isinstance(items, list):
        return []
    normalized: List[str] = []
    for item in items:
        if isinstance(item, str):
            item_text = item.strip()
            if item_text:
                normalized.append(item_text)
    return normalized


def _load_area_data(module_name: str, current_area_id: str) -> Optional[Dict[str, Any]]:
    """Load area data for current module/area when available."""
    if not module_name or not current_area_id:
        return None

    try:
        path_manager = ModulePathManager(module_name.replace(" ", "_"))
        area_path = path_manager.get_area_path(current_area_id)
        loaded = safe_json_load(area_path)
        if isinstance(loaded, dict):
            return loaded
    except Exception as exc:
        debug(
            f"AUTHORITATIVE_STATE_PACKET: area load degraded for module='{module_name}' area='{current_area_id}': {exc}",
            category="ai_validation",
        )
    return None


def _extract_location_data(
    area_data: Optional[Dict[str, Any]],
    current_location_id: str,
) -> Optional[Dict[str, Any]]:
    """Extract current location object from area data."""
    if not isinstance(area_data, dict):
        return None

    for location in area_data.get("locations", []):
        if isinstance(location, dict) and location.get("locationId") == current_location_id:
            return location
    return None


def _extract_known_locations(
    area_data: Optional[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """Extract known location IDs and names for current area."""
    known_ids: List[str] = []
    known_names: List[str] = []

    if not isinstance(area_data, dict):
        return {"ids": known_ids, "names": known_names}

    for location in area_data.get("locations", []):
        if not isinstance(location, dict):
            continue
        location_id = _safe_string(location.get("locationId", ""))
        location_name = _safe_string(location.get("name", ""))

        if location_id:
            known_ids.append(location_id)
        if location_name:
            known_names.append(location_name)

    return {"ids": known_ids, "names": known_names}


def _extract_adjacent_location_ids(location_data: Optional[Dict[str, Any]]) -> List[str]:
    """Extract adjacent/connected location IDs from current location payload."""
    adjacent: List[str] = []

    if not isinstance(location_data, dict):
        return adjacent

    connectivity = location_data.get("connectivity", [])
    if isinstance(connectivity, list):
        adjacent.extend(_safe_list_of_strings(connectivity))

    connected_locations = location_data.get("connectedLocations", [])
    if isinstance(connected_locations, list):
        for item in connected_locations:
            if isinstance(item, dict):
                location_id = _safe_string(item.get("locationId", ""))
                if location_id:
                    adjacent.append(location_id)
            elif isinstance(item, str):
                location_id = item.strip()
                if location_id:
                    adjacent.append(location_id)

    # De-duplicate while preserving order
    deduped: List[str] = []
    seen = set()
    for item in adjacent:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def build_authoritative_state_packet(
    party_tracker_data: Dict[str, Any],
    area_data: Optional[Dict[str, Any]] = None,
    location_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a narrow authoritative packet for validator and DM Note parity.

    Args:
        party_tracker_data: Current party tracker payload.
        area_data: Optional already-loaded area data to avoid duplicate I/O.
        location_data: Optional already-loaded current location data.

    Returns:
        Narrow packet with location/module/party/topology truth.
    """
    if not isinstance(party_tracker_data, dict):
        party_tracker_data = {}

    world_conditions = party_tracker_data.get("worldConditions", {})
    if not isinstance(world_conditions, dict):
        world_conditions = {}

    module_name = _safe_string(party_tracker_data.get("module", ""))
    current_area_id = _safe_string(world_conditions.get("currentAreaId", ""))
    current_area_name = _safe_string(world_conditions.get("currentArea", ""))
    current_location_id = _safe_string(world_conditions.get("currentLocationId", ""))
    current_location_name = _safe_string(world_conditions.get("currentLocation", ""))

    resolved_area_data = area_data if isinstance(area_data, dict) else _load_area_data(module_name, current_area_id)
    resolved_location_data = location_data if isinstance(location_data, dict) else _extract_location_data(
        resolved_area_data,
        current_location_id,
    )

    location_name_from_area = _safe_string((resolved_location_data or {}).get("name", ""))
    if location_name_from_area:
        current_location_name = location_name_from_area

    known_locations = _extract_known_locations(resolved_area_data)
    adjacent_location_ids = _extract_adjacent_location_ids(resolved_location_data)

    party_members = _safe_list_of_strings(party_tracker_data.get("partyMembers", []))
    active_character = _safe_string(party_tracker_data.get("active_character", ""))

    raw_party_npcs = party_tracker_data.get("partyNPCs", [])
    if not isinstance(raw_party_npcs, list):
        raw_party_npcs = []

    party_npcs: List[Dict[str, Any]] = []
    party_npc_names: List[str] = []
    for entry in raw_party_npcs:
        if not isinstance(entry, dict):
            continue
        party_npcs.append(entry)
        name = _safe_string(entry.get("name", ""))
        if name:
            party_npc_names.append(name)

    location_description = _safe_string((resolved_location_data or {}).get("description", ""))
    location_dm_instructions = _safe_string((resolved_location_data or {}).get("dmInstructions", ""))

    return {
        "version": "v1",
        "module": {
            "name": module_name,
        },
        "world": {
            "current_area_id": current_area_id,
            "current_area_name": current_area_name,
            "current_location_id": current_location_id,
            "current_location_name": current_location_name,
        },
        "party": {
            "party_members": party_members,
            "active_character": active_character,
            "party_npcs": party_npcs,
            "party_npc_names": party_npc_names,
        },
        "location": {
            "description": location_description,
            "dm_instructions": location_dm_instructions,
            "adjacent_location_ids": adjacent_location_ids,
        },
        "topology": {
            "known_location_ids": known_locations.get("ids", []),
            "known_location_names": known_locations.get("names", []),
        },
    }
