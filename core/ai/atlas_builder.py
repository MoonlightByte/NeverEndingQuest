#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
Atlas Builder - Assembles all area files into a complete world atlas for AI navigation
Production version that uses area files (not map files) for complete connectivity
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

def safe_load_json(path: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON file"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Silent fail for production
        return None

def list_area_files(module_root: str) -> List[str]:
    """Find all area JSON files in a module's areas directory"""
    areas_dir = os.path.join(module_root, "areas")
    if not os.path.exists(areas_dir):
        return []
    
    area_files = []
    for fn in os.listdir(areas_dir):
        if fn.endswith(".json") and not fn.endswith("_BU.json") and not fn.endswith(".bak"):
            # Skip backup files
            if "_backup" not in fn and ".backup" not in fn:
                area_files.append(os.path.join(areas_dir, fn))
    return sorted(area_files)

def extract_location_info(location: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key information from a location"""
    return {
        "id": location.get("locationId"),
        "name": location.get("name", "Unknown"),
        "type": location.get("type", "unknown"),
        "connectivity": location.get("connectivity", []),
        "areaConnectivity": location.get("areaConnectivity", []),
        "areaConnectivityId": location.get("areaConnectivityId", []),
        "npcs": [npc.get("name", "Unknown") for npc in location.get("npcs", [])],
        "dangerLevel": location.get("dangerLevel", "unknown"),
        "hasTraps": len(location.get("traps", [])) > 0,
        "hasMonsters": len(location.get("monsters", [])) > 0,
        "hasTreasure": len(location.get("treasures", [])) > 0 or len(location.get("lootTable", [])) > 0
    }

def build_atlas_for_module(module_name: str, modules_root: str = "modules") -> Dict[str, Any]:
    """Build a complete atlas from area files for a single module"""
    module_root = os.path.join(modules_root, module_name)
    area_files = list_area_files(module_root)
    
    atlas = {
        "atlas_version": "2.0",
        "module": module_name,
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
    for area_path in area_files:
        area_data = safe_load_json(area_path)
        if not area_data:
            continue
        
        area_id = area_data.get("areaId")
        if not area_id:
            continue
            
        # Extract area information
        # Get description and safely truncate
        desc = area_data.get("areaDescription", "")
        if len(desc) > 200:
            desc = desc[:197] + "..."
        
        area_entry = {
            "name": area_data.get("areaName", "Unknown Area"),
            "type": area_data.get("areaType", "unknown"),
            "description": desc,
            "dangerLevel": area_data.get("dangerLevel", "unknown"),
            "recommendedLevel": area_data.get("recommendedLevel", 0),
            "locations": {}
        }
        
        # Extract all locations in this area
        for location in area_data.get("locations", []):
            loc_id = location.get("locationId")
            if loc_id:
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
                    markers.append(f"NPCs: {', '.join(loc_data['npcs'][:3])}")  # First 3 NPCs
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
    
    return "\n".join(lines)