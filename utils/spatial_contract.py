# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Spatial Contract Helpers
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Shared deterministic helpers for authored spatial contracts used by builder,
ingest, validation, and remediation paths.
"""

import json
import re
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple


CARDINAL_DIRECTIONS = ("north", "south", "east", "west")
COORDINATE_PATTERN = re.compile(r"^X([0-9]+)Y([0-9]+)$")
_DIRECTION_DELTA = {
    (0, -1): "north",
    (0, 1): "south",
    (1, 0): "east",
    (-1, 0): "west",
}
_DIRECTION_VECTORS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}
_DEFAULT_DIRECTION_ORDER = ("east", "south", "west", "north")
_DIRECTION_HINT_PATTERNS = {
    "north": (r"\bnorth(?:ern|ward)?\b", r"\bupper\b", r"\bupstairs\b"),
    "south": (r"\bsouth(?:ern|ward)?\b", r"\blower\b", r"\bdownstairs\b"),
    "east": (r"\beast(?:ern|ward)?\b", r"\bright\b"),
    "west": (r"\bwest(?:ern|ward)?\b", r"\bleft\b"),
}
_ROOM_REFERENCE_PATTERN = re.compile(r"\broom\s+(\d{1,4})\b", re.IGNORECASE)
_ADJACENCY_CUE_TERMS = (
    "exit",
    "passage",
    "corridor",
    "hall",
    "hallway",
    "door",
    "doorway",
    "stairs",
    "stair",
    "ladder",
    "tunnel",
    "bridge",
    "archway",
    "to",
    "toward",
    "leads",
    "leading",
)


def is_valid_coordinate(value: Any) -> bool:
    """Return True when value matches X#Y# coordinate contract."""
    return isinstance(value, str) and COORDINATE_PATTERN.match(value) is not None


def parse_coordinate(value: Any) -> Tuple[int, int]:
    """Parse X#Y# coordinates with safe fallback."""
    if not isinstance(value, str):
        return 0, 0
    match = COORDINATE_PATTERN.match(value)
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def format_coordinate(x_value: int, y_value: int) -> str:
    """Format integer coordinate pair to X#Y# string."""
    return f"X{int(x_value)}Y{int(y_value)}"


def build_linear_spatial_plan(
    location_ids: List[str],
    start_x: int = 10,
    start_y: int = 10,
) -> Dict[str, Any]:
    """Build deterministic linear coordinate/connectivity plan."""
    coordinates: Dict[str, str] = {}
    connectivity: Dict[str, List[str]] = {}
    directions: Dict[str, Dict[str, str]] = {}

    for index, location_id in enumerate(location_ids):
        coordinates[location_id] = format_coordinate(start_x + index, start_y)

        links: List[str] = []
        if index > 0:
            links.append(location_ids[index - 1])
        if index < len(location_ids) - 1:
            links.append(location_ids[index + 1])
        connectivity[location_id] = links

        direction_map: Dict[str, str] = {}
        if index > 0:
            direction_map["west"] = location_ids[index - 1]
        if index < len(location_ids) - 1:
            direction_map["east"] = location_ids[index + 1]
        directions[location_id] = direction_map

    return {
        "coordinates": coordinates,
        "connectivity": connectivity,
        "directions": directions,
        "layout": [[location_id] for location_id in location_ids],
    }


def _extract_direction_hints(text_value: str) -> List[str]:
    """Extract cardinal hints from free-form prose and labels."""
    if not isinstance(text_value, str) or not text_value.strip():
        return []

    normalized = text_value.strip().lower()
    hints: List[str] = []
    for direction_key, pattern_group in _DIRECTION_HINT_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in pattern_group):
            hints.append(direction_key)
    return hints


def _build_direction_priority(
    source_record: Dict[str, Any],
    target_record: Dict[str, Any],
) -> List[str]:
    """Build deterministic direction priority from target/source semantics."""
    priority: List[str] = []

    target_text = " ".join(
        [
            str(target_record.get("name", "")),
            str(target_record.get("description", "")),
            str(target_record.get("type", "")),
        ]
    )
    source_text = " ".join(
        [
            str(source_record.get("name", "")),
            str(source_record.get("description", "")),
            str(source_record.get("type", "")),
        ]
    )

    for direction_key in _extract_direction_hints(target_text):
        if direction_key not in priority:
            priority.append(direction_key)
    for direction_key in _extract_direction_hints(source_text):
        if direction_key not in priority:
            priority.append(direction_key)
    for direction_key in _DEFAULT_DIRECTION_ORDER:
        if direction_key not in priority:
            priority.append(direction_key)
    return priority


