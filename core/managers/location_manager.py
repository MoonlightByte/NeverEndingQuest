# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# LOCATION_MANAGER.PY - GAME SYSTEMS LAYER - EXPLORATION
# ============================================================================
# 
# ARCHITECTURE ROLE: Game Systems Layer - Location and Movement Management
# 
# This module manages 5e exploration mechanics including location transitions,
# area connectivity, and spatial relationships. It implements our hierarchical
# module organization with ID-based location management.
# 
# KEY RESPONSIBILITIES:
# - Manage location data loading and caching
# - Handle area-to-area and location-to-location transitions
# - Validate movement requests against connectivity rules
# - Coordinate with path finding system for movement validation
# - Maintain location state and discovery tracking
# 
# LOCATION HIERARCHY:
# Module -> Areas (HH001, G001) -> Locations (A01, B02) -> Local Features
# 
# ID CONVENTION:
# - Area IDs: 3-letter prefix + 3-digit number (HH001, G001, TBM001)
# - Location IDs: Letter + 2-digit number (A01, B02, C15)
# - Encounter IDs: Location-Encounter format (B02-E1)
# 
# CONNECTIVITY SYSTEM:
# - Within-area connectivity through location connections
# - Cross-area connectivity through special transition locations
# - Graph-based pathfinding for movement validation
# - Support for hidden passages and conditional connections
# 
# ARCHITECTURAL INTEGRATION:
# - Called by action_handler.py for location transitions
# - Uses ModulePathManager for area file loading
# - Integrates with party_tracker.json for current location state
# - Coordinates with location_path_finder.py for validation
# 
# DESIGN PATTERNS:
# - Facade Pattern: Simplifies complex location operations
# - Flyweight Pattern: Efficient location data caching
# - Observer Pattern: Location change notifications
# 
# This module demonstrates our approach to complex spatial relationships
# while maintaining performance and data consistency.
# ============================================================================

import json
import subprocess
import os
import sys
import unicodedata
import re
import traceback
from datetime import datetime
from utils.module_path_manager import ModulePathManager
import core.ai.cumulative_summary as cumulative_summary
import utils.reconcile_location_state as reconcile_location_state
from utils.encoding_utils import (
    sanitize_text,
    sanitize_dict,
    safe_json_load,
    safe_json_dump,
    fix_corrupted_location_name
)
from utils.enhanced_logger import debug, info, warning, error, game_event, set_script_name

# Set script name for logging
set_script_name(__name__)

def get_storage_at_location(location_id):
    """Get all player storage containers at a specific location"""
    try:
        from core.managers.storage_manager import get_storage_manager
        manager = get_storage_manager()
        return manager.get_storage_at_location(location_id)
    except Exception as e:
        debug(f"FILE_OP: Could not load storage at location {location_id}", category="storage_operations")
        return []

def format_storage_description(storage_containers):
    """Format storage containers for location description"""
    if not storage_containers:
        return ""
    
    descriptions = []
    for storage in storage_containers:
        name = storage.get("deviceName", "Storage Container")
        storage_type = storage.get("deviceType", "container")
        contents_count = len(storage.get("contents", []))
        
        if contents_count > 0:
            descriptions.append(f"A {storage_type} named '{name}' containing {contents_count} item{'s' if contents_count != 1 else ''}")
        else:
            descriptions.append(f"An empty {storage_type} named '{name}'")
    
    if descriptions:
        return f"\n\nPLAYER STORAGE: {'; '.join(descriptions)}."
    
    return ""

def load_json_file(file_path):
    """Load a JSON file, with error handling"""
    try:
        if file_path.endswith('.txt'):
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        else:
            # Use safe_json_load for JSON files
            return safe_json_load(file_path)
    except FileNotFoundError:
        # This message is misleading - we're not creating the file, just noting it doesn't exist
        debug(f"FILE_OP: File {file_path} not found", category="file_operations")
        return None
    except json.JSONDecodeError:
        error(f"FILE_OP: Invalid JSON in {file_path}", category="file_operations")
        return None
    except UnicodeDecodeError:
        error(f"FILE_OP: Unable to decode {file_path} using UTF-8 encoding", category="file_operations")
        return None

def normalize_string(s):
    """Simple string normalization for fallback comparison"""
    if not s:
        return ""
    # First sanitize the text to fix encoding issues
    s = sanitize_text(s)
    s = unicodedata.normalize('NFC', s)
    s = s.lower().strip()
    return s

