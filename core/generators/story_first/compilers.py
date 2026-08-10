# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Pure deterministic compilers for the story-first generation path."""

from __future__ import annotations

import copy
import re
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple


ASCII_TYPOGRAPHY_REPLACEMENTS = MappingProxyType(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
)


class GraphEmbeddingError(ValueError):
    """Bounded, prose-free failure category for deterministic grid embedding."""

    _REASONS = frozenset({"search_budget_exhausted", "non_embeddable"})

    def __init__(self, edges: Iterable[Tuple[str, str]], reason: str):
        if reason not in self._REASONS:
            raise ValueError("invalid graph embedding error reason")
        self.edges = tuple(sorted(set(tuple(sorted(edge)) for edge in edges)))
        self.reason = reason
        super().__init__(reason)


_GRID_DELTAS = ((0, -1), (1, 0), (0, 1), (-1, 0))


def _local_graph_edges(adjacency: Mapping[str, Set[str]]) -> List[Tuple[str, str]]:
    return sorted(
        (source, target)
        for source in sorted(adjacency)
        for target in sorted(adjacency[source])
        if source < target
    )


def compile_grid_embedding(
    connections: Mapping[str, Iterable[str]], max_states: int = 250_000
) -> Dict[str, Tuple[int, int]]:
    """Deterministically embed one small undirected graph as an induced grid graph."""
    adjacency = {
        str(node): {str(target) for target in targets}
        for node, targets in connections.items()
    }
    nodes = sorted(adjacency)
    if not nodes:
        raise GraphEmbeddingError((), "non_embeddable")
    edges = _local_graph_edges(adjacency)
    if any(node in targets for node, targets in adjacency.items()):
        raise GraphEmbeddingError(edges, "non_embeddable")
    if any(
        target not in adjacency or node not in adjacency[target]
        for node, targets in adjacency.items()
        for target in targets
    ):
        raise GraphEmbeddingError(edges, "non_embeddable")
    excessive = [node for node in nodes if len(adjacency[node]) > 4]
    if excessive:
        incident = [edge for edge in edges if set(edge) & set(excessive)]
        raise GraphEmbeddingError(incident, "non_embeddable")
    reached = {nodes[0]}
    frontier = [nodes[0]]
    while frontier:
        source = frontier.pop()
        for target in sorted(adjacency[source] - reached):
            reached.add(target)
            frontier.append(target)
    if reached != set(nodes):
        raise GraphEmbeddingError(edges, "non_embeddable")

    positions: Dict[str, Tuple[int, int]] = {nodes[0]: (0, 0)}
    occupied = {(0, 0)}
    visited_states = 0
    search_budget_exhausted = False
    solved: Optional[Dict[str, Tuple[int, int]]] = None

    def adjacent_cells(position: Tuple[int, int]) -> Set[Tuple[int, int]]:
        x, y = position
        return {(x + dx, y + dy) for dx, dy in _GRID_DELTAS}

    def still_has_capacity() -> bool:
        placed = set(positions)
        for node, position in positions.items():
            remaining_neighbors = len(adjacency[node] - placed)
            free_neighbors = sum(
                candidate not in occupied for candidate in adjacent_cells(position)
            )
            if remaining_neighbors > free_neighbors:
                return False
        return True

    def search() -> bool:
        nonlocal search_budget_exhausted, solved, visited_states
        visited_states += 1
        if visited_states > max_states:
            search_budget_exhausted = True
            return False
        if len(positions) == len(nodes):
            solved = dict(positions)
            return True
        placed = set(positions)
        frontier_nodes = [
            node for node in nodes if node not in placed and adjacency[node] & placed
        ]
        if not frontier_nodes:
            return False
        node = min(
            frontier_nodes,
            key=lambda item: (
                -len(adjacency[item] & placed),
                -len(adjacency[item]),
                item,
            ),
        )
        placed_neighbors = sorted(adjacency[node] & placed)
        candidates = adjacent_cells(positions[placed_neighbors[0]])
        for neighbor in placed_neighbors[1:]:
            candidates &= adjacent_cells(positions[neighbor])
        ordered = sorted(
            (candidate for candidate in candidates if candidate not in occupied),
            key=lambda point: (abs(point[0]) + abs(point[1]), point[1], point[0]),
        )
        for candidate in ordered:
            if any(
                (
                    (abs(candidate[0] - position[0]) + abs(candidate[1] - position[1]))
                    == 1
                )
                != (other in adjacency[node])
                for other, position in positions.items()
            ):
                continue
            positions[node] = candidate
            occupied.add(candidate)
            if still_has_capacity() and search():
                return True
            occupied.remove(candidate)
            positions.pop(node)
        return False

    if not search() or solved is None:
        raise GraphEmbeddingError(
            edges,
            (
                "search_budget_exhausted"
                if search_budget_exhausted
                else "non_embeddable"
            ),
        )
    min_x = min(point[0] for point in solved.values())
    min_y = min(point[1] for point in solved.values())
    return {
        node: (position[0] - min_x + 1, position[1] - min_y + 1)
        for node, position in sorted(solved.items())
    }