def _build_layout_from_coordinates(coordinates: Dict[str, str]) -> List[List[str]]:
    """Build rectangular layout grid from coordinate mapping."""
    if not coordinates:
        return []

    parsed: Dict[Tuple[int, int], str] = {}
    x_values: List[int] = []
    y_values: List[int] = []

    for room_id, coordinate in coordinates.items():
        if not is_valid_coordinate(coordinate):
            continue
        x_value, y_value = parse_coordinate(coordinate)
        parsed[(x_value, y_value)] = room_id
        x_values.append(x_value)
        y_values.append(y_value)

    if not parsed:
        return []

    min_x = min(x_values)
    max_x = max(x_values)
    min_y = min(y_values)
    max_y = max(y_values)

    layout: List[List[str]] = []
    for y_value in range(min_y, max_y + 1):
        row: List[str] = []
        for x_value in range(min_x, max_x + 1):
            row.append(parsed.get((x_value, y_value), "   "))
        layout.append(row)
    return layout


def _normalize_reference_text(value: Any) -> str:
    """Normalize freeform room text for deterministic phrase matching."""
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _extract_room_reference_aliases(room: Dict[str, Any]) -> List[str]:
    """Build deterministic room aliases used for authored adjacency matching."""
    aliases: List[str] = []

    candidate_values = [
        room.get("name", ""),
        room.get("source_room_title", ""),
        room.get("sourceRoomTitle", ""),
    ]
    for candidate in candidate_values:
        normalized = _normalize_reference_text(candidate)
        if normalized and normalized not in aliases:
            aliases.append(normalized)

    room_name = room.get("name")
    if isinstance(room_name, str) and ":" in room_name:
        suffix = _normalize_reference_text(room_name.split(":", 1)[1])
        if suffix and suffix not in aliases:
            aliases.append(suffix)

    return aliases


def _record_has_adjacency_cues(reference_text: str, direction_hints: List[str]) -> bool:
    """Return True when text likely indicates explicit adjacency intent."""
    if not reference_text:
        return False
    if direction_hints:
        return True
    return any(term in reference_text for term in _ADJACENCY_CUE_TERMS)


