# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Map Projection
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.

Pure, side-effect-free helpers for building the spoiler-safe fog-of-war map
payload sent to game clients. This module intentionally has NO Flask/socketio
imports so it can be imported cheaply (e.g. from tests) without pulling in
web_interface.py's heavy module-level side effects (Flask app creation,
OpenAI client construction, etc).

SECURITY NOTE: `project_map_payload` is the security boundary for the map
feature. Fog-of-war on the client is purely cosmetic -- anything emitted here
is readable in devtools. Never add locations[], descriptions, encounters,
dmInstructions, doors, traps, loot, adventureSummary, or explorationState to
the returned payload.
"""

import os
import re

from utils.path_encounter_analyzer import derive_location_exploration_state

AREA_ID_PATTERN = re.compile(r'[A-Z]+[0-9]+')


def derive_revealed(area_json, current_loc):
    """Compute the set of revealed room ids for an area.

    A room is revealed if it has been visited (per
    ``derive_location_exploration_state``) or if it is the party's current
    location -- the engine only marks a location visited on departure, so the
    room the party currently occupies must be revealed even when its
    exploration state still reads "unvisited"/"unknown".

    A falsy ``current_loc`` (None/"" etc) is never added to the set: letting
    None into the set would (a) make ``None == None`` match any room dict
    that happens to lack an "id" key, revealing it, and (b) crash
    ``sorted()`` in project_map_payload when mixed with string ids.
    """
    visited_ids = set()
    for loc in area_json.get("locations", []) or []:
        if not isinstance(loc, dict):
            continue
        state = derive_location_exploration_state(loc)
        if state.get("status") == "visited":
            location_id = loc.get("locationId")
            if location_id:
                visited_ids.add(location_id)

    revealed = visited_ids | ({current_loc} if current_loc else set())
    return revealed


def resolve_area_path(module, area_id):
    """Resolve and validate the on-disk path for an area file.

    Pure, Flask-free path-safety logic shared by the socket handler and
    tests. Raises ``ValueError`` (never lets a bad path through) when:
    - ``area_id`` doesn't fullmatch ``[A-Z]+[0-9]+`` (blocks things like
      "G001_BU", lowercase ids, or ids containing path separators such as
      "A01/..").
    - the resolved path doesn't stay under ``realpath('modules') + os.sep``
      (blocks a corrupt/malicious module name from traversing out of
      modules/, e.g. "../../etc").
    - ``module`` or ``area_id`` is empty/falsy.

    Returns the validated area file path (whatever
    ``ModulePathManager.get_area_path`` returns -- may or may not exist on
    disk; callers still need to safe_read_json it and handle None).
    """
    if not module or not area_id:
        raise ValueError("Invalid module or area id")

    if not AREA_ID_PATTERN.fullmatch(area_id):
        raise ValueError(f"Invalid area id: {area_id!r}")

    # Local import: keep this module importable without pulling in the
    # broader utils/web import graph at module load time.
    from utils.module_path_manager import ModulePathManager

    path_manager = ModulePathManager(module)
    area_path = path_manager.get_area_path(area_id)

    modules_root = os.path.realpath('modules') + os.sep
    if not os.path.realpath(area_path).startswith(modules_root):
        raise ValueError("Resolved area path escapes modules/")

    return area_path


COORDINATES_PATTERN = re.compile(r'X(\d+)Y(\d+)')


def _parse_coordinates(value):
    """Return (x, y) for an ``X<n>Y<n>`` string, else None."""
    if not isinstance(value, str):
        return None
    match = COORDINATES_PATTERN.fullmatch(value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def project_map_payload(area_json, revealed_set, current_loc):
    """Build the spoiler-safe map payload for the given area.

    Only fields explicitly listed below are ever emitted. Rooms not in
    ``revealed_set`` get no name/type; their connections are filtered to
    revealed neighbors only. Coordinates go only to revealed rooms and their
    direct ("frontier") neighbours; every other room gets ``None``.
    ``map.grid`` is the whole area's extent, so the layout stays fixed as
    rooms are revealed. Revealed rooms take their name/type from the matching
    ``locations[]`` entry (the map rooms may carry placeholder names).
    """
    rooms_source = ((area_json.get("map") or {}).get("rooms")) or []
    known_room_ids = {room.get("id") for room in rooms_source if isinstance(room, dict)}
    known_room_ids.discard(None)

    locations_by_id = {
        loc.get("locationId"): loc
        for loc in area_json.get("locations", []) or []
        if isinstance(loc, dict) and loc.get("locationId")
    }

    # First pass: filter each room's connections to those whose OTHER
    # endpoint exists as a real room, keeping only edges where at least one
    # endpoint is revealed. Frontier rooms are the source neighbours of a
    # revealed room.
    filtered_connections = {}
    frontier = set()
    for room in rooms_source:
        if not isinstance(room, dict):
            continue
        room_id = room.get("id")
        if not room_id:
            continue
        raw_connections = room.get("connections") or []
        kept = []
        for neighbor in raw_connections:
            if neighbor not in known_room_ids:
                continue
            if room_id in revealed_set or neighbor in revealed_set:
                kept.append(neighbor)
            if room_id in revealed_set:
                frontier.add(neighbor)
            if neighbor in revealed_set:
                frontier.add(room_id)
        filtered_connections[room_id] = kept

    # Second pass: symmetrize. If A kept B, ensure B keeps A (avoids
    # one-way-edge artifacts from filtering).
    for room_id, neighbors in list(filtered_connections.items()):
        for neighbor in neighbors:
            neighbor_list = filtered_connections.get(neighbor)
            if neighbor_list is not None and room_id not in neighbor_list:
                neighbor_list.append(room_id)

    projected_rooms = []
    parsed = []
    for room in rooms_source:
        if not isinstance(room, dict):
            continue
        room_id = room.get("id")
        if not room_id:
            continue
        xy = _parse_coordinates(room.get("coordinates"))
        if xy is not None:
            parsed.append(xy)
        shown = room_id in revealed_set or room_id in frontier
        projected = {
            "id": room_id,
            "coordinates": room.get("coordinates") if (shown and xy is not None) else None,
        }
        if room_id in revealed_set:
            location = locations_by_id.get(room_id) or {}
            projected["name"] = location.get("name") or room.get("name")
            projected["type"] = location.get("type") or room.get("type")
        projected["connections"] = filtered_connections.get(room_id, [])
        projected_rooms.append(projected)

    area_id = area_json.get("areaId")
    area_name = area_json.get("areaName", area_id)

    map_block = {
        "mapId": area_id,
        "mapName": area_name,
        "rooms": projected_rooms,
    }
    if parsed:
        xs = [x for x, _ in parsed]
        ys = [y for _, y in parsed]
        map_block["grid"] = {
            "cols": max(xs) - min(xs) + 1,
            "rows": max(ys) - min(ys) + 1,
            "originX": min(xs),
            "originY": min(ys),
        }

    return {
        "areaId": area_id,
        "areaName": area_name,
        "map": map_block,
        "area": {
            k: area_json.get(k)
            for k in ("areaType", "terrain", "climate", "areaDescription")
        },
        "revealed": sorted(set(revealed_set) & known_room_ids),
        "currentLocationId": current_loc,
        "undiscoveredCount": len(known_room_ids - set(revealed_set)),
    }
