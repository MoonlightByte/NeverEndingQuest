# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Action Handler
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# ACTION_HANDLER.PY - COMMAND PATTERN IMPLEMENTATION
# ============================================================================
# 
# ARCHITECTURE ROLE: Action Processing Layer in Command Pattern
# 
# This module implements the Command Pattern for the 5e system, encapsulating
# all game interactions as discrete, typed actions with specific parameters.
# It serves as the central dispatcher for all game state modifications.
# 
# KEY RESPONSIBILITIES:
# - Parse and validate action commands from AI responses
# - Route actions to appropriate subsystem handlers
# - Module transition detection and marker insertion
# - Ensure atomic execution of compound operations
# - Maintain consistency across all game state updates
# - Provide standardized error handling for all actions
# 
# SUPPORTED ACTION TYPES:
# - updateCharacterInfo: Character stat and inventory management
# - transitionLocation: Movement and exploration actions
# - createEncounter: Combat encounter initialization
# - updatePlot: Module narrative progression
# - updateWorldTime: Game time advancement
# - And extensible action framework for future features
# 
# ARCHITECTURAL INTEGRATION:
# - Called by main.py as part of AI response processing
# - Coordinates with various managers (combat, location, character)
# - Uses ModulePathManager for file operations
# - Implements our "Data Integrity Above All" principle
# 
# DESIGN PATTERNS:
# - Command Pattern: Actions as first-class objects
# - Strategy Pattern: Different handlers for different action types
# - Template Method: Consistent action processing pipeline
# ============================================================================

import json
import subprocess
import os
import random
from datetime import datetime
from typing import Dict, Any
from openai import OpenAI
import config
from core.managers.location_manager import get_location_data
from utils.module_path_manager import ModulePathManager
from updates.plot_update import update_plot
from utils.encoding_utils import sanitize_text, safe_json_dump, safe_json_load
from utils.file_operations import safe_read_json
from core.managers.status_manager import (
    status_transitioning_location, status_updating_character, status_updating_party,
    status_updating_plot, status_advancing_time, status_processing_levelup
)
from utils.location_path_finder import LocationGraph
from core.ai.conversation_utils import handle_module_conversation_segmentation
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Import token tracking
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass

# Import socketio for web interface progress updates
try:
    from web.web_interface import socketio
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    socketio = None

# Import multi-PC combat manager (plugin-style - only used if MULTIPLAYER_MODE enabled)
try:
    from core.managers.multi_pc_combat import (
        create_combat_manager,
        get_combat_manager,
        is_multi_pc_combat_enabled,
        modify_combat_prompt_for_multi_pc
    )
    MULTI_PC_COMBAT_AVAILABLE = True
except ImportError:
    MULTI_PC_COMBAT_AVAILABLE = False
    def is_multi_pc_combat_enabled(): return False

# Set script name for logging
set_script_name("action_handler")

# Action type constants
ACTION_CREATE_ENCOUNTER = "createEncounter"
ACTION_UPDATE_ENCOUNTER = "updateEncounter"
ACTION_UPDATE_TIME = "updateTime"
ACTION_UPDATE_PLOT = "updatePlot"
ACTION_EXIT_GAME = "exitGame"
ACTION_TRANSITION_LOCATION = "transitionLocation"
ACTION_LEVEL_UP = "levelUp"
ACTION_UPDATE_CHARACTER_INFO = "updateCharacterInfo"
ACTION_UPDATE_PARTY_NPCS = "updatePartyNPCs"
ACTION_CREATE_NEW_MODULE = "createNewModule"
ACTION_ESTABLISH_HUB = "establishHub"
ACTION_STORAGE_INTERACTION = "storageInteraction"
ACTION_UPDATE_PARTY_TRACKER = "updatePartyTracker"
ACTION_MOVE_BACKGROUND_NPC = "moveBackgroundNPC"
ACTION_SAVE_GAME = "saveGame"
ACTION_RESTORE_GAME = "restoreGame"
ACTION_LIST_SAVES = "listSaves"
ACTION_DELETE_SAVE = "deleteSave"
ACTION_REST = "rest"

# Module conversation segmentation has been moved to conversation_utils.py
# to work with the regular conversation update cycle


# Import merge helper from utils for testability
from utils.party_tracker_merge import _merge_party_tracker_updates


def pre_validate_transition(parameters, party_tracker_data, conversation_history, location_graph, path_manager):
    """
    Pre-validate a transitionLocation action using the transition intelligence agent.
    This runs BEFORE the main validator, similar to how validation runs before execution.

    Args:
        parameters: Action parameters dict with newLocation
        party_tracker_data: Current party tracker data
        conversation_history: Current conversation history
        location_graph: LocationGraph instance
        path_manager: ModulePathManager instance

    Returns:
        Tuple (approved: bool, error_message: str)
        - If approved: (True, "")
        - If blocked: (False, "Detailed error message with instructions")
    """
    from utils.path_encounter_analyzer import analyze_path_for_encounters
    from core.ai.transition_atlas_builder import build_transition_atlas
    from core.ai.transition_validator import validate_transition_request
    from utils.file_operations import safe_read_json

    try:
        new_location_id = parameters.get("newLocation", "")
        if not new_location_id:
            # No location specified, let normal validator handle it
            return True, ""

        # Get current location from party tracker
        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
        current_location_name = party_tracker_data["worldConditions"]["currentLocation"]
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
        current_area_name = party_tracker_data["worldConditions"]["currentArea"]

        # Get path from location graph
        success, path, path_message = location_graph.find_path(current_location_id, new_location_id)

        if not success:
            # Path doesn't exist - let normal validation handle it
            return True, ""

        # Analyze path for encounters and blocking
        current_module = party_tracker_data.get("module", "").replace(" ", "_")
        world_conditions = party_tracker_data.get("worldConditions", {})
        path_analysis = analyze_path_for_encounters(path, location_graph, current_module, world_conditions)

        # RETREAT DETECTION: Check if this is a legitimate retreat vs fast-travel exploit
        future_segments = [
            seg for seg in path_analysis['path_segments']
            if seg['location_id'] != current_location_id
        ]

        # Check if ALL future locations are visited (retreat to safety)
        all_visited = all(seg['status'] == 'visited' for seg in future_segments) if future_segments else False

        # Check if ANY future locations have unexplored monsters
        has_unexplored_monsters = any(
            seg['status'] == 'unexplored' and seg['has_monsters']
            for seg in future_segments
        )

        # ALLOW RETREAT: If all future locations are visited, this is a tactical retreat
        if all_visited:
            # Player fleeing through cleared areas - ALLOW even if current location has monsters
            debug(f"RETREAT DETECTED: All future locations visited, allowing tactical retreat", category="transition_validation")
            return True, ""  # Approve immediately, skip agent call

        # Build transition atlas
        transition_atlas = build_transition_atlas(location_graph, current_module, world_conditions)

        # Load plot data
        plot_data = safe_read_json(path_manager.get_plot_path()) or {}

        # Get party level
        party_level = 1
        if party_tracker_data.get("partyMembers"):
            try:
                first_member = party_tracker_data.get("active_character") or party_tracker_data["partyMembers"][0]
                from updates.update_character_info import normalize_character_name
                char_name = normalize_character_name(first_member)
                char_file = path_manager.get_character_path(char_name)
                if os.path.exists(char_file):
                    char_data = safe_read_json(char_file)
                    if char_data:
                        party_level = char_data.get("level", 1)
            except Exception:
                pass

        # Get player request from conversation history
        player_request = ""
        for msg in reversed(conversation_history):
            if msg.get("role") == "user" and not msg.get("content", "").startswith("Error Note:"):
                player_request = msg.get("content", "")
                break

        # Call transition intelligence agent
        print(f"DEBUG: [TRANSITION AGENT] Checking travel: {current_location_id} -> {new_location_id}")
        info(f"TRANSITION AGENT: Validating travel request {current_location_id} -> {new_location_id}", category="transition_validation")

        transition_result = validate_transition_request(
            player_request=player_request,
            current_location_id=current_location_id,
            current_location_name=current_location_name,
            current_area_id=current_area_id,
            current_area_name=current_area_name,
            target_location_id=new_location_id,
            path=path,
            path_analysis=path_analysis,
            transition_atlas=transition_atlas,
            plot_data=plot_data,
            party_level=party_level
        )

        # Log agent decision
        agent_decision = "APPROVED" if transition_result.get("approved", True) else "BLOCKED"
        print(f"[TRANSITION AGENT] Decision: {agent_decision}")
        info(f"TRANSITION AGENT: {agent_decision} - {transition_result.get('reason', 'No reason')}", category="transition_validation")

        # Check if approved
        if not transition_result.get("approved", True):
            # Build error message with explicit instructions
            stop_location = transition_result.get("stop_location", "")
            stop_location_name = transition_result.get("stop_location_name", "Unknown")
            reason = transition_result.get("reason", "Unknown")
            narrative_guidance = transition_result.get("narrative_guidance", "")
            requires_encounter = transition_result.get("requires_encounter", False)

            # Check if stop location is the current location
            if stop_location == current_location_id:
                # Already at the blocking location - don't use transitionLocation
                error_msg = f"[TRAVEL AGENT] Travel Blocked: {reason}\n\n"
                error_msg += f"REQUIRED ACTION: You must revise your response to:\n"
                error_msg += f"1. The party is already at {stop_location} ({stop_location_name})\n"
                error_msg += f"2. DO NOT use transitionLocation (already at this location)\n"
                error_msg += f"3. Narrate that the path forward/backward is blocked by the encounter\n"
                error_msg += f"4. Describe the blocking encounter appearing, set scene, prompt player for action\n"
                error_msg += f"5. Player must resolve this encounter before they can continue traveling\n"
            else:
                # Need to stop at a different location
                error_msg = f"[TRAVEL AGENT] Travel Blocked: {reason}\n\n"
                error_msg += f"REQUIRED ACTION: You must revise your response to:\n"
                error_msg += f"1. Stop the party at {stop_location} ({stop_location_name})\n"
                error_msg += f"2. Use transitionLocation action with newLocation: \"{stop_location}\"\n"
                error_msg += f"3. DO NOT use createEncounter action - let the player arrive and explore first\n"
                error_msg += f"4. Describe the arrival at this location, set the scene, and prompt player for action\n"

            if requires_encounter:
                error_msg += f"\nNOTE: This location has a potential encounter, but wait for player interaction before triggering it.\n"

            error_msg += f"\nNARRATIVE GUIDANCE:\n{narrative_guidance}"

            if transition_result.get("plot_guidance"):
                error_msg += f"\n\nPLOT GUIDANCE: {transition_result['plot_guidance']}"

            return False, error_msg

        # Approved - return success
        return True, ""

    except Exception as e:
        # On error, allow normal validation to proceed
        debug(f"Transition pre-validation error: {e}", category="location_transitions")
        return True, ""


def validate_location_transition(location_graph, current_location_id, destination_location_id):
    """
    Validate that a location transition is possible using the location graph.
    
    Args:
        location_graph (LocationGraph): Initialized location graph
        current_location_id (str): Current location ID (e.g., "E02")
        destination_location_id (str): Destination location ID (e.g., "B01")
    
    Returns:
        tuple: (bool, str, str) - (is_valid, error_message, area_connectivity_id)
    """
    try:
        # Validate destination location exists
        if not location_graph.validate_location_id_format(destination_location_id):
            return False, f"Destination location '{destination_location_id}' does not exist in module", None
        
        # Use pathfinding to validate that a connected path exists
        success, path, path_message = location_graph.find_path(current_location_id, destination_location_id)
        if not success:
            return False, f"No valid path exists between '{current_location_id}' and '{destination_location_id}': {path_message}", None
        
        # Check if this is a cross-area transition
        is_cross_area = location_graph.is_cross_area_transition(current_location_id, destination_location_id)
        if is_cross_area is None:
            return False, f"Invalid location ID format: current='{current_location_id}', destination='{destination_location_id}'", None
        
        # Generate area connectivity ID if needed (for backward compatibility with location_manager)
        area_connectivity_id = None
        if is_cross_area:
            dest_area_id = location_graph.get_area_id_from_location_id(destination_location_id)
            area_connectivity_id = f"{dest_area_id}-{destination_location_id}"
        
        debug("VALIDATION: Location transition validation passed", category="location_transitions")
        debug(f"VALIDATION: Path found: {' -> '.join(path) if path else 'Direct connection'}", category="location_transitions")
        debug(f"VALIDATION: Cross-area transition: {is_cross_area}", category="location_transitions")
        if area_connectivity_id:
            debug(f"VALIDATION: Generated area connectivity ID: {area_connectivity_id}", category="location_transitions")
        
        return True, "", area_connectivity_id
        
    except Exception as e:
        return False, f"Location validation failed with exception: {str(e)}", None

