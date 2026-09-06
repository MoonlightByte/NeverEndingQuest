#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
Atlas Builder - Assembles all area files into a complete world atlas for AI navigation
Production version that uses area files (not map files) for complete connectivity
"""

from typing import Dict, Any
from pathlib import Path

from utils.path_encounter_analyzer import build_active_module_snapshot, _id_list, _read_json_object


def format_installed_module_references(current_module: str, modules_root: str = "modules") -> str:
    """Share foreign identities with T067 and T065 without pooling route graphs (#307 A2)."""
    lines = [
        "=== INSTALLED MODULE REFERENCES ===",
        "Advisory identities only, not routes, travel permission, or player knowledge.",
        "The current-module atlas is not the whole world. Missing references are not proof of global absence.",
        "Any proposed destination still requires live target lookup and travel preflight.",
    ]
    try:
        registry = _read_json_object(Path(modules_root) / "world_registry.json")
        modules = registry.get("modules")
        if not isinstance(modules, dict):
            raise ValueError("registry modules must be an object")
    except (OSError, ValueError) as exc:
        lines.append(f"Registry references unavailable ({type(exc).__name__}); no absence conclusion is supported.")
        return "\n".join(lines)
    for module in sorted(modules):
        if module.replace(" ", "_") == current_module.replace(" ", "_"):
            continue
        try:
            snapshot = build_active_module_snapshot(module, modules_root)
        except (OSError, ValueError, TypeError) as exc:
            lines.append(f"Module: {module}; SOURCE READ unavailable ({type(exc).__name__}); target lookup still required.")
            continue
        lines.append(f"Module: {snapshot['module_name']}")
        for kind, records in (
            ("LIVE SOURCE LABELS", snapshot["source_records"]),
            ("PRISTINE REFERENCE ONLY, NOT LIVE", snapshot["reference_records"]),
        ):
            for source in records:
                area = source.get("area")
                if not isinstance(area, dict):
                    continue
                lines.append(f"  {kind}: area {area.get('areaId', '')} ({area.get('areaName', '')})")
                locations = area.get("locations")
                for location in locations if isinstance(locations, list) else []:
                    if isinstance(location, dict):
                        lines.append(f"    {location.get('locationId', '')} ({location.get('name', '')})")
        for issue in snapshot["validation_errors"]:
            lines.append(f"  SOURCE DIAGNOSTIC: {issue['code']}: {issue['message']}")
        for issue in snapshot["read_errors"]:
            lines.append(f"  SOURCE READ: {issue['kind']}: {issue['source_file']}")
    return "\n".join(lines)

def extract_location_info(location: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key information from a location"""
    npcs = location.get("npcs", [])
    npcs = npcs if isinstance(npcs, list) else []
    return {
        "id": location.get("locationId"),
        "name": location.get("name", "Unknown"),
        "type": location.get("type", "unknown"),
        "connectivity": _id_list(location.get("connectivity")),
        "areaConnectivity": _id_list(location.get("areaConnectivity")),
        "areaConnectivityId": _id_list(location.get("areaConnectivityId")),
        "npcs": [npc["name"] for npc in npcs if isinstance(npc, dict) and isinstance(npc.get("name"), str)],
        "dangerLevel": location.get("dangerLevel", "unknown"),
        "hasTraps": bool(location.get("traps")),
        "hasMonsters": bool(location.get("monsters")),
        "hasTreasure": bool(location.get("treasures")) or bool(location.get("lootTable"))
    }

def build_atlas_for_module(
    module_name: str, modules_root: str = "modules", *, snapshot=None,
) -> Dict[str, Any]:
    """Render the same detached source records used by travel preflight (#303)."""
    if snapshot is None:
        snapshot = build_active_module_snapshot(module_name, modules_root)
    if snapshot["module_name"] != module_name.replace(" ", "_"):
        raise ValueError("atlas snapshot belongs to a different module")
    
    atlas = {
        "atlas_version": "2.0",
        "module": snapshot["module_name"],
        "validation_errors": list(snapshot["validation_errors"]),
        "read_errors": snapshot.get("read_errors", []),
        "reference_records": snapshot.get("reference_records", []),
        "areas": {},
        "inter_area_connections": [],
        "statistics": {
            "total_areas": 0,
            "total_locations": 0,
            "total_npcs": 0,
            "total_connections": 0
        }
    }
    
    # First pass: Load all areas and their locations
    for source in snapshot["source_records"]:
        area_data = source.get("area")
        if not area_data:
            continue
        
        area_id = area_data.get("areaId")
        if not isinstance(area_id, str) or not area_id or area_id in atlas["areas"]:
            continue
            
        # Extract area information
        desc = area_data.get("areaDescription", "")
        
        area_entry = {
            "name": area_data.get("areaName", "Unknown Area"),
            "type": area_data.get("areaType", "unknown"),
            "description": desc,
            "dangerLevel": area_data.get("dangerLevel", "unknown"),
            "recommendedLevel": area_data.get("recommendedLevel", 0),
            "locations": {}
        }
        
        # Extract all locations in this area
        locations = area_data.get("locations", [])
        for location in locations if isinstance(locations, list) else []:
            if not isinstance(location, dict):
                continue
            loc_id = location.get("locationId")
            if isinstance(loc_id, str) and loc_id and loc_id not in area_entry["locations"]:
                npcs = location.get("npcs", [])
                if not isinstance(npcs, list) or any(
                    not isinstance(npc, dict) or not isinstance(npc.get("name"), str)
                    for npc in npcs
                ):
                    atlas["validation_errors"].append({
                        "code": "invalid_npc_labels",
                        "message": f"Area {area_id} location {loc_id} has malformed NPC labels; usable location identities remain listed.",
                    })
                loc_info = extract_location_info(location)
                area_entry["locations"][loc_id] = loc_info
                
                # Track inter-area connections
                for i, area_conn in enumerate(loc_info.get("areaConnectivity", [])):
                    target_id = loc_info["areaConnectivityId"][i] if i < len(loc_info["areaConnectivityId"]) else "?"
                    atlas["inter_area_connections"].append({
                        "from_area": area_id,
                        "from_location": loc_id,
                        "from_name": loc_info["name"],
                        "to_area": "?",  # We'll resolve this in second pass
                        "to_location": target_id,
                        "to_name": area_conn
                    })
                
                # Update statistics
                atlas["statistics"]["total_npcs"] += len(loc_info.get("npcs", []))
        
        atlas["areas"][area_id] = area_entry
        atlas["statistics"]["total_areas"] += 1
        atlas["statistics"]["total_locations"] += len(area_entry["locations"])
    
    # Second pass: Resolve which area each connection goes to
    for connection in atlas["inter_area_connections"]:
        target_loc_id = connection["to_location"]
        # Search all areas for this location ID
        for area_id, area_data in atlas["areas"].items():
            if target_loc_id in area_data["locations"]:
                connection["to_area"] = area_id
                break
    
    # Third pass: Check for bidirectional connections
    for i, conn in enumerate(atlas["inter_area_connections"]):
        # Look for reverse connection
        reverse_found = False
        for other_conn in atlas["inter_area_connections"]:
            if (other_conn["from_location"] == conn["to_location"] and 
                other_conn["to_location"] == conn["from_location"]):
                reverse_found = True
                break
        conn["bidirectional"] = reverse_found
    
    # Count total connections
    for area_data in atlas["areas"].values():
        for location in area_data["locations"].values():
            atlas["statistics"]["total_connections"] += len(location.get("connectivity", []))
    
    return atlas

def format_atlas_for_conversation(atlas: Dict[str, Any]) -> str:
    """Format atlas into a complete world map for conversation context"""
    lines = []
    lines.append("=== COMPLETE MODULE WORLD ATLAS ===")
    lines.append(f"Module: {atlas['module']}")
    lines.append(f"Areas: {atlas['statistics']['total_areas']}, Locations: {atlas['statistics']['total_locations']}, NPCs: {atlas['statistics']['total_npcs']}")
    lines.append("")
    
    # Build complete location connectivity graph
    lines.append("WORLD MAP STRUCTURE:")
    lines.append("")
    
    for area_id, area_data in atlas.get("areas", {}).items():
        lines.append(f"AREA {area_id}: {area_data['name']} ({area_data['type']})")
        lines.append(f"  Danger Level: {area_data.get('dangerLevel', 'unknown')}, Recommended Level: {area_data.get('recommendedLevel', '?')}")
        
        if area_data.get("locations"):
            lines.append("  Locations:")
            for loc_id, loc_data in area_data["locations"].items():
                # Build location line
                loc_line = f"    {loc_id}: {loc_data['name']} ({loc_data['type']})"
                
                # Add local connections
                if loc_data.get("connectivity"):
                    loc_line += f" -> [{', '.join(loc_data['connectivity'])}]"
                
                # Add special markers
                markers = []
                if loc_data.get("npcs"):
                    markers.append(f"NPCs: {', '.join(loc_data['npcs'])}")
                if loc_data.get("hasTraps"):
                    markers.append("TRAPPED")
                if loc_data.get("hasMonsters"):
                    markers.append("MONSTERS")
                if loc_data.get("hasTreasure"):
                    markers.append("TREASURE")
                
                if markers:
                    loc_line += f" <{', '.join(markers)}>"
                
                lines.append(loc_line)
                
                # Show inter-area connections
                if loc_data.get("areaConnectivity"):
                    for i, conn in enumerate(loc_data["areaConnectivity"]):
                        target_id = loc_data["areaConnectivityId"][i] if i < len(loc_data["areaConnectivityId"]) else "?"
                        lines.append(f"      +--> To {conn} ({target_id})")
        
        lines.append("")  # Blank line between areas
    
    # Add inter-area connection summary
    if atlas.get("inter_area_connections"):
        lines.append("INTER-AREA CONNECTIONS:")
        # Group connections to show bidirectionality
        shown_connections = set()
        for conn in atlas["inter_area_connections"]:
            # Create a connection key to avoid showing duplicates
            conn_key = tuple(sorted([f"{conn['from_area']}:{conn['from_location']}", 
                                    f"{conn['to_area']}:{conn['to_location']}"]))
            if conn_key in shown_connections:
                continue
            shown_connections.add(conn_key)
            
            if conn["to_area"] != "?":
                if conn.get("bidirectional"):
                    # Bidirectional connection
                    lines.append(f"  {conn['from_area']}:{conn['from_location']} ({conn['from_name']}) <--> {conn['to_area']}:{conn['to_location']} ({conn['to_name']}) [BIDIRECTIONAL]")
                else:
                    # One-way connection
                    lines.append(f"  {conn['from_area']}:{conn['from_location']} ({conn['from_name']}) --> {conn['to_area']}:{conn['to_location']} ({conn['to_name']}) [ONE-WAY]")
            else:
                lines.append(f"  {conn['from_area']}:{conn['from_location']} ({conn['from_name']}) --> ??? ({conn['to_name']}) [BROKEN]")
        lines.append("")
    
    # Add navigation summary
    lines.append("NAVIGATION SUMMARY:")
    lines.append(f"  Total Connections: {atlas['statistics']['total_connections']}")
    lines.append(f"  Inter-Area Transitions: {len(atlas.get('inter_area_connections', []))}")
    lines.append("This atlas identifies places; it does not authorize movement or reveal facts to the player.")
    if atlas.get("reference_records"):
        lines.append("PRISTINE REFERENCE LABELS ONLY (not live destinations or route permission):")
        for source in atlas["reference_records"]:
            area = source["area"]
            lines.append(f"  AREA {area['areaId']}: {area.get('areaName', '')}")
            for location in area["locations"]:
                if isinstance(location, dict):
                    lines.append(f"    {location.get('locationId', '')}: {location.get('name', '')}")
    if atlas.get("validation_errors") or atlas.get("read_errors"):
        lines.append("SOURCE DIAGNOSTICS (do not interpret unreadable content as absence):")
        for issue in atlas.get("validation_errors", []):
            lines.append(f"  {issue['code']}: {issue['message']}")
        for issue in atlas.get("read_errors", []):
            lines.append(f"  {issue['kind']}: {issue['source_file']}")
    
    return "\n".join(lines)
