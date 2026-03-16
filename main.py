# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Game Loop Controller
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# MAIN.PY - GAME LOOP CONTROLLER
# ============================================================================
#
# ARCHITECTURE ROLE: Primary Controller in MVC Pattern
#
# This is the central orchestrator of the 5th edition Dungeon Master system, implementing
# the main game loop and coordinating all subsystems. It follows the Command Pattern
# where every game interaction is processed as a discrete action.
#
# KEY RESPONSIBILITIES:
# - Game session management and main loop execution
# - Action parsing and routing to appropriate handlers
# - AI response validation with NPC codex integration
# - Conversation history management and context compression
# - Module transition processing with timeline preservation
# - Real-time user feedback and status reporting
# - DM Note generation for authoritative current game state
# - AI-powered NPC validation system coordination
#
# DM NOTE DESIGN PHILOSOPHY:
# - AUTHORITATIVE SOURCE: DM Note contains current, dynamic game state
# - REAL-TIME DATA: Always reflects most up-to-date character information
# - AI CLARITY: Single source of truth prevents conflicting information
# - DYNAMIC FOCUS: HP, spell slots, conditions, and active effects
#
# DM NOTE CONTENT STRATEGY:
# Generated content includes:
#   - Current party status (HP, level, XP, spell slots)
#   - Active location and environmental conditions
#   - Time, date, and world state information
#   - Dynamic character states (not static reference data)
#
# INFORMATION ARCHITECTURE:
# - DM NOTES: Current state, real-time data, authoritative information
# - SYSTEM MESSAGES: Static character reference (conversation_utils.py)
# - SEPARATION PRINCIPLE: Prevents AI confusion from version conflicts
#
# ARCHITECTURAL INTEGRATION:
# - Coordinates with dm_wrapper.py for AI interactions
# - Uses action_handler.py for command processing
# - Manages state through party_tracker.json updates
# - Validates responses using multiple AI models with NPC codex verification
# - Integrates with ModulePathManager for file operations
# - Provides dynamic data to conversation_utils.py for context management
# - Leverages npc_codex_generator.py for AI-powered character validation
#
# DATA FLOW:
# User Input -> Action Processing -> AI Response -> NPC Codex Validation -> State Update -> DM Note Refresh
#
# This file embodies our "AI-First Design with Human Safety Nets" principle
# by combining powerful AI capabilities with rigorous validation layers and
# clear information architecture that prevents AI confusion.
# ============================================================================

import json
import subprocess
import os
import re
import sys
import codecs
import glob
import time
from openai import OpenAI
from datetime import datetime, timedelta
from termcolor import colored
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import encoding utilities
from utils.encoding_utils import (
    sanitize_text,
    sanitize_dict,
    safe_json_load,
    safe_json_dump,
    fix_corrupted_location_name,
    setup_utf8_console
)
from utils.session_cleanup import cleanup_history_files, remove_stale_resume_recaps

# Import token tracking
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass

# Import other necessary modules (config is now patched)
from core.managers.combat_manager import run_combat_simulation
from updates.plot_update import update_plot
from utils.player_stats import get_player_stat
from updates.update_world_time import update_world_time
from core.ai.conversation_utils import update_conversation_history, update_character_data
from updates.update_character_info import update_character_info, normalize_character_name
from core.managers.level_up_manager import LevelUpSession # Add this line
from core.ai.incremental_compression import IncrementalLocationCompressor

# TABLETOP MODE: Import character creator for narrative-aware PC creation
from utils.character_creator import (
    is_creation_mode_active,
    get_party_level,
    calculate_starting_wealth,
    generate_ambiguous_transition,
    restore_conversation_history,
    abort_character_creation_session,
    finalize_character_creation_candidate,
    persist_dm_created_character,
    CHARACTER_CREATION_MARKER,
    recover_poisoned_creation_session_on_startup,
)
from utils import pc_manager
from utils.save_roll_contract import calculate_concentration_dc

# Import new manager modules
from core.managers import location_manager
from utils.location_path_finder import LocationGraph
from core.ai import action_handler
from core.ai.cumulative_summary import (
    generate_enhanced_adventure_summary,
    update_journal_with_summary,
    compress_conversation_history_on_transition,
    check_and_compact_missing_summaries
)
from core.managers.status_manager import (
    status_manager, status_ready, status_processing_ai, status_validating,
    status_retrying, status_transitioning_location, status_generating_summary,
    status_updating_journal, status_compressing_history, status_updating_character,
    status_updating_party, status_updating_plot, status_advancing_time, status_saving
)

# Import atomic file operations
from utils.file_operations import safe_write_json, safe_read_json
from utils.module_path_manager import ModulePathManager
from core.managers.campaign_manager import CampaignManager
from core.ai.inventory_context_integration import build_enhanced_dm_note

# Import training data collection
# from simple_training_collector import log_complete_interaction  # DISABLED
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name(__name__)

# Import model configurations from config.py
from config import (
    OPENAI_API_KEY,
    DM_MAIN_MODEL,
    DM_SUMMARIZATION_MODEL,
    DM_VALIDATION_MODEL
)

# Initialize AI client using factory (supports OpenAI and OpenRouter)
from utils.ai_client_factory import create_chat_client, reset_fallback_status, get_chat_model_name, handle_provider_error
reset_fallback_status()  # Reset fallback tracking at module load
client = create_chat_client()

# LocationGraph will be initialized inside main() after modules are integrated
location_graph = None

# Temperature Configuration (remains the same)
TEMPERATURE = 0.8

SOLID_GREEN = "\033[38;2;0;180;0m"  # Slightly darker solid green for player name
LIGHT_OFF_GREEN = "\033[38;2;100;180;100m"  # More muted light green for stats
GOLD = "\033[38;2;255;215;0m"  # Gold color for status messages
RESET_COLOR = "\033[0m"

json_file = "modules/conversation_history/conversation_history.json"

needs_conversation_history_update = False
should_inject_creation_prompt = False  # Global flag for module creation prompt injection

# Message combination system state variables
held_response = None
awaiting_combat_resolution = False

# Status display configuration
current_status_line = None


def get_request_roll_concentration_dc(damage_taken: int) -> int:
    """Return deterministic concentration DC for requestRoll scaffolding."""
    return calculate_concentration_dc(damage_taken)

def display_status(message):
    """Display status message above the command prompt"""
    global current_status_line
    # Clear previous status line if exists
    if current_status_line is not None:
        print(f"\r{' ' * len(current_status_line)}\r", end='', flush=True)
    # Display new status
    status_display = f"{GOLD}[{message}]{RESET_COLOR}"
    print(f"\r{status_display}", flush=True)
    current_status_line = status_display

# Set up status callback
def status_callback(message, is_processing):
    """Callback for status manager to display status updates"""
    if is_processing:
        display_status(message)
    else:
        # Clear status when ready
        global current_status_line
        if current_status_line is not None:
            print(f"\r{' ' * len(current_status_line)}\r", end='', flush=True)
            current_status_line = None

# Register the callback
status_manager.set_callback(status_callback)

# Note: Old summarization functions removed - using cumulative summary system instead

# Add this new function near the top of the file
def exit_game():
    print("Fond farewell until we meet again!")
    exit()

def check_and_inject_return_message(conversation_history, is_combat_active=False):
    """
    Checks if a startup recap message needs to be injected at startup.

    Args:
        conversation_history: List of conversation messages
        is_combat_active: Boolean indicating if combat is currently active (prevents duplicate injection)

    Returns:
        Tuple of (updated_conversation_history, was_injected)
    """
    # Skip if no conversation history (first startup)
    if not conversation_history:
        debug("STATE_CHANGE: No conversation history found, skipping startup recap message injection", category="session_management")
        return conversation_history, False

    # Check if there are any user messages (game has been played before)
    user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
    if not user_messages:
        debug("STATE_CHANGE: No user messages found, skipping startup recap message injection", category="session_management")
        return conversation_history, False

    # TABLETOP MODE: Shared stale recap cleanup (idempotent guard)
    # Primary cleanup runs in startup path for both history files.
    cleaned_history, removed_count = remove_stale_resume_recaps(conversation_history)
    if removed_count > 0:
        conversation_history[:] = cleaned_history
        debug(f"STATE_CHANGE: Removed {removed_count} stale recap messages", category="session_management")

    # Get the last message
    last_message = conversation_history[-1] if conversation_history else None
    if not last_message:
        debug("STATE_CHANGE: No last message found, skipping startup recap message injection", category="session_management")
        return conversation_history, False

    # Check if last message is already the startup recap control message
    last_content = last_message.get("content", "")
    if "SESSION RESUME RECAP ONLY" in last_content:
        debug("STATE_CHANGE: Startup recap message already present, skipping injection", category="session_management")
        return conversation_history, False

    # Check if we're resuming from combat - if so, inject a different tracking message
    if is_combat_active:
        # Combat manager will handle its own resume message, so we just add a tracking marker
        tracking_message = {
            "role": "user",
            "content": "[SYSTEM: Combat was interrupted and is being resumed from crash]"
        }
        conversation_history.append(tracking_message)
        debug("STATE_CHANGE: Added combat resume tracking message", category="session_management")
        
        # Also add an assistant acknowledgment to mark the recovery point
        recovery_marker = {
            "role": "assistant",
            "content": "[SYSTEM: Combat recovery initiated - continuing from last known state]"
        }
        conversation_history.append(recovery_marker)
        debug("STATE_CHANGE: Added combat recovery marker", category="session_management")
        return conversation_history, True
    
    # Normal (non-combat) startup recap injection
    return_message = {
        "role": "user",
        "content": "Dungeon Master Note: SESSION RESUME RECAP ONLY. Provide a brief in-world recap so the table can continue immediately from current state. The party is already present at the current location. Do NOT narrate anyone returning, arriving, or being welcomed back. Do NOT include reunion dialogue, relief beats, or newcomer framing (for example, 'wanderer returns'). Summarize only: (1) where the party is, (2) what happened most recently, and (3) the most immediate unresolved objective or threat. Keep it concise (3-5 sentences), atmospheric, and grounded in existing conversation history and current world state. End with one forward prompt for action. IMPORTANT: Narration-only recap; do NOT emit gameplay actions. IMPORTANT: Do NOT use transitionLocation action - the party is already at their current location."
    }
    conversation_history.append(return_message)
    debug("STATE_CHANGE: Injected startup recap message at startup", category="session_management")
    return conversation_history, True

