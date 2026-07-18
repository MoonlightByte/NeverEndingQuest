#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# LOCATION_PATH_FINDER.PY - SPATIAL VALIDATION SYSTEM
# ============================================================================
# 
# ARCHITECTURE ROLE: Validation Layer - Movement and Connectivity Validation
# 
# This module implements graph-based pathfinding for location transitions,
# ensuring players can only move through connected areas. It demonstrates
# our "Defense in Depth" validation approach for game rule enforcement.
# 
# KEY RESPONSIBILITIES:
# - Build connectivity graphs from module area data
# - Validate movement requests against actual location connections
# - Find shortest paths between locations across multiple areas
# - Detect unreachable locations and connectivity issues
# - Provide detailed path information for DM reference
# 
# PATHFINDING ALGORITHM:
# - Breadth-First Search (BFS) for shortest path finding
# - Graph construction from area connectivity data
# - Support for both within-area and cross-area movement
# - Efficient caching of commonly requested paths
# 
# CONNECTIVITY MODEL:
# Module -> Areas (HH001, G001) -> Locations (A01, B02) -> Connections
# - Within-area: Direct location-to-location connections
# - Cross-area: Special transition locations with areaConnectivity
# - Hidden passages: Conditional connections based on game state
# 
# ARCHITECTURAL INTEGRATION:
# - Used by main.py for movement validation in AI response processing
# - Integrates with ModulePathManager for area data loading
# - Supports action_handler.py location transition validation
# - Implements our "Data Integrity Above All" principle
# 
# VALIDATION FEATURES:
# - Real-time connectivity verification
# - Path distance calculation for DM reference
# - Unreachable location detection
# - ASCII-safe output for cross-platform compatibility
# 
# This module ensures movement rules are consistently enforced while
# providing helpful information for both AI and human DMs.
# ============================================================================

"""
Location Path Finder for NeverEndingQuest

This script determines the path between two locations across areas in the module.
It builds a graph of all locations and their connections, then finds the shortest path.
Uses location IDs (A01, B02, etc.) internally but accepts both IDs and names as input.

Usage:
    python location_path_finder.py <from_location_id_or_name> <to_location_id_or_name>
    
Examples:
    python location_path_finder.py "A01" "C08"
    python location_path_finder.py "Harrow's Hollow General Store" "Secret Passage"
"""

import json
import os
import sys
from collections import deque, defaultdict
from typing import Dict, List, Tuple, Optional
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_refresh_lock import module_refresh_lock

def write_debug(message: str):
    """Write debug message to debug.txt file"""
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug", "location_pathfinder_debug.txt"), "a", encoding="utf-8") as f:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass  # Silently fail if debug file can't be written


