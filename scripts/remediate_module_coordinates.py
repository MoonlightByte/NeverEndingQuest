#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Spatial Contract Remediation Tool
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Backfills spatial contract fields for legacy modules in dry-run or apply mode.
"""

import argparse
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.file_operations import safe_write_json
from utils.spatial_contract import (
    build_direction_map_from_rooms,
    build_location_aliases,
    build_tactical_grid,
    is_valid_coordinate,
    parse_coordinate,
    resolve_semantic_spatial_plan,
)


def _is_excluded_json_file(path: Path) -> bool:
    name = path.name
    return any(
        token in name
        for token in ("_BU.json", ".bak", ".backup", ".tmp", "_backup.json")
    )


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_room_index(map_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    room_index: Dict[str, Dict[str, Any]] = {}
    for room in map_data.get("rooms", []):
        room_id = room.get("id")
        if isinstance(room_id, str) and room_id:
            room_index[room_id] = room
    return room_index


def _build_plan_from_locations(locations: List[Dict[str, Any]]) -> Dict[str, Any]:
    room_records: List[Dict[str, Any]] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        location_id = location.get("locationId")
        if not isinstance(location_id, str) or not location_id:
            continue
        room_records.append(
            {
                "id": location_id,
                "name": location.get("name", location_id),
                "type": location.get("type", "room"),
                "description": location.get("description", ""),
                "connections": location.get("connectivity", []),
            }
        )

    return resolve_semantic_spatial_plan(
        room_records,
        start_x=10,
        start_y=10,
        use_llm=False,
    )


def _build_force_relayout_coordinates(locations: List[Dict[str, Any]]) -> Dict[str, str]:
    """Assign adjacency-safe coordinates from authored connectivity."""
    coordinates: Dict[str, str] = {}
    occupied: set[Tuple[int, int]] = set()
    order: List[str] = []
    graph: Dict[str, List[str]] = {}

    for location in locations:
        if not isinstance(location, dict):
            continue
        location_id = location.get("locationId")
        if not isinstance(location_id, str) or not location_id:
            continue
        order.append(location_id)
        graph[location_id] = [
            target
            for target in location.get("connectivity", [])
            if isinstance(target, str) and target
        ]

    component_index = 0
    for location_id in order:
        if location_id in coordinates:
            continue

        start = (10 + (component_index * 4), 10)
        while start in occupied:
            start = (start[0] + 1, start[1] + 1)

        coordinates[location_id] = f"X{start[0]}Y{start[1]}"
        occupied.add(start)

        queue: deque[str] = deque([location_id])
        while queue:
            current_id = queue.popleft()
            current_coordinate = coordinates[current_id]
            current_x, current_y = parse_coordinate(current_coordinate)

            for neighbor_id in graph.get(current_id, []):
                if neighbor_id not in graph or neighbor_id in coordinates:
                    continue
                for delta_x, delta_y in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
                    candidate = (current_x + delta_x, current_y + delta_y)
                    if candidate in occupied:
                        continue
                    coordinates[neighbor_id] = f"X{candidate[0]}Y{candidate[1]}"
                    occupied.add(candidate)
                    queue.append(neighbor_id)
                    break

        component_index += 1

    for location_id in order:
        if location_id in coordinates:
            continue
        fallback = (10 + len(occupied), 10)
        while fallback in occupied:
            fallback = (fallback[0] + 1, fallback[1])
        coordinates[location_id] = f"X{fallback[0]}Y{fallback[1]}"
        occupied.add(fallback)

    return coordinates


def remediate_area_map_pair(
    area_data: Dict[str, Any],
    map_data: Dict[str, Any],
    force_relayout: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    """Backfill spatial contract fields while preserving authored connectivity."""
    locations = area_data.get("locations", [])
    room_index = _build_room_index(map_data)
    fallback_plan = _build_plan_from_locations(locations)
    forced_coordinates = _build_force_relayout_coordinates(locations) if force_relayout else {}
    changes = 0

    for index, location in enumerate(locations):
        if not isinstance(location, dict):
            continue
        location_id = location.get("locationId")
        if not isinstance(location_id, str) or not location_id:
            continue

        map_room = room_index.get(location_id, {})
        map_coordinate = map_room.get("coordinates")
        fallback_coordinate = forced_coordinates.get(location_id) or fallback_plan["coordinates"].get(
            location_id, f"X{10 + index}Y10"
        )
        coordinate = location.get("coordinates")
        if force_relayout and coordinate != fallback_coordinate:
            location["coordinates"] = fallback_coordinate
            changes += 1
        elif is_valid_coordinate(map_coordinate) and coordinate != map_coordinate:
            location["coordinates"] = map_coordinate
            changes += 1
        elif not is_valid_coordinate(coordinate):
            location["coordinates"] = (
                map_coordinate
                if is_valid_coordinate(map_coordinate)
                else fallback_coordinate
            )
            changes += 1

        if (
            "aliases" not in location
            or not isinstance(location.get("aliases"), list)
            or not location.get("aliases")
        ):
            location["aliases"] = build_location_aliases(
                location.get("name", ""), location_id
            )
            changes += 1

        if (
            "tactical_grid" not in location
            or not isinstance(location.get("tactical_grid"), list)
            or len(location.get("tactical_grid", [])) != 9
        ):
            location["tactical_grid"] = build_tactical_grid(
                location.get("name", ""), location.get("type", "room")
            )
            changes += 1

        if "connectivity" not in location or not isinstance(
            location.get("connectivity"), list
        ):
            location["connectivity"] = map_room.get(
                "connections", fallback_plan["connectivity"].get(location_id, [])
            )
            changes += 1

    area_data["spatialContractVersion"] = 1

    map_rooms: List[Dict[str, Any]] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        location_id = location.get("locationId")
        if not isinstance(location_id, str) or not location_id:
            continue

        current_room = room_index.get(location_id, {})
        location_connectivity = location.get("connectivity")
        room_connections = current_room.get("connections")

        if isinstance(location_connectivity, list):
            # Use authored location connectivity as the canonical runtime source.
            room_connections = [
                target
                for target in location_connectivity
                if isinstance(target, str) and target
            ]
        elif isinstance(room_connections, list):
            room_connections = [
                target
                for target in room_connections
                if isinstance(target, str) and target
            ]
        else:
            room_connections = fallback_plan["connectivity"].get(location_id, [])

        room_record = dict(current_room) if isinstance(current_room, dict) else {}
        room_record["id"] = location_id
        room_record["name"] = (
            current_room.get("name") or location.get("name") or location_id
        )
        room_record["connections"] = room_connections
        room_record["coordinates"] = location.get(
            "coordinates", fallback_plan["coordinates"].get(location_id, "X10Y10")
        )
        map_rooms.append(room_record)

    direction_map = build_direction_map_from_rooms(map_rooms)
    for room in map_rooms:
        room["directions"] = direction_map.get(room["id"], {})

    if map_data.get("rooms") != map_rooms:
        map_data["rooms"] = map_rooms
        changes += 1

    expected_layout = fallback_plan.get("layout", [])
    existing_layout = map_data.get("layout")
    if not isinstance(existing_layout, list) or not existing_layout:
        map_data["layout"] = expected_layout
        changes += 1

    map_data["totalRooms"] = len(map_rooms)
    map_data["startRoom"] = map_rooms[0]["id"] if map_rooms else ""
    map_data["spatialContractVersion"] = 1

    return area_data, map_data, changes


def remediate_module(module_path: Path, apply: bool, force_relayout: bool = False) -> Dict[str, Any]:
    """Remediate one module path and return summary metrics."""
    areas_dir = module_path / "areas"
    if not areas_dir.exists():
        return {"module": module_path.name, "processed": 0, "changed": 0, "errors": []}

    processed = 0
    changed = 0
    errors: List[str] = []

    for area_path in sorted(areas_dir.glob("*.json")):
        if _is_excluded_json_file(area_path):
            continue
        try:
            area_data = _load_json(area_path)
            area_id = area_data.get("areaId")
            if not isinstance(area_id, str) or not area_id:
                continue

            map_path = module_path / f"map_{area_id}.json"
            has_external_map = map_path.exists() and not _is_excluded_json_file(
                map_path
            )

            if has_external_map:
                map_data = _load_json(map_path)
            else:
                embedded_map = area_data.get("map")
                if not isinstance(embedded_map, dict) or not embedded_map:
                    continue
                map_data = embedded_map

            patched_area, patched_map, pair_changes = remediate_area_map_pair(
                area_data,
                map_data,
                force_relayout=force_relayout,
            )

            processed += 1
            if pair_changes > 0:
                changed += 1
                if apply:
                    safe_write_json(str(area_path), patched_area)
                    if has_external_map:
                        safe_write_json(str(map_path), patched_map)
        except Exception as exc:
            errors.append(f"{area_path.name}: {exc}")

    return {
        "module": module_path.name,
        "processed": processed,
        "changed": changed,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill spatial contract fields for module area/map files"
    )
    parser.add_argument(
        "--module", type=str, default="", help="Single module slug under modules/"
    )
    parser.add_argument("--apply", action="store_true", help="Write remediated files")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview only (default behavior)"
    )
    args = parser.parse_args()

    modules_root = Path("modules")
    if args.module:
        module_paths = [modules_root / args.module]
    else:
        module_paths = [
            path for path in sorted(modules_root.iterdir()) if path.is_dir()
        ]

    apply_mode = bool(args.apply)
    results = []
    for module_path in module_paths:
        if not module_path.exists():
            continue
        results.append(remediate_module(module_path, apply=apply_mode))

    total_processed = sum(item["processed"] for item in results)
    total_changed = sum(item["changed"] for item in results)
    total_errors = sum(len(item["errors"]) for item in results)

    mode_label = "apply" if apply_mode else "dry-run"
    print(
        f"SPATIAL_REMEDIATE mode={mode_label} modules={len(results)} processed={total_processed} changed={total_changed} errors={total_errors}"
    )
    for item in results:
        print(
            f"- {item['module']}: processed={item['processed']} changed={item['changed']} errors={len(item['errors'])}"
        )
        for error_text in item["errors"]:
            print(f"  [ERROR] {error_text}")


if __name__ == "__main__":
    main()