def normalize_ascii_typography(value: Any) -> Tuple[Any, int]:
    """Deep-copy one JSON value while replacing only lossless typography."""
    replacements = 0

    def visit(item: Any) -> Any:
        nonlocal replacements
        if isinstance(item, dict):
            return {key: visit(child) for key, child in item.items()}
        if isinstance(item, list):
            return [visit(child) for child in item]
        if not isinstance(item, str):
            return copy.deepcopy(item)
        normalized = []
        for char in item:
            replacement = ASCII_TYPOGRAPHY_REPLACEMENTS.get(char)
            if replacement is None:
                normalized.append(char)
            else:
                normalized.append(replacement)
                replacements += 1
        return "".join(normalized)

    return visit(value), replacements


def compile_redundant_binding_mechanics(
    binding: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Resolve only redundant anchor claims and exact duplicate passage records."""
    compiled = copy.deepcopy(binding)
    roles = {
        (area["areaRoleId"], role["roleKey"]): role
        for area in compiled["areas"]
        for role in area["locationRoles"]
    }
    beat_claim_additions = 0
    for anchor in compiled["beatAnchors"]:
        role = roles.get((anchor["areaRoleId"], anchor["roleKey"]))
        if role is not None and anchor["beatId"] not in role["beatIds"]:
            role["beatIds"].append(anchor["beatId"])
            beat_claim_additions += 1

    passages = []
    endpoints_seen = set()
    collapsed_passages = 0
    for link in compiled["crossAreaLinks"]:
        endpoints = tuple(
            sorted(
                (
                    (link["fromAreaRoleId"], link["fromRoleKey"]),
                    (link["toAreaRoleId"], link["toRoleKey"]),
                )
            )
        )
        if endpoints in endpoints_seen:
            collapsed_passages += 1
            continue
        endpoints_seen.add(endpoints)
        passages.append(link)
    compiled["crossAreaLinks"] = passages
    return compiled, {
        "deterministicAnchorBeatClaimAdditions": beat_claim_additions,
        "deterministicExactPassageDuplicatesCollapsed": collapsed_passages,
    }


def compile_area_binding(
    binding: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
    """Assign runtime IDs/coordinates without authoring fictional content."""
    areas: List[Dict[str, Any]] = []
    maps: List[Dict[str, Any]] = []
    beat_locations: Dict[str, str] = {}
    compiled_by_area: Dict[str, Dict[str, Any]] = {}
    location_ids_by_role: Dict[Tuple[str, str], str] = {}

    for area_index, authored in enumerate(binding["areas"]):
        prefix = chr(ord("A") + area_index)
        authored_roles = sorted(
            authored["locationRoles"], key=lambda role: role["roleKey"]
        )
        role_to_location = {
            role["roleKey"]: f"{prefix}{index:02d}"
            for index, role in enumerate(authored_roles, start=1)
        }
        role_positions = compile_grid_embedding(
            {role["roleKey"]: role["connections"] for role in authored_roles}
        )
        for role_key, location_id in role_to_location.items():
            location_ids_by_role[(authored["areaRoleId"], role_key)] = location_id
        stubs = []
        rooms = []
        for role in authored_roles:
            location_id = role_to_location[role["roleKey"]]
            connections = [role_to_location[key] for key in sorted(role["connections"])]
            x, y = role_positions[role["roleKey"]]
            coordinates = f"X{x}Y{y}"
            stubs.append(
                {
                    "locationId": location_id,
                    "name": role["name"],
                    "type": role["type"],
                    "coordinates": coordinates,
                    "connectivity": connections,
                    "areaConnectivity": [],
                    "areaConnectivityId": [],
                    "storyPurpose": role["storyPurpose"],
                    "beatIds": role["beatIds"],
                    "dangerLevel": authored["dangerLevel"],
                }
            )
            rooms.append(
                {
                    "id": location_id,
                    "name": role["name"],
                    "connections": connections,
                    "coordinates": coordinates,
                    "type": role["type"],
                    "purpose": role["storyPurpose"],
                }
            )
        width = max(x for x, _ in role_positions.values())
        height = max(y for _, y in role_positions.values())
        layout = [["   " for _ in range(width)] for _ in range(height)]
        for role_key, (x, y) in role_positions.items():
            layout[y - 1][x - 1] = role_to_location[role_key]
        area_id = authored["areaRoleId"]
        areas.append(
            {
                "areaName": authored["areaName"],
                "areaId": area_id,
                "areaDescription": authored["areaDescription"],
                "areaType": authored["areaType"],
                "dangerLevel": authored["dangerLevel"],
                "recommendedLevel": authored["recommendedLevel"],
                "locations": stubs,
            }
        )
        compiled_by_area[area_id] = areas[-1]
        maps.append(
            {
                "mapName": authored["areaName"],
                "mapId": f"MAP_{area_id}",
                "totalRooms": len(rooms),
                "startRoom": rooms[0]["id"],
                "version": "story-first-v1",
                "notes": "Compiled from model-authored location roles.",
                "rooms": rooms,
                "layout": layout,
            }
        )

    for link in binding["crossAreaLinks"]:
        source_area = link["fromAreaRoleId"]
        target_area = link["toAreaRoleId"]
        source_location = location_ids_by_role[(source_area, link["fromRoleKey"])]
        target_location = location_ids_by_role[(target_area, link["toRoleKey"])]
        source_data = next(
            item
            for item in compiled_by_area[source_area]["locations"]
            if item["locationId"] == source_location
        )
        target_data = next(
            item
            for item in compiled_by_area[target_area]["locations"]
            if item["locationId"] == target_location
        )
        source_data["areaConnectivity"].append(
            compiled_by_area[target_area]["areaName"]
        )
        source_data["areaConnectivityId"].append(target_location)
        target_data["areaConnectivity"].append(
            compiled_by_area[source_area]["areaName"]
        )
        target_data["areaConnectivityId"].append(source_location)

    for anchor in binding["beatAnchors"]:
        beat_locations[anchor["beatId"]] = location_ids_by_role[
            (anchor["areaRoleId"], anchor["roleKey"])
        ]
    return areas, maps, beat_locations


def compile_plot_skeleton(
    outline: Mapping[str, Any],
    beat_locations: Mapping[str, str],
    beat_to_plot: Mapping[str, str],
    thread_to_quest: Mapping[str, str],
) -> Dict[str, Any]:
    """Compile every runtime plot mechanic from already accepted story data."""
    beats = list(outline["beats"])
    forward = {beat_to_plot[beat["id"]]: [] for beat in beats}
    for beat in beats:
        point_id = beat_to_plot[beat["id"]]
        for prerequisite in beat["prerequisites"]:
            forward[beat_to_plot[prerequisite]].append(point_id)

    points = []
    points_by_beat = {}
    for beat in beats:
        beat_id = beat["id"]
        point = {
            "id": beat_to_plot[beat_id],
            "title": "",
            "description": "",
            "location": beat_locations[beat_id],
            "nextPoints": list(forward[beat_to_plot[beat_id]]),
            "status": "not started",
            "plotImpact": "",
            "sideQuests": [],
        }
        points.append(point)
        points_by_beat[beat_id] = point

    for thread in outline["sideThreads"]:
        anchor_beat = thread["anchorBeatId"]
        quest_id = thread_to_quest[thread["id"]]
        projection = compile_side_thread_projection(thread, quest_id)
        points_by_beat[anchor_beat]["sideQuests"].append(
            {
                "id": quest_id,
                "title": projection["title"],
                "description": projection["description"],
                "involvedLocations": [beat_locations[anchor_beat]],
                "status": "not started",
                "plotImpact": "",
            }
        )
    return {
        "plotTitle": "",
        "mainObjective": "",
        "plotPoints": points,
    }


def compile_side_thread_projection(
    thread: Mapping[str, Any], quest_id: str
) -> Dict[str, str]:
    """Project one accepted creative thread into exact runtime prose fields."""
    title = str(thread["title"])
    description = f"{thread['hook']} Main-story payoff: {thread['mainStoryPayoff']}"
    return {
        "title": title,
        "description": description,
        "plotHook": f"[{quest_id}] {title}: {description}",
    }


def project_side_threads_to_locations(
    areas: List[Dict[str, Any]],
    outline: Mapping[str, Any],
    beat_locations: Mapping[str, str],
    thread_to_quest: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """Install each accepted thread exactly once at its compiled host location."""
    projected = copy.deepcopy(areas)
    locations = {
        location["locationId"]: location
        for area in projected
        for location in area["locations"]
    }
    for thread in outline["sideThreads"]:
        quest_id = thread_to_quest[thread["id"]]
        canonical = compile_side_thread_projection(thread, quest_id)["plotHook"]
        host_id = beat_locations[thread["anchorBeatId"]]
        if host_id not in locations:
            raise ValueError("side-thread host location is missing")
        for location in locations.values():
            location["plotHooks"] = [
                hook for hook in location["plotHooks"] if hook != canonical
            ]
        locations[host_id]["plotHooks"].append(canonical)
    return projected


def merge_plot_narrative(
    skeleton: Mapping[str, Any], narrative: Mapping[str, Any]
) -> Dict[str, Any]:
    """Overlay only narrative slots onto a detached deterministic skeleton."""
    merged = copy.deepcopy(skeleton)
    narrative_points = list(narrative["plotPoints"])
    if len(merged["plotPoints"]) != len(narrative_points):
        raise ValueError("plot narrative cardinality differs from compiled skeleton")

    merged["plotTitle"] = narrative["plotTitle"]
    merged["mainObjective"] = narrative["mainObjective"]
    for point, authored in zip(merged["plotPoints"], narrative_points):
        for field in ("title", "description", "plotImpact"):
            point[field] = authored[field]
    return merged


def migrate_initial_encounters_to_dm_guidance(
    generated_areas: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Preserve hypothetical scenes and clear the runtime history ledger."""
    migrated = copy.deepcopy(generated_areas)
    moved_count = 0
    for area in migrated:
        for location in area["locations"]:
            encounters = location.get("encounters", [])
            if encounters:
                guidance = []
                for encounter in encounters:
                    line = f"Potential scene: {encounter['summary'].strip()}"
                    impact = encounter["impact"].strip()
                    if impact:
                        line += f" Possible impact: {impact}"
                    guidance.append(line)
                location["dmInstructions"] = (
                    location["dmInstructions"].rstrip()
                    + "\n\nPOTENTIAL SCENE GUIDANCE (not completed history):\n"
                    + "\n".join(f"- {line}" for line in guidance)
                )
                moved_count += len(encounters)
            location["encounters"] = []
    return migrated, moved_count


def preserve_potential_scene_guidance(base: str, repaired: str) -> str:
    """Keep accepted hypothetical-scene prose exact across focused repair."""
    marker = "POTENTIAL SCENE GUIDANCE (not completed history):"
    if marker not in base:
        return repaired
    return repaired.split(marker, 1)[0].rstrip() + "\n\n" + base[base.index(marker) :]


def add_level_scaling_precedence(guidance: str) -> str:
    """Make computed level caps authoritative over preserved prose quantities."""
    marker = "POTENTIAL SCENE GUIDANCE (not completed history):"
    rule = (
        "PRECEDENCE: The level-specific roster limits above override any creature "
        "quantities mentioned in the potential scene guidance below."
    )
    if marker not in guidance or rule in guidance:
        return guidance
    return guidance.replace(marker, rule + "\n\n" + marker, 1)


def safe_filename(value: str) -> str:
    """Normalize an accepted display name for a package-local JSON filename."""
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
