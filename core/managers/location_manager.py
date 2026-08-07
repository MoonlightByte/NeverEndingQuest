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
import copy
import subprocess
import os
import sys
import tempfile
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


_TRANSITION_NARRATION_FIELDS = (
    "type",
    "description",
    "features",
    "npcs",
    "monsters",
    "encounters",
    "adventureSummary",
    "dmInstructions",
    "doors",
    "traps",
    "accessibility",
    "dangerLevel",
    "weatherConditions",
)


def _build_transition_narration_prompt(
    new_location_info,
    *,
    area_id,
    area_name,
    storage_description="",
):
    """Build a destination-grounded T013 prompt from verified location data."""
    location_data = new_location_info.get("data")
    if not isinstance(location_data, dict):
        location_data = new_location_info

    facts = {
        "locationId": location_data.get("locationId"),
        "name": new_location_info.get("location_name")
        or location_data.get("name")
        or "Unknown Location",
        "areaId": area_id,
        "areaName": area_name,
    }
    for field in _TRANSITION_NARRATION_FIELDS:
        value = location_data.get(field)
        if value not in (None, "", [], {}):
            facts[field] = value

    return (
        "Narrate the party's immediate arrival at the destination. Use only "
        "the supplied destination facts; do not invent technology, named "
        "characters, creatures, hazards, history, or changes to game state. "
        "Do not resolve or trigger an encounter. If the supplied facts are "
        "sparse, keep the narration brief rather than filling gaps. Respect "
        "the adventureSummary as the authoritative record of what has already "
        "happened.\n\nDESTINATION FACTS:\n"
        + json.dumps(facts, ensure_ascii=False, sort_keys=True)
        + storage_description
    )

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

def update_world_conditions(
    current_conditions,
    new_location,
    current_area,
    current_area_id,
    location_info_override=None,
):
    """Update world conditions based on location change"""
    from datetime import datetime, timedelta
    current_time = datetime.strptime(current_conditions["time"], "%H:%M:%S")
    new_time = current_time.strftime("%H:%M:%S")  # Don't automatically add time - let DM handle it

    location_info = location_info_override or get_location_info(
        new_location, current_area, current_area_id
    )

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


def _run_departure_summary(
    current_location, current_area_id, origin_party_tracker=None
):
    """Run the optional departure summary and return an explicit status."""
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    adv_summary_path = os.path.join(project_root, "core", "ai", "adv_summary.py")
    tracker_snapshot_path = None
    try:
        if isinstance(origin_party_tracker, dict):
            snapshot_file = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".json",
                prefix="neq_departure_party_",
                delete=False,
            )
            tracker_snapshot_path = snapshot_file.name
            with snapshot_file:
                json.dump(origin_party_tracker, snapshot_file, ensure_ascii=False)
            try:
                os.chmod(tracker_snapshot_path, 0o600)
            except OSError:
                pass

        command = [
            sys.executable,
            adv_summary_path,
            "modules/conversation_history/conversation_history.json",
            "current_location.json",
            current_location,
            current_area_id,
        ]
        if tracker_snapshot_path:
            command.append(tracker_snapshot_path)
    except Exception as exc:
        if tracker_snapshot_path:
            try:
                os.remove(tracker_snapshot_path)
            except OSError:
                pass
        return {"success": False, "status": "unavailable", "error": str(exc)}
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        error(
            "FAILURE: Departure summary was unavailable; travel will continue",
            exception=exc,
            category="summary_building",
        )
        debug(f"SUBPROCESS: stdout: {exc.stdout}", category="subprocess_output")
        debug(f"SUBPROCESS: stderr: {exc.stderr}", category="subprocess_output")
        return {
            "success": False,
            "status": "unavailable",
            "returncode": exc.returncode,
        }
    except Exception as exc:
        error(
            "FAILURE: Could not launch departure summary; travel will continue",
            exception=exc,
            category="summary_building",
        )
        return {
            "success": False,
            "status": "unavailable",
            "error": str(exc),
        }

    else:
        info("SUCCESS: Adventure summary transaction committed", category="summary_building")
        return {
            "success": True,
            "status": "committed",
            "stdout": result.stdout,
        }
    finally:
        if tracker_snapshot_path:
            try:
                os.remove(tracker_snapshot_path)
            except OSError:
                pass