class LocationGraph:
    """Graph representation of all locations and their connections"""
    
    def __init__(self):
        self.nodes = {}  # location_id -> {area_id, location_name, data}
        self.edges = defaultdict(list)  # location_id -> [connected_location_ids]
        self.area_data = {}  # area_id -> area_data
        self.id_to_name = {}  # location_id -> location_name
        self.name_to_id = {}  # location_name -> location_id

    def reload(self):
        """Clears and reloads all module data for the graph."""
        print("DEBUG: [LocationGraph.reload] Reloading all graph data...")
        self.nodes = {}
        self.edges = defaultdict(list)
        self.area_data = {}
        self.id_to_name = {}
        self.name_to_id = {}
        self.load_module_data()
        print(f"DEBUG: [LocationGraph.reload] Reload complete. Total nodes: {len(self.nodes)}")

    def load_module_data(self):
        """Load all area data and build the graph"""
        print("DEBUG: [LocationGraph.load_module_data] Starting to load module data...")
        # Load world registry to get all available modules
        world_registry_path = "modules/world_registry.json"
        world_registry = safe_read_json(world_registry_path)
        
        if not world_registry or 'modules' not in world_registry:
            write_debug("  [ERROR] Could not load world registry")
            # Fallback to current module only
            # Get current module from party tracker for consistent path resolution
            try:
                party_tracker = safe_read_json("party_tracker.json")
                current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
                path_manager = ModulePathManager(current_module)
            except:
                path_manager = ModulePathManager()  # Fallback to reading from file
            area_ids = path_manager.get_area_ids()
            if not area_ids:
                write_debug("  [WARNING] No area files found in module")
                return
            write_debug(f"Loading module areas... (discovered: {', '.join(area_ids)})")
            for area_id in area_ids:
                area_file = path_manager.get_area_path(area_id)
                if os.path.exists(area_file):
                    area_data = safe_read_json(area_file)
                    if area_data:
                        self.area_data[area_id] = area_data
                        self._process_area_locations(area_id, area_data)
                        write_debug(f"  [OK] Loaded {area_id}: {area_data.get('areaName', 'Unknown')}")
        else:
            # Load areas from ALL modules in the world registry
            all_areas_by_module = {}
            
            # Get current module for priority loading
            try:
                party_tracker = safe_read_json("party_tracker.json")
                current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
                current_path_manager = ModulePathManager(current_module)
                if not current_module:
                    current_module = current_path_manager.module_name
            except:
                current_path_manager = ModulePathManager()  # Fallback to reading from file
                current_module = current_path_manager.module_name
            
            # Process all modules in world registry
            for module_name in world_registry['modules']:
                module_path_manager = ModulePathManager(module_name)
                module_area_ids = module_path_manager.get_area_ids()
                
                if module_area_ids:
                    all_areas_by_module[module_name] = module_area_ids
            
            # Create discovery string with module attribution
            discovery_parts = []
            for module_name, area_ids in sorted(all_areas_by_module.items()):
                discovery_parts.append(f"{module_name}({','.join(sorted(area_ids))})")
            
            write_debug(f"Loading all module areas... (discovered: {'; '.join(discovery_parts)})")
            
            # Load current module areas first (for priority)
            if current_module in all_areas_by_module:
                for area_id in all_areas_by_module[current_module]:
                    module_path_manager = ModulePathManager(current_module)
                    area_file = module_path_manager.get_area_path(area_id)
                    if os.path.exists(area_file):
                        area_data = safe_read_json(area_file)
                        if area_data:
                            self.area_data[area_id] = area_data
                            self._process_area_locations(area_id, area_data, area_file)
                            write_debug(f"  [OK] Loaded {area_id}: {area_data.get('areaName', 'Unknown')} [{current_module}]")
                        else:
                            write_debug(f"  [ERROR] Failed to load {area_file}")
                    else:
                        write_debug(f"  [ERROR] File not found: {area_file}")
            
            # Load other module areas
            for module_name, area_ids in sorted(all_areas_by_module.items()):
                if module_name != current_module:
                    for area_id in area_ids:
                        module_path_manager = ModulePathManager(module_name)
                        area_file = module_path_manager.get_area_path(area_id)
                        if os.path.exists(area_file):
                            area_data = safe_read_json(area_file)
                            if area_data:
                                self.area_data[area_id] = area_data
                                self._process_area_locations(area_id, area_data, area_file)
                                write_debug(f"  [OK] Loaded {area_id}: {area_data.get('areaName', 'Unknown')} [{module_name}]")
                            else:
                                write_debug(f"  [ERROR] Failed to load {area_file}")
                        else:
                            write_debug(f"  [ERROR] File not found: {area_file}")
        
        # Process external connections after all locations are loaded
        self._process_external_connections()
        
        write_debug(f"Graph built: {len(self.nodes)} locations, {sum(len(v) for v in self.edges.values())} connections")
        print(f"DEBUG: [LocationGraph.load_module_data] Load complete. Total nodes: {len(self.nodes)}, Total edges: {sum(len(v) for v in self.edges.values())}")
    
    def _process_area_locations(self, area_id: str, area_data: Dict, area_file: str = None):
        """Process all locations in an area and add them to the graph"""
        locations = area_data.get('locations', [])
        
        for location in locations:
            location_id = location.get('locationId')
            location_name = location.get('name')
            
            if not location_name or not location_id:
                continue
                
            # Add node to graph using location_id as key
            self.nodes[location_id] = {
                'area_id': area_id,
                'location_name': location_name,
                'data': location,
                'area_file': area_file  # Track the source file for auto-fixing
            }
            
            # Build ID <-> name mappings
            self.id_to_name[location_id] = location_name
            self.name_to_id[location_name] = location_id
            
            # Add internal connections (within same area)
            internal_connections = location.get('connectivity', [])
            for connected_id in internal_connections:
                # connected_id should be a location ID like "B02"
                self.edges[location_id].append(connected_id)
    
    def _process_external_connections(self):
        """Process external connections between areas after all locations are loaded"""
        for location_id, node_info in self.nodes.items():
            location_data = node_info['data']
            area_connectivity = location_data.get('areaConnectivity', [])
            area_connectivity_ids = location_data.get('areaConnectivityId', [])
            
            # Process areaConnectivity (location names)
            fixed_connectivity = []
            needs_fixing = False
            
            for i, connected_location_name in enumerate(area_connectivity):
                # Auto-fix dict objects in areaConnectivity
                if isinstance(connected_location_name, dict):
                    print(f"WARNING: Dict found in areaConnectivity for location {location_id} in {node_info.get('area_file', 'Unknown')}")
                    print(f"         Auto-fixing by extracting area name...")
                    
                    # Try to extract a useful name from the dict
                    # Look for 'name', 'areaName', 'description' fields
                    area_name = None
                    if 'name' in connected_location_name:
                        area_name = connected_location_name['name']
                    elif 'areaName' in connected_location_name:
                        area_name = connected_location_name['areaName']
                    elif 'description' in connected_location_name:
                        # Extract area name from description if possible
                        desc = connected_location_name['description']
                        if 'toward the' in desc:
                            # e.g., "toward the Goblin Warren Depths"
                            area_name = desc.split('toward the')[1].split(',')[0].strip()
                        elif 'to the' in desc:
                            area_name = desc.split('to the')[1].split(',')[0].strip()
                    
                    # If we found a name, use it; otherwise try to construct from areaId
                    if not area_name and 'areaId' in connected_location_name:
                        # Try to find the area name from the areaId
                        area_id = connected_location_name['areaId']
                        for aid, adata in self.area_data.items():
                            if aid == area_id:
                                area_name = adata.get('areaName', f"Area {area_id}")
                                break
                    
                    if area_name:
                        fixed_connectivity.append(area_name)
                        connected_location_name = area_name
                        needs_fixing = True
                        print(f"         Extracted area name: {area_name}")
                    else:
                        print(f"         Could not extract area name, skipping entry")
                        continue
                else:
                    fixed_connectivity.append(connected_location_name)
                
                if connected_location_name in self.name_to_id:
                    connected_location_id = self.name_to_id[connected_location_name]
                    # Add bidirectional connection using IDs
                    if connected_location_id not in self.edges[location_id]:
                        self.edges[location_id].append(connected_location_id)
                    if location_id not in self.edges[connected_location_id]:
                        self.edges[connected_location_id].append(location_id)
            
            # If we fixed any dict objects, update the file
            if needs_fixing and node_info.get('area_file'):
                try:
                    print(f"         Updating file {node_info['area_file']} with fixed areaConnectivity...")
                    
                    # Update the location data in memory
                    location_data['areaConnectivity'] = fixed_connectivity

                    # This reader has a legacy self-healing write path. T088
                    # consumes the same area file, so publish only a fresh
                    # field-level merge while holding the outer module-tree
                    # fence. Replacing the stale graph snapshot here could
                    # otherwise undo a completed NPC reconciliation.
                    with module_refresh_lock() as refresh_acquired:
                        if not refresh_acquired:
                            print(
                                "         Module refresh is busy; skipped "
                                "persisting the connectivity repair."
                            )
                        else:
                            area_json = safe_read_json(node_info['area_file'])
                            if not isinstance(area_json, dict):
                                raise ValueError("area file is not a JSON object")

                            target_found = False
                            for loc in area_json.get('locations', []):
                                if loc.get('locationId') == location_id:
                                    loc['areaConnectivity'] = fixed_connectivity
                                    target_found = True
                                    break
                            if not target_found:
                                raise ValueError(
                                    f"location {location_id} is no longer in the area"
                                )

                            if not safe_write_json(
                                node_info['area_file'],
                                area_json,
                                create_backup=False,
                            ):
                                raise OSError("failed to write repaired area file")

                            # Preserve the legacy behavior for an existing
                            # module backup, under the same refresh boundary.
                            backup_file = node_info['area_file'].replace(
                                '.json', '_BU.json'
                            )
                            if os.path.exists(backup_file) and not safe_write_json(
                                backup_file,
                                area_json,
                                create_backup=False,
                            ):
                                raise OSError("failed to write repaired area backup")

                            print(f"         File updated successfully!")
                    
                except Exception as e:
                    print(f"         Error updating file: {e}")
            
            # Process areaConnectivityId (now containing direct location IDs)
            for connected_location_id in area_connectivity_ids:
                if connected_location_id in self.nodes:
                    # Add bidirectional connection using IDs
                    if connected_location_id not in self.edges[location_id]:
                        self.edges[location_id].append(connected_location_id)
                    if location_id not in self.edges[connected_location_id]:
                        self.edges[connected_location_id].append(location_id)
    
    def _find_location_by_id(self, area_id: str, location_id: str) -> Optional[Dict]:
        """Find a location by its ID within a specific area"""
        area_data = self.area_data.get(area_id)
        if not area_data:
            return None
            
        for location in area_data.get('locations', []):
            if location.get('locationId') == location_id:
                return location
        return None
    
    def find_path(self, from_location_id: str, to_location_id: str) -> Tuple[bool, List[str], str]:
        """
        Find the shortest path between two locations using BFS
        
        Args:
            from_location_id: Starting location ID (e.g., "A01")
            to_location_id: Destination location ID (e.g., "C08")
        
        Returns:
            (success, path_of_location_ids, message)
        """
        # Validate input locations
        print(f"DEBUG: [LocationGraph.find_path] Checking path from '{from_location_id}' to '{to_location_id}'")
        print(f"DEBUG: [LocationGraph.find_path] Total nodes in graph: {len(self.nodes)}")
        if from_location_id not in self.nodes:
            print(f"DEBUG: [LocationGraph.find_path] ERROR - '{from_location_id}' not in nodes. First 10 nodes: {list(self.nodes.keys())[:10]}")
            return False, [], f"Starting location ID '{from_location_id}' not found"
        
        if to_location_id not in self.nodes:
            return False, [], f"Destination location ID '{to_location_id}' not found"
        
        if from_location_id == to_location_id:
            return True, [from_location_id], "Already at destination"
        
        # BFS to find shortest path
        queue = deque([(from_location_id, [from_location_id])])
        visited = {from_location_id}
        
        while queue:
            current_location_id, path = queue.popleft()
            
            # Check all connected locations
            for neighbor_id in self.edges[current_location_id]:
                if neighbor_id == to_location_id:
                    # Found the destination
                    final_path = path + [neighbor_id]
                    return True, final_path, f"Path found with {len(final_path)} steps"
                
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, path + [neighbor_id]))
        
        return False, [], f"No path exists between '{from_location_id}' and '{to_location_id}'"
    
    def get_location_info(self, location_id: str) -> Optional[Dict]:
        """Get detailed information about a location by ID"""
        return self.nodes.get(location_id)
    
    def get_path_areas(self, path: List[str]) -> List[str]:
        """Get the areas that a path passes through"""
        areas = []
        for location_id in path:
            location_info = self.get_location_info(location_id)
            if location_info:
                area_id = location_info['area_id']
                area_name = self.area_data[area_id].get('areaName', area_id)
                if area_name not in areas:
                    areas.append(area_name)
        return areas
    
    def get_location_name(self, location_id: str) -> str:
        """Get location name from location ID"""
        return self.id_to_name.get(location_id, f"Unknown location ({location_id})")
    
    def get_location_id(self, location_name: str) -> Optional[str]:
        """Get location ID from location name"""
        return self.name_to_id.get(location_name)
    
    def get_area_id_from_location_id(self, location_id: str) -> Optional[str]:
        """
        Get the area ID from a location ID using the loaded module data.
        
        Args:
            location_id (str): Location ID like "A01", "B05", "C03", etc.
        
        Returns:
            str: Area ID like "HH001", "G001", "SK001", etc.
            None: If location ID not found in any area
        """
        location_info = self.get_location_info(location_id)
        if location_info:
            return location_info['area_id']
        return None
    
    def is_cross_area_transition(self, from_location_id: str, to_location_id: str) -> Optional[bool]:
        """
        Determine if a transition between two location IDs crosses area boundaries.
        
        Args:
            from_location_id (str): Starting location ID
            to_location_id (str): Destination location ID
        
        Returns:
            bool: True if transition crosses areas, False if within same area
            None: If either location ID is invalid
        """
        from_area = self.get_area_id_from_location_id(from_location_id)
        to_area = self.get_area_id_from_location_id(to_location_id)
        
        if from_area is None or to_area is None:
            return None
        
        return from_area != to_area
    
    def validate_location_id_format(self, location_id: str) -> bool:
        """
        Validate that a location ID exists in the loaded module data.
        
        Args:
            location_id (str): Location ID to validate
        
        Returns:
            bool: True if location exists in module, False otherwise
        """
        return location_id in self.nodes
    
    def get_area_name_from_location_id(self, location_id: str) -> str:
        """
        Get the area name from a location ID (for debugging/logging).
        
        Args:
            location_id (str): Location ID like "A01", "B05", etc.
        
        Returns:
            str: Area name or "Unknown Area" if not found
        """
        area_id = self.get_area_id_from_location_id(location_id)
        if area_id and area_id in self.area_data:
            return self.area_data[area_id].get('areaName', 'Unknown Area')
        return 'Unknown Area'
    
    def get_entry_location_for_area(self, area_id: str) -> Optional[str]:
        """
        Find the entry location ID for a given area ID by looking for locations 
        with areaConnectivity or using the first location in the area.
        
        Args:
            area_id (str): Area ID like "TW001", "RO001", etc.
        
        Returns:
            str: Entry location ID like "TW01", "RO01", etc. or None if area not found
        """
        if area_id not in self.area_data:
            return None
        
        area_data = self.area_data[area_id]
        locations = area_data.get('locations', [])
        
        if not locations:
            return None
        
        # First, look for locations with areaConnectivity (external connections)
        for location in locations:
            if location.get('areaConnectivity') or location.get('areaConnectivityId'):
                return location.get('locationId')
        
        # Fallback: return the first location in the area
        return locations[0].get('locationId')