def resolve_authored_adjacency(
    room_records: List[Dict[str, Any]],
    fallback_connectivity: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[str]]:
    """Resolve deterministic authored adjacency with bounded fail-open fallback.

    This helper prioritizes explicit room references and directional cues in room
    text. When evidence is weak or ambiguous, it falls back to the provided
    connectivity graph (or source record connectivity) so ingest remains safe.
    """
    room_order: List[str] = []
    room_index: Dict[str, int] = {}
    room_metadata: Dict[str, Dict[str, Any]] = {}
    fallback_by_id: Dict[str, List[str]] = {}
    number_to_room_id: Dict[int, str] = {}

    for index, room in enumerate(room_records):
        room_id = room.get("id") or room.get("locationId")
        if not isinstance(room_id, str) or not room_id.strip() or room_id in room_index:
            continue

        cleaned_id = room_id.strip()
        room_order.append(cleaned_id)
        room_index[cleaned_id] = len(room_order) - 1

        fallback_links: List[str] = []
        source_fallback = None
        if isinstance(fallback_connectivity, dict):
            source_fallback = fallback_connectivity.get(cleaned_id)
        if not isinstance(source_fallback, list):
            source_fallback = room.get("connections", room.get("connectivity", []))
        if isinstance(source_fallback, list):
            for candidate in source_fallback:
                if (
                    isinstance(candidate, str)
                    and candidate != cleaned_id
                    and candidate not in fallback_links
                ):
                    fallback_links.append(candidate)

        source_number = room.get("source_room_number")
        if not isinstance(source_number, int):
            source_number = room.get("sourceRoomNumber")
        if isinstance(source_number, int) and source_number not in number_to_room_id:
            number_to_room_id[source_number] = cleaned_id

        text_chunks = [
            room.get("name", ""),
            room.get("source_room_title", ""),
            room.get("description", ""),
            room.get("raw_content", ""),
            room.get("exit_comment", ""),
        ]
        reference_text = _normalize_reference_text(
            " ".join(str(chunk) for chunk in text_chunks if isinstance(chunk, str))
        )

        directional_hints = _extract_direction_hints(reference_text)
        room_metadata[cleaned_id] = {
            "aliases": _extract_room_reference_aliases(room),
            "reference_text": reference_text,
            "direction_hints": directional_hints,
            "has_cues": _record_has_adjacency_cues(reference_text, directional_hints),
        }
        fallback_by_id[cleaned_id] = fallback_links

    if not room_order:
        return {}

    id_set = set(room_order)

    # Normalize fallback edges for valid room ids only.
    for room_id in room_order:
        filtered = [
            target
            for target in fallback_by_id.get(room_id, [])
            if target in id_set and target != room_id
        ]
        fallback_by_id[room_id] = filtered

    adjacency: Dict[str, Set[str]] = {room_id: set() for room_id in room_order}

    for room_id in room_order:
        metadata = room_metadata.get(room_id, {})
        reference_text = metadata.get("reference_text", "")
        if not isinstance(reference_text, str) or not reference_text:
            continue

        # 1) Explicit room-number references (strongest signal).
        for match in _ROOM_REFERENCE_PATTERN.finditer(reference_text):
            source_number = int(match.group(1))
            target_id = number_to_room_id.get(source_number)
            if target_id and target_id != room_id:
                adjacency[room_id].add(target_id)

        # 2) Explicit room title/name references.
        for target_id in room_order:
            if target_id == room_id:
                continue
            target_aliases = room_metadata.get(target_id, {}).get("aliases", [])
            if not isinstance(target_aliases, list):
                continue
            for alias in target_aliases:
                if not isinstance(alias, str) or len(alias) < 4:
                    continue
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, reference_text):
                    adjacency[room_id].add(target_id)
                    break

        # 3) Directional cues aligned to target room hints.
        source_hints = metadata.get("direction_hints", [])
        if not isinstance(source_hints, list):
            source_hints = []
        for direction_key in source_hints:
            candidate_targets: List[str] = []
            for target_id in room_order:
                if target_id == room_id:
                    continue
                target_hints = room_metadata.get(target_id, {}).get(
                    "direction_hints", []
                )
                if not isinstance(target_hints, list):
                    continue
                if direction_key in target_hints:
                    candidate_targets.append(target_id)
            if candidate_targets:
                candidate_targets.sort(
                    key=lambda candidate: (
                        abs(room_index.get(candidate, 0) - room_index.get(room_id, 0)),
                        room_index.get(candidate, 0),
                    )
                )
                adjacency[room_id].add(candidate_targets[0])

    # Ensure bidirectional edges for deterministic graph parity.
    for room_id in room_order:
        for target_id in list(adjacency[room_id]):
            if target_id in adjacency:
                adjacency[target_id].add(room_id)

    # Bounded fallback: only rooms without extracted edges use safe scaffold.
    for room_id in room_order:
        if adjacency[room_id]:
            continue
        fallback_links = fallback_by_id.get(room_id, [])
        for target_id in fallback_links:
            if target_id in adjacency and target_id != room_id:
                adjacency[room_id].add(target_id)
                adjacency[target_id].add(room_id)

    # Final deterministic ordering and bounded edge count.
    ordered_adjacency: Dict[str, List[str]] = {}
    max_neighbors = 6
    for room_id in room_order:
        sorted_targets = sorted(
            [
                target
                for target in adjacency[room_id]
                if target in id_set and target != room_id
            ],
            key=lambda candidate: room_index.get(candidate, 10**6),
        )
        ordered_adjacency[room_id] = sorted_targets[:max_neighbors]

    return ordered_adjacency