def generate_arrival_narration(departure_narration, party_tracker_data, conversation_history):
    """
    Takes the departure narration and generates a seamless arrival narration.
    """
    debug("STATE_CHANGE: Generating cinematic arrival narration...", category="narrative_generation")
    
    # Get details for the new location from the (now updated) party tracker
    new_location_name = party_tracker_data["worldConditions"]["currentLocation"]
    new_area_name = party_tracker_data["worldConditions"]["currentArea"]

    # Construct the special prompt
    arrival_prompt = f"""
    You are a master storyteller. The following text describes the party's departure from one location. Your task is to write a seamless, cinematic, and immersive description of their arrival at their destination, "{new_location_name}" in the "{new_area_name}" area.

    The arrival narration should:
    1.  Feel like a direct continuation of the departure text.
    2.  Focus on sensory details (sights, sounds, smells) of the new location.
    3.  Set the mood and atmosphere of the new environment.
    4.  Incorporate the reactions or immediate impressions of the player characters and NPCs.
    5.  Do not repeat any information from the departure text. Just write the arrival part.

    DEPARTURE NARRATION (for context):
    ---
    {departure_narration}
    ---

    Now, write the arrival narration.
    """
    
    # We can also add the most recent non-system messages for better context
    recent_context = [msg for msg in conversation_history if msg.get("role") != "system"][-5:]

    narration_request_messages = [
        {"role": "system", "content": "You are a master storyteller specializing in immersive, cinematic narrations."},
        *recent_context,
        {"role": "user", "content": arrival_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model=DM_MAIN_MODEL,  # Use the main model for high-quality narration
            temperature=TEMPERATURE,
            messages=narration_request_messages
        )

        # Log API call to master log
        try:
            from utils.api_logger import log_api_call
            log_api_call("narration_generator", narration_request_messages, response,
                        metadata={"temperature": TEMPERATURE, "context": "module_transition_arrival"})
        except Exception as e:
            print(f"[API_LOG] Warning: Failed to log narration call: {e}")

        # Track token usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(response, context={'endpoint': 'narration_generator', 'purpose': 'generate_narrative_summary'})
            except:
                pass
        
        arrival_text = response.choices[0].message.content.strip()
        
        # Sometimes the AI will still wrap its response in a JSON object. We need to handle that.
        try:
            parsed_json = json.loads(arrival_text)
            arrival_text = parsed_json.get("narration", arrival_text)
        except json.JSONDecodeError:
            # It's just plain text, which is what we want.
            pass

        debug("SUCCESS: Arrival narration generated successfully.", category="narrative_generation")
        return sanitize_text(arrival_text)
    except Exception as e:
        error(f"FAILURE: Failed to generate arrival narration", exception=e, category="narrative_generation")
        return f"(The journey to {new_location_name} is uneventful.)" # Fallback text


# <--- NEW FUNCTION to blend the departure and arrival narrations --->
def generate_seamless_transition_narration(departure_narration, arrival_narration):
    """
    Takes two separate narration blocks (departure and arrival) and uses an AI
    to rewrite them into a single, cohesive, and seamless narrative.
    """
    debug("STATE_CHANGE: Blending departure and arrival narrations into a seamless whole...", category="narrative_generation")

    # If either part is empty, just return the other part to avoid weird API calls.
    if not departure_narration:
        return arrival_narration
    if not arrival_narration:
        return departure_narration

    stitching_prompt = f"""
You are a master storyteller and narrative editor. The following two text blocks describe a party's departure from one place and their subsequent arrival at another. The transition between them is abrupt because they were generated separately.

Your task is to rewrite them into a single, cohesive, and cinematic narration.
- Preserve all key details, sensory information, and character actions from both parts.
- Smooth out the transition so it feels like one continuous story beat.
- Enhance the prose where possible to create a more engaging and atmospheric experience.
- Do not add new plot points or actions; your role is to refine the existing narrative flow.

DEPARTURE NARRATION:
---
{departure_narration}
---

ARRIVAL NARRATION:
---
{arrival_narration}
---

Now, provide the rewritten, seamless narration.
"""

    try:
        response = client.chat.completions.create(
            model=DM_MAIN_MODEL,  # Use the main model for high-quality writing
            temperature=TEMPERATURE,
            messages=[
                {"role": "system", "content": "You are a master storyteller and editor, skilled at weaving separate narrative fragments into a single, seamless, and immersive piece of prose."},
                {"role": "user", "content": stitching_prompt}
            ]
        )

        # Log API call to master log
        try:
            from utils.api_logger import log_api_call
            log_api_call("narrative_stitcher", [
                {"role": "system", "content": "You are a master storyteller and editor, skilled at weaving separate narrative fragments into a single, seamless, and immersive piece of prose."},
                {"role": "user", "content": stitching_prompt}
            ], response, metadata={"temperature": TEMPERATURE, "context": "module_transition_stitch"})
        except Exception as e:
            print(f"[API_LOG] Warning: Failed to log stitcher call: {e}")

        # Track token usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(response, context={'endpoint': 'narrative_stitching', 'purpose': 'stitch_location_descriptions'})
            except:
                pass
        
        seamless_narration = response.choices[0].message.content.strip()
        debug("SUCCESS: Seamless narration generated successfully.", category="narrative_generation")
        return sanitize_text(seamless_narration)
    except Exception as e:
        error(f"FAILURE: Failed to generate seamless transition narration", exception=e, category="narrative_generation")
        # Fallback to simple concatenation if the API call fails
        debug("STATE_CHANGE: Falling back to simple concatenation.", category="narrative_generation")
        return f"{departure_narration}\n\n{arrival_narration}"

# Message combination system helper functions
def detect_create_encounter(parsed_data):
    """Check if the parsed response contains a createEncounter action"""
    if not isinstance(parsed_data, dict) or "actions" not in parsed_data:
        return False
    
    actions = parsed_data.get("actions", [])
    for action in actions:
        if isinstance(action, dict) and action.get("action") == "createEncounter":
            return True
    return False

def combine_messages(first_response, second_response):
    """Combine two JSON responses into a single cohesive message"""
    try:
        # Parse both responses
        first_data = json.loads(first_response)
        second_data = json.loads(second_response)
        
        # Combine narrations
        first_narration = first_data.get("narration", "")
        second_narration = second_data.get("narration", "")
        combined_narration = f"{first_narration}\n\n{second_narration}"
        
        # Combine actions
        first_actions = first_data.get("actions", [])
        second_actions = second_data.get("actions", [])
        combined_actions = first_actions + second_actions
        
        # Create combined response
        combined_data = {
            "narration": combined_narration,
            "actions": combined_actions
        }
        
        return json.dumps(combined_data, indent=2)
        
    except json.JSONDecodeError as e:
        error(f"FAILURE: Error combining messages", exception=e, category="narrative_generation")
        # Fallback: return second response if combination fails
        return second_response
    except Exception as e:
        error(f"FAILURE: Unexpected error combining messages", exception=e, category="narrative_generation")
        return second_response

def clear_message_buffer():
    """Reset the message buffering state"""
    global held_response, awaiting_combat_resolution
    held_response = None
    awaiting_combat_resolution = False

def get_npc_stat(npc_name, stat_name, time_estimate):
    debug(f"STATE_CHANGE: get_npc_stat called for {npc_name}, stat: {stat_name}", category="npc_management")
    # Load party tracker to get correct module
    party_data = load_json_file("party_tracker.json")
    module_name = party_data.get("module", "").replace(" ", "_")
    path_manager = ModulePathManager(module_name)
    npc_file = path_manager.get_character_path(npc_name)
    try:
        with open(npc_file, "r", encoding="utf-8") as file:
            npc_stats = json.load(file)
    except FileNotFoundError:
        error(f"FAILURE: {npc_file} not found. Stat retrieval failed.", category="file_operations")
        return "NPC stat not found"
    except json.JSONDecodeError:
        error(f"FAILURE: {npc_file} has an invalid JSON format. Stat retrieval failed.", category="file_operations")
        return "NPC stat not found"

    stat_value = None
    modifier_value = None

    if npc_stats:
        if stat_name.lower() in npc_stats["abilities"]:
            stat_value = npc_stats["abilities"][stat_name.lower()]
            modifier_value = (stat_value - 10) // 2

    if stat_value is not None and modifier_value is not None:
        # Update the world time based on the time estimate (in minutes)
        update_world_time(time_estimate)

        return f"NPC's {stat_name.capitalize()}: {stat_value} (Modifier: {modifier_value})"
    else:
        return "NPC stat not found"

def parse_json_safely(text):
    # First, try to parse as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract from code block
    json_content = extract_json_from_codeblock(text)
    try:
        return json.loads(json_content)
    except json.JSONDecodeError:
        pass

    # If all else fails, try to find any JSON-like structure
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError:
        pass

    # If we still can't parse it, raise an exception
    raise json.JSONDecodeError("Unable to parse JSON from the given text", text, 0)

def create_module_validation_context(party_tracker_data, path_manager):
    """Create module data context for validation system to check location/NPC references"""
    try:
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
        current_module = party_tracker_data.get("module", "Unknown")
        
        validation_context = f"MODULE VALIDATION DATA:\nCurrent Module: {current_module}\nCurrent Area: {current_area_id}\nCurrent Location: {current_location_id}\n\n"
        
        # NPC context now dynamically built in validate_dm_response function
        # No longer loading static NPC compendium here
        
        # Get all valid locations in current area and location-specific NPCs
        area_file = path_manager.get_area_path(current_area_id)
        current_location_npcs = []
        area_locations_with_npcs = {}
        
        try:
            with open(area_file, "r", encoding="utf-8") as file:
                area_data = json.load(file)
            
            valid_location_ids = []
            for location in area_data.get("locations", []):
                loc_id = location.get("locationId", "")
                loc_name = location.get("name", "")
                if loc_id:
                    valid_location_ids.append(loc_id)
                    
                    # Track NPCs by location
                    location_npcs = [npc.get("name") for npc in location.get("npcs", []) if npc.get("name")]
                    if location_npcs:
                        area_locations_with_npcs[loc_id] = location_npcs
                    
                    # Collect NPCs for current location
                    if loc_id == current_location_id:
                        current_location_npcs = location_npcs.copy()  # Start with location NPCs
            
            # Add party NPCs to current location (they travel with the party)
            party_npcs = party_tracker_data.get("partyNPCs", [])
            for party_npc in party_npcs:
                npc_name = party_npc.get("name", "")
                if npc_name and npc_name not in current_location_npcs:
                    current_location_npcs.append(npc_name)
            
            # Just list the location IDs for current area since full details are below
            validation_context += f"Current area ({current_area_id}) location IDs: "
            if valid_location_ids:
                validation_context += ", ".join(valid_location_ids)
            else:
                validation_context += "None found"
            validation_context += "\n\n"
                
        except (FileNotFoundError, json.JSONDecodeError):
            validation_context += f"ERROR: Could not load area data for {current_area_id}\n\n"
        
        # Add ALL accessible locations from the entire module using LocationGraph
        try:
            all_accessible_locations = []
            areas_included = set()
            
            # Get all locations from the location graph
            for loc_id, node_info in location_graph.nodes.items():
                area_id = node_info.get('area_id', '')
                location_name = node_info.get('location_name', '')
                if area_id and location_name:
                    areas_included.add(area_id)
                    all_accessible_locations.append(f"{loc_id} ({location_name}) in area {area_id}")
            
            validation_context += f"ALL ACCESSIBLE LOCATIONS (across {len(areas_included)} areas):\n"
            if all_accessible_locations:
                # Sort by area for clarity
                all_accessible_locations.sort()
                # Include all locations since we only have ~78 total which is manageable
                validation_context += "\n".join([f"- {loc}" for loc in all_accessible_locations])
            else:
                validation_context += "- No locations found in location graph"
            validation_context += "\n\n"
            validation_context += "MULTI-AREA TRAVEL NOTE: transitionLocation can target ANY accessible location above, not just those in the current area.\n\n"
                
        except Exception as e:
            validation_context += f"ERROR: Could not load location graph data: {str(e)}\n\n"
        
        # Get all valid NPCs from ALL module codexes
        try:
            valid_npcs = []
            
            # Import all module codexes and merge their NPCs
            modules_dir = "modules"
            if os.path.exists(modules_dir):
                for item in os.listdir(modules_dir):
                    module_path = os.path.join(modules_dir, item)
                    if (os.path.isdir(module_path) and 
                        not item.startswith('.') and 
                        item not in ['campaign_archives', 'campaign_summaries', 'conversation_history', 'encounters', 'logs', 'backups']):
                        
                        # Check if this module has a codex file
                        codex_file = os.path.join(module_path, "npc_codex.json")
                        if os.path.exists(codex_file):
                            try:
                                with open(codex_file, "r", encoding="utf-8") as f:
                                    codex = json.load(f)
                                
                                for npc_entry in codex.get("npcs", []):
                                    if isinstance(npc_entry, dict) and "name" in npc_entry:
                                        npc_name = npc_entry["name"]
                                        source = npc_entry.get("source", "unknown")
                                        valid_npcs.append(f"{npc_name} (Module: {item})")
                            except Exception as e:
                                continue
            
            # DEBUG: Print what NPCs are being passed to validator
            # print("\n" + "="*60)
            # print("DEBUG: NPC VALIDATION CONTEXT BEING CREATED")
            # print("="*60)
            # print(f"Total NPCs found across all modules: {len(valid_npcs)}")
            # if valid_npcs:
            #     print("NPCs being passed to validator:")
            #     for npc in valid_npcs:
            #         print(f"  - {npc}")
            #         if "Kira" in npc:
            #             print(f"    ^^^ FOUND KIRA: {npc}")
            # else:
            #     print("WARNING: NO NPCs found in any module codex!")
            # print("="*60)
            # print()
            
            # Add party members to the valid characters list
            validation_context += "VALID CHARACTERS (Party Members and All Module NPCs):\n"
            
            # First add party members from party tracker
            party_members = party_tracker_data.get("partyMembers", [])
            for member in party_members:
                validation_context += f"- {member} (party member)\n"
            
            # Then add NPCs from codexes
            if valid_npcs:
                validation_context += "\n".join([f"- {npc}" for npc in valid_npcs])
            else:
                validation_context += "- No NPCs found in module codexes"
                
        except Exception as e:
            # Fallback to original character file method if codex fails
            # print(f"DEBUG: Exception in NPC codex loading: {e}")
            # print(f"DEBUG: Exception type: {type(e)}")
            # print("DEBUG: Falling back to character files method")
            # print(f"WARNING: NPC codex failed, falling back to character files: {e}")
            character_files = glob.glob(f"{path_manager.module_dir}/characters/*.json")
            
            valid_npcs = []
            for char_file in character_files:
                try:
                    with open(char_file, "r", encoding="utf-8") as file:
                        char_data = json.load(file)
                    char_name = char_data.get("name", "")
                    char_type = char_data.get("character_type", "unknown")
                    if char_name:
                        valid_npcs.append(f"{char_name} ({char_type})")
                except (json.JSONDecodeError, KeyError):
                    continue
            
            validation_context += "VALID CHARACTERS (Party Members and Module Characters):\n"
            
            # First add party members from party tracker
            party_members = party_tracker_data.get("partyMembers", [])
            for member in party_members:
                validation_context += f"- {member} (party member)\n"
            
            # Then add NPCs from character files
            if valid_npcs:
                validation_context += "\n".join([f"- {npc}" for npc in valid_npcs])
            else:
                validation_context += "- No character files found"
        
        # Add location-aware NPC context
        validation_context += f"\n\nLOCATION-AWARE NPC VALIDATION:\n"
        validation_context += f"Current Location: {current_location_id}\n"
        
        if current_location_npcs:
            validation_context += f"NPCs PRESENT at current location ({current_location_id}):\n"
            validation_context += "\n".join([f"- {npc}" for npc in current_location_npcs])
            validation_context += "\n\n"
        else:
            validation_context += f"NO NPCs present at current location ({current_location_id})\n\n"
        
        if area_locations_with_npcs:
            validation_context += "NPCs at OTHER locations in this area:\n"
            for loc_id, npcs in area_locations_with_npcs.items():
                if loc_id != current_location_id:  # Don't repeat current location
                    validation_context += f"  {loc_id}: {', '.join(npcs)}\n"
            validation_context += "\n"
        
        validation_context += """ENHANCED VALIDATION RULES:
1. For interactions happening AT the current location, ONLY use NPCs from the "PRESENT at current location" list
2. For references to NPCs at OTHER locations, they must exist in the "NPCs at OTHER locations" or module character lists
3. NEVER create new NPCs - all names must exist in the provided lists
4. If an NPC is referenced incorrectly, suggest the CORRECT NPC from the current location list
5. NPCs cannot be in multiple locations simultaneously - verify location consistency

CHARACTER NAME RULES FOR updateCharacterInfo:
- ALWAYS use the FULL character name exactly as it appears in the party tracker or NPC lists
- For party NPCs, use their complete name (e.g., "Scout Kira" not "kira", "Sir Aldric" not "aldric")
- For party members, use the exact name from partyMembers list
- NEVER shorten or modify character names in action parameters
- If a character has a title or descriptor, it MUST be included (e.g., "Scout Kira", "Knight Commander Marcus")

CRITICAL: If validation fails due to wrong NPC for location, provide specific correction using NPCs actually present at the current location."""
        
        return validation_context
        
    except Exception as e:
        # print(f"DEBUG: MAJOR EXCEPTION in create_module_validation_context: {e}")
        # print(f"DEBUG: Exception type: {type(e)}")
        # import traceback
        # print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return f"MODULE VALIDATION DATA: Error loading module data - {str(e)}"

def normalize_character_names_in_response(response_text, party_tracker_data):
    """
    Normalize NPC names in updateCharacterInfo and updatePartyNPCs actions before validation.
    Handles name variations like "Kira" → "Scout Kira", "Ranger Kira" → "Scout Kira"

    Returns:
        (normalized_response, message) or (None, error_message) if unresolvable
    """
    from utils.npc_name_normalizer import normalize_npc_name_for_action

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        # If it's not valid JSON, skip normalization
        return response_text, "JSON invalid - skipping NPC normalization"

    if 'actions' not in parsed or not isinstance(parsed['actions'], list):
        # No actions to normalize
        return response_text, "No actions to normalize"

    corrections = []
    rejections = []

    for i, action in enumerate(parsed['actions']):
        if not isinstance(action, dict):
            continue

        action_type = action.get('action')

        # Normalize updateCharacterInfo actions
        if action_type == 'updateCharacterInfo':
            params = action.get('parameters', {})
            original_name = params.get('characterName')

            if original_name:
                print(f"[NPC_NORM] Checking updateCharacterInfo action with characterName='{original_name}'")

                # Try to normalize the name
                normalized_name, match_type = normalize_npc_name_for_action(
                    original_name, party_tracker_data, debug_print=True
                )

                if normalized_name is None:
                    # Could not resolve name - reject
                    rejections.append(f"Action {i+1}: '{original_name}' not in party tracker")
                    print(f"[NPC_NORM] REJECT: '{original_name}' cannot be matched to party tracker")

                elif normalized_name != original_name:
                    # Name was normalized
                    params['characterName'] = normalized_name
                    corrections.append(f"Action {i+1}: '{original_name}' → '{normalized_name}'")
                    print(f"[NPC_NORM] CORRECTED: '{original_name}' → '{normalized_name}'")

                else:
                    # Name was already correct
                    print(f"[NPC_NORM] OK: '{original_name}' matches party tracker")

        # TABLETOP MODE: Normalize updatePartyNPCs actions
        elif action_type == 'updatePartyNPCs':
            params = action.get('parameters', {})
            npc_param = params.get('npc')

            if npc_param:
                # npc can be a dict with 'name' key (canonical form)
                if isinstance(npc_param, dict):
                    original_name = npc_param.get('name')
                    if original_name:
                        print(f"[NPC_NORM] Checking updatePartyNPCs action with npc.name='{original_name}'")

                        normalized_name, match_type = normalize_npc_name_for_action(
                            original_name, party_tracker_data, debug_print=True
                        )

                        if normalized_name is None:
                            rejections.append(f"Action {i+1} (updatePartyNPCs): '{original_name}' not in party tracker")
                            print(f"[NPC_NORM] REJECT: '{original_name}' cannot be matched to party tracker")

                        elif normalized_name != original_name:
                            npc_param['name'] = normalized_name
                            corrections.append(f"Action {i+1} (updatePartyNPCs): '{original_name}' → '{normalized_name}'")
                            print(f"[NPC_NORM] CORRECTED: '{original_name}' → '{normalized_name}'")

                        else:
                            print(f"[NPC_NORM] OK: '{original_name}' matches party tracker")

                # npc can also be a string (non-canonical but accepted for normalization)
                elif isinstance(npc_param, str):
                    original_name = npc_param
                    print(f"[NPC_NORM] Checking updatePartyNPCs action with npc='{original_name}' (string form)")

                    normalized_name, match_type = normalize_npc_name_for_action(
                        original_name, party_tracker_data, debug_print=True
                    )

                    if normalized_name is None:
                        rejections.append(f"Action {i+1} (updatePartyNPCs): '{original_name}' not in party tracker")
                        print(f"[NPC_NORM] REJECT: '{original_name}' cannot be matched to party tracker")

                    elif normalized_name != original_name:
                        # Convert string to dict with canonical name
                        params['npc'] = {"name": normalized_name}
                        corrections.append(f"Action {i+1} (updatePartyNPCs): '{original_name}' → '{normalized_name}' (converted to dict)")
                        print(f"[NPC_NORM] CORRECTED: '{original_name}' → '{normalized_name}' (converted string to dict)")

                    else:
                        # Convert string to dict to match canonical form
                        params['npc'] = {"name": original_name}
                        print(f"[NPC_NORM] OK: '{original_name}' matches party tracker (converted to dict)")

        # TABLETOP MODE: Normalize moveBackgroundNPC actions
        elif action_type == 'moveBackgroundNPC':
            params = action.get('parameters', {})
            original_name = params.get('npcName')

            if original_name:
                print(f"[NPC_NORM] Checking moveBackgroundNPC action with npcName='{original_name}'")

                # Try to normalize the name
                normalized_name, match_type = normalize_npc_name_for_action(
                    original_name, party_tracker_data, debug_print=True
                )

                if normalized_name is None:
                    # TABLETOP MODE: moveBackgroundNPC is module-world routing, not party-only routing.
                    # Try canonical identity resolution against module-known NPCs before rejecting.
                    module_name = str(party_tracker_data.get('module', '') or '').strip()
                    module_match = None
                    module_ambiguous = False

                    if module_name:
                        try:
                            from utils.npc_arrival_validator import resolve_npc_identity, load_module_npc_names

                            module_npc_names = load_module_npc_names(module_name)
                            if module_npc_names:
                                module_resolve = resolve_npc_identity(original_name, module_npc_names)
                                if module_resolve.status == "matched" and module_resolve.canonical_name:
                                    module_match = module_resolve.canonical_name
                                elif module_resolve.status == "ambiguous":
                                    module_ambiguous = True
                        except Exception as e:
                            print(f"[NPC_NORM] INFO: Module NPC resolution degraded for '{original_name}': {e}")

                    if module_match is not None:
                        params['npcName'] = module_match
                        corrections.append(
                            f"Action {i+1} (moveBackgroundNPC): '{original_name}' -> '{module_match}'"
                        )
                        print(f"[NPC_NORM] CORRECTED (module NPC): '{original_name}' -> '{module_match}'")
                    elif module_ambiguous:
                        rejections.append(
                            f"Action {i+1} (moveBackgroundNPC): '{original_name}' ambiguous in module NPC set"
                        )
                        print(f"[NPC_NORM] REJECT: '{original_name}' ambiguous in module NPC set")
                    else:
                        # Could not resolve in party or module canon - reject.
                        rejections.append(
                            f"Action {i+1} (moveBackgroundNPC): '{original_name}' not in party tracker or module NPC set"
                        )
                        print(
                            f"[NPC_NORM] REJECT: '{original_name}' cannot be matched to party tracker or module NPC set"
                        )

                elif normalized_name != original_name:
                    # Name was normalized
                    params['npcName'] = normalized_name
                    corrections.append(f"Action {i+1} (moveBackgroundNPC): '{original_name}' → '{normalized_name}'")
                    print(f"[NPC_NORM] CORRECTED: '{original_name}' → '{normalized_name}'")

                else:
                    # Name was already correct
                    print(f"[NPC_NORM] OK: '{original_name}' matches party tracker")

        # TABLETOP MODE: Normalize updatePartyNPCs add parameter forms
        # Handle parameters.add (string, list of strings, or list of dicts)
        if action_type == 'updatePartyNPCs':
            params = action.get('parameters', {})
            add_param = params.get('add')

            if add_param:
                # Normalize add parameter based on its type
                if isinstance(add_param, str):
                    # String form: "add": "Kira"
                    original_name = add_param
                    print(f"[NPC_NORM] Checking updatePartyNPCs action with add='{original_name}' (string form)")

                    normalized_name, match_type = normalize_npc_name_for_action(
                        original_name, party_tracker_data, debug_print=True
                    )

                    if normalized_name is None:
                        rejections.append(f"Action {i+1} (updatePartyNPCs): '{original_name}' not in party tracker")
                        print(f"[NPC_NORM] REJECT: '{original_name}' cannot be matched to party tracker")

                    elif normalized_name != original_name:
                        params['add'] = normalized_name
                        corrections.append(f"Action {i+1} (updatePartyNPCs): '{original_name}' → '{normalized_name}'")
                        print(f"[NPC_NORM] CORRECTED: '{original_name}' → '{normalized_name}'")

                    else:
                        print(f"[NPC_NORM] OK: '{original_name}' matches party tracker")

                elif isinstance(add_param, list):
                    # List form: "add": ["Kira", "Maelo"] or [{"name": "Kira"}, {"name": "Maelo"}]
                    print(f"[NPC_NORM] Checking updatePartyNPCs action with add={add_param} (list form)")
                    normalized_list = []
                    has_rejection = False

                    for idx, item in enumerate(add_param):
                        if isinstance(item, str):
                            # List of strings
                            original_name = item
                            normalized_name, match_type = normalize_npc_name_for_action(
                                original_name, party_tracker_data, debug_print=True
                            )

                            if normalized_name is None:
                                rejections.append(f"Action {i+1} (updatePartyNPCs): list item[{idx}] '{original_name}' not in party tracker")
                                print(f"[NPC_NORM] REJECT: list item[{idx}] '{original_name}' cannot be matched to party tracker")
                                has_rejection = True

                            elif normalized_name != original_name:
                                normalized_list.append(normalized_name)
                                corrections.append(f"Action {i+1} (updatePartyNPCs): list item[{idx}] '{original_name}' → '{normalized_name}'")
                                print(f"[NPC_NORM] CORRECTED: list item[{idx}] '{original_name}' → '{normalized_name}'")

                            else:
                                normalized_list.append(original_name)
                                print(f"[NPC_NORM] OK: list item[{idx}] '{original_name}' matches party tracker")

                        elif isinstance(item, dict):
                            # List of dicts - check for name key
                            original_name = item.get('name')
                            if original_name:
                                normalized_name, match_type = normalize_npc_name_for_action(
                                    original_name, party_tracker_data, debug_print=True
                                )

                                if normalized_name is None:
                                    rejections.append(f"Action {i+1} (updatePartyNPCs): dict item[{idx}] '{original_name}' not in party tracker")
                                    print(f"[NPC_NORM] REJECT: dict item[{idx}] '{original_name}' cannot be matched to party tracker")
                                    has_rejection = True

                                elif normalized_name != original_name:
                                    item['name'] = normalized_name
                                    normalized_list.append(item)
                                    corrections.append(f"Action {i+1} (updatePartyNPCs): dict item[{idx}] '{original_name}' → '{normalized_name}'")
                                    print(f"[NPC_NORM] CORRECTED: dict item[{idx}] '{original_name}' → '{normalized_name}'")

                                else:
                                    normalized_list.append(item)
                                    print(f"[NPC_NORM] OK: dict item[{idx}] '{original_name}' matches party tracker")
                            else:
                                # No name key in dict, keep as-is
                                normalized_list.append(item)

                        else:
                            # Unknown type, keep as-is
                            normalized_list.append(item)

                    # Only update params if no rejections occurred
                    if not has_rejection and normalized_list:
                        params['add'] = normalized_list

    # If any rejections, return error
    if rejections:
        error_msg = "NPC names not in party tracker: " + "; ".join(rejections)
        error_msg += f". Valid party NPCs: {[npc.get('name') for npc in party_tracker_data.get('partyNPCs', [])]}"
        error_msg += f". Valid party members: {party_tracker_data.get('partyMembers', [])}"
        return None, error_msg

    # If corrections were made, return updated response
    if corrections:
        corrected_response = json.dumps(parsed, ensure_ascii=True, indent=2)
        message = "Auto-corrected NPC names: " + "; ".join(corrections)
        return corrected_response, message

    # No changes needed
    return response_text, "All NPC names valid"

def validate_json_structure(response_text):
    """
    Pre-validate JSON structure before sending to AI validator.
    Returns tuple: (is_valid, fixed_response, error_message)
    """
    try:
        # Parse the JSON
        parsed = json.loads(response_text)
        
        # Check top-level structure
        if not isinstance(parsed, dict):
            return False, None, "Response is not a JSON object"
        
        if "narration" not in parsed:
            return False, None, "Missing 'narration' field"
        
        if "actions" not in parsed:
            # Add empty actions array if missing
            parsed["actions"] = []
            fixed = json.dumps(parsed, ensure_ascii=True)
            return True, fixed, "Added missing actions array"
        
        if not isinstance(parsed["actions"], list):
            return False, None, "'actions' must be an array"
        
        # Check each action's structure
        fixed_actions = []
        structure_issues = []
        
        for i, action in enumerate(parsed["actions"]):
            if not isinstance(action, dict):
                structure_issues.append(f"Action {i+1} is not an object")
                continue
                
            # Check if action has correct structure
            if "action" in action and "parameters" in action:
                # Correct structure
                fixed_actions.append(action)
            elif len(action) == 1:
                # Likely wrong format like {"updatePlot": {...}}
                action_name = list(action.keys())[0]
                action_params = action[action_name]
                
                # Auto-fix to correct structure
                fixed_action = {
                    "action": action_name,
                    "parameters": action_params if isinstance(action_params, dict) else {}
                }
                fixed_actions.append(fixed_action)
                structure_issues.append(f"Auto-fixed action {i+1}: {action_name}")
            else:
                structure_issues.append(f"Action {i+1} has invalid structure")
        
        # If we fixed any actions, return the fixed version
        if structure_issues and len(fixed_actions) == len(parsed["actions"]):
            parsed["actions"] = fixed_actions
            fixed_json = json.dumps(parsed, ensure_ascii=True, indent=2)
            return True, fixed_json, f"Auto-fixed structure issues: {'; '.join(structure_issues)}"
        elif structure_issues:
            return False, None, f"Structure errors: {'; '.join(structure_issues)}"
        
        # All good
        return True, response_text, "Structure valid"
        
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return False, None, f"Validation error: {str(e)}"

def validate_ai_response(primary_response, user_input, validation_prompt_text, conversation_history, party_tracker_data):
    print("DEBUG: NPC validation running...")
    status_validating()
    
    # Pre-validate JSON structure
    is_valid_structure, fixed_response, structure_message = validate_json_structure(primary_response)
    
    if not is_valid_structure:
        # Structure is too broken to fix automatically
        print(f"ERROR: JSON structure invalid - {structure_message}")
        return (False, f"JSON structure error: {structure_message}. Response must be valid JSON with 'narration' and 'actions' fields.")
    
    # Use fixed response if structure was auto-corrected
    response_to_validate = fixed_response if fixed_response != primary_response else primary_response

    if fixed_response != primary_response:
        print(f"INFO: Auto-fixed JSON structure - {structure_message}")

    # Pre-validate and normalize NPC names in updateCharacterInfo actions
    npc_normalized_response, npc_normalization_message = normalize_character_names_in_response(
        response_to_validate, party_tracker_data
    )

    if npc_normalized_response is None:
        # Name normalization failed - unresolvable NPC name
        print(f"ERROR: NPC name validation failed - {npc_normalization_message}")
        return (False, f"NPC name error: {npc_normalization_message}")

    if npc_normalized_response != response_to_validate:
        print(f"INFO: Auto-corrected NPC names - {npc_normalization_message}")
        response_to_validate = npc_normalized_response

    # TABLETOP MODE: NPC Arrival State Sync Validation (Tasks 1.1-1.4)
    # Validate that narration cannot introduce off-location known NPCs
    # unless the same response includes a matching state action
    # STRICT FAIL-CLOSED: All context loading must succeed or validation fails
    try:
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync, load_module_npc_names
        
        # Parse the response JSON for validation
        try:
            response_json = json.loads(response_to_validate)
        except json.JSONDecodeError as e:
            error_msg = "NPC arrival state sync validation error: invalid assistant JSON during guard evaluation"
            print(f"ERROR: {error_msg}")
            return (False, error_msg)
        
        # Get module name - required for context loading
        module_name = party_tracker_data.get("module", "")
        if not module_name or not module_name.strip():
            error_msg = "NPC arrival state sync validation error: module name missing from party tracker"
            print(f"ERROR: {error_msg}")
            return (False, error_msg)
        
        # Get current location data - required for present NPC detection
        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
        
        module_name_normalized = module_name.replace(" ", "_")
        from utils.module_path_manager import ModulePathManager
        path_manager = ModulePathManager(module_name_normalized)
        area_file = path_manager.get_area_path(current_area_id)
        
        try:
            with open(area_file, "r", encoding="utf-8") as file:
                area_data = json.load(file)
            location_data = next((loc for loc in area_data["locations"] if loc["locationId"] == current_location_id), None)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            error_msg = f"NPC arrival state sync validation error: failed to load location context ({str(e)})"
            print(f"ERROR: {error_msg}")
            return (False, error_msg)
        
        if location_data is None:
            error_msg = f"NPC arrival state sync validation error: location '{current_location_id}' not found in area '{current_area_id}'"
            print(f"ERROR: {error_msg}")
            return (False, error_msg)
        
        # Load all module NPC names for comprehensive known NPC detection
        module_npc_names = load_module_npc_names(module_name)
        
        # TABLETOP MODE: Detect travel intent from user input
        # Travel turns should fail-soft on NPC mentions without explicit arrival verbs
        # Requires directional keywords AND destination; excludes inquiry-only inputs
        is_travel_intent = False
        if user_input:
            input_lower = user_input.lower()
            
            # PHASE 1: Check for directional movement verbs (required)
            directional_verbs = ["go", "travel", "head", "move", "walk", "run", "proceed"]
            has_directional_verb = any(
                re.search(r'\b' + verb + r'\b', input_lower) for verb in directional_verbs
            )
            
            # PHASE 2: Check for destination indicators (required)
            # Includes: cardinal directions, location references, "there", module names
            destination_indicators = [
                # Cardinal directions
                "north", "south", "east", "west", "up", "down", "left", "right",
                "forward", "backward", "back",
                # Generic destination markers
                "there", "here", "to the", "toward", "towards",
            ]
            # Add current module location names as valid destinations
            if location_data and "locations" in location_data:
                for loc in location_data["locations"]:
                    loc_name = loc.get("name", "").lower()
                    if loc_name:
                        destination_indicators.append(loc_name)
            
            has_destination = any(
                re.search(r'\b' + re.escape(indicator) + r'\b', input_lower) 
                for indicator in destination_indicators
            )
            
            # PHASE 3: Detect inquiry-only inputs (must NOT be inquiry-only)
            # Inquiry-only = wondering/thinking/asking WITHOUT directional movement
            # Having wondering words + movement verbs = NOT inquiry-only (travel intent)
            inquiry_patterns = [
                r'^\s*(?:i\s+)?wonder\s+(?:about|if|whether)',
                r'^\s*(?:i\s+)?think\s+(?:about|of)',
                r'^\s*what\s+do\s+(?:i|we)\s+know',
                r'^\s*tell\s+(?:me|us)\s+about',
                r'^\s*ask\s+(?:about|regarding)',
            ]
            # Only check inquiry patterns if NO directional verb present
            is_inquiry_only = not has_directional_verb and any(
                re.search(pattern, input_lower) for pattern in inquiry_patterns
            )
            
            # Travel intent = directional verb AND destination AND NOT inquiry-only
            is_travel_intent = has_directional_verb and has_destination and not is_inquiry_only
        
        # Run NPC arrival state sync validation
        is_sync_valid, sync_reason = validate_npc_arrival_state_sync(
            response_json,
            party_tracker_data,
            location_data=location_data,
            module_npc_names=module_npc_names,
            is_travel_intent=is_travel_intent,
            user_utterance=user_input
        )
        
        # TABLETOP MODE: Step 3.1 - Capture deterministic result as structured metadata
        # This metadata is passed to LLM validator so it does not re-litigate deterministic pass/fail
        deterministic_result = {
            "deterministic_passed": is_sync_valid,
            "deterministic_reason": sync_reason if not is_sync_valid else "",
            "deterministic_required_action": sync_reason if not is_sync_valid else ""
        }
        
        if not is_sync_valid:
            print(f"ERROR: NPC arrival state sync validation failed - {sync_reason}")
            return (False, sync_reason)
        
    except Exception as e:
        # Fail-closed: all validation errors block processing
        error_msg = f"NPC arrival state sync validation error: {str(e)}"
        print(f"ERROR: {error_msg}")
        return (False, error_msg)

    # TABLETOP MODE: Deterministic mechanics precheck for explicit contradictions
    # Run before LLM validator to fail closed on parseable HP/slot/inventory contradictions.
    try:
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        mechanics_ok, mechanics_reason = validate_deterministic_mechanics_precheck(
            response_json,
            party_tracker_data=party_tracker_data,
        )
        if not mechanics_ok:
            print(f"ERROR: {mechanics_reason}")
            return (False, mechanics_reason)
    except Exception as e:
        error_msg = f"Deterministic mechanics precheck error: {str(e)}"
        print(f"ERROR: {error_msg}")
        return (False, error_msg)

    skip_llm_validation = False
    skip_reason = "not_evaluated"
    validation_routing_telemetry = {
        "skip_llm_validation": False,
        "skip_reason": "not_evaluated",
        "used_validation_compression": False,
        "compression_reason": "not_evaluated",
        "validation_payload_chars": 0,
    }

    # TABLETOP MODE: Conservative low-risk validator skip routing.
    # If deterministic checks pass and actions are explicitly low-risk, skip LLM validation.
    try:
        from utils.validation_routing import should_skip_llm_validation, build_validation_routing_telemetry

        skip_llm_validation, skip_reason = should_skip_llm_validation(
            response_json=response_json,
            deterministic_passed=deterministic_result.get("deterministic_passed", False),
        )
        validation_routing_telemetry = build_validation_routing_telemetry(
            skip_llm_validation=skip_llm_validation,
            skip_reason=skip_reason,
            used_validation_compression=False,
            compression_reason="not_evaluated",
            validation_payload_chars=0,
        )
        if skip_llm_validation:
            debug(
                f"VALIDATION: LLM validator skipped ({skip_reason}) telemetry={json.dumps(validation_routing_telemetry)}",
                category="ai_validation"
            )
            return (True, response_to_validate)
    except Exception as e:
        skip_reason = "skip_routing_unavailable"
        warning(
            f"VALIDATION: Skip routing unavailable, continuing full validation: {e}",
            category="ai_validation"
        )

    # The validation needs sufficient context to understand what happened
    # We need to include recent conversation history, not just the last two messages
    # This helps the validator understand ongoing narratives like ritual completions
    
    # Get the last several messages for context (excluding system messages and failed validations)
    recent_messages = []
    skip_next_assistant = False
    
    for i in range(len(conversation_history) - 1, -1, -1):
        msg = conversation_history[i]
        content = msg.get("content", "")
        
        # If we see an Error Note, mark to skip the previous assistant message (failed attempt)
        if msg["role"] == "user" and content.startswith("Error Note:"):
            skip_next_assistant = True
            continue  # Don't include the Error Note itself
            
        # Skip system messages and location transitions
        if msg["role"] in ["user", "assistant"]:
            # Skip this assistant message if it's a failed validation attempt
            if msg["role"] == "assistant" and skip_next_assistant:
                skip_next_assistant = False
                continue
                
            # Skip pure system notes
            if not content.startswith(("Location transition:", "Module transition:")):
                recent_messages.insert(0, msg)
                # Get last 4 messages (2 exchanges) for context
                if len(recent_messages) >= 4:
                    break
    
    # Ensure we have at least some context
    while len(recent_messages) < 4:
        recent_messages.insert(0, {"role": "assistant", "content": "Previous context not available."})

    # Get location data from party tracker
    current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
    current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]

    # Load the area data with correct module
    module_name = party_tracker_data.get("module", "").replace(" ", "_")
    path_manager = ModulePathManager(module_name)
    area_file = path_manager.get_area_path(current_area_id)
    try:
        with open(area_file, "r", encoding="utf-8") as file:
            area_data = json.load(file)
        location_data = next((loc for loc in area_data["locations"] if loc["locationId"] == current_location_id), None)
    except (FileNotFoundError, json.JSONDecodeError):
        location_data = None

    # Create the location details message
    if location_data:
        location_details = f"Location Details: {location_data['description']} {location_data.get('dmInstructions', '')}"
    else:
        location_details = "Location Details: Not available."
    
    # NOTE: Path validation now handled by transition intelligence agent in pre-validation
    # This old validation code is disabled to prevent conflicts
    if False and '"action": "transitionLocation"' in primary_response:
        try:
            # Extract the destination from the AI response
            destination_match = re.search(r'"newLocation":\s*"([^"]*)"', primary_response)
            if destination_match:
                destination = destination_match.group(1).strip()
                current_origin = current_location_id
                
                # Validate we have required data
                if not destination:
                    path_info = f"Path Validation ERROR: Empty destination in transitionLocation action."
                elif not current_origin:
                    path_info = f"Path Validation ERROR: Current location ID not available in party tracker."
                elif not location_graph:
                    path_info = f"Path Validation ERROR: Location graph not initialized."
                else:
                    # Check if location_graph is empty and reload if needed
                    if len(location_graph.nodes) == 0:
                        print("DEBUG: [LocationGraph] Global graph is empty, reloading...")
                        location_graph.reload()
                        print(f"DEBUG: [LocationGraph] Reload complete. Total nodes: {len(location_graph.nodes)}")

                    # Validate path using location graph
                    print(f"DEBUG: [LocationGraph] Path validation - From: {current_origin}, To: {destination}")
                    print(f"DEBUG: [LocationGraph] Current graph state - Nodes: {len(location_graph.nodes)}, Has origin: {current_origin in location_graph.nodes}")
                    success, path, message = location_graph.find_path(current_origin, destination)
                    
                    if success:
                        path_info = f"The party is currently at {current_origin} and desires to travel to {destination}. VALID PATH FOUND. The path of travel is: {' -> '.join(path)}."
                    else:
                        path_info = f"The party is currently at {current_origin} and desires to travel to {destination}. INVALID PATH: {message}"
                
                # Add path validation to location details
                location_details += f"\n\nPath Validation: {path_info}"
            else:
                # transitionLocation detected but no newLocation parameter found
                location_details += f"\n\nPath Validation ERROR: transitionLocation action detected but destination could not be extracted."
                
        except Exception as e:
            # Catch any unexpected errors in path validation
            location_details += f"\n\nPath Validation ERROR: Failed to validate path - {str(e)}"

    # Create user input context for validation
    user_input_context = f"VALIDATION CONTEXT: The user input that triggered this assistant response was: '{user_input}'"
    
    # Create module data context for location/NPC validation
    module_data_context = create_module_validation_context(party_tracker_data, path_manager)
    
    # Build compact mechanics-first truth packs for touched updateCharacterInfo actions.
    character_truth_pack_context = ""
    try:
        from utils.validator_truth_pack import (
            build_touched_character_truth_pack,
            format_truth_pack_for_validation,
        )

        truth_packs = build_touched_character_truth_pack(response_json)
        if truth_packs:
            character_truth_pack_context = format_truth_pack_for_validation(truth_packs)
            debug(
                f"VALIDATION: CHARACTER_MECHANICAL_TRUTH_PACK built for {len(truth_packs)} character(s)",
                category="ai_validation"
            )
    except Exception as e:
        debug(f"VALIDATION: Truth-pack build failed, continuing without it: {e}", category="ai_validation")
    
    # Add structure validation status to context
    structure_validation_note = ""
    if fixed_response != primary_response:
        structure_validation_note = f"JSON STRUCTURE PRE-VALIDATED: {structure_message}. Structure has been auto-corrected. Focus on validating CONTENT only (NPCs, locations, game rules)."
    else:
        structure_validation_note = "JSON STRUCTURE PRE-VALIDATED: Structure is correct. Focus on validating CONTENT only (NPCs, locations, game rules)."
    
    # Build dynamic NPC context
    npc_validation_context = ""
    try:
        from core.ai.build_npc_context import build_npc_validation_context
        
        # Get party NPCs from party tracker data
        party_npc_names = [npc.get('name') for npc in party_tracker_data.get('partyNPCs', [])]
        
        # Build compressed NPC context
        npc_validation_context = build_npc_validation_context(
            current_module=party_tracker_data.get('module', 'Unknown'),
            current_location=party_tracker_data.get('worldConditions', {}).get('currentLocationId', 'Unknown'),
            party_npcs=party_npc_names
        )
    except Exception as e:
        print(f"ERROR: Failed to build NPC context: {e}")
        import traceback
        traceback.print_exc()
    
    # TABLETOP MODE: Step 3.1 - Add deterministic result metadata to validation context
    # This ensures LLM validator knows deterministic pass/fail and does not re-litigate
    deterministic_metadata_msg = json.dumps(deterministic_result)
    
    validation_conversation = [
        {"role": "system", "content": validation_prompt_text},
        {"role": "system", "content": structure_validation_note},
        {"role": "system", "content": f"DETERMINISTIC_VALIDATION_RESULT: {deterministic_metadata_msg}"},
        {"role": "system", "content": f"VALIDATION_ROUTING_TELEMETRY: {json.dumps(validation_routing_telemetry)}"},
        {"role": "system", "content": npc_validation_context},  # Always include, even if empty
        {"role": "system", "content": location_details},
        {"role": "system", "content": user_input_context},
        {"role": "system", "content": module_data_context},
        {"role": "system", "content": character_truth_pack_context} if character_truth_pack_context else None,
    ]
    
    
    # Add recent conversation context
    validation_conversation.extend(recent_messages)
    
    # Add the response being validated (use fixed version if structure was corrected)
    validation_conversation.append({"role": "assistant", "content": response_to_validate})
    
    # Filter out None entries
    validation_conversation = [msg for msg in validation_conversation if msg is not None]
    
    # DEBUG: Log what validation AI sees for createNewModule actions
    if '"action": "createNewModule"' in primary_response:
        debug("VALIDATION: *** VALIDATION DEBUG - createNewModule detected ***", category="ai_validation")
        debug(f"VALIDATION: User input that triggered this: {user_input}", category="ai_validation")
        debug("VALIDATION: Last two messages validation AI sees:", category="ai_validation")
        # Get last two messages from validation conversation
        last_two_messages = validation_conversation[-2:] if len(validation_conversation) >= 2 else validation_conversation
        for i, msg in enumerate(last_two_messages):
            debug(f"VALIDATION: Message {i+1}: {msg['role']}: {msg['content'][:100]}...", category="ai_validation")
        debug("VALIDATION: *** END VALIDATION DEBUG ***", category="ai_validation")

    # Apply compression to validation messages only when payload exceeds threshold.
    from model_config import COMPRESSION_ENABLED, VALIDATION_COMPRESSION_MIN_CHARS
    from utils.validation_routing import (
        build_validation_routing_telemetry,
        get_validation_compression_decision,
    )

    validation_payload_size = sum(
        len(msg.get("content", ""))
        for msg in validation_conversation
        if isinstance(msg, dict)
    )
    use_validation_compression, compression_reason = get_validation_compression_decision(
        total_chars=validation_payload_size,
        compression_enabled=COMPRESSION_ENABLED,
        threshold_chars=VALIDATION_COMPRESSION_MIN_CHARS,
    )

    validation_routing_telemetry = build_validation_routing_telemetry(
        skip_llm_validation=skip_llm_validation,
        skip_reason=skip_reason,
        used_validation_compression=use_validation_compression,
        compression_reason=compression_reason,
        validation_payload_chars=validation_payload_size,
    )

    for msg in validation_conversation:
        if isinstance(msg, dict) and isinstance(msg.get("content"), str) and msg["content"].startswith("VALIDATION_ROUTING_TELEMETRY:"):
            msg["content"] = f"VALIDATION_ROUTING_TELEMETRY: {json.dumps(validation_routing_telemetry)}"
            break

    if use_validation_compression:
        try:
            from pathlib import Path

            # Save validation conversation to temp file
            temp_file = Path("/tmp/temp_validation_for_api.json")
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(validation_conversation, f, indent=2, ensure_ascii=False)

            # TABLETOP MODE: Use multi-PC aware compressor when in multi-PC mode
            # Detect multi-PC mode by checking for active_pc tags in conversation history
            use_multi_pc_compressor = False
            try:
                from config import MULTIPLAYER_MODE
                if MULTIPLAYER_MODE:
                    # Check if any messages have active_pc tags (indicates multi-PC mode)
                    has_active_pc_tags = any(
                        msg.get("active_pc") for msg in validation_conversation
                        if isinstance(msg, dict)
                    )
                    if has_active_pc_tags:
                        use_multi_pc_compressor = True
            except ImportError:
                use_multi_pc_compressor = False

            if use_multi_pc_compressor:
                # Use multi-PC aware compressor for tabletop mode
                from utils.compression.multi_pc_conversation_compressor import MultiPCConversationCompressor
                compressor = MultiPCConversationCompressor(inject_module_creation=False)
                debug("VALIDATION: Using multi-PC conversation compressor", category="ai_validation")
            else:
                # Use standard parallel compressor for single-PC mode
                from utils.compression.conversation_compressor_parallel import ParallelConversationCompressor
                compressor = ParallelConversationCompressor(inject_module_creation=False)

            # Compress using selected compressor
            validation_messages_to_send = compressor.process_conversation_history(str(temp_file))
            
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
            
            debug("VALIDATION: Applied parallel compression to validation messages", category="ai_validation")
        except Exception as e:
            # If compression fails, use original messages
            warning(f"VALIDATION: Compression failed, using original messages: {e}", category="ai_validation")
            validation_messages_to_send = validation_conversation
    else:
        debug(
            f"VALIDATION: Compression skipped (payload={validation_payload_size} chars, threshold={VALIDATION_COMPRESSION_MIN_CHARS}, reason={compression_reason})",
            category="ai_validation"
        )
        validation_messages_to_send = validation_conversation
    
    # TABLETOP MODE: Strip active_pc from validation messages before API call
    # Some providers reject unknown fields in message objects
    for msg in validation_messages_to_send:
        if isinstance(msg, dict) and "active_pc" in msg:
            del msg["active_pc"]
    
    # Export validation messages for debugging
    os.makedirs("debug/api_captures", exist_ok=True)
    with open("debug/api_captures/main_validation_messages_to_api.json", "w", encoding="utf-8") as f:
        json.dump(validation_messages_to_send, f, indent=2, ensure_ascii=False)
    print(f"DEBUG: [MAIN VALIDATION] Exported validation messages to debug/api_captures/main_validation_messages_to_api.json")
    
    max_validation_retries = 3
    for attempt in range(max_validation_retries):
        validation_result = client.chat.completions.create(
            model=DM_VALIDATION_MODEL, # Use imported model name
            temperature=0.1,  # Low temperature for consistent validation
            messages=validation_messages_to_send
        )

        # Log API call to master log
        try:
            from utils.api_logger import log_api_call
            log_api_call("validation", validation_messages_to_send, validation_result,
                        metadata={"attempt": attempt+1, "max_retries": max_validation_retries})
        except Exception as e:
            print(f"[API_LOG] Warning: Failed to log validation call: {e}")

        # Track token usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(validation_result, context={'endpoint': 'validation', 'purpose': 'validate_dm_response'})
            except:
                pass

        validation_response = validation_result.choices[0].message.content.strip()

        try:
            validation_json = parse_json_safely(validation_response)
            is_valid = validation_json.get("valid", False)
            reason = validation_json.get("reason", "No reason provided")
            
            # Track validation pairs for quality control
            try:
                os.makedirs("debug/quality_control", exist_ok=True)
                validation_pair = {
                    "timestamp": datetime.now().isoformat(),
                    "user_input": user_input,  # What the user originally said
                    "assistant_response": response_to_validate if attempt == 0 else validation_messages_to_send[-1]["content"],
                    "structure_validation": {
                        "needed_fix": fixed_response != primary_response,
                        "message": structure_message,
                        "original_response": primary_response if fixed_response != primary_response else None
                    },
                    "validation_result": {
                        "valid": is_valid,
                        "reason": reason,
                        "raw_response": validation_response
                    },
                    "attempt": attempt + 1,
                    "model_used": DM_VALIDATION_MODEL
                }
                
                # Append to validation pairs log
                validation_log_path = "debug/quality_control/validation_pairs.jsonl"
                with open(validation_log_path, "a", encoding="utf-8") as f:
                    json.dump(validation_pair, f, ensure_ascii=False)
                    f.write("\n")
            except Exception as e:
                debug(f"Failed to log validation pair: {e}", category="ai_validation")

            # TABLETOP MODE: Step 3.1 - Deterministic hard-gate for arrival-sync
            # If deterministic validator passed, LLM validator MUST NOT fail on arrival-sync grounds
            # This enforces spec: deterministic validator is sole source of truth for arrival sync
            arrival_sync_override = False
            if is_valid:
                # Already valid - no override needed
                pass
            elif deterministic_result.get("deterministic_passed", False):
                # Deterministic passed but LLM failed - check if it's arrival-sync related
                arrival_sync_keywords = [
                    "arrival", "arrives", "arrived", "arriving",
                    "moveBackgroundNPC", "updatePartyNPCs",
                    "off-location", "not currently present",
                    "NPC arrival state sync"
                ]
                reason_lower = reason.lower()
                is_arrival_sync_failure = any(kw in reason_lower for kw in arrival_sync_keywords)
                
                if is_arrival_sync_failure:
                    # HARD-GATE: Override LLM failure, respect deterministic pass
                    warning(f"VALIDATION: LLM validator attempted arrival-sync failure but deterministic validator passed. Overriding to VALID. Reason: {reason}", category="ai_validation")
                    debug(f"DETERMINISTIC_GATE: Arrival-sync failure suppressed, respecting deterministic_passed=true", category="ai_validation")
                    is_valid = True
                    arrival_sync_override = True
            
            # Log only failed validations to prompt_validation.json
            if not is_valid:
                log_entry = {
                    "prompt": validation_conversation,
                    "response": validation_response,
                    "reason": reason
                }

                # Ensure debug/logs directory exists
                os.makedirs("debug/logs", exist_ok=True)

                with open("debug/logs/prompt_validation.json", "a", encoding="utf-8") as log_file:
                    json.dump(log_entry, log_file)
                    log_file.write("\n")  # Add a newline for better readability

                return (False, reason)  # Return tuple with failure status and reason
            else:
                if arrival_sync_override:
                    debug("SUCCESS: Validation passed via deterministic hard-gate (LLM arrival-sync failure suppressed)", category="ai_validation")
                else:
                    debug("SUCCESS: Validation passed successfully", category="ai_validation")
                # Return the fixed/validated response content
                return (True, response_to_validate)  # Return tuple with validation status and content

        except json.JSONDecodeError:
            debug(f"VALIDATION: Invalid JSON from validation model (Attempt {attempt + 1}/{max_validation_retries})", category="ai_validation")
            debug(f"VALIDATION: Problematic response: {validation_response}", category="ai_validation")
            continue  # Retry the validation

    # If we've exhausted all retries and still don't have a valid JSON response
    warning("VALIDATION: Validation model consistently produced invalid JSON. Assuming primary response is valid.", category="ai_validation")
    # Return the (potentially fixed) response
    return (True, response_to_validate)