def update_party_npcs(party_tracker_data, operation, npc):
    """Update NPC party members (add or remove)"""
    if operation == "add":
        # Get the correct module from party tracker
        module_name = party_tracker_data.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(module_name)
        
        # Use fuzzy matching to find the NPC file
        from updates.update_character_info import find_character_file_fuzzy
        matched_name = find_character_file_fuzzy(npc['name'])
        
        if matched_name:
            npc_file = path_manager.get_character_path(matched_name)
        else:
            # If no match found, use the original name for potential creation
            npc_file = path_manager.get_character_path(npc['name'])
        
        if not os.path.exists(npc_file):
            # NPC file doesn't exist, so we need to create it
            try:
                # Get party level as default if no level specified
                default_level = ''
                if not npc.get('level'):
                    # Get the first party member's level as default
                    if party_tracker_data.get("partyMembers"):
                        player_name = party_tracker_data.get("active_character") or party_tracker_data["partyMembers"][0]
                        # Normalize name for file access
                        from updates.update_character_info import normalize_character_name
                        player_name_normalized = normalize_character_name(player_name)
                        player_file = path_manager.get_character_path(player_name_normalized)
                        if os.path.exists(player_file):
                            try:
                                from utils.encoding_utils import safe_json_load
                                player_data = safe_json_load(player_file)
                                if player_data and 'level' in player_data:
                                    default_level = str(player_data['level'])
                                    debug(f"STATE_CHANGE: Using party level {default_level} as default for NPC {npc['name']}", category="character_updates")
                            except Exception as e:
                                warning(f"FAILURE: Could not get party level, using default: {e}", category="character_updates")
                
                npc_level = str(npc.get('level', default_level))
                
                # Add this debug line right before the subprocess.run call
                debug(f"SUBPROCESS: Calling npc_builder.py with arguments: {npc['name']} {npc.get('race', '')} {npc.get('class', '')} {npc_level} {npc.get('background', '')}", category="character_updates")

                subprocess.run([
                    "python", "core/generators/npc_builder.py",
                    npc['name'],
                    npc.get('race', ''),
                    npc.get('class', ''),
                    npc_level,
                    npc.get('background', '')
                ], check=True)
                info(f"SUCCESS: NPC profile created for {npc['name']}", category="character_updates")
            except subprocess.CalledProcessError as e:
                error(f"FAILURE: Failed to create NPC profile for {npc['name']}: {e}", category="character_updates")
                return

        # Now we can add the NPC to the party
        # Create entry matching the party_schema.json requirements (name and role)
        npc_entry = {
            "name": npc.get('name'),
            "role": npc.get('role', npc.get('class', 'Companion'))  # Use role if provided, else class, else default
        }
        
        # Load the actual NPC data to get the correct display name
        from utils.encoding_utils import safe_json_load
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy
        
        # Use fuzzy matching to find the correct NPC file
        matched_name = find_character_file_fuzzy(npc['name'])
        if matched_name:
            npc_file = path_manager.get_character_path(matched_name)
        else:
            # Fallback to normalized name if no match found
            normalized_name = normalize_character_name(npc['name'])
            npc_file = path_manager.get_character_path(normalized_name)
        
        if os.path.exists(npc_file):
            npc_data = safe_json_load(npc_file)
            if npc_data and 'name' in npc_data:
                # Use the name from the character file for consistency
                npc_entry['name'] = npc_data['name']
                debug(f"STATE_CHANGE: Using character file name '{npc_data['name']}' for party tracker", category="character_updates")
        
        party_tracker_data["partyNPCs"].append(npc_entry)
    elif operation == "remove":
        party_tracker_data["partyNPCs"] = [x for x in party_tracker_data["partyNPCs"] if x["name"] != npc["name"]]

    safe_json_dump(party_tracker_data, "party_tracker.json")
    info(f"STATE_CHANGE: Party NPCs updated - {operation} {npc['name']}", category="character_updates")

def run_combat_simulation(encounter_id, party_tracker_data, location_data):
    """Run the combat simulation"""
    # Import here to avoid circular imports
    from core.managers.combat_manager import run_combat_simulation as run_combat
    return run_combat(encounter_id, party_tracker_data, location_data)

def get_module_starting_location(module_name: str) -> tuple:
    """Get the starting location for a module using AI analysis with caching"""
    try:
        # Check world registry for cached starting location
        world_registry_path = "modules/world_registry.json"
        world_registry = safe_json_load(world_registry_path)
        
        if world_registry and 'modules' in world_registry:
            module_data = world_registry['modules'].get(module_name, {})
            cached_start = module_data.get('startingLocation')
            
            if cached_start:
                debug(f"FILE_OP: Using cached starting location for {module_name}", category="module_loading")
                return (
                    cached_start.get('locationId', 'A01'),
                    cached_start.get('locationName', 'Unknown Location'),
                    cached_start.get('areaId', 'AREA001'),
                    cached_start.get('areaName', 'Unknown Area')
                )
        
        # No cached result, use AI to analyze module
        debug(f"AI_CALL: No cached starting location found, analyzing {module_name} with AI", category="module_loading")
        
        path_manager = ModulePathManager(module_name)
        area_ids = path_manager.get_area_ids()
        
        if not area_ids:
            return ("A01", "Unknown Location", "AREA001", "Unknown Area")
        
        # Gather all module data for AI analysis
        module_analysis_data = {
            "moduleName": module_name,
            "areas": {},
            "plotData": None
        }
        
        # Load all area files
        for area_id in area_ids:
            try:
                area_file = path_manager.get_area_path(area_id)
                area_data = safe_json_load(area_file)
                if area_data:
                    # Include key information for AI analysis
                    module_analysis_data["areas"][area_id] = {
                        "areaName": area_data.get("areaName", ""),
                        "areaType": area_data.get("areaType", ""),
                        "areaDescription": area_data.get("areaDescription", ""),
                        "recommendedLevel": area_data.get("recommendedLevel", 1),
                        "dangerLevel": area_data.get("dangerLevel", "unknown"),
                        "locations": area_data.get("locations", [])  # All locations for analysis
                    }
            except Exception as e:
                warning(f"FILE_OP: Could not load area {area_id}: {e}", category="file_operations")
                continue
        
        # Load plot data
        try:
            plot_file = path_manager.get_plot_path()
            plot_data = safe_json_load(plot_file)
            if plot_data:
                # Include key plot information
                module_analysis_data["plotData"] = {
                    "mainObjective": plot_data.get("mainObjective", ""),
                    "plotPoints": plot_data.get("plotPoints", [])  # All plot points
                }
        except Exception as e:
            warning(f"FILE_OP: Could not load plot data: {e}", category="file_operations")
        
        # Use AI to determine starting location
        starting_location = _ai_analyze_starting_location(module_analysis_data)
        
        # Cache the result in world registry
        if starting_location and world_registry:
            if module_name not in world_registry['modules']:
                world_registry['modules'][module_name] = {}
            
            world_registry['modules'][module_name]['startingLocation'] = {
                'locationId': starting_location[0],
                'locationName': starting_location[1], 
                'areaId': starting_location[2],
                'areaName': starting_location[3],
                'determinedBy': 'AI',
                'timestamp': datetime.now().isoformat()
            }
            
            safe_json_dump(world_registry, world_registry_path)
            info(f"SUCCESS: Cached AI-determined starting location for {module_name}", category="module_loading")
        
        return starting_location
        
    except Exception as e:
        error(f"FAILURE: Could not get starting location for {module_name}: {e}", category="module_loading")
        return ("A01", "Unknown Location", "AREA001", "Unknown Area")

def _ai_analyze_starting_location(module_data: dict) -> tuple:
    """Use AI to analyze module data and determine the best starting location"""
    try:
        # Use factory for multi-provider support
        from utils.ai_client_factory import create_chat_client, get_chat_model_name, handle_provider_error
        client = create_chat_client()
        
        # Get provider-aware model
        model_name = get_chat_model_name()
        debug(f"Using AI model for starting location: {model_name}", category="ai_provider")
        
        system_prompt = """You are an expert 5th edition adventure module analyst. Analyze the provided module data to determine the most logical starting location for player characters entering this adventure module.

ANALYSIS CRITERIA:
1. **Adventure Flow**: Look at plot points (PP001 usually indicates starting area)
2. **Area Types**: Towns/settlements are typical starting points, dungeons/ruins typically aren't
3. **NPCs**: Areas with guides, quest-givers, or friendly NPCs often indicate starting locations
4. **Danger Level**: Lower danger areas are more suitable for arrivals
5. **Logical Narrative**: Where would adventurers most likely arrive or be directed to begin?

RETURN FORMAT:
Respond with ONLY a JSON object in this exact format:
{
  "locationId": "R01",
  "locationName": "Specific Location Name", 
  "areaId": "SR001",
  "areaName": "Area Name",
  "reasoning": "Brief explanation of why this is the starting location"
}

Use the EXACT locationId and areaId from the provided data. Do not create new IDs."""

        user_prompt = f"""Analyze this 5th edition adventure module to determine the starting location:

MODULE DATA:
{json.dumps(module_data, indent=2)}

Determine the most logical starting location based on adventure flow, area types, NPCs, and narrative logic."""

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )
        except Exception as api_error:
            # Check if we should fallback to OpenAI
            error_result = handle_provider_error(api_error, context="Starting location analysis")
            if error_result['should_fallback']:
                warning(f"Falling back to OpenAI: {api_error}", category="ai_provider")
                fallback_client = create_chat_client(use_fallback=True)
                response = fallback_client.chat.completions.create(
                    model=config.DM_MINI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1
                )
            else:
                raise
        
        # Track token usage
        if USAGE_TRACKING_AVAILABLE:
            try:
                track_response(response)
            except:
                pass
        
        ai_response = response.choices[0].message.content.strip()
        debug(f"AI_CALL: Starting location analysis response: {ai_response}", category="ai_operations")
        
        # Parse AI response - handle markdown code blocks
        json_content = ai_response
        if ai_response.startswith('```json'):
            # Extract JSON from markdown code block
            lines = ai_response.split('\n')
            json_lines = []
            in_json_block = False
            for line in lines:
                if line.strip() == '```json':
                    in_json_block = True
                    continue
                elif line.strip() == '```' and in_json_block:
                    break
                elif in_json_block:
                    json_lines.append(line)
            json_content = '\n'.join(json_lines)
            debug(f"AI_CALL: Extracted JSON from code block: {json_content}", category="ai_operations")
        
        try:
            result = json.loads(json_content)
            
            # Validate required fields
            required_fields = ['locationId', 'locationName', 'areaId', 'areaName']
            if all(field in result for field in required_fields):
                info(f"AI_CALL: AI determined starting location: {result['areaId']}/{result['locationId']} - {result['locationName']}", category="module_loading")
                debug(f"AI_CALL: AI reasoning: {result.get('reasoning', 'No reasoning provided')}", category="ai_operations")
                
                return (
                    result['locationId'],
                    result['locationName'],
                    result['areaId'], 
                    result['areaName']
                )
            else:
                print(f"ERROR: AI response missing required fields: {result}")
                
        except json.JSONDecodeError as e:
            print(f"ERROR: Could not parse AI response as JSON: {e}")
            print(f"AI response was: {ai_response}")
        
        # Fallback to first area/location if AI analysis fails
        print("WARNING: AI analysis failed, falling back to first available location")
        return _get_fallback_starting_location(module_data)
        
    except Exception as e:
        print(f"ERROR: AI starting location analysis failed: {e}")
        return _get_fallback_starting_location(module_data)

def _get_fallback_starting_location(module_data: dict) -> tuple:
    """Fallback method to get first available location if AI analysis fails"""
    try:
        areas = module_data.get('areas', {})
        if areas:
            # Get first area
            first_area_id = next(iter(areas.keys()))
            first_area = areas[first_area_id]
            
            locations = first_area.get('locations', [])
            if locations:
                first_location = locations[0]
                return (
                    first_location.get('locationId', 'A01'),
                    first_location.get('name', 'Unknown Location'),
                    first_area_id,
                    first_area.get('areaName', 'Unknown Area')
                )
        
        return ("A01", "Unknown Location", "AREA001", "Unknown Area")
        
    except Exception as e:
        print(f"WARNING: Fallback location detection failed: {e}")
        return ("A01", "Unknown Location", "AREA001", "Unknown Area")

def get_travel_narration(target_module: str) -> str:
    """Get AI-generated travel narration for module transition"""
    try:
        world_registry = safe_json_load("modules/world_registry.json")
        if world_registry and "modules" in world_registry:
            module_data = world_registry["modules"].get(target_module, {})
            travel_data = module_data.get("travelNarration", {})
            return travel_data.get("travelNarration", 
                f"The party travels to the {target_module} region, where new adventures await.")
    except:
        return f"The party travels to the {target_module} region, where new adventures await."