def get_location_info(location_name, current_area, current_area_id):
    """Get location information based on ID first, then name"""
    # Get current module from party tracker for consistent path resolution
    try:
        party_tracker = load_json_file("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    area_file = path_manager.get_area_path(current_area_id)
    area_data = load_json_file(area_file)
    if area_data and "locations" in area_data:
        # First try to find by locationId (most reliable)
        for location in area_data["locations"]:
            if location["locationId"] == location_name:
                return location
                
        # Then try exact name matching
        for location in area_data["locations"]:
            if location["name"] == location_name:
                return location
    return None

def get_location_data(location_id, area_id):
    """Get location data based on location ID and area ID"""
    # Get current module from party tracker for consistent path resolution
    try:
        party_tracker = load_json_file("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    area_file = path_manager.get_area_path(area_id)
    try:
        with open(area_file, "r", encoding="utf-8") as file:
            area_data = json.load(file)
        for location in area_data["locations"]:
            if location["locationId"] == location_id:
                return location
        warning(f"VALIDATION: Location {location_id} not found in {area_file}", category="location_transitions")
    except FileNotFoundError:
        error(f"FILE_OP: Area file {area_file} not found", category="file_operations")
    except json.JSONDecodeError:
        error(f"FILE_OP: Invalid JSON in {area_file}", category="file_operations")
    return None

def update_world_conditions(current_conditions, new_location, current_area, current_area_id):
    """Update world conditions based on location change"""
    from datetime import datetime, timedelta
    current_time = datetime.strptime(current_conditions["time"], "%H:%M:%S")
    new_time = current_time.strftime("%H:%M:%S")  # Don't automatically add time - let DM handle it

    location_info = get_location_info(new_location, current_area, current_area_id)

    if location_info:
        return {
            "year": current_conditions["year"],
            "month": current_conditions["month"],
            "day": current_conditions["day"],
            "time": new_time,
            "weather": location_info.get("weatherConditions", ""), 
            "season": current_conditions["season"],
            "dayNightCycle": "Day" if 6 <= int(new_time[:2]) < 18 else "Night",
            "moonPhase": current_conditions["moonPhase"],
            "currentLocation": new_location,
            "currentLocationId": location_info["locationId"],
            "currentArea": current_area,
            "currentAreaId": current_area_id,
            "majorEventsUnderway": current_conditions["majorEventsUnderway"],
            "politicalClimate": "",
            "activeEncounter": "",
            "activeCombatEncounter": current_conditions.get("activeCombatEncounter", "")
        }
    else:
        return current_conditions

def handle_location_transition(current_location, new_location, current_area, current_area_id, area_connectivity_id=None):
    """Handle transition between locations, prioritizing ID matching"""
    info(f"STATE_CHANGE: Location transition from '{current_location}' to '{new_location}'", category="location_transitions")
    debug(f"STATE_CHANGE: Current area: '{current_area}', Current area ID: '{current_area_id}'", category="location_transitions")

    party_tracker = load_json_file("party_tracker.json")
    if party_tracker:
        # Get current module from party tracker for consistent path resolution
        current_module = party_tracker.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(current_module)
        current_area_file = path_manager.get_area_path(current_area_id)
        current_area_data = load_json_file(current_area_file)
        current_location_id_from_tracker = str(party_tracker.get("worldConditions", {}).get("currentLocationId", "") or "").strip()
        current_location_normalized = str(current_location or "").strip()
        current_location_room_prefix_stripped = re.sub(r"^Room\s+\d+\s*:\s*", "", current_location_normalized, flags=re.IGNORECASE).strip()

        if current_area_data and "locations" in current_area_data:
            # Find current location info 
            current_location_info = None
            for loc in current_area_data["locations"]:
                source_room_title = str(loc.get("source_room_title", "") or "").strip()
                location_name = str(loc.get("name", "") or "").strip()
                location_id = str(loc.get("locationId", "") or "").strip()
                if (
                    location_name == current_location
                    or location_id == current_location
                    or (current_location_id_from_tracker and location_id == current_location_id_from_tracker)
                    or (source_room_title and source_room_title == current_location_normalized)
                    or (current_location_room_prefix_stripped and location_name == current_location_room_prefix_stripped)
                ):
                    current_location_info = loc
                    break
                    
            if current_location_info:
                debug(f"VALIDATION: Current location identified: {current_location_info['name']} (ID: {current_location_info['locationId']})", category="location_transitions")
            else:
                error(f"VALIDATION: Current location '{current_location}' not found in area data", category="location_transitions")
                return None
        else:
            error(f"FILE_OP: Failed to load current area data from {current_area_file}", category="file_operations")
            return None

        # The new_location parameter is now always a specific location ID.
        # We just need to find which area it belongs to.
        new_location_info = None
        new_area_data = None
        new_area_id_for_conditions = None

        # Search all loaded areas to find the new location
        from utils.location_path_finder import LocationGraph
        graph = LocationGraph() # Use the graph to access all loaded data
        graph.load_module_data()

        new_location_info = graph.get_location_info(new_location)

        if new_location_info:
            new_area_id_for_conditions = new_location_info['area_id']
            new_area_data = graph.area_data.get(new_area_id_for_conditions)
            debug(f"VALIDATION: Found new location '{new_location_info['location_name']}' in area {new_area_id_for_conditions}", category="location_transitions")
            debug(f"SUCCESS: New location validated: {new_location_info['location_name']} (ID: {new_location})", category="location_transitions")
        else:
            error(f"FAILURE: Could not find new location '{new_location}' by any method", category="location_transitions")
            return None
    else:
        error("FILE_OP: Failed to load party_tracker.json", category="file_operations")
        return None

    if current_location_info:
        # Update current_location.json with current location info
        try:
            safe_json_dump(current_location_info, "current_location.json")
        except Exception as e:
            error(f"FILE_OP: Failed to update current_location.json", exception=e, category="file_operations")

        # =================================================================
        # NEW RECONCILIATION STEP - INSERT THIS BLOCK
        # =================================================================
        try:
            # Load the full conversation history to find the relevant segment
            conversation_history = load_json_file("modules/conversation_history/conversation_history.json") or []
            
            # Find the start of this location's history by looking for the last transition message
            start_index = 0
            for i in range(len(conversation_history) - 1, -1, -1):
                msg = conversation_history[i]
                content = msg.get("content", "")
                if msg.get("role") == "user" and ("Location transition:" in content or "Module transition:" in content):
                    start_index = i + 1
                    break
            
            history_segment = conversation_history[start_index:]

            # Call the new reconciler for the location we are LEAVING
            reconcile_location_state.run(
                area_id=current_area_id, 
                location_id=current_location_info['locationId'],
                conversation_history_segment=history_segment
            )
            info(f"STATE_RECONCILIATION: Ran reconciler for {current_location_info['name']} ({current_location_info['locationId']}).")

        except Exception as e:
            error(f"FAILURE: Location State Reconciliation failed for {current_location_info['name']}", exception=e)
        # =================================================================
        # END OF NEW STEP
        # =================================================================

        # Run adventure summary update
        try:
            # Get the path to adv_summary.py relative to the project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            adv_summary_path = os.path.join(project_root, "core", "ai", "adv_summary.py")
            
            result = subprocess.run([sys.executable, adv_summary_path, "modules/conversation_history/conversation_history.json", "current_location.json", current_location, current_area_id],
                        check=True, capture_output=True, text=True)
            info("SUCCESS: Adventure summary updated successfully", category="summary_building")
        except subprocess.CalledProcessError as e:
            error(f"FAILURE: Failed to run adv_summary.py", exception=e, category="summary_building")
            debug(f"SUBPROCESS: stdout: {e.stdout}", category="subprocess_output")
            debug(f"SUBPROCESS: stderr: {e.stderr}", category="subprocess_output")

        # Log the transition for debugging
        debug_log_file = "transition_debug.log"
        try:
            with open(debug_log_file, "a", encoding="utf-8") as debug_file:
                debug_file.write(f"\n--- TRANSITION DEBUG: {current_location} to {new_location} ---\n")
                debug_file.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                debug_file.write(f"Area ID: {current_area_id}\n")
                debug_file.write(f"Adventure summary has been generated\n")
        except Exception as e:
            error(f"FILE_OP: Failed to write to debug log", exception=e, category="file_operations")

        # Update party tracker with new location information
        if party_tracker and new_location_info:
            # Use the new area data if we're transitioning to a different area
            area_for_conditions = new_area_data if new_area_data else current_area_data
            area_id_for_conditions = new_area_id_for_conditions if new_area_id_for_conditions else current_area_id
            
            party_tracker["worldConditions"] = update_world_conditions(
                party_tracker["worldConditions"],
                new_location_info.get("location_name", new_location_info.get("name", "Unknown Location")),
                area_for_conditions.get("areaName", current_area if not area_connectivity_id else "Unknown Area"),
                area_id_for_conditions
            )
            
            # Explicitly set these values to ensure they're correct
            # Sanitize the location name before saving
            party_tracker["worldConditions"]["currentLocation"] = sanitize_text(new_location_info.get("location_name", new_location_info.get("name", "Unknown Location")))
            party_tracker["worldConditions"]["currentLocationId"] = new_location

            if new_area_id_for_conditions != current_area_id and new_area_data:
                # We're transitioning to a new area
                party_tracker["worldConditions"]["currentArea"] = new_area_data.get("areaName", "Unknown Area")
                party_tracker["worldConditions"]["currentAreaId"] = new_area_id_for_conditions

            try:
                safe_json_dump(party_tracker, "party_tracker.json")
                info("SUCCESS: Updated party_tracker.json with new location", category="file_operations")
                
                # Log successful location transition as a game event
                game_event("location_transition", {
                    "from": current_location,
                    "to": new_location_info.get("location_name", new_location_info.get("name", "Unknown Location")),
                    "from_id": current_location_info.get("locationId", current_location) if current_location_info else current_location,
                    "to_id": new_location,
                    "area_change": new_area_id_for_conditions != current_area_id
                })
            except Exception as e:
                error(f"FAILURE: Failed to update party_tracker.json", exception=e, category="file_operations")

        # Get storage information for the new location
        storage_containers = get_storage_at_location(new_location)
        storage_description = format_storage_description(storage_containers)
        
        base_prompt = f"Describe the immediate surroundings and any notable features or encounters in {new_location_info.get('location_name', new_location_info.get('name', 'this location'))}, based on its recent history and current state."
        
        return base_prompt + storage_description
    else:
        error(f"FAILURE: Could not find information for current location: {current_location}", category="location_transitions")
        return None