def format_path_result(success: bool, path: List[str], message: str, graph: LocationGraph) -> str:
    """Format the path finding result for display"""
    result = []
    result.append("=" * 60)
    result.append("LOCATION PATH FINDER RESULT")
    result.append("=" * 60)
    
    if success and path:
        result.append(f"[SUCCESS]: {message}")
        result.append("")
        result.append("Path Details:")
        
        areas_traversed = graph.get_path_areas(path)
        result.append(f"  Areas traversed: {' -> '.join(areas_traversed)}")
        result.append(f"  Total steps: {len(path)}")
        result.append("")
        
        result.append("Step-by-step path:")
        for i, location_id in enumerate(path):
            location_info = graph.get_location_info(location_id)
            location_name = graph.get_location_name(location_id)
            area_name = graph.area_data[location_info['area_id']].get('areaName', 'Unknown')
            
            step_marker = "START" if i == 0 else f"Step {i}"
            if i == len(path) - 1:
                step_marker = "DEST"
                
            result.append(f"  {step_marker:>5}: {location_name} [{area_name}:{location_id}]")
    else:
        result.append(f"[FAILURE]: {message}")
    
    result.append("=" * 60)
    return "\n".join(result)


def show_available_locations(graph: LocationGraph):
    """Show all available locations by area for debugging"""
    print("\n" + "=" * 60)
    print("AVAILABLE LOCATIONS BY AREA")
    print("=" * 60)
    
    by_area = defaultdict(list)
    for location_id, info in graph.nodes.items():
        area_name = graph.area_data[info['area_id']].get('areaName', info['area_id'])
        location_name = info['location_name']
        by_area[area_name].append((location_id, location_name))
    
    for area_name in sorted(by_area.keys()):
        print(f"\n{area_name}:")
        for location_id, location_name in sorted(by_area[area_name]):
            print(f"  - {location_id}: {location_name}")

