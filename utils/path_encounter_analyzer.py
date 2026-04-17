"""
Path Encounter Analyzer - Analyze travel paths for encounters and blocking conditions

This module examines a path between two locations and identifies:
- Unexplored locations with encounters that would block travel
- Monster/NPC encounters along the route
- Safe locations that can be passed through
"""

import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from utils.file_operations import safe_read_json
from utils.enhanced_logger import debug, info, warning
from utils.module_path_manager import ModulePathManager


def analyze_path_for_encounters(
    path: List[str],
    location_graph,
    module_name: str,
    world_conditions: Optional[Dict] = None
) -> Dict:
    """
    Analyze a path for encounters, exploration status, and blocking conditions.

    Args:
        path: List of location IDs representing the path (e.g., ["A01", "B02", "C01"])
        location_graph: LocationGraph instance with loaded module data
        module_name: Current module name
        world_conditions: Optional world state dict; may contain
            'resolvedHostilesByLocation' mapping location_id -> bool to mark
            peacefully resolved hostile locations as safe for travel.

    Note:
        Visited status determined by checking if encounters array has entries
        OR if location is marked resolved in world_conditions.
        Empty encounters array and not resolved = location not yet visited/explored.
        Has encounters or marked resolved = location has been visited.

    Returns:
        Dict with:
        {
            "has_unexplored": bool,
            "first_unexplored_with_encounters": str or None,
            "first_blocking_location": str or None,
            "path_segments": [
                {
                    "location_id": "A01",
                    "location_name": "Market",
                    "area_id": "HFG001",
                    "area_name": "Greenfields Vale",
                    "status": "visited" | "unexplored",
                    "has_monsters": bool,
                    "has_encounter_entries": bool,
                    "monster_count": int,
                    "monster_names": [...],
                    "blocks_travel": bool,
                    "reason": "Has unresolved combat encounter"
                }
            ],
            "safe_to_auto_travel": bool,
            "requires_stop": bool,
            "stop_reason": str
        }
    """
    debug(f"Analyzing path for encounters: {' -> '.join(path)}", category="path_analysis")

    path_manager = ModulePathManager(module_name)
    result = {
        "has_unexplored": False,
        "first_unexplored_with_encounters": None,
        "first_blocking_location": None,
        "path_segments": [],
        "safe_to_auto_travel": True,
        "requires_stop": False,
        "stop_reason": ""
    }

    for location_id in path:
        # Get location info from graph
        node_info = location_graph.nodes.get(location_id)
        if not node_info:
            warning(f"Location {location_id} not found in graph", category="path_analysis")
            continue

        area_id = node_info.get('area_id')
        location_name = node_info.get('location_name', 'Unknown')
        area_name = location_graph.area_data.get(area_id, {}).get('areaName', 'Unknown')

        # Load area file to check for monsters/encounters
        area_file = path_manager.get_area_path(area_id)
        monsters = []
        encounters = []
        has_monsters = False
        has_encounter_entries = False

        if os.path.exists(area_file):
            area_data = safe_read_json(area_file)
            if area_data:
                # Find this specific location in the area file
                for location in area_data.get('locations', []):
                    if location.get('locationId') == location_id:
                        monsters = location.get('monsters', [])
                        encounters = location.get('encounters', [])
                        has_monsters = len(monsters) > 0

                        # Check for GAMEPLAY encounters (have encounterId key)
                        # Template encounters (type/description) don't count as visited
                        has_encounter_entries = any(
                            isinstance(e, dict) and 'encounterId' in e
                            for e in encounters
                        )
                        break

        # Check exploration status
        # If encounters array has GAMEPLAY entries (with encounterId), location visited
        # Template encounters (type/description) or empty array = not yet explored
        # Also consider location visited if marked resolved in world_conditions
        resolved_hostiles = (
            world_conditions.get("resolvedHostilesByLocation", {})
            if world_conditions else {}
        )
        is_resolved = resolved_hostiles.get(location_id, False) if isinstance(resolved_hostiles, dict) else False
        is_visited = has_encounter_entries or is_resolved
        status = "visited" if is_visited else "unexplored"

        # Determine if this location blocks travel
        # Block if: NOT visited (empty encounters array) AND has monsters defined
        blocks_travel = False
        block_reason = ""

        if not is_visited and has_monsters:
            blocks_travel = True
            block_reason = "Unexplored location with hostile monsters"
            result["has_unexplored"] = True

            # Set first blocking location
            if not result["first_blocking_location"]:
                result["first_blocking_location"] = location_id
                result["first_unexplored_with_encounters"] = location_id
                result["safe_to_auto_travel"] = False
                result["requires_stop"] = True
                result["stop_reason"] = (
                    f"Party must stop at {location_id} ({location_name}) "
                    f"to resolve monster encounters before continuing"
                )

        # Build segment info
        segment = {
            "location_id": location_id,
            "location_name": location_name,
            "area_id": area_id,
            "area_name": area_name,
            "status": status,
            "has_monsters": has_monsters,
            "has_encounter_entries": has_encounter_entries,
            "is_resolved": is_resolved,
            "monster_count": len(monsters),
            "monster_names": [m.get('name', 'Unknown') for m in monsters if isinstance(m, dict)],
            "blocks_travel": blocks_travel,
            "reason": block_reason
        }

        result["path_segments"].append(segment)

    debug(f"Path analysis complete: {len(result['path_segments'])} segments", category="path_analysis")
    if result["requires_stop"]:
        debug(f"Travel blocked at: {result['first_blocking_location']}", category="path_analysis")

    return result


def get_encounter_summary_for_location(location_id: str, area_id: str, module_name: str) -> str:
    """
    Get a summary of encounters at a specific location.

    Args:
        location_id: Location ID (e.g., "C01")
        area_id: Area ID (e.g., "CMS001")
        module_name: Module name

    Returns:
        String summary of encounters for narrative guidance
    """
    path_manager = ModulePathManager(module_name)
    area_file = path_manager.get_area_path(area_id)

    if not os.path.exists(area_file):
        return "No encounter data available"

    area_data = safe_read_json(area_file)
    if not area_data:
        return "Could not load area data"

    # Find location
    for location in area_data.get('locations', []):
        if location.get('locationId') == location_id:
            location_name = location.get('name', 'Unknown')
            monsters = location.get('monsters', [])
            encounters = location.get('encounters', [])

            if not monsters and not encounters:
                return f"No encounters at {location_name}"

            summary_parts = [f"At {location_name}:"]

            if monsters:
                monster_names = [m.get('name', 'Unknown') for m in monsters if isinstance(m, dict)]
                summary_parts.append(f"  Monsters: {', '.join(monster_names)}")

            if encounters:
                encounter_count = len([e for e in encounters if e])
                summary_parts.append(f"  Encounters: {encounter_count} defined")

            return "\n".join(summary_parts)

    return f"Location {location_id} not found in area {area_id}"


def build_path_context_for_ai(path_analysis: Dict) -> str:
    """
    Build a narrative-friendly path context for the transition validator AI.

    Args:
        path_analysis: Result from analyze_path_for_encounters()

    Returns:
        Formatted string for AI consumption
    """
    if not path_analysis["path_segments"]:
        return "ERROR: No path data available"

    lines = ["TRAVEL PATH ANALYSIS:", "=" * 60]

    for i, segment in enumerate(path_analysis["path_segments"], 1):
        loc_id = segment["location_id"]
        loc_name = segment["location_name"]
        area_name = segment["area_name"]
        status = segment["status"]

        # Build status indicator
        if segment["blocks_travel"]:
            status_marker = "[BLOCKS TRAVEL]"
        elif status == "unexplored" and segment.get("has_monsters"):
            status_marker = "[UNEXPLORED - HAS MONSTERS]"
        elif status == "unexplored":
            status_marker = "[UNEXPLORED - SAFE]"
        else:
            status_marker = "[VISITED]"

        line = f"{i}. {loc_id}: {loc_name} ({area_name}) {status_marker}"
        lines.append(line)

        # Add monster details for unexplored locations
        if status == "unexplored" and segment.get("has_monsters"):
            if segment.get("monster_names"):
                lines.append(f"   Monsters: {', '.join(segment['monster_names'])}")

    lines.append("=" * 60)

    if path_analysis["requires_stop"]:
        lines.append(f"\nBLOCKING CONDITION: {path_analysis['stop_reason']}")
    else:
        lines.append("\nPath is clear for travel")

    return "\n".join(lines)