def _normalize_room_records(
    room_records: List[Dict[str, Any]],
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Normalize generic room/location records for shared spatial planning."""
    normalized_order: List[str] = []
    normalized_records: Dict[str, Dict[str, Any]] = {}

    for room in room_records:
        room_id = room.get("id") or room.get("locationId")
        if not isinstance(room_id, str) or not room_id.strip():
            continue
        cleaned_id = room_id.strip()
        if cleaned_id in normalized_records:
            continue

        normalized_order.append(cleaned_id)
        normalized_records[cleaned_id] = {
            "id": cleaned_id,
            "name": room.get("name", cleaned_id),
            "description": room.get("description", ""),
            "type": room.get("type", "room"),
            "raw_connections": room.get("connections", room.get("connectivity", [])),
            "connections": [],
        }

    if not normalized_order:
        return [], {}

    id_set = set(normalized_order)
    for index, room_id in enumerate(normalized_order):
        room_record = normalized_records[room_id]
        raw_connections = room_record.get("raw_connections", [])
        clean_connections: List[str] = []
        if isinstance(raw_connections, list):
            for target_id in raw_connections:
                if (
                    isinstance(target_id, str)
                    and target_id in id_set
                    and target_id != room_id
                    and target_id not in clean_connections
                ):
                    clean_connections.append(target_id)

        if not clean_connections and len(normalized_order) > 1:
            if index > 0:
                clean_connections.append(normalized_order[index - 1])
            if index < len(normalized_order) - 1:
                clean_connections.append(normalized_order[index + 1])

        room_record["connections"] = clean_connections

    # Enforce bidirectional edges for deterministic parity.
    for room_id in normalized_order:
        for target_id in list(normalized_records[room_id]["connections"]):
            reverse_links = normalized_records[target_id]["connections"]
            if room_id not in reverse_links:
                reverse_links.append(room_id)

    # Stable ordering of each room's connections.
    index_lookup = {room_id: idx for idx, room_id in enumerate(normalized_order)}
    for room_id in normalized_order:
        normalized_records[room_id]["connections"] = sorted(
            normalized_records[room_id]["connections"],
            key=lambda candidate: index_lookup.get(candidate, 10**6),
        )

    return normalized_order, normalized_records


def _reserve_coordinate(
    source_coordinate: Tuple[int, int],
    direction_key: str,
    occupied: Set[Tuple[int, int]],
) -> Tuple[int, int]:
    """Reserve a nearby unoccupied coordinate in the requested direction."""
    delta = _DIRECTION_VECTORS.get(direction_key, _DIRECTION_VECTORS["east"])
    for step in range(1, 64):
        candidate = (
            source_coordinate[0] + (delta[0] * step),
            source_coordinate[1] + (delta[1] * step),
        )
        if candidate not in occupied:
            return candidate

    return (
        source_coordinate[0] + delta[0],
        source_coordinate[1] + delta[1],
    )


def _build_semantic_spatial_plan_deterministic(
    room_records: List[Dict[str, Any]],
    start_x: int,
    start_y: int,
) -> Dict[str, Any]:
    """Build semantic coordinates from room metadata and connectivity."""
    room_order, normalized_records = _normalize_room_records(room_records)
    if not room_order:
        return build_linear_spatial_plan([])

    coordinates_xy: Dict[str, Tuple[int, int]] = {}
    occupied: Set[Tuple[int, int]] = set()
    component_index = 0

    for root_id in room_order:
        if root_id in coordinates_xy:
            continue

        component_anchor = (
            start_x + (component_index * 4),
            start_y + (component_index * 2),
        )
        while component_anchor in occupied:
            component_anchor = (component_anchor[0] + 1, component_anchor[1])

        coordinates_xy[root_id] = component_anchor
        occupied.add(component_anchor)
        component_index += 1

        queue: deque[str] = deque([root_id])
        while queue:
            source_id = queue.popleft()
            source_record = normalized_records[source_id]
            source_coordinate = coordinates_xy[source_id]

            for target_id in source_record.get("connections", []):
                if target_id in coordinates_xy:
                    continue

                target_record = normalized_records[target_id]
                priority = _build_direction_priority(source_record, target_record)

                target_coordinate = None
                for direction_key in priority:
                    candidate = _reserve_coordinate(
                        source_coordinate, direction_key, occupied
                    )
                    if candidate not in occupied:
                        target_coordinate = candidate
                        break

                if target_coordinate is None:
                    target_coordinate = (source_coordinate[0] + 1, source_coordinate[1])
                    while target_coordinate in occupied:
                        target_coordinate = (
                            target_coordinate[0] + 1,
                            target_coordinate[1],
                        )

                coordinates_xy[target_id] = target_coordinate
                occupied.add(target_coordinate)
                queue.append(target_id)

    coordinates = {
        room_id: format_coordinate(x_value, y_value)
        for room_id, (x_value, y_value) in coordinates_xy.items()
    }
    connectivity = {
        room_id: list(normalized_records[room_id]["connections"])
        for room_id in room_order
    }

    rooms_for_direction = []
    for room_id in room_order:
        rooms_for_direction.append(
            {
                "id": room_id,
                "coordinates": coordinates.get(
                    room_id, format_coordinate(start_x, start_y)
                ),
                "connections": connectivity.get(room_id, []),
            }
        )

    return {
        "coordinates": coordinates,
        "connectivity": connectivity,
        "directions": build_direction_map_from_rooms(rooms_for_direction),
        "layout": _build_layout_from_coordinates(coordinates),
    }


def _build_structured_spatial_prompt(room_records: List[Dict[str, Any]]) -> str:
    """Build a single shared prompt contract for optional LLM spatial inference."""
    lines: List[str] = []
    for room in room_records:
        room_id = room.get("id", room.get("locationId", ""))
        if not isinstance(room_id, str) or not room_id:
            continue
        room_name = str(room.get("name", room_id)).strip()
        room_type = str(room.get("type", "room")).strip()
        description = str(room.get("description", "")).strip().replace("\n", " ")
        if len(description) > 180:
            description = f"{description[:177]}..."
        connections = room.get("connections", room.get("connectivity", []))
        if isinstance(connections, list):
            connections_text = ", ".join(
                target
                for target in connections
                if isinstance(target, str) and target.strip()
            )
        else:
            connections_text = ""
        lines.append(
            f"- {room_id} | name={room_name} | type={room_type} | connects=[{connections_text}] | desc={description}"
        )

    room_block = "\n".join(lines)
    return (
        "Return STRICT JSON with keys 'coordinates' and 'connectivity'. "
        "Coordinates must be X#Y# strings and connectivity must be arrays of room ids. "
        "Do not include any keys beyond coordinates and connectivity. "
        "Ground placement on directional cues in names/descriptions and listed adjacency.\n\n"
        f"ROOMS:\n{room_block}"
    )


def _resolve_semantic_spatial_plan_with_llm(
    room_records: List[Dict[str, Any]],
    room_order: List[str],
    fallback_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Attempt structured spatial inference via LLM, fail-open to fallback."""
    if not room_order:
        return fallback_plan

    try:
        from model_config import DM_VALIDATION_MODEL
        from utils.ai_client_factory import create_chat_client, get_model_config
    except Exception:
        return fallback_plan

    prompt_text = _build_structured_spatial_prompt(room_records)

    try:
        client = create_chat_client(use_fallback=True)
        model_config = get_model_config("dm_validation", DM_VALIDATION_MODEL)
        response = client.chat.completions.create(
            model=model_config["model"],
            **model_config.get("extra_body", {}),
            temperature=model_config.get("temperature", 0.2),
            messages=[
                {
                    "role": "system",
                    "content": "You produce strict JSON graph layouts for room coordinates.",
                },
                {"role": "user", "content": prompt_text},
            ],
            response_format={"type": "json_object"},
        )
    except Exception:
        return fallback_plan

    content = (
        response.choices[0].message.content if response and response.choices else ""
    )
    parsed = parse_structured_spatial_response(content or "", room_order)

    # Keep deterministic connectivity/directions guardrails from normalized fallback plan.
    parsed_connectivity = parsed.get("connectivity", {})
    if not isinstance(parsed_connectivity, dict):
        parsed_connectivity = fallback_plan.get("connectivity", {})

    merged_plan = {
        "coordinates": parsed.get("coordinates", fallback_plan.get("coordinates", {})),
        "connectivity": parsed_connectivity,
        "directions": parsed.get("directions", {}),
        "layout": parsed.get("layout", []),
    }

    if not merged_plan["layout"]:
        merged_plan["layout"] = _build_layout_from_coordinates(
            merged_plan["coordinates"]
        )

    return merged_plan


def resolve_semantic_spatial_plan(
    room_records: List[Dict[str, Any]],
    start_x: int = 10,
    start_y: int = 10,
    use_llm: bool = False,
) -> Dict[str, Any]:
    """Resolve semantic spatial contract for builder, ingest, and remediation paths."""
    room_order, _ = _normalize_room_records(room_records)
    fallback_plan = _build_semantic_spatial_plan_deterministic(
        room_records,
        start_x=start_x,
        start_y=start_y,
    )
    if not room_order or not use_llm:
        return fallback_plan

    return _resolve_semantic_spatial_plan_with_llm(
        room_records=room_records,
        room_order=room_order,
        fallback_plan=fallback_plan,
    )


def build_tactical_grid(location_name: str, location_type: str) -> List[str]:
    """Create deterministic 3x3 tactical grid (9 elements)."""
    safe_type = (location_type or "area").strip().lower() or "area"
    safe_name = (location_name or "location").strip() or "location"
    center = f"center_{safe_type}:{safe_name}"
    return [
        "northwest:cover",
        "north:approach",
        "northeast:cover",
        "west:approach",
        center,
        "east:approach",
        "southwest:cover",
        "south:approach",
        "southeast:cover",
    ]


def build_location_aliases(
    location_name: str,
    location_id: str,
    existing_aliases: Optional[List[str]] = None,
) -> List[str]:
    """Build stable aliases preserving existing authored aliases first."""
    aliases: List[str] = []
    if isinstance(existing_aliases, list):
        for item in existing_aliases:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned and cleaned not in aliases:
                    aliases.append(cleaned)

    candidates = [location_name, location_id]
    if isinstance(location_name, str) and ":" in location_name:
        suffix = location_name.split(":", 1)[1].strip()
        if suffix:
            candidates.append(suffix)

    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        cleaned = candidate.strip()
        if cleaned and cleaned not in aliases:
            aliases.append(cleaned)

    return aliases


def build_direction_map_from_rooms(
    rooms: List[Dict[str, Any]],
) -> Dict[str, Dict[str, str]]:
    """Build cardinal direction mapping from room coordinates and connections."""
    room_by_id = {
        room.get("id"): room
        for room in rooms
        if isinstance(room.get("id"), str) and room.get("id")
    }
    directions: Dict[str, Dict[str, str]] = {}

    for room_id, room in room_by_id.items():
        room_directions: Dict[str, str] = {}
        source_x, source_y = parse_coordinate(room.get("coordinates"))
        for target_id in room.get("connections", []):
            target_room = room_by_id.get(target_id)
            if not target_room:
                continue
            target_x, target_y = parse_coordinate(target_room.get("coordinates"))
            delta = (target_x - source_x, target_y - source_y)
            direction_key = _DIRECTION_DELTA.get(delta)
            if direction_key:
                room_directions[direction_key] = target_id
        directions[room_id] = room_directions

    return directions


def parse_structured_spatial_response(
    response_text: str,
    expected_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Parse strict JSON response with fail-open fallback for malformed data."""
    fallback = build_linear_spatial_plan(expected_ids)
    if not isinstance(response_text, str) or not response_text.strip():
        return fallback

    try:
        payload = json.loads(response_text)
    except Exception:
        return fallback

    if not isinstance(payload, dict):
        return fallback

    coordinates = payload.get("coordinates")
    connectivity = payload.get("connectivity")
    if not isinstance(coordinates, dict) or not isinstance(connectivity, dict):
        return fallback

    for location_id in expected_ids:
        candidate = coordinates.get(location_id)
        if not is_valid_coordinate(candidate):
            return fallback
        links = connectivity.get(location_id)
        if not isinstance(links, list) or not all(
            isinstance(item, str) for item in links
        ):
            return fallback

    strict_payload = build_linear_spatial_plan(expected_ids)
    strict_payload["coordinates"] = {
        location_id: coordinates[location_id] for location_id in expected_ids
    }
    strict_payload["connectivity"] = {
        location_id: connectivity[location_id] for location_id in expected_ids
    }

    room_records = []
    for location_id in expected_ids:
        room_records.append(
            {
                "id": location_id,
                "coordinates": strict_payload["coordinates"][location_id],
                "connections": strict_payload["connectivity"][location_id],
            }
        )
    strict_payload["directions"] = build_direction_map_from_rooms(room_records)
    strict_payload["layout"] = _build_layout_from_coordinates(
        strict_payload["coordinates"]
    )
    return strict_payload