def process_action(action, party_tracker_data, location_data, conversation_history):
    """Process an action based on its type
    
    Returns:
        dict: {
            "status": "continue" | "exit" | "needs_response",
            "needs_update": bool,
            "response_data": dict (optional) - data for generating new AI response
        }
    """
    # Import modules here to avoid circular imports
    from core.managers import location_manager
    from updates.update_world_time import update_world_time
    from updates.plot_update import update_plot
    from updates.update_character_info import update_character_info

    # Helper function to create consistent return values
    def create_return(status="continue", needs_update=False, response_data=None):
        result = {"status": status, "needs_update": needs_update}
        if response_data:
            result["response_data"] = response_data
        return result

    global needs_conversation_history_update
    needs_conversation_history_update = False
    
    action_type = action.get("action")
    parameters = action.get("parameters", {})

    if action_type == ACTION_CREATE_ENCOUNTER:
        print("\n[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER START ==========")
        print(f"[DEBUG ACTION_HANDLER] Action received: {action}")
        debug("INITIALIZATION: Creating combat encounter", category="combat_processing")
        
        # TABLETOP MODE: Filter party members from NPCs list
        # Party members should be treated as players, not NPCs
        try:
            # TABLETOP MODE: Use centralized party data access when available
            import utils.pc_manager as pc_manager
            if pc_manager.should_use_abstraction_layer(party_tracker_data):
                party_members = pc_manager.get_party_tracker().get('partyMembers', [])
            else:
                party_members = party_tracker_data.get("partyMembers", [])
            npcs_list = parameters.get("npcs", [])
            
            if party_members and npcs_list:
                # Filter out any party members from the npcs list
                filtered_npcs = []
                removed_party_members = []
                
                for npc_name in npcs_list:
                    # Check if this NPC is actually a party member
                    is_party_member = any(
                        pm.lower() == npc_name.lower() or 
                        pm.lower().replace(" ", "_") == npc_name.lower().replace(" ", "_")
                        for pm in party_members
                    )
                    
                    if is_party_member:
                        removed_party_members.append(npc_name)
                        debug(f"TABLETOP MODE: Removed party member '{npc_name}' from NPCs list (treating as player)", category="combat_processing")
                    else:
                        filtered_npcs.append(npc_name)
                
                if removed_party_members:
                    parameters["npcs"] = filtered_npcs
                    action["parameters"] = parameters
                    info(f"TABLETOP MODE: Filtered {len(removed_party_members)} party members from encounter NPCs: {removed_party_members}", category="combat_processing")
                    print(f"[DEBUG ACTION_HANDLER] TABLETOP MODE: Filtered party members from NPCs: {removed_party_members}")
        except Exception as e:
            debug(f"TABLETOP MODE: Error filtering party members from NPCs: {e}", category="combat_processing")
        
        # Update status to lock input during encounter building
        try:
            from core.managers.status_manager import status_manager
            status_manager.update_status("Prepare for battle - building encounter...", is_processing=True)
            debug("STATE_CHANGE: Status updated to building encounter", category="combat_processing")
        except Exception as e:
            error(f"FAILURE: Could not update status for encounter building", exception=e, category="combat_processing")
        
        try:
            print("[DEBUG ACTION_HANDLER] Calling combat_builder.py...")
            debug(f"SUBPROCESS: Sending to combat_builder.py: {json.dumps(action)}", category="combat_processing")
            # Get the path to combat_builder.py relative to the project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            combat_builder_path = os.path.join(project_root, "core", "generators", "combat_builder.py")
            
            result = subprocess.run(
                ["python", combat_builder_path],
                input=json.dumps(action),
                check=True, capture_output=True, text=True
            )
            print(f"[DEBUG ACTION_HANDLER] combat_builder.py completed")
            print(f"[DEBUG ACTION_HANDLER] Output: {result.stdout[:200]}...")  # First 200 chars
            debug(f"SUBPROCESS: combat_builder.py output: {result.stdout}", category="combat_processing")
            debug(f"SUBPROCESS: combat_builder.py status: {result.stderr}", category="combat_processing")
            info("SUCCESS: Combat encounter created successfully", category="combat_processing")

            print(f"[DEBUG ACTION_HANDLER] Checking for success in output...")
            if "Encounter successfully built and saved to" in result.stdout:
                # Extract encounter ID from the full path
                # Example: "modules/encounters/encounter_TW03-E2.json" -> "TW03-E2"
                for line in result.stdout.split('\n'):
                    if "Encounter successfully built and saved to" in line:
                        encounter_path = line.split()[-1]
                        encounter_id = encounter_path.split('encounter_')[-1].replace('.json', '')
                        print(f"[DEBUG ACTION_HANDLER] SUCCESS! Encounter created with ID: {encounter_id}")
                        break

                # TABLETOP MODE: Validate encounter file has at least one enemy before
                # starting combat. Prevents zombie combat sessions where the narrator
                # hallucinated enemy names that combat_builder couldn't resolve, resulting
                # in an encounter file with only player/NPC entries and zero enemies.
                encounter_file_check = f"modules/encounters/encounter_{encounter_id}.json"
                try:
                    encounter_check_data = safe_json_load(encounter_file_check)
                    if encounter_check_data:
                        enemy_count = sum(1 for c in encounter_check_data.get("creatures", [])
                                          if c.get("type") == "enemy")
                        if enemy_count == 0:
                            error(f"TABLETOP MODE: Encounter {encounter_id} created with 0 enemies. "
                                  f"Aborting combat - narrator may have hallucinated creature names "
                                  f"that were not found in the bestiary.",
                                  category="combat_processing")
                            print(f"[DEBUG ACTION_HANDLER] TABLETOP MODE: Encounter has 0 enemies, aborting combat")
                            # Clean up the invalid encounter file
                            try:
                                os.remove(encounter_file_check)
                                debug(f"STATE_CHANGE: Removed empty encounter file: {encounter_file_check}",
                                      category="combat_processing")
                            except OSError:
                                pass
                            # C1.2: Return explicit error status instead of silent continue
                            # Reset status and return error to prevent fake combat continuation
                            try:
                                from core.managers.status_manager import status_ready
                                status_ready()
                            except Exception:
                                pass
                            print("[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END - NO ENEMIES ==========\n")
                            # C1.A2: Return explicit error status to prevent continuing combat narration
                            return {"status": "error", "error_message": "Encounter created with zero enemies. Combat aborted - narrator may have hallucinated creature names not in bestiary."}
                except Exception as e:
                    error(f"TABLETOP MODE: Failed to validate encounter enemy count: {e}",
                          exception=e, category="combat_processing")
                    # Fail open - let combat proceed if validation itself crashes

                party_tracker_data["worldConditions"]["activeCombatEncounter"] = encounter_id
                safe_json_dump(party_tracker_data, "party_tracker.json")
                debug(f"STATE_CHANGE: Updated party tracker with combat encounter ID: {encounter_id}", category="combat_processing")

                # MULTI-PC COMBAT: Initialize combat manager if multiplayer mode enabled
                multi_pc_manager = None
                if MULTI_PC_COMBAT_AVAILABLE and is_multi_pc_combat_enabled():
                    try:
                        multi_pc_manager = create_combat_manager(party_tracker_data)
                        if multi_pc_manager:
                            debug(f"STATE_CHANGE: Multi-PC combat manager initialized with {len(multi_pc_manager.pc_states)} PCs", category="combat_processing")
                            
                            # TABLETOP MODE: Phase 1 two-group initiative state
                            # Roll DM group now, wait for facilitator PC roll via /init.
                            dm_group_roll = random.randint(1, 20)
                            encounter_file = f"modules/encounters/encounter_{encounter_id}.json"
                            encounter_data_for_init = safe_json_load(encounter_file) or {}
                            encounter_data_for_init["initiativeMode"] = "two_group_phase1"
                            encounter_data_for_init["initiativeRolls"] = {
                                "dmGroup": dm_group_roll,
                                "pcGroup": None
                            }
                            encounter_data_for_init["initiativeWinner"] = None
                            encounter_data_for_init["roundStartsWith"] = None
                            encounter_data_for_init["awaitingPcGroupRoll"] = True
                            safe_json_dump(encounter_data_for_init, encounter_file)

                            print(f"[DEBUG ACTION_HANDLER] PHASE1 INIT: DM group pre-roll={dm_group_roll}; awaiting /init from facilitator")
                            debug(
                                f"COMBAT: Initialized Phase 1 initiative state for encounter {encounter_id} "
                                f"(dmGroup={dm_group_roll}, awaitingPcGroupRoll=True)",
                                category="combat_processing"
                            )

                            # Legacy compatibility mirror for older paths that still read party tracker.
                            party_tracker_data["worldConditions"]["combatInitiative"] = {
                                "partyRoll": None,
                                "enemyRoll": dm_group_roll,
                                "partyGoesFirst": None
                            }
                            safe_json_dump(party_tracker_data, "party_tracker.json")
                    except Exception as e:
                        error(f"FAILURE: Multi-PC combat initialization failed: {e}", exception=e, category="combat_processing")
                        multi_pc_manager = None  # Fall back to single-PC mode

                # Reload location data here
                current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
                current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
                # Use the reloaded location data for the combat simulation
                reloaded_location_data = get_location_data(current_location_id, current_area_id)


                if reloaded_location_data is None:
                    print(f"ERROR: Failed to load location data for {current_location_id}")
                    return # Or handle error appropriately

                print(f"[DEBUG ACTION_HANDLER] About to call run_combat_simulation with encounter: {encounter_id}")
                print("[DEBUG ACTION_HANDLER] This should start INTERACTIVE turn-based combat...")
                if multi_pc_manager:
                    print(f"[DEBUG ACTION_HANDLER] MULTI-PC MODE ACTIVE: {len(multi_pc_manager.pc_states)} PCs participating")
                
                # Update status to show combat is starting
                try:
                    from core.managers.status_manager import status_manager
                    status_manager.update_status("Combat in progress...", is_processing=True)
                    debug("STATE_CHANGE: Status updated to combat in progress", category="combat_processing")
                except Exception as e:
                    error(f"FAILURE: Could not update status for combat start", exception=e, category="combat_processing")
                
                dialogue_summary, updated_player_info = run_combat_simulation(encounter_id, party_tracker_data, reloaded_location_data)
                
                print(f"[DEBUG ACTION_HANDLER] Combat simulation returned. Type of result: {type(dialogue_summary)}")
                print(f"[DEBUG ACTION_HANDLER] Dialogue summary preview: {str(dialogue_summary)[:200]}...")

                # MULTI-PC COMBAT: Clean up combat manager state
                # TABLETOP MODE: File persistence is now handled by combat_manager.py per-turn
                # via final_character_updates (SP) and persist_combat_changes (MP)
                if multi_pc_manager and MULTI_PC_COMBAT_AVAILABLE:
                    try:
                        from core.managers.multi_pc_combat import cleanup_combat_manager
                        cleanup_combat_manager()
                        debug("STATE_CHANGE: Multi-PC combat manager cleaned up", category="combat_processing")
                    except ImportError:
                        pass  # cleanup_combat_manager not available

                # Single-PC mode (original behavior) - save player file if provided
                # UPSTREAM: This maintains single-player compatibility
                if not (multi_pc_manager and MULTI_PC_COMBAT_AVAILABLE):
                    module_name = party_tracker_data.get("module", "").replace(" ", "_")
                    path_manager = ModulePathManager(module_name)
                    from updates.update_character_info import normalize_character_name
                    player_name = party_tracker_data.get("active_character") or next((member for member in party_tracker_data.get("partyMembers", [])), None)
                    if player_name and updated_player_info is not None:
                        player_name_normalized = normalize_character_name(player_name)
                        player_file = path_manager.get_character_path(player_name_normalized)
                        safe_json_dump(updated_player_info, player_file)
                        debug(f"FILE_OP: Updated player file for {player_name}", category="character_updates")
                    else:
                        print("WARNING: Combat simulation did not return valid player info. Player file not updated.")

                # Copy combat summary to main conversation history
                print("[DEBUG ACTION_HANDLER] Loading combat conversation history...")
                combat_history = safe_json_load("modules/conversation_history/combat_conversation_history.json")
                print(f"[DEBUG ACTION_HANDLER] Combat history has {len(combat_history) if combat_history else 0} entries")
                
                combat_summary = next((entry for entry in reversed(combat_history) if entry["role"] == "assistant" and "Combat Summary:" in entry["content"]), None)

                if combat_summary:
                    print("[DEBUG ACTION_HANDLER] Found combat summary, appending to conversation history")
                    # Add clear historical marker to prevent Combat Commitment Point confusion
                    modified_combat_summary = {
                        "role": "user",
                        "content": "[COMBAT CONCLUDED - HISTORICAL RECORD]\n" + combat_summary["content"] + "\n[END OF COMBAT RECORD - Please continue the narrative after this combat]\n\nIMPORTANT: All XP, treasure, currency, items, and other rewards mentioned above have already been distributed by the combat system. Do NOT award them again."
                    }
                    conversation_history.append(modified_combat_summary)
                    # Import save_conversation_history from main
                    import sys

                    if __name__ != "__main__":

                        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

                    from main import save_conversation_history
                    save_conversation_history(conversation_history)
                    print("[DEBUG ACTION_HANDLER] Returning with status='needs_post_combat_narration' - main loop will get follow-up from AI")
                    print("[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END ==========\n")
                    # SIGNAL-BASED ARCHITECTURE: This return value is crucial for maintaining chronological history.
                    # When combat ends, we've already added the [COMBAT CONCLUDED...] summary to conversation_history.
                    # This signal tells main.py to:
                    # 1. NOT append the original createEncounter message (preventing duplication)
                    # 2. Request a new AI response for natural post-combat narration
                    # This ensures players get seamless transitions like Kira's dialogue after combat.
                    return {"status": "needs_post_combat_narration"}
                else:
                    print("ERROR: Combat summary not found in combat conversation history")
                    print("[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END WITH ERROR ==========\n")
                    # Reset status on error
                    try:
                        from core.managers.status_manager import status_ready
                        status_ready()
                    except Exception:
                        pass
            else:
                print(f"[DEBUG ACTION_HANDLER] FAILED! Encounter was not created successfully")
                print(f"[DEBUG ACTION_HANDLER] Full stdout: {result.stdout}")
                print(f"[DEBUG ACTION_HANDLER] Full stderr: {result.stderr}")
                print("[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END WITH FAILURE ==========\n")
                # C1.2: Return explicit error status instead of silent continue
                # TABLETOP MODE: 3.1 Enrich error message with missing monster details
                try:
                    from core.managers.status_manager import status_ready
                    status_ready()
                except Exception:
                    pass
                # Extract missing monster info from builder output
                error_detail = "Combat encounter creation failed."
                if result.stdout:
                    # Look for TABLETOP MODE monster errors in stdout
                    import re
                    monster_match = re.search(r"TABLETOP MODE: Monster '([^']+)' not found in bestiary at ([^\.]+\.json)", result.stdout)
                    if monster_match:
                        monster_name = monster_match.group(1)
                        expected_file = monster_match.group(2)
                        error_detail = f"Combat encounter creation failed: Monster '{monster_name}' is referenced in module content but missing stat file '{expected_file}'. Add the monster stat file or correct the reference."
                    elif "Failed to generate encounter" in result.stdout:
                        error_detail = "Combat encounter creation failed. Check game logs for details."
                return {"status": "error", "error_message": error_detail}

        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running combat_builder.py: {e}")
            print("Error output:", e.stderr)
            print("Standard output:", e.stdout)
            # C1.2: Return explicit error status on subprocess failure
            try:
                from core.managers.status_manager import status_ready
                status_ready()
            except Exception:
                pass
            return {"status": "error", "error_message": f"Combat builder subprocess failed: {e}"}
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
            # C1.2: Return explicit error status on unexpected exception
            try:
                from core.managers.status_manager import status_ready
                status_ready()
            except Exception:
                pass
            return {"status": "error", "error_message": f"Unexpected error during encounter creation: {e}"}

    elif action_type == ACTION_UPDATE_TIME:
        status_advancing_time()
        time_estimate_str = str(parameters["timeEstimate"])
        update_world_time(time_estimate_str)

    elif action_type == ACTION_UPDATE_PLOT:
        status_updating_plot()
        plot_point_id = parameters["plotPointId"]
        new_status = parameters["newStatus"]
        plot_impact = parameters.get("plotImpact", "")
        plot_filename = "module_plot.json"  # Now using unified plot file
        updated_plot = update_plot(plot_point_id, new_status, plot_impact, plot_filename)

    elif action_type == ACTION_EXIT_GAME:
        # Don't add return message here - it will be added when the player actually returns
        import sys

        if __name__ != "__main__":

            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        from main import save_conversation_history, exit_game
        save_conversation_history(conversation_history)
        exit_game()
        return create_return(status="exit")

    elif action_type == ACTION_TRANSITION_LOCATION:
        status_transitioning_location()
        new_location_name_or_id = parameters["newLocation"] # This should be a location ID now
        
        # Sanitize location names to prevent encoding issues
        current_location_name = sanitize_text(party_tracker_data["worldConditions"]["currentLocation"])
        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
        current_area_name = party_tracker_data["worldConditions"]["currentArea"]
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
        
        # Use the global location graph for validation
        from main import location_graph
        if location_graph is None or len(location_graph.nodes) == 0:
            print("DEBUG: [LocationGraph] WARNING - Global graph is empty or uninitialized. Triggering emergency reload.")
            if location_graph is None:
                # Graph was never initialized - create it now
                location_graph = LocationGraph()
                location_graph.load_module_data()
            else:
                # Graph exists but is empty - reload it
                location_graph.reload()
        print(f"DEBUG: [LocationGraph] Using global graph with {len(location_graph.nodes)} nodes")
        
        # MAP: Convert area ID to entry location ID if needed (TW001 -> TW01)
        if not location_graph.validate_location_id_format(new_location_name_or_id):
            # Try to find entry location for this area ID
            entry_location = location_graph.get_entry_location_for_area(new_location_name_or_id)
            if entry_location:
                debug(f"VALIDATION: Mapped area ID '{new_location_name_or_id}' to entry location '{entry_location}'", category="location_transitions")
                new_location_name_or_id = entry_location
        
        # VALIDATE: Check if location transition is valid
        is_valid, error_message, auto_area_connectivity_id = validate_location_transition(
            location_graph, current_location_id, new_location_name_or_id
        )
        
        if not is_valid:
            # Check if this is a cross-module transition attempt
            from core.managers.campaign_manager import CampaignManager
            campaign_manager = CampaignManager()
            
            # Determine which module owns the target location
            target_module = campaign_manager.get_module_from_location(new_location_name_or_id)
            current_module = party_tracker_data.get("module", "")
            
            if target_module and target_module != current_module:
                # This is a cross-module transition attempt!
                print(f"INFO: Cross-module transition detected: {current_module} -> {target_module}")
                
                # Get target location details for better error message
                target_location_name = "Unknown"
                if location_graph.nodes.get(new_location_name_or_id):
                    target_location_name = location_graph.nodes[new_location_name_or_id].get('location_name', 'Unknown')
                
                # Create helpful error message that guides the AI
                error_msg = (
                    f"Module Transition Required: The location '{new_location_name_or_id}' ({target_location_name}) "
                    f"is in the '{target_module}' module, but you are currently in the '{current_module}' module. "
                    f"If the player intends to travel to a different module (e.g., 'take me back to my keep', "
                    f"'let's return to {target_module}'), use the updatePartyTracker action with module parameter. "
                    f"If the player wants to stay in the current module (e.g., 'let's go to the inn'), "
                    f"use the appropriate location in the current module instead. "
                    f"For module travel, use: updatePartyTracker with module='{target_module}'"
                )
                
                print(f"ERROR: {error_msg}")
                return create_return(
                    status="error",
                    needs_update=False,
                    response_data={"error_message": error_msg}
                )
            
            # Original error for non-module path issues
            print(f"ERROR: {error_message}")
            return create_return(
                status="error",
                needs_update=False,
                response_data={"error_message": f"Path Validation: {error_message}"}
            )

        # NOTE: Transition intelligence agent now runs in PRE-VALIDATION (main.py)
        # before this action handler is called. If we reach here, the transition
        # was already approved by the agent.

        # Debug the exact string values for easier troubleshooting
        info(f"STATE_CHANGE: Transitioning from '{current_location_name}' to '{new_location_name_or_id}'", category="location_transitions")
        debug(f"VALIDATION: Current location string (hex): {current_location_name.encode('utf-8').hex()}", category="location_transitions")
        debug(f"VALIDATION: New location string (hex): {new_location_name_or_id.encode('utf-8').hex()}", category="location_transitions")
        
        # Use enhanced location manager with auto-generated area connectivity ID
        transition_prompt = location_manager.handle_location_transition(
            current_location_name, 
            new_location_name_or_id, 
            current_area_name, 
            current_area_id, 
            auto_area_connectivity_id
        )

        if transition_prompt:
            # Get the new location ID from party tracker after transition
            # The location manager updates party_tracker.json before we get here
            try:
                updated_party_tracker = safe_json_load("party_tracker.json")
                new_location_name = updated_party_tracker["worldConditions"]["currentLocation"]
                new_location_id = updated_party_tracker["worldConditions"]["currentLocationId"]
                # Include location IDs in the transition message for reliable matching
                conversation_history.append({"role": "user", "content": f"Location transition: {sanitize_text(current_location_name)} ({current_location_id}) to {sanitize_text(new_location_name)} ({new_location_id})"})
            except Exception as e:
                warning(f"FAILURE: Could not get updated location IDs: {str(e)}", category="location_transitions")
                # Fallback to original format if we can't get the IDs
                conversation_history.append({"role": "user", "content": f"Location transition: {sanitize_text(current_location_name)} to {sanitize_text(new_location_name_or_id)}"})
            
            # Save conversation history immediately after adding transition marker
            import sys

            if __name__ != "__main__":

                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

            from main import save_conversation_history
            save_conversation_history(conversation_history)

            # GENERATE TRANSITION NARRATION using the transition_prompt
            info("STATE_CHANGE: Generating transition narration using AI", category="location_transitions")
            try:
                # Use factory for multi-provider support
                from utils.ai_client_factory import create_chat_client, get_chat_model_name, handle_provider_error
                client = create_chat_client()
                
                # Get provider-aware model
                model_name = get_chat_model_name()
                debug(f"Using AI model for transition: {model_name}", category="ai_provider")

                # Build prompt for transition narration
                transition_messages = [
                    {"role": "system", "content": "You are a skilled Dungeon Master narrating a location transition."},
                    {"role": "user", "content": transition_prompt}
                ]

                try:
                    transition_response = client.chat.completions.create(
                        model=model_name,
                        messages=transition_messages,
                        temperature=0.7
                    )
                except Exception as api_error:
                    # Check if we should fallback to OpenAI
                    error_result = handle_provider_error(api_error, context="Transition narration")
                    if error_result['should_fallback']:
                        warning(f"Falling back to OpenAI: {api_error}", category="ai_provider")
                        fallback_client = create_chat_client(use_fallback=True)
                        transition_response = fallback_client.chat.completions.create(
                            model=config.DM_MAIN_MODEL,
                            messages=transition_messages,
                            temperature=0.7
                        )
                    else:
                        raise

                transition_narration = transition_response.choices[0].message.content.strip()
                info("SUCCESS: Transition narration generated", category="location_transitions")

                # Save transition narration to conversation history as assistant message
                conversation_history.append({"role": "assistant", "content": transition_narration})
                save_conversation_history(conversation_history)
                debug("SUCCESS: Transition narration saved to conversation history", category="location_transitions")

            except Exception as e:
                error(f"FAILURE: Failed to generate transition narration", exception=e, category="location_transitions")
                transition_narration = f"The party travels to {new_location_name}."
                # Save fallback narration too
                conversation_history.append({"role": "assistant", "content": transition_narration})
                save_conversation_history(conversation_history)
            
            # CAMPAIGN INTEGRATION: Check for cross-module transitions
            try:
                from core.managers.campaign_manager import CampaignManager
                campaign_manager = CampaignManager()
                
                # Detect if this is a cross-module transition
                is_cross_module, from_module, to_module = campaign_manager.detect_module_transition(
                    current_location_id, new_location_id
                )
                
                if is_cross_module:
                    info(f"STATE_CHANGE: Cross-module transition detected during location change: {from_module} -> {to_module}", category="module_management")
                    
                    # DON'T generate summary here - it will be handled by updatePartyTracker
                    # This prevents duplicate summaries for the same module transition
                    debug("STATE_CHANGE: Deferring module summary generation to updatePartyTracker action", category="module_management")
                    
                    # Just update the module field in party tracker
                    updated_party_tracker["module"] = to_module
                    safe_json_dump(updated_party_tracker, "party_tracker.json")
                    debug(f"STATE_CHANGE: Updated party tracker module to {to_module}", category="module_management")
                    
                    # Note: Campaign context injection will happen when updatePartyTracker is called
                    # This ensures summaries are generated only once per transition
                else:
                    debug(f"STATE_CHANGE: Within-module transition: {current_location_id} -> {new_location_id}", category="location_transitions")
                    
            except Exception as e:
                print(f"Warning: Campaign transition check failed: {e}")
                # Don't let campaign system errors break location transitions
            
            info("SUCCESS: Location transition complete", category="location_transitions")
            needs_conversation_history_update = True  # Trigger conversation history reload
             # After transition, the current_location_data in the main loop might be stale.
            # We need to ensure the AI response processing uses the *new* location data.
            # This might require process_ai_response to reload location data or for main_game_loop to handle it.
            # For now, let's assume the main loop will reload it before the next AI call.
        else:
            print("ERROR: Failed to handle location transition")
            # Create error message for the AI DM
            error_message = f"""SYSTEM ERROR: Location Transition Failed

The attempted transition to '{new_location_name_or_id}' failed because this location does not exist or is not connected from the current location '{current_location_name}'.

Please use a valid location that exists in the current area ({current_area_id}) and is connected to the current location. Check the map data and connectivity information to ensure valid transitions."""
            
            # Append error to conversation history
            conversation_history.append({"role": "user", "content": error_message})
            
            # Import necessary functions from main
            import sys

            if __name__ != "__main__":

                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

            from main import save_conversation_history
            save_conversation_history(conversation_history)
            
            # Return signal to get new AI response
            return create_return(status="needs_response", needs_update=True)

    elif action_type == ACTION_LEVEL_UP:
        status_processing_levelup()
        entity_name = parameters.get("entityName")
        new_level = parameters.get("newLevel")
        info(f"INITIALIZATION: Starting levelUp session for {entity_name} to level {new_level}", category="character_updates")

        try:
            # Import the session manager
            from core.managers.level_up_manager import LevelUpSession
            
            # Find character file to get current level
            from updates.update_character_info import normalize_character_name
            module_name = party_tracker_data.get("module", "").replace(" ", "_")
            path_manager = ModulePathManager(module_name)
            char_file = path_manager.get_character_path(normalize_character_name(entity_name))
            character_data = safe_read_json(char_file)
            
            if not character_data:
                print(f"ERROR: Could not find character {entity_name} to start level up.")
                # Return an error message to display in the UI
                return create_return(status="error", response_data={"error_message": "Character data not found."})

            current_level = character_data.get("level", 1)

            # Create a new level up session object
            level_up_session = LevelUpSession(entity_name, current_level, new_level)
            
            # Return a special status to the main loop, passing the session object
            return {
                "status": "enter_levelup_mode",
                "session": level_up_session
            }

        except Exception as e:
            print(f"ERROR: A critical error occurred while initializing the level up session: {e}")
            import traceback
            traceback.print_exc()
            return create_return(status="error", response_data={"error_message": "System error during level up."})

    elif action_type == ACTION_UPDATE_CHARACTER_INFO:
        status_updating_character()
        debug("STATE_CHANGE: Processing updateCharacterInfo action", category="character_updates")
        changes = parameters.get("changes")
        
        # Validate changes parameter
        if not changes or not isinstance(changes, (str, dict)):
            print(f"ERROR: Invalid changes parameter: {changes} (type: {type(changes)})")
            return create_return(status="continue", needs_update=False)
        
        # Convert dict to string if needed
        if isinstance(changes, dict):
            changes = json.dumps(changes)
        
        character_name = parameters.get("characterName")
        
        # Backward compatibility: if no characterName provided, try legacy parameters
        if not character_name:
            # Try npcName first (for NPC updates)
            character_name = parameters.get("npcName")
            if not character_name:
                # Fall back to active player name from party tracker
                active_char = party_tracker_data.get("active_character")
                if active_char:
                    character_name = active_char.lower()
                else:
                    character_name = next((member.lower() for member in party_tracker_data.get("partyMembers", [])), None)
        
        if character_name:
            debug(f"STATE_CHANGE: Updating character info for {character_name}", category="character_updates")
            try:
                debug(f"STATE_CHANGE: Calling update_character_info for {character_name}", category="character_updates")
                success = update_character_info(character_name, changes)
                debug(f"STATE_CHANGE: update_character_info returned {success}", category="character_updates")
                if success:
                    info("SUCCESS: Character info updated successfully", category="character_updates")
                    needs_conversation_history_update = True
                    
                    # Track temporary effects in parallel
                    try:
                        from updates.update_character_effects import update_character_effects
                        debug(f"EFFECTS: Tracking potential effect for {character_name}: {changes}", category="effects_tracking")
                        effects_success = update_character_effects(character_name, changes)
                        if effects_success:
                            debug(f"EFFECTS: Successfully tracked effect", category="effects_tracking")
                        else:
                            debug(f"EFFECTS: Effect not tracked (not applicable or failed)", category="effects_tracking")
                    except Exception as e:
                        warning(f"EFFECTS: Failed to track effect: {str(e)}", category="effects_tracking")
                        # Don't break the game if effects tracking fails
                else:
                    error(f"FAILURE: Failed to update character info for {character_name}", category="character_updates")
                    print(f"ERROR: Failed to update character info for {character_name}")
            except Exception as e:
                error(f"FAILURE: Exception in character update", exception=e, category="character_updates")
                # Use print with separate arguments to avoid format string interpretation
                print("ERROR: Failed to update character info:", str(e))
            finally:
                # Always reset status after character update completes
                try:
                    from core.managers.status_manager import status_ready
                    status_ready()
                    debug("STATE_CHANGE: Status reset after character update", category="character_updates")
                except Exception:
                    pass
        else:
            print("ERROR: No character name provided and no player found in party tracker.")
            # Reset status even if no character was found
            try:
                from core.managers.status_manager import status_ready
                status_ready()
            except Exception:
                pass


    elif action_type == ACTION_UPDATE_PARTY_NPCS:
        operation = parameters["operation"]
        npc = parameters["npc"]
        update_party_npcs(party_tracker_data, operation, npc)

    elif action_type == ACTION_UPDATE_ENCOUNTER:
        debug("STATE_CHANGE: Processing updateEncounter action", category="combat_processing")
        encounter_id = parameters.get("encounterId")
        changes = parameters.get("changes")
        
        if encounter_id and changes:
            try:
                # Import the update_encounter function
                from updates.update_encounter import update_encounter
                
                # Update the encounter
                updated_encounter = update_encounter(encounter_id, changes)
                
                if updated_encounter:
                    info(f"SUCCESS: Encounter {encounter_id} updated successfully", category="combat_processing")
                    needs_conversation_history_update = True
                else:
                    print(f"ERROR: Failed to update encounter {encounter_id}")
            except Exception as e:
                print(f"ERROR: Exception while updating encounter: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            print(f"ERROR: Missing required parameters for updateEncounter. encounterId: {encounter_id}, changes: {changes}")

    elif action_type == ACTION_CREATE_NEW_MODULE:
        debug("STATE_CHANGE: Processing createNewModule action", category="module_management")
        try:
            # Pass ALL parameters directly from AI to module builder
            # The AI is fully in control of module creation
            from core.generators.module_builder import ai_driven_module_creation
            
            # Define progress callback to send updates to web interface
            def module_progress_callback(progress_data):
                """Send module creation progress to web interface"""
                from datetime import datetime
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"DEBUG: [Action Handler] [{timestamp}] module_progress_callback called - Stage {progress_data.get('stage')}")
                
                # Try to use the module progress queue if available (web mode)
                try:
                    from web.shared_state import module_progress_queue
                    module_progress_queue.put(progress_data)
                    print(f"DEBUG: [Action Handler] [{timestamp}] Successfully queued progress for stage {progress_data.get('stage')}")
                    debug(f"MODULE_PROGRESS: Queued for web - Stage {progress_data.get('stage')}/{progress_data.get('total_stages')} - {progress_data.get('message')}", category="module_management")
                except ImportError as e:
                    print(f"DEBUG: [Action Handler] [{timestamp}] ImportError: {e}")
                    # Terminal mode - just log progress
                    debug(f"MODULE_PROGRESS: Stage {progress_data.get('stage')}/{progress_data.get('total_stages')} - {progress_data.get('message')}", category="module_management")
                except Exception as e:
                    print(f"DEBUG: [Action Handler] [{timestamp}] Unexpected error: {e}")
            
            # Check if this is a single narrative parameter (new format)
            # or multiple parameters (old format)
            if len(parameters) == 1 and isinstance(list(parameters.values())[0], str):
                # Single narrative parameter - new format
                narrative = list(parameters.values())[0]
                parameters = {"narrative": narrative}
            
            # Let the module builder handle ALL parameter validation
            # This makes the system fully agentic - AI decides everything
            success, module_name = ai_driven_module_creation(parameters, progress_callback=module_progress_callback)
            
            if success:
                # Module name is now returned from the AI parser
                info(f"SUCCESS: Module '{module_name}' created successfully", category="module_management")
                
                # Auto-integrate with module stitcher
                try:
                    from core.generators.module_stitcher import get_module_stitcher
                    stitcher = get_module_stitcher()
                    # Run stitcher in fully autonomous mode
                    integrated_modules = stitcher.scan_and_integrate_new_modules()
                    info(f"SUCCESS: Module '{module_name}' integrated into world registry", category="module_management")
                    debug(f"STATE_CHANGE: Integration summary: {integrated_modules}", category="module_management")
                except Exception as e:
                    print(f"WARNING: Module created but stitching failed: {e}")
                
                # Reset processing status to ready
                try:
                    from core.managers.status_manager import status_ready
                    status_ready()
                    debug("STATE_CHANGE: Status reset to ready", category="session_management")
                except Exception as e:
                    error(f"FAILURE: Error resetting status", exception=e, category="session_management")
                
                # Signal module creation complete
                dm_note = f"Dungeon Master Note: New module '{module_name}' has been successfully created and integrated into the world. You may now guide the party to this new adventure."
                conversation_history.append({"role": "user", "content": dm_note})
                
                # Save conversation history
                import sys

                if __name__ != "__main__":

                    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

                from main import save_conversation_history
                save_conversation_history(conversation_history)
                
                needs_conversation_history_update = True
                
                # Return a special flag to trigger DM response generation
                return {"success": True, "needs_update": True, "needs_dm_response": True}
            else:
                print(f"ERROR: Failed to create module")
                
                # Reset status even on failure  
                try:
                    from core.managers.status_manager import status_ready
                    status_ready()
                    debug("STATE_CHANGE: Status reset after failure", category="session_management")
                except Exception as e:
                    error(f"FAILURE: Error resetting status after failure", exception=e, category="session_management")
                
        except Exception as e:
            print(f"ERROR: Exception while creating module: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Reset status on exception
            try:
                from core.managers.status_manager import status_ready  
                status_ready()
                debug("STATE_CHANGE: Status reset after exception", category="session_management")
            except Exception as status_e:
                error(f"FAILURE: Error resetting status after exception", exception=status_e, category="session_management")

    elif action_type == ACTION_ESTABLISH_HUB:
        debug("STATE_CHANGE: Processing establishHub action", category="module_management")
        try:
            # Extract hub parameters
            hub_name = parameters.get('hubName')
            hub_type = parameters.get('hubType', 'settlement')
            description = parameters.get('description', '')
            services = parameters.get('services', [])
            ownership = parameters.get('ownership', 'party')
            
            if hub_name:
                # Import campaign manager
                from core.managers.campaign_manager import CampaignManager
                campaign_manager = CampaignManager()
                
                # Establish the hub
                hub_data = {
                    "hubType": hub_type,
                    "description": description, 
                    "services": services,
                    "ownership": ownership
                }
                
                campaign_manager.establish_hub(hub_name, hub_data)
                
                info(f"SUCCESS: Hub '{hub_name}' established successfully", category="module_management")
                
                # Add DM note about hub establishment
                dm_note = f"Dungeon Master Note: '{hub_name}' has been established as a hub location. The party can now return here from other adventures."
                conversation_history.append({"role": "user", "content": dm_note})
                
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Missing required parameter 'hubName' for establishHub action")
                
        except Exception as e:
            print(f"ERROR: Exception while establishing hub: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_STORAGE_INTERACTION:
        debug("STATE_CHANGE: Processing storageInteraction action", category="storage_operations")
        try:
            # Import storage modules
            from core.managers.storage_processor import process_storage_request
            from core.managers.storage_manager import execute_storage_operation
            
            # Get storage description from parameters
            storage_description = parameters.get("description", "")
            character_name = parameters.get("characterName", "")
            
            # Fallback to party member if no character specified
            if not character_name:
                character_name = party_tracker_data.get("active_character") or next((member for member in party_tracker_data.get("partyMembers", [])), None)
                
            if not character_name:
                print(f"ERROR: No character name provided for storage interaction")
                return create_return(status="continue", needs_update=False)
                
            if not storage_description:
                print(f"ERROR: No storage description provided")
                return create_return(status="continue", needs_update=False)
                
            debug(f"AI_CALL: Processing storage request for {character_name}: '{storage_description}'", category="storage_operations")
            
            # Process natural language description into operation
            processor_result = process_storage_request(storage_description, character_name)
            
            if not processor_result.get("success"):
                print(f"ERROR: Storage processor failed: {processor_result.get('error')}")
                
                # Add error message to conversation
                error_message = f"Storage Error: {processor_result.get('error', 'Unknown error processing storage request')}"
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                return create_return(status="needs_response", needs_update=True)
                
            # Execute the validated storage operation
            operation = processor_result["operation"]
            debug(f"STATE_CHANGE: Executing storage operation: {operation}", category="storage_operations")
            
            execution_result = execute_storage_operation(operation)
            
            if execution_result.get("success"):
                info(f"SUCCESS: Storage operation successful: {execution_result.get('message')}", category="storage_operations")
                
                # Add success message to conversation
                success_message = f"Storage: {execution_result.get('message')}"
                conversation_history.append({"role": "user", "content": success_message})
                needs_conversation_history_update = True
                
            else:
                print(f"ERROR: Storage operation failed: {execution_result.get('error')}")
                
                # Add error message to conversation
                error_message = f"Storage Error: {execution_result.get('error', 'Unknown error executing storage operation')}"
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing storage interaction: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Add error message to conversation
            error_message = f"Storage System Error: An unexpected error occurred while processing your storage request."
            conversation_history.append({"role": "user", "content": error_message})
            needs_conversation_history_update = True

    elif action_type == ACTION_UPDATE_PARTY_TRACKER:
        debug("STATE_CHANGE: Processing updatePartyTracker action", category="party_management")
        try:
            # Load current party tracker
            current_party_data = safe_json_load("party_tracker.json")
            if not current_party_data:
                current_party_data = party_tracker_data.copy() if party_tracker_data else {}
            
            current_module = current_party_data.get("module", "Unknown")
            
            # Check if module is being changed
            new_module = parameters.get("module")
            if new_module and new_module != current_module:
                print(f"DEBUG: [Module Transition] Module change detected: {current_module} -> {new_module}")
                print(f"DEBUG: [Party Tracker Before Update] Module: {current_party_data.get('module', 'Unknown')}")
                info(f"STATE_CHANGE: Module change detected: {current_module} -> {new_module}", category="module_management")
                
                # Insert module transition marker immediately when module change is detected
                transition_text = f"Module transition: {current_module} to {new_module}"
                transition_message = {
                    "role": "user",
                    "content": transition_text
                }
                conversation_history.append(transition_message)
                print(f"DEBUG: [Module Transition] Inserted transition marker: '{transition_text}'")
                debug(f"STATE_CHANGE: Inserted module transition marker: '{transition_text}'", category="module_management")
                
                # Import campaign manager for auto-archiving
                from core.managers.campaign_manager import CampaignManager
                from main import save_conversation_history
                campaign_manager = CampaignManager()
                
                # DELAYED ARCHIVING: Don't archive immediately, set a flag instead
                # This allows the travel narrative to be added to conversation history first
                if current_module != "Unknown":
                    print(f"DEBUG: [Module Transition] Setting pending archive flag for module: {current_module}")
                    info(f"STATE_CHANGE: Module transition detected - archiving will occur after travel narrative", category="module_management")
                    
                    # Store the pending archive info in the return result
                    pending_archive = {
                        "from_module": current_module,
                        "to_module": new_module,
                        "party_tracker_data": current_party_data.copy()
                    }
                    
                    # Inject accumulated campaign context for the new module
                    debug(f"AI_CALL: Requesting campaign context for module: {new_module}", category="module_management")
                    campaign_context = campaign_manager.get_accumulated_summaries_context(new_module)
                    debug(f"AI_CALL: Campaign context received - Length: {len(campaign_context) if campaign_context else 0} characters", category="module_management")
                    if campaign_context:
                        conversation_history.append({
                            "role": "system", 
                            "content": f"=== CAMPAIGN CONTEXT ===\n{campaign_context}"
                        })
                        save_conversation_history(conversation_history)
                        info(f"SUCCESS: Campaign context injected for {new_module}", category="module_management")
                    else:
                        warning(f"STATE_CHANGE: No campaign context to inject for {new_module} - context was empty", category="module_management")
                
                # Auto-update to starting location if not explicitly provided
                if ("currentAreaId" not in parameters and 
                    "currentLocationId" not in parameters):
                    try:
                        location_id, location_name, area_id, area_name = get_module_starting_location(new_module)
                        info(f"STATE_CHANGE: Auto-setting starting location for {new_module}: {location_name} [{location_id}] in {area_name} [{area_id}]", category="module_management")
                        
                        # Add starting location to parameters for processing below
                        parameters["currentLocationId"] = location_id
                        parameters["currentLocation"] = location_name
                        parameters["currentAreaId"] = area_id
                        parameters["currentArea"] = area_name
                    except Exception as e:
                        print(f"WARNING: Could not auto-set starting location for {new_module}: {e}")
            
            # Update party tracker with all provided parameters using merge helper
            current_party_data = _merge_party_tracker_updates(current_party_data, parameters)
            
            # Save updated party tracker
            safe_json_dump(current_party_data, "party_tracker.json")
            print(f"DEBUG: [Party Tracker After Update] Module: {current_party_data.get('module', 'Unknown')}")
            info("SUCCESS: Party tracker updated successfully", category="party_management")
            # Always reload conversation history to pick up changes
            needs_conversation_history_update = True
            
            # If we set a pending archive flag, include it in the return
            if new_module and new_module != current_module and current_module != "Unknown":
                print(f"DEBUG: [Module Transition] Returning with pending_archive flag")
                return create_return(
                    needs_update=needs_conversation_history_update,
                    response_data={"pending_archive": pending_archive}
                )
            
        except Exception as e:
            print(f"ERROR: Exception while updating party tracker: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_MOVE_BACKGROUND_NPC:
        debug("STATE_CHANGE: Processing moveBackgroundNPC action", category="npc_management")
        try:
            # Extract parameters
            npc_name = parameters.get("npcName")
            context = parameters.get("context", "")
            current_location = parameters.get("currentLocation")
            
            if not npc_name:
                print(f"ERROR: Missing required parameter 'npcName' for moveBackgroundNPC action")
                return create_return(status="continue", needs_update=False)
            
            # Process the NPC movement
            success = move_background_npc(npc_name, context, current_location, party_tracker_data)
            
            if success:
                info(f"SUCCESS: Processed movement for NPC: {npc_name}", category="npc_management")
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Failed to process movement for NPC: {npc_name}")
                
        except Exception as e:
            print(f"ERROR: Exception while processing moveBackgroundNPC: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_SAVE_GAME:
        debug("STATE_CHANGE: Processing save game action", category="save_game")
        try:
            from updates.save_game_manager import SaveGameManager
            
            # Extract parameters
            description = parameters.get("description", "")
            save_mode = parameters.get("saveMode", "essential")  # "essential" or "full"
            
            # Create save game
            manager = SaveGameManager()
            success, message = manager.create_save_game(description, save_mode)
            
            if success:
                info(f"SUCCESS: Save game created: {message}", category="save_game")
                # Add success message to conversation
                save_message = f"Game saved successfully! {message}"
                conversation_history.append({"role": "system", "content": save_message})
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Failed to save game: {message}")
                # Add error message to conversation  
                error_message = f"Failed to save game: {message}"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing saveGame: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_RESTORE_GAME:
        debug("STATE_CHANGE: Processing restore game action", category="save_game")
        try:
            from updates.save_game_manager import SaveGameManager
            
            # Extract parameters
            save_folder = parameters.get("saveFolder")
            
            if not save_folder:
                print("ERROR: Missing required parameter 'saveFolder' for restoreGame action")
                error_message = "Error: No save folder specified for restore operation"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                return create_return(needs_update=needs_conversation_history_update)
            
            # Restore save game
            manager = SaveGameManager()
            success, message = manager.restore_save_game(save_folder)
            
            if success:
                info(f"SUCCESS: Save game restored: {message}", category="save_game")
                # Add success message to conversation
                restore_message = f"Game restored successfully! {message}\nRestarting game session..."
                conversation_history.append({"role": "system", "content": restore_message})
                needs_conversation_history_update = True
                # Return special status to indicate game should restart
                return create_return(status="restart", needs_update=needs_conversation_history_update)
            else:
                print(f"ERROR: Failed to restore game: {message}")
                # Add error message to conversation
                error_message = f"Failed to restore game: {message}"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing restoreGame: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_LIST_SAVES:
        debug("STATE_CHANGE: Processing list saves action", category="save_game")
        try:
            from updates.save_game_manager import SaveGameManager
            
            # Get list of save games
            manager = SaveGameManager()
            saves = manager.list_save_games()
            
            if saves:
                save_list_text = "Available save games:\n"
                for i, save in enumerate(saves, 1):
                    save_date = save.get("save_date_readable", "Unknown date")
                    description = save.get("description", "No description")
                    save_mode = save.get("save_mode", "unknown")
                    module = save.get("module", "Unknown")
                    save_folder = save.get("save_folder", "Unknown")
                    
                    save_list_text += f"{i}. {save_folder}\n"
                    save_list_text += f"   Date: {save_date}\n"
                    save_list_text += f"   Module: {module}\n"
                    save_list_text += f"   Mode: {save_mode}\n"
                    save_list_text += f"   Description: {description}\n\n"
            else:
                save_list_text = "No save games found."
            
            debug(f"VALIDATION: Found {len(saves)} save games", category="save_game")
            conversation_history.append({"role": "system", "content": save_list_text})
            needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing listSaves: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_DELETE_SAVE:
        debug("STATE_CHANGE: Processing delete save action", category="save_game")
        try:
            from updates.save_game_manager import SaveGameManager
            
            # Extract parameters
            save_folder = parameters.get("saveFolder")
            
            if not save_folder:
                print("ERROR: Missing required parameter 'saveFolder' for deleteSave action")
                error_message = "Error: No save folder specified for delete operation"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                return create_return(needs_update=needs_conversation_history_update)
            
            # Delete save game
            manager = SaveGameManager()
            success, message = manager.delete_save_game(save_folder)
            
            if success:
                info(f"SUCCESS: Save game deleted: {message}", category="save_game")
                conversation_history.append({"role": "system", "content": message})
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Failed to delete save game: {message}")
                conversation_history.append({"role": "system", "content": f"Error: {message}"})
                needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing deleteSave: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_REST:
        # TABLETOP MODE: Phase 3 - Rest Automation Enhancement (Option B)
        # Automatically restore HP, spell slots, and class features on rest
        debug("STATE_CHANGE: Processing rest action", category="character_updates")
        
        try:
            rest_type = parameters.get("type", "short")
            target_characters = parameters.get("characters", [])
            
            # If no specific characters, apply to all party members
            if not target_characters:
                target_characters = party_tracker_data.get("partyMembers", [])
            
            if not target_characters:
                warning("REST: No characters specified for rest action", category="character_updates")
                conversation_history.append({
                    "role": "system",
                    "content": "[SYSTEM] No characters available for rest."
                })
                needs_conversation_history_update = True
            else:
                rest_results = []
                
                for char_name in target_characters:
                    result = _process_character_rest(char_name, rest_type, party_tracker_data)
                    if result:
                        rest_results.append(result)
                
                # Generate summary message
                if rest_results:
                    rest_summary = _format_rest_summary(rest_results, rest_type)
                    conversation_history.append({
                        "role": "system",
                        "content": rest_summary
                    })
                    needs_conversation_history_update = True
                    
                    info(f"REST: Completed {rest_type} rest for {len(rest_results)} characters", 
                         category="character_updates")
                else:
                    warning(f"REST: No valid characters processed for {rest_type} rest", 
                           category="character_updates")
                    
        except Exception as e:
            error(f"REST: Error processing rest action: {e}", exception=e, category="character_updates")
            print(f"ERROR: Exception while processing rest action: {str(e)}")
            import traceback
            traceback.print_exc()

    else:
        print(f"WARNING: Unknown action type: {action_type}")
    
    return create_return(needs_update=needs_conversation_history_update)


def _process_character_rest(character_name: str, rest_type: str, party_tracker_data: dict) -> dict:
    """
    Process rest for a single character following 5e rules.
    
    5e Rest Rules:
    - Short Rest (>=1 hour): Players spend Hit Dice to heal, refresh shortRest features,
      Warlocks regain all spell slots
    - Long Rest (>=8 hours): Full HP restore, all spell slots, all features (short+long rest),
      removes exhaustion condition
    
    Args:
        character_name: Name of the character to process
        rest_type: 'short' or 'long'
        party_tracker_data: Current party tracker data
        
    Returns:
        dict with rest results or None if character not found
    """
    try:
        from utils.file_operations import safe_read_json
        from updates.update_character_info import update_character_info, find_character_file_fuzzy
        from utils.module_path_manager import ModulePathManager
        
        # Validate rest_type parameter
        if rest_type not in ["short", "long"]:
            warning(f"REST: Invalid rest_type '{rest_type}' for {character_name}, defaulting to 'short'", 
                   category="character_updates")
            rest_type = "short"
        
        # Get current module for path resolution
        module_name = party_tracker_data.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(module_name)
        
        # Use fuzzy matching to find character file
        matched_name = find_character_file_fuzzy(character_name)
        if matched_name:
            char_filepath = path_manager.get_character_path(matched_name)
            debug(f"REST: Fuzzy matched '{character_name}' to '{matched_name}'", category="character_updates")
        else:
            # Fallback to normalized name
            normalized_name = character_name.lower().replace(" ", "_").replace("'", "_")
            char_filepath = path_manager.get_character_path(normalized_name)
        
        character_data = safe_read_json(char_filepath)
        if not character_data:
            warning(f"REST: Could not load character data for {character_name} (tried: {char_filepath})", category="character_updates")
            return None
        
        results = {
            "character": character_name,
            "rest_type": rest_type,
            "hp_restored": 0,
            "spell_slots_restored": 0,
            "features_reset": [],
            "exhaustion_reduced": False
        }
        
        # Build update actions list
        update_actions = []
        
        # Check if character is a Warlock (for short rest spell slot recovery)
        character_class = character_data.get("class", "").lower()
        is_warlock = "warlock" in character_class
        
        # Handle HP restoration (long rest only in 5e)
        if rest_type == "long":
            current_hp = character_data.get("hitPoints", 0)
            max_hp = character_data.get("maxHitPoints", current_hp)
            
            if current_hp < max_hp:
                hp_diff = max_hp - current_hp
                update_actions.append(f"Restores {hp_diff} hit points (HP {current_hp} -> {max_hp})")
                results["hp_restored"] = hp_diff
        # Note: Short rest does NOT auto-heal - players must spend Hit Dice manually
        
        # Handle spell slots restoration
        spellcasting = character_data.get("spellcasting", {})
        spell_slots = spellcasting.get("spellSlots", {})
        
        if spell_slots:
            for level_key, slot_data in spell_slots.items():
                if isinstance(slot_data, dict):
                    current = slot_data.get("current", 0)
                    max_slots = slot_data.get("max", 0)
                    
                    should_restore_slots = False
                    if rest_type == "long":
                        # Long rest: all casters restore all spell slots
                        should_restore_slots = True
                    elif rest_type == "short" and is_warlock:
                        # Short rest: only Warlocks restore spell slots
                        should_restore_slots = True
                    
                    if should_restore_slots and current < max_slots:
                        slots_diff = max_slots - current
                        update_actions.append(f"Restores {slots_diff} level {level_key.replace('level', '')} spell slot(s)")
                        results["spell_slots_restored"] += slots_diff
        
        # Handle class features that refresh on rest
        class_features = character_data.get("classFeatures", [])
        for feature in class_features:
            usage = feature.get("usage")
            if usage and isinstance(usage, dict):
                refresh_on = usage.get("refreshOn", "")
                current_uses = usage.get("current", 0)
                max_uses = usage.get("max", 0)
                
                should_refresh = False
                if rest_type == "long" and refresh_on in ["longRest", "shortRest"]:
                    should_refresh = True
                elif rest_type == "short" and refresh_on == "shortRest":
                    should_refresh = True
                
                if should_refresh and current_uses < max_uses:
                    feature_name = feature.get("name", "Unknown")
                    update_actions.append(f"Refreshes {feature_name} usage ({current_uses} -> {max_uses})")
                    results["features_reset"].append(feature_name)
        
        # Handle exhaustion reduction (long rest only)
        if rest_type == "long":
            condition_affected = character_data.get("condition_affected", [])
            exhaustion_present = False
            
            # Schema: condition_affected is list[string], not list[dict]
            for condition in condition_affected:
                if isinstance(condition, str) and condition.lower().startswith("exhaustion"):
                    exhaustion_present = True
                    break
            
            if exhaustion_present:
                update_actions.append("Removes exhaustion condition")
                results["exhaustion_reduced"] = True
        
        # Execute updates via update_character_info
        if update_actions:
            # Combine all actions into a single update
            combined_action = f"{rest_type.capitalize()} rest: " + "; ".join(update_actions)
            
            # Call update_character_info which will handle the actual file update
            success = update_character_info(character_name, combined_action)
            
            if success:
                debug(f"REST: Successfully processed {rest_type} rest for {character_name}", 
                      category="character_updates")
                return results
            else:
                warning(f"REST: Failed to update character {character_name}", category="character_updates")
                return None
        else:
            # No updates needed - character already fully rested
            debug(f"REST: No updates needed for {character_name} (already fully rested)", 
                  category="character_updates")
            return results
            
    except Exception as e:
        error(f"REST: Error processing rest for {character_name}: {e}", 
              exception=e, category="character_updates")
        return None


def _format_rest_summary(rest_results: list, rest_type: str) -> str:
    """
    Format rest results into a readable summary message.
    
    Args:
        rest_results: List of rest result dicts from _process_character_rest
        rest_type: 'short' or 'long'
        
    Returns:
        Formatted summary string
    """
    if not rest_results:
        return f"[SYSTEM] {rest_type.capitalize()} rest completed (no changes)."
    
    total_hp = sum(r.get("hp_restored", 0) for r in rest_results)
    total_spell_slots = sum(r.get("spell_slots_restored", 0) for r in rest_results)
    total_features = sum(len(r.get("features_reset", [])) for r in rest_results)
    exhaustion_reduced = any(r.get("exhaustion_reduced", False) for r in rest_results)
    
    lines = [f"[SYSTEM] {rest_type.capitalize()} rest completed for {len(rest_results)} character(s):"]
    
    # Character details
    for result in rest_results:
        char_name = result.get("character", "Unknown")
        hp = result.get("hp_restored", 0)
        slots = result.get("spell_slots_restored", 0)
        features = result.get("features_reset", [])
        
        details = []
        if hp > 0:
            details.append(f"+{hp} HP")
        if slots > 0:
            details.append(f"+{slots} spell slots")
        if features:
            details.append(f"refreshed: {', '.join(features)}")
        
        if details:
            lines.append(f"  - {char_name}: {', '.join(details)}")
        else:
            lines.append(f"  - {char_name}: (no changes)")
    
    # Summary totals
    summary_parts = []
    if total_hp > 0:
        summary_parts.append(f"{total_hp} HP restored")
    if total_spell_slots > 0:
        summary_parts.append(f"{total_spell_slots} spell slots restored")
    if total_features > 0:
        summary_parts.append(f"{total_features} features refreshed")
    if exhaustion_reduced:
        summary_parts.append("exhaustion reduced")
    
    if summary_parts:
        lines.append(f"\nTotal: {', '.join(summary_parts)}.")
    
    return "\n".join(lines)


def move_background_npc(npc_name, context, current_location_hint=None, party_tracker_data=None):
    """
    AI-driven function to handle NPC movement/status changes with atomic safety
    
    Args:
        npc_name (str): Name of the NPC to move/update
        context (str): Narrative context explaining what happened to the NPC
        current_location_hint (str, optional): Hint about current location if not found automatically
        party_tracker_data (dict, optional): Party tracker data for module context
        
    Returns:
        bool: True if successful, False otherwise
    """
    import json
    import copy
    import shutil
    import os
    import time
    import threading
    from datetime import datetime
    from utils.file_operations import safe_write_json, safe_read_json
    
    debug(f"STATE_CHANGE: moveBackgroundNPC called for {npc_name}", category="npc_management")
    debug(f"AI_CALL: Context: {context}", category="npc_management")
    
    # File locking for atomic operations (similar to updateCharacterInfo)
    lock = threading.Lock()
    
    with lock:
        try:
            # Get module context
            if not party_tracker_data:
                party_tracker_data = safe_read_json("party_tracker.json")
                if not party_tracker_data:
                    print("ERROR: Could not load party tracker data")
                    return False
            
            module_name = party_tracker_data.get("module", "").replace(" ", "_")
            if not module_name:
                print("ERROR: No current module found in party tracker")
                return False
                
            path_manager = ModulePathManager(module_name)
            
            # Find the NPC in area files
            npc_location = find_npc_in_areas(npc_name, path_manager, current_location_hint)
            if not npc_location:
                print(f"ERROR: Could not find NPC '{npc_name}' in any location")
                return False
                
            area_file, location_id, npc_data = npc_location
            debug(f"VALIDATION: Found {npc_name} in {area_file} at location {location_id}", category="npc_management")
            
            # Load area data with backup
            area_data = safe_read_json(area_file)
            if not area_data:
                print(f"ERROR: Could not load area data from {area_file}")
                return False
                
            # Create backup
            backup_path = create_area_backup(area_file)
            if not backup_path:
                print("WARNING: Could not create backup, proceeding anyway")
            
            # Get party NPCs for validation
            party_npcs = party_tracker_data.get("partyNPCs", [])
            
            # Retry loop with fallback system
            ai_decision = None
            max_attempts = 5
            
            for attempt in range(1, max_attempts + 1):
                debug(f"AI_CALL: AI decision attempt {attempt}/{max_attempts}", category="npc_management")
                
                # Get AI decision on what to do with the NPC
                ai_decision = get_ai_npc_movement_decision(
                    npc_name, context, npc_data, area_data, location_id, module_name, party_npcs, attempt
                )
                
                if ai_decision:
                    # Validate the AI decision
                    validation_result = validate_npc_movement_decision(ai_decision, area_data, location_id, party_npcs)
                    if validation_result["valid"]:
                        info(f"SUCCESS: AI decision validated on attempt {attempt}", category="npc_management")
                        break
                    else:
                        warning(f"VALIDATION: AI decision failed on attempt {attempt}: {validation_result['reason']}", category="npc_management")
                        if attempt == max_attempts:
                            print("ERROR: Max attempts reached, AI could not generate valid decision")
                            return False
                        else:
                            # Add validation feedback to context for retry
                            context += f"\n\nPREVIOUS ATTEMPT FAILED: {validation_result['reason']}"
                else:
                    error(f"FAILURE: AI could not generate decision on attempt {attempt}", category="npc_management")
                    if attempt == max_attempts:
                        print("ERROR: Max attempts reached, AI could not determine appropriate action")
                        return False
            
            if not ai_decision:
                print("ERROR: AI could not determine appropriate action after all attempts")
                return False
                
            info(f"AI_CALL: Final AI decision: {ai_decision.get('action')} - {ai_decision.get('reasoning', 'No reasoning')}", category="npc_management")
            
            # Execute the AI decision with surgical updates
            success = execute_npc_movement_decision(ai_decision, area_data, location_id, npc_name, path_manager)
            
            if success:
                # Save updated area data
                if safe_write_json(area_file, area_data):
                    info(f"SUCCESS: Updated area file {area_file}", category="file_operations")
                    # Clean up old backups
                    cleanup_old_area_backups(area_file)
                    return True
                else:
                    print(f"ERROR: Failed to save updated area data")
                    # Restore from backup if save failed
                    if backup_path and os.path.exists(backup_path):
                        try:
                            shutil.copy2(backup_path, area_file)
                            warning("FILE_OP: Restored area file from backup due to save failure", category="file_operations")
                        except Exception as e:
                            print(f"ERROR: Could not restore from backup: {e}")
                    return False
            else:
                print("ERROR: Failed to execute NPC movement decision")
                return False
                
        except Exception as e:
            print(f"ERROR: Exception in move_background_npc: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def find_npc_in_areas(npc_name, path_manager, location_hint=None):
    """Find an NPC in area files, returning (area_file, location_id, npc_data)"""
    import glob
    import os
    from utils.file_operations import safe_read_json
    
    # Get all area files in the module, excluding backup files
    area_pattern = f"{path_manager.module_dir}/areas/*.json"
    all_files = glob.glob(area_pattern)
    
    # Filter out backup files (_BU.json) and backup copies (.backup_*)
    area_files = []
    for file_path in all_files:
        filename = os.path.basename(file_path)
        # Skip backup files
        if filename.endswith('_BU.json') or '.backup_' in filename:
            debug(f"FILE_OP: Skipping backup file: {filename}", category="file_operations")
            continue
        area_files.append(file_path)
    
    debug(f"FILE_OP: Searching {len(area_files)} active area files (excluded {len(all_files) - len(area_files)} backup files)", category="file_operations")
    
    for area_file in area_files:
        try:
            area_data = safe_read_json(area_file)
            if not area_data:
                continue
                
            # Search through all locations in this area
            for location in area_data.get("locations", []):
                location_id = location.get("locationId", "")
                
                # If location hint provided, check if this matches
                if location_hint and location_hint != location_id:
                    continue
                    
                # Search NPCs in this location
                for npc in location.get("npcs", []):
                    if npc.get("name", "").lower() == npc_name.lower():
                        return (area_file, location_id, npc)
                        
        except Exception as e:
            warning(f"FILE_OP: Could not search area file {area_file}: {e}", category="file_operations")
            continue
    
    return None

def get_ai_npc_movement_decision(npc_name, context, npc_data, area_data, location_id, module_name, party_npcs=None, attempt=1):
    """Use AI to determine what to do with the NPC based on context"""
    try:
        # Use factory for multi-provider support
        from utils.ai_client_factory import create_chat_client, get_chat_model_name, handle_provider_error
        client = create_chat_client()
        
        # Get provider-aware model
        model_name = get_chat_model_name()
        debug(f"Using AI model for NPC movement: {model_name}", category="ai_provider")
        
        # Get available locations for potential moves
        available_locations = []
        for location in area_data.get("locations", []):
            loc_id = location.get("locationId", "")
            loc_name = location.get("name", "")
            if loc_id and loc_name and loc_id != location_id:
                available_locations.append(f"{loc_id} ({loc_name})")
        
        # Check if this is a party NPC vs background NPC
        party_npc_names = [npc.get("name", "").lower() for npc in (party_npcs or [])]
        is_party_npc = npc_name.lower() in party_npc_names
        
        # Load and validate against location schema
        from jsonschema import validate, ValidationError
        import json
        
        try:
            with open("schemas/loca_schema.json", "r") as f:
                location_schema = json.load(f)
        except Exception as e:
            warning(f"FILE_OP: Could not load location schema: {e}", category="file_operations")
            location_schema = None
        
        system_prompt = f"""You are an expert 5th edition narrative manager specialized in NPC movement and status changes. Your job is to make intelligent decisions about background NPCs based on narrative context while maintaining strict game world consistency.

CRITICAL DISTINCTIONS:
- BACKGROUND NPCs: NPCs found in location files who are not traveling with the party
- PARTY NPCs: NPCs actively traveling with and assisting the party (managed separately)
- This action is ONLY for BACKGROUND NPCs - NPCs who exist in specific locations

CURRENT NPC CLASSIFICATION:
- {npc_name} is {'a PARTY NPC (ERROR - use updatePartyNPCs instead)' if is_party_npc else 'a BACKGROUND NPC (correct for this action)'}

AVAILABLE ACTIONS FOR BACKGROUND NPCs:
1. "remove" - Remove NPC from location entirely
   - Use for: Captured and taken elsewhere, fled permanently, left the area
   - Result: NPC disappears from location, may add location description update
   
2. "update_status" - Keep NPC in location but change their description  
   - Use for: Death, injury, status change, but NPC remains in place
   - Result: NPC description updated, location may be updated too
   
3. "move" - Move NPC to different location within same area
   - Use for: NPC relocated to another nearby location
   - Result: NPC moves between locations, descriptions updated

SCHEMA VALIDATION REQUIREMENTS:
All NPC objects must maintain this exact structure:
{{
  "name": "string (required)",
  "description": "string (required)", 
  "attitude": "string (required)"
}}

CONTEXT INFORMATION:
- Module: {module_name}
- Current Location: {location_id}
- Available Target Locations: {', '.join(available_locations) if available_locations else 'None (cannot use move action)'}
- Attempt: {attempt}/5

RESPONSE FORMAT (JSON only):
{{
  "action": "remove|update_status|move",
  "reasoning": "Brief explanation of decision based on narrative context",
  "newDescription": "Updated NPC description if action is update_status (required field, max 500 chars)",
  "newAttitude": "Updated attitude if action is update_status (required field)", 
  "newLocation": "Target location ID if action is move (must match available locations exactly)",
  "locationUpdate": "Brief addition to location description explaining change (optional, max 200 chars)"
}}

DECISION GUIDELINES WITH EXAMPLES:

CAPTURE SCENARIO:
Context: "Rusk was captured by the party and taken to Thornwood"
Decision: "remove" - Rusk is no longer at this location
Reasoning: "Captured and removed from area by party"

DEATH SCENARIO:  
Context: "The merchant was killed by bandits"
Decision: "update_status" - Body remains in location
New Description: "The merchant's lifeless body lies sprawled among scattered goods..."
New Attitude: "Dead"
Location Update: "Signs of violence and blood stain the ground"

RELOCATION SCENARIO:
Context: "Elen went to report to the watchtower"  
Decision: "move" - IF watchtower location exists in available locations
New Location: "WT01" (only if this exact ID exists)
Reasoning: "Moved to fulfill duty obligations"

INJURY SCENARIO:
Context: "The guard was wounded but survived the attack"
Decision: "update_status" - Guard stays but is injured
New Description: "A wounded guard with bandaged arms, still determined despite recent injuries..."
New Attitude: "Cautious but resilient"

IMPORTANT VALIDATION RULES:
- NEVER move party NPCs (they travel with the party automatically)
- ONLY use exact location IDs from the available locations list
- ALWAYS provide required fields: newDescription and newAttitude for update_status
- Keep descriptions realistic and immersive
- Maintain narrative consistency with established world"""

        user_prompt = f"""Background NPC Movement Decision Request:

NPC Name: {npc_name}
Current Description: {npc_data.get('description', 'No description available')}
Current Attitude: {npc_data.get('attitude', 'No attitude specified')}
Narrative Context: {context}
Current Location: {location_id}

Based on this narrative context, determine the most appropriate action for this background NPC. Consider the story implications and choose the action that best maintains narrative consistency.

Remember: This is a background NPC management action, not party NPC management."""

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
        except Exception as api_error:
            # Check if we should fallback to OpenAI
            error_result = handle_provider_error(api_error, context="NPC movement decision")
            if error_result['should_fallback']:
                warning(f"Falling back to OpenAI: {api_error}", category="ai_provider")
                fallback_client = create_chat_client(use_fallback=True)
                response = fallback_client.chat.completions.create(
                    model=config.NPC_INFO_UPDATE_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7
                )
            else:
                raise
        
        # Track token usage
        if USAGE_TRACKING_AVAILABLE:
            try:
                track_response(response)
            except:
                pass
        
        ai_response = response.choices[0].message.content.strip()
        debug(f"AI_CALL: Movement decision response: {ai_response}", category="ai_operations")
        
        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            error("AI_CALL: No valid JSON found in AI response", category="ai_operations")
            return None
            
    except Exception as e:
        error(f"AI_CALL: AI decision failed: {str(e)}", category="ai_operations")
        return None

def validate_npc_movement_decision(decision, area_data, location_id, party_npcs):
    """Validate AI decision against schema and game rules"""
    try:
        # Check required fields
        if not isinstance(decision, dict):
            return {"valid": False, "reason": "Decision must be a JSON object"}
            
        action = decision.get("action")
        if action not in ["remove", "update_status", "move"]:
            return {"valid": False, "reason": f"Invalid action '{action}'. Must be: remove, update_status, or move"}
        
        # Validate action-specific requirements
        if action == "update_status":
            if not decision.get("newDescription"):
                return {"valid": False, "reason": "update_status action requires newDescription field"}
            if not decision.get("newAttitude"):
                return {"valid": False, "reason": "update_status action requires newAttitude field"}
            
            # Check length limits
            if len(decision.get("newDescription", "")) > 500:
                return {"valid": False, "reason": "newDescription must be 500 characters or less"}
                
        elif action == "move":
            new_location = decision.get("newLocation")
            if not new_location:
                return {"valid": False, "reason": "move action requires newLocation field"}
                
            # Check if target location exists
            valid_locations = [loc.get("locationId") for loc in area_data.get("locations", [])]
            if new_location not in valid_locations:
                return {"valid": False, "reason": f"Target location '{new_location}' does not exist. Valid locations: {valid_locations}"}
        
        # Check location update length
        location_update = decision.get("locationUpdate", "")
        if location_update and len(location_update) > 200:
            return {"valid": False, "reason": "locationUpdate must be 200 characters or less"}
        
        # Schema validation - check NPC structure requirements
        if action == "update_status":
            # Simulate the NPC object that would be created
            test_npc = {
                "name": "test",
                "description": decision.get("newDescription"),
                "attitude": decision.get("newAttitude")
            }
            
            # Basic validation
            for field in ["name", "description", "attitude"]:
                if not test_npc.get(field):
                    return {"valid": False, "reason": f"NPC object missing required field: {field}"}
                if not isinstance(test_npc[field], str):
                    return {"valid": False, "reason": f"NPC field '{field}' must be a string"}
        
        return {"valid": True, "reason": "Decision validated successfully"}
        
    except Exception as e:
        return {"valid": False, "reason": f"Validation error: {str(e)}"}

def execute_npc_movement_decision(decision, area_data, location_id, npc_name, path_manager):
    """Execute the AI's decision with surgical updates to area data"""
    try:
        action = decision.get("action")
        
        # Find the location and NPC in area data
        target_location = None
        npc_index = None
        
        for location in area_data.get("locations", []):
            if location.get("locationId") == location_id:
                target_location = location
                # Find NPC index
                for i, npc in enumerate(location.get("npcs", [])):
                    if npc.get("name", "").lower() == npc_name.lower():
                        npc_index = i
                        break
                break
        
        if not target_location or npc_index is None:
            error("VALIDATION: Could not find location or NPC in area data", category="npc_management")
            return False
        
        if action == "remove":
            # Remove NPC from location
            target_location["npcs"].pop(npc_index)
            info(f"STATE_CHANGE: Removed {npc_name} from {location_id}", category="npc_management")
            
            # Update location description if provided
            location_update = decision.get("locationUpdate")
            if location_update:
                current_desc = target_location.get("description", "")
                target_location["description"] = f"{current_desc} {location_update}".strip()
                
        elif action == "update_status":
            # Update NPC description and attitude
            new_description = decision.get("newDescription")
            new_attitude = decision.get("newAttitude")
            
            if new_description:
                target_location["npcs"][npc_index]["description"] = new_description
                info(f"STATE_CHANGE: Updated description for {npc_name}", category="npc_management")
            
            if new_attitude:
                target_location["npcs"][npc_index]["attitude"] = new_attitude
                info(f"STATE_CHANGE: Updated attitude for {npc_name}", category="npc_management")
                
            # Update location description if provided
            location_update = decision.get("locationUpdate")
            if location_update:
                current_desc = target_location.get("description", "")
                target_location["description"] = f"{current_desc} {location_update}".strip()
                    
        elif action == "move":
            # Move NPC to different location
            new_location_id = decision.get("newLocation")
            if not new_location_id:
                error("VALIDATION: Move action specified but no target location provided", category="npc_management")
                return False
                
            # Find target location
            target_new_location = None
            for location in area_data.get("locations", []):
                if location.get("locationId") == new_location_id:
                    target_new_location = location
                    break
                    
            if not target_new_location:
                error(f"VALIDATION: Target location {new_location_id} not found", category="npc_management")
                return False
                
            # Move NPC
            npc_to_move = target_location["npcs"].pop(npc_index)
            target_new_location["npcs"].append(npc_to_move)
            info(f"STATE_CHANGE: Moved {npc_name} from {location_id} to {new_location_id}", category="npc_management")
            
            # Update both location descriptions if provided
            location_update = decision.get("locationUpdate")
            if location_update:
                # Update source location
                current_desc = target_location.get("description", "")
                target_location["description"] = f"{current_desc} {location_update}".strip()
        
        else:
            error(f"VALIDATION: Unknown action: {action}", category="npc_management")
            return False
            
        return True
        
    except Exception as e:
        error(f"FAILURE: Failed to execute decision: {str(e)}", category="npc_management")
        return False

def create_area_backup(area_file):
    """Create timestamped backup of area file"""
    import shutil
    import os
    from datetime import datetime
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{area_file}.backup_npc_move_{timestamp}"
        shutil.copy2(area_file, backup_name)
        debug(f"FILE_OP: Created area backup: {os.path.basename(backup_name)}", category="file_operations")
        return backup_name
    except Exception as e:
        error(f"FILE_OP: Could not create area backup: {e}", category="file_operations")
        return None

def cleanup_old_area_backups(area_file, max_backups=5):
    """Clean up old area backup files"""
    import os
    
    try:
        directory = os.path.dirname(area_file)
        base_name = os.path.basename(area_file)
        
        backup_files = []
        for file in os.listdir(directory):
            if file.startswith(f"{base_name}.backup_npc_move_") and file.endswith(".json"):
                backup_path = os.path.join(directory, file)
                mtime = os.path.getmtime(backup_path)
                backup_files.append((mtime, backup_path))
        
        # Sort by modification time (newest first) and remove old ones
        backup_files.sort(reverse=True)
        if len(backup_files) > max_backups:
            for _, old_backup in backup_files[max_backups:]:
                try:
                    os.remove(old_backup)
                    debug(f"FILE_OP: Removed old backup: {os.path.basename(old_backup)}", category="file_operations")
                except Exception as e:
                    warning(f"FILE_OP: Could not remove old backup: {e}", category="file_operations")
                    
    except Exception as e:
        warning(f"FILE_OP: Backup cleanup failed: {e}", category="file_operations")