def load_validation_prompt():
    # Canonical runtime authority: always use compressed validation prompt.
    prompt_file = "prompts/validation/validation_prompt_compressed.txt"
    
    with open(prompt_file, "r", encoding="utf-8") as file:
        return file.read().strip()

def load_json_file(file_path):
    """Load a JSON file, with error handling and encoding sanitization"""
    return safe_json_load(file_path)

def remove_duplicate_npcs(party_tracker_data):
    """Remove duplicate NPCs from party tracker, keeping first occurrence.
    
    Args:
        party_tracker_data: The party tracker dictionary
        
    Returns:
        tuple: (cleaned_data, changes_made) where changes_made is boolean
    """
    if not party_tracker_data or "partyNPCs" not in party_tracker_data:
        return party_tracker_data, False
    
    original_npcs = party_tracker_data["partyNPCs"]
    seen_names = set()
    unique_npcs = []
    duplicates_removed = []
    
    for npc in original_npcs:
        npc_name = npc.get("name", "")
        if npc_name not in seen_names:
            seen_names.add(npc_name)
            unique_npcs.append(npc)
        else:
            duplicates_removed.append(npc_name)
    
    if duplicates_removed:
        debug(f"STATE_CHANGE: Removing duplicate NPCs: {duplicates_removed}", category="npc_management")
        party_tracker_data["partyNPCs"] = unique_npcs
        return party_tracker_data, True
    
    return party_tracker_data, False

def process_conversation_history(history):
    debug("STATE_CHANGE: Processing conversation history", category="conversation_management")
    for message in history:
        if message["role"] == "user" and message["content"].startswith("Leveling Dungeon Master Guidance"):
            message["content"] = "DM Guidance: Proceed with leveling up the player character or the party NPC given the 5th Edition role playing game rules. Only level the player character or party NPC one level at a time to ensure no mistakes are made. If you are leveling up a party NPC then pass all changes at once using the 'updateCharacterInfo' action. If you are leveling up a player character then you must ask the player for important decisions and choices they would have control over. After the player has provided the needed information then use the 'updateCharacterInfo' to pass all changes to the players character sheet and include the experience goal for the next level. Do not update the player's information in segements."
    
    # Apply DM note truncation to clean up bloated messages
    history = truncate_dm_notes(history)
    
    debug("SUCCESS: Conversation history processing complete", category="conversation_management")
    return history

def remove_duplicate_messages(conversation_history):
    """Remove duplicate messages from conversation history, specifically targeting combat system messages"""
    if not conversation_history or len(conversation_history) < 2:
        return conversation_history
    
    cleaned_history = []
    seen_combat_system_messages = set()  # Track unique "[SYSTEM: Combat" messages
    
    for i, msg in enumerate(conversation_history):
        content = msg.get("content", "")
        
        # Check if this is a combat-related system message
        is_combat_system_msg = content.startswith("[SYSTEM: Combat")
        
        # Always keep the first message
        if i == 0:
            cleaned_history.append(msg)
            if is_combat_system_msg:
                seen_combat_system_messages.add(content)
        # For combat system messages, check if we've seen this exact message before
        elif is_combat_system_msg:
            if content not in seen_combat_system_messages:
                cleaned_history.append(msg)
                seen_combat_system_messages.add(content)
            else:
                debug(f"Removed duplicate combat system message at index {i}: {content[:60]}...", category="conversation_management")
        # For all other messages, only check against previous message (original behavior)
        elif msg != conversation_history[i-1]:
            cleaned_history.append(msg)
        else:
            debug(f"Removed duplicate message at index {i}", category="conversation_management")
    
    return cleaned_history

def truncate_dm_notes(conversation_history):
    for message in conversation_history:
        if message["role"] == "user" and message["content"].startswith("Dungeon Master Note:"):
            parts = message["content"].split("Player:", 1)
            if len(parts) == 2:
                date_time = re.search(r"Current date and time: ([^.]+)", parts[0])
                if date_time:
                    message["content"] = f"Dungeon Master Note: {date_time.group(0)}. Player:{parts[1]}"
    return conversation_history

def check_and_process_location_transitions(conversation_history, party_tracker_data, path_manager):
    """
    Check if there are any unprocessed location transitions in the conversation history
    and process them to create summaries and compress the history.
    """
    # Find the most recent transition that hasn't been processed yet
    last_transition_index = None
    last_transition_content = None
    
    for i in range(len(conversation_history) - 1, -1, -1):
        msg = conversation_history[i]
        if msg.get("role") == "user" and "Location transition:" in msg.get("content", ""):
            last_transition_index = i
            last_transition_content = msg.get("content", "")
            break
    
    if last_transition_index is None:
        # No transitions found
        return conversation_history
    
    # Check if this transition has already been processed (has a summary right before it)
    if last_transition_index > 0:
        prev_msg = conversation_history[last_transition_index - 1]
        if "=== LOCATION SUMMARY ===" in prev_msg.get("content", ""):
            # This transition has already been processed
            return conversation_history
    
    # Check if there's already a summary after this transition
    # If there are regular conversation messages after the transition, we should process it
    has_conversation_after = False
    for i in range(last_transition_index + 1, len(conversation_history)):
        msg = conversation_history[i]
        # Skip system messages and DM notes
        if msg.get("role") == "assistant" or (msg.get("role") == "user" and "Dungeon Master Note:" not in msg.get("content", "")):
            has_conversation_after = True
            break
    
    if not has_conversation_after:
        # No conversation after the transition yet, wait for next round
        return conversation_history
    
    # Extract the leaving location from the transition message
    # New format: "Location transition: [from_location] (ID) to [to_location] (ID)"
    # Old format: "Location transition: [from_location] to [to_location]"
    try:
        import re
        # Try to extract with IDs first (new format)
        id_pattern = r'Location transition: (.+?) \(([A-Z]\d+)\) to (.+?) \(([A-Z]\d+)\)'
        id_match = re.match(id_pattern, last_transition_content)
        
        if id_match:
            # New format with IDs
            leaving_location_name = id_match.group(1)
            leaving_location_id = id_match.group(2)
            debug(f"STATE_CHANGE: Extracted from new format - Location: {leaving_location_name}, ID: {leaving_location_id}", category="location_transitions")
        else:
            # Fall back to old format
            parts = last_transition_content.split(" to ")
            if len(parts) == 2:
                from_part = parts[0].replace("Location transition: ", "").strip()
                leaving_location_name = from_part
                leaving_location_id = None
                debug(f"STATE_CHANGE: Extracted from old format - Location: {leaving_location_name}", category="location_transitions")
            else:
                warning("VALIDATION: Could not parse transition message format", category="location_transitions")
                return conversation_history
    except Exception as e:
        error(f"FAILURE: Error parsing transition message", exception=e, category="location_transitions")
        return conversation_history
    
    debug(f"STATE_CHANGE: Processing transition from {leaving_location_name}", category="location_transitions")
    
    try:
        # Generate enhanced adventure summary
        adventure_summary = generate_enhanced_adventure_summary(
            conversation_history,
            party_tracker_data,
            leaving_location_name
        )
        
        if adventure_summary:
            # Update journal with the summary
            update_journal_with_summary(
                adventure_summary,
                party_tracker_data,
                leaving_location_name
            )
            
            # Compress conversation history
            compressed_history = compress_conversation_history_on_transition(
                conversation_history,
                leaving_location_name
            )
            
            # Check if chunked compression is needed after creating the location summary
            try:
                from core.ai.chunked_compression_integration import check_and_perform_chunked_compression
                if check_and_perform_chunked_compression():
                    debug("SUCCESS: Chunked compression performed after location transition", category="conversation_management")
                    # Reload the compressed history
                    compressed_history = load_json_file(json_file) or compressed_history
            except Exception as e:
                error(f"FAILURE: Chunked compression check failed", exception=e, category="conversation_management")
            
            debug("SUCCESS: Location summary and compression completed", category="location_transitions")
            return compressed_history
        else:
            debug("STATE_CHANGE: No adventure summary generated", category="location_transitions")
            return conversation_history
            
    except Exception as e:
        error(f"FAILURE: Failed to process location transition", exception=e, category="location_transitions")
        import traceback
        traceback.print_exc()
        return conversation_history

def check_and_process_module_transitions(conversation_history, party_tracker_data):
    """
    Check if there are any unprocessed module transitions in the conversation history
    and process them to create summaries and compress the history.
    Mirrors the logic of check_and_process_location_transitions().
    """
    # Find the most recent transition that hasn't been processed yet
    last_transition_index = None
    last_transition_content = None
    
    for i in range(len(conversation_history) - 1, -1, -1):
        msg = conversation_history[i]
        if msg.get("role") == "user" and "Module transition:" in msg.get("content", ""):
            last_transition_index = i
            last_transition_content = msg.get("content", "")
            break
    
    if last_transition_index is None:
        # No module transitions found
        return conversation_history
    
    # Check if this transition has already been processed (has a summary right before it)
    if last_transition_index > 0:
        prev_msg = conversation_history[last_transition_index - 1]
        if prev_msg.get("role") == "user" and prev_msg.get("content", "").startswith("Module summary:"):
            # This transition has already been processed
            return conversation_history
    
    # Check if there's already conversation after this transition
    # If there are regular conversation messages after the transition, we should process it
    has_conversation_after = False
    for i in range(last_transition_index + 1, len(conversation_history)):
        msg = conversation_history[i]
        # Skip system messages and DM notes
        if msg.get("role") == "assistant" or (msg.get("role") == "user" and "Dungeon Master Note:" not in msg.get("content", "")):
            has_conversation_after = True
            break
    
    if not has_conversation_after:
        # No conversation after the transition yet, wait for next round
        return conversation_history
    
    # Extract the leaving module from the transition message
    # Format: "Module transition: [from_module] to [to_module]"
    try:
        import re
        pattern = r'Module transition: (.+?) to (.+?)$'
        match = re.match(pattern, last_transition_content)
        
        if match:
            leaving_module_name = match.group(1)
            arriving_module_name = match.group(2)
            debug(f"STATE_CHANGE: Extracted module transition - From: {leaving_module_name}, To: {arriving_module_name}", category="module_transitions")
        else:
            warning("VALIDATION: Could not parse module transition message format", category="module_transitions")
            return conversation_history
    except Exception as e:
        error(f"FAILURE: Error parsing module transition message", exception=e, category="module_transitions")
        return conversation_history
    
    debug(f"STATE_CHANGE: Processing module transition from {leaving_module_name}", category="module_transitions")
    
    try:
        # Generate module summary using similar logic to location summaries
        module_summary = generate_module_summary(
            conversation_history,
            party_tracker_data,
            leaving_module_name,
            last_transition_index
        )
        
        if module_summary:
            # Compress conversation history for module transition
            compressed_history = compress_conversation_history_on_module_transition(
                conversation_history,
                leaving_module_name,
                module_summary,
                last_transition_index
            )
            
            debug("SUCCESS: Module summary and compression completed", category="module_transitions")
            return compressed_history
        else:
            debug("STATE_CHANGE: No module summary generated", category="module_transitions")
            return conversation_history
            
    except Exception as e:
        error(f"FAILURE: Failed to process module transition", exception=e, category="module_transitions")
        import traceback
        traceback.print_exc()
        return conversation_history

def generate_module_summary(conversation_history, party_tracker_data, module_name, transition_index):
    """Generate a summary for a module transition"""
    
    # Condition 1: Look for previous module transition OR module summary first
    boundary_index = None
    
    for i in range(transition_index - 1, -1, -1):
        msg = conversation_history[i]
        content = msg.get("content", "")
        
        # Look for either previous module transition or existing module summary
        if (msg.get("role") == "user" and 
            ("Module transition:" in content or "Module summary:" in content)):
            boundary_index = i + 1  # Start after previous transition/summary
            debug(f"VALIDATION: CONDITION 1 - Found previous module marker at index {i}, boundary at {boundary_index}", category="conversation_management")
            break
    
    # Condition 2: If no previous module transition/summary, find last system message
    if boundary_index is None:
        for i in range(transition_index - 1, -1, -1):
            msg = conversation_history[i]
            if msg.get("role") == "system":
                boundary_index = i + 1  # Start after last system message
                debug(f"VALIDATION: CONDITION 2 - Found last system message at index {i}, boundary at {boundary_index}", category="conversation_management")
                break
        
        # Fallback if no system message found (shouldn't happen)
        if boundary_index is None:
            boundary_index = 0
            debug(f"VALIDATION: FALLBACK - No system message found, using boundary at {boundary_index}", category="conversation_management")
    
    # Extract ONLY the conversation from boundary to transition (actual gameplay)
    module_conversation = conversation_history[boundary_index:transition_index]
    debug(f"STATE_CHANGE: Extracting {len(module_conversation)} messages from index {boundary_index} to {transition_index} for summary", category="conversation_management")
    
    # Generate summary from ACTUAL conversation history, not plot files
    try:
        # Filter out system messages and technical messages from the conversation
        meaningful_messages = []
        for msg in module_conversation:
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            # Skip technical messages but keep actual gameplay
            if (role in ["user", "assistant"] and 
                not content.startswith(("Location transition:", "Module transition:", 
                                      "Module summary:", "Dungeon Master Note:", "Error Note:"))):
                meaningful_messages.append(msg)
        
        debug(f"STATE_CHANGE: Found {len(meaningful_messages)} meaningful conversation messages to summarize", category="summary_building")
        
        # If we have substantial conversation, generate AI summary from actual gameplay
        if len(meaningful_messages) >= 3:
            try:
                # Generate summary using AI client factory (OpenAI/OpenRouter)
                summary_client = create_chat_client()
                summary_model = get_chat_model_name()

                # Prepare conversation for summarization
                conversation_text = ""
                for msg in meaningful_messages:  # All meaningful messages from this module
                    role = "Player" if msg.get("role") == "user" else "DM"
                    content = msg.get("content", "")
                    conversation_text += f"{role}: {content}\n\n"
                
                summary_prompt = f"""You are creating an adventure chronicle for a 5th edition session. Summarize this actual gameplay conversation from the {module_name} module into a compelling narrative story.

IMPORTANT: Only include events that actually happened in the conversation. Do not add events from other sources.

Focus on:
- Actual player actions and decisions made
- NPCs encountered and interactions that occurred  
- Locations visited and described
- Plot developments that happened
- Character relationships and moments

Write in an elevated fantasy prose style, like a chronicle or epic tale. Make it engaging but accurate to what actually occurred.

ACTUAL GAMEPLAY CONVERSATION:
{conversation_text}

Write a compelling chronicle of these actual events:"""

                try:
                    response = summary_client.chat.completions.create(
                        model=summary_model,
                        messages=[
                            {"role": "system", "content": "You are an expert at creating beautiful adventure chronicles from 5th edition gameplay, focusing only on events that actually occurred."},
                            {"role": "user", "content": summary_prompt}
                        ],
                        temperature=0.7
                    )
                except Exception as api_error:
                    error_result = handle_provider_error(api_error, context="Module summary generation")
                    if error_result["should_fallback"]:
                        fallback_client = create_chat_client(use_fallback=True)
                        response = fallback_client.chat.completions.create(
                            model=DM_SUMMARIZATION_MODEL,
                            messages=[
                                {"role": "system", "content": "You are an expert at creating beautiful adventure chronicles from 5th edition gameplay, focusing only on events that actually occurred."},
                                {"role": "user", "content": summary_prompt}
                            ],
                            temperature=0.7
                        )
                    else:
                        raise

                # Log API call to master log
                try:
                    from utils.api_logger import log_api_call
                    log_api_call("module_summary", [
                        {"role": "system", "content": "You are an expert at creating beautiful adventure chronicles from 5th edition gameplay, focusing only on events that actually occurred."},
                        {"role": "user", "content": summary_prompt}
                    ], response, metadata={"temperature": 0.7, "module": module_name})
                except Exception as e:
                    print(f"[API_LOG] Warning: Failed to log summary call: {e}")

                # Track token usage with context for telemetry
                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(response, context={'endpoint': 'module_summary', 'purpose': 'generate_module_summary', 'module': module_name})
                    except:
                        pass
                
                ai_summary = response.choices[0].message.content.strip()
                formatted_summary = f"=== MODULE SUMMARY ===\n\n{module_name}:\n------------------------------\n{ai_summary}"
                debug(f"SUCCESS: Generated AI summary from actual conversation for {module_name}", category="summary_building")
                return formatted_summary
                
            except Exception as e:
                warning(f"FAILURE: Error generating AI summary from conversation, using fallback", category="summary_building")
        
        debug(f"STATE_CHANGE: Not enough meaningful conversation for AI summary ({len(meaningful_messages)} messages), using fallback", category="summary_building")
        
    except Exception as e:
        error(f"FAILURE: Error processing conversation for summary, using fallback", exception=e, category="summary_building")
    
    # Fallback to simple summary if no AI summary available
    meaningful_messages = [
        msg for msg in module_conversation 
        if msg.get("role") in ["user", "assistant"] and 
        not msg.get("content", "").startswith(("Location transition:", "Module transition:", "Module summary:"))
    ]
    
    if len(meaningful_messages) < 2:
        return f"Brief activities in {module_name}."
    elif len(meaningful_messages) <= 5:
        return f"Short adventure in {module_name} with several interactions."
    else:
        return f"Extended adventure in {module_name} with multiple significant events and discoveries."