def run_tests(graph: LocationGraph):
    """Run a series of test cases to validate the path finder"""
    print("\n" + "=" * 60)
    print("RUNNING PATH FINDER TESTS")
    print("=" * 60)
    
    # Test cases: (from_id, to_id, should_succeed)
    test_cases = [
        # Valid paths within same area
        ("A01", "A02", True),  # General Store to Town Square
        ("B01", "B02", True),  # Witchlight Trailhead to Abandoned Ranger Outpost
        ("C01", "C03", True),  # Outer Courtyard to The Ruined Chapel
        
        # Valid paths across areas
        ("A01", "B02", True),  # General Store to Abandoned Ranger Outpost
        ("A02", "C08", True),  # Town Square to Secret Passage
        ("A05", "C07", True),  # Wyrd Lantern Inn to Lord's Study
        ("B01", "D05", True),  # Witchlight Trailhead to Ancient Standing Stones
        
        # Cross-area long paths
        ("A03", "D06", True),  # East Gate to The Cursed Barrow
        ("A04", "C06", True),  # Militia Barracks to Broken Tower
        
        # Invalid paths (should fail)
        ("XXX", "A01", False),  # Non-existent location ID
        ("A01", "YYY", False),  # Non-existent destination ID
        
        # Edge cases
        ("A01", "A01", True),  # Same location
    ]
    
    passed = 0
    failed = 0
    
    for i, (from_id, to_id, should_succeed) in enumerate(test_cases, 1):
        from_name = graph.get_location_name(from_id)
        to_name = graph.get_location_name(to_id)
        print(f"\nTest {i}: {from_id} ({from_name}) -> {to_id} ({to_name})")
        success, path, message = graph.find_path(from_id, to_id)
        
        if success == should_succeed:
            print(f"  [PASS]: Expected {should_succeed}, got {success}")
            if success and len(path) > 1:
                areas = graph.get_path_areas(path)
                print(f"    Path: {' -> '.join(path[:3])}{'...' if len(path) > 3 else ''} ({len(path)} steps)")
                print(f"    Areas: {' -> '.join(areas)}")
            passed += 1
        else:
            print(f"  [FAIL]: Expected {should_succeed}, got {success}")
            print(f"    Message: {message}")
            failed += 1
    
    print(f"\n" + "=" * 60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)