def handle_location_transition(
    current_location,
    new_location,
    current_area,
    current_area_id,
    area_connectivity_id=None,
    authorized_destination=None,
):
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

        if current_area_data and "locations" in current_area_data:
            # Find current location info 
            current_location_info = None
            for loc in current_area_data["locations"]:
                if loc["name"] == current_location or loc["locationId"] == current_location:
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

        if authorized_destination is not None:
            if not isinstance(authorized_destination, dict):
                error(
                    "VALIDATION: Authorized destination metadata is invalid",
                    category="location_transitions",
                )
                return None
            authorized_module = authorized_destination.get("module_name")
            authorized_location_id = authorized_destination.get("location_id")
            authorized_area_id = authorized_destination.get("area_id")
            authorized_location_data = authorized_destination.get("location_data")
            if (
                authorized_module != current_module
                or authorized_location_id != new_location
                or not isinstance(authorized_area_id, str)
                or not authorized_area_id
                or not isinstance(authorized_location_data, dict)
                or authorized_location_data.get("locationId") != new_location
            ):
                error(
                    "VALIDATION: Authorized destination does not match active module movement",
                    category="location_transitions",
                )
                return None
            new_area_id_for_conditions = authorized_area_id
            new_area_data = {
                "areaId": authorized_area_id,
                "areaName": authorized_destination.get("area_name", "Unknown Area"),
            }
            new_location_info = {
                "area_id": authorized_area_id,
                "location_name": authorized_destination.get(
                    "location_name", authorized_location_data.get("name", "Unknown Location")
                ),
                "data": authorized_location_data,
            }
        else:
            # Compatibility path for legacy callers that have no request-bound
            # authorization. Approved within-module travel never enters it.
            from utils.location_path_finder import LocationGraph

            graph = LocationGraph()
            graph.load_module_data()
            new_location_info = graph.get_location_info(new_location)
            if new_location_info:
                new_area_id_for_conditions = new_location_info['area_id']
                new_area_data = graph.area_data.get(new_area_id_for_conditions)

        if new_location_info:
            debug(f"VALIDATION: Found new location '{new_location_info['location_name']}' in area {new_area_id_for_conditions}", category="location_transitions")
            debug(f"SUCCESS: New location validated: {new_location_info['location_name']} (ID: {new_location})", category="location_transitions")
        else:
            error(f"FAILURE: Could not find new location '{new_location}' by any method", category="location_transitions")
            return None
    else:
        error("FILE_OP: Failed to load party_tracker.json", category="file_operations")
        return None

    if current_location_info:
        # Capture origin inputs before movement. Optional departure work runs
        # only after the authoritative commit, but must describe the state and
        # conversation segment from the location being left.
        origin_party_tracker = copy.deepcopy(party_tracker)
        origin_history = load_json_file(
            "modules/conversation_history/conversation_history.json"
        )
        if not isinstance(origin_history, list):
            origin_history = []
        start_index = 0
        for i in range(len(origin_history) - 1, -1, -1):
            msg = origin_history[i]
            content = msg.get("content", "") if isinstance(msg, dict) else ""
            if isinstance(msg, dict) and msg.get("role") == "user" and (
                "Location transition:" in content or "Module transition:" in content
            ):
                start_index = i + 1
                break
        origin_history_segment = copy.deepcopy(origin_history[start_index:])

        # Commit party movement before any irreversible departure-side write.
        area_for_conditions = new_area_data if new_area_data else current_area_data
        area_id_for_conditions = (
            new_area_id_for_conditions
            if new_area_id_for_conditions
            else current_area_id
        )
        world_condition_args = (
            party_tracker["worldConditions"],
            new_location_info.get(
                "location_name", new_location_info.get("name", "Unknown Location")
            ),
            area_for_conditions.get(
                "areaName",
                current_area if not area_connectivity_id else "Unknown Area",
            ),
            area_id_for_conditions,
        )
        if isinstance(authorized_destination, dict):
            party_tracker["worldConditions"] = update_world_conditions(
                *world_condition_args,
                location_info_override=authorized_destination.get("location_data"),
            )
        else:
            party_tracker["worldConditions"] = update_world_conditions(
                *world_condition_args
            )
        party_tracker["worldConditions"]["currentLocation"] = sanitize_text(
            new_location_info.get(
                "location_name", new_location_info.get("name", "Unknown Location")
            )
        )
        party_tracker["worldConditions"]["currentLocationId"] = new_location
        if new_area_id_for_conditions != current_area_id and new_area_data:
            party_tracker["worldConditions"]["currentArea"] = new_area_data.get(
                "areaName", "Unknown Area"
            )
            party_tracker["worldConditions"]["currentAreaId"] = (
                new_area_id_for_conditions
            )
        try:
            safe_json_dump(party_tracker, "party_tracker.json")
            info(
                "SUCCESS: Updated party_tracker.json with new location",
                category="file_operations",
            )
        except Exception as e:
            error(
                "FAILURE: Failed to update party_tracker.json",
                exception=e,
                category="file_operations",
            )
            raise

        # Everything below is optional post-commit departure processing.
        try:
            safe_json_dump(current_location_info, "current_location.json")
        except Exception as e:
            error(
                "FILE_OP: Failed to update current_location.json",
                exception=e,
                category="file_operations",
            )
        try:
            reconcile_location_state.run(
                area_id=current_area_id,
                location_id=current_location_info["locationId"],
                conversation_history_segment=origin_history_segment,
            )
            info(
                f"STATE_RECONCILIATION: Ran reconciler for {current_location_info['name']} ({current_location_info['locationId']})."
            )
        except Exception as e:
            error(
                f"FAILURE: Location State Reconciliation failed for {current_location_info['name']}",
                exception=e,
            )
        try:
            summary_result = _run_departure_summary(
                current_location,
                current_area_id,
                origin_party_tracker=origin_party_tracker,
            )
        except Exception as e:
            error(
                "FAILURE: Departure summary raised after committed travel",
                exception=e,
                category="summary_building",
            )
            summary_result = {"status": "unavailable", "error": str(e)}

        try:
            with open("transition_debug.log", "a", encoding="utf-8") as debug_file:
                debug_file.write(
                    f"\n--- TRANSITION DEBUG: {current_location} to {new_location} ---\n"
                )
                debug_file.write(
                    f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                debug_file.write(f"Area ID: {current_area_id}\n")
                debug_file.write(
                    f"Adventure summary status: {summary_result['status']}\n"
                )
        except Exception as e:
            error(
                "FILE_OP: Failed to write to debug log",
                exception=e,
                category="file_operations",
            )
        try:
            game_event(
                "location_transition",
                {
                    "from": current_location,
                    "to": new_location_info.get(
                        "location_name",
                        new_location_info.get("name", "Unknown Location"),
                    ),
                    "from_id": current_location_info.get(
                        "locationId", current_location
                    ),
                    "to_id": new_location,
                    "area_change": new_area_id_for_conditions != current_area_id,
                },
            )
        except Exception as e:
            error(
                "FILE_OP: Failed to log location transition event",
                exception=e,
                category="file_operations",
            )

        storage_containers = get_storage_at_location(new_location)
        storage_description = format_storage_description(storage_containers)
        return _build_transition_narration_prompt(
            new_location_info,
            area_id=new_area_id_for_conditions or current_area_id,
            area_name=(
                new_area_data.get("areaName", "Unknown Area")
                if new_area_data
                else current_area
            ),
            storage_description=storage_description,
        )
    else:
        error(f"FAILURE: Could not find information for current location: {current_location}", category="location_transitions")
        return None