def compress_conversation_history_on_module_transition(conversation_history, module_name, summary_text, transition_index):
    """Compress conversation history by replacing conversation segment with summary, preserving previous summaries"""
    
    # Find the boundary for compression - same logic as generate_module_summary
    boundary_index = None
    
    for i in range(transition_index - 1, -1, -1):
        msg = conversation_history[i]
        content = msg.get("content", "")
        
        # Look for either previous module transition or existing module summary
        if (msg.get("role") == "user" and 
            ("Module transition:" in content or "Module summary:" in content)):
            boundary_index = i + 1  # Start after previous transition/summary
            debug(f"VALIDATION: COMPRESSION - Found previous module marker at index {i}, boundary at {boundary_index}", category="conversation_management")
            break
    
    # If no previous module marker, find last system message
    if boundary_index is None:
        for i, msg in enumerate(conversation_history):
            if msg.get("role") == "system":
                boundary_index = i + 1  # Start after system message
                debug(f"VALIDATION: COMPRESSION - Found system message at index {i}, boundary at {boundary_index}", category="conversation_management")
                break
        
        if boundary_index is None:
            boundary_index = 0
            debug(f"VALIDATION: COMPRESSION - No system message found, using boundary at {boundary_index}", category="conversation_management")
    
    # Create summary message
    summary_message = {
        "role": "user",
        "content": f"Module summary: {summary_text}"
    }
    
    # Build compressed history: everything before boundary + summary + transition + everything after
    compressed_history = []
    
    # Keep everything before the boundary (includes system message + previous summaries)
    compressed_history.extend(conversation_history[:boundary_index])
    
    # Add the new summary for this module  
    compressed_history.append(summary_message)
    
    # Add transition marker and everything after
    compressed_history.extend(conversation_history[transition_index:])
    
    debug(f"SUCCESS: Compressed module conversation from {len(conversation_history)} to {len(compressed_history)} messages", category="conversation_management")
    debug(f"STATE_CHANGE: Preserved {boundary_index} messages before boundary, added 1 summary, kept {len(conversation_history) - transition_index} messages after transition", category="conversation_management")
    debug("STATE_CHANGE: Result structure: main system message + module summary + transition + new conversation", category="conversation_management")
    return compressed_history

def extract_json_from_codeblock(text):
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()

def handle_character_creation_response(response, party_tracker_data, conversation_history):
    """
    Handle character creation mode responses.
    Detects when LLM outputs complete character JSON and finalizes creation.
    
    Args:
        response: The LLM's response text
        party_tracker_data: Current party tracker state
        conversation_history: Current conversation history
        
    Returns:
        One of:
        - "not_candidate": response is not a final character JSON candidate
        - "needs_retry": final JSON was detected but requires correction
        - "finalized": character creation completed successfully
        - "error": finalization failed closed
    """
    try:
        response_text = response.strip()
        if not response_text:
            return "not_candidate"

        finalize_result = finalize_character_creation_candidate(
            response_text,
            source="main_dm_interview_finalize",
        )
        finalize_status = str(finalize_result.get("status", "")).strip().lower()

        if finalize_status == "not_candidate":
            return "not_candidate"

        if finalize_status == "needs_retry":
            corrective_note = finalize_result.get("corrective_guidance", "").strip()
            if not corrective_note:
                missing_paths = finalize_result.get("missing_paths") or []
                missing_paths_text = ", ".join(missing_paths[:12]) if missing_paths else "unknown"
                result_type = finalize_result.get("audit_result_type", "unknown")
                corrective_note = (
                    "Character creation final JSON failed validation. "
                    f"Result: {result_type}. "
                    f"Missing/invalid paths: {missing_paths_text}. "
                    "Output a single corrected JSON object with all required fields completed."
                )

            conversation_history.append({"role": "user", "content": corrective_note})
            save_conversation_history(conversation_history)

            result_type = finalize_result.get("audit_result_type", "unknown")
            warning(
                f"CHARACTER_CREATION: Audit blocked finalization ({result_type})",
                category="character_creation",
            )
            print(colored("[SYSTEM]", "yellow"), colored("Character JSON incomplete. Creation mode remains active.", "yellow"))
            return "needs_retry"

        if finalize_status == "error":
            finalize_error = finalize_result.get("error_message", "unknown error")
            error(
                f"CHARACTER_CREATION: Shared finalizer failed: {finalize_error}",
                category="character_creation",
            )
            return "error"

        if finalize_status != "success":
            warning(
                f"CHARACTER_CREATION: Unexpected finalizer status '{finalize_status}'",
                category="character_creation",
            )
            return "error"

        character_data = finalize_result.get("character_data")
        if not isinstance(character_data, dict):
            warning(
                "CHARACTER_CREATION: Shared finalizer returned success without character data",
                category="character_creation",
            )
            return "error"

        info(f"CHARACTER_CREATION: Detected character JSON for {character_data.get('name')}", category="character_creation")

        persist_result = persist_dm_created_character(character_data)
        if not persist_result.get("success"):
            persist_error = persist_result.get("error", "unknown persistence error")
            warning(
                f"CHARACTER_CREATION: Failed to persist character file ({persist_error})",
                category="character_creation",
            )
            return "error"

        character_name = persist_result.get("character_name") or character_data.get("name", "Unknown")
        info(f"CHARACTER_CREATION: Saved character file for {character_name}", category="character_creation")
        
        # Get creation context
        creation_context = safe_json_load(CHARACTER_CREATION_MARKER) or {}
        active_pc = creation_context.get('active_pc', '')
        current_location = creation_context.get('current_location', 'current location')
        
        # Add to party tracker
        pc_manager.add_pc(character_name)
        
        # Restore conversation history
        restore_success = restore_conversation_history()
        if restore_success:
            info("CHARACTER_CREATION: Restored conversation history", category="character_creation")
            # Reload conversation history
            conversation_history = safe_json_load("modules/conversation_history/conversation_history.json") or []
        
        # Generate and inject transition
        transition = generate_ambiguous_transition(
            character_data=character_data,
            active_pc_name=active_pc or character_name,
            location_context={"location": current_location},
        )
        
        # Add transition to conversation
        conversation_history.append({"role": "assistant", "content": transition})
        save_conversation_history(conversation_history)
        
        # Set new character as active
        pc_manager.set_active_pc(character_name)
        
        # Clean up creation marker
        if os.path.exists(CHARACTER_CREATION_MARKER):
            os.remove(CHARACTER_CREATION_MARKER)
        
        info(f"CHARACTER_CREATION: Character {character_name} creation complete. Narrative resumed.", category="character_creation")
        
        print(colored("\n[SYSTEM]", "yellow"), colored(f"Character '{character_name}' created successfully!", "green"))
        print(colored("[SYSTEM]", "yellow"), colored("Narrative thread resumed.\n", "green"))
        
        return "finalized"
        
    except json.JSONDecodeError:
        # Not valid JSON, not a character creation completion
        return "not_candidate"
    except Exception as e:
        error(f"CHARACTER_CREATION: Error processing character creation response: {e}", exception=e, category="character_creation")
        return "error"