def main():
    """Main function for command line usage"""
    # Initialize the graph and load module data
    graph = LocationGraph()
    graph.load_module_data()
    
    # If command line arguments provided, find specific path
    if len(sys.argv) == 3:
        from_input = sys.argv[1]
        to_input = sys.argv[2]
        
        # Try to convert input to location IDs (handle both names and IDs)
        from_id = from_input if from_input in graph.nodes else graph.get_location_id(from_input)
        to_id = to_input if to_input in graph.nodes else graph.get_location_id(to_input)
        
        if from_id is None:
            print(f"Error: Could not find location '{from_input}' (tried as both ID and name)")
            return 1
        
        if to_id is None:
            print(f"Error: Could not find location '{to_input}' (tried as both ID and name)")
            return 1
        
        from_name = graph.get_location_name(from_id)
        to_name = graph.get_location_name(to_id)
        
        print(f"\nFinding path from '{from_id}' ({from_name}) to '{to_id}' ({to_name})...")
        success, path, message = graph.find_path(from_id, to_id)
        
        result = format_path_result(success, path, message, graph)
        print(result)
        
        return 0 if success else 1
    
    # If no arguments, run interactive mode or tests
    elif len(sys.argv) == 1:
        print("\nNo arguments provided. Showing available locations and running test suite...")
        show_available_locations(graph)
        run_tests(graph)
        
        print("\nFor specific path finding, use:")
        print("  python location_path_finder.py \"<from_location_id_or_name>\" \"<to_location_id_or_name>\"")
        print("\nExamples:")
        print("  python location_path_finder.py \"A01\" \"C08\"")
        print("  python location_path_finder.py \"Harrow's Hollow General Store\" \"Secret Passage\"")
        
        return 0
    
    else:
        print("Usage: python location_path_finder.py [from_location] [to_location]")
        print("  Accepts either location IDs (e.g., A01, C08) or location names")
        print("  If no arguments provided, runs test suite")
        return 1


if __name__ == "__main__":
    sys.exit(main())
