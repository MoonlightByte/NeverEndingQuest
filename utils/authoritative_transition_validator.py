# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Authoritative Transition Validator
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from collections import deque
from typing import Any, Dict, List, Set
import os

from utils.file_operations import safe_read_json
from utils.module_path_manager import ModulePathManager


def _normalize_id(value: Any) -> str:
    return str(value or "").strip()


def _get_backup_area_path(area_path: str) -> str:
    if area_path.endswith(".json"):
        return area_path[:-5] + "_BU.json"
    return area_path + "_BU.json"


def _normalize_neighbor_list(raw_neighbors: Any) -> List[str]:
    if not isinstance(raw_neighbors, list):
        return []
    return [
        _normalize_id(loc_id)
        for loc_id in raw_neighbors
        if _normalize_id(loc_id)
    ]


def _collect_location_records(area_payload: Dict[str, Any], area_id: str) -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    if not isinstance(area_payload, dict):
        return records

    for location in area_payload.get("locations", []):
        if not isinstance(location, dict):
            continue

        location_id = _normalize_id(location.get("locationId"))
        if not location_id:
            continue

        records[location_id] = {
            "area_id": _normalize_id(area_id),
            "name": str(location.get("name") or "").strip(),
            "connectivity": _normalize_neighbor_list(location.get("connectivity", [])),
            "area_connectivity": _normalize_neighbor_list(location.get("areaConnectivityId", [])),
        }
    return records


def _merge_location_records(primary: Dict[str, Dict[str, Any]], fallback: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    all_ids = set(primary.keys()) | set(fallback.keys())
    for location_id in all_ids:
        primary_record = primary.get(location_id, {})
        fallback_record = fallback.get(location_id, {})
        connectivity = primary_record.get("connectivity") or fallback_record.get("connectivity") or []
        area_connectivity = primary_record.get("area_connectivity") or fallback_record.get("area_connectivity") or []
        merged[location_id] = {
            "area_id": primary_record.get("area_id") or fallback_record.get("area_id") or "",
            "name": primary_record.get("name") or fallback_record.get("name") or "",
            "neighbors": connectivity + area_connectivity,
        }
    return merged


def _build_module_topology(module_name: str) -> Dict[str, Dict[str, Any]]:
    """Build fresh location topology from current module area files.

    Prefer live runtime area data, but backfill static connectivity from canonical
    `_BU` area files when the live runtime copy has stale or missing topology.
    """
    topology: Dict[str, Dict[str, Any]] = {}
    path_manager = ModulePathManager(module_name)

    for area_id in path_manager.get_area_ids():
        area_path = path_manager.get_area_path(area_id)
        live_area_data = safe_read_json(area_path)
        backup_area_path = _get_backup_area_path(area_path)
        backup_area_data = safe_read_json(backup_area_path) if os.path.exists(backup_area_path) else None

        live_records = _collect_location_records(live_area_data, area_id)
        backup_records = _collect_location_records(backup_area_data, area_id)
        area_topology = _merge_location_records(live_records, backup_records)
        topology.update(area_topology)

    return topology


def _find_path(topology: Dict[str, Dict[str, Any]], origin_id: str, destination_id: str) -> List[str]:
    """Return directed BFS path from origin to destination, or empty list."""
    if origin_id not in topology or destination_id not in topology:
        return []
    if origin_id == destination_id:
        return [origin_id]

    queue: deque = deque([(origin_id, [origin_id])])
    visited: Set[str] = {origin_id}

    while queue:
        current_id, path = queue.popleft()
        neighbors = topology.get(current_id, {}).get("neighbors", [])
        if not isinstance(neighbors, list):
            continue

        for neighbor in neighbors:
            neighbor_id = _normalize_id(neighbor)
            if not neighbor_id or neighbor_id in visited:
                continue
            if neighbor_id not in topology:
                continue

            next_path = path + [neighbor_id]
            if neighbor_id == destination_id:
                return next_path

            visited.add(neighbor_id)
            queue.append((neighbor_id, next_path))

    return []


def validate_same_module_transition_authority(
    module_name: str,
    current_location_id: str,
    destination_location_id: str,
    current_area_id: str,
) -> Dict[str, Any]:
    """Validate same-module transitions from fresh module topology.

    Returns:
        {
            "applies": bool,
            "valid": bool,
            "error_message": str,
            "area_connectivity_id": str|None,
            "destination_area_id": str,
            "path": list[str],
        }
    """
    module_slug = str(module_name or "").replace(" ", "_")
    origin_id = _normalize_id(current_location_id)
    destination_id = _normalize_id(destination_location_id)
    origin_area_id = _normalize_id(current_area_id)

    if not module_slug or not origin_id or not destination_id:
        return {
            "applies": False,
            "valid": False,
            "error_message": "Missing transition authority input.",
            "area_connectivity_id": None,
            "destination_area_id": "",
            "path": [],
        }

    topology = _build_module_topology(module_slug)
    if origin_id not in topology or destination_id not in topology:
        return {
            "applies": False,
            "valid": False,
            "error_message": "Destination is not in the current module topology.",
            "area_connectivity_id": None,
            "destination_area_id": "",
            "path": [],
        }

    path = _find_path(topology, origin_id, destination_id)
    if not path:
        return {
            "applies": True,
            "valid": False,
            "error_message": (
                f"No valid same-module path exists between '{origin_id}' and "
                f"'{destination_id}' in module '{module_slug}'."
            ),
            "area_connectivity_id": None,
            "destination_area_id": _normalize_id(topology.get(destination_id, {}).get("area_id")),
            "path": [],
        }

    destination_area_id = _normalize_id(topology.get(destination_id, {}).get("area_id"))
    is_cross_area = bool(destination_area_id and destination_area_id != origin_area_id)
    area_connectivity_id = f"{destination_area_id}-{destination_id}" if is_cross_area else None

    return {
        "applies": True,
        "valid": True,
        "error_message": "",
        "area_connectivity_id": area_connectivity_id,
        "destination_area_id": destination_area_id,
        "path": path,
    }