def process_ai_response(response, party_tracker_data, location_data, conversation_history):
    global needs_conversation_history_update
    
    # TABLETOP MODE: Check if we're in character creation mode and this is the final JSON
    if is_creation_mode_active():
        creation_status = handle_character_creation_response(response, party_tracker_data, conversation_history)
        if creation_status == "finalized":
            return {"role": "assistant", "content": response}
        if creation_status == "needs_retry":
            return "creation_retry"
        if creation_status == "error":
            return "creation_error"
    
    try:
        json_content = extract_json_from_codeblock(response)
        parsed_response = json.loads(json_content)
        actions = parsed_response.get("actions", [])
        
        # --- START OF FIX: Detect levelUp action before printing narration ---
        is_levelup_action = any(action.get("action") == "levelUp" for action in actions)

        if is_levelup_action:
            debug("STATE_CHANGE: levelUp action detected. Suppressing initial narration and starting session.", category="level_up")
            # Process ONLY the levelUp action from the list to start the session.
            # This assumes the first levelUp action is the one to process.
            for action in actions:
                if action.get("action") == "levelUp":
                    # Directly call the action handler for just this action
                    return action_handler.process_action(action, party_tracker_data, location_data, conversation_history)
            # Fallback in case the loop doesn't find it, though it should.
            return None
        # --- END OF FIX ---

        # --- NEW TRANSITION LOGIC ---
        is_transition = False
        departure_narration = ""
        # Check if the response contains a transition action
        for action in parsed_response.get("actions", []):
            if action.get("action") == "transitionLocation":
                is_transition = True
                departure_narration = parsed_response.get("narration", "")
                break
        
        # If it's a transition, handle it with the special two-step process
        if is_transition:
            debug("STATE_CHANGE: Transition action detected. Holding departure narration.", category="location_transitions")

            # SURGICAL FIX: Save pre-transition response to history before processing action
            conversation_history.append({"role": "assistant", "content": response})
            save_conversation_history(conversation_history)
            debug("SUCCESS: Pre-transition assistant message saved to history", category="location_transitions")

            # Step 1: Process actions to update state (summary, party_tracker, etc.)
            actions_processed = False
            for action in parsed_response.get("actions", []):
                result = action_handler.process_action(action, party_tracker_data, location_data, conversation_history)
                actions_processed = True
                if isinstance(result, dict):
                    if result.get("needs_update"):
                        needs_conversation_history_update = True
                    # Check if we need to generate a DM response (e.g., after module creation)
                    if result.get("needs_dm_response"):
                        # Save current assistant response first
                        current_response = {"role": "assistant", "content": response}
                        conversation_history.append(current_response)
                        save_conversation_history(conversation_history)
                        
                        # Reload and generate new AI response
                        conversation_history = load_json_file("modules/conversation_history/conversation_history.json") or []
                        ai_response = get_ai_response(conversation_history)
                        return process_ai_response(ai_response, party_tracker_data, location_data, conversation_history)
                elif isinstance(result, bool) and result:
                    needs_conversation_history_update = True
            if actions_processed:
                party_tracker_data = load_json_file("party_tracker.json")
            
            # Step 2: Reload the state to get the NEW location context
            fresh_party_data = load_json_file("party_tracker.json")
            fresh_conversation_history = load_json_file(json_file) or []
            
            # Step 3: Generate the arrival narration using the new helper function
            arrival_narration = generate_arrival_narration(departure_narration, fresh_party_data, fresh_conversation_history)
            
            # <--- MODIFIED SECTION: Use the new seamless narration generator --->
            # Step 4: Blend the departure and arrival narrations into a single, cohesive story.
            full_narration = generate_seamless_transition_narration(departure_narration, arrival_narration)
            
            # Step 5: Display the final, polished narration
            print(colored("Dungeon Master:", "blue"), colored(full_narration, "blue"))
            # <--- END OF MODIFIED SECTION --->

            # Step 6: Replace the raw transition narration with the seamless version in history
            # This ensures conversation history matches what the player saw
            fresh_conversation_history = load_json_file(json_file) or []
            for i in range(len(fresh_conversation_history) - 1, -1, -1):
                if fresh_conversation_history[i].get("role") == "assistant":
                    fresh_conversation_history[i]['content'] = full_narration
                    debug("SUCCESS: Replaced raw transition narration with seamless version in history", category="location_transitions")
                    break

            save_conversation_history(fresh_conversation_history)

            return {"role": "assistant", "content": json.dumps({"narration": full_narration, "actions": []})}
        
        # --- END NEW TRANSITION LOGIC ---

        # If not a transition or levelup, proceed with normal processing
        narration = parsed_response.get("narration", "")
        sanitized_narration = sanitize_text(narration)
        
        # TABLETOP MODE: 3.3 Defer narration emission until after action processing
        # This prevents combat narration from being shown when createEncounter fails
        narration_deferred = sanitized_narration
        narration_emitted = False

        actions_processed = False
        
        # Debug: Log what actions we received
        debug(f"STATE_CHANGE: Received {len(actions)} total actions", category="character_updates")
        print(f"DEBUG: STATE_CHANGE: Received {len(actions)} total actions")
        for i, action in enumerate(actions):
            debug(f"  Action {i+1}: {action.get('action', 'unknown')}", category="character_updates")
            print(f"DEBUG:   Action {i+1}: {action.get('action', 'unknown')}")
        
        # Separate updateCharacterInfo actions from others for concurrent processing
        char_update_actions = [action for action in actions if action.get("action") == "updateCharacterInfo"]
        other_actions = [action for action in actions if action.get("action") != "updateCharacterInfo"]
        
        # TABLETOP MODE: Fail-open fallback for transitionLocation without updateTime
        # If movement occurs without explicit time advancement, inject deterministic updateTime
        has_transition = any(action.get("action") == "transitionLocation" for action in actions)
        has_update_time = any(action.get("action") == "updateTime" for action in actions)
        
        if has_transition and not has_update_time:
            # Find the transitionLocation action to get target
            transition_action = next((a for a in actions if a.get("action") == "transitionLocation"), None)
            if transition_action:
                target_location = transition_action.get("parameters", {}).get("newLocation", "")
                current_area_id = party_tracker_data.get("worldConditions", {}).get("currentAreaId", "")
                
                # Determine if cross-area transition using location graph
                is_cross_area = False
                try:
                    if location_graph and target_location in location_graph.nodes:
                        target_area_id = location_graph.nodes[target_location].get("area_id", "")
                        is_cross_area = (target_area_id != current_area_id)
                except Exception as e:
                    debug(f"STATE_SYNC: Could not determine area for location {target_location}: {e}", category="time_sync")
                    # Default to cross-area if we can't determine (safer assumption)
                    is_cross_area = True
                
                # Deterministic fallback minutes
                fallback_minutes = 20 if is_cross_area else 10
                
                # Create synthetic updateTime action
                synthetic_update_time = {
                    "action": "updateTime",
                    "parameters": {
                        "timeEstimate": fallback_minutes
                    }
                }
                
                # Insert at beginning of other_actions so time updates before transition
                other_actions.insert(0, synthetic_update_time)
                
                info(f"STATE_SYNC: Auto-applied updateTime={fallback_minutes} due to transitionLocation without updateTime (cross_area={is_cross_area})", category="time_sync")
        
        debug(f"STATE_CHANGE: Separated into {len(char_update_actions)} character updates and {len(other_actions)} other actions", category="character_updates")
        print(f"DEBUG: STATE_CHANGE: Separated into {len(char_update_actions)} character updates and {len(other_actions)} other actions")
        
        # If there are no actions at all, signal that processing is complete
        if len(actions) == 0:
            try:
                from core.managers.status_manager import status_manager
                status_manager.update_status("Ready for input", is_processing=False)
                debug("STATE_CHANGE: No actions to process, setting status to ready", category="character_updates")
            except Exception as e:
                debug(f"Could not update status: {e}", category="status")
        
        # Process character updates concurrently if there are multiple
        if len(char_update_actions) > 1:
            debug(f"STATE_CHANGE: Processing {len(char_update_actions)} character updates concurrently", category="character_updates")
            print(f"DEBUG: STATE_CHANGE: Processing {len(char_update_actions)} character updates concurrently")
            
            concurrent_start = time.time()
            with ThreadPoolExecutor(max_workers=min(4, len(char_update_actions))) as executor:
                # Submit all character updates
                future_to_action = {
                    executor.submit(action_handler.process_action, action, party_tracker_data, location_data, conversation_history): action 
                    for action in char_update_actions
                }
                
                # Collect results
                for future in as_completed(future_to_action):
                    try:
                        result = future.result()
                        actions_processed = True
                        # Handle result same as sequential processing
                        if isinstance(result, dict) and result.get("needs_update"):
                            needs_conversation_history_update = True
                        elif isinstance(result, bool) and result:
                            needs_conversation_history_update = True
                    except Exception as e:
                        action = future_to_action[future]
                        char_name = action.get("parameters", {}).get("characterName", "unknown")
                        error(f"FAILURE: Concurrent character update failed for {char_name}", exception=e, category="character_updates")
            
            concurrent_end = time.time()
            debug(f"STATE_CHANGE: Completed concurrent character updates", category="character_updates")
            print(f"DEBUG: STATE_CHANGE: Completed concurrent character updates in {concurrent_end - concurrent_start:.2f} seconds")
        
        elif char_update_actions:
            # Single character update - process normally
            for action in char_update_actions:
                result = action_handler.process_action(action, party_tracker_data, location_data, conversation_history)
                actions_processed = True
                if isinstance(result, dict) and result.get("needs_update"):
                    needs_conversation_history_update = True
                elif isinstance(result, bool) and result:
                    needs_conversation_history_update = True
        
        # Track pending archive info for delayed processing
        pending_archive_info = None
        
        # Process all other actions sequentially
        for action in other_actions:
            result = action_handler.process_action(action, party_tracker_data, location_data, conversation_history)
            actions_processed = True
            
            # Check for pending archive flag from module transitions
            if isinstance(result, dict) and result.get("response_data", {}).get("pending_archive"):
                pending_archive_info = result["response_data"]["pending_archive"]
                print(f"DEBUG: [Module Transition] Captured pending archive info: from {pending_archive_info['from_module']} to {pending_archive_info['to_module']}")
            
            # --- SIGNAL-BASED SUB-SYSTEM CONTROL ---
            # Check for special signals from the action handler that indicate a sub-system has completed.
            if isinstance(result, dict) and result.get("status") == "needs_post_combat_narration":
                # This signal means combat finished and its summary was added to the history.
                # The action_handler has already:
                # 1. Run the entire combat encounter
                # 2. Added the [COMBAT CONCLUDED...] summary to conversation_history
                # 3. Returned this signal instead of a normal response
                
                debug("STATE_CHANGE: Combat resolved. Requesting post-combat narration from AI.", category="combat_events")
                
                # We must reload the history from disk to ensure we have the combat summary.
                # This is necessary because the action_handler modified and saved the history independently.
                post_combat_history = load_json_file(json_file) or conversation_history
                ai_response_after_combat = get_ai_response(post_combat_history)
                
                # Set flag to indicate we just finished combat (for XP display fix)
                process_ai_response._just_finished_combat = True
                
                # Process the AI's post-combat response by calling this function again (recursively).
                # This ensures the post-combat narration is handled just like any other turn,
                # maintaining consistency in how we process AI responses.
                return process_ai_response(ai_response_after_combat, party_tracker_data, location_data, post_combat_history)
            # --- END SIGNAL-BASED SUB-SYSTEM CONTROL ---
            
            # C1.3: Handle explicit error status from action processing (e.g., encounter init failure)
            if isinstance(result, dict) and result.get("status") == "error":
                error_msg = result.get("error_message", "Unknown error in action processing")
                error(f"ACTION_ERROR: {error_msg}", category="action_processing")
                # Add deterministic system error to conversation instead of continuing with potentially corrupted state
                conversation_history.append({
                    "role": "system",
                    "content": f"[SYSTEM] {error_msg}"
                })
                save_conversation_history(conversation_history)
                # C1.A2: Prevent continuing normal combat narration flow after error
                # DO NOT fall through to assistant append - abort response path immediately
                return {"role": "system", "content": f"[SYSTEM] {error_msg}"}

            if isinstance(result, dict):
                if result.get("status") == "exit": return "exit"
                if result.get("status") == "restart": return "restart"
                # This check is now crucial for the level up flow
                if result.get("status") == "enter_levelup_mode":
                    return result
                if result.get("status") == "needs_response":
                    # Combat summary was added to conversation history, get AI response
                    # CRITICAL FIX: Save the current response to conversation history before getting new response
                    current_response = {"role": "assistant", "content": response}
                    conversation_history.append(current_response)
                    save_conversation_history(conversation_history)
                    
                    # Now reload and get the new AI response
                    conversation_history = load_json_file("modules/conversation_history/conversation_history.json") or []
                    ai_response = get_ai_response(conversation_history)
                    return process_ai_response(ai_response, party_tracker_data, location_data, conversation_history)
                if result.get("needs_update"): needs_conversation_history_update = True
            elif result == "exit": return "exit"
            elif isinstance(result, bool) and result: needs_conversation_history_update = True

        # TABLETOP MODE: 3.3 Emit deferred narration after successful action processing
        # This prevents combat narration from being shown when createEncounter fails
        if not narration_emitted and narration_deferred:
            print(colored("Dungeon Master:", "blue"), colored(narration_deferred, "blue"))
            narration_emitted = True

        if actions_processed:
            party_tracker_data = load_json_file("party_tracker.json")
            
            if hasattr(action_handler.process_action, 'level_up_summaries') and action_handler.process_action.level_up_summaries:
                debug(f"STATE_CHANGE: Injecting {len(action_handler.process_action.level_up_summaries)} level up summaries", category="level_up")
                
                combined_summary = "\n\n".join(action_handler.process_action.level_up_summaries)
                conversation_history.append({"role": "user", "content": combined_summary})
                save_conversation_history(conversation_history)
                
                action_handler.process_action.level_up_summaries = []
                
                ai_response = get_ai_response(conversation_history)
                return process_ai_response(ai_response, party_tracker_data, location_data, conversation_history)

        # STANDARD TURN COMPLETION: For a normal turn (no special signals or sub-systems),
        # we append the AI's response to history here in process_ai_response.
        # This centralizes history management - the main_game_loop no longer needs to handle it.
        # This ensures the history is saved atomically with the response processing,
        # preventing any possibility of the history and game state becoming out of sync.
        assistant_message = {"role": "assistant", "content": response}
        conversation_history.append(assistant_message)
        save_conversation_history(conversation_history)
        
        # DELAYED ARCHIVING: Process any pending archive after the AI response is saved
        if pending_archive_info:
            print(f"DEBUG: [Module Transition] Processing delayed archive for module: {pending_archive_info['from_module']}")
            try:
                from core.managers.campaign_manager import CampaignManager
                campaign_manager = CampaignManager()
                
                # Reload conversation history to ensure we have the travel narrative
                fresh_conversation_history = load_json_file("modules/conversation_history/conversation_history.json") or []
                
                # Archive the conversation history
                archive_success = campaign_manager._archive_conversation_history(
                    pending_archive_info['from_module'],
                    fresh_conversation_history
                )
                
                if archive_success:
                    print(f"DEBUG: [Module Transition] Successfully archived conversation history for {pending_archive_info['from_module']}")
                    info(f"SUCCESS: Archived conversation history for module: {pending_archive_info['from_module']}", category="module_management")
                    
                    # Regenerate the summary with the complete conversation history (including travel narrative)
                    print(f"DEBUG: [Module Transition] Regenerating summary with complete conversation history")
                    print(f"DEBUG: [Module Transition] Module name: {pending_archive_info['from_module']}")
                    print(f"DEBUG: [Module Transition] Conversation history length: {len(fresh_conversation_history)}")
                    
                    # Get existing visit info before regenerating
                    existing_visit_info = campaign_manager._get_module_visit_info(pending_archive_info['from_module'])
                    print(f"DEBUG: [Module Transition] Existing visit info: {existing_visit_info}")
                    
                    try:
                        summary = campaign_manager._generate_module_summary(
                            pending_archive_info['from_module'],
                            pending_archive_info.get('party_tracker_data', {}),
                            fresh_conversation_history,
                            skip_archiving=True  # Skip archiving since we just did it
                        )
                        print(f"DEBUG: [Module Transition] Summary generated successfully")
                        print(f"DEBUG: [Module Transition] Summary keys: {list(summary.keys()) if summary else 'None'}")
                    except Exception as e:
                        print(f"ERROR: [Module Transition] Failed to generate summary: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        raise
                    
                    # Update the summary file with the regenerated summary
                    summary_file = os.path.join(campaign_manager.summaries_dir, f"{pending_archive_info['from_module']}_summary_001.json")
                    summary["sequenceNumber"] = 1
                    # Preserve first visit date and increment visit count properly
                    summary["visitCount"] = existing_visit_info.get("visitCount", 0) + 1
                    summary["firstVisitDate"] = existing_visit_info.get("firstVisitDate") or datetime.now().isoformat()
                    summary["lastVisitDate"] = datetime.now().isoformat()
                    
                    print(f"DEBUG: [Module Transition] Saving regenerated summary to: {summary_file}")
                    print(f"DEBUG: [Module Transition] Visit count: {summary['visitCount']}, Last visit: {summary['lastVisitDate']}")
                    
                    try:
                        safe_json_dump(summary, summary_file)
                        print(f"DEBUG: [Module Transition] Summary saved successfully")
                        
                        # Verify the file was written
                        if os.path.exists(summary_file):
                            file_stat = os.stat(summary_file)
                            print(f"DEBUG: [Module Transition] Summary file size: {file_stat.st_size} bytes")
                            print(f"DEBUG: [Module Transition] Summary file modified time: {datetime.fromtimestamp(file_stat.st_mtime)}")
                        else:
                            print(f"ERROR: [Module Transition] Summary file doesn't exist after save!")
                    except Exception as e:
                        print(f"ERROR: [Module Transition] Failed to save summary: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        raise
                    
                    print(f"DEBUG: [Module Transition] Summary regenerated and saved for {pending_archive_info['from_module']}")
                    info(f"SUCCESS: Regenerated summary with travel narrative for module: {pending_archive_info['from_module']}", category="module_management")
                else:
                    print(f"DEBUG: [Module Transition] Failed to archive conversation history for {pending_archive_info['from_module']}")
                    warning(f"FAILURE: Could not archive conversation history for module: {pending_archive_info['from_module']}", category="module_management")
                    
            except Exception as e:
                print(f"ERROR: Failed to process delayed archive: {str(e)}")
                print(f"ERROR: Module name was: {pending_archive_info.get('from_module', 'UNKNOWN')}")
                print(f"ERROR: Pending archive info: {pending_archive_info}")
                import traceback
                traceback.print_exc()
                error(f"FAILURE: Delayed archive processing failed for {pending_archive_info.get('from_module', 'UNKNOWN')}", exception=e, category="module_management")
        
        return assistant_message

    except json.JSONDecodeError as e:
        print(f"Error: Unable to parse AI response as JSON: {e}")
        print(f"Problematic response: {response}")
        sanitized_response = sanitize_text(response)
        print(colored("Dungeon Master:", "blue"), colored(sanitized_response, "blue"))
        # Even in error case, append to history
        assistant_message = {"role": "assistant", "content": response}
        conversation_history.append(assistant_message)
        save_conversation_history(conversation_history)
        return assistant_message


def save_conversation_history(history):
    try:
        # Check if we should compress before saving
        compressor = IncrementalLocationCompressor()
        
        # Check compression conditions (15+ valid pairs at current location)
        if compressor.should_compress(history):
            debug("Compression conditions met - applying incremental compression", category="compression")
            
            # Apply compression (returns new list if successful)
            compressed_history = compressor.apply_compression_to_list(history)
            if compressed_history:
                history = compressed_history
                info("Conversation history compressed successfully", category="compression")
            else:
                debug("Compression not applied - conditions not fully met", category="compression")
        
        # Save the (possibly compressed) history
        safe_json_dump(history, json_file)
    except Exception as e:
        error(f"FAILURE: Failed to save conversation history", exception=e, category="file_operations")

def get_ai_response(conversation_history, validation_retry_count=0, transient_correction=None):
    global should_inject_creation_prompt
    status_processing_ai()
    
    # Import action predictor and config
    from utils.action_predictor import predict_actions_required, extract_actual_actions, log_prediction_accuracy
    from config import ENABLE_INTELLIGENT_ROUTING, DM_MINI_MODEL, DM_FULL_MODEL, MAX_VALIDATION_RETRIES
    from config import USE_GPT5_MODELS, GPT5_MINI_MODEL, GPT5_FULL_MODEL
    
    # Import provider factory for multi-provider support
    from utils.ai_client_factory import (
        get_chat_model_name, 
        handle_provider_error, 
        get_fallback_notification,
        create_chat_client
    )
    
    # Get the last user message for action prediction
    user_input = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            user_input = msg.get("content", "")
            break
    
    # Check if module creation prompt is present in user input
    has_module_creation_prompt = "You are a master storyteller, cartographer of myth" in user_input
    
    # Predict if actions will be required (unless we're in a validation retry or module creation prompt)
    if validation_retry_count == 0 and not has_module_creation_prompt:
        prediction = predict_actions_required(user_input)
    elif has_module_creation_prompt:
        # Force full model when module creation prompt is present
        prediction = {"requires_actions": True, "reason": "Module creation prompt detected - using full model"}
    else:
        # On validation retry, force full model and skip prediction
        prediction = {"requires_actions": True, "reason": "Validation retry - using full model"}
    
    # Determine which model to use based on intelligent routing and validation retry
    if ENABLE_INTELLIGENT_ROUTING and validation_retry_count == 0 and not has_module_creation_prompt:
        # Use prediction to determine model (Phase 2 of token optimization)
        selected_model = DM_MINI_MODEL if not prediction["requires_actions"] else DM_FULL_MODEL
        
        # Log the routing decision
        routing_info = "MINI MODEL" if not prediction["requires_actions"] else "FULL MODEL"
        print(f"DEBUG: MODEL ROUTING - Selected: {routing_info} (Prediction: {prediction['requires_actions']}, Reason: {prediction['reason']})")
    else:
        # Use full model (default behavior or validation retry)
        selected_model = DM_FULL_MODEL
        if validation_retry_count > 0:
            print(f"DEBUG: MODEL ROUTING - VALIDATION RETRY {validation_retry_count}: Using FULL MODEL")
        else:
            print(f"DEBUG: MODEL ROUTING - Intelligent routing disabled, using FULL MODEL")
    
    # Track model selection decision for quality control
    print(f"DEBUG: Logging model selection - model={selected_model}, retry={validation_retry_count}")
    try:
        os.makedirs("debug/quality_control", exist_ok=True)
        model_selection_record = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input[:200],  # First 200 chars
            "prediction": prediction if validation_retry_count == 0 and not has_module_creation_prompt else None,
            "selected_model": selected_model,
            "routing_reason": prediction.get("reason", "Validation retry or module creation") if validation_retry_count == 0 else f"Validation retry {validation_retry_count}",
            "validation_retry_count": validation_retry_count,
            "has_module_creation_prompt": has_module_creation_prompt,
            "intelligent_routing_enabled": ENABLE_INTELLIGENT_ROUTING
        }
        
        # Append to model selection log
        model_log_path = "debug/quality_control/model_selection.jsonl"
        with open(model_log_path, "a", encoding="utf-8") as f:
            json.dump(model_selection_record, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"ERROR: Failed to log model selection: {e}")
        debug(f"Failed to log model selection: {e}", category="ai_routing")
    
    # Check if compression is enabled and apply if needed
    try:
        from model_config import COMPRESSION_ENABLED
        if COMPRESSION_ENABLED:
            from pathlib import Path

            # Save conversation to temp file
            temp_file = Path("/tmp/temp_conversation_for_api.json")
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_history, f, indent=2, ensure_ascii=False)

            # TABLETOP MODE: Use multi-PC aware compressor when in multi-PC mode
            # Detect multi-PC mode by checking for active_pc tags in conversation history
            use_multi_pc_compressor = False
            try:
                from config import MULTIPLAYER_MODE
                if MULTIPLAYER_MODE:
                    # Check if any messages have active_pc tags (indicates multi-PC mode)
                    has_active_pc_tags = any(
                        msg.get("active_pc") for msg in conversation_history 
                        if isinstance(msg, dict)
                    )
                    if has_active_pc_tags:
                        use_multi_pc_compressor = True
            except ImportError:
                use_multi_pc_compressor = False

            if use_multi_pc_compressor:
                # Use multi-PC aware compressor for tabletop mode
                from utils.compression.multi_pc_conversation_compressor import MultiPCConversationCompressor
                compressor = MultiPCConversationCompressor(inject_module_creation=should_inject_creation_prompt)
                debug("Using multi-PC conversation compressor", category="compression")
            else:
                # Use standard parallel compressor for single-PC mode
                from utils.compression.conversation_compressor_parallel import ParallelConversationCompressor
                compressor = ParallelConversationCompressor(inject_module_creation=should_inject_creation_prompt)

            # Compress using selected compressor
            messages_to_send = compressor.process_conversation_history(str(temp_file))
            
            # TABLETOP MODE: Strip active_pc from messages before API call to avoid provider compatibility issues
            # The active_pc field is used for multi-PC compression but should not be sent to the API
            for msg in messages_to_send:
                if isinstance(msg, dict) and "active_pc" in msg:
                    del msg["active_pc"]
            
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
                
            print(f"DEBUG: Parallel compression applied successfully")
        else:
            messages_to_send = conversation_history
    except Exception as e:
        # If compression fails, use original history
        print(f"WARNING: Compression failed: {e}")
        messages_to_send = conversation_history
    
    # TABLETOP MODE: Ensure active_pc is stripped from all messages before API call
    # This covers both the non-compression path and the exception fallback path
    for msg in messages_to_send:
        if isinstance(msg, dict) and "active_pc" in msg:
            del msg["active_pc"]

    # TABLETOP MODE: Prompt singularity guard.
    # Ensure exactly one canonical main system prompt in outbound payload,
    # removing legacy prompt variants and duplicate canonical copies.
    try:
        with open("prompts/system_prompt_compressed.txt", "r", encoding="utf-8") as prompt_file:
            canonical_prompt_text = prompt_file.read()
        messages_to_send = dedupe_main_system_prompt_messages(messages_to_send, canonical_prompt_text)
    except Exception as e:
        warning(
            f"PROMPT_GUARD: Failed to apply main prompt singularity dedupe; continuing fail-open: {e}",
            category="conversation_management"
        )
    
    # TABLETOP MODE: Step 3.2 - Inject transient correction note without polluting conversation history
    # This correction is passed to the AI for this request only, not persisted
    if transient_correction:
        messages_to_send = messages_to_send + [{"role": "user", "content": transient_correction}]
        debug(f"RETRY: Injected transient correction note (not persisted)", category="ai_validation")
    
    # Export main conversation messages for debugging
    with open("main_conversation_messages_to_api.json", "w", encoding="utf-8") as f:
        json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
    print(f"DEBUG: [MAIN CONVERSATION] Exported conversation messages to main_conversation_messages_to_api.json")
    
    # Generate response with selected model
    # Get provider-aware model name (supports OpenRouter and OpenAI)
    provider_model = get_chat_model_name()
    debug(f"Using AI model: {provider_model} (selected_model: {selected_model})", category="ai_provider")
    
    if USE_GPT5_MODELS:
        # GPT-5: Always use mini, no temperature/max_tokens
        selected_model = GPT5_MINI_MODEL
        
        # Handle retry logic for GPT-5 - switch to full model after failures
        if validation_retry_count >= 4:
            selected_model = GPT5_FULL_MODEL
            print(f"DEBUG: GPT-5 - Switching to full model after {validation_retry_count} retries")
        
        print(f"DEBUG: [MAIN.PY] Using GPT-5 model: {selected_model}")
        
        try:
            response = client.chat.completions.create(
                model=selected_model,
                messages=messages_to_send  # Use potentially compressed messages
            )
        except Exception as api_error:
            # Check if we should fallback to OpenAI
            error_result = handle_provider_error(api_error, context="DM response generation (GPT-5)")
            
            if error_result['should_fallback']:
                warning(f"Falling back to OpenAI due to error: {api_error}", category="ai_provider")
                fallback_client = create_chat_client(use_fallback=True)
                
                # Retry with fallback client using OpenAI model
                response = fallback_client.chat.completions.create(
                    model=GPT5_MINI_MODEL,
                    messages=messages_to_send
                )
                
                # Check for fallback notification
                fallback_msg = get_fallback_notification()
                if fallback_msg:
                    messages_to_send.append({"role": "system", "content": fallback_msg})
            else:
                raise

        # Log API call to master log
        try:
            from utils.api_logger import log_api_call
            log_api_call("main_dm", messages_to_send, response,
                        metadata={"retry_count": validation_retry_count, "branch": "gpt5"})
        except Exception as e:
            print(f"[API_LOG] Warning: Failed to log main DM call: {e}")

        # Track token usage
        if USAGE_TRACKING_AVAILABLE:
            try:
                track_response(response)
            except:
                pass
    else:
        # GPT-4.1 or OpenRouter: Use existing logic with temperature
        # Use provider-aware model if different from selected_model
        actual_model = provider_model if provider_model != selected_model else selected_model
        print(f"DEBUG: [MAIN.PY] Using model: {actual_model}")
        
        try:
            response = client.chat.completions.create(
                model=actual_model,
                temperature=TEMPERATURE,
                messages=messages_to_send  # Use potentially compressed messages
            )
        except Exception as api_error:
            # Check if we should fallback to OpenAI
            error_result = handle_provider_error(api_error, context="DM response generation (GPT-4.1/OpenRouter)")
            
            if error_result['should_fallback']:
                warning(f"Falling back to OpenAI due to error: {api_error}", category="ai_provider")
                fallback_client = create_chat_client(use_fallback=True)
                
                # Retry with fallback client using OpenAI model
                response = fallback_client.chat.completions.create(
                    model=selected_model,  # Use original selected_model for fallback
                    temperature=TEMPERATURE,
                    messages=messages_to_send
                )
                
                # Check for fallback notification
                fallback_msg = get_fallback_notification()
                if fallback_msg:
                    messages_to_send.append({"role": "system", "content": fallback_msg})
            else:
                raise

        # Log API call to master log
        try:
            from utils.api_logger import log_api_call
            log_api_call("main_dm", messages_to_send, response,
                        metadata={"temperature": TEMPERATURE, "retry_count": validation_retry_count, "branch": "gpt4.1"})
        except Exception as e:
            print(f"[API_LOG] Warning: Failed to log main DM call: {e}")

        # Track token usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(response, context={'endpoint': 'main_dm', 'purpose': 'primary_game_response', 'model': actual_model})
            except:
                pass
    content = response.choices[0].message.content.strip()
    
    # Extract actual actions from the response for accuracy tracking (only on initial attempt)
    if validation_retry_count == 0:
        actual_actions = extract_actual_actions(content)
        # Log prediction accuracy
        log_prediction_accuracy(user_input, prediction, actual_actions)
        
        # Track model selection result for quality control
        try:
            # Update the model selection record with actual outcome
            model_result_record = {
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input[:200],
                "selected_model": selected_model,
                "prediction": prediction,
                "actual_actions": actual_actions,
                "prediction_correct": bool(actual_actions) == prediction["requires_actions"],
                "response_length": len(content)
            }
            
            # Append to model results log
            results_log_path = "debug/quality_control/model_results.jsonl"
            with open(results_log_path, "a", encoding="utf-8") as f:
                json.dump(model_result_record, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            debug(f"Failed to log model result: {e}", category="ai_routing")
    
    # The sanitization line that was here has been removed.
    # We now pass the raw, untouched JSON string to the next function.
    
    # Log training data - complete conversation history and AI response
    # DISABLED: Training data collection
    # try:
    #     log_complete_interaction(conversation_history, content)
    # except Exception as e:
    #     print(f"Warning: Could not log training data: {e}")
    
    return content

def ensure_main_system_prompt(conversation_history, main_system_prompt_text):
    """
    Ensure the main system prompt is first in the conversation history.
    This removes any existing instances of the main prompt and adds it at the beginning.
    """
    return dedupe_main_system_prompt_messages(conversation_history, main_system_prompt_text)


def dedupe_main_system_prompt_messages(conversation_history, main_system_prompt_text):
    """Deduplicate legacy/canonical main prompts and keep one canonical copy first."""
    legacy_prompt_identifiers = [
        "These are Ashiralis's Sowhains' game rules",
        "## Section 1: Core Foundation",
        "You are a world-class 5th edition Dungeon Master",
    ]

    canonical_prompt_start = ""
    if isinstance(main_system_prompt_text, str) and main_system_prompt_text.strip():
        canonical_prompt_start = main_system_prompt_text[:50]

    fallback_canonical_start = "You are the Dungeon Master for the world's most popular roleplaying game, 5th Edition."

    deduped_history = []
    preserved_main_prompt = None

    for msg in conversation_history:
        if not isinstance(msg, dict):
            continue

        if msg.get("role") != "system":
            deduped_history.append(msg)
            continue

        content = msg.get("content", "")
        if not isinstance(content, str):
            deduped_history.append(msg)
            continue

        is_canonical_prompt = False
        if canonical_prompt_start and content.startswith(canonical_prompt_start):
            is_canonical_prompt = True
        elif content.startswith(fallback_canonical_start[:50]):
            is_canonical_prompt = True

        is_legacy_prompt = any(content.startswith(prefix) for prefix in legacy_prompt_identifiers)

        if is_canonical_prompt:
            if preserved_main_prompt is None:
                preserved_main_prompt = content
            continue

        if is_legacy_prompt:
            debug(
                f"Removing legacy main system prompt starting with: {content[:50]}...",
                category="conversation_management"
            )
            continue

        deduped_history.append(msg)

    if isinstance(main_system_prompt_text, str) and main_system_prompt_text.strip():
        canonical_prompt = main_system_prompt_text
    elif preserved_main_prompt is not None:
        canonical_prompt = preserved_main_prompt
    else:
        return deduped_history

    return [{"role": "system", "content": canonical_prompt}] + deduped_history

def order_conversation_messages(conversation_history, main_system_prompt_text):
    """Order conversation messages with main system prompt first, followed by other system prompts"""
    main_prompt = None
    other_system_prompts = []
    non_system_messages = []

    for msg in conversation_history:
        if msg["role"] == "system":
            if msg["content"].startswith(main_system_prompt_text[:50]):
                main_prompt = msg
            else:
                other_system_prompts.append(msg)
        else:
            non_system_messages.append(msg)

    # Reconstruct with proper order
    ordered_history = []
    if main_prompt:
        ordered_history.append(main_prompt)
    ordered_history.extend(other_system_prompts)
    ordered_history.extend(non_system_messages)
    
    return ordered_history

def check_all_modules_plot_completion():
    """
    Check plot completion status for ALL available modules, not just the current one.
    Returns a dictionary with completion data for all modules.
    """
    import os
    import glob
    
    # Comprehensive module plot completion check (verbose logging removed)
    
    modules_dir = "modules"
    all_modules_data = {
        "modules_checked": [],
        "all_complete": True,
        "completion_summary": {}
    }
    
    if not os.path.exists(modules_dir):
        warning("FILE_OP: No modules directory found", category="module_management")
        return all_modules_data
    
    # Find all valid module directories
    available_modules = []
    for item in os.listdir(modules_dir):
        module_path = os.path.join(modules_dir, item)
        if os.path.isdir(module_path) and not item.startswith('.') and item not in ['campaign_archives', 'campaign_summaries']:
            # Check if this directory has area JSON files (indicating it's a valid module)
            area_files = []
            
            # Check root directory (legacy structure)
            try:
                root_area_files = [f for f in os.listdir(module_path) 
                                 if os.path.isfile(os.path.join(module_path, f)) 
                                 and f.endswith('.json') 
                                 and len(f.split('.')[0]) <= 7  # Area codes like HH001, G001, SR001
                                 and not f.startswith('map_') 
                                 and not f.startswith('plot_')
                                 and not f.startswith('party_')
                                 and not f.startswith('module_')
                                 and f not in ['campaign.json', 'world_registry.json', 'module_context.json']]
                area_files.extend(root_area_files)
            except Exception as e:
                error(f"FAILURE: Error checking root area files for {item}", exception=e, category="module_management")
            
            # Check areas/ subdirectory (new structure)
            areas_subdir = os.path.join(module_path, 'areas')
            if os.path.exists(areas_subdir) and os.path.isdir(areas_subdir):
                try:
                    subdir_area_files = [f for f in os.listdir(areas_subdir) 
                                       if os.path.isfile(os.path.join(areas_subdir, f)) 
                                       and f.endswith('.json') 
                                       and len(f.split('.')[0]) <= 7  # Area codes
                                       and not f.startswith('map_') 
                                       and not f.startswith('plot_')
                                       and not f.startswith('party_')
                                       and not f.startswith('module_')]
                    area_files.extend(subdir_area_files)
                except Exception as e:
                    error(f"FAILURE: Error checking areas subdirectory for {item}", exception=e, category="module_management")
            
            if area_files:
                available_modules.append(item)
    
    # Found modules: {available_modules} (consolidated logging)
    
    # Check plot completion for each module
    for module_name in available_modules:
        module_path_manager = ModulePathManager(module_name)
        plot_file_path = module_path_manager.get_plot_path()
        
        # Checking plot completion for module '{module_name}' at {plot_file_path}
        
        try:
            plot_data = load_json_file(plot_file_path)
            
            if plot_data and "plotPoints" in plot_data:
                # Only count main plot points (PP), not side quests (SQ)
                main_plots = [p for p in plot_data["plotPoints"] if p.get("id", "").startswith("PP")]
                total_plots = len(main_plots)
                completed_plots = 0
                
                for plot_point in main_plots:
                    status = plot_point.get("status", "unknown")
                    plot_id = plot_point.get("id", "unknown")
                    
                    if status == "completed":
                        completed_plots += 1
                
                # Module is complete when all main plots (PP) are done, side quests (SQ) are optional
                module_complete = completed_plots == total_plots and total_plots > 0
                
                all_modules_data["completion_summary"][module_name] = {
                    "total_plots": total_plots,
                    "completed_plots": completed_plots,
                    "is_complete": module_complete,
                    "plot_file_exists": True
                }
                
                if not module_complete:
                    all_modules_data["all_complete"] = False
                
                # Module {module_name} completion: {completed_plots}/{total_plots} ({module_complete})
                
            else:
                debug(f"STATE_CHANGE: Module {module_name} has no plot data or plotPoints", category="module_management")
                all_modules_data["completion_summary"][module_name] = {
                    "total_plots": 0,
                    "completed_plots": 0,
                    "is_complete": False,
                    "plot_file_exists": False
                }
                all_modules_data["all_complete"] = False
                
        except Exception as e:
            error(f"FAILURE: Error loading plot data for module {module_name}", exception=e, category="module_management")
            all_modules_data["completion_summary"][module_name] = {
                "total_plots": 0,
                "completed_plots": 0,
                "is_complete": False,
                "plot_file_exists": False,
                "error": str(e)
            }
            all_modules_data["all_complete"] = False
    
    all_modules_data["modules_checked"] = available_modules
    
    # Module completion check: {len(available_modules)} modules, all complete: {all_modules_data['all_complete']}
    
    return all_modules_data


def _normalize_combat_command_input(raw_input_text):
    """Normalize user input for combat command guard checks."""
    raw_input = (raw_input_text or "").strip()
    clean_input = raw_input

    # Handle tagged multi-PC inputs like "[Character]: /command"
    if raw_input.startswith("[") and "]:" in raw_input:
        parts = raw_input.split("]:", 1)
        if len(parts) == 2:
            clean_input = parts[1].strip()

    return clean_input


def _is_combat_only_command(clean_input):
    """Return True if input is a combat-only command or command form."""
    cmd = (clean_input or "").lower()

    combat_commands = [
        "/init", "\\init", "init",
        "/end", "\\end", "end turn", "end",
        "/pass", "\\pass",
        "/att", "\\att", "attack",
        "/dmg", "\\dmg",
        "/end_combat", "\\end_combat", "exit combat",
        "/switch_pc_focus"
    ]

    return (
        cmd in combat_commands
        or cmd.startswith("/init ")
        or cmd.startswith("\\init ")
        or cmd.startswith("/att ")
        or cmd.startswith("\\att ")
        or cmd.startswith("/dmg ")
        or cmd.startswith("\\dmg ")
        or cmd.startswith("/end ")
        or cmd.startswith("\\end ")
        or cmd.startswith("/pass ")
        or cmd.startswith("\\pass ")
    )


def get_noncombat_guard_message(raw_input_text, active_combat_encounter):
    """Return deterministic system guidance for combat-only commands outside combat."""
    clean_input = _normalize_combat_command_input(raw_input_text)
    cmd = clean_input.lower()

    if active_combat_encounter or not _is_combat_only_command(clean_input):
        return None

    if cmd.startswith("/init") or cmd.startswith("\\init") or cmd == "init":
        return "[skipTTS] Dungeon Master: [SYSTEM] No active combat encounter. Use /init after combat has started. To start combat, describe your party approaching or encountering enemies."
    if (
        cmd in ["/end", "\\end", "end turn", "end", "/pass", "\\pass"]
        or cmd.startswith("/end ")
        or cmd.startswith("\\end ")
        or cmd.startswith("/pass ")
        or cmd.startswith("\\pass ")
    ):
        return "[skipTTS] Dungeon Master: [SYSTEM] No active combat encounter. The /end command is used to end your turn during combat."
    if cmd in ["/att", "\\att", "attack"] or cmd.startswith("/att ") or cmd.startswith("\\att "):
        return "[skipTTS] Dungeon Master: [SYSTEM] No active combat encounter. Use /att after combat has started with an enemy."
    if cmd in ["/dmg", "\\dmg"] or cmd.startswith("/dmg ") or cmd.startswith("\\dmg "):
        return "[skipTTS] Dungeon Master: [SYSTEM] No active combat encounter. Use /dmg after hitting an enemy during combat."
    if cmd in ["/end_combat", "\\end_combat", "exit combat"]:
        return "[skipTTS] Dungeon Master: [SYSTEM] No active combat encounter to end."
    if cmd == "/switch_pc_focus":
        return "[skipTTS] Dungeon Master: [SYSTEM] No active combat encounter. Use /switch_pc_focus during combat to switch focus between party members."

    return "[skipTTS] Dungeon Master: [SYSTEM] That command is only available during active combat."


def _get_new_pc_creation_guidance_message():
    """Return deterministic guidance for dedicated player-character creation flow."""
    return (
        "[skipTTS] Dungeon Master: [SYSTEM] Brand-new player characters cannot be created "
        "through normal gameplay chat. Use the dedicated creation flow instead. In the web "
        "UI, open Manage Party and choose Create with DM or Roll Your Own."
    )


def extract_novel_update_party_npc_names(response_text, party_tracker_data):
    """Extract novel identity names from updatePartyNPCs actions in an AI response."""
    try:
        response_data = json.loads(response_text)
    except (TypeError, json.JSONDecodeError):
        return []

    actions = response_data.get("actions", [])
    if not isinstance(actions, list):
        return []

    known_names = set()
    for member in (party_tracker_data or {}).get("partyMembers", []):
        member_name = str(member).strip().lower()
        if member_name:
            known_names.add(member_name)

    for party_npc in (party_tracker_data or {}).get("partyNPCs", []):
        if isinstance(party_npc, dict):
            npc_name = str(party_npc.get("name", "")).strip().lower()
        else:
            npc_name = str(party_npc).strip().lower()
        if npc_name:
            known_names.add(npc_name)

    novel_names = []
    seen_novel = set()

    for action in actions:
        if not isinstance(action, dict) or action.get("action") != "updatePartyNPCs":
            continue

        params = action.get("parameters", {})
        if not isinstance(params, dict):
            continue

        candidate_names = []

        npc_param = params.get("npc")
        if isinstance(npc_param, dict):
            candidate_names.append(npc_param.get("name"))
        elif isinstance(npc_param, str):
            candidate_names.append(npc_param)

        add_param = params.get("add")
        if isinstance(add_param, str):
            candidate_names.append(add_param)
        elif isinstance(add_param, list):
            for item in add_param:
                if isinstance(item, str):
                    candidate_names.append(item)
                elif isinstance(item, dict):
                    candidate_names.append(item.get("name"))

        for candidate in candidate_names:
            normalized_candidate = str(candidate or "").strip().lower()
            if not normalized_candidate:
                continue
            if normalized_candidate in known_names:
                continue
            if normalized_candidate in seen_novel:
                continue

            seen_novel.add(normalized_candidate)
            novel_names.append(str(candidate).strip())

    return novel_names


def get_new_pc_creation_guard_message(raw_input_text, party_tracker_data):
    """Return deterministic system guidance for brand-new PC creation requests in gameplay chat."""
    if is_creation_mode_active():
        return None

    clean_input = _normalize_combat_command_input(raw_input_text)
    if not clean_input:
        return None

    text = clean_input.lower()

    # TABLETOP MODE: Conservative exclusion list so NPC recruitment remains unaffected.
    npc_recruitment_markers = [
        "join us",
        "who can you spare",
        "can anyone help",
        "anyone help",
        "need backup",
        "npc",
        "companion",
        "hireling",
        "follower",
    ]
    if any(marker in text for marker in npc_recruitment_markers):
        return None

    # TABLETOP MODE: Explicit high-confidence phrases for brand-new player creation intent.
    explicit_new_pc_phrases = [
        "create another player character",
        "create a new player character",
        "add another player character",
        "add a new player character",
        "make another player character",
        "make a new player character",
        "create another pc",
        "create a new pc",
        "add another pc",
        "add a new pc",
        "make another pc",
        "make a new pc",
        "roll up another player character",
        "roll up a new player character",
        "roll up another pc",
        "roll up a new pc",
    ]
    if any(phrase in text for phrase in explicit_new_pc_phrases):
        return _get_new_pc_creation_guidance_message()

    # TABLETOP MODE: Fallback detection requires explicit creation verbs plus explicit PC terms.
    has_creation_verb = bool(re.search(r"\b(create|add|make|build|generate|roll\s+up)\b", text))
    has_pc_target = bool(
        re.search(
            r"\b(player\s+character|pc|new\s+character|another\s+character|new\s+player|another\s+player)\b",
            text,
        )
    )
    if has_creation_verb and has_pc_target:
        # If any known character is named directly, treat this as likely existing-character context.
        known_party_members = [
            str(name).lower() for name in (party_tracker_data or {}).get("partyMembers", []) if name
        ]
        if any(member_name in text for member_name in known_party_members):
            return None

        return _get_new_pc_creation_guidance_message()

    return None


def get_new_pc_creation_retry_guard_message(user_input_text, ai_response_content, party_tracker_data):
    """Detect retry-loop new-PC misroutes and return deterministic creation guidance."""
    if is_creation_mode_active():
        return None

    novel_names = extract_novel_update_party_npc_names(ai_response_content, party_tracker_data)
    if not novel_names:
        return None

    # Reuse explicit Step 3.1 guard first.
    primary_guard_msg = get_new_pc_creation_guard_message(user_input_text, party_tracker_data)
    if primary_guard_msg:
        return primary_guard_msg

    text = _normalize_combat_command_input(user_input_text).lower()
    if not text:
        return None

    # Keep NPC-recruitment intents out of this redirect path.
    npc_recruitment_markers = [
        "join us",
        "who can you spare",
        "can anyone help",
        "anyone help",
        "need backup",
        "npc",
        "companion",
        "hireling",
        "follower",
    ]
    if any(marker in text for marker in npc_recruitment_markers):
        return None

    # Step 3.2: Catch player-identity conversion language that can still misroute.
    has_pc_term = bool(re.search(r"\b(player\s+character|pc)\b", text))
    has_creation_or_conversion_verb = bool(
        re.search(r"\b(create|add|make|build|generate|roll\s+up|turn|convert|promote|become)\b", text)
    )
    has_identity_conversion_phrase = (
        "as a player character" in text
        or "into a player character" in text
        or "as a pc" in text
        or "into a pc" in text
    )

    if has_pc_term and (has_creation_or_conversion_verb or has_identity_conversion_phrase):
        return _get_new_pc_creation_guidance_message()

    return None


def get_validation_retry_exhaustion_message():
    """Return deterministic fail-closed message for validation retry exhaustion."""
    return (
        "[SYSTEM] Unable to generate a valid response after multiple attempts. "
        "The game state may be inconsistent. Please try a different action or restart the session."
    )


# TABLETOP MODE: TTS scope marker helpers for suppressing TTS in non-narrative flows
def _should_emit_tts_markers():
    """Check if stdout supports TTS scope markers (web mode only)."""
    return getattr(sys.stdout, "supports_tts_scope_markers", False)


def _emit_tts_scope(enable_block):
    """Emit TTS scope control marker if in web mode."""
    if _should_emit_tts_markers():
        if enable_block:
            print("[TTS_BLOCK_ON]")
        else:
            print("[TTS_BLOCK_OFF]")


class _tts_block_scope:
    """Context manager for TTS block scope markers."""
    def __enter__(self):
        _emit_tts_scope(True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        _emit_tts_scope(False)


def main_game_loop():
    global needs_conversation_history_update, should_inject_creation_prompt

    # Ensure debug directories and files exist
    import os
    os.makedirs("debug/logs", exist_ok=True)
    os.makedirs("debug/api_captures", exist_ok=True)
    os.makedirs("debug/combat", exist_ok=True)

    # Create prompt_validation.json if it doesn't exist
    if not os.path.exists("debug/logs/prompt_validation.json"):
        with open("debug/logs/prompt_validation.json", "w") as f:
            f.write("[]")  # Initialize with empty array

    # Initialize companion memories from journal if needed
    try:
        from core.memories.initialize_memories import check_and_initialize_on_startup
        check_and_initialize_on_startup()
    except Exception as e:
        debug(f"Could not initialize memories (non-fatal): {e}", category="startup")

    # Check if first-time setup is needed
    try:
        from utils.startup_wizard import startup_required, run_startup_sequence

        if startup_required():
            print("[D20] Welcome to your 5th Edition Adventure! [D20]")
            print("It looks like this is your first time, or you need to set up a character.")
            print("Let's get you ready for adventure!\n")

            # TABLETOP MODE: Suppress TTS during startup/setup flow
            with _tts_block_scope():
                success = run_startup_sequence()
            if not success:
                print("[ERROR] Setup was cancelled or failed. Cannot start game loop.")
                return
    except Exception as e:
        error(f"FAILURE: Startup wizard failed", exception=e, category="startup")
        return

    # TABLETOP MODE: Recover previously poisoned character-creation sessions
    # so restart does not re-enter a dead correction loop.
    try:
        recovery_result = recover_poisoned_creation_session_on_startup()
        if recovery_result.get("recovered"):
            info(
                "CHARACTER_CREATION: Recovered poisoned creation session on startup",
                category="character_creation",
            )
    except Exception as e:
        warning(
            f"CHARACTER_CREATION: Startup recovery check failed: {e}",
            category="character_creation",
        )

    # --- START: COMBAT RESUMPTION LOGIC ---
    party_tracker_data = load_json_file("party_tracker.json")
    combat_was_resumed = False  # Track if we resumed from combat

    # Initialize variables needed in main loop for both paths (combat resume and normal startup)
    module_name = party_tracker_data.get("module", "").replace(" ", "_") if party_tracker_data else ""
    path_manager = ModulePathManager(module_name)
    debug(f"INITIALIZATION: Path manager initialized for module: '{module_name}'", category="module_management")

    # Reload global location_graph to ensure it's current for the active module
    global location_graph
    print("DEBUG: [LocationGraph] Reloading location graph for current module...")
    location_graph = LocationGraph()
    location_graph.load_module_data()
    print(f"DEBUG: [LocationGraph] Reload complete. Total nodes: {len(location_graph.nodes)}, Total edges: {sum(len(edges) for edges in location_graph.edges.values())}")
    debug(f"INITIALIZATION: Location graph reloaded with {len(location_graph.nodes)} nodes", category="module_management")
    
    # Load validation prompt for both paths - needed in main loop
    validation_prompt_text = load_validation_prompt()
    debug("INITIALIZATION: Validation prompt loaded for both paths", category="initialization")
    
    # Load main system prompt for both paths - also needed in main loop
    # Canonical runtime authority: compressed prompt is the live narrator source.
    with open("prompts/system_prompt_compressed.txt", "r", encoding="utf-8") as file:
        main_system_prompt_text = file.read()
    debug("INITIALIZATION: Main system prompt loaded for both paths", category="initialization")
    
    # TABLETOP MODE: Automatic stale recap cleanup at startup for both history files.
    # Prevents recap constraint accumulation that can block normal gameplay actions.
    # Runs BEFORE combat/non-combat branching to ensure cleanup always occurs.
    cleanup_results = cleanup_history_files(apply_changes=True)
    for cleanup_result in cleanup_results:
        history_name = os.path.basename(cleanup_result.get("path", "history"))
        status = cleanup_result.get("status", "error")
        removed_count = cleanup_result.get("removed_count", 0)

        if status == "ok":
            if removed_count > 0:
                debug(
                    f"STATE_CHANGE: Removed {removed_count} stale recap messages from {history_name}",
                    category="session_management"
                )
        elif status == "missing":
            debug(
                f"STATE_CHANGE: Skipped stale recap cleanup for missing file {history_name}",
                category="session_management"
            )
        else:
            warning(
                f"STATE_CHANGE: Stale recap cleanup degraded for {history_name}: {cleanup_result.get('error', 'unknown error')}",
                category="session_management"
            )
    
    if party_tracker_data and party_tracker_data["worldConditions"].get("activeCombatEncounter"):
        active_encounter_id = party_tracker_data["worldConditions"]["activeCombatEncounter"]
        print(colored(f"[SYSTEM] Active combat encounter '{active_encounter_id}' detected. Resuming combat...", "yellow"))
        combat_was_resumed = True  # Mark that we're resuming from combat
        
        # Load conversation history and inject combat resume markers BEFORE starting combat
        conversation_history = load_json_file(json_file) or []
        
        # Inject combat recovery tracking messages
        tracking_message = {
            "role": "user",
            "content": "[SYSTEM: Combat was interrupted and is being resumed from crash]"
        }
        conversation_history.append(tracking_message)
        
        recovery_marker = {
            "role": "assistant",
            "content": "[SYSTEM: Combat recovery initiated - continuing from last known state]"
        }
        conversation_history.append(recovery_marker)
        
        # Save the updated conversation history
        save_conversation_history(conversation_history)
        debug("STATE_CHANGE: Added combat resume tracking messages before combat restart", category="session_management")
        
        # Directly get location info for the combat manager
        current_area_id_resume = party_tracker_data["worldConditions"]["currentAreaId"]
        location_data_resume = location_manager.get_location_info(
            party_tracker_data["worldConditions"]["currentLocation"],
            party_tracker_data["worldConditions"]["currentArea"],
            current_area_id_resume
        )

        # Call run_combat_simulation directly to get the return values
        from core.managers.combat_manager import run_combat_simulation
        dialogue_summary, _ = run_combat_simulation(active_encounter_id, party_tracker_data, location_data_resume)

        print(colored("[SYSTEM] Combat resolved. Integrating summary and continuing adventure...", "yellow"))

        # After combat, reload everything to ensure state is fresh
        party_tracker_data = load_json_file("party_tracker.json")
        conversation_history = load_json_file(json_file) or []

        # ** CRITICAL FIX: Integrate the combat summary into the main conversation history **
        if dialogue_summary:
            # We create a clear, systemic message indicating combat is over.
            # This mimics the handoff from action_handler.
            combat_summary_message = f"[COMBAT CONCLUDED] The encounter has ended. The following is a summary of events:\n\n{dialogue_summary}"
            conversation_history.append({"role": "user", "content": combat_summary_message})
            debug("STATE_CHANGE: Appended combat summary to main history after resumed session.", category="session_management")
            save_conversation_history(conversation_history)

        # ** CRITICAL FIX: Get a new AI response for post-combat narration **
        # This makes the resumed flow behave exactly like the normal flow.
        ai_response_after_combat = get_ai_response(conversation_history)
        if ai_response_after_combat:
            # Process the AI's post-combat response to get the game moving again.
            # We need to load the fresh location data for this call.
            current_area_id_post_combat = party_tracker_data["worldConditions"]["currentAreaId"]
            location_data_post_combat = location_manager.get_location_info(
                party_tracker_data["worldConditions"]["currentLocation"],
                party_tracker_data["worldConditions"]["currentArea"],
                current_area_id_post_combat
            )
            process_ai_response(ai_response_after_combat, party_tracker_data, location_data_post_combat, conversation_history)
        
        debug("CRITICAL: Combat resumption complete - attempting to enter main loop", category="session_management")
        
    # --- END: COMBAT RESUMPTION LOGIC ---
    else:
        # print("[DEBUG] Normal startup path - will enter main game loop")
        # Normal game loop (when not resuming from combat)
        # validation_prompt_text and main_system_prompt_text already loaded above for both paths 

        conversation_history = load_json_file(json_file) or []
    
        # CRITICAL: Check and inject return message BEFORE any processing
        # Don't inject if we already did it for combat resume
        was_injected = False  # Initialize to track if we generated a response for return message
        if not combat_was_resumed:
            conversation_history, was_injected = check_and_inject_return_message(conversation_history, is_combat_active=False)
            if was_injected:
                save_conversation_history(conversation_history)
                # Generate AI response to the return message for startup narration
                debug("STATE_CHANGE: Generating startup narration after return message injection", category="startup")
                ai_response = get_ai_response(conversation_history)
                if ai_response:
                    # Note: We don't call process_ai_response here, just save the response
                    # process_ai_response will be called below with the proper context
                    conversation_history.append({"role": "assistant", "content": ai_response})
                    save_conversation_history(conversation_history)
                    debug("SUCCESS: Startup narration added to conversation history", category="startup")
    
        party_tracker_data = load_json_file("party_tracker.json")
    
        # Verify party tracker loaded successfully
        if not party_tracker_data:
            print("[ERROR] Party tracker not found after setup. Something went wrong.")
            return
    
        # Path manager already initialized above for both paths
        # Just verify it's using the correct module
        debug(f"INITIALIZATION: Path manager already initialized - module_name: '{path_manager.module_name}', module_dir: '{path_manager.module_dir}'", category="module_management")
    
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
        location_data = location_manager.get_location_info( 
            party_tracker_data["worldConditions"]["currentLocation"],
            party_tracker_data["worldConditions"]["currentArea"],
            current_area_id
        )

        # Use current module from party tracker for plot data  
        current_module_name = party_tracker_data.get("module", "").replace(" ", "_")
        current_path_manager = ModulePathManager(current_module_name)
        plot_data = load_json_file(current_path_manager.get_plot_path())
        debug(f"FILE_OP: Plot file path: {current_path_manager.get_plot_path()}", category="module_management")
    
        module_data = load_json_file(current_path_manager.get_module_file_path())

        # CRITICAL: Reload party_tracker to get latest data after module integration
        # Module stitcher may have updated location IDs during integration
        party_tracker_data = load_json_file("party_tracker.json")
        print(f"DEBUG: [Before first update_conversation_history] Reloaded party tracker after integration. Location: {party_tracker_data.get('worldConditions', {}).get('currentLocationId', 'Unknown')}")

        conversation_history = ensure_main_system_prompt(conversation_history, main_system_prompt_text)
        debug(f"STATE_CHANGE: Before update_conversation_history - history has {len(conversation_history)} messages", category="conversation_management")
        conversation_history = update_conversation_history(conversation_history, party_tracker_data, plot_data, module_data)
        debug(f"STATE_CHANGE: After update_conversation_history - history has {len(conversation_history)} messages", category="conversation_management")
        conversation_history = update_character_data(conversation_history, party_tracker_data)
    
        # Use the new order_conversation_messages function
        conversation_history = order_conversation_messages(conversation_history, main_system_prompt_text)
    
        # Check for missing summaries at game startup
        debug("STATE_CHANGE: Checking for missing location summaries at startup", category="startup")
        conversation_history = check_and_compact_missing_summaries(
            conversation_history,
            party_tracker_data
        )
    
        save_conversation_history(conversation_history)

        # Get initial AI response - either we already have one from return message or we need to generate it
        if was_injected:
            # We already generated a response for the return message above
            # Now we need to process it (extract actions, update UI, etc.)
            # The response is already in conversation history, get it from there
            if conversation_history and conversation_history[-1]["role"] == "assistant":
                initial_ai_response = conversation_history[-1]["content"]
                process_ai_response(initial_ai_response, party_tracker_data, location_data, conversation_history)
        else:
            # Normal startup - get initial AI response
            initial_ai_response = get_ai_response(conversation_history)
            # Ensure location_data passed here is the one loaded for the initial state
            process_ai_response(initial_ai_response, party_tracker_data, location_data, conversation_history) 

    # Add safeguard against infinite loops in non-interactive environments
    empty_input_count = 0
    max_empty_inputs = 5
    
    def handle_local_command(input_text):
        """Handle local slash commands that shouldn't go to the LLM"""
        # Clean input of potential multi-PC tags (e.g., "[Character]: /command")
        raw_input = input_text.strip()
        clean_input = raw_input
        if raw_input.startswith("[") and "]:" in raw_input:
            parts = raw_input.split("]:", 1)
            if len(parts) == 2:
                clean_input = parts[1].strip()
        
        cmd = clean_input.lower()
        
        if cmd == "/save":
            try:
                from updates.save_game_manager import SaveGameManager
                manager = SaveGameManager()
                success, message = manager.create_save_game("Manual save", "essential")
                print(colored(f"[SYSTEM] {message}", "green"))
            except Exception as e:
                print(colored(f"[ERROR] Save failed: {e}", "red"))
            return True
            
        elif cmd in ["/quit", "/exit"]:
            print(colored("[SYSTEM] Exiting game...", "yellow"))
            import sys
            sys.exit(0)
            return True
            
        elif cmd == "/help":
            help_msg = (
                "[skipTTS] Dungeon Master: [SYSTEM] Available Commands:\n"
                "  /save - Save current game state\n"
                "  /quit - Exit the game\n"
                "  /stats - View full character stats\n"
                "  /hp [amount] - Heal (positive) or damage (negative)\n"
                "  /xp [amount] - Add experience points\n"
                "  /level [number] - Set character level\n"
                "  /inventory [add/remove] [item] - Manage inventory\n"
                "  /gold [amount] - Add/remove gold\n"
                "  /check [skill] - Perform skill check\n"
                "  /travel [location] - Travel to location\n"
                "  /rest [short/long] - Rest\n"
                "  /storage - Access storage\n"
                "  /levelup - Trigger level up if XP requirement met"
            )
            print(colored(help_msg, "cyan"))
            # Force flush to ensure it reaches the web interface immediately
            import sys
            sys.stdout.flush()
            return True

        # --- Character Info Commands ---

        elif cmd == "/levelup":
            try:
                # Get active character
                pt_data = safe_read_json("party_tracker.json")
                char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
                char_path = path_manager.get_character_path(normalize_character_name(char_name))
                char_data = safe_read_json(char_path)
                
                if not char_data:
                    print(colored(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}", "red"))
                    import sys; sys.stdout.flush()
                    return True
                
                current_xp = char_data.get('experience_points', 0)
                next_level_xp = char_data.get('exp_required_for_next_level', 999999)
                current_level = char_data.get('level', 1)
                
                if current_xp < next_level_xp:
                    msg = f"Dungeon Master: [SYSTEM] {char_name} is not ready to level up. XP: {current_xp}/{next_level_xp}"
                    print(colored(msg, "yellow"))
                    import sys; sys.stdout.flush()
                    return True
                
                # Ready to level up!
                new_level = current_level + 1
                msg = f"Dungeon Master: [SYSTEM] {char_name} is ready to reach level {new_level}! Starting level up session..."
                print(colored(msg, "green"))
                import sys; sys.stdout.flush()
                
                # Initialize session
                from core.managers.level_up_manager import LevelUpSession
                level_up_session = LevelUpSession(char_name, current_level, new_level)
                
                # TABLETOP MODE: Suppress TTS during level-up interview flow
                with _tts_block_scope():
                    # Start session
                    dm_response = level_up_session.start()
                    print(colored("Dungeon Master:", "blue"), colored(dm_response, "blue"))
                    conversation_history.append({"role": "assistant", "content": dm_response})
                    save_conversation_history(conversation_history)
                    
                    # Interactive loop
                    final_narration = ""
                    while not level_up_session.is_complete:
                        try:
                            player_name_display = f"{SOLID_GREEN}{char_name}{RESET_COLOR}"
                            level_up_input = input(f"{player_name_display} (Leveling Up): ")
                            
                            if not level_up_input or not level_up_input.strip():
                                continue
                                
                            # Handle input
                            dm_response = level_up_session.handle_input(level_up_input)
                            
                            # Check response type
                            try:
                                parsed_data = json.loads(dm_response)
                                final_narration = parsed_data.get("narration", "Level up complete!")
                                print(colored("Dungeon Master:", "blue"), colored(final_narration, "blue"))
                            except (json.JSONDecodeError, TypeError):
                                print(colored("Dungeon Master:", "blue"), colored(dm_response, "blue"))
                                
                        except EOFError:
                            break
                    
                    # Finalize
                    if level_up_session.success:
                        conversation_history.append({"role": "assistant", "content": json.dumps({"narration": final_narration, "actions": []})})
                        save_conversation_history(conversation_history)
                        print(colored(f"Dungeon Master: [SYSTEM] {char_name} is now level {new_level}!", "green"))
                    else:
                        print(colored("Dungeon Master: [SYSTEM] Level up cancelled or failed.", "red"))
                        conversation_history.append({"role": "system", "content": level_up_session.summary})
                        save_conversation_history(conversation_history)
                    
                    import sys; sys.stdout.flush()
                
            except Exception as e:
                print(colored(f"Dungeon Master: [SYSTEM] Error during level up: {e}", "red"))
                import sys; sys.stdout.flush()
                import traceback
                traceback.print_exc()
            return True
        
        elif cmd.startswith("/stats"):
            try:
                # Get active character
                pt_data = safe_read_json("party_tracker.json")
                char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
                char_path = path_manager.get_character_path(normalize_character_name(char_name))
                char_data = safe_read_json(char_path)
                
                if char_data:
                    stats_msg = f"Dungeon Master: [SYSTEM] Stats for {char_name}:\n"
                    stats_msg += f"  Level: {char_data.get('level', 1)} | XP: {char_data.get('experience_points', 0)}\n"
                    stats_msg += f"  HP: {char_data.get('hitPoints', 0)}/{char_data.get('maxHitPoints', 0)} | AC: {char_data.get('armorClass', 10)}\n"
                    stats_msg += f"  Speed: {char_data.get('speed', 30)} | Init: {char_data.get('initiative', 0)}\n"
                    
                    abilities = char_data.get('abilities', {})
                    stats_msg += f"  STR: {abilities.get('strength', 10)} | DEX: {abilities.get('dexterity', 10)} | CON: {abilities.get('constitution', 10)}\n"
                    stats_msg += f"  INT: {abilities.get('intelligence', 10)} | WIS: {abilities.get('wisdom', 10)} | CHA: {abilities.get('charisma', 10)}\n"
                    
                    print(colored(stats_msg, "green"))
                    import sys
                    sys.stdout.flush()
                else:
                    print(colored(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}", "red"))
                    import sys
                    sys.stdout.flush()
            except Exception as e:
                print(colored(f"Dungeon Master: [SYSTEM] Error showing stats: {e}", "red"))
                import sys
                sys.stdout.flush()
            return True

        elif cmd.startswith("/hp"):
            try:
                parts = cmd.split()
                if len(parts) < 2:
                    print(colored("Dungeon Master: [SYSTEM] Usage: /hp [amount]", "red"))
                    import sys; sys.stdout.flush()
                    return True
                
                amount = int(parts[1])
                
                # Get active character
                pt_data = safe_read_json("party_tracker.json")
                char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
                char_path = path_manager.get_character_path(normalize_character_name(char_name))
                char_data = safe_read_json(char_path)
                
                if char_data:
                    current_hp = char_data.get('hitPoints', 0)
                    max_hp = char_data.get('maxHitPoints', 0)
                    new_hp = max(0, min(max_hp, current_hp + amount))
                    char_data['hitPoints'] = new_hp
                    
                    safe_write_json(char_path, char_data)
                    
                    action_str = "healed" if amount >= 0 else "damaged"
                    msg = f"Dungeon Master: [SYSTEM] {char_name} {action_str} by {abs(amount)}. HP: {current_hp} -> {new_hp}/{max_hp}"
                    print(colored(msg, "green"))
                    import sys; sys.stdout.flush()
                else:
                    print(colored(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}", "red"))
                    import sys; sys.stdout.flush()
            except ValueError:
                print(colored("Dungeon Master: [SYSTEM] Usage: /hp [amount] (must be a number)", "red"))
                import sys; sys.stdout.flush()
            except Exception as e:
                print(colored(f"Dungeon Master: [SYSTEM] Error updating HP: {e}", "red"))
                import sys; sys.stdout.flush()
            return True

        elif cmd.startswith("/xp"):
            try:
                parts = cmd.split()
                if len(parts) < 2:
                    print(colored("Dungeon Master: [SYSTEM] Usage: /xp [amount]", "red"))
                    import sys; sys.stdout.flush()
                    return True
                
                amount = int(parts[1])
                
                # Get active character
                pt_data = safe_read_json("party_tracker.json")
                char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
                char_path = path_manager.get_character_path(normalize_character_name(char_name))
                char_data = safe_read_json(char_path)
                
                if char_data:
                    current_xp = char_data.get('experience_points', 0)
                    new_xp = max(0, current_xp + amount)
                    char_data['experience_points'] = new_xp
                    
                    safe_write_json(char_path, char_data)
                    
                    msg = f"Dungeon Master: [SYSTEM] {char_name} gained {amount} XP. Total: {current_xp} -> {new_xp}"
                    print(colored(msg, "green"))
                    import sys; sys.stdout.flush()
                else:
                    print(colored(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}", "red"))
                    import sys; sys.stdout.flush()
            except ValueError:
                print(colored("Dungeon Master: [SYSTEM] Usage: /xp [amount] (must be a number)", "red"))
                import sys; sys.stdout.flush()
            except Exception as e:
                print(colored(f"Dungeon Master: [SYSTEM] Error updating XP: {e}", "red"))
                import sys; sys.stdout.flush()
            return True

        elif cmd.startswith("/level"):
            try:
                parts = cmd.split()
                if len(parts) < 2:
                    print(colored("Dungeon Master: [SYSTEM] Usage: /level [number]", "red"))
                    import sys; sys.stdout.flush()
                    return True
                
                level = int(parts[1])
                
                # Get active character
                pt_data = safe_read_json("party_tracker.json")
                char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
                char_path = path_manager.get_character_path(normalize_character_name(char_name))
                char_data = safe_read_json(char_path)
                
                if char_data:
                    current_level = char_data.get('level', 1)
                    char_data['level'] = level
                    
                    safe_write_json(char_path, char_data)
                    
                    msg = f"Dungeon Master: [SYSTEM] {char_name} level set to {level} (was {current_level})"
                    print(colored(msg, "green"))
                    import sys; sys.stdout.flush()
                else:
                    print(colored(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}", "red"))
                    import sys; sys.stdout.flush()
            except ValueError:
                print(colored("Dungeon Master: [SYSTEM] Usage: /level [number] (must be a number)", "red"))
                import sys; sys.stdout.flush()
            except Exception as e:
                print(colored(f"Dungeon Master: [SYSTEM] Error updating level: {e}", "red"))
                import sys; sys.stdout.flush()
            return True
            
        return False
    if combat_was_resumed:
        debug("SUCCESS: Main game loop reached after combat resumption", category="session_management")
    while True:
        conversation_history = truncate_dm_notes(conversation_history)
        conversation_history = remove_duplicate_messages(conversation_history)

        if needs_conversation_history_update:
            debug("STATE_CHANGE: Reloading conversation history from disk due to needs_conversation_history_update flag", category="conversation_management")
            # Reload conversation history from disk to get any changes made during actions
            conversation_history = load_json_file("modules/conversation_history/conversation_history.json") or []
            # CRITICAL: Also reload party tracker to get the latest module information
            party_tracker_data = load_json_file("party_tracker.json")
            print(f"DEBUG: [Main Loop] Reloaded party tracker after update. Module: {party_tracker_data.get('module', 'Unknown')}")
            conversation_history = process_conversation_history(conversation_history)
            conversation_history = remove_duplicate_messages(conversation_history)  # Clean any duplicates
            save_conversation_history(conversation_history)
            needs_conversation_history_update = False

        # Your essential cleanup script remains here, running every cycle.
        # Loop until all unprocessed location transitions are handled
        transitions_were_processed = False
        while True:
            original_length = len(conversation_history)
            conversation_history = check_and_process_location_transitions(conversation_history, party_tracker_data, path_manager)
            if len(conversation_history) == original_length:
                break  # No compression occurred, we're done
            else:
                transitions_were_processed = True  # Mark that we did actual work
        save_conversation_history(conversation_history)
        
        # Only check for chunked compression if we actually processed transitions
        if transitions_were_processed:
            try:
                from core.ai.chunked_compression_integration import check_and_perform_chunked_compression
                if check_and_perform_chunked_compression():
                    debug("SUCCESS: Chunked compression performed after processing old transitions", category="conversation_management")
                    # Reload the compressed history
                    conversation_history = load_json_file(json_file) or conversation_history
            except Exception as e:
                error(f"FAILURE: Chunked compression check failed", exception=e, category="conversation_management")
    
        # DISABLED: Module summary insertion now handled by inject_campaign_summaries with separate system messages
        # conversation_history = check_and_process_module_transitions(conversation_history, party_tracker_data)
        save_conversation_history(conversation_history)
    
        # Check for expired temporary effects
        try:
            from updates.process_effect_expirations import process_all_effect_expirations
            debug("EFFECTS: Checking for expired effects", category="effects_tracking")
            process_all_effect_expirations()
        except Exception as e:
            debug(f"EFFECTS: Failed to process effect expirations: {str(e)}", category="effects_tracking")
            # Don't break the game if effects processing fails


        # Set status to ready before accepting input
        status_ready()

        # Check if stdin is available (prevent infinite loops in non-interactive environments)
        if hasattr(sys.stdin, 'isatty') and not sys.stdin.isatty():
            warning("INITIALIZATION: Running in non-interactive environment. Stdin is not a terminal.", category="startup")
            print("Game loop stopped to prevent infinite empty input cycle.")
            print("To run interactively, ensure the program is run from a proper terminal.")
            break

        # --- Post-Combat State Refresh & UI Display ---
        # This is the core fix. After combat, we MUST reload all data from disk
        # to avoid using stale in-memory data from before the fight.
        if hasattr(process_ai_response, '_just_finished_combat') and process_ai_response._just_finished_combat:
            info("STATE_REFRESH: Post-combat state refresh triggered. Reloading data from disk.", category="game_loop")
            # Reload the party tracker first, as it's the source of truth.
            party_tracker_data = load_json_file("party_tracker.json")
            # Reset the flag so this only runs once per combat.
            process_ai_response._just_finished_combat = False
    
        # Now, get the player's name and load their character file for the UI.
        # This data will now be fresh if a refresh was just triggered.
        player_name_actual = party_tracker_data.get("active_character") or party_tracker_data["partyMembers"][0]
        from updates.update_character_info import normalize_character_name
        player_name_normalized = normalize_character_name(player_name_actual)
        player_data_file = path_manager.get_character_path(player_name_normalized)
        player_data_current = load_json_file(player_data_file)
    
        # TABLETOP MODE: Check if we're in character creation mode
        if is_creation_mode_active():
            creation_context = safe_json_load(CHARACTER_CREATION_MARKER) or {}
            creating_char = creation_context.get('character_name', 'Unknown')
            target_level = creation_context.get('target_level', 1)
            print(colored("\n" + "="*60, "cyan"))
            print(colored("CHARACTER CREATION MODE", "cyan", attrs=["bold"]))
            print(colored(f"Creating: {creating_char} (Level {target_level})", "cyan"))
            print(colored("Narrative thread paused - Interview in progress", "cyan"))
            print(colored("="*60 + "\n", "cyan"))
    
        # Display the prompt with the (now correct) stats.
        if player_data_current:
            current_hp = player_data_current.get("hitPoints", "N/A")
            max_hp = player_data_current.get("maxHitPoints", "N/A")
            current_xp = player_data_current.get("experience_points", "N/A")
            next_level_xp = player_data_current.get("exp_required_for_next_level", "N/A")
            # Get time with context for display
            from utils.time_context import get_time_context
            current_time_str = party_tracker_data["worldConditions"]["time"]
            time_context = get_time_context(current_time_str)
            # Show both time and context in prompt
            time_display = f"{current_time_str[:5]} ({time_context})"  # Show HH:MM (context)
            stats_display = f"{LIGHT_OFF_GREEN}[{time_display}][HP:{current_hp}/{max_hp}][XP:{current_xp}/{next_level_xp}]{RESET_COLOR}"
            player_name_display = f"{SOLID_GREEN}{player_name_actual}{RESET_COLOR}"
            user_input_text = input(f"{stats_display} {player_name_display}: ")
        else:
            user_input_text = input("User: ")

        # Skip processing if input is empty or only whitespace
        if not user_input_text or not user_input_text.strip():
            continue
        else:
            # Reset counter on valid input
            empty_input_count = 0

            # Check for local commands
            if handle_local_command(user_input_text):
                continue

            # TABLETOP MODE: C2 - Combat-only command routing guards
            # Block combat-only commands when no active combat encounter is present
            clean_input = _normalize_combat_command_input(user_input_text)
            party_tracker_for_input_guards = load_json_file("party_tracker.json") or {}
            if _is_combat_only_command(clean_input):
                active_combat = party_tracker_for_input_guards.get("worldConditions", {}).get("activeCombatEncounter", "")
                guard_msg = get_noncombat_guard_message(user_input_text, active_combat)
                if guard_msg:
                    print(colored(guard_msg, "yellow"))
                    sys.stdout.flush()
                    continue

            # TABLETOP MODE: Step 3.1 - Fail-closed guard for brand-new PC creation requests
            # outside dedicated character creation flows.
            new_pc_guard_msg = get_new_pc_creation_guard_message(
                user_input_text,
                party_tracker_for_input_guards,
            )
            if new_pc_guard_msg:
                print(colored(new_pc_guard_msg, "yellow"))
                sys.stdout.flush()
                continue
    
        party_tracker_data = load_json_file("party_tracker.json") 
    
        # Remove duplicate NPCs if any exist
        party_tracker_data, npcs_were_cleaned = remove_duplicate_npcs(party_tracker_data)
        if npcs_were_cleaned:
            # Save the cleaned party tracker back to file
            safe_write_json("party_tracker.json", party_tracker_data)
            debug("FILE_OP: Updated party_tracker.json with duplicate NPCs removed", category="npc_management")

        party_members_stats = []
        for member_name_iter in party_tracker_data["partyMembers"]:
            member_file_path = path_manager.get_character_path(member_name_iter)
            member_data_iter = load_json_file(member_file_path)
            if member_data_iter:
                stats = {
                    "name": member_name_iter,  # Keep original case to match file names
                    "display_name": member_name_iter.capitalize(),  # For display purposes
                    "level": member_data_iter.get("level", "N/A"),
                    "xp": member_data_iter.get("experience_points", "N/A"),
                    "hp": member_data_iter.get("hitPoints", "N/A"),
                    "max_hp": member_data_iter.get("maxHitPoints", "N/A")
                }
                party_members_stats.append(stats)

        try:
            for npc_info_iter in party_tracker_data["partyNPCs"]:
                debug(f"STATE_CHANGE: Processing NPC: {npc_info_iter['name']}", category="npc_management")
                npc_name_iter = npc_info_iter["name"]
                npc_data_file = path_manager.get_character_path(npc_name_iter)
                debug(f"FILE_OP: NPC file path: {npc_data_file}", category="npc_management")
                npc_data_iter = load_json_file(npc_data_file)
                debug(f"FILE_OP: NPC data loaded: {npc_data_iter is not None}", category="npc_management")
                if npc_data_iter:
                    stats = {
                        "name": npc_info_iter["name"],
                        "display_name": npc_info_iter["name"].capitalize(),  # For display purposes
                        "level": npc_data_iter.get("level", npc_info_iter.get("level", "N/A")),
                        "xp": npc_data_iter.get("experience_points", "N/A"),
                        "hp": npc_data_iter.get("hitPoints", "N/A"),
                        "max_hp": npc_data_iter.get("maxHitPoints", "N/A")
                    }
                    party_members_stats.append(stats)
                    debug(f"STATE_CHANGE: Added NPC stats: {stats}", category="npc_management")
        except Exception as e:
            error(f"FAILURE: Error processing NPCs", exception=e, category="npc_management")
            import traceback
            traceback.print_exc()
    
        # Reload current location_data for the DM note based on party_tracker
        # This ensures location_data is fresh for each DM note construction
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"] 
        location_data = location_manager.get_location_info( 
            party_tracker_data["worldConditions"]["currentLocation"],
            party_tracker_data["worldConditions"]["currentArea"],
            current_area_id
        )

        if party_members_stats:
            world_conditions = party_tracker_data["worldConditions"]
            # Use enhanced time formatting with context
            from utils.time_context import format_time_with_context
            date_time_str = format_time_with_context(world_conditions)
            party_stats_formatted = []
            for stats_item in party_members_stats:
                # Check if this is a player or an NPC
                if stats_item['name'] in party_tracker_data["partyMembers"]:
                    member_data_for_note = load_json_file(path_manager.get_character_path(stats_item['name']))
                else:
                    member_data_for_note = load_json_file(path_manager.get_character_path(stats_item['name']))
                if member_data_for_note:
                    abilities = member_data_for_note.get("abilities", {})
                    ability_str = f"STR:{abilities.get('strength', 'N/A')} DEX:{abilities.get('dexterity', 'N/A')} CON:{abilities.get('constitution', 'N/A')} INT:{abilities.get('intelligence', 'N/A')} WIS:{abilities.get('wisdom', 'N/A')} CHA:{abilities.get('charisma', 'N/A')}"
                    next_level_xp_note = member_data_for_note.get("exp_required_for_next_level", "N/A")
                    display_name = stats_item.get('display_name', stats_item['name'].capitalize())
                
                    # Extract spell slot information if character has spellcasting
                    spell_slots_str = ""
                    spellcasting = member_data_for_note.get("spellcasting", {})
                    if spellcasting and "spellSlots" in spellcasting:
                        spell_slots = spellcasting["spellSlots"]
                        slot_parts = []
                        for level in range(1, 10):  # Spell levels 1-9
                            level_key = f"level{level}"
                            if level_key in spell_slots:
                                slot_data = spell_slots[level_key]
                                current = slot_data.get("current", 0)
                                maximum = slot_data.get("max", 0)
                                if maximum > 0:  # Only show levels with available slots
                                    slot_parts.append(f"L{level}:{current}/{maximum}")
                        if slot_parts:
                            spell_slots_str = f", Spell Slots: {' '.join(slot_parts)}"
                
                    party_stats_formatted.append(f"{display_name}: Level {stats_item['level']}, XP {stats_item['xp']}/{next_level_xp_note}, HP {stats_item['hp']}/{stats_item['max_hp']}, {ability_str}{spell_slots_str}")

            party_stats_str = "; ".join(party_stats_formatted) if party_stats_formatted else "None"
            current_location_name_note = world_conditions["currentLocation"]
            current_location_id_note = world_conditions["currentLocationId"]
            
            # Check if current location has been peacefully resolved
            resolved_map = world_conditions.get("resolvedHostilesByLocation", {})
            is_resolved_here = resolved_map.get(current_location_id_note, False) if isinstance(resolved_map, dict) else False
            
            threat_guidance = (
                "Resolved Hostile State: Hostile guardian at this location has been appeased. Do not re-initiate this threat unless the party provokes it. "
                if is_resolved_here else
                "Monsters should be active threats per engagement rules. "
            )
        
            # --- CONNECTIVITY SECTION ---
            connected_locations_display_str = "None listed"
            connected_areas_display_str = "" # Initialize as empty

            if location_data: # Ensure location_data is not None
                # Get connections within the current area
                if "connectivity" in location_data and location_data["connectivity"]:
                    connected_ids_current_area = location_data["connectivity"]
                    connected_names_current_area = []
                    # Load the current area's full data to get names from IDs
                    current_area_full_data = load_json_file(path_manager.get_area_path(current_area_id))
                    if current_area_full_data and "locations" in current_area_full_data:
                        for loc_id in connected_ids_current_area:
                            found_loc = next((l["name"] for l in current_area_full_data["locations"] if l["locationId"] == loc_id), loc_id)
                            connected_names_current_area.append(found_loc)
                    if connected_names_current_area:
                         connected_locations_display_str = ", ".join(connected_names_current_area)
            
                # Get connections to other areas
                if "areaConnectivityId" in location_data and location_data["areaConnectivityId"]:
                    # Use the global location_graph to get info about connected locations
                    connected_area_details = []
                    for connected_loc_id in location_data["areaConnectivityId"]:
                        # Get the full info for the connected location
                        conn_loc_info = location_graph.get_location_info(connected_loc_id)
                        if conn_loc_info:
                            conn_loc_name = conn_loc_info['location_name']
                            conn_area_name = location_graph.get_area_name_from_location_id(connected_loc_id)
                            connected_area_details.append(f"{conn_loc_name} (in {conn_area_name})")
                
                    if connected_area_details:
                        connected_areas_display_str = ". Connects to other areas via: " + ", ".join(connected_area_details)
        
            # --- INTER-MODULE CONNECTIVITY SECTION ---
            available_modules_str = ""
            try:
                # Load world registry to get all available modules
                world_registry_path = "modules/world_registry.json"
                world_registry = safe_read_json(world_registry_path)
            
                if world_registry and 'modules' in world_registry:
                    current_module = party_tracker_data.get('module', '').replace(' ', '_')
                    all_modules = list(world_registry['modules'].keys())
                    other_modules = [m for m in all_modules if m != current_module]
                
                    if other_modules:
                        # Get areas from other modules
                        other_module_areas = []
                        for module_name in other_modules:
                            module_info = world_registry['modules'][module_name]
                            # Get the areas for this module from the areas section
                            module_areas = []
                            for area_id, area_info in world_registry.get('areas', {}).items():
                                if area_info.get('module') == module_name:
                                    area_name = area_info.get('areaName', area_id)
                                    module_areas.append(f"{area_name} ({area_id})")
                        
                            if module_areas:
                                level_range = module_info.get('levelRange', {})
                                level_str = f"Level {level_range.get('min', '?')}-{level_range.get('max', '?')}"
                            
                                # Get starting location for this module
                                try:
                                    start_location_id, start_location_name, start_area_id, start_area_name = action_handler.get_module_starting_location(module_name)
                                    starting_info = f" (Starting location: {start_location_name} [{start_location_id}] in {start_area_name} [{start_area_id}])"
                                except Exception as e:
                                    print(f"Warning: Could not get starting location for {module_name}: {e}")
                                    starting_info = ""
                            
                                module_description = f"{module_name} [{level_str}]: {', '.join(module_areas[:3])}{starting_info}"
                                other_module_areas.append(module_description)
                    
                        if other_module_areas:
                            available_modules_str = ". Available modules for travel: " + "; ".join(other_module_areas)
            except Exception as e:
                error(f"FAILURE: Failed to load inter-module connectivity", exception=e, category="module_management")
            # --- END OF INTER-MODULE CONNECTIVITY SECTION ---
            # --- END OF CONNECTIVITY SECTION ---
        
            # Use current module from party tracker for plot data
            current_module_for_plot = party_tracker_data.get("module", "").replace(" ", "_")
            current_plot_manager = ModulePathManager(current_module_for_plot)
            plot_data_for_note = load_json_file(current_plot_manager.get_plot_path())
            debug(f"FILE_OP: Plot file path: {current_plot_manager.get_plot_path()}", category="module_management")
            debug(f"FILE_OP: Plot data loaded: {plot_data_for_note is not None}", category="module_management")
            if plot_data_for_note:
                debug(f"FILE_OP: Plot data keys: {list(plot_data_for_note.keys())}", category="module_management")
            else:
                debug("FILE_OP: No plot data loaded - plot_data_for_note is None", category="module_management") 
            current_plot_points = []
            all_active_plot_points = []
            if plot_data_for_note and "plotPoints" in plot_data_for_note:
                plot_points = plot_data_for_note.get("plotPoints", [])
                plot_status_by_id = {
                    str(point.get("id", "")).strip(): str(point.get("status", "")).strip().lower()
                    for point in plot_points
                    if isinstance(point, dict) and point.get("id")
                }

                # TABLETOP MODE: Hide prerequisite-locked plot points from DM notes
                # to avoid surfacing downstream hooks before required milestones complete.
                def _is_plot_point_unlocked(point):
                    prerequisites = point.get("prerequisites", [])
                    if not isinstance(prerequisites, list):
                        return True
                    for prereq_id in prerequisites:
                        prereq_key = str(prereq_id).strip()
                        if not prereq_key:
                            continue
                        if plot_status_by_id.get(prereq_key) != "completed":
                            return False
                    return True

                # Get plot points for current location
                current_plot_points = [
                    point for point in plot_points
                    if (
                        point.get("location") == current_area_id
                        and point.get("status") != "completed"
                        and _is_plot_point_unlocked(point)
                    )
                ]
                # Get ALL active plot points in the module
                all_active_plot_points = [
                    point for point in plot_points
                    if point.get("status") != "completed" and _is_plot_point_unlocked(point)
                ]
        
            # Format plot points - show current location plots first, then other active plots
            plot_points_parts = []
            if current_plot_points:
                plot_points_parts.append("At this location:")
                plot_points_parts.extend([f"- {point['id']}: {point['title']} [{point.get('status', 'active')}]" for point in current_plot_points])
        
            # Add other active plots from different locations
            other_plots = [p for p in all_active_plot_points if p not in current_plot_points]
            if other_plots:
                if plot_points_parts:  # Add separator if we have location plots
                    plot_points_parts.append("\nActive elsewhere in module:")
                plot_points_parts.extend([f"- {point['id']}: {point['title']} [{point.get('status', 'active')}] @{point.get('location', 'Unknown')}" for point in other_plots])
        
            plot_points_str = "\n".join(plot_points_parts) if plot_points_parts else "None active"
        
            side_quests = []
            # Get ALL side quests from ALL plot points (not just current location)
            for point in plot_data_for_note.get("plotPoints", []):
                for quest in point.get("sideQuests", []):
                    if quest["status"] != "completed":
                        location_info = f" [Location: {point.get('location', 'Unknown')}]" if point.get('location') != current_area_id else ""
                        side_quests.append(f"- {quest['id']}: {quest['title']} [{quest['status']}]{location_info}")
            side_quests_str = "\n".join(side_quests) if side_quests else "None active"

            traps_str = "None listed"
            if location_data and "traps" in location_data: 
                traps = location_data.get("traps", [])
                if traps:
                    traps_str = "\n".join([
                        f"- {trap.get('name', 'Unknown Trap')}: {trap.get('description', 'No description')} (Detect DC: {trap.get('detectDC', 'N/A')}, Disable DC: {trap.get('disableDC', 'N/A')}, Trigger DC: {trap.get('triggerDC', 'N/A')}, Damage: {trap.get('damage', 'N/A')})"
                        for trap in traps
                    ])

            monsters_str = "None listed"
            if location_data and "monsters" in location_data:
                monsters = location_data.get("monsters", [])
            
                # Bulletproof check: ensure monsters is actually a list/array
                if not isinstance(monsters, (list, tuple)):
                    monsters_str = f"Invalid monster data format: {type(monsters)}"
                elif monsters:
                    monster_list = []
                    for monster in monsters:
                        # Graceful handling for different monster formats
                        if isinstance(monster, str):
                            # Handle legacy string format (just use the string)
                            monster_list.append(f"- {monster}")
                        elif isinstance(monster, dict):
                            # Handle dictionary format (multiple schema versions)
                            name = monster.get('name', 'Unknown')
                        
                            # Try different quantity field names
                            qty = None
                            qty_str = "1"
                        
                            if 'quantity' in monster:
                                # Standard schema: {"quantity": {"min": 1, "max": 1}}
                                qty = monster.get('quantity', {})
                                if isinstance(qty, dict):
                                    qty_str = f"{qty.get('min', 1)}-{qty.get('max', 1)}"
                                else:
                                    qty_str = str(qty)
                            elif 'number' in monster:
                                # Keep of Doom schema: {"number": "2d4"}
                                qty_str = str(monster.get('number', 1))
                            elif 'count' in monster:
                                # Silver Vein schema: {"count": 2}
                                qty_str = str(monster.get('count', 1))
                        
                            monster_list.append(f"- {name} ({qty_str})")
                        else:
                            # Handle unexpected types
                            monster_list.append(f"- Unknown monster type: {type(monster)}")
                    monsters_str = "\n".join(monster_list)

            # Check ALL modules for plot completion before suggesting module creation
            module_creation_prompt = ""
            # should_inject_creation_prompt is now a global variable
            try:
                # Debug current module detection
                current_module = party_tracker_data.get('module', '').replace(' ', '_')
                debug(f"STATE_CHANGE: Current module from party tracker: '{current_module}'", category="module_management")
            
                # Use new comprehensive module completion checker
                all_modules_completion = check_all_modules_plot_completion()
            
                # Extract results
                all_modules_complete = all_modules_completion["all_complete"]
                modules_checked = all_modules_completion["modules_checked"]
                completion_summary = all_modules_completion["completion_summary"]
            
                # Print summary of all modules
                debug("STATE_CHANGE: === ALL MODULES COMPLETION SUMMARY ===", category="module_management")
                print("DEBUG: [Module Manager] === MODULE COMPLETION SUMMARY ===")
                for module_name, summary in completion_summary.items():
                    status = "COMPLETE" if summary["is_complete"] else "INCOMPLETE"
                    debug(f"STATE_CHANGE: {module_name}: {summary['completed_plots']}/{summary['total_plots']} plots - {status}", category="module_management")
                    print(f"DEBUG: [Module Manager] {module_name}: {summary['completed_plots']}/{summary['total_plots']} plots - {status}")
                debug("STATE_CHANGE: === END SUMMARY ===", category="module_management")
            
                # Determine if we should inject module creation prompt
                # Only suggest module creation if ALL modules are complete
                should_inject_creation_prompt = all_modules_complete and len(modules_checked) > 0
            
                debug(f"STATE_CHANGE: All modules complete: {all_modules_complete}", category="module_management")
                debug(f"STATE_CHANGE: Should inject module creation prompt: {should_inject_creation_prompt}", category="module_management")
                print(f"DEBUG: [Module Manager] All modules complete: {all_modules_complete}")
                print(f"DEBUG: [Module Manager] Module transfer available: {should_inject_creation_prompt}")
            
                # If ALL modules are complete, inject creation prompt
                if should_inject_creation_prompt:
                    debug("STATE_CHANGE: *** MODULE CREATION PROMPT INJECTION TRIGGERED ***", category="module_management")
                    debug("STATE_CHANGE: All available modules have completed plots - suggesting new module creation", category="module_management")
                    # Load the module creation prompt
                    import os
                    if os.path.exists("prompts/generators/module_creation_prompt.txt"):
                        with open("prompts/generators/module_creation_prompt.txt", "r", encoding="utf-8") as f:
                            module_creation_prompt = "\n\n" + f.read()
                        debug(f"FILE_OP: Module creation prompt loaded ({len(module_creation_prompt)} characters)", category="module_management")
                    else:
                        warning("FILE_OP: module_creation_prompt.txt not found!", category="module_management")

                else:
                    incomplete_modules = [name for name, summary in completion_summary.items() if not summary["is_complete"]]
                    if incomplete_modules:
                        debug(f"STATE_CHANGE: Module creation prompt NOT injected - incomplete modules: {incomplete_modules}", category="module_management")
                    else:
                        debug("STATE_CHANGE: Module creation prompt NOT injected - no modules found to check", category="module_management")
                
            except Exception as e:
                error(f"FAILURE: Module completion check failed", exception=e, category="module_management")
                import traceback
                traceback.print_exc()
        
            # Sanitize location name before using in DM note
            current_location_name_note = sanitize_text(current_location_name_note)
        
            # Get current module, season, and area for enhanced DM note
            current_module_name = party_tracker_data.get('module', 'Unknown')
            current_season = world_conditions.get('season', 'Unknown')
            current_area_name = world_conditions.get('currentArea', 'Unknown')
        
            # Get established hubs information
            established_hubs_str = ""
            try:
                from core.managers.campaign_manager import CampaignManager
                campaign_manager = CampaignManager()
                hubs = campaign_manager.get_available_hubs()
                if hubs:
                    hub_details = []
                    for hub in hubs:
                        hub_data = campaign_manager.campaign_data['hubs'].get(hub, {})
                        ownership = hub_data.get('ownership', 'party')
                        hub_type = hub_data.get('hubType', 'settlement')
                        hub_details.append(f"{hub} ({hub_type}, {ownership})")
                    established_hubs_str = f" Established hubs: {', '.join(hub_details)}."
            except Exception as e:
                debug(f"Could not load hub information: {e}", category="dm_note")

            # TABLETOP MODE: Multi-PC DM Note enhancement
            # Check if we should use enhanced multi-PC format
            party_members_list = party_tracker_data.get('partyMembers', [])
            use_multi_pc_note = len(party_members_list) > 1
            
            if use_multi_pc_note:
                # Use enhanced multi-PC DM Note with [>] marker and sections
                from utils.multi_pc_dm_note import build_multi_pc_dm_note
                connected_locations_str = f"{connected_locations_display_str}{connected_areas_display_str}{available_modules_str}{established_hubs_str}"
                
                dm_note = build_multi_pc_dm_note(
                    party_tracker_data=party_tracker_data,
                    location_data=location_data,
                    world_conditions=world_conditions,
                    date_time_str=date_time_str,
                    current_season=current_season,
                    current_module_name=current_module_name,
                    current_location_name=current_location_name_note,
                    current_location_id=current_location_id_note,
                    current_area_name=current_area_name,
                    plot_points_str=plot_points_str,
                    side_quests_str=side_quests_str,
                    monsters_str=monsters_str,
                    traps_str=traps_str,
                    connected_locations_str=connected_locations_str,
                    module_creation_prompt=module_creation_prompt,
                    should_inject_creation_prompt=should_inject_creation_prompt
                )
                debug(f"STATE_CHANGE: Using multi-PC DM Note format for {len(party_members_list)} party members", category="multi_pc_dm_note")
            else:
                # Format party members and NPCs for standard single-PC DM note
                party_members_str = ", ".join(party_members_list) if party_members_list else "None"
                
                party_npcs_list = party_tracker_data.get('partyNPCs', [])
                party_npcs_formatted = []
                for npc in party_npcs_list:
                    party_npcs_formatted.append(f"{npc['name']} ({npc['role']})")
                party_npcs_str = ", ".join(party_npcs_formatted) if party_npcs_formatted else "None"
                
                # Build DM note - exclude plot/quest info when module creation is active
                if should_inject_creation_prompt:
                    # Simplified DM note for module creation - no confusing plot/quest info
                    dm_note = (f"Dungeon Master Note: Current date and time: {date_time_str}, {current_season} season. "
                        f"Current module: {current_module_name}. "
                        f"Current location: {current_location_name_note} ({current_location_id_note}) in the {current_area_name} area. "
                        f"Active Player Characters (User Controlled): {party_members_str}. "
                        f"Accompanied by Party NPCs (DM Controlled): {party_npcs_str}. "
                        f"Party stats: {party_stats_str}. "
                        f"Adjacent locations in this area: {connected_locations_display_str}{connected_areas_display_str}{available_modules_str}{established_hubs_str}.\n")
                else:
                    # Normal DM note with all plot/quest/monster info
                    dm_note = (f"Dungeon Master Note: Current date and time: {date_time_str}, {current_season} season. "
                        f"Current module: {current_module_name}. "
                        f"Current location: {current_location_name_note} ({current_location_id_note}) in the {current_area_name} area. "
                        f"Active Player Characters (User Controlled): {party_members_str}. "
                        f"Accompanied by Party NPCs (DM Controlled): {party_npcs_str}. "
                        f"Party stats: {party_stats_str}. "
                        f"Adjacent locations in this area: {connected_locations_display_str}{connected_areas_display_str}{available_modules_str}{established_hubs_str}.\n"
                        f"Active plot points for this location:\n{plot_points_str}\n"
                        f"Active side quests for this location:\n{side_quests_str}\n"
                        f"Monsters in this location:\n{monsters_str}\n"
                        f"Traps in this location:\n{traps_str}\n"
                        f"{threat_guidance}")
        
            # Add common instructions (skip for multi-PC mode to reduce prompt bulk)
            # TABLETOP MODE: Multi-PC path uses leaner prompt without legacy instruction tail
            is_multi_pc_mode = False
            try:
                from config import MULTIPLAYER_MODE
                party_members = party_tracker_data.get('partyMembers', [])
                is_multi_pc_mode = MULTIPLAYER_MODE and len(party_members) > 1
            except ImportError:
                is_multi_pc_mode = False
            
            if not is_multi_pc_mode:
                dm_note += (
                    "updateCharacterInfo for player and NPC character changes (inventory, stats, abilities), "
                    "updateTime for time passage, "
                    "updatePlot for story progression, discovers, and new information, "
                    "updatePartyNPCs for party composition changes to the party tracker, "
                    "levelUp for advancement, "
                    "establishHub when the party gains ownership or control of a location that could serve as a base of operations (stronghold, tavern, keep, etc.) - example: establishHub('The Silver Swan Inn', {hubType: 'tavern', description: 'Our permanent base of operations', services: ['rest', 'information'], ownership: 'party'}), "
                    "exitGame for ending sessions, and "
                    "transitionLocation should always be used when the player expresses a desire to move to a new location, "
                    "Always roleplay the NPC and NPC party rolls without asking the player. "
                    "Always ask the player character to roll for skill checks and other actions. "
                    "Proactively narrate location NPCs, start conversations, and weave plot elements into the adventure. "
                    "Use party NPCs to narrate if possible instead of always narrating from the DM's perspective, but don't overdo it. "
                    "Maintain immersive and engaging storytelling similar to an adventure novel while accurately managing game mechanics. "
                    "Update all relevant information immediately and confirm with the player before major actions. "
                    "Consider whether the party's action trigger traps in this location. "
                    "Consider updating the plot elements on every action the player and NPCs take."
                    f"{module_creation_prompt}")
        else:
            dm_note = "Dungeon Master Note: Remember to take actions if necessary such as updating the plot, time, character sheets, and location if changes occur."

        # Enhance player input with inventory context
        # Using 'general' context for main conversation (combat has separate manager)
        # Note: We pass None for character_data/characters_data as the integration 
        # function will extract inventory from party_tracker_data
        user_input_with_note = build_enhanced_dm_note(
            dm_note,
            user_input_text,
            None,  # character_data not available at this scope
            party_tracker_data,
            None,  # characters_data not available at this scope
            in_combat=False  # Always use general context for main conversation
        )

        # TABLETOP MODE: Tag messages with active PC in multi-PC mode
        should_tag_messages = False
        try:
            from config import MULTIPLAYER_MODE
            should_tag_messages = MULTIPLAYER_MODE
        except ImportError:
            should_tag_messages = False

        if should_tag_messages:
            party_members = party_tracker_data.get('partyMembers', [])
            if len(party_members) > 1:
                active_pc = party_tracker_data.get('active_character')
                if active_pc:
                    conversation_history.append({"role": "user", "content": user_input_with_note, "active_pc": active_pc})
                else:
                    conversation_history.append({"role": "user", "content": user_input_with_note})
            else:
                conversation_history.append({"role": "user", "content": user_input_with_note})
        else:
            conversation_history.append({"role": "user", "content": user_input_with_note})
        save_conversation_history(conversation_history)

        retry_count = 0
        valid_response_received = False 
        ai_response_content = None
        
        # TABLETOP MODE: Retry de-looping state (Task 3.3)
        last_validation_reason = None
        repeated_reason_count = 0
        
        # TABLETOP MODE: Step 3.2 - Retry-local correction note (not persisted to conversation history)
        retry_correction_note = None

        # TABLETOP MODE: Step 3.2 - Track deterministic redirect for new-PC creation misroutes.
        new_pc_creation_redirected = False
    
        while retry_count < 5 and not valid_response_received:
            # Pass validation retry count for intelligent model escalation
            # Pass transient correction note if this is a retry
            ai_response_content = get_ai_response(
                conversation_history,
                validation_retry_count=retry_count,
                transient_correction=retry_correction_note
            )

            # PRE-PROCESSING: Fix incorrect updatePartyTracker usage for within-module travel
            # This must happen BEFORE any validation to prevent wrong action from being checked
            try:
                import json
                response_data = json.loads(ai_response_content)
                actions = response_data.get("actions", [])

                # Debug: Show what actions AI sent before any processing
                if actions:
                    action_list = [a.get("action") if isinstance(a, dict) else str(a) for a in actions]
                    print(f"DEBUG: [AI RESPONSE] Actions received: {action_list}")
                else:
                    print(f"DEBUG: [AI RESPONSE] No actions in response")

                current_module = party_tracker_data.get("module", "")
                actions_modified = False

                # Check for updatePartyTracker being used for within-module location changes
                for i, action in enumerate(actions):
                    if isinstance(action, dict) and action.get("action") == "updatePartyTracker":
                        params = action.get("parameters", {})

                        # Check if this is a location transition (has currentLocationId) vs party composition change
                        has_location_id = "currentLocationId" in params
                        has_module = "module" in params

                        if has_location_id and has_module:
                            # Check if module is the SAME as current module (within-module travel)
                            target_module = params.get("module", "")

                            if target_module == current_module:
                                # WRONG ACTION: Using updatePartyTracker for within-module travel
                                # Convert to transitionLocation
                                new_location_id = params.get("currentLocationId", "")

                                print(f"DEBUG: [ACTION FIX] Converting updatePartyTracker to transitionLocation({new_location_id}) - same module")
                                info(f"ACTION FIX: Converted updatePartyTracker to transitionLocation for within-module travel", category="action_preprocessing")

                                # Replace with transitionLocation
                                actions[i] = {
                                    "action": "transitionLocation",
                                    "parameters": {
                                        "newLocation": new_location_id
                                    }
                                }
                                actions_modified = True

                # Update response if we modified actions
                if actions_modified:
                    response_data['actions'] = actions
                    ai_response_content = json.dumps(response_data)
                    info(f"ACTION FIX: Updated response with corrected action types", category="action_preprocessing")

            except (json.JSONDecodeError, Exception) as e:
                debug(f"Could not pre-process actions: {e}", category="action_preprocessing")

            # PRE-VALIDATION: Check for transitionLocation and call transition intelligence agent
            transition_check_passed = True
            try:
                import json
                response_data = json.loads(ai_response_content)  # Re-parse in case it was modified
                actions = response_data.get("actions", [])

                # Check if any action is transitionLocation
                for action in actions:
                    if isinstance(action, dict) and action.get("action") == "transitionLocation":
                        # Quick check: Reject same-location transitions immediately (no agent needed)
                        new_location = action.get("parameters", {}).get("newLocation", "")
                        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]

                        if new_location == current_location_id:
                            # Same location transition - STRIP the action instead of retrying
                            info(f"VALIDATION: Same-location transition detected ({current_location_id}), stripping action", category="location_transitions")
                            print(f"DEBUG: [SAME-LOCATION] Stripping transitionLocation({current_location_id}) from response")

                            # Remove this action from the actions array
                            actions.remove(action)

                            # Update the response content with stripped actions
                            response_data['actions'] = actions
                            ai_response_content = json.dumps(response_data)

                            # Don't retry - continue with modified response
                            info(f"VALIDATION: Same-location action stripped, continuing with narration only", category="location_transitions")
                            break  # Exit action checking loop, proceed to normal validation

                        # Found transitionLocation - call transition intelligence agent
                        from core.ai.action_handler import pre_validate_transition

                        # TABLETOP MODE: Pass raw player input for pre-validation (not DM-note-augmented)
                        # This provides clearer intent to the transition validator
                        raw_player_input_for_transition = user_input_text

                        transition_approved, transition_error = pre_validate_transition(
                            action.get("parameters", {}),
                            party_tracker_data,
                            conversation_history,
                            location_graph,
                            path_manager,
                            raw_player_input=raw_player_input_for_transition
                        )

                        if not transition_approved:
                            # Transition blocked - store transient correction and retry
                            # TABLETOP MODE: Step 3.2 - Use retry-local variable (not persisted to history)
                            retry_correction_note = f"Error Note: {transition_error}. Please adjust your response accordingly."
                            debug(f"RETRY: Stored transient transition correction (not persisted)", category="ai_validation")
                            retry_count += 1
                            transition_check_passed = False
                            info(f"VALIDATION: Transition blocked by intelligence agent, retry {retry_count}", category="location_transitions")
                            break  # Don't check other actions, retry immediately

            except (json.JSONDecodeError, Exception) as e:
                # If we can't parse the response, let the normal validator handle it
                debug(f"Could not pre-validate transition: {e}", category="location_transitions")

            if not transition_check_passed:
                continue  # Skip to next retry iteration

            validation_result = validate_ai_response(ai_response_content, user_input_text, validation_prompt_text, conversation_history, party_tracker_data)
        
            # Unpack the validation result tuple
            is_valid = False
            validation_reason = ""
            if isinstance(validation_result, tuple):
                is_valid, validated_content = validation_result
                if is_valid:
                    # Use the fixed/validated content if auto-fix was applied
                    ai_response_content = validated_content
                else:
                    validation_reason = validated_content  # It's the error message when invalid
            else:
                # Handle old-style return (shouldn't happen after our change)
                is_valid = validation_result is True
                validation_reason = validation_result if isinstance(validation_result, str) else ""
            
            if is_valid:
                valid_response_received = True
                # TABLETOP MODE: Step 3.2 - Clear transient correction note on success
                retry_correction_note = None
                debug(f"SUCCESS: Valid response generated on attempt {retry_count + 1}", category="ai_validation")
            
                # SIMPLIFIED ARCHITECTURE: process_ai_response now handles ALL complexity internally.
                # This includes:
                # - Standard turn processing
                # - Combat encounters (via needs_post_combat_narration signal)
                # - Location transitions (with seamless narration generation)
                # - Level-up sessions (returned as enter_levelup_mode signal)
                # - All conversation history updates
                # The main loop is now just a thin orchestration layer.
                final_result = process_ai_response(ai_response_content, party_tracker_data, location_data, conversation_history)

                # After processing, we only need to check for control flow signals.
                # Everything else (including history updates) has been handled by process_ai_response.
                if final_result == "exit":
                    return
                elif final_result == "restart":
                    print("\n[SYSTEM] Restarting game with restored save...\n")
                    main_game_loop()
                    return
                elif final_result == "creation_retry":
                    info(
                        "CHARACTER_CREATION: Retrying corrected final JSON in active creation mode",
                        category="character_creation",
                    )
                    retry_count += 1
                    valid_response_received = False
                    if retry_count >= 5:
                        abort_character_creation_session(reason="final_json_retry_exhausted")
                        error(
                            "CHARACTER_CREATION: Final JSON correction retries exhausted",
                            category="character_creation",
                        )
                        print(colored("[SYSTEM]", "yellow"), colored(
                            "Character creation failed after repeated correction attempts. Creation mode was closed and the prior narrative state was restored.",
                            "yellow",
                        ))
                        status_ready()
                        continue
                    continue
                elif final_result == "creation_error":
                    abort_character_creation_session(reason="creation_terminal_error")
                    print(colored("[SYSTEM]", "yellow"), colored(
                        "Character creation failed and was closed. Prior narrative state was restored.",
                        "yellow",
                    ))
                    status_ready()
                    continue
                elif isinstance(final_result, dict) and final_result.get("status") == "enter_levelup_mode":
                    # Enter the level up sub-loop
                    level_up_session = final_result["session"]
                    final_narration = ""

                    # TABLETOP MODE: Suppress TTS during level-up interview flow
                    with _tts_block_scope():
                        # Get the first message from the session
                        dm_response = level_up_session.start()
                    
                        # Display the first message and add to history
                        print(colored("Dungeon Master:", "blue"), colored(dm_response, "blue"))
                        conversation_history.append({"role": "assistant", "content": dm_response})
                        save_conversation_history(conversation_history)

                        # Loop until the session is complete
                        while not level_up_session.is_complete:
                            # Get player input
                            player_name_display = f"{SOLID_GREEN}{player_name_actual}{RESET_COLOR}"
                            level_up_input = input(f"{player_name_display} (Leveling Up): ")

                            if not level_up_input or not level_up_input.strip():
                                continue
                        
                            # Handle the input and get the next AI response from the session
                            dm_response = level_up_session.handle_input(level_up_input)

                            # Check if the response is the final JSON or a conversational step
                            try:
                                # It's the final JSON response
                                parsed_data = json.loads(dm_response)
                                final_narration = parsed_data.get("narration", "Level up complete!")
                                print(colored("Dungeon Master:", "blue"), colored(final_narration, "blue"))
                                # The session is now complete, loop will exit
                            except (json.JSONDecodeError, TypeError):
                                # It's a normal conversational response
                                print(colored("Dungeon Master:", "blue"), colored(dm_response, "blue"))

                        # After the loop, the session is complete.
                        if level_up_session.success:
                            debug("SUCCESS: Level up successful. Using final narration for context.", category="level_up")
                            # Add the final, high-quality narration to the history as the definitive AI response.
                            # This provides perfect context for the next turn without an extra AI call.
                            conversation_history.append({"role": "assistant", "content": json.dumps({"narration": final_narration, "actions": []})})
                            save_conversation_history(conversation_history)
                        else:
                            # If the level up failed, inform the player and log it.
                            print(colored("Dungeon Master:", "red"), colored(level_up_session.summary, "red"))
                            conversation_history.append({"role": "system", "content": level_up_session.summary})
                            save_conversation_history(conversation_history)

                    # Break the outer validation loop and proceed to the next turn.
                    break 

                # CRITICAL: Reload conversation history from disk.
                # Since process_ai_response handles all history updates internally (including sub-systems
                # like combat that may add multiple messages), we must reload to ensure our local
                # conversation_history variable matches the persisted state.
                # This is the ONLY place the main loop needs to manage conversation_history.
                conversation_history = load_json_file(json_file) or []
                # No need to save here, as process_ai_response already handled all persistence.

            elif not is_valid and validation_reason:
                # Validation failed with a reason
                debug(f"VALIDATION: Validation failed. Reason: {validation_reason}", category="ai_validation")
                status_retrying(retry_count + 1, 5)

                # TABLETOP MODE: Step 3.2 - Short-circuit novel updatePartyNPCs retry loops.
                redirect_msg = get_new_pc_creation_retry_guard_message(
                    user_input_text,
                    ai_response_content,
                    party_tracker_data,
                )
                if redirect_msg:
                    info(
                        "VALIDATION: Redirecting novel updatePartyNPCs identity to dedicated creation flow",
                        category="ai_validation",
                    )
                    print(colored(redirect_msg, "yellow"))
                    sys.stdout.flush()
                    retry_correction_note = None
                    new_pc_creation_redirected = True
                    break
                
                # TABLETOP MODE: Task 3.3 - Repeated reason short-circuit detection
                # Check if this is the same deterministic reason as last time
                normalized_reason = validation_reason.strip().lower()
                if last_validation_reason and normalized_reason == last_validation_reason:
                    repeated_reason_count += 1
                    if repeated_reason_count >= 1:  # Same reason twice = short-circuit
                        error(f"VALIDATION: Same deterministic reason repeated twice ({repeated_reason_count}), short-circuiting retry loop", category="ai_validation")
                        # Force exhaustion by setting retry_count to max
                        retry_count = 5
                        break  # Exit retry loop immediately
                else:
                    # New reason - reset counter and store
                    last_validation_reason = normalized_reason
                    repeated_reason_count = 0
                
                # TABLETOP MODE: Task 3.1 - Do NOT append failed assistant output for deterministic guard failures
                # The AI only needs the correction note, not the invalid response
                
                # TABLETOP MODE: Task 3.2 - Concise normalized correction note
                # Use shorter, stable correction message to reduce token bloat
                is_deterministic = (
                    "npc arrival state sync" in normalized_reason or
                    "transition pre-validation" in normalized_reason or
                    "validation failed" in normalized_reason
                )
                
                if is_deterministic:
                    # Concise deterministic guard correction
                    correction_note = f"[CORRECTION REQUIRED]: {validation_reason}"
                else:
                    # Standard correction for non-deterministic failures
                    correction_note = f"Error Note: {validation_reason}. Please adjust your response."
                
                # TABLETOP MODE: Step 3.2 - Store correction in retry-local variable (not persisted)
                # Transient correction will be passed to next get_ai_response() call
                retry_correction_note = correction_note
                debug(f"RETRY: Stored transient correction note (not persisted to history)", category="ai_validation")
                retry_count += 1
            else: 
                warning(f"VALIDATION: Unexpected validation result: is_valid={is_valid}, reason={validation_reason}. Retrying.", category="ai_validation")
                retry_count += 1
    
        # TABLETOP MODE: Step 3.2 - Creation-flow redirect is terminal for this turn.
        if new_pc_creation_redirected:
            status_ready()
            continue

        # TABLETOP MODE C1.1: Fail-closed - do NOT execute invalid responses after validation exhaustion
        if not valid_response_received:
            error("FAILURE: Failed to generate a valid response after 5 attempts. STOPPING to prevent desync.", category="ai_validation")
            # C1.A1: No code path executes invalid combat response as canonical progression
            # Add deterministic error instead of executing invalid response
            error_message = get_validation_retry_exhaustion_message()
            conversation_history.append({"role": "system", "content": error_message})
            save_conversation_history(conversation_history)
            # C1.A2: Encounter init failure does not continue normal combat narration flow
            # Abort turn processing - skip post-turn history update path
            status_ready()
            continue

        # This block now only runs if a response was NOT held
        # CRITICAL: Reload party tracker to ensure we have the latest module information after any updates
        party_tracker_data = load_json_file("party_tracker.json")
        print(f"DEBUG: [Before update_conversation_history] Reloaded party tracker. Module: {party_tracker_data.get('module', 'Unknown')}")
    
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"] 
        # Use current module from party tracker for plot data  
        module_name_updated = party_tracker_data.get("module", "").replace(" ", "_")
        updated_path_manager = ModulePathManager(module_name_updated)
        plot_data = load_json_file(updated_path_manager.get_plot_path())
        module_data = load_json_file(updated_path_manager.get_module_file_path())
        debug(f"FILE_OP: Updated plot file path: {updated_path_manager.get_plot_path()}", category="module_management")

        debug(f"STATE_CHANGE: Before AI response update_conversation_history - history has {len(conversation_history)} messages", category="conversation_management")
        conversation_history = update_conversation_history(conversation_history, party_tracker_data, plot_data, module_data)
        debug(f"STATE_CHANGE: After AI response update_conversation_history - history has {len(conversation_history)} messages", category="conversation_management")
        conversation_history = update_character_data(conversation_history, party_tracker_data)
        conversation_history = ensure_main_system_prompt(conversation_history, main_system_prompt_text)
    
        # Use the new order_conversation_messages function
        conversation_history = order_conversation_messages(conversation_history, main_system_prompt_text)
    
        save_conversation_history(conversation_history)

def main():
    """Main entry point with startup wizard integration"""
    setup_utf8_console()
    
    # Check if config.py exists, create from template if not
    import os
    import shutil
    if not os.path.exists('config.py'):
        print("[D20] Welcome to NeverEndingQuest! [D20]")
        print("\nFirst-time setup detected...")
        
        try:
            # Copy config_template.py to config.py
            shutil.copy('config_template.py', 'config.py')
            print("\n✓ Created config.py from template")
            print("\n" + "="*60)
            print("IMPORTANT: OpenAI API Key Required")
            print("="*60)
            print("\n1. Open config.py in a text editor")
            print("2. Find the line: OPENAI_API_KEY = \"your_openai_api_key_here\"")
            print("3. Replace \"your_openai_api_key_here\" with your actual OpenAI API key")
            print("4. Save the file and run the game again")
            print("\nGet your API key at: https://platform.openai.com/api-keys")
            print("\n" + "="*60)
            input("\nPress Enter to exit...")
            return
        except Exception as e:
            print(f"[ERROR] Failed to create config.py: {e}")
            print("Please manually copy config_template.py to config.py")
            input("\nPress Enter to exit...")
            return
    
    # Initialize all required directories
    required_dirs = [
        "modules/conversation_history",
        "modules/campaign_archives", 
        "modules/campaign_summaries",
        "modules/backups",
        "modules/logs",
        "save_games",
        "characters",
        "combat_logs"
    ]
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    # DISABLED FOR DEBUGGING - Create empty party tracker if it doesn't exist (in root directory)
    # party_tracker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'party_tracker.json')
    # if not os.path.exists(party_tracker_path):
    #     empty_party_tracker = {
    #         "module": "",
    #         "partyMembers": [],
    #         "partyNPCs": [],
    #         "worldConditions": {
    #             "year": 1492,
    #             "month": "Springmonth",
    #             "day": 1,
    #             "time": "08:00:00",
    #             "weather": "",
    #             "season": "Spring",
    #             "dayNightCycle": "Day",
    #             "moonPhase": "New Moon",
    #             "currentLocation": "",
    #             "currentLocationId": "",
    #             "currentArea": "",
    #             "currentAreaId": "",
    #             "majorEventsUnderway": [],
    #             "politicalClimate": "",
    #             "activeEncounter": "",
    #             "activeCombatEncounter": ""
    #         }
    #     }
    #     try:
    #         with open(party_tracker_path, 'w', encoding='utf-8') as f:
    #             json.dump(empty_party_tracker, f, indent=2)
    #         print(f"[INFO] Created empty party_tracker.json in root directory for first-time setup")
    #     except Exception as e:
    #         print(f"[WARNING] Could not create party_tracker.json in root: {e}")
    
    # Always initialize game files from BU templates if needed
    from utils.startup_wizard import initialize_game_files_from_bu
    initialize_game_files_from_bu()
    
    # Run character repair utility to ensure all sheets are synchronized and valid
    try:
        print("[SYSTEM] Running character repair service...")
        from scripts.repair_all_characters import repair_all
        repair_all()
    except Exception as e:
        print(f"[WARNING] Character repair service encountered an issue: {e}")
    
    # Run calendar migration check
    from utils.calendar_migration import run_calendar_migration
    run_calendar_migration()
    
    # Check if first-time setup is needed
    try:
        from utils.startup_wizard import startup_required, run_startup_sequence
        
        if startup_required():
            print("[D20] Welcome to your 5th Edition Adventure! [D20]")
            print("It looks like this is your first time, or you need to set up a character.")
            print("Let's get you ready for adventure!\n")
            
            success = run_startup_sequence()
            if not success:
                print("[ERROR] Setup was cancelled or failed. Exiting...")
                return
            
            print("Setup complete! Your adventure begins now...\n")
    
    except Exception as e:
        warning(f"INITIALIZATION: Startup wizard had an issue", category="startup")
        print("Continuing with main game (assuming setup is complete)...\n")

    # Initialize the global location graph AFTER all modules are stitched and ready
    global location_graph
    print("DEBUG: [LocationGraph] Initializing global graph for game session...")
    location_graph = LocationGraph()
    location_graph.load_module_data()
    print(f"DEBUG: [LocationGraph] Initialization complete. Total nodes loaded: {len(location_graph.nodes)}")
    print(f"DEBUG: [LocationGraph] Total edges loaded: {sum(len(edges) for edges in location_graph.edges.values())}")
    if len(location_graph.nodes) > 0:
        print(f"DEBUG: [LocationGraph] First 5 location IDs: {list(location_graph.nodes.keys())[:5]}")
    else:
        print("DEBUG: [LocationGraph] WARNING - No nodes loaded! Check if modules are integrated.")

    # Continue with normal game loop
    main_game_loop()

if __name__ == "__main__":
    main()
