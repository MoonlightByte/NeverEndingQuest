"""
Transition Atlas Builder - Build exploration-aware atlas for travel validation

This is a SEPARATE atlas builder specifically for the transition intelligence agent.
It does NOT modify the main atlas_builder.py used by the game.

Purpose: Provide lightweight, exploration-focused atlas for validating travel requests.
"""

import os
from typing import Dict, List, Any
from utils.file_operations import safe_read_json
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug
from utils.path_encounter_analyzer import derive_location_exploration_state


def build_transition_atlas(location_graph, module_name: str) -> str:
    """
    Build atlas with exploration status markers for transition validation.

    This is optimized for the transition intelligence agent and includes:
    - Exploration status ([VISITED], [UNEXPLORED - SAFE], [UNEXPLORED - HAS MONSTERS])
    - Monster presence indicators
    - Lightweight format (no full descriptions)

    Args:
        location_graph: LocationGraph instance
        module_name: Current module name

    Returns:
        String atlas with exploration markers

    Note:
        New modules use the explicit machine-owned exploration state. Legacy
        modules derive visits from a non-empty adventure summary or a runtime
        encounter record; template encounter definitions alone do not count.
    """
    debug(f"Building transition atlas for {module_name}", category="transition_atlas")

    path_manager = ModulePathManager(module_name)

    lines = []
    lines.append("=== EXPLORATION-AWARE ATLAS ===")
    lines.append(f"Module: {module_name}")
    lines.append("")

    # Group locations by area
    areas_data = {}
    for loc_id, node_info in location_graph.nodes.items():
        area_id = node_info.get('area_id')
        if not area_id:
            continue

        if area_id not in areas_data:
            area_data = location_graph.area_data.get(area_id, {})
            areas_data[area_id] = {
                'name': area_data.get('areaName', 'Unknown'),
                'type': area_data.get('areaType', 'unknown'),
                'danger': area_data.get('dangerLevel', 'unknown'),
                'level': area_data.get('recommendedLevel', 0),
                'locations': []
            }

        # Load area file to check for monsters/encounters
        area_file = path_manager.get_area_path(area_id)
        has_monsters = False
        is_visited = False
        monster_names = []

        if os.path.exists(area_file):
            area_json = safe_read_json(area_file)
            if area_json:
                for location in area_json.get('locations', []):
                    if location.get('locationId') == loc_id:
                        monsters = location.get('monsters', [])
                        has_monsters = len(monsters) > 0
                        is_visited = derive_location_exploration_state(location)["visited"]
                        monster_names = [m.get('name', 'Unknown') for m in monsters if isinstance(m, dict)]
                        break

        # Determine status marker
        if is_visited:
            status_marker = "[VISITED]"
        else:
            # Unexplored location
            if has_monsters:
                status_marker = "[UNEXPLORED - HAS MONSTERS]"
            else:
                status_marker = "[UNEXPLORED - SAFE]"

        # Build location line
        location_name = node_info.get('location_name', 'Unknown')
        loc_type = node_info.get('data', {}).get('type', 'unknown')

        loc_line = f"{loc_id}: {location_name} ({loc_type}) {status_marker}"

        # Add monster info for unexplored dangerous locations
        if not is_visited and monster_names:
            loc_line += f" [Monsters: {', '.join(monster_names)}]"

        # Add internal connections
        connectivity = location_graph.edges.get(loc_id, [])
        if connectivity:
            # Filter to only same-area connections for clarity
            same_area_connections = [
                conn_id for conn_id in connectivity
                if location_graph.nodes.get(conn_id, {}).get('area_id') == area_id
            ]
            if same_area_connections:
                loc_line += f" -> [{', '.join(same_area_connections)}]"

        # Add area connections
        location_data = node_info.get('data', {})
        area_connectivity = location_data.get('areaConnectivity', [])
        area_connectivity_ids = location_data.get('areaConnectivityId', [])
        if area_connectivity and area_connectivity_ids:
            for area_name, loc_id_target in zip(area_connectivity, area_connectivity_ids):
                loc_line += f"\n      +--> To {area_name} ({loc_id_target})"

        areas_data[area_id]['locations'].append(loc_line)

    # Format output by area
    for area_id in sorted(areas_data.keys()):
        area = areas_data[area_id]
        lines.append(f"AREA {area_id}: {area['name']} ({area['type']})")
        lines.append(f"  Danger: {area['danger']}, Recommended Level: {area['level']}")
        lines.append("  Locations:")
        for loc_line in area['locations']:
            lines.append(f"    {loc_line}")
        lines.append("")

    # Add legend
    lines.append("LEGEND:")
    lines.append("  [VISITED] - Location has explicit or legacy runtime visit evidence")
    lines.append("  [UNEXPLORED - SAFE] - Not visited, no monsters defined (safe passage)")
    lines.append("  [UNEXPLORED - HAS MONSTERS] - Not visited, has monsters defined (BLOCKS TRAVEL)")

    return "\n".join(lines)
