# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Combat Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# COMBAT_MANAGER.PY - TURN-BASED COMBAT SYSTEM
# ============================================================================
#
# ARCHITECTURE ROLE: Game Systems Layer - Combat Management
#
# This module provides comprehensive turn-based combat management for the 5th edition
# Dungeon Master system, implementing AI-driven combat encounters with full rule
# compliance and intelligent resource tracking.
#
# KEY RESPONSIBILITIES:
# - Turn-based combat orchestration with initiative order management
# - AI-powered combat decision making for NPCs and monsters
# - Combat state validation and rule compliance verification
# - Experience point calculation and reward distribution
# - Combat logging and debugging support with per-encounter directories
# - Real-time combat status display and resource tracking
# - Preroll dice caching system to prevent AI manipulation
#

"""
Combat Manager Module for NeverEndingQuest

Handles combat encounters between players, NPCs, and monsters.

Features:
- Manages turn-based combat with initiative order
- Processes player actions and AI responses
- Generates combat summaries and experience rewards
- Maintains combat logs for debugging and analysis
- Round-based preroll caching to ensure dice consistency
- Real-time combat state display with dynamic resource tracking

Combat Logging System:
- Creates per-encounter logs in the combat_logs/{encounter_id}/ directory
- Generates both timestamped and "latest" versions of each log
- Maintains a combined log of all encounters in all_combat_latest.json
- Filters out system messages for cleaner, more readable logs

"""
# ============================================================================
# COMBAT_MANAGER.PY - GAME SYSTEMS LAYER - COMBAT
# ============================================================================
# 
# ARCHITECTURE ROLE: Game Systems Layer - Turn-Based Combat Management
# 
# This module implements 5e combat mechanics using AI-driven simulation
# with strict rule validation. It demonstrates our multi-model AI strategy
# by using specialized models for combat-specific interactions.
# 
# KEY RESPONSIBILITIES:
# - Manage turn-based combat encounters with initiative tracking
# - Validate combat actions against 5e rules
# - Coordinate HP tracking, status effects, and combat state
# - Generate and manage pre-rolled dice to prevent AI confusion
# - Cache prerolls per combat round to ensure consistency
# - Track combat rounds through AI responses
# - Provide specialized combat AI prompts and validation
# - Real-time dynamic state display for combat awareness
# 
# COMBAT STATE DISPLAY PHILOSOPHY:
# - REAL-TIME AWARENESS: Shows current HP, spell slots, conditions during combat
# - RESOURCE TRACKING: Displays available spell slots for tactical decisions
# - DYNAMIC UPDATES: Reflects changes immediately as they occur
# - AI CLARITY: Provides authoritative current state to prevent confusion
# 
# COMBAT INFORMATION ARCHITECTURE:
# - DYNAMIC STATE DISPLAY: Current HP, spell slots, active conditions
# - STATIC REFERENCE: Character abilities remain in system messages
# - SEPARATION PRINCIPLE: Combat state vs character capabilities
# - TACTICAL FOCUS: Information relevant to immediate combat decisions
# 
# COMBAT FLOW:
# Encounter Start -> Initiative Roll -> Turn Management -> Action Resolution ->
# Validation -> State Update -> Dynamic State Display -> Win/Loss Conditions
# 
# AI INTEGRATION:
# - Specialized combat model for turn-based interactions
# - Pre-rolled dice system prevents AI attack count confusion
# - Combat-specific validation model for rule compliance
# - Real-time HP and status tracking with state synchronization
# - Dynamic spell slot tracking for spellcaster resource management
# 
# ARCHITECTURAL INTEGRATION:
# - Called by action_handler.py for combat-related actions
# - Uses generate_prerolls.py for dice management
# - Integrates with party_tracker.json for state persistence
# - Implements our "Defense in Depth" validation strategy
# 
# DESIGN PATTERNS:
# - State Machine: Combat phases and turn management
# - Strategy Pattern: Different AI models for different combat aspects
# - Observer Pattern: Real-time combat state updates
# 
# This module exemplifies our approach to complex game system management
# while maintaining strict 5e rule compliance through AI validation.
# ============================================================================

import json
import os
import sys
import time
import re
import random
import subprocess
import threading
from typing import Any, Dict, List, Optional

# Add project root to sys.path for direct execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from model_config import (
    USE_COMPRESSED_COMBAT,
    COMBAT_API_TIMEOUT_SECONDS,
    COMPRESSION_ENABLED,
    VALIDATION_COMPRESSION_MIN_CHARS,
)
from datetime import datetime
from utils.xp import main as calculate_xp
from utils.ai_client_factory import create_chat_client

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response, get_usage_stats
    USAGE_TRACKING_AVAILABLE = True
    print("[COMBAT_MANAGER] OpenAI usage tracking enabled")
except Exception as e:
    USAGE_TRACKING_AVAILABLE = False
    print(f"[COMBAT_MANAGER] OpenAI usage tracking not available: {e}")
    def track_response(r): pass
    def get_usage_stats(): return {}
# Import model configurations from config.py
from config import (
    OPENAI_API_KEY,
    COMBAT_MAIN_MODEL,
    # Use the existing validation model instead of COMBAT_VALIDATION_MODEL
    DM_VALIDATION_MODEL, 
    COMBAT_DIALOGUE_SUMMARY_MODEL,
    DM_MINI_MODEL
)
from updates.update_character_info import update_character_info, normalize_character_name
from utils.character_state_hygiene import normalize_life_state_fields
import updates.update_encounter as update_encounter
import updates.update_party_tracker as update_party_tracker
# Import the preroll generator
from core.generators.generate_prerolls import generate_prerolls
# Import safe JSON functions
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
import core.ai.cumulative_summary as cumulative_summary
from utils.enhanced_logger import debug, info, warning, error, game_event, set_script_name
from utils.save_roll_contract import calculate_concentration_dc
from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck
from utils.validation_routing import (
    get_validation_compression_decision,
    build_validation_routing_telemetry,
)
# Import combat message compressor for optimizing conversation history
from core.ai.combat_compressor import CombatUserMessageCompressor
# Import inventory context matcher for enhancing player combat actions
from core.ai.inventory_context_integration import enhance_player_input_with_inventory

# Import combat state sync helpers (plugin-style)
# TABLETOP MODE: Phase and roster synchronization helpers
try:
    from core.managers.combat_state_sync import (
        apply_opening_batch_marker,
        normalize_multi_pc_roster,
    )
    COMBAT_STATE_SYNC_AVAILABLE = True
except ImportError:
    COMBAT_STATE_SYNC_AVAILABLE = False
    def apply_opening_batch_marker(encounter_data, starts_with):
        """Fallback: No-op if combat_state_sync not available."""
        return False
    def normalize_multi_pc_roster(encounter_data, party_tracker_data, path_manager):
        """Fallback: No-op if combat_state_sync not available."""
        return encounter_data, False

# Import multi-PC combat manager (plugin-style)
try:
    from core.managers.multi_pc_combat import (
        create_combat_manager,
        get_combat_manager,
        is_multi_pc_combat_enabled,
        modify_combat_prompt_for_multi_pc,
        get_multi_pc_initiative_narrative,
        emit_combat_event,
        CombatantType,
        PCStatus
    )
    MULTI_PC_COMBAT_AVAILABLE = True
except ImportError:
    MULTI_PC_COMBAT_AVAILABLE = False
    def get_combat_manager(): return None
    def is_multi_pc_combat_enabled(): return False
    def modify_combat_prompt_for_multi_pc(base_prompt, pc_name, manager): return base_prompt
    def get_multi_pc_initiative_narrative(manager): return ""

# Set script name for logging
set_script_name(__name__)

# Remove color constants - no longer used
# Color codes removed per CLAUDE.md guidelines

# Temperature
TEMPERATURE = 0.8


def build_request_roll_action(
    character_name: str,
    roll_type: str,
    dc: int,
    reason: str,
    ability: str = None,
    skill: str = None,
    advantage: str = "normal",
) -> dict:
    """Build a lightweight requestRoll action payload (scaffolding helper)."""
    parameters = {
        "characterName": character_name,
        "rollType": roll_type,
        "dc": dc,
        "reason": reason,
        "advantage": advantage,
    }
    if ability:
        parameters["ability"] = ability
    if skill:
        parameters["skill"] = skill
    return {
        "action": "requestRoll",
        "parameters": parameters,
    }


def get_concentration_request_dc(damage_taken: int) -> int:
    """Return deterministic concentration save DC for requestRoll scaffolding."""
    return calculate_concentration_dc(damage_taken)

def get_combat_temperature(encounter_data, validation_attempt=0):
    """
    Calculate temperature for main combat processing based on encounter complexity.
    More creatures = lower temperature for better logical processing.
    Additional reduction applied for validation failures to improve consistency.
    
    Args:
        encounter_data: The encounter data containing creature information
        validation_attempt: The current validation attempt number (0 = first try)
    
    Returns:
        float: Temperature value between 0.1 and 0.8
    """
    creatures = encounter_data.get("creatures", [])
    creature_count = len(creatures)
    
    # Base temperature based on creature count
    if creature_count > 8:
        base_temp = 0.4
        complexity = "massive"
    elif creature_count > 6:
        base_temp = 0.5
        complexity = "very complex"
    elif creature_count > 4:
        base_temp = 0.6
        complexity = "complex"
    else:
        base_temp = 0.8
        complexity = "normal"
    
    # Apply reduction for validation failures
    # Each failure reduces temperature by 0.1, max reduction of 0.4
    temperature_reduction = min(validation_attempt * 0.1, 0.4)
    final_temp = max(base_temp - temperature_reduction, 0.1)  # Never go below 0.1
    
    # Round to 2 decimal places to avoid floating-point display issues
    final_temp = round(final_temp, 2)
    
    # Log the temperature selection
    if validation_attempt == 0:
        print(f"[COMBAT_MANAGER] Using temperature {final_temp} for {complexity} encounter ({creature_count} creatures)")
    else:
        print(f"[COMBAT_MANAGER] Lowering temperature from {base_temp:.1f} to {final_temp} after validation failure (attempt {validation_attempt + 1})")
    
    return final_temp

# AI client (factory supports OpenAI and OpenRouter)
client = create_chat_client()

conversation_history_file = "modules/conversation_history/combat_conversation_history.json"
second_model_history_file = "modules/conversation_history/second_model_history.json"
third_model_history_file = "modules/conversation_history/third_model_history.json"

# Create a combat_logs directory if it doesn't exist
os.makedirs("combat_logs", exist_ok=True)

# Initialize combat message compressor with API key
combat_message_compressor = CombatUserMessageCompressor(api_key=OPENAI_API_KEY)

# Constants for chat history generation
HISTORY_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def load_npc_with_fuzzy_match(npc_name, path_manager):
    """
    Load NPC data with fuzzy name matching support.
    First tries exact match, then falls back to fuzzy matching if needed.
    
    Args:
        npc_name: The NPC name to look for
        path_manager: ModulePathManager instance
        
    Returns:
        tuple: (npc_data, matched_filename) or (None, None) if not found
    """
    from utils.encoding_utils import safe_json_load
    
    # First try exact match with normalized name
    formatted_npc_name = path_manager.format_filename(npc_name)
    npc_file = path_manager.get_character_path(formatted_npc_name)
    npc_data = safe_json_load(npc_file)
    
    if npc_data:
        debug(f"NPC_LOAD: Exact match found for '{npc_name}' -> '{formatted_npc_name}'", category="combat_manager")
        return npc_data, formatted_npc_name
    
    # If exact match fails, try fuzzy matching
    debug(f"NPC_LOAD: Exact match failed for '{formatted_npc_name}', attempting fuzzy match", category="combat_manager")
    
    # Get all character files in the module
    import glob
    # Use the unified characters directory
    character_dir = "characters"
    character_files = glob.glob(os.path.join(character_dir, "*.json"))
    
    best_match = None
    best_score = 0
    best_filename = None
    
    for char_file in character_files:
        # Skip backup files
        if char_file.endswith(".bak") or char_file.endswith("_BU.json") or "backup" in char_file:
            continue
            
        # Load the character data to check if it's an NPC
        char_data = safe_json_load(char_file)
        # Check both character_type (correct field) and characterType (legacy) for compatibility
        char_type = char_data.get("character_type") or char_data.get("characterType")
        if char_data and char_type == "npc":
            char_name = char_data.get("name", "")
            # Simple fuzzy matching - check if key words from requested name are in character name
            requested_words = set(formatted_npc_name.lower().split("_"))
            char_words = set(char_name.lower().replace(" ", "_").split("_"))
            
            # Debug log for fuzzy matching
            debug(f"NPC_FUZZY: Comparing '{formatted_npc_name}' with '{char_name}' from {char_file}", category="combat_manager")
            debug(f"NPC_FUZZY: Requested words: {requested_words}, Character words: {char_words}", category="combat_manager")
            
            # Calculate match score based on word overlap
            common_words = requested_words.intersection(char_words)
            if common_words:
                score = len(common_words) / max(len(requested_words), len(char_words))
                
                if score > best_score:
                    best_score = score
                    best_match = char_data
                    # Extract just the filename without path for consistency
                    best_filename = os.path.splitext(os.path.basename(char_file))[0]
    
    # Use best match if score is high enough (threshold: 0.5)
    if best_match and best_score >= 0.5:
        info(f"NPC_FUZZY_MATCH: Success - '{npc_name}' matched to '{best_match['name']}' (score: {best_score:.2f})", category="combat_manager")
        return best_match, best_filename
    else:
        warning(f"NPC_FUZZY_MATCH: Failed for '{npc_name}' (best score: {best_score:.2f})", category="combat_manager")
        return None, None


def get_current_area_id():
    party_tracker = safe_json_load("party_tracker.json")
    if not party_tracker:
        error("FILE_OP: Failed to load party_tracker.json", category="file_operations")
        return None
    return party_tracker["worldConditions"]["currentAreaId"]

def get_location_data(location_id):
    from utils.module_path_manager import ModulePathManager
    from utils.encoding_utils import safe_json_load
    # Get current module from party tracker for consistent path resolution
    try:
        party_tracker = safe_json_load("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    
    current_area_id = get_current_area_id()
    debug(f"STATE_CHANGE: Current area ID: {current_area_id}", category="combat_events")
    area_file = path_manager.get_area_path(current_area_id)
    debug(f"FILE_OP: Attempting to load area file: {area_file}", category="file_operations")

    if not os.path.exists(area_file):
        error(f"FILE_OP: Area file {area_file} does not exist", category="file_operations")
        return None

    area_data = safe_json_load(area_file)
    if not area_data:
        error(f"FILE_OP: Failed to load area file: {area_file}", category="file_operations")
        return None
    debug(f"FILE_OP: Loaded area data: {json.dumps(area_data, indent=2)}", category="file_operations")

    for location in area_data["locations"]:
        if location["locationId"] == location_id:
            debug(f"VALIDATION: Found location data for ID {location_id}", category="combat_events")
            return location

    error(f"VALIDATION: Location with ID {location_id} not found in area data", category="combat_events")
    return None

def read_prompt_from_file(filename):
    # Prompts are now in the prompts/ directory at project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, '..', '..')
    
    # Check if this is a combat prompt and use compressed version if toggle is on
    if USE_COMPRESSED_COMBAT:
        if filename == 'combat/combat_sim_prompt.txt':
            filename = 'combat/combat_sim_prompt_compressed.txt'
            debug("Using compressed combat prompt", category="combat_events")
        elif filename == 'combat/combat_sim_prompt_multipc.txt':
            filename = 'combat/combat_sim_prompt_multipc_compressed.txt'
            debug("Using compressed multi-pc combat prompt", category="combat_events")
    
    file_path = os.path.join(project_root, 'prompts', filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except Exception as e:
        error(f"FILE_OP: Failed to read prompt file {filename}: {str(e)}", category="file_operations")
        return ""

def load_monster_stats(monster_name):
    # Import the path manager
    from utils.module_path_manager import ModulePathManager
    from utils.encoding_utils import safe_json_load
    # Get current module from party tracker for consistent path resolution
    try:
        party_tracker = safe_json_load("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    
    # Get the correct path for the monster file
    monster_file = path_manager.get_monster_path(monster_name)

    monster_stats = safe_json_load(monster_file)
    if not monster_stats:
        error(f"FILE_OP: Failed to load monster file: {monster_file}", category="file_operations")
    return monster_stats

def load_json_file(file_path):
    data = safe_json_load(file_path)
    if data is None:
        # If file doesn't exist or has invalid JSON, return an empty list
        return []
    return data

def save_json_file(file_path, data):
    try:
        safe_write_json(file_path, data)
    except Exception as e:
        error(f"FILE_OP: Failed to save {file_path}: {str(e)}", category="file_operations")


class CombatSessionAlreadyActiveError(RuntimeError):
    """Raised when a second combat loop attempts to start concurrently."""


_combat_session_lock = threading.Lock()
_active_combat_session_id = None


def _enter_combat_session(encounter_id):
    """Claim the single active combat loop slot for this process."""
    global _active_combat_session_id

    with _combat_session_lock:
        if _active_combat_session_id is not None:
            raise CombatSessionAlreadyActiveError(
                f"Combat session already active for encounter '{_active_combat_session_id}'"
            )
        _active_combat_session_id = encounter_id


def _exit_combat_session(encounter_id):
    """Release the active combat loop slot after combat exits."""
    global _active_combat_session_id

    with _combat_session_lock:
        if _active_combat_session_id == encounter_id:
            _active_combat_session_id = None

def clean_combat_state_blocks(conversation_history):
    """
    Remove the instructional combat state blocks from all but the most recent user message.
    This prevents bloating the conversation with repeated instructions while preserving
    the actual player actions and narrative.
    """
    # Find all user messages that contain combat state blocks
    user_messages_with_state = []
    for i, message in enumerate(conversation_history):
        if (message.get("role") == "user" and 
            "--- CURRENT COMBAT STATE ---" in message.get("content", "")):
            user_messages_with_state.append(i)
    
    # If we have more than one, clean all but the last one
    if len(user_messages_with_state) > 1:
        for idx in user_messages_with_state[:-1]:  # All except the last one
            content = conversation_history[idx]["content"]
            
            # Extract just the player's actual message
            # Look for the pattern "Player: " after the state block ends
            if "Player: " in content:
                # Find where the state block ends (after "--- END OF STATE & DICE ---")
                if "--- END OF STATE & DICE ---" in content:
                    # Split on the end marker and then find the player message
                    parts = content.split("--- END OF STATE & DICE ---", 1)
                    if len(parts) == 2 and "Player: " in parts[1]:
                        # Extract just the player's message
                        player_parts = parts[1].split("Player: ", 1)
                        if len(player_parts) == 2:
                            player_msg = player_parts[1].split("\n\nNow, continue the combat flow", 1)[0].strip()
                            # Replace the entire message with just the player's input
                            conversation_history[idx]["content"] = f"Player: {player_msg}"
                            continue
            
            # Fallback: If we can't extract cleanly, at least remove the bulk of the state
            # but keep any player message
            if "Player: " in content:
                player_split = content.split("Player: ", 1)
                if len(player_split) == 2:
                    player_msg = player_split[1].split("\n\nNow, continue the combat flow", 1)[0].strip()
                    conversation_history[idx]["content"] = f"Player: {player_msg}"
    
    return conversation_history

def clean_old_dm_notes(conversation_history):
    """
    Clean up old Dungeon Master Notes from conversation history while preserving critical information.
    Keeps round tracking, HP status, and basic combat state for the last 2 rounds.
    This reduces token usage while maintaining enough context for proper combat flow.
    """
    # Find all DM note indices
    dm_note_indices = []
    for i, message in enumerate(conversation_history):
        if message.get("role") == "user" and "Dungeon Master Note:" in message.get("content", ""):
            dm_note_indices.append(i)
    
    # Keep the last 3 DM notes fully intact, clean older ones
    keep_full_count = 3
    
    for i, message in enumerate(conversation_history):
        if (message.get("role") == "user" and 
            "Dungeon Master Note:" in message.get("content", "")):
            
            # Check if this is one of the recent DM notes to keep
            note_index_in_list = dm_note_indices.index(i) if i in dm_note_indices else -1
            if note_index_in_list >= len(dm_note_indices) - keep_full_count:
                # Keep this note fully intact
                continue
            
            # Clean older DM notes but preserve essential information
            content = message["content"]
            
            # Extract round information
            round_match = re.search(r"COMBAT ROUND (\d+)", content)
            round_info = f"Round {round_match.group(1)}" if round_match else ""
            
            # Extract HP state information
            hp_pattern = r"HP: \d+/\d+"
            hp_matches = re.findall(hp_pattern, content)
            hp_info = ", ".join(hp_matches) if hp_matches else ""
            
            # Extract player's message
            player_split = content.split("Player:", 1)
            player_msg = player_split[1].strip() if len(player_split) == 2 else ""
            
            # Construct cleaned message with essential info
            cleaned_parts = []
            if round_info:
                cleaned_parts.append(round_info)
            if hp_info:
                cleaned_parts.append(f"HP: {hp_info}")
            if player_msg:
                cleaned_parts.append(f"Player: {player_msg}")
            
            if cleaned_parts:
                message["content"] = f"Dungeon Master Note: {'. '.join(cleaned_parts)}"
            else:
                # Keep the original message to see what's not being extracted
                # This helps identify what other user messages are in the conversation
                # (e.g., "resuming combat", system messages, etc.)
                pass  # Don't modify the message - keep original content
    
    return conversation_history

def is_valid_json(json_string):
    try:
        json_object = json.loads(json_string)
        if not isinstance(json_object, dict):
            return False
        if "narration" not in json_object or not isinstance(json_object["narration"], str):
            return False
        if "actions" not in json_object or not isinstance(json_object["actions"], list):
            return False
        # Optional plan field - if present, must be a string
        if "plan" in json_object and not isinstance(json_object["plan"], str):
            return False
        return True
    except json.JSONDecodeError:
        return False

def write_debug_output(content, filename="debug_second_model.json"):
    try:
        with open(filename, "w") as debug_file:
            json.dump(content, debug_file, indent=2)
    except Exception as e:
        debug(f"FILE_OP: Writing debug output failed - {str(e)}", category="file_operations")

def parse_json_safely(text):
    """Extract and parse JSON from text, handling various formats"""
    # First, try to parse as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract from code block
    try:
        match = re.search(r'```json\n(.*?)```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
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

def check_multiple_update_encounter(actions):
    """Check if there are multiple updateEncounter actions that should be consolidated"""
    if not isinstance(actions, list):
        return False
    
    update_encounter_count = 0
    for action in actions:
        if isinstance(action, dict) and action.get("action", "").lower() == "updateencounter":
            update_encounter_count += 1
    
    return update_encounter_count > 1

def create_consolidation_prompt(parsed_response):
    """Create a retry prompt for consolidating multiple updateEncounter actions"""
    actions = parsed_response.get("actions", [])
    
    # Extract all updateEncounter changes
    encounter_changes = []
    encounter_id = None
    
    for action in actions:
        if action.get("action", "").lower() == "updateencounter":
            params = action.get("parameters", {})
            if not encounter_id:
                encounter_id = params.get("encounterId", "")
            changes = params.get("changes", "")
            if changes:
                encounter_changes.append(changes)
    
    # Create the consolidated changes description
    # Add proper punctuation between changes
    consolidated_changes = ". ".join(encounter_changes)
    if not consolidated_changes.endswith("."):
        consolidated_changes += "."
    
    retry_prompt = f"""Your previous response contained multiple updateEncounter actions, but these must be consolidated into ONE action.

IMPORTANT RULES:
1. ALL monster/enemy changes must be in ONE updateEncounter action
2. updateCharacterInfo is ONLY for players and NPCs (never monsters)
3. updateEncounter is ONLY for monsters/enemies (never players or NPCs)

You had {len(encounter_changes)} separate updateEncounter actions with these changes:
{chr(10).join(f'- {change}' for change in encounter_changes)}

Please provide a new response with:
1. The same narration and combat_round
2. ONE updateEncounter action combining all monster changes: "{consolidated_changes}"
3. Keep all other actions (updateCharacterInfo, exit, etc.) unchanged

Remember: One updateEncounter for ALL monster changes, separate updateCharacterInfo for each player/NPC change."""
    
    return retry_prompt

def create_multiple_update_requery_prompt(parsed_response):
    """Create a requery prompt when multiple updateEncounter actions are detected"""
    actions = parsed_response.get("actions", [])
    
    # Count updateEncounter actions
    update_encounter_count = 0
    for action in actions:
        if isinstance(action, dict) and action.get("action", "").lower() == "updateencounter":
            update_encounter_count += 1
    
    retry_prompt = f"""Your response contained {update_encounter_count} updateEncounter actions. This is incorrect - you must use ONLY ONE updateEncounter action that describes ALL monster changes.

CRITICAL ACTION DISTINCTION - NEVER CONFUSE THESE:
- updateCharacterInfo: Use ONLY for players (your character) and NPCs (allies/neutral characters)
  - These have their own character files that store their HP, inventory, etc.
  - Example: updateCharacterInfo for "ExampleChar_Cleric" (player) or "Scout Kira" (NPC)
  
- updateEncounter: Use ONLY for monsters/enemies in the encounter
  - These exist only within the encounter file
  - Use ONE updateEncounter action that describes ALL monster changes
  - Example: updateEncounter describing "Goblin takes 10 damage (HP 15 -> 5). Orc takes 8 damage (HP 20 -> 12)."

REMEMBER: 
- The encounter file references player/NPC files but doesn't store their HP
- Monster HP is stored directly in the encounter file
- Use exactly ONE updateEncounter action for ALL monster changes in a turn

Please provide a corrected response that:
1. Uses exactly ONE updateEncounter action for all monster changes
2. Uses updateCharacterInfo for any player/NPC changes
3. Consolidates all monster updates into the single updateEncounter's changes field"""
    
    return retry_prompt

def sanitize_unicode_for_logging(text):
    """
    Replace common Unicode characters with ASCII equivalents for logging compatibility.
    Prevents UnicodeEncodeError when logging to files on Windows.
    """
    if not isinstance(text, str):
        return text
    
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2192': '->',  # Right arrow
        '\u2190': '<-',  # Left arrow
        '\u2194': '<->',  # Left-right arrow
        '\u2014': '--',  # Em dash
        '\u2013': '-',   # En dash
        '\u201c': '"',   # Left double quotation mark
        '\u201d': '"',   # Right double quotation mark
        '\u2018': "'",   # Left single quotation mark
        '\u2019': "'",   # Right single quotation mark
        '\u2026': '...',  # Horizontal ellipsis
    }
    
    for unicode_char, ascii_replacement in replacements.items():
        text = text.replace(unicode_char, ascii_replacement)
    
    return text


def _is_combat_inventory_or_ammo_change(changes_text):
    """Return True when changes text implies inventory/ammo mutation."""
    if not isinstance(changes_text, str) or not changes_text.strip():
        return False

    lower = changes_text.lower()
    inventory_terms = (
        "inventory",
        "equipment",
        "item",
        "ammo",
        "ammunition",
        "arrow",
        "bolt",
        "quiver",
        "coin",
        "gold",
        "silver",
        "copper",
        "expended",
    )
    non_inventory_terms = (
        "hp",
        "hit point",
        "damage",
        "healed",
        "condition",
        "death save",
        "spell slot",
        "slot",
        "unconscious",
        "stabil",
    )

    if any(term in lower for term in inventory_terms):
        return True
    if any(term in lower for term in non_inventory_terms):
        return False
    return False


def _extract_touched_character_updates_from_response_json(response_json):
    """Extract touched updateCharacterInfo targets and compact change metadata."""
    if not isinstance(response_json, dict):
        return {}

    actions = response_json.get("actions", [])
    if not isinstance(actions, list):
        return {}

    touched_updates = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action") != "updateCharacterInfo":
            continue

        params = action.get("parameters", {})
        if not isinstance(params, dict):
            continue

        character_name = str(params.get("characterName", "")).strip()
        if not character_name:
            continue

        changes = params.get("changes", "")
        if not isinstance(changes, str):
            changes = ""

        entry = touched_updates.setdefault(
            character_name,
            {"changes": [], "inventory_relevant": False},
        )

        if changes.strip():
            entry["changes"].append(changes.strip())
            if _is_combat_inventory_or_ammo_change(changes):
                entry["inventory_relevant"] = True

    return touched_updates


def _build_compact_combat_truth_pack(response_json, encounter_data):
    """Build compact touched-combatant truth packs for PC/allied NPC updates."""
    touched_updates = _extract_touched_character_updates_from_response_json(response_json)
    if not touched_updates:
        return []

    allowed_names = set()
    creatures = encounter_data.get("creatures", [])
    if isinstance(creatures, list):
        for creature in creatures:
            if not isinstance(creature, dict):
                continue
            creature_type = str(creature.get("type", "")).strip().lower()
            if creature_type not in ("player", "npc"):
                continue
            creature_name = str(creature.get("name", "")).strip().lower()
            if creature_name:
                allowed_names.add(creature_name)

    from utils.pc_manager import get_character_state

    truth_packs = []
    for character_name, meta in touched_updates.items():
        normalized_name = character_name.strip().lower()
        if allowed_names and normalized_name not in allowed_names:
            continue

        character_data = get_character_state(character_name)
        if not isinstance(character_data, dict):
            continue

        hp = character_data.get("hitPoints", 0)
        max_hp = character_data.get("maxHitPoints", 0)
        try:
            hp_value = int(hp or 0)
        except (TypeError, ValueError):
            hp_value = 0
        try:
            max_hp_value = int(max_hp or 0)
        except (TypeError, ValueError):
            max_hp_value = 0

        conditions = character_data.get("condition_affected", [])
        if not isinstance(conditions, list):
            conditions = []

        spell_slots_summary = {}
        spell_slots = character_data.get("spellSlots", {})
        if not isinstance(spell_slots, dict):
            spell_slots = {}
        spellcasting = character_data.get("spellcasting")
        if isinstance(spellcasting, dict):
            nested_slots = spellcasting.get("spellSlots")
            if isinstance(nested_slots, dict):
                spell_slots = nested_slots
        if isinstance(spell_slots, dict):
            for level, slot_data in spell_slots.items():
                if not isinstance(slot_data, dict):
                    continue
                try:
                    spell_slots_summary[str(level)] = {
                        "current": int(slot_data.get("current", 0) or 0),
                        "max": int(slot_data.get("max", 0) or 0),
                    }
                except (TypeError, ValueError):
                    continue

        death_saves_data = character_data.get("deathSaves")
        if isinstance(death_saves_data, dict):
            death_success = death_saves_data.get("successes", 0)
            death_fail = death_saves_data.get("failures", 0)
        else:
            death_success = character_data.get("deathSaveSuccesses", 0)
            death_fail = character_data.get("deathSaveFailures", 0)

        try:
            death_saves = {
                "successes": int(death_success or 0),
                "failures": int(death_fail or 0),
            }
        except (TypeError, ValueError):
            death_saves = {"successes": 0, "failures": 0}

        pack = {
            "characterName": str(character_data.get("name") or character_name),
            "hp": hp_value,
            "maxHp": max_hp_value,
            "conditions": [str(condition) for condition in conditions],
            "spellSlots": spell_slots_summary,
            "deathSaves": death_saves,
            "touchedChanges": meta.get("changes", []),
        }

        features = character_data.get("classFeatures", [])
        limited_resources = []
        if isinstance(features, list):
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                feature_name = str(feature.get("name", "")).strip()
                if not feature_name:
                    continue
                nested_usage = feature.get("usage")
                has_nested_usage = isinstance(nested_usage, dict) and (
                    nested_usage.get("current") is not None or nested_usage.get("max") is not None
                )
                has_flat_usage = any(key in feature for key in ("uses", "maxUses", "currentUses", "recharge"))
                if not has_nested_usage and not has_flat_usage:
                    continue
                resource_item = {"name": feature_name}
                if has_nested_usage:
                    usage_block = {}
                    if nested_usage.get("current") is not None:
                        usage_block["current"] = nested_usage.get("current")
                    if nested_usage.get("max") is not None:
                        usage_block["max"] = nested_usage.get("max")
                    if nested_usage.get("refreshOn"):
                        usage_block["refreshOn"] = nested_usage.get("refreshOn")
                    if usage_block:
                        resource_item["usage"] = usage_block
                for key in ("uses", "maxUses", "currentUses", "recharge"):
                    if key in feature:
                        resource_item[key] = feature.get(key)
                limited_resources.append(resource_item)
                if len(limited_resources) >= 8:
                    break

        if limited_resources:
            pack["limitedResources"] = limited_resources

        if meta.get("inventory_relevant", False):
            inventory_block = {}

            currency = character_data.get("currency", {})
            if isinstance(currency, dict):
                inventory_block["currency"] = {
                    "gold": int(currency.get("gold", 0) or 0),
                    "silver": int(currency.get("silver", 0) or 0),
                    "copper": int(currency.get("copper", 0) or 0),
                }

            ammunition = character_data.get("ammunition", [])
            ammo_summary = []
            if isinstance(ammunition, list):
                for ammo_item in ammunition[:10]:
                    if not isinstance(ammo_item, dict):
                        continue
                    ammo_name = ammo_item.get("name", "Unknown")
                    ammo_quantity = ammo_item.get("quantity", 0)
                    ammo_summary.append(
                        {
                            "name": str(ammo_name),
                            "quantity": ammo_quantity,
                        }
                    )
            if ammo_summary:
                inventory_block["ammunition"] = ammo_summary

            equipment = character_data.get("equipment", [])
            equipment_summary = []
            if isinstance(equipment, list):
                for equipment_item in equipment[:12]:
                    if not isinstance(equipment_item, dict):
                        continue
                    equipment_name = equipment_item.get("item_name") or equipment_item.get("name") or "Unknown"
                    equipment_quantity = equipment_item.get("quantity", 1)
                    equipment_summary.append(
                        {
                            "name": str(equipment_name),
                            "quantity": equipment_quantity,
                        }
                    )
            if equipment_summary:
                inventory_block["equipment"] = equipment_summary

            if inventory_block:
                pack["inventory"] = inventory_block

        truth_packs.append(pack)

    return truth_packs

def validate_combat_response(response, encounter_data, user_input, conversation_history=None, multi_pc_manager=None):
    """
    Validate a combat response for accuracy in HP tracking, combat flow, etc.
    Returns True if valid, or a string with the reason for failure if invalid.
    """
    print(f"[COMBAT_MANAGER] Starting validation for combat response")
    
    # --- MULTI-PC VALIDATION GUARDRAIL ---
    # Strictly enforce round integrity: Round cannot advance if PCs are still pending.
    if multi_pc_manager:
        try:
            response_json = parse_json_safely(response)
            if response_json:
                ai_round = response_json.get("combat_round")
                # Determine current round from encounter data
                current_round = encounter_data.get('combat_round', encounter_data.get('current_round', 1))
                
                # Check if AI is attempting to advance the round
                if isinstance(ai_round, int) and ai_round > current_round:
                    # Check if all PCs have acted
                    pending_pcs = multi_pc_manager.get_available_pcs()
                    
                    if pending_pcs:
                        debug(f"VALIDATION_FAIL: Round advance blocked. Pending PCs: {pending_pcs}", category="combat_validation")
                        
                        # Construct a strict rejection message
                        failure_msg = (
                            f"VALIDATION FAILURE: You attempted to advance to Round {ai_round}, but the following Player Characters have NOT acted in Round {current_round}: {', '.join(pending_pcs)}.\n\n"
                            "THE GOLDEN RULE OF MULTI-PC COMBAT:\n"
                            "1. You CANNOT end the round until ALL PCs have taken their turns.\n"
                            "2. STOP your narration immediately.\n"
                            f"3. Prompt {pending_pcs[0]} for their action.\n"
                            f"4. Keep 'combat_round' as {current_round}."
                        )
                        return failure_msg
                        
        except Exception as e:
            debug(f"VALIDATION_ERROR: Error in Multi-PC guardrail: {e}", category="combat_validation")
            # Continue to standard validation if this check crashes (fail open vs closed? decided fail open to avoid deadlock, but log it)

    # --- TABLETOP MODE: PHASE-INTEGRITY DETERMINISTIC PRECHECK ---
    # Additive deterministic guard for explicit phase contradictions.
    # Fail-open on ambiguity/errors to avoid combat deadlocks.
    if multi_pc_manager:
        try:
            response_json = parse_json_safely(response)
            if response_json and isinstance(response_json, dict):
                current_round = encounter_data.get('combat_round', encounter_data.get('current_round', 1))
                try:
                    current_round = int(current_round)
                except (TypeError, ValueError):
                    current_round = 1

                phase_state = {
                    "current_phase": multi_pc_manager.combat_phase,
                    "forbidden_actors": multi_pc_manager.get_forbidden_actors(),
                    "pending_enemies": multi_pc_manager.get_remaining_enemies_for_round(),
                    "pc_phase_complete": multi_pc_manager.pc_phase_complete,
                    "current_round": current_round,
                }

                phase_ok, phase_reason = validate_combat_phase_integrity_precheck(
                    response_json,
                    encounter_data,
                    phase_state=phase_state,
                )
                if not phase_ok:
                    debug(
                        f"VALIDATION_FAIL: Phase-integrity precheck rejected response: {phase_reason}",
                        category="combat_validation",
                    )
                    return f"VALIDATION FAILURE: {phase_reason}"
        except Exception as phase_precheck_error:
            debug(
                f"VALIDATION_ERROR: Phase-integrity precheck failed open due to error: {phase_precheck_error}",
                category="combat_validation",
            )
    # --- END MULTI-PC VALIDATION GUARDRAIL ---

    debug("VALIDATION: Validating combat response...", category="combat_validation")
    
    # Log key validation context
    try:
        response_json = json.loads(response)
        combat_round = response_json.get("combat_round", "unknown")
        num_actions = len(response_json.get("actions", []))
        has_plan = "plan" in response_json
        debug(f"VALIDATION_CONTEXT: Round={combat_round}, Actions={num_actions}, HasPlan={has_plan}", category="combat_validation")
    except:
        debug("VALIDATION_CONTEXT: Unable to parse response JSON for context", category="combat_validation")
    
    # Load validation prompt from file (using toggle for compressed vs original)
    from model_config import USE_COMPRESSED_COMBAT, COMBAT_API_TIMEOUT_SECONDS
    if multi_pc_manager:
        # TABLETOP MODE: Multi-PC validation prompt authority is compressed-only.
        validation_prompt = read_prompt_from_file('combat/combat_validation_prompt_multipc_compressed.txt')
        debug("Using compressed multi-pc validation prompt", category="combat_validation")
    else:
        if USE_COMPRESSED_COMBAT:
            validation_prompt = read_prompt_from_file('combat/combat_validation_prompt_compressed.txt')
            debug("Using compressed validation prompt", category="combat_validation")
        else:
            validation_prompt = read_prompt_from_file('combat/combat_validation_prompt.txt')
            debug("Using original validation prompt", category="combat_validation")
    
    # Start with validation prompt
    validation_conversation = [
        {"role": "system", "content": validation_prompt}
    ]
    
    # Fixed context size - always use 12 messages (6 pairs)
    context_pairs = 6  # 12 messages total
    num_creatures = len(encounter_data.get("creatures", []))
    debug(f"VALIDATION: Using fixed context ({context_pairs} pairs) for encounter with {num_creatures} creatures", category="combat_validation")
    
    # Add previous user/assistant pairs for context with threshold-based compression
    context_messages = []
    if conversation_history and len(conversation_history) > (context_pairs * 2):
        # Get the last 12 messages (6 pairs)
        # +1 to exclude current user input since we'll add it separately
        recent_messages = conversation_history[-(context_pairs * 2 + 1):-1]

        # Filter to only user/assistant messages (no system messages)
        context_messages = [
            msg for msg in recent_messages
            if msg["role"] in ["user", "assistant"]
        ][-(context_pairs * 2):]  # Ensure we only get exactly 12 messages

    current_validation_entries = [
        {"role": "system", "content": "=== CURRENT VALIDATION DATA ==="},
        {"role": "system", "content": f"Encounter Data:\n{json.dumps(encounter_data, indent=2)}"},
        {"role": "user", "content": f"Player Input: {user_input}"},
        {"role": "assistant", "content": response},
    ]

    truth_pack_entries = []
    try:
        response_json_for_truth_pack = parse_json_safely(response)
        touched_truth_pack = _build_compact_combat_truth_pack(
            response_json_for_truth_pack,
            encounter_data,
        )
        if touched_truth_pack:
            truth_pack_entries = [
                {"role": "system", "content": "=== TOUCHED COMBATANT TRUTH PACK ==="},
                {
                    "role": "system",
                    "content": json.dumps(touched_truth_pack, indent=2, ensure_ascii=True),
                },
            ]
    except Exception as truth_pack_error:
        debug(f"VALIDATION: Skipping truth pack due to error: {truth_pack_error}", category="combat_validation")

    validation_preview = list(validation_conversation)
    if context_messages:
        validation_preview.append({
            "role": "system",
            "content": f"=== PREVIOUS COMBAT CONTEXT (last {context_pairs} exchanges) ===",
        })
        validation_preview.extend(context_messages)
    validation_preview.extend(truth_pack_entries)
    validation_preview.extend(current_validation_entries)

    validation_payload_chars = sum(len(json.dumps(msg)) for msg in validation_preview)
    use_validation_compression = False
    compression_reason = "decision_helper_default_uncompressed"
    try:
        use_validation_compression, compression_reason = get_validation_compression_decision(
            total_chars=validation_payload_chars,
            compression_enabled=COMPRESSION_ENABLED,
            threshold_chars=VALIDATION_COMPRESSION_MIN_CHARS,
        )
    except Exception as compression_decision_error:
        use_validation_compression = False
        compression_reason = "decision_helper_error_default_uncompressed"
        debug(
            f"VALIDATION: Compression decision helper failed; using uncompressed fallback. Error: {compression_decision_error}",
            category="combat_validation",
        )

    used_validation_compression = False
    if context_messages:
        if use_validation_compression:
            try:
                # Compress user messages except the last two user turns.
                compressed_context = []
                user_message_count = 0
                total_user_messages = sum(1 for msg in context_messages if msg["role"] == "user")

                for msg in context_messages:
                    if msg["role"] == "user":
                        user_message_count += 1
                        if user_message_count <= total_user_messages - 2:
                            if combat_message_compressor.should_compress_user_message(msg, 0, 999):
                                compressed_content = combat_message_compressor.compress_message((0, msg["content"]))[1]
                                compressed_context.append({
                                    "role": "user",
                                    "content": compressed_content,
                                })
                                debug(
                                    f"VALIDATION: Compressed user message {user_message_count}/{total_user_messages}",
                                    category="combat_validation",
                                )
                            else:
                                compressed_context.append(msg)
                        else:
                            compressed_context.append(msg)
                            debug(
                                f"VALIDATION: Keeping user message {user_message_count}/{total_user_messages} uncompressed",
                                category="combat_validation",
                            )
                    else:
                        compressed_context.append(msg)

                validation_conversation.append({
                    "role": "system",
                    "content": f"=== PREVIOUS COMBAT CONTEXT (last {context_pairs} exchanges with compression) ===",
                })
                validation_conversation.extend(compressed_context)
                used_validation_compression = True
            except Exception as compression_apply_error:
                compression_reason = "compression_apply_error_fallback_uncompressed"
                use_validation_compression = False
                used_validation_compression = False
                debug(
                    f"VALIDATION: Compression apply failed; falling back to uncompressed context. Error: {compression_apply_error}",
                    category="combat_validation",
                )
                validation_conversation.append({
                    "role": "system",
                    "content": f"=== PREVIOUS COMBAT CONTEXT (last {context_pairs} exchanges) ===",
                })
                validation_conversation.extend(context_messages)
        else:
            validation_conversation.append({
                "role": "system",
                "content": f"=== PREVIOUS COMBAT CONTEXT (last {context_pairs} exchanges) ===",
            })
            validation_conversation.extend(context_messages)

    validation_conversation.extend(truth_pack_entries)
    validation_conversation.extend(current_validation_entries)

    validation_routing_telemetry = {
        "skip_llm_validation": False,
        "skip_reason": "combat_full_validation",
        "used_validation_compression": bool(used_validation_compression),
        "compression_reason": str(compression_reason),
        "validation_payload_chars": int(validation_payload_chars),
    }
    try:
        validation_routing_telemetry = build_validation_routing_telemetry(
            skip_llm_validation=False,
            skip_reason="combat_full_validation",
            used_validation_compression=used_validation_compression,
            compression_reason=compression_reason,
            validation_payload_chars=validation_payload_chars,
        )
    except Exception as telemetry_build_error:
        validation_routing_telemetry["compression_reason"] = "telemetry_builder_error_fallback"
        debug(
            f"VALIDATION: Telemetry helper failed; using fallback telemetry payload. Error: {telemetry_build_error}",
            category="combat_validation",
        )
    debug(
        f"VALIDATION_ROUTING_TELEMETRY: {json.dumps(validation_routing_telemetry)}",
        category="combat_validation",
    )

    # Export validation conversation for review
    with open("validation_messages_to_api.json", "w", encoding="utf-8") as f:
        json.dump(validation_conversation, f, indent=2, ensure_ascii=False)
    
    # Calculate size for debugging
    validation_size = sum(len(json.dumps(msg)) for msg in validation_conversation)
    print(f"DEBUG: [VALIDATION] Exported validation messages to validation_messages_to_api.json")
    print(f"DEBUG: [VALIDATION] Total validation context size: {validation_size:,} characters ({len(validation_conversation)} messages)")

    max_validation_retries = 5
    for attempt in range(max_validation_retries):
        try:
            validation_result = client.chat.completions.create(
                model=DM_VALIDATION_MODEL,
                temperature=0.3,  # Lower temperature for more consistent validation
                messages=validation_conversation,
                timeout=COMBAT_API_TIMEOUT_SECONDS  # TABLETOP MODE: Prevent indefinite hang
            )

            # Log API call to master log
            try:
                from utils.api_logger import log_api_call
                log_api_call("combat_validation", validation_conversation, validation_result,
                            metadata={"temperature": 0.3, "attempt": attempt+1})
            except Exception as e:
                print(f"[API_LOG] Warning: Failed to log combat validation call: {e}")

            # Track usage with context for telemetry
            if USAGE_TRACKING_AVAILABLE:
                try:
                    from utils.openai_usage_tracker import get_global_tracker
                    tracker = get_global_tracker()
                    tracker.track(validation_result, context={'endpoint': 'combat_validation', 'purpose': 'validate_combat_response'})
                except:
                    pass

            validation_response = validation_result.choices[0].message.content.strip()
            
            try:
                validation_json = parse_json_safely(validation_response)
                is_valid = validation_json.get("valid", False)
                
                # Extract feedback components and sanitize them for Windows console
                # CRITICAL: Must sanitize to prevent Unicode characters from crashing Windows console
                feedback_obj = validation_json.get("feedback", {})
                positive = sanitize_unicode_for_logging(feedback_obj.get("positive", "None."))
                negative = sanitize_unicode_for_logging(feedback_obj.get("negative", "No reason provided."))
                recommendation = sanitize_unicode_for_logging(feedback_obj.get("recommendation", "No recommendation provided."))

                # Log validation results with encounter context
                # Create debug/combat directory if it doesn't exist
                import os
                from datetime import datetime
                debug_combat_dir = os.path.join("debug", "combat")
                os.makedirs(debug_combat_dir, exist_ok=True)
                
                # Create timestamped filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Remove last 3 digits of microseconds
                encounter_id = encounter_data.get("encounterId", "unknown").replace("/", "_")
                validation_filename = f"validation_{timestamp}_{encounter_id}_attempt{attempt + 1}.json"
                validation_file_path = os.path.join(debug_combat_dir, validation_filename)
                
                with open(validation_file_path, "w") as log_file:
                    log_entry = {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "encounter_size": num_creatures,
                        "context_pairs": context_pairs,
                        "attempt": attempt + 1,
                        "valid": is_valid,
                        "feedback": {
                            "positive": sanitize_unicode_for_logging(positive),
                            "negative": sanitize_unicode_for_logging(negative),
                            "recommendation": sanitize_unicode_for_logging(recommendation)
                        },
                        "response": sanitize_unicode_for_logging(response)
                    }
                    json.dump(log_entry, log_file)
                    log_file.write("\n")

                if is_valid:
                    print(f"[COMBAT_MANAGER] Validation PASSED")
                    # Optionally log the positive feedback
                    debug(f"VALIDATION: Passed. Positive feedback: {positive}", category="combat_validation")
                    return True
                else:
                    print(f"[COMBAT_MANAGER] Validation FAILED: {sanitize_unicode_for_logging(negative)}")
                    debug(f"VALIDATION: Failed. Negative feedback: {sanitize_unicode_for_logging(negative)}", category="combat_validation")
                    
                    # Extract specific validation rule that failed from the negative feedback
                    negative_lower = negative.lower()
                    if "round" in negative_lower and ("increment" in negative_lower or "advance" in negative_lower):
                        debug("VALIDATION_RULE: ROUND_TRACKING_ACCURACY violation detected", category="combat_validation")
                    elif "golden rule" in negative_lower or "mid-round" in negative_lower:
                        debug("VALIDATION_RULE: GOLDEN_RULE_VIOLATION detected", category="combat_validation")
                    elif "hp" in negative_lower or "hit point" in negative_lower or "damage" in negative_lower:
                        debug("VALIDATION_RULE: HP_TRACKING violation detected", category="combat_validation")
                    elif "death" in negative_lower or "dead" in negative_lower or "0 hp" in negative_lower:
                        debug("VALIDATION_RULE: DEATH_DETECTION violation detected", category="combat_validation")
                    elif "initiative" in negative_lower and "order" in negative_lower:
                        debug("VALIDATION_RULE: INITIATIVE_ORDER violation detected", category="combat_validation")
                    elif "player" in negative_lower and ("roll" in negative_lower or "dice" in negative_lower):
                        debug("VALIDATION_RULE: PLAYER_INTERACTION_FLOW violation detected", category="combat_validation")
                    elif "plan" in negative_lower:
                        debug("VALIDATION_RULE: PLAN_VALIDATION violation detected", category="combat_validation")
                    elif "json" in negative_lower or "format" in negative_lower:
                        debug("VALIDATION_RULE: JSON_STRUCTURE violation detected", category="combat_validation")
                    elif "updatecharacterinfo" in negative_lower or "updateencounter" in negative_lower:
                        debug("VALIDATION_RULE: ACTION_USAGE violation detected", category="combat_validation")
                    elif "ammunition" in negative_lower or "equipment" in negative_lower:
                        debug("VALIDATION_RULE: RESOURCE_USAGE violation detected", category="combat_validation")
                    else:
                        debug("VALIDATION_RULE: UNKNOWN - could not categorize validation failure", category="combat_validation")
                    
                    # Construct comprehensive feedback message for the AI
                    full_feedback = (
                        f"Your previous response was invalid. Here is a breakdown:\n\n"
                        f"## What You Did Correctly (Keep This):\n- {positive}\n\n"
                        f"## What You Did Incorrectly (You Must Fix This):\n- {negative}\n\n"
                        f"## Corrective Action Required:\n- {recommendation}"
                    )
                    
                    debug(f"VALIDATION: Full feedback for AI:\n{full_feedback}", category="combat_validation")
                    
                    # Return the full, structured feedback
                    return full_feedback
                    
            except json.JSONDecodeError:
                debug(f"VALIDATION: Invalid JSON from validation model (Attempt {attempt + 1}/{max_validation_retries})", category="combat_validation")
                debug(f"VALIDATION: Problematic response: {validation_response}", category="combat_validation")
                continue
                
        except Exception as e:
            debug(f"VALIDATION: Validation error - {str(e)}", category="combat_validation")
            continue
    
    # If we've exhausted all retries and still don't have a valid result
    warning("VALIDATION: Validation failed after max retries, assuming response is valid", category="combat_validation")
    return True

def normalize_encounter_status(encounter_data):
    """Normalizes status values in encounter data to lowercase"""
    if not encounter_data or not isinstance(encounter_data, dict):
        return encounter_data
        
    # Convert status values to lowercase
    for creature in encounter_data.get('creatures', []):
        if 'status' in creature:
            creature['status'] = creature['status'].lower()
    
    return encounter_data


def normalize_phase1_initiative(encounter_data, party_tracker_data):
    """Normalize encounter initiative fields for Phase 1 two-group flow."""
    if not encounter_data or not isinstance(encounter_data, dict):
        return encounter_data, False, None

    world_conditions = {}
    if isinstance(party_tracker_data, dict):
        world_conditions = party_tracker_data.get("worldConditions", {}) or {}

    mirror = world_conditions.get("combatInitiative", {})
    if not isinstance(mirror, dict):
        mirror = {}

    changed = False
    rolls = encounter_data.get("initiativeRolls")
    if not isinstance(rolls, dict):
        rolls = {}

    dm_group = rolls.get("dmGroup")
    pc_group = rolls.get("pcGroup")
    initiative_winner = encounter_data.get("initiativeWinner")
    round_starts_with = encounter_data.get("roundStartsWith")
    awaiting_pc_group_roll = encounter_data.get("awaitingPcGroupRoll")

    if dm_group is None and mirror.get("enemyRoll") is not None:
        dm_group = mirror.get("enemyRoll")
        changed = True
    if pc_group is None and mirror.get("partyRoll") is not None:
        pc_group = mirror.get("partyRoll")
        changed = True

    if encounter_data.get("initiativeMode") != "two_group_phase1":
        encounter_data["initiativeMode"] = "two_group_phase1"
        changed = True

    if encounter_data.get("initiativeRolls") != {"dmGroup": dm_group, "pcGroup": pc_group}:
        encounter_data["initiativeRolls"] = {"dmGroup": dm_group, "pcGroup": pc_group}
        changed = True

    if initiative_winner not in ("pcGroup", "dmGroup"):
        party_goes_first = mirror.get("partyGoesFirst")
        if party_goes_first is True:
            initiative_winner = "pcGroup"
            changed = True
        elif party_goes_first is False:
            initiative_winner = "dmGroup"
            changed = True

    if round_starts_with not in ("pcGroup", "dmGroup") and initiative_winner in ("pcGroup", "dmGroup"):
        round_starts_with = initiative_winner
        changed = True

    current_round = encounter_data.get("combat_round", encounter_data.get("current_round", 1))
    try:
        current_round_value = int(current_round)
    except Exception:
        current_round_value = 1

    if current_round_value > 1:
        desired_awaiting = False
    elif initiative_winner in ("pcGroup", "dmGroup"):
        desired_awaiting = False
    else:
        desired_awaiting = True

    if awaiting_pc_group_roll != desired_awaiting:
        awaiting_pc_group_roll = desired_awaiting
        changed = True

    encounter_data["initiativeWinner"] = initiative_winner
    encounter_data["roundStartsWith"] = round_starts_with
    encounter_data["awaitingPcGroupRoll"] = awaiting_pc_group_roll

    party_goes_first_out = None
    if initiative_winner in ("pcGroup", "dmGroup"):
        party_goes_first_out = initiative_winner == "pcGroup"

    mirror_payload = {
        "partyRoll": pc_group,
        "enemyRoll": dm_group,
        "partyGoesFirst": party_goes_first_out,
    }

    return encounter_data, changed, mirror_payload

# TABLETOP MODE: Isolated helper contract for Phase 1 /init gate handling
def _handle_group_initiative_gate(cmd, encounter_data, multi_pc_manager, party_tracker_data):
    """
    Handle TT Phase 1 two-group initiative gate for `/init <1-20>` command.

    Args:
        cmd: Lowercase command string (e.g., "/init 15")
        encounter_data: Current encounter state dict
        multi_pc_manager: MultiPCCombatManager instance (optional)
        party_tracker_data: Party tracker state dict

    Returns:
        dict with structure:
        {
            "handled": bool,              # True if valid /init processed
            "valid_init": bool,           # True if syntax valid and roll in range
            "error_message": str,         # Guidance message if invalid (with [skipTTS][prefill:/init ])
            "winner": str,                # "pcGroup" or "dmGroup"
            "pc_group_roll": int,
            "dm_group_roll": int,
            "phase_label": str,           # "PC_PHASE" or "ENEMY_PHASE"
            "encounter_updates": dict,    # Fields to write to encounter_data
            "marker_enabled": bool,       # Result of apply_opening_batch_marker
            "mirror_payload": dict,       # Combat initiative mirror for party tracker
            "needs_enemy_injection": bool # True if dmGroup winner needs enemy phase trigger
        }
    """
    result = {
        "handled": False,
        "valid_init": False,
        "error_message": "",
        "winner": None,
        "pc_group_roll": 0,
        "dm_group_roll": 0,
        "phase_label": "",
        "encounter_updates": {},
        "marker_enabled": False,
        "mirror_payload": {},
        "needs_enemy_injection": False
    }

    # Only process /init commands
    if not cmd.startswith("/init"):
        result["error_message"] = "[skipTTS][prefill:/init ] Dungeon Master: [SYSTEM] Initiative pending. Enter /init <1-20> to begin combat."
        return result

    # Parse the command
    parts = cmd.split()
    if len(parts) != 2:
        result["error_message"] = "[skipTTS][prefill:/init ] Dungeon Master: [SYSTEM] Initiative pending. Usage: /init <1-20>"
        return result

    try:
        pc_group_roll = int(parts[1])
    except ValueError:
        result["error_message"] = "[skipTTS][prefill:/init ] Dungeon Master: [SYSTEM] Initiative pending. Usage: /init <1-20>"
        return result

    if pc_group_roll < 1 or pc_group_roll > 20:
        result["error_message"] = "[skipTTS][prefill:/init ] Dungeon Master: [SYSTEM] Initiative pending. Roll must be between 1 and 20."
        return result

    # Valid /init received
    result["handled"] = True
    result["valid_init"] = True
    result["pc_group_roll"] = pc_group_roll

    initiative_rolls = encounter_data.get("initiativeRolls", {})
    dm_group_roll = initiative_rolls.get("dmGroup", 1)
    result["dm_group_roll"] = dm_group_roll

    # Determine winner (dmGroup wins ties per Phase 1 rules)
    if pc_group_roll > dm_group_roll:
        winner = "pcGroup"
        phase_label = "PC_PHASE"
    else:
        winner = "dmGroup"
        phase_label = "ENEMY_PHASE"

    result["winner"] = winner
    result["phase_label"] = phase_label

    # Prepare encounter updates
    result["encounter_updates"] = {
        "initiativeMode": "two_group_phase1",
        "initiativeRolls": {
            "dmGroup": dm_group_roll,
            "pcGroup": pc_group_roll
        },
        "initiativeWinner": winner,
        "roundStartsWith": winner,
        "awaitingPcGroupRoll": False
    }

    # Apply opening batch marker via helper
    if COMBAT_STATE_SYNC_AVAILABLE:
        result["marker_enabled"] = apply_opening_batch_marker(encounter_data, winner)
    else:
        result["marker_enabled"] = False

    # Prepare mirror payload for party tracker
    result["mirror_payload"] = {
        "partyRoll": pc_group_roll,
        "enemyRoll": dm_group_roll,
        "partyGoesFirst": (winner == "pcGroup")
    }

    # dmGroup winner needs enemy phase injection
    result["needs_enemy_injection"] = (winner == "dmGroup")

    return result

def get_initiative_order(encounter_data):
    """Generate initiative order string for combat validation context"""
    if not encounter_data or not isinstance(encounter_data, dict):
        return "Initiative order unknown"
        
    creatures = encounter_data.get("creatures", [])
    if not creatures:
        return "No creatures in encounter"
    
    # Filter out dead creatures - they should not be in the initiative order
    active_creatures = [c for c in creatures if c.get("status", "unknown").lower() != "dead"]
    
    if not active_creatures:
        return "All creatures are dead"
    
    # Sort by initiative (descending), then alphabetically for ties
    sorted_creatures = sorted(active_creatures, key=lambda x: (-x.get("initiative", 0), x.get("name", "")))
    
    order_parts = []
    for creature in sorted_creatures:
        name = creature.get("name", "Unknown")
        initiative = creature.get("initiative", 0)
        status = creature.get("status", "unknown")
        order_parts.append(f"{name} ({initiative}, {status})")
    
    return " -> ".join(order_parts)

def log_conversation_structure(conversation):
    """Log the structure of the conversation history for debugging"""
    debug("VALIDATION: Conversation Structure:", category="combat_validation")
    debug(f"Total messages: {len(conversation)}", category="combat_validation")
    
    roles = {}
    for i, msg in enumerate(conversation):
        role = msg.get("role", "unknown")
        content_preview = msg.get("content", "")[:50].replace("\n", " ") + "..."
        roles[role] = roles.get(role, 0) + 1
        debug(f"  [{i}] {role}: {content_preview}", category="combat_validation")
    
    debug("Message count by role:", category="combat_validation")
    for role, count in roles.items():
        debug(f"  {role}: {count}", category="combat_validation")
    # Empty line for debug output


def summarize_dialogue(conversation_history_param, location_data, party_tracker_data):
    debug("AI_CALL: Activating the third model...", category="ai_operations")
    
    # Extract clean narrative content from conversation history
    clean_conversation = []
    for message in conversation_history_param:
        if message.get("role") == "system":
            continue  # Skip system messages
        elif message.get("role") == "user":
            clean_conversation.append(f"Player: {message.get('content', '')}")
        elif message.get("role") == "assistant":
            content = message.get("content", "")
            
            # Check for the special "Combat Summary:" message format first
            if content.strip().startswith("Combat Summary:"):
                # Extract the JSON part of the string by removing the prefix
                json_part = content.replace("Combat Summary:", "").strip()
                try:
                    parsed = json.loads(json_part)
                    if isinstance(parsed, dict) and "narration" in parsed:
                        # We found the final summary, use its clean narration
                        clean_conversation.append(f"Dungeon Master: {parsed['narration']}")
                    else:
                        # The content after the prefix was not the expected JSON, use the raw content
                        clean_conversation.append(f"Dungeon Master: {content}")
                except json.JSONDecodeError:
                    # If parsing the JSON part fails, use the raw content as fallback
                    clean_conversation.append(f"Dungeon Master: {content}")
            else:
                # This is a normal combat turn response, not the final summary
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "narration" in parsed:
                        clean_conversation.append(f"Dungeon Master: {parsed['narration']}")
                    else:
                        clean_conversation.append(f"Dungeon Master: {content}")
                except json.JSONDecodeError:
                    # If it's not JSON (e.g., an error message), use the raw content
                    clean_conversation.append(f"Dungeon Master: {content}")
    
    clean_text = "\n\n".join(clean_conversation)
    
    dialogue_summary_prompt = [
        {"role": "system", "content": "Your task is to create a vivid, colorful narrative summary of this combat encounter. Capture the dramatic highs and lows - critical hits, narrow misses, clever tactics, desperate moments, and heroic actions. Write it as an exciting story paragraph that captures the flow and feel of the battle. Include: the initial setup, key turning points, memorable moments, the final blow, total XP awarded, and what remains after combat (defeated foes, environmental changes). Write in past tense as a complete narrative summary, not a play-by-play. Make it engaging and memorable - this will be the permanent record of this battle."},
        {"role": "user", "content": clean_text}
    ]

    # Generate dialogue summary
    response = client.chat.completions.create(
        model=COMBAT_DIALOGUE_SUMMARY_MODEL, # Use imported model
        temperature=TEMPERATURE,
        messages=dialogue_summary_prompt
    )

    # Log API call to master log
    try:
        from utils.api_logger import log_api_call
        log_api_call("combat_summary", dialogue_summary_prompt, response,
                    metadata={"temperature": TEMPERATURE, "context": "dialogue_summary"})
    except Exception as e:
        print(f"[API_LOG] Warning: Failed to log combat summary call: {e}")

    # Track usage
    if USAGE_TRACKING_AVAILABLE:
        try:
            track_response(response)
        except:
            pass

    dialogue_summary = response.choices[0].message.content.strip()
    
    # Extract just the narration if the AI returned JSON
    try:
        parsed_summary = json.loads(dialogue_summary)
        if isinstance(parsed_summary, dict) and "narration" in parsed_summary:
            dialogue_summary = parsed_summary["narration"]
            debug("Extracted narration from JSON combat summary", category="combat_summary")
    except (json.JSONDecodeError, KeyError):
        # Not JSON or doesn't have narration field, use as-is
        pass

    current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
    debug(f"STATE_CHANGE: Current location ID: {current_location_id}", category="encounter_setup")

    if location_data and location_data.get("locationId") == current_location_id:
        encounter_id = party_tracker_data["worldConditions"].get("activeCombatEncounter", "")
        
        # Debug to identify why encounter_id might be empty
        debug(f"[summarize_dialogue] Retrieved activeCombatEncounter ID: '{encounter_id}'", category="encounter_setup")
        if not encounter_id:
            error("[summarize_dialogue] activeCombatEncounter ID is EMPTY or None. This is the cause of missing encounter IDs.", category="encounter_setup")
            # Try to generate a fallback ID if missing
            existing_encounters = location_data.get("encounters", [])
            next_num = len(existing_encounters) + 1
            encounter_id = f"{current_location_id}-E{next_num}"
            warning(f"[summarize_dialogue] Generated fallback encounter ID: {encounter_id}", category="encounter_setup")
        
        new_encounter = {
            "encounterId": encounter_id,
            "summary": dialogue_summary,
            "impact": "To be determined",
            "worldConditions": {
                "year": int(party_tracker_data["worldConditions"]["year"]),
                "month": party_tracker_data["worldConditions"]["month"],
                "day": int(party_tracker_data["worldConditions"]["day"]),
                "time": party_tracker_data["worldConditions"]["time"]
            }
        }
        if "encounters" not in location_data:
            location_data["encounters"] = []
        location_data["encounters"].append(new_encounter)
        # adventureSummary field is deprecated - no longer updated to prevent data bloat

        from utils.module_path_manager import ModulePathManager
        from utils.encoding_utils import safe_json_load
        # Get current module from party tracker for consistent path resolution
        try:
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        current_area_id = get_current_area_id()
        area_file = path_manager.get_area_path(current_area_id)
        area_data = safe_json_load(area_file)
        if not area_data:
            error(f"FILE_OP: Failed to load area file: {area_file}", category="file_operations")
            return dialogue_summary
        
        for i, loc in enumerate(area_data["locations"]):
            if loc["locationId"] == current_location_id:
                area_data["locations"][i] = location_data
                break
        
        if not safe_write_json(area_file, area_data):
            error(f"FILE_OP: Failed to save area file: {area_file}", category="file_operations")
        debug(f"STATE_CHANGE: Encounter {encounter_id} added to {area_file}.", category="encounter_setup")

        conversation_history_param.append({"role": "assistant", "content": f"Combat Summary: {dialogue_summary}"})
        conversation_history_param.append({"role": "user", "content": "The combat has concluded. What would you like to do next?"})

        debug(f"FILE_OP: Attempting to write to file: {conversation_history_file}", category="file_operations")
        if not safe_write_json(conversation_history_file, conversation_history_param):
            error("FILE_OP: Failed to save conversation history", category="file_operations")
        else:
            debug("FILE_OP: Conversation history saved successfully", category="file_operations")
        info("SUCCESS: Conversation history updated with encounter summary.", category="combat_events")
    else:
        error(f"VALIDATION: Location {current_location_id} not found in location data or location data is incorrect.", category="combat_events")
    return dialogue_summary

def merge_updates(original_data, updated_data):
    fields_to_update = ['hitPoints', 'equipment', 'attacksAndSpellcasting', 'experience_points']

    for field in fields_to_update:
        if field in updated_data:
            if field in ['equipment', 'attacksAndSpellcasting']:
                # For arrays, replace the entire array
                original_data[field] = updated_data[field]
            elif field == 'experience_points':
                # For XP, only update if the new value is greater than the existing value
                if updated_data[field] > original_data.get(field, 0):
                    original_data[field] = updated_data[field]
            else:
                # For simple fields like hitpoints, just update the value
                original_data[field] = updated_data[field]

    return original_data

# DEPRECATED: This function is no longer used and has been replaced by the new XP awarding system
# that uses update_character_info directly with proper synchronization.
# The new system:
# 1. Awards XP through update_character_info with "Awarded X experience points" message
# 2. Uses atomic file operations with proper locking
# 3. Has XP protection to prevent reduction
# 4. Includes comprehensive debug logging
# Keeping this function for reference only - DO NOT USE
def update_json_schema(ai_response, player_info, encounter_data, party_tracker_data):
    # This old function tried to extract XP from AI responses and update characters
    # It has been replaced by the more robust XP awarding system in the main combat loop
    warning("DEPRECATED: update_json_schema called but is no longer used", category="xp_tracking")
    return player_info  # Return unchanged data

def generate_chat_history(conversation_history, encounter_id):
    """
    Generate a lightweight combat chat history without system messages
    for a specific encounter ID
    """
    # Create a formatted timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime(HISTORY_TIMESTAMP_FORMAT)

    # Create directory for this encounter if it doesn't exist
    encounter_dir = f"combat_logs/{encounter_id}"
    os.makedirs(encounter_dir, exist_ok=True)

    # Create a unique filename based on encounter ID and timestamp
    output_file = f"{encounter_dir}/combat_chat_{timestamp}.json"

    try:
        # Filter out system messages and keep only user and assistant messages
        chat_history = [msg for msg in conversation_history if msg["role"] != "system"]

        # Write the filtered chat history to the output file
        if not safe_write_json(output_file, chat_history):
            error(f"FILE_OP: Failed to save chat history to {output_file}", category="file_operations")

        # Print statistics
        system_count = len(conversation_history) - len(chat_history)
        total_count = len(conversation_history)
        user_count = sum(1 for msg in chat_history if msg["role"] == "user")
        assistant_count = sum(1 for msg in chat_history if msg["role"] == "assistant")

        info("SUCCESS: Combat chat history updated!", category="combat_events")
        debug(f"Encounter ID: {encounter_id}", category="combat_events")
        debug(f"System messages removed: {system_count}", category="combat_events")
        debug(f"SUMMARY: User messages: {user_count}", category="combat_logs")
        debug(f"SUMMARY: Assistant messages: {assistant_count}", category="combat_logs")
        debug(f"SUMMARY: Total messages (including system): {total_count}", category="combat_logs")
        info(f"SUCCESS: Output saved to: {output_file}", category="combat_logs")

        # Also create/update the latest version of this encounter for easy reference
        latest_file = f"{encounter_dir}/combat_chat_latest.json"
        if not safe_write_json(latest_file, chat_history):
            error("FILE_OP: Failed to save latest chat history", category="file_operations")
        info(f"SUCCESS: Latest version also saved to: {latest_file}", category="combat_logs")

        # Save a combined latest file for all encounters as well
        all_latest_file = f"combat_logs/all_combat_latest.json"
        try:
            # Load existing all-combat history if it exists
            if os.path.exists(all_latest_file):
                with open(all_latest_file, "r", encoding="utf-8") as f:
                    all_combat_data = json.load(f)
            else:
                all_combat_data = {}

            # Add or update this encounter's data
            all_combat_data[encounter_id] = {
                "timestamp": timestamp,
                "messageCount": len(chat_history),
                "history": chat_history
            }

            # Write the combined file
            with open(all_latest_file, "w", encoding="utf-8") as f:
                json.dump(all_combat_data, f, indent=2)

        except Exception as e:
            error(f"FAILURE: Error updating combined combat log", exception=e, category="combat_logs")

    except Exception as e:
        error(f"FAILURE: Error generating combat chat history", exception=e, category="combat_logs")

def sync_active_encounter():
    """Sync player and NPC data to the active encounter file if one exists"""
    from utils.module_path_manager import ModulePathManager
    from utils.encoding_utils import safe_json_load
    # Get current module from party tracker for consistent path resolution
    try:
        party_tracker = safe_json_load("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    
    # Check if there's an active combat encounter
    try:
        party_tracker = safe_json_load("party_tracker.json")
        if not party_tracker:
            error("FAILURE: Failed to load party_tracker.json", category="file_operations")
            return
        
        active_encounter_id = party_tracker.get("worldConditions", {}).get("activeCombatEncounter", "")
        if not active_encounter_id:
            # No active encounter, nothing to sync
            return
            
        # Load the encounter file
        encounter_file = f"modules/encounters/encounter_{active_encounter_id}.json"
        encounter_data = safe_json_load(encounter_file)
        if not encounter_data:
            error(f"FAILURE: Failed to load encounter file: {encounter_file}", category="file_operations")
            return {}
            
        # Track if any changes were made
        changes_made = False
            
        # Update player and NPC data in the encounter
        for creature in encounter_data.get("creatures", []):
            if creature["type"] == "player":
                player_file = path_manager.get_character_path(normalize_character_name(creature['name']))
                try:
                    player_data = safe_json_load(player_file)
                    if not player_data:
                        error(f"FAILURE: Failed to load player file: {player_file}", category="file_operations")
                    else:
                        player_data = normalize_life_state_fields(player_data)
                        # Update combat-relevant fields
                        if creature.get("currentHitPoints") != player_data.get("hitPoints"):
                            creature["currentHitPoints"] = player_data.get("hitPoints")
                            changes_made = True
                        if creature.get("maxHitPoints") != player_data.get("maxHitPoints"):
                            creature["maxHitPoints"] = player_data.get("maxHitPoints")
                            changes_made = True
                        if creature.get("status") != player_data.get("status"):
                            creature["status"] = player_data.get("status")
                            changes_made = True
                        if creature.get("conditions") != player_data.get("condition_affected"):
                            creature["conditions"] = player_data.get("condition_affected", [])
                            changes_made = True
                except Exception as e:
                    error(f"FAILURE: Failed to sync player data to encounter", exception=e, category="encounter_setup")
                    
            elif creature["type"] == "npc":
                try:
                    # Use fuzzy matching for NPC loading
                    npc_data, matched_filename = load_npc_with_fuzzy_match(creature['name'], path_manager)
                    if not npc_data:
                        error(f"FAILURE: Failed to load NPC file for: {creature['name']}", category="file_operations")
                    else:
                        npc_data = normalize_life_state_fields(npc_data)
                        # Update combat-relevant fields
                        if creature.get("currentHitPoints") != npc_data.get("hitPoints"):
                            creature["currentHitPoints"] = npc_data.get("hitPoints")
                            changes_made = True
                        if creature.get("maxHitPoints") != npc_data.get("maxHitPoints"):
                            creature["maxHitPoints"] = npc_data.get("maxHitPoints")
                            changes_made = True
                        if creature.get("status") != npc_data.get("status"):
                            creature["status"] = npc_data.get("status")
                            changes_made = True
                        if creature.get("conditions") != npc_data.get("condition_affected"):
                            creature["conditions"] = npc_data.get("condition_affected", [])
                            changes_made = True
                except Exception as e:
                    error(f"FAILURE: Failed to sync NPC data to encounter", exception=e, category="encounter_setup")
        
        # Save the encounter file if changes were made
        if changes_made:
            if not safe_write_json(encounter_file, encounter_data):
                error(f"FAILURE: Failed to save encounter file: {encounter_file}", category="file_operations")
            debug(f"SUCCESS: Active encounter {active_encounter_id} synced with latest character data", category="encounter_setup")
            
    except Exception as e:
        error(f"FAILURE: Error in sync_active_encounter", exception=e, category="encounter_setup")

def filter_dynamic_fields(data):
    """Remove dynamic combat fields from character/monster data for system prompts"""
    dynamic_fields = ['hitPoints', 'maxHitPoints', 'status', 'condition', 'condition_affected', 
                     'temporaryEffects', 'currentHitPoints']
    return {k: v for k, v in data.items() if k not in dynamic_fields}

def format_character_for_combat(char_data, char_type="player", role=None):
    """
    Format character data (player or NPC) for combat system prompts using the same format as conversation_utils.
    This ensures consistency between main conversation and combat systems.
    
    Args:
        char_data: The character's data dictionary
        char_type: "player" or "npc"
        role: Optional role description (mainly for NPCs)
    
    Returns:
        Formatted string matching conversation_utils format
    """
    if isinstance(char_data, dict):
        char_data = normalize_life_state_fields(dict(char_data))

    # Get equipment string - include ALL items with quantities (not just equipped)
    # Don't include item type in parentheses for combat - wastes tokens
    equipment_str = "None"
    if char_data.get('equipment'):
        equipment_list = []
        for item in char_data['equipment']:
            item_description = item['item_name']
            if item.get('quantity', 1) > 1:
                item_description = f"{item_description} x{item['quantity']}"
            equipment_list.append(item_description)
        if equipment_list:
            equipment_str = ", ".join(equipment_list)
    
    # Get background feature name
    bg_feature_name = "None"
    bg_feature = char_data.get('backgroundFeature', {})
    if bg_feature and isinstance(bg_feature, dict):
        bg_feature_name = bg_feature.get('name', 'None')
    
    # Determine header based on type
    if char_type == "player":
        header = f"CHAR: {char_data.get('name', 'Unknown')}"
        type_line = f"TYPE: {char_data.get('character_type', 'player').capitalize()}"
    else:
        header = f"NPC: {char_data.get('name', 'Unknown')}"
        type_line = f"ROLE: {role if role else 'Adventurer'} | TYPE: {char_data.get('character_type', 'npc').capitalize()}"
    
    # Calculate skill modifiers for display
    skills_display = ""
    skills_field = char_data.get('skills', {})
    if isinstance(skills_field, dict):
        # Legacy format - use pre-calculated values
        skills_display = ', '.join(f"{skill} +{bonus}" if bonus >= 0 else f"{skill} {bonus}" 
                                 for skill, bonus in skills_field.items())
    elif isinstance(skills_field, list):
        # Array format - calculate modifiers for proficient skills
        skill_abilities = {
            'Acrobatics': 'dexterity', 'Animal Handling': 'wisdom', 
            'Arcana': 'intelligence', 'Athletics': 'strength',
            'Deception': 'charisma', 'History': 'intelligence',
            'Insight': 'wisdom', 'Intimidation': 'charisma',
            'Investigation': 'intelligence', 'Medicine': 'wisdom',
            'Nature': 'intelligence', 'Perception': 'wisdom',
            'Performance': 'charisma', 'Persuasion': 'charisma',
            'Religion': 'intelligence', 'Sleight of Hand': 'dexterity',
            'Stealth': 'dexterity', 'Survival': 'wisdom'
        }
        
        skill_displays = []
        abilities = char_data.get('abilities', {})
        prof_bonus = char_data.get('proficiencyBonus', 2)
        
        for skill in skills_field:
            if skill in skill_abilities:
                ability_name = skill_abilities[skill]
                ability_score = abilities.get(ability_name, 10)
                ability_mod = (ability_score - 10) // 2
                modifier = ability_mod + prof_bonus
                if modifier >= 0:
                    skill_displays.append(f"{skill} +{modifier}")
                else:
                    skill_displays.append(f"{skill} {modifier}")
        skills_display = ', '.join(skill_displays) if skill_displays else 'none'
    else:
        skills_display = 'none'
    
    # Build the formatted string (exactly matching conversation_utils format)
    formatted_data = f"""{header}
{type_line} | LVL: {char_data.get('level', 1)} | RACE: {char_data.get('race', 'Unknown')} | CLASS: {char_data.get('class', 'Unknown')} | ALIGN: {char_data.get('alignment', 'neutral')[:2].upper()} | BG: {char_data.get('background', 'None')}
AC: {char_data.get('armorClass', 10)} | SPD: {char_data.get('speed', 30)}
STATUS: {char_data.get('status', 'alive')} | CONDITION: {char_data.get('condition', 'none')} | AFFECTED: {', '.join(char_data.get('condition_affected', []))}
STATS: STR {char_data.get('abilities', {}).get('strength', 10)}, DEX {char_data.get('abilities', {}).get('dexterity', 10)}, CON {char_data.get('abilities', {}).get('constitution', 10)}, INT {char_data.get('abilities', {}).get('intelligence', 10)}, WIS {char_data.get('abilities', {}).get('wisdom', 10)}, CHA {char_data.get('abilities', {}).get('charisma', 10)}
SAVES: {', '.join(char_data.get('savingThrows', []))}
SKILLS: {skills_display}
PROF BONUS: +{char_data.get('proficiencyBonus', 2)}
SENSES: {', '.join(f"{sense} {value}" for sense, value in char_data.get('senses', {}).items())}
LANGUAGES: {', '.join(char_data.get('languages', ['Common']))}
PROF: {', '.join([f"{cat}: {', '.join(items) if items else 'none'}" for cat, items in char_data.get('proficiencies', {}).items()])}
VULN: {', '.join(char_data.get('damageVulnerabilities', []))}
RES: {', '.join(char_data.get('damageResistances', []))}
IMM: {', '.join(char_data.get('damageImmunities', []))}
COND IMM: {', '.join(char_data.get('conditionImmunities', []))}
RACIAL: {', '.join([t['name'] for t in char_data.get('racialTraits', [])])}
BG FEAT: {bg_feature_name}
FEATS: {', '.join([f['name'] for f in char_data.get('feats', [])])}
TEMP FX: {', '.join([e['name'] for e in char_data.get('temporaryEffects', [])])}
EQUIP: {equipment_str}
AMMO: {', '.join([f"{a['name']} x{a['quantity']}" for a in char_data.get('ammunition', [])])}
ATK: {', '.join([f"{a['name']} ({a.get('type', 'melee')}, {a.get('damageDice', '1d4')} {a.get('damageType', 'bludgeoning')})" for a in char_data.get('attacksAndSpellcasting', [])])}"""
    
    # Add spellcasting if present
    spellcasting = char_data.get('spellcasting', {})
    if spellcasting:
        formatted_data += f"""
SPELLCASTING: {spellcasting.get('ability', 'N/A')} | DC: {spellcasting.get('spellSaveDC', 'N/A')} | ATK: +{spellcasting.get('spellAttackBonus', 'N/A')}
SPELLS: {', '.join([f"{level}: {', '.join(spells)}" for level, spells in spellcasting.get('spells', {}).items() if spells])}"""
    
    # Add currency
    currency = char_data.get('currency', {})
    if currency:
        formatted_data += f"""
CURRENCY: {currency.get('gold', 0)}G, {currency.get('silver', 0)}S, {currency.get('copper', 0)}C"""
    
    # Add XP
    if 'experience_points' in char_data:
        formatted_data += f"""
XP: {char_data['experience_points']}/{char_data.get('exp_required_for_next_level', 'N/A')}"""
    
    # Add personality traits
    if char_data.get('personality_traits'):
        formatted_data += f"""
TRAITS: {char_data['personality_traits']}"""
    
    if char_data.get('ideals'):
        formatted_data += f"""
IDEALS: {char_data['ideals']}"""
    
    if char_data.get('bonds'):
        formatted_data += f"""
BONDS: {char_data['bonds']}"""
    
    if char_data.get('flaws'):
        formatted_data += f"""
FLAWS: {char_data['flaws']}"""
    
    # Add backstory context when present (bounded)
    if char_data.get('backstory'):
        backstory_display = str(char_data['backstory'])[:120]
        formatted_data += f"""
BACKSTORY: {backstory_display}"""
    
    return formatted_data

def format_npc_for_combat(npc_data, npc_role=None):
    """
    Format NPC data for combat system prompts using the same format as conversation_utils.
    This ensures consistency between main conversation and combat systems.
    
    Args:
        npc_data: The NPC's character data dictionary
        npc_role: Optional role description from party tracker
    
    Returns:
        Formatted string matching conversation_utils format
    """
    # Get equipment string - include ALL items with quantities (not just equipped)
    # Don't include item type in parentheses for combat - wastes tokens
    equipment_str = "None"
    if npc_data.get('equipment'):
        equipment_list = []
        for item in npc_data['equipment']:
            item_description = item['item_name']
            if item.get('quantity', 1) > 1:
                item_description = f"{item_description} x{item['quantity']}"
            equipment_list.append(item_description)
        if equipment_list:
            equipment_str = ", ".join(equipment_list)
    
    # Get background feature name
    bg_feature_name = "None"
    bg_feature = npc_data.get('backgroundFeature', {})
    if bg_feature and isinstance(bg_feature, dict):
        bg_feature_name = bg_feature.get('name', 'None')
    
    # Calculate skill modifiers for NPC display
    npc_skills_display = ""
    skills_field = npc_data.get('skills', {})
    if isinstance(skills_field, dict):
        # NPCs typically use dict format with pre-calculated values
        npc_skills_display = ', '.join(f"{skill} +{bonus}" if bonus >= 0 else f"{skill} {bonus}" 
                                     for skill, bonus in skills_field.items())
    elif isinstance(skills_field, list):
        # In case NPCs use array format, calculate modifiers
        skill_abilities = {
            'Acrobatics': 'dexterity', 'Animal Handling': 'wisdom', 
            'Arcana': 'intelligence', 'Athletics': 'strength',
            'Deception': 'charisma', 'History': 'intelligence',
            'Insight': 'wisdom', 'Intimidation': 'charisma',
            'Investigation': 'intelligence', 'Medicine': 'wisdom',
            'Nature': 'intelligence', 'Perception': 'wisdom',
            'Performance': 'charisma', 'Persuasion': 'charisma',
            'Religion': 'intelligence', 'Sleight of Hand': 'dexterity',
            'Stealth': 'dexterity', 'Survival': 'wisdom'
        }
        
        skill_displays = []
        abilities = npc_data.get('abilities', {})
        prof_bonus = npc_data.get('proficiencyBonus', 2)
        
        for skill in skills_field:
            if skill in skill_abilities:
                ability_name = skill_abilities[skill]
                ability_score = abilities.get(ability_name, 10)
                ability_mod = (ability_score - 10) // 2
                modifier = ability_mod + prof_bonus
                if modifier >= 0:
                    skill_displays.append(f"{skill} +{modifier}")
                else:
                    skill_displays.append(f"{skill} {modifier}")
        npc_skills_display = ', '.join(skill_displays) if skill_displays else 'none'
    else:
        npc_skills_display = 'none'
    
    # Build the formatted string (exactly matching conversation_utils format)
    formatted_data = f"""NPC: {npc_data.get('name', 'Unknown')}
ROLE: {npc_role if npc_role else 'Adventurer'} | TYPE: {npc_data.get('character_type', 'npc').capitalize()} | LVL: {npc_data.get('level', 1)} | RACE: {npc_data.get('race', 'Unknown')} | CLASS: {npc_data.get('class', 'Unknown')} | ALIGN: {npc_data.get('alignment', 'neutral')[:2].upper()} | BG: {npc_data.get('background', 'None')}
AC: {npc_data.get('armorClass', 10)} | SPD: {npc_data.get('speed', 30)}
STATUS: {npc_data.get('status', 'alive')} | CONDITION: {npc_data.get('condition', 'none')} | AFFECTED: {', '.join(npc_data.get('condition_affected', []))}
STATS: STR {npc_data.get('abilities', {}).get('strength', 10)}, DEX {npc_data.get('abilities', {}).get('dexterity', 10)}, CON {npc_data.get('abilities', {}).get('constitution', 10)}, INT {npc_data.get('abilities', {}).get('intelligence', 10)}, WIS {npc_data.get('abilities', {}).get('wisdom', 10)}, CHA {npc_data.get('abilities', {}).get('charisma', 10)}
SAVES: {', '.join(npc_data.get('savingThrows', []))}
SKILLS: {npc_skills_display}
PROF BONUS: +{npc_data.get('proficiencyBonus', 2)}
SENSES: {', '.join(f"{sense} {value}" for sense, value in npc_data.get('senses', {}).items())}
LANGUAGES: {', '.join(npc_data.get('languages', ['Common']))}
PROF: {', '.join([f"{cat}: {', '.join(items) if items else 'none'}" for cat, items in npc_data.get('proficiencies', {}).items()])}
VULN: {', '.join(npc_data.get('damageVulnerabilities', []))}
RES: {', '.join(npc_data.get('damageResistances', []))}
IMM: {', '.join(npc_data.get('damageImmunities', []))}
COND IMM: {', '.join(npc_data.get('conditionImmunities', []))}
RACIAL: {', '.join([t['name'] for t in npc_data.get('racialTraits', [])])}
BG FEAT: {bg_feature_name}
FEATS: {', '.join([f['name'] for f in npc_data.get('feats', [])])}
TEMP FX: {', '.join([e['name'] for e in npc_data.get('temporaryEffects', [])])}
EQUIP: {equipment_str}
AMMO: {', '.join([f"{a['name']} x{a['quantity']}" for a in npc_data.get('ammunition', [])])}
ATK: {', '.join([f"{a['name']} ({a.get('type', 'melee')}, {a.get('damageDice', '1d4')} {a.get('damageType', 'bludgeoning')})" for a in npc_data.get('attacksAndSpellcasting', [])])}"""
    
    # Add spellcasting if present
    spellcasting = npc_data.get('spellcasting', {})
    if spellcasting:
        formatted_data += f"""
SPELLCASTING: {spellcasting.get('ability', 'N/A')} | DC: {spellcasting.get('spellSaveDC', 'N/A')} | ATK: +{spellcasting.get('spellAttackBonus', 'N/A')}
SPELLS: {', '.join([f"{level}: {', '.join(spells)}" for level, spells in spellcasting.get('spells', {}).items() if spells])}"""
    
    # Add currency
    currency = npc_data.get('currency', {})
    if currency:
        formatted_data += f"""
CURRENCY: {currency.get('gold', 0)}G, {currency.get('silver', 0)}S, {currency.get('copper', 0)}C"""
    
    # Add XP
    if 'experience_points' in npc_data:
        formatted_data += f"""
XP: {npc_data['experience_points']}/{npc_data.get('exp_required_for_next_level', 'N/A')}"""
    
    # Add personality traits
    if npc_data.get('personality_traits'):
        formatted_data += f"""
TRAITS: {npc_data['personality_traits']}"""
    
    if npc_data.get('ideals'):
        formatted_data += f"""
IDEALS: {npc_data['ideals']}"""
    
    if npc_data.get('bonds'):
        formatted_data += f"""
BONDS: {npc_data['bonds']}"""
    
    if npc_data.get('flaws'):
        formatted_data += f"""
FLAWS: {npc_data['flaws']}"""
    
    # Add backstory context when present (bounded)
    if npc_data.get('backstory'):
        backstory_display = str(npc_data['backstory'])[:120]
        formatted_data += f"""
BACKSTORY: {backstory_display}"""
    
    return formatted_data

def filter_encounter_for_system_prompt(encounter_data):
    """Create minimal encounter data for system prompt with only essential fields"""
    if not encounter_data or not isinstance(encounter_data, dict):
        return encounter_data
    
    # Create minimal structure with only essential fields
    minimal_data = {
        "encounterId": encounter_data.get("encounterId"),
        "encounterSummary": encounter_data.get("encounterSummary", ""),
        "creatures": []
    }
    
    # Process each creature to keep only essential fields
    for creature in encounter_data.get("creatures", []):
        minimal_creature = {
            "name": creature.get("name")
        }
        
        # Add type information
        if creature.get("type"):
            minimal_creature["type"] = creature["type"]
        
        # Add monster/npc specific type info
        if creature.get("monsterType"):
            minimal_creature["monsterType"] = creature["monsterType"]
        if creature.get("npcType"):
            minimal_creature["npcType"] = creature["npcType"]
        
        # Add armor class for all creatures (important for combat)
        if "armorClass" in creature:
            minimal_creature["armorClass"] = creature["armorClass"]
        
        # Add conditions (will be important when not empty)
        if "conditions" in creature and creature["conditions"]:
            minimal_creature["conditions"] = creature["conditions"]
        
        # Add actions (even though currently bugged and empty)
        if "actions" in creature:
            minimal_creature["actions"] = creature["actions"]
        
        minimal_data["creatures"].append(minimal_creature)
    
    debug("STATE_CHANGE: Created minimal encounter data for system prompt", category="combat_events")
    return minimal_data

def compress_old_combat_rounds(conversation_history, current_round, keep_recent_rounds=1):
    """
    Compress old combat rounds in conversation history to reduce token usage.
    Keeps the last 'keep_recent_rounds' rounds uncompressed for context.
    With keep_recent_rounds=1: Round 2 keeps round 1, Round 3 compresses round 1, etc.
    """
    try:
        # Debug logging
        debug(f"COMPRESSION: Called with current_round={current_round}, keep_recent_rounds={keep_recent_rounds}", category="combat_events")
        debug(f"COMPRESSION: Conversation history has {len(conversation_history)} messages", category="combat_events")
        
        # Don't compress if we're in early rounds (need at least 2 rounds to start compressing)
        if current_round <= keep_recent_rounds + 1:
            debug(f"COMPRESSION: Skipping - too early (round {current_round} <= {keep_recent_rounds + 1})", category="combat_events")
            return conversation_history
        
        # Check if compression is needed
        rounds_to_compress = []
        for round_num in range(1, current_round - keep_recent_rounds):
            # Check if this round is already compressed
            already_compressed = any(
                msg.get('role') == 'assistant' and 
                f"COMBAT ROUND {round_num} SUMMARY:" in msg.get('content', '')
                for msg in conversation_history
            )
            if not already_compressed:
                rounds_to_compress.append(round_num)
            else:
                debug(f"COMPRESSION: Round {round_num} already compressed", category="combat_events")
        
        if not rounds_to_compress:
            debug("COMPRESSION: No rounds need compression", category="combat_events")
            return conversation_history
        
        debug(f"COMPRESSION: Compressing rounds {rounds_to_compress}", category="combat_events")
        
        # Find round boundaries
        round_boundaries = {}
        current_tracking_round = None
        
        for i, msg in enumerate(conversation_history):
            content = msg.get('content', '')
            
            # Check for combat round markers in user messages
            # Look for both old format (COMBAT ROUND X) and new format (combat_round: X)
            if msg.get('role') == 'user':
                # Old format: COMBAT ROUND X
                match = re.search(r'COMBAT ROUND (\d+)', content)
                if not match:
                    # New format from initiative tracker: combat_round: X
                    match = re.search(r'combat_round:\s*(\d+)', content)
                
                if match:
                    round_num = int(match.group(1))
                    if round_num in rounds_to_compress:
                        current_tracking_round = round_num
                        if round_num not in round_boundaries:
                            round_boundaries[round_num] = []
                        round_boundaries[round_num].append(i)
            
            # Check for combat_round field in AI responses
            elif msg.get('role') == 'assistant' and '"combat_round"' in content:
                try:
                    # Extract JSON from content
                    json_match = re.search(r'\{.*"combat_round"\s*:\s*(\d+).*\}', content, re.DOTALL)
                    if json_match:
                        round_num = int(json_match.group(1))
                        if round_num in rounds_to_compress:
                            current_tracking_round = round_num
                            if round_num not in round_boundaries:
                                round_boundaries[round_num] = []
                            round_boundaries[round_num].append(i)
                except:
                    pass
            
            # Continue tracking messages for current round
            elif current_tracking_round and current_tracking_round in round_boundaries:
                round_boundaries[current_tracking_round].append(i)
                
                # Stop tracking when we hit the next round
                # Check both old and new format
                next_round_match = re.search(r'COMBAT ROUND (\d+)', content)
                if not next_round_match:
                    next_round_match = re.search(r'combat_round:\s*(\d+)', content)
                
                if next_round_match and int(next_round_match.group(1)) != current_tracking_round:
                    current_tracking_round = None
        
        # Compress each round
        new_conversation = []
        processed_indices = set()
        
        for i, msg in enumerate(conversation_history):
            if i in processed_indices:
                continue
            
            # Check if this starts a round to compress
            round_to_compress = None
            for round_num, indices in round_boundaries.items():
                if i == indices[0]:
                    round_to_compress = round_num
                    break
            
            if round_to_compress:
                # Extract messages for this round
                indices = round_boundaries[round_to_compress]
                round_messages = []
                for idx in indices:
                    if idx < len(conversation_history):
                        round_messages.append(conversation_history[idx])
                
                # Generate summary
                summary = generate_combat_round_summary(round_to_compress, round_messages)
                
                if summary:
                    # Add compressed round
                    new_conversation.append({
                        "role": "assistant",
                        "content": f"COMBAT ROUND {round_to_compress} SUMMARY:\n{json.dumps(summary, indent=2)}"
                    })
                    
                    # Add transition message
                    if round_to_compress < current_round - keep_recent_rounds:
                        new_conversation.append({
                            "role": "user",
                            "content": f"Round {round_to_compress} ends and Round {round_to_compress + 1} begins"
                        })
                    
                    processed_indices.update(indices)
                    info(f"COMPRESSION: Compressed round {round_to_compress}", category="combat_events")
                else:
                    # Keep original if compression fails
                    for idx in indices:
                        new_conversation.append(conversation_history[idx])
                        processed_indices.add(idx)
            else:
                # Keep message as-is
                new_conversation.append(msg)
                processed_indices.add(i)
        
        return new_conversation
        
    except Exception as e:
        error(f"COMPRESSION: Error compressing combat rounds", exception=e, category="combat_events")
        return conversation_history

def _normalize_combatant_name(name):
    """Normalize combatant names for case-insensitive fuzzy matching."""
    return str(name or "").split("(")[0].strip().lower()


def _name_matches_authoritative_roster(candidate_name, authoritative_names):
    """Return True when candidate name fuzzily matches a known roster entry."""
    if not candidate_name:
        return False

    for known_name in authoritative_names:
        if candidate_name in known_name or known_name in candidate_name:
            return True
    return False


def _collect_authoritative_combat_roster(encounter_data, multi_pc_manager=None, party_tracker_data=None):
    """Collect authoritative combat roster from encounter + active multi-PC roster."""
    roster = []
    seen = set()

    def add_entry(name, combatant_type):
        normalized_name = _normalize_combatant_name(name)
        if not normalized_name or normalized_name in seen:
            return

        seen.add(normalized_name)
        roster.append({
            "name": str(name).strip(),
            "type": str(combatant_type or "unknown").strip(),
            "normalized_name": normalized_name,
        })

    for creature in encounter_data.get("creatures", []):
        add_entry(creature.get("name", "Unknown"), creature.get("type", "unknown"))

    # TABLETOP MODE: C4.2 - Include active multi-PC roster so non-active PCs are valid targets
    if multi_pc_manager:
        for pc_name in multi_pc_manager.pc_states.keys():
            add_entry(pc_name, "player")
    elif isinstance(party_tracker_data, dict):
        for member in party_tracker_data.get("partyMembers", []):
            if isinstance(member, dict):
                add_entry(member.get("name", ""), "player")
            else:
                add_entry(member, "player")

    return roster


def validate_combatant_integrity(response_json_str, encounter_data, multi_pc_manager=None, party_tracker_data=None):
    """
    Validates that the AI has not hallucinated new combatants or acted for non-existent ones.
    Returns True if valid, or an error message string if invalid.
    """
    try:
        if not isinstance(response_json_str, str):
            return True

        response = json.loads(response_json_str)
        actions = response.get("actions", [])
        
        # 1. Build authoritative list of valid combat targets from encounter + multi-PC roster
        authoritative_roster = _collect_authoritative_combat_roster(
            encounter_data,
            multi_pc_manager=multi_pc_manager,
            party_tracker_data=party_tracker_data,
        )
        authoritative_names = [entry["normalized_name"] for entry in authoritative_roster]

        # 2. Validate updateCharacterInfo/updateNPCInfo targets against authoritative roster
        unknown_targets = set()
        
        for action in actions:
            act_type = action.get("action", "").lower()
            params = action.get("parameters", {})
            
            # updateCharacterInfo/updateNPCInfo target check
            if act_type in ["updatecharacterinfo", "updatenpcinfo"]:
                char_name = params.get("characterName", "") or params.get("npcName", "")
                if char_name:
                    clean_name = _normalize_combatant_name(char_name)

                    if not _name_matches_authoritative_roster(clean_name, authoritative_names):
                        unknown_targets.add(char_name)

        if unknown_targets:
            # Construct strict rejection message with expanded authoritative roster
            known_list_str = ", ".join(
                [f"{entry['name']} ({entry['type']})" for entry in authoritative_roster]
            )
            return (
                f"INTEGRITY ERROR: updateCharacterInfo/updateNPCInfo references targets not in the authoritative combat roster: {', '.join(unknown_targets)}.\n"
                f"The valid target roster is: {known_list_str}.\n"
                "PCs remain forbidden as DM-controlled actors during ENEMY_PHASE, but PCs are valid targets for enemy/NPC effects."
            )
            
        return True
        
    except json.JSONDecodeError:
        return True # JSON format errors are handled elsewhere
    except Exception as e:
        # Fail open if validation crashes, but log it
        error(f"INTEGRITY_CHECK_ERROR: {e}", category="combat_validation")
        return True

def generate_combat_round_summary(round_num, round_messages):
    """Generate a structured summary of a combat round using AI"""
    try:
        # Extract content from messages
        round_content = "\n\n".join([
            f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')}"
            for msg in round_messages
        ])
        
        prompt = f"""Convert this combat round into a structured JSON summary optimized for AI consumption.

Round {round_num} Combat Log:
{round_content}

Create a JSON summary with EXACTLY this structure:
{{
  "round": {round_num},
  "actions": [
    {{"actor": "name", "init": number, "action": "action_type", "target": "target_name", "roll": "dice+mod=total vs AC/DC", "result": "hit/miss/save/fail", "damage": "X type" or "heal": "X", "effects": "HP changes, conditions, etc"}}
  ],
  "deaths": ["list of creatures that died this round"],
  "status_changes": ["new conditions or effects applied"],
  "resource_usage": {{"character": "resources used (spell slots, abilities, etc)"}},
  "narrative_highlights": ["2-4 evocative single sentences capturing key dramatic moments, critical hits, deaths, powerful spells, or memorable character actions"],
  "round_end_state": {{
    "alive": ["Name (current/max HP)"],
    "dead": ["Name"],
    "conditions": {{"Name": ["conditions"]}}
  }}
}}

Focus on mechanical accuracy for the actions. For narrative_highlights, extract the most dramatic or memorable moments that happened this round - critical hits, character deaths, powerful spells, clutch saves, or impactful dialogue. Keep each highlight to one evocative sentence."""

        # Use the mini model for efficiency
        response = client.chat.completions.create(
            model=DM_MINI_MODEL,
            messages=[
                {"role": "system", "content": "You are a combat log analyzer. Extract mechanical game information and key narrative moments. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
            # Note: response_format removed for LM Studio compatibility
            # The prompt already instructs the model to return JSON
        )
        
        # Track usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(response, context={'endpoint': 'combat_dm', 'purpose': 'combat_turn_processing', 'model': selected_model})
            except:
                pass
        
        summary = json.loads(response.choices[0].message.content)
        return summary
        
    except Exception as e:
        error(f"COMPRESSION: Failed to generate round {round_num} summary", exception=e, category="combat_events")
        return None


def _queue_final_character_update(
    final_character_updates: Dict[str, List[Dict[str, Any]]],
    character_name: Optional[str],
    changes: Optional[str] = None,
    ops: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Queue a character update payload for end-of-turn persistence."""
    if not character_name or (not changes and not ops):
        return

    final_character_updates.setdefault(character_name, []).append({
        "changes": changes,
        "ops": ops,
    })


def _sync_multi_pc_character_state(multi_pc_manager: Any, character_name: str) -> None:
    """Refresh in-memory multi-PC state from persisted character data."""
    if not multi_pc_manager:
        return

    persisted_path = f"characters/{normalize_character_name(character_name)}.json"
    persisted_data = safe_json_load(persisted_path)
    if isinstance(persisted_data, dict):
        multi_pc_manager.sync_pc_persistent_state(character_name, persisted_data)


def _apply_final_character_updates(
    final_character_updates: Dict[str, List[Dict[str, Any]]],
    multi_pc_manager: Any,
) -> None:
    """Persist queued character updates while preserving deterministic ops payloads."""
    if not final_character_updates:
        return

    info("STATE_UPDATE: Applying all consolidated updates.", category="character_updates")
    debug(f"AMMO_DEBUG: Processing {len(final_character_updates)} character updates", category="ammunition")

    for character_name, update_entries in final_character_updates.items():
        ops_entries = [entry for entry in update_entries if entry.get("ops")]
        prose_changes = [entry.get("changes") for entry in update_entries if entry.get("changes") and not entry.get("ops")]

        for entry in ops_entries:
            entry_changes = entry.get("changes") or ""
            entry_ops = entry.get("ops")
            try:
                update_success = update_character_info(character_name, entry_changes, ops=entry_ops)
                if not update_success:
                    error(f"FAILURE: Deterministic combat update failed for {character_name}.", category="character_updates")
                    continue
                _sync_multi_pc_character_state(multi_pc_manager, character_name)
            except Exception as e:
                error(f"FAILURE: Critical error during deterministic combat update for {character_name}", exception=e, category="character_updates")

        if prose_changes:
            final_change_string = "Following the turn's events: " + ", and ".join(prose_changes) + "."
            info(f"FINAL_CHANGE_STRING for {character_name}: {final_change_string}", category="character_updates")

            if any(word in final_change_string.lower() for word in ["arrow", "bolt", "ammunition", "ammo", "expended"]):
                debug(f"AMMO_DEBUG: About to update ammunition for {character_name}", category="ammunition")
                debug(f"AMMO_DEBUG: Final change string: '{final_change_string}'", category="ammunition")

            try:
                update_success = update_character_info(character_name, final_change_string)
                if not update_success:
                    error(f"FAILURE: Final consolidated update failed for {character_name}.", category="character_updates")
                else:
                    _sync_multi_pc_character_state(multi_pc_manager, character_name)
                    if any(word in final_change_string.lower() for word in ["arrow", "bolt", "ammunition", "ammo", "expended"]):
                        debug(f"AMMO_DEBUG: Successfully processed ammunition update for {character_name}", category="ammunition")
            except Exception as e:
                error(f"FAILURE: Critical error during consolidated update for {character_name}", exception=e, category="character_updates")
                if any(word in final_change_string.lower() for word in ["arrow", "bolt", "ammunition", "ammo", "expended"]):
                    debug(f"AMMO_DEBUG: Exception during ammunition update: {str(e)}", category="ammunition")

def run_combat_simulation(encounter_id, party_tracker_data, location_info):
    """Run combat simulation with single-session ownership safeguards."""
    effective_encounter_id = str(encounter_id).strip()
    durable_owner = ""

    # TABLETOP MODE: Prefer durable encounter owner from party tracker if the
    # caller passed a mismatched encounter id.
    try:
        durable_tracker = safe_json_load("party_tracker.json") or {}
        world_conditions = durable_tracker.get("worldConditions", {})
        durable_owner = str(world_conditions.get("activeCombatEncounter", "")).strip()
    except Exception as e:
        warning(
            f"COMBAT_SESSION_GUARD: Could not read durable combat owner, continuing fail-open: {e}",
            category="combat_events"
        )

    if durable_owner and durable_owner != effective_encounter_id:
        warning(
            f"COMBAT_SESSION_MISMATCH: Requested encounter '{effective_encounter_id}' does not match "
            f"durable owner '{durable_owner}'. Preferring durable owner.",
            category="combat_events"
        )
        effective_encounter_id = durable_owner

    try:
        _enter_combat_session(effective_encounter_id)
    except CombatSessionAlreadyActiveError as e:
        error(f"COMBAT_SESSION_GUARD: {e}", category="combat_events")
        return None, None

    try:
        return _run_combat_simulation_internal(effective_encounter_id, party_tracker_data, location_info)
    finally:
        _exit_combat_session(effective_encounter_id)


def _run_combat_simulation_internal(encounter_id, party_tracker_data, location_info):
   """Main function to run the combat simulation"""
   print(f"\n[COMBAT_MANAGER] ========== COMBAT SIMULATION START ==========")
   print(f"[COMBAT_MANAGER] Encounter ID: {encounter_id}")
   print(f"[COMBAT_MANAGER] Location: {location_info.get('name', 'Unknown')}")
   debug(f"INITIALIZATION: Starting combat simulation for encounter {encounter_id}", category="combat_events")
   
   # Initialize path manager
   from utils.module_path_manager import ModulePathManager
   from utils.encoding_utils import safe_json_load
   party_tracker = {}
   try:
       party_tracker = safe_json_load("party_tracker.json")
       current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
       path_manager = ModulePathManager(current_module)
   except:
       path_manager = ModulePathManager()

   # Load encounter data FIRST so it's available for prompt setup
   json_file_path = f"modules/encounters/encounter_{encounter_id}.json"
   print(f"[COMBAT_MANAGER] Loading encounter file: {json_file_path}")
   try:
       encounter_data = safe_json_load(json_file_path)
       if not encounter_data:
           print(f"[COMBAT_MANAGER] Failed to load encounter file")
           error(f"FAILURE: Failed to load encounter file {json_file_path}", category="file_operations")
           return None, None
       print(f"[COMBAT_MANAGER] Encounter loaded: {len(encounter_data.get('creatures', []))} creatures")
   except Exception as e:
       print(f"[COMBAT_MANAGER] Exception loading encounter: {str(e)}")
       error(f"FAILURE: Failed to load encounter file {json_file_path}", exception=e, category="file_operations")
       return None, None

   # TABLETOP MODE: C3.1/C3.2 - Normalize Phase 1 initiative state for active encounters
   if MULTI_PC_COMBAT_AVAILABLE and is_multi_pc_combat_enabled():
       encounter_data, encounter_changed, mirror_payload = normalize_phase1_initiative(encounter_data, party_tracker)
       if encounter_changed:
           save_json_file(json_file_path, encounter_data)
           debug("STATE_SYNC: Normalized Phase 1 initiative state", category="combat_events")
       if mirror_payload:
           party_tracker.setdefault("worldConditions", {})["combatInitiative"] = mirror_payload
           party_tracker_data.setdefault("worldConditions", {})["combatInitiative"] = mirror_payload
           save_json_file("party_tracker.json", party_tracker)
           debug("STATE_SYNC: Updated party tracker combatInitiative mirror", category="combat_events")

   # TABLETOP MODE: Retrieve or initialize combat manager
   multi_pc_manager = None
   if MULTI_PC_COMBAT_AVAILABLE and is_multi_pc_combat_enabled():
       multi_pc_manager = get_combat_manager()
       if not multi_pc_manager:
           # Re-initialize manager if it doesn't exist (e.g., after script restart)
           debug("[COMBAT_MANAGER] Re-initializing MultiPCCombatManager", category="combat_events")
           multi_pc_manager = create_combat_manager(party_tracker_data)
       
       # INITIALIZE TURN QUEUE
       if multi_pc_manager:
            multi_pc_manager.initialize_turn_queue(encounter_data)
            
            # TABLETOP MODE: Sync round state from encounter file
            # The manager defaults to round 1 on construction, but the encounter
            # may be at a higher round from a previous session
            if multi_pc_manager.sync_round_from_encounter(encounter_data):
                info(f"STATE_SYNC: Combat round synced to {multi_pc_manager.current_round} from encounter file", category="combat_events")

    # Check if combat history file exists and has content to determine if we are resuming.
   if os.path.exists(conversation_history_file) and os.path.getsize(conversation_history_file) > 100:
       conversation_history = load_json_file(conversation_history_file)
       
       # CRITICAL FIX: Ensure we are resuming the SAME encounter, not an old one
       history_encounter_id = None
       # Check the system message that stores the encounter ID (usually index 1)
       for msg in conversation_history[:3]:
           if msg.get("role") == "system" and "Current Combat Encounter:" in msg.get("content", ""):
               history_encounter_id = msg["content"].replace("Current Combat Encounter:", "").strip()
               break
       
       if history_encounter_id == encounter_id:
           is_resuming = True
           print(f"[COMBAT_MANAGER] Resuming existing combat session for encounter {encounter_id}.")
       else:
           is_resuming = False
           print(f"[COMBAT_MANAGER] Found stale history for encounter '{history_encounter_id}', starting fresh for '{encounter_id}'.")
           # Clear the stale conversation history
           conversation_history = []
   else:
       is_resuming = False
       
   if not is_resuming:
        # TABLETOP MODE: Select correct system prompt
        prompt_file = 'combat/combat_sim_prompt.txt'
        is_multipc = MULTI_PC_COMBAT_AVAILABLE and is_multi_pc_combat_enabled()
        
        if is_multipc:
            # TABLETOP MODE: Multi-PC sim prompt authority is compressed-only.
            prompt_file = 'combat/combat_sim_prompt_multipc_compressed.txt'
            debug(f"[COMBAT_MANAGER] Loading Multi-PC system prompt: {prompt_file}", category="combat_events")

        system_prompt = read_prompt_from_file(prompt_file)
        
        # TABLETOP MODE: Replace placeholders in system prompt
        if is_multipc:
            # Get all PC names
            pc_names = []
            for creature in encounter_data.get("creatures", []):
                if creature.get("type") == "player":
                    pc_names.append(creature.get("name", "Unknown PC"))
            
            pc_list_str = ", ".join(pc_names)
            active_pc = party_tracker_data.get("active_character") or (pc_names[0] if pc_names else "Unknown PC")
            
            system_prompt = system_prompt.replace("[PC_LIST]", pc_list_str)
            # TABLETOP MODE: [PC_NAME] left as literal metavariable - per-turn context provides concrete name
            debug(f"[COMBAT_MANAGER] Replaced Multi-PC placeholders: PC_LIST={pc_list_str}", category="combat_events")

        conversation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Current Combat Encounter: {encounter_id}"},
            {"role": "system", "content": ""}, # Player data placeholder (Head Context)
            {"role": "system", "content": ""}, # Monster templates placeholder
            {"role": "system", "content": ""}, # Location info placeholder
       ]
        print(f"[COMBAT_MANAGER] Starting new combat session (Mode: {'Multi-PC' if 'multipc' in prompt_file else 'Single-PC'}).")

   # Initialize and reset secondary model histories
   second_model_history = []
   third_model_history = []
   save_json_file(second_model_history_file, second_model_history)
   save_json_file(third_model_history_file, third_model_history)
   
   # Initialize data containers
   player_info = None
   monster_templates = {}
   npc_templates = {}
   
   # Extract data for all creatures in the encounter
   for creature in encounter_data["creatures"]:
       if creature["type"] == "player":
           player_name = normalize_character_name(creature["name"])
           player_file = path_manager.get_character_path(player_name)
           print(f"[COMBAT_MANAGER] Loading player: {creature['name']} from {player_file}")
           try:
               player_info = safe_json_load(player_file)
               if not player_info:
                   print(f"[COMBAT_MANAGER] Failed to load player file")
                   error(f"FAILURE: Failed to load player file: {player_file}", category="file_operations")
                   return None, None
               print(f"[COMBAT_MANAGER] Player loaded successfully")
           except Exception as e:
               print(f"[COMBAT_MANAGER] Exception loading player: {str(e)}")
               error(f"FAILURE: Failed to load player file {player_file}", exception=e, category="file_operations")
               return None, None
       
       elif creature["type"] == "enemy":
           monster_type = creature["monsterType"]
           if monster_type not in monster_templates:
               monster_file = path_manager.get_monster_path(monster_type)
               print(f"[COMBAT_MANAGER] Loading monster: {creature['name']} (type: {monster_type})")
               debug(f"FILE_OP: Attempting to load monster file: {monster_file}", category="file_operations")
               try:
                   monster_data = safe_json_load(monster_file)
                   if monster_data:
                       monster_templates[monster_type] = monster_data
                       print(f"[COMBAT_MANAGER] Monster loaded successfully: {monster_type}")
                       debug(f"SUCCESS: Successfully loaded monster: {monster_type}", category="file_operations")
                   else:
                       print(f"[COMBAT_MANAGER] Failed to load monster file")
                       error(f"FILE_OP: Failed to load monster file: {monster_file}", category="file_operations")
               except FileNotFoundError as e:
                   error(f"FAILURE: Monster file not found: {monster_file}", category="file_operations")
                   error(f"FAILURE: {str(e)}", category="file_operations")
                   # Check available files for debugging
                   monster_dir = f"{path_manager.module_dir}/monsters"
                   if os.path.exists(monster_dir):
                       debug(f"FILE_OP: Available monster files in {monster_dir}:", category="file_operations")
                       for f in os.listdir(monster_dir):
                           debug(f"  - {f}", category="combat_validation")
                   return None, None
               except json.JSONDecodeError as e:
                   error(f"FAILURE: Invalid JSON in monster file {monster_file}", exception=e, category="file_operations")
                   return None, None
               except Exception as e:
                   error(f"FAILURE: Failed to load monster file {monster_file}", exception=e, category="file_operations")
                   error(f"FAILURE: Exception type: {type(e).__name__}", category="file_operations")
                   import traceback
                   traceback.print_exc()
                   return None, None
       
       elif creature["type"] == "npc":
           # Use fuzzy matching for NPC loading
           npc_data, matched_filename = load_npc_with_fuzzy_match(creature["name"], path_manager)
           if npc_data and matched_filename:
               # Use the matched filename as the key to avoid duplicates
               if matched_filename not in npc_templates:
                   npc_templates[matched_filename] = npc_data
           else:
               error(f"FAILURE: Failed to load NPC file for: {creature['name']}", category="file_operations")
   
   # Populate the system messages
   if not is_resuming:
       # New combat - create fresh system messages and clear compression caches
       print("[COMBAT_MANAGER] Starting new combat - clearing compression caches")
       
       # Clear combat compression caches for fresh start
       cache_files = [
           "modules/conversation_history/combat_compression_cache.json",
           "modules/conversation_history/combat_user_message_cache.json"
       ]
       
       for cache_file in cache_files:
           if os.path.exists(cache_file):
               try:
                   os.remove(cache_file)
                   print(f"[COMBAT_MANAGER] Cleared cache: {cache_file}")
               except Exception as e:
                   print(f"[COMBAT_MANAGER] Warning: Could not clear cache {cache_file}: {e}")
       
       # TABLETOP MODE: Authoritative Head Context (JSON for Multi-PC, Text for Single-PC)
       if multi_pc_manager:
           conversation_history[2]["content"] = multi_pc_manager.format_multi_pc_head_context()
       else:
           # Format player character using the same function as NPCs
           formatted_player = format_character_for_combat(player_info, char_type="player")
           conversation_history[2]["content"] = f"Here's the player character data:\n\n{formatted_player}\n"
           
       conversation_history[3]["content"] = f"Monster Templates:\n{json.dumps({k: filter_dynamic_fields(v) for k, v in monster_templates.items()}, indent=2)}"
       if not monster_templates and any(c["type"] == "enemy" for c in encounter_data["creatures"]):
           error("FAILURE: No monster templates were loaded!", category="file_operations")
           return None, None
       
       # Filter out adventureSummary and encounters from location data to reduce token usage (same as conversation_utils.py)
       # Encounters are tracked separately and don't need to be in the location context
       location_for_combat = {k: v for k, v in location_info.items() if k not in ['adventureSummary', 'encounters']}
       conversation_history[4]["content"] = f"Location:\n{json.dumps(location_for_combat, indent=2)}"
       
       # Add each NPC as a separate system message (matching conversation_utils format)
       # Get NPC roles from party tracker
       party_npcs = party_tracker_data.get('partyNPCs', [])
       npc_roles = {npc['name']: npc.get('role', 'Adventurer') for npc in party_npcs}
       
       # Format and add each NPC individually
       for npc_name, npc_data in npc_templates.items():
           # Get the role for this NPC
           npc_role = npc_roles.get(npc_data.get('name', ''), 'Adventurer')
           
           # Format the NPC data using the same format as conversation_utils
           formatted_data = format_npc_for_combat(npc_data, npc_role)
           npc_message = f"Here's the NPC data for {npc_data['name']}:\n\n{formatted_data}\n"
           conversation_history.append({"role": "system", "content": npc_message})
       
       conversation_history.append({"role": "system", "content": f"Encounter Details:\n{json.dumps(filter_encounter_for_system_prompt(encounter_data), indent=2)}"})
       
       log_conversation_structure(conversation_history)
       save_json_file(conversation_history_file, conversation_history)
   else:
       # Resuming combat - update player character and NPC templates to new format if needed
       print("[COMBAT_MANAGER] Updating player and NPC templates to new format during resume...")
       
       # First, update the player character or Multi-PC head context format
       for i in range(len(conversation_history)):
           msg = conversation_history[i]
           # Check for either old format (with json), new format (with "Here's the player character data"), or Multi-PC JSON format
           is_player_data = "Player Character:" in msg.get("content", "") or "Here's the player character data:" in msg.get("content", "")
           is_multipc_data = "=== AUTHORITATIVE MULTI-PC STATE (JSON) ===" in msg.get("content", "")
           
           if msg.get("role") == "system" and (is_player_data or is_multipc_data):
               # Found data slot - update it to ensure it's current using the correct format for the mode
               print(f"[COMBAT_MANAGER] Updating head context at index {i}")
               if multi_pc_manager:
                   conversation_history[i]["content"] = multi_pc_manager.format_multi_pc_head_context()
               else:
                   formatted_player = format_character_for_combat(player_info, char_type="player")
                   conversation_history[i]["content"] = f"Here's the player character data:\n\n{formatted_player}\n"
               break
       
       # Find and remove old NPC Templates message if it exists
       for i in range(len(conversation_history) - 1, -1, -1):
           msg = conversation_history[i]
           if msg.get("role") == "system" and "NPC Templates:" in msg.get("content", ""):
               # Found old format - remove it
               print(f"[COMBAT_MANAGER] Removing old NPC Templates at index {i}")
               conversation_history.pop(i)
               break
       
       # Also remove any old individual NPC messages (in case of partial migration)
       indices_to_remove = []
       for i in range(len(conversation_history) - 1, -1, -1):
           msg = conversation_history[i]
           if msg.get("role") == "system" and "Here's the NPC data for" in msg.get("content", ""):
               indices_to_remove.append(i)
       
       for idx in sorted(indices_to_remove, reverse=True):
           print(f"[COMBAT_MANAGER] Removing old NPC message at index {idx}")
           conversation_history.pop(idx)
       
       # Now add NPCs in new format
       party_npcs = party_tracker_data.get('partyNPCs', [])
       npc_roles = {npc['name']: npc.get('role', 'Adventurer') for npc in party_npcs}
       
       # Find where to insert the new NPC messages (after location, before encounter details)
       insert_index = -1
       for i, msg in enumerate(conversation_history):
           if msg.get("role") == "system" and "Location:" in msg.get("content", ""):
               insert_index = i + 1
               break
       
       if insert_index == -1:
           # Fallback: insert at position 5 (after standard system messages)
           insert_index = min(5, len(conversation_history))
       
       # Insert each NPC in the new format
       for npc_name, npc_data in npc_templates.items():
           npc_role = npc_roles.get(npc_data.get('name', ''), 'Adventurer')
           formatted_data = format_npc_for_combat(npc_data, npc_role)
           npc_message = f"Here's the NPC data for {npc_data['name']}:\n\n{formatted_data}\n"
           conversation_history.insert(insert_index, {"role": "system", "content": npc_message})
           insert_index += 1
           print(f"[COMBAT_MANAGER] Added NPC {npc_data['name']} in new format at index {insert_index - 1}")
       
       # Save the updated conversation history
       save_json_file(conversation_history_file, conversation_history)
       print("[COMBAT_MANAGER] NPC templates updated to new format")
   
   # Prepare initial dynamic state info for all creatures
   dynamic_state_parts = []
   user_controlled_parts = []
   dm_controlled_parts = []
   enemy_parts = []
   
   # Player info - ALWAYS reload from character file for current HP (source of truth)
   player_name_display = player_info["name"]
   player_file = path_manager.get_character_path(normalize_character_name(player_name_display))
   try:
       fresh_player_data = safe_json_load(player_file)
       if fresh_player_data:
           # Use fresh data from character file
           current_hp = fresh_player_data.get("hitPoints", 0)
           max_hp = fresh_player_data.get("maxHitPoints", 0)
           player_status = fresh_player_data.get("status", "alive")
           player_condition = fresh_player_data.get("condition", "none")
           player_conditions = fresh_player_data.get("condition_affected", [])
           # Also update spell slots from fresh data
           player_info["spellcasting"] = fresh_player_data.get("spellcasting", {})
       else:
           # Fallback to stale data if load fails
           current_hp = player_info.get("hitPoints", 0)
           max_hp = player_info.get("maxHitPoints", 0)
           player_status = player_info.get("status", "alive")
           player_condition = player_info.get("condition", "none")
           player_conditions = player_info.get("condition_affected", [])
   except Exception as e:
       error(f"Failed to reload player data for initial CREATURE STATES", exception=e, category="combat_events")
       # Fallback to stale data
       current_hp = player_info.get("hitPoints", 0)
       max_hp = player_info.get("maxHitPoints", 0)
       player_status = player_info.get("status", "alive")
       player_condition = player_info.get("condition", "none")
       player_conditions = player_info.get("condition_affected", [])
   
   # Build compact state line
   state_line = f"{player_name_display}: HP {current_hp}/{max_hp}, {player_status}"
   if player_condition != "none":
       state_line += f", {player_condition}"
   if player_conditions:
       state_line += f", conditions: {','.join(player_conditions)}"
   
   # Add spell slots inline if player has spellcasting
   spellcasting = player_info.get("spellcasting", {})
   if spellcasting and "spellSlots" in spellcasting:
       spell_slots = spellcasting["spellSlots"]
       slot_parts = []
       for level in range(1, 10):  # Spell levels 1-9
           level_key = f"level{level}"
           if level_key in spell_slots:
               slot_data = spell_slots[level_key]
               current_slots = slot_data.get("current", 0)
               max_slots = slot_data.get("max", 0)
               if max_slots > 0:  # Only show levels with available slots
                   slot_parts.append(f"L{level}:{current_slots}/{max_slots}")
       if slot_parts:
           state_line += f", Spell Slots: {' '.join(slot_parts)}"
   
   user_controlled_parts.append(state_line)
   
   # Creature info
   for creature in encounter_data["creatures"]:
       if creature["type"] != "player":
           creature_name = creature.get("name", "Unknown Creature")
           creature_hp = creature.get("currentHitPoints", "Unknown")
           creature_status = creature.get("status", "alive")
           creature_condition = creature.get("condition", "none")
           
           # Get the actual max HP from the correct source
           if creature["type"] == "npc":
               # For NPCs, look up their true max HP from their character file using fuzzy match
               npc_data, matched_filename = load_npc_with_fuzzy_match(creature_name, path_manager)
               if npc_data:
                   creature_max_hp = npc_data["maxHitPoints"]
               else:
                   error(f"FAILURE: Failed to get correct max HP for {creature_name}", category="combat_events")
                   creature_max_hp = creature.get("maxHitPoints", "Unknown")
           else:
               # For monsters, use the encounter data
               creature_max_hp = creature.get("maxHitPoints", "Unknown")
           
           # Build compact creature state line
           creature_line = f"{creature_name}: HP {creature_hp}/{creature_max_hp}, {creature_status}"
           if creature_condition != "none":
               creature_line += f", {creature_condition}"
           
           # Group by control type
           if creature["type"] == "npc":
               dm_controlled_parts.append(creature_line)
           elif creature["type"] == "enemy":
               enemy_parts.append(creature_line)
           else:
               # Fallback for any other types
               dm_controlled_parts.append(creature_line)
   
   # Build the labeled sections
   if user_controlled_parts:
       dynamic_state_parts.append("Active Player Characters (User Controlled):")
       dynamic_state_parts.extend([f"  {p}" for p in user_controlled_parts])
   
   if dm_controlled_parts:
       dynamic_state_parts.append("Accompanied by Party NPCs (DM Controlled):")
       dynamic_state_parts.extend([f"  {p}" for p in dm_controlled_parts])
       
   if enemy_parts:
       dynamic_state_parts.append("Enemies (DM Controlled):")
       dynamic_state_parts.extend([f"  {p}" for p in enemy_parts])
   
   all_dynamic_state = "\n".join(dynamic_state_parts)

   # TABLETOP MODE: C4.2/C4.3 - Include active multi-PC roster so PCs are valid targets
   roster_entries = _collect_authoritative_combat_roster(
       encounter_data,
       multi_pc_manager=multi_pc_manager,
       party_tracker_data=party_tracker_data,
   )
   roster_list = [f"- {entry['name']} ({entry['type']})" for entry in roster_entries]
   roster_str = "\n".join(roster_list) if roster_list else "- None"
   all_dynamic_state += (
       f"\n\n++ VALID TARGETS & ACTORS (IMMUTABLE) ++\n{roster_str}\n"
       "RULES: This is the definitive list of all beings in the scene. "
       "Do NOT narrate actions for anyone not on this list. "
       "During ENEMY_PHASE, PCs remain forbidden as actors but are valid targets."
   )
   
   # Initialize round tracking and generate prerolls
   # Use combat_round as primary, fall back to current_round
   round_num = encounter_data.get('combat_round', encounter_data.get('current_round', 1))
   preroll_text = generate_prerolls(encounter_data, round_num=round_num)
   
   encounter_data['preroll_cache'] = {
       'round': round_num,
       'rolls': preroll_text,
       'preroll_id': f"{round_num}-{random.randint(1000,9999)}"
   }
   save_json_file(json_file_path, encounter_data)
   debug(f"STATE_CHANGE: Saved prerolls for round {round_num}", category="combat_events")
   
   # --- START: RESUMPTION AND INITIAL SCENE LOGIC ---
   if is_resuming:
       # This is a resumed session. Inject a message to get a re-engagement narration.
       print("[COMBAT_MANAGER] Injecting 'player has returned' message to re-engage AI.")
       debug("RESUME: Starting combat resume flow", category="combat_events")
       print("DEBUG: [RESUME] Starting combat resume flow")
       resume_prompt = "Dungeon Master Note: The game session is resuming after a pause. The player has returned. Please provide a brief narration to re-establish the scene and prompt the player for their next action, based on the last known state from the conversation history."
       
       # Add the resume prompt to the history only if it's not already the last message.
       if not conversation_history or conversation_history[-1].get('content') != resume_prompt:
           debug("RESUME: Adding resume prompt to conversation history", category="combat_events")
           print("DEBUG: [RESUME] Adding resume prompt to conversation history")
           conversation_history.append({"role": "user", "content": resume_prompt})
           save_json_file(conversation_history_file, conversation_history)
       else:
           debug("RESUME: Resume prompt already exists, skipping", category="combat_events")
           print("DEBUG: [RESUME] Resume prompt already exists, skipping")

       # Get the AI's re-engagement response
       try:
           print("[COMBAT_MANAGER] Getting re-engagement narration from AI...")
           debug("RESUME: Requesting AI re-engagement response", category="combat_events")
           print("DEBUG: [RESUME] About to call AI for re-engagement")
           # Use base temperature for re-engagement (no validation failures)
           # Import GPT-5 config
           from config import USE_GPT5_MODELS, GPT5_MINI_MODEL
           
           if USE_GPT5_MODELS:
               # GPT-5: Use mini model for re-engagement
               print(f"DEBUG: [COMBAT RE-ENGAGE] Using GPT-5 model: {GPT5_MINI_MODEL}")
               # Compress conversation history before sending to AI
               messages_to_send = combat_message_compressor.process_combat_conversation(conversation_history)
               
               # Export compressed conversation for review
               with open("debug/api_captures/combat_messages_to_api.json", "w", encoding="utf-8") as f:
                   json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
               print(f"DEBUG: [COMBAT] Exported compressed messages to debug/api_captures/combat_messages_to_api.json")
               
               response = client.chat.completions.create(
                   model=GPT5_MINI_MODEL,
                   messages=messages_to_send
               )

               # Log API call to master log
               try:
                   from utils.api_logger import log_api_call
                   log_api_call("combat", messages_to_send, response,
                               metadata={"branch": "gpt5", "context": "re-engage"})
               except Exception as e:
                   print(f"[API_LOG] Warning: Failed to log combat call: {e}")
           else:
               # GPT-4.1: Use temperature
               temperature_used = get_combat_temperature(encounter_data, validation_attempt=0)
               
               print(f"DEBUG: [COMBAT RE-ENGAGE] Using GPT-4.1 model: {COMBAT_MAIN_MODEL} (temp: {temperature_used})")
               # Compress conversation history before sending to AI
               messages_to_send = combat_message_compressor.process_combat_conversation(conversation_history)
               
               # Export compressed conversation for review
               with open("debug/api_captures/combat_messages_to_api.json", "w", encoding="utf-8") as f:
                   json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
               print(f"DEBUG: [COMBAT] Exported compressed messages to debug/api_captures/combat_messages_to_api.json")
               
               response = client.chat.completions.create(
                   model=COMBAT_MAIN_MODEL,
                   temperature=temperature_used,
                   messages=messages_to_send
               )

               # Log API call to master log
               try:
                   from utils.api_logger import log_api_call
                   log_api_call("combat", messages_to_send, response,
                               metadata={"temperature": temperature_used, "branch": "gpt4.1", "context": "re-engage"})
               except Exception as e:
                   print(f"[API_LOG] Warning: Failed to log combat call: {e}")

           # Track usage if available
           if USAGE_TRACKING_AVAILABLE:
               try:
                   track_response(response)
               except:
                   pass  # Silently ignore tracking errors
           
           resume_response_content = response.choices[0].message.content.strip()
           debug(f"RESUME: Got AI response, length: {len(resume_response_content)}", category="combat_events")
           print(f"DEBUG: [RESUME] Got AI response, length: {len(resume_response_content)}")
           
           conversation_history.append({"role": "assistant", "content": resume_response_content})
           save_json_file(conversation_history_file, conversation_history)

           parsed_response = json.loads(resume_response_content)
           narration = parsed_response.get("narration", "The battle continues! What do you do?")
           print(f"Dungeon Master: {narration}")
           import sys
           sys.stdout.flush()  # Ensure narration is displayed before waiting for input
           debug("RESUME: Successfully displayed re-engagement narration", category="combat_events")
           print("DEBUG: [RESUME] Successfully displayed re-engagement narration and flushed output")

       except Exception as e:
           error("FAILURE: Could not get re-engagement narration.", exception=e, category="combat_events")
           print(f"DEBUG: [RESUME] Error getting re-engagement: {str(e)}")
           print("Dungeon Master: The battle continues! What will you do next?")
           import sys
           sys.stdout.flush()
           debug(f"RESUME: Using fallback narration due to error: {str(e)}", category="combat_events")
   else:
       # This is a new combat. Use the original logic to get the initial scene.

       # TABLETOP MODE: Fast-lane for Phase 1 multi-PC combat with pending initiative
       # Skip redundant LLM narration when main DM response already described the encounter
       is_fast_lane = (
           multi_pc_manager is not None and
           encounter_data.get("awaitingPcGroupRoll", False) is True
       )

       if is_fast_lane:
           info("COMBAT_INIT: Using fast-lane path (skipping initial-scene LLM call)", category="combat_events")
           # Skip the initial scene LLM generation block entirely
           # TABLETOP MODE: Immediately prompt for initiative without extra LLM narration
           print("[skipTTS][prefill:/init ] Dungeon Master: [SYSTEM] Combat initiated. Initiative pending. Enter /init <1-20> to begin combat.")
           import sys
           sys.stdout.flush()
       else:
           debug("AI_CALL: Getting initial scene description...", category="combat_events")
           initiative_order = get_initiative_order(encounter_data)

       # TABLETOP MODE: In fast-lane, skip initial-scene bootstrap entirely and go
       # directly to combat loop so /init can resolve deterministically.
       if not is_fast_lane:
            # TABLETOP MODE: Check for group initiative handover
            initiative_narrative = ""
            if multi_pc_manager:
                combat_initiative = party_tracker_data.get("worldConditions", {}).get("combatInitiative")
                if not combat_initiative:
                    # TABLETOP MODE: C3.2 - Derive from normalized encounter state; do not use legacy reroll fallback
                    normalized_rolls = encounter_data.get("initiativeRolls", {})
                    normalized_winner = encounter_data.get("initiativeWinner")
                    combat_initiative = {
                        "partyRoll": normalized_rolls.get("pcGroup"),
                        "enemyRoll": normalized_rolls.get("dmGroup"),
                        "partyGoesFirst": (normalized_winner == "pcGroup") if normalized_winner in ("pcGroup", "dmGroup") else True
                    }
                    party_tracker_data.setdefault("worldConditions", {})["combatInitiative"] = combat_initiative

                debug(f"[COMBAT_MANAGER] Using group initiative state: {combat_initiative}", category="combat_events")
                multi_pc_manager.party_initiative = combat_initiative.get("partyRoll", 0) or 0
                multi_pc_manager.enemy_initiative = combat_initiative.get("enemyRoll", 0) or 0
                multi_pc_manager.party_goes_first = combat_initiative.get("partyGoesFirst", True)
                initiative_narrative = get_multi_pc_initiative_narrative(multi_pc_manager)
            
            # TABLETOP MODE: Anchor narration to Immutable Roster to prevent phantom enemy hallucination
            initial_prompt_text = f"""The setup scene for the combat has already been given and described to the party. Now, describe the combat situation and ONLY the enemies listed in the VALID TARGETS & ACTORS (IMMUTABLE) roster that the party faces."""
            if initiative_narrative:
                initial_prompt_text = f"{initiative_narrative}\n\n{initial_prompt_text}"

            # TABLETOP MODE: Reinforce Immutable Roster constraint in initial scene prompt
            initial_prompt = f"""Dungeon Master Note: Respond with valid JSON containing a 'narration' field, 'combat_round' field, and an 'actions' array. This is the start of combat, so describe the scene using ONLY creatures from the VALID TARGETS & ACTORS (IMMUTABLE) roster and set initiative order, but don't take any actions yet. Start off by hooking the player and engaging them for the start of combat the way any world class dungeon master would.

Important Character Field Definitions:
- 'status' field: Overall life/death state - ONLY use 'alive', 'dead', 'unconscious', or 'defeated' (lowercase)
- 'condition' field: 5e status conditions - use 'none' when no conditions, or valid 5e conditions like 'blinded', 'charmed', 'poisoned', etc.
- NEVER set condition to 'alive' - that goes in the status field
- NEVER set status to 'none' - use 'alive' for conscious characters

Combat Round Tracking:
- MANDATORY: Include "combat_round": 1 in your response (this is round 1)
- Track rounds throughout combat and increment when all creatures have acted

Current dynamic state for all creatures:
{all_dynamic_state}

Initiative Order: {initiative_order}

{preroll_text}

Player: {initial_prompt_text}"""

            # TABLETOP MODE: Inject multi-PC context into initial prompt
            if multi_pc_manager:
                active_pc = party_tracker_data.get("active_character") or multi_pc_manager.current_pc_name
                initial_prompt = modify_combat_prompt_for_multi_pc(initial_prompt, active_pc, multi_pc_manager)

            conversation_history.append({"role": "user", "content": initial_prompt})
            save_json_file(conversation_history_file, conversation_history)

            max_retries = 3
            initial_response = None
            initial_conversation_length = len(conversation_history)
            initial_retry_feedback_note = None
            
            for attempt in range(max_retries):
                try:
                    # Calculate temperature with attempt number for dynamic adjustment
                    temperature_used = get_combat_temperature(encounter_data, validation_attempt=attempt)

                    retry_local_history = list(conversation_history)
                    if initial_retry_feedback_note:
                        retry_local_history.append({
                            "role": "user",
                            "content": initial_retry_feedback_note,
                        })
                    
                    # Compress conversation history before sending to AI
                    messages_to_send = combat_message_compressor.process_combat_conversation(retry_local_history)
                    
                    # Export compressed conversation for review
                    with open("debug/api_captures/combat_messages_to_api.json", "w", encoding="utf-8") as f:
                        json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
                    print(f"DEBUG: [COMBAT] Exported compressed messages to debug/api_captures/combat_messages_to_api.json")
                    
                    response = client.chat.completions.create(
                        model=COMBAT_MAIN_MODEL, 
                        temperature=temperature_used, 
                             messages=messages_to_send,
                             timeout=COMBAT_API_TIMEOUT_SECONDS  # TABLETOP MODE: Prevent indefinite hang
                    )
                    
                    # Track usage
                    if USAGE_TRACKING_AVAILABLE:
                        try:
                            track_response(response)
                        except:
                            pass
                    
                    initial_response = response.choices[0].message.content.strip()

                    retry_validation_history = list(retry_local_history)
                    retry_validation_history.append({"role": "assistant", "content": initial_response})
                    
                    if not is_valid_json(initial_response):
                        if attempt < max_retries - 1:
                            initial_retry_feedback_note = "Invalid JSON format. Please try again."
                            continue
                        else: break

                    # FIX: Use the correct variable for the user input parameter
                    # PASS MULTI-PC MANAGER FOR INITIAL VALIDATION
                    validation_result = validate_combat_response(
                        initial_response,
                        encounter_data,
                        initial_prompt_text,
                        retry_validation_history,
                        multi_pc_manager=multi_pc_manager,
                    )
                    
                    if validation_result is True:
                        initial_retry_feedback_note = None
                        break
                    else:
                        if attempt < max_retries - 1:
                            initial_retry_feedback_note = validation_result
                            continue
                        else: break
                except Exception as e:
                    error(f"FAILURE: AI call for initial scene failed on attempt {attempt + 1}", exception=e, category="combat_events")
                    if attempt >= max_retries - 1: break
            
            # FIX: Simplified cleanup logic
            conversation_history = conversation_history[:initial_conversation_length]
            if initial_response:
                conversation_history.append({"role": "assistant", "content": initial_response})
                save_json_file(conversation_history_file, conversation_history)
                try:
                    parsed_response = json.loads(initial_response)
                    print(f"Dungeon Master: {parsed_response['narration']}")
                    import sys
                    sys.stdout.flush()
                except (json.JSONDecodeError, KeyError):
                    print(f"Dungeon Master: {initial_response}") # Print raw if parsing fails
                    import sys
                    sys.stdout.flush()
            else:
                error("FAILURE: Could not get a valid initial scene from AI.", category="combat_events")
                return None, None # Exit if we can't start combat
       else:
           debug("COMBAT_INIT: Fast-lane startup complete; deferring narration until phase starts", category="combat_events")
   # --- END: RESUMPTION AND INITIAL SCENE LOGIC ---
   
   # Combat loop
   debug("[COMBAT_MANAGER] Entering main combat loop", category="combat_events")
   print("DEBUG: [COMBAT_LOOP] Entering main while True combat loop")
   if is_resuming:
       print("DEBUG: [RESUME] Successfully reached main combat loop after resume")
   
   # Update status to show combat is active
   try:
       from core.managers.status_manager import status_manager
       status_manager.update_status("Combat in progress - awaiting your action", is_processing=False)
   except Exception as e:
       debug(f"Could not update status: {e}", category="status")
   while True:
       # Ensure all character data is synced to the encounter
       debug("[COMBAT_MANAGER] Syncing character data to encounter", category="combat_events")
       print("DEBUG: [COMBAT_LOOP] Top of while loop - syncing character data")
       
       # TABLETOP MODE: Reload party tracker to get latest active character
       if multi_pc_manager:
           party_tracker_data = safe_json_load("party_tracker.json") or party_tracker_data
           active_pc = party_tracker_data.get("active_character")
           if active_pc:
               multi_pc_manager.set_current_pc(active_pc)
               debug(f"[COMBAT_MANAGER] Multi-PC Active Character: {active_pc}", category="combat_events")

       # Clear processing status when ready for player input
       try:
           from core.managers.status_manager import status_manager
           status_manager.update_status("", is_processing=False)
       except Exception as e:
           debug(f"Could not clear status: {e}", category="status")
       sync_active_encounter()
       
       # TABLETOP MODE: Sync HP from reloaded encounter data to multi_pc_manager
       if multi_pc_manager:
           # Reload encounter data to get fresh HP values synced by sync_active_encounter
           temp_encounter_data = safe_json_load(json_file_path)
           if temp_encounter_data:
               for creature in temp_encounter_data.get("creatures", []):
                   if creature.get("type") == "player":
                       name = creature.get("name")
                       hp = creature.get("currentHitPoints", 0)
                       multi_pc_manager.update_pc_hp(name, hp)
               debug("[COMBAT_MANAGER] Multi-PC Manager HP synced from encounter", category="combat_events")

       # REFRESH CONVERSATION HISTORY WITH LATEST DATA
       debug("STATE_CHANGE: Refreshing conversation history with latest character data...", category="combat_events")
       
       # TABLETOP MODE: Authoritative Head Context Refresh
       if multi_pc_manager:
           # Refresh with authoritative Multi-PC JSON
           conversation_history[2]["content"] = multi_pc_manager.format_multi_pc_head_context()
           debug("[COMBAT_MANAGER] Refreshed Multi-PC Head Context", category="combat_events")
       else:
           # Reload player info FOR CONVERSATION HISTORY ONLY - use same pattern as NPCs
           # This prevents XP reset bug by not overwriting the in-memory player_info object
           player_name = normalize_character_name(player_info["name"])
           player_file = path_manager.get_character_path(player_name)
           try:
               # Load fresh data for conversation history without overwriting player_info
               fresh_player_data = safe_json_load(player_file)
               if not fresh_player_data:
                   error(f"FAILURE: Failed to load player file: {player_file}", category="file_operations")
               else:
                   # Update conversation history with fresh data using compressed format
                   formatted_player = format_character_for_combat(fresh_player_data, char_type="player")
                   conversation_history[2]["content"] = f"Here's the player character data:\n\n{formatted_player}\n"
           except Exception as e:
               error(f"FAILURE: Failed to reload player file {player_file}", exception=e, category="file_operations")
       
       # Reload encounter data
       json_file_path = f"modules/encounters/encounter_{encounter_id}.json"
       try:
           encounter_data = safe_json_load(json_file_path)
           if encounter_data:
               # Find and update the encounter data in conversation history
               for i, msg in enumerate(conversation_history):
                   if msg["role"] == "system" and "Encounter Details:" in msg["content"]:
                       conversation_history[i]["content"] = f"Encounter Details:\n{json.dumps(filter_encounter_for_system_prompt(encounter_data), indent=2)}"
                       break
       except Exception as e:
           error(f"FAILURE: Failed to reload encounter file {json_file_path}", exception=e, category="file_operations")
       
       # Reload NPC data
       for creature in encounter_data["creatures"]:
           if creature["type"] == "npc":
               # Use fuzzy matching for NPC reloading
               npc_data, matched_filename = load_npc_with_fuzzy_match(creature["name"], path_manager)
               if npc_data and matched_filename:
                   # Update the NPC in the templates dictionary
                   npc_templates[matched_filename] = npc_data
               else:
                   error(f"FAILURE: Failed to reload NPC file for: {creature['name']}", category="file_operations")
       
       # Replace NPC templates in conversation history (with dynamic fields filtered)
       for i, msg in enumerate(conversation_history):
           if msg["role"] == "system" and "NPC Templates:" in msg["content"]:
               conversation_history[i]["content"] = f"NPC Templates:\n{json.dumps({k: filter_dynamic_fields(v) for k, v in npc_templates.items()}, indent=2)}"
               break
       
       # Save updated conversation history
       save_json_file(conversation_history_file, conversation_history)
       
       # Display player stats and get input
       player_name_display = player_info["name"]
       current_hp = player_info.get("hitPoints", 0)
       max_hp = player_info.get("maxHitPoints", 0)
       current_xp = player_info.get("experience_points", 0)
       next_level_xp = player_info.get("exp_required_for_next_level", 0)
       current_time_str = party_tracker_data["worldConditions"].get("time", "Unknown")
       
       stats_display = f"[{current_time_str}][HP:{current_hp}/{max_hp}][XP:{current_xp}/{next_level_xp}]"
       
       print("DEBUG: [COMBAT_LOOP] About to request player input")
       debug("COMBAT_LOOP: Requesting player input", category="combat_events")
       try:
           user_input_text = input(f"{stats_display} {player_name_display}: ")
           print(f"DEBUG: [COMBAT_LOOP] Got player input: {user_input_text[:50]}..." if len(user_input_text) > 50 else f"DEBUG: [COMBAT_LOOP] Got player input: {user_input_text}")
           debug(f"COMBAT_LOOP: Received player input of length {len(user_input_text)}", category="combat_events")
       except EOFError:
           error("FAILURE: EOF when reading a line in run_combat_simulation", category="combat_events")
           print("DEBUG: [COMBAT_LOOP] EOF encountered, breaking loop")
           break
       
       # Skip empty input to prevent infinite loop
       if not user_input_text or not user_input_text.strip():
           continue
       
       # Handle local combat commands
       # Clean input of potential multi-PC tags (e.g., "[Character]: /command")
       raw_input = user_input_text.strip()
       clean_input = raw_input
       input_actor_name = None
       
       if raw_input.startswith("[") and "]:" in raw_input:
           parts = raw_input.split("]:", 1)
           if len(parts) == 2:
               input_actor_name = parts[0][1:].strip() # Extract name from [Name]
               clean_input = parts[1].strip()
       
       # TABLETOP MODE: Force context switch if input tag doesn't match current active PC
       # This fixes the bug where tab clicks might be missed, ensuring the correct PC acts.
       if multi_pc_manager and input_actor_name:
           current_active = multi_pc_manager.current_pc_name
           # Case-insensitive comparison
           if current_active and input_actor_name.lower() != current_active.lower():
               debug(f"SWITCH: Detected actor mismatch (Input: {input_actor_name} != Active: {current_active})", category="combat_events")
               # Force switch to the actor specified in the input tag
               # Try to find exact case match in pc_states
               target_pc = None
               for pc_name in multi_pc_manager.pc_states.keys():
                   if pc_name.lower() == input_actor_name.lower():
                       target_pc = pc_name
                       break
               
               if target_pc:
                   multi_pc_manager.set_current_pc(target_pc)
                   party_tracker_data["active_character"] = target_pc
                   safe_write_json("party_tracker.json", party_tracker_data)
                   debug(f"SWITCH: Force-switched active PC to {target_pc}", category="combat_events")
                   
                   # We don't need to 'continue' loop here because we just fixed the state in-memory
                   # for the immediate command processing below.
       
       cmd = clean_input.lower()

       # TABLETOP MODE: Phase 1 initiative gate
       # When awaiting facilitator PC group roll, block all combat progression
       # until valid `/init <1-20>` is received.
       if multi_pc_manager and encounter_data.get("awaitingPcGroupRoll", False):
           gate_result = _handle_group_initiative_gate(cmd, encounter_data, multi_pc_manager, party_tracker_data)

           if not gate_result["handled"]:
               # Invalid or non-/init input: print guidance and continue
               if gate_result["error_message"]:
                   print(gate_result["error_message"])
                   import sys
                   sys.stdout.flush()
               continue

           # Valid /init processed
           # Update encounter state from helper
           encounter_data.update(gate_result["encounter_updates"])

           # Apply manager phase state based on winner
           if gate_result["winner"] == "pcGroup":
               multi_pc_manager.pc_phase_complete = False
           else:
               multi_pc_manager.pc_phase_complete = True

           # Log marker state change
           if gate_result["marker_enabled"]:
               debug(
                   "PHASE_MARKER: Set openingEnemyBatchPending=True via /init dmGroup path",
                   category="combat_events"
               )
           else:
               debug(
                   "PHASE_MARKER: Cleared openingEnemyBatchPending via /init pcGroup path",
                   category="combat_events"
               )

           save_json_file(json_file_path, encounter_data)

           # TABLETOP MODE: C3.3 - Sync compatibility mirror after /init resolution
           party_tracker_data.setdefault("worldConditions", {})["combatInitiative"] = gate_result["mirror_payload"]
           save_json_file("party_tracker.json", party_tracker_data)

           debug(
               f"INITIATIVE: Received /init {gate_result['pc_group_roll']}. "
               f"DM_GROUP={gate_result['dm_group_roll']}, winner={gate_result['winner']}, "
               f"phase={gate_result['phase_label']}",
               category="combat_events"
           )
           phase_label_display = str(gate_result.get("phase_label", "")).replace("_", " ")
           print(
               f"Dungeon Master: [SYSTEM] Initiative locked. "
               f"DM GROUP {gate_result['dm_group_roll']} vs PC GROUP {gate_result['pc_group_roll']}. "
               f"Starting {phase_label_display}."
           )
           import sys
           sys.stdout.flush()

           if gate_result["winner"] == "pcGroup":
               active_pc_name = (
                   multi_pc_manager.current_pc_name
                   or party_tracker_data.get("active_character")
                   or "the active PC"
               )
               print(
                   f"Dungeon Master: Your party has the initiative and strikes first, "
                   f"what does {active_pc_name} do?"
               )
               sys.stdout.flush()
               # Wait for the facilitator's first PC action.
               continue

           # DM group starts: inject explicit enemy-phase trigger and fall through to AI.
           pending_enemies = multi_pc_manager.get_remaining_enemies_for_round()
           pending_list_str = ", ".join(pending_enemies) if pending_enemies else "all remaining enemies/NPCs"
           system_msg = (
               "System: Initiative resolved. DM_GROUP won the opening phase. PROCEED TO ENEMY PHASE.\n"
               f"Turn Order: {pending_list_str}.\n"
               "INSTRUCTIONS: Generate actions for exactly these combatants in order. Once they have acted, STOP.\n"
               "If this ends the round, increment 'combat_round' in your JSON, but DO NOT narrate the start of the next round."
           )
           conversation_history.append({"role": "user", "content": system_msg})
           save_json_file(conversation_history_file, conversation_history)
           user_input_text = "Enemies turn."
        
        # ----------------------------------------------------------------------
        # TABLETOP MODE: Fast Lane Command Processing
        # ----------------------------------------------------------------------
       # Handle PC Focus Switch (from UI Tab Click)
       if cmd == "/switch_pc_focus":
           debug("SWITCH: Detected PC switch command, refreshing loop", category="combat_events")
           # Immediately continue to next loop iteration
           # This reloads party_tracker.json (updated by UI), gets the new active PC,
           # and generates a fresh prompt for the new character WITHOUT calling AI.
           continue
       
       # Handle explicit END command to FORCE enemy phase (User Request: Manual Control)
       if multi_pc_manager and cmd in ["/end", "/pass", "end turn", "end"]:
           debug("TURN_END: Detected explicit force enemy phase command", category="combat_events")
           print(f"DEBUG: Forcing Enemy Phase per user request (Active: {multi_pc_manager.current_pc_name})")
           
           # 1. Ensure we have the correct PC selected (handle case sensitivity/whitespace)
           target_pc = input_actor_name or multi_pc_manager.current_pc_name or party_tracker_data.get("active_character")
           if target_pc:
               multi_pc_manager.set_current_pc(target_pc)

           # 2. Mark ALL PCs as acted to ensure the prompt context reflects that the PC phase is over.
           # This prevents the AI from seeing "PCs who can still act" and refusing to proceed.
           multi_pc_manager.force_end_pc_phase()
           
           # 3. Force the transition immediately
           debug("TURN_END: Forcing enemy phase injection", category="combat_events")
           print("DEBUG: Triggering Enemy Phase Transition...")
           
           # Get explicit list of pending enemies to guide the AI
           pending_enemies = multi_pc_manager.get_remaining_enemies_for_round()
           pending_list_str = ", ".join(pending_enemies) if pending_enemies else "all remaining enemies/NPCs"
           
           # Inject system message to force AI to process enemies with explicit targets
           system_msg = (
               f"System: Player has manually ended the PC Phase. PROCEED TO ENEMY PHASE.\n"
               f"Turn Order: {pending_list_str}.\n"
               "INSTRUCTIONS: Generate actions for exactly these combatants in order. Once they have acted, STOP.\n"
               "If this ends the round, increment 'combat_round' in your JSON, but DO NOT narrate the start of the next round."
           )
           conversation_history.append({"role": "user", "content": system_msg})
           save_json_file(conversation_history_file, conversation_history)
           
           # Override user input to ensure AI understands the transition
           user_input_text = "Enemies turn."
           
           # Fall through to allow the AI to generate the enemy turn narration
           # We DO NOT continue/loop here; we proceed to AI generation.

       # MOVED UP: Processing this BEFORE generating prompt state to ensure
       # the LLM sees the *result* of the command (e.g. updated HP)
       
       fast_lane_action_occurred = False # Track if a Fast Lane command implies an action
       
       if multi_pc_manager:
           # Pass the actor name (either forced from tag or current active) to the handler
           actor_for_log = input_actor_name if input_actor_name else (multi_pc_manager.current_pc_name or "Player")
           feedback, log_msg = multi_pc_manager.handle_combat_command(clean_input, encounter_data, actor_name=actor_for_log)
           
           if feedback:
               # Show feedback to user (e.g., "(DM): Hit! Roll damage.")
               print(feedback)
               import sys
               sys.stdout.flush()
               
           if log_msg:
               # Inject log message silently for the LLM
               conversation_history.append({"role": "user", "content": log_msg})
               save_json_file(conversation_history_file, conversation_history)
               debug(f"[COMBAT_MANAGER] Injected system log: {log_msg}", category="combat_events")

               # TABLETOP MODE: Persist latest encounter state after fast-lane command logs.
               # This prevents stale on-disk encounter data from overwriting immediate
               # /dmg HP/status changes before the next LLM updateEncounter call.
               if encounter_id and encounter_data:
                   if not safe_write_json(f"modules/encounters/encounter_{encounter_id}.json", encounter_data):
                       warning(
                           "STATE_PERSIST: Failed to persist fast-lane encounter state",
                           category="combat_events"
                       )
                   else:
                       debug(
                           "STATE_PERSIST: Fast-lane encounter state persisted",
                           category="combat_events"
                       )
               
               # NOTE: We do NOT set fast_lane_action_occurred = True here anymore.
               # Auto-advancing breaks Multiattack. The user must manually end turn or rely on LLM logic.
               # fast_lane_action_occurred = True 
               
           # Control Flow:
           # 1. Feedback ONLY (e.g. /att hit) -> Skip LLM, wait for next input
           # 2. Log ONLY (e.g. /dmg or /att miss) -> Proceed to LLM (it needs to narrate)
           # 3. Both -> Proceed to LLM
           # 4. Neither -> Continue to standard handling
           
           if feedback and not log_msg:
               # User needs to provide more input (e.g., damage roll)
               continue
               
           # If log_msg exists, we fall through to the LLM call below
           # The LLM will see the log_msg in the history and narrate accordingly.
       
       # ----------------------------------------------------------------------

           if cmd in ["/help", "\\help"]:
               help_msg = (
                   "[skipTTS] Dungeon Master: [SYSTEM] Available Combat Commands:\n"
                   "  /stats      - View full character stats\n"
                   "  /hp [val]   - Combat Heal (positive) or damage (negative)\n"
                   "  /att [target] [roll] [weapon] - Attack a target\n"
                   "  /dmg [val]  - Apply damage\n"
                   "  /init [1-20] - Set PC group initiative roll\n"
                   "  /end        - End PC combat turn\n"
                   "  /end_combat - Force end the current combat encounter\n"
                   "  /save       - Save current game state\n"
                   "  /quit       - Exit the game\n"
                   "  /help       - Show this help message\n"
                   "[SYSTEM] Reference Guides:\n"
                   "  - NEQ Quick Reference Guide: /static/docs/NEQ_Quick_Reference_Guide.pdf\n"
                   "  - 5e Cheat Sheet: /static/docs/5E_Actions_Cheat_Sheet.pdf\n"
                   "  - 5e Rules on a Page: /static/docs/5E_Rules_On_A_Page.pdf\n"
                   "  - 5e Basic Rules: https://www.dndbeyond.com/sources/dnd/basic-rules-2014"
               )
               print(help_msg)
               # Force flush to ensure it reaches the web interface immediately
               import sys
               sys.stdout.flush()
               continue

       # --- Character Info Commands ---
       
       if cmd.startswith("/stats"):
           try:
               # Get active character
               pt_data = safe_json_load("party_tracker.json")
               char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
               char_path = path_manager.get_character_path(normalize_character_name(char_name))
               char_data = safe_json_load(char_path)
               
               if char_data:
                   stats_msg = f"Dungeon Master: [SYSTEM] Stats for {char_name}:\n"
                   stats_msg += f"  Level: {char_data.get('level', 1)} | XP: {char_data.get('experience_points', 0)}\n"
                   stats_msg += f"  HP: {char_data.get('hitPoints', 0)}/{char_data.get('maxHitPoints', 0)} | AC: {char_data.get('armorClass', 10)}\n"
                   stats_msg += f"  Speed: {char_data.get('speed', 30)} | Init: {char_data.get('initiative', 0)}\n"
                   
                   abilities = char_data.get('abilities', {})
                   stats_msg += f"  STR: {abilities.get('strength', 10)} | DEX: {abilities.get('dexterity', 10)} | CON: {abilities.get('constitution', 10)}\n"
                   stats_msg += f"  INT: {abilities.get('intelligence', 10)} | WIS: {abilities.get('wisdom', 10)} | CHA: {abilities.get('charisma', 10)}\n"
                   
                   print(stats_msg)
                   import sys
                   sys.stdout.flush()
               else:
                   print(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}")
                   import sys
                   sys.stdout.flush()
           except Exception as e:
               print(f"Dungeon Master: [SYSTEM] Error showing stats: {e}")
               import sys
               sys.stdout.flush()
           continue

       if cmd.startswith("/hp"):
           try:
               parts = cmd.split()
               if len(parts) < 2:
                   print("Dungeon Master: [SYSTEM] Usage: /hp [amount]")
                   import sys; sys.stdout.flush()
                   continue
               
               amount = int(parts[1])
               
               # Get active character
               pt_data = safe_json_load("party_tracker.json")
               char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
               char_path = path_manager.get_character_path(normalize_character_name(char_name))
               char_data = safe_json_load(char_path)
               
               if char_data:
                   current_hp = char_data.get('hitPoints', 0)
                   max_hp = char_data.get('maxHitPoints', 0)
                   new_hp = max(0, min(max_hp, current_hp + amount))
                   char_data['hitPoints'] = new_hp
                   
                   safe_write_json(char_path, char_data)
                   
                   action_str = "healed" if amount >= 0 else "damaged"
                   msg = f"Dungeon Master: [SYSTEM] {char_name} {action_str} by {abs(amount)}. HP: {current_hp} -> {new_hp}/{max_hp}"
                   print(msg)
                   import sys; sys.stdout.flush()
                   
                   # Force sync to update combat state immediately
                   sync_active_encounter()
                   
               else:
                   print(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}")
                   import sys; sys.stdout.flush()
           except ValueError:
               print("Dungeon Master: [SYSTEM] Usage: /hp [amount] (must be a number)")
               import sys; sys.stdout.flush()
           except Exception as e:
               print(f"Dungeon Master: [SYSTEM] Error updating HP: {e}")
               import sys; sys.stdout.flush()
           continue

       if cmd.startswith("/xp"):
           try:
               parts = cmd.split()
               if len(parts) < 2:
                   print("Dungeon Master: [SYSTEM] Usage: /xp [amount]")
                   import sys; sys.stdout.flush()
                   continue
               
               amount = int(parts[1])
               
               # Get active character
               pt_data = safe_json_load("party_tracker.json")
               char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
               char_path = path_manager.get_character_path(normalize_character_name(char_name))
               char_data = safe_json_load(char_path)
               
               if char_data:
                   current_xp = char_data.get('experience_points', 0)
                   new_xp = max(0, current_xp + amount)
                   char_data['experience_points'] = new_xp
                   
                   safe_write_json(char_path, char_data)
                   
                   msg = f"Dungeon Master: [SYSTEM] {char_name} gained {amount} XP. Total: {current_xp} -> {new_xp}"
                   print(msg)
                   import sys; sys.stdout.flush()
               else:
                   print(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}")
                   import sys; sys.stdout.flush()
           except ValueError:
               print("Dungeon Master: [SYSTEM] Usage: /xp [amount] (must be a number)")
               import sys; sys.stdout.flush()
           except Exception as e:
               print(f"Dungeon Master: [SYSTEM] Error updating XP: {e}")
               import sys; sys.stdout.flush()
           continue

       if cmd.startswith("/level"):
           try:
               parts = cmd.split()
               if len(parts) < 2:
                   print("Dungeon Master: [SYSTEM] Usage: /level [number]")
                   import sys; sys.stdout.flush()
                   continue
               
               level = int(parts[1])
               
               # Get active character
               pt_data = safe_json_load("party_tracker.json")
               char_name = pt_data.get("active_character") or pt_data.get("partyMembers", [])[0]
               char_path = path_manager.get_character_path(normalize_character_name(char_name))
               char_data = safe_json_load(char_path)
               
               if char_data:
                   current_level = char_data.get('level', 1)
                   char_data['level'] = level
                   
                   safe_write_json(char_path, char_data)
                   
                   msg = f"Dungeon Master: [SYSTEM] {char_name} level set to {level} (was {current_level})"
                   print(msg)
                   import sys; sys.stdout.flush()
               else:
                   print(f"Dungeon Master: [SYSTEM] Error: Could not load data for {char_name}")
                   import sys; sys.stdout.flush()
           except ValueError:
               print("Dungeon Master: [SYSTEM] Usage: /level [number] (must be a number)")
               import sys; sys.stdout.flush()
           except Exception as e:
               print(f"Dungeon Master: [SYSTEM] Error updating level: {e}")
               import sys; sys.stdout.flush()
           continue
           
       if cmd in ["/save", "\\save"]:
           try:
               from updates.save_game_manager import SaveGameManager
               manager = SaveGameManager()
               success, message = manager.create_save_game(f"Combat Save - Round {current_round}", "essential")
               print(f"[SYSTEM] {message}")
           except Exception as e:
               print(f"[ERROR] Save failed: {e}")
           continue

       if cmd in ["/quit", "\\quit", "/exit", "\\exit"]:
           print("[SYSTEM] Exiting game...")
           sys.exit(0)

       # Check for force end combat command
       if cmd in ["\\end_combat", "/end_combat", "exit combat"]:
           print("[COMBAT_MANAGER] FORCE END: User requested immediate combat termination.")
           debug("STATE_CHANGE: User triggered force end combat", category="combat_events")
           
           # Add marker to conversation history
           conversation_history.append({"role": "user", "content": "Dungeon Master Note: Combat has been forcefully ended by the user."})
           
           # Store the encounter ID before clearing it
           last_encounter_id = party_tracker_data.get("worldConditions", {}).get("activeCombatEncounter", "")
           
           # Generate summary
           info("AI_CALL: Generating final combat summary (Force End)...", category="ai_operations")
           dialogue_summary_result = summarize_dialogue(conversation_history, location_info, party_tracker_data)
           
           # Clear active encounter
           if 'worldConditions' in party_tracker_data and 'activeCombatEncounter' in party_tracker_data['worldConditions']:
               if last_encounter_id:
                   party_tracker_data["worldConditions"]["lastCompletedEncounter"] = last_encounter_id
               party_tracker_data['worldConditions']['activeCombatEncounter'] = ""
               debug(f"STATE_CHANGE: Cleared active combat encounter. Last completed is now {last_encounter_id}", category="combat_events")
               safe_write_json("party_tracker.json", party_tracker_data)
           
           # Save logs
           info("FILE_OP: Saving final combat chat history log...", category="combat_logs")
           generate_chat_history(conversation_history, encounter_id)
           
           # Reload player info
           player_info = safe_json_load(player_file)

           info("SUCCESS: Combat complete. Exiting simulation.", category="combat_events")
           return dialogue_summary_result, player_info
       
       # Enhance player input with inventory context for combat
       try:
           # Load fresh player data for inventory
           player_file = path_manager.get_character_path(normalize_character_name(player_name_display))
           fresh_player_data = safe_json_load(player_file)
           
           # Enhance the input with inventory context (combat mode)
           user_input_text = enhance_player_input_with_inventory(
               user_input_text,
               fresh_player_data,  # character_data
               party_tracker_data,  # party_tracker_data
               None,  # characters_data not needed
               in_combat=True  # This is combat context
           )
           debug(f"COMBAT_LOOP: Enhanced player input with inventory context", category="combat_events")
       except Exception as e:
           debug(f"COMBAT_LOOP: Failed to enhance input with inventory context: {e}", category="combat_events")
           # Continue with unenhanced input if enhancement fails
       
       # Prepare dynamic state info for all creatures - compact format
       dynamic_state_parts = []
       user_controlled_parts = []
       dm_controlled_parts = []
       enemy_parts = []
       
       # Player info - ALWAYS reload from character file for current HP (source of truth)
       player_file = path_manager.get_character_path(normalize_character_name(player_name_display))
       try:
           fresh_player_data = safe_json_load(player_file)
           if fresh_player_data:
               # Use fresh data from character file
               current_hp = fresh_player_data.get("hitPoints", 0)
               max_hp = fresh_player_data.get("maxHitPoints", 0)
               player_status = fresh_player_data.get("status", "alive")
               player_condition = fresh_player_data.get("condition", "none")
               player_conditions = fresh_player_data.get("condition_affected", [])
               # Also update spell slots from fresh data
               player_info["spellcasting"] = fresh_player_data.get("spellcasting", {})
           else:
               # Fallback to stale data if load fails
               player_status = player_info.get("status", "alive")
               player_condition = player_info.get("condition", "none")
               player_conditions = player_info.get("condition_affected", [])
       except Exception as e:
           error(f"Failed to reload player data for CREATURE STATES", exception=e, category="combat_events")
           # Fallback to stale data
           player_status = player_info.get("status", "alive")
           player_condition = player_info.get("condition", "none")
           player_conditions = player_info.get("condition_affected", [])
       
       # Extract class features from player
       class_features_names = []
       if fresh_player_data:
           class_features = fresh_player_data.get("classFeatures", [])
           class_features_names = [f.get("name", "") for f in class_features if f.get("name")]
       
       # Build compact state line
       state_line = f"{player_name_display}: HP {current_hp}/{max_hp}, {player_status}"
       if class_features_names:
           state_line += f", Class Features: {', '.join(class_features_names)}"
       if player_condition != "none":
           state_line += f", {player_condition}"
       if player_conditions:
           state_line += f", conditions: {','.join(player_conditions)}"
       
       # Add spell slots inline if player has spellcasting
       spellcasting = player_info.get("spellcasting", {})
       if spellcasting and "spellSlots" in spellcasting:
           spell_slots = spellcasting["spellSlots"]
           slot_parts = []
           for level in range(1, 10):  # Spell levels 1-9
               level_key = f"level{level}"
               if level_key in spell_slots:
                   slot_data = spell_slots[level_key]
                   current_slots = slot_data.get("current", 0)
                   max_slots = slot_data.get("max", 0)
                   if max_slots > 0:  # Only show levels with available slots
                       slot_parts.append(f"L{level}:{current_slots}/{max_slots}")
           if slot_parts:
               state_line += f", Spell Slots: {' '.join(slot_parts)}"
       
       user_controlled_parts.append(state_line)
       
       # Creature info
       for creature in encounter_data["creatures"]:
           if creature["type"] != "player":
               creature_name = creature.get("name", "Unknown Creature")
               creature_hp = creature.get("currentHitPoints", "Unknown")
               creature_status = creature.get("status", "alive")
               creature_condition = creature.get("condition", "none")
               
               # Get the actual max HP from the correct source
               npc_data = None
               if creature["type"] == "npc":
                   # For NPCs, look up their true max HP from their character file using fuzzy match
                   npc_data, matched_filename = load_npc_with_fuzzy_match(creature_name, path_manager)
                   if npc_data:
                       creature_max_hp = npc_data["maxHitPoints"]
                   else:
                       error(f"FAILURE: Failed to get correct max HP for {creature_name}", category="combat_events")
                       creature_max_hp = creature.get("maxHitPoints", "Unknown")
               else:
                   # For monsters, use the encounter data
                   creature_max_hp = creature.get("maxHitPoints", "Unknown")
               
               # Build compact creature state line
               creature_line = f"{creature_name}: HP {creature_hp}/{creature_max_hp}, {creature_status}"
               
               # Add class features for NPCs (party members might have important abilities)
               if creature["type"] == "npc" and npc_data:
                   npc_class_features = npc_data.get("classFeatures", [])
                   if npc_class_features:
                       npc_features_names = [f.get("name", "") for f in npc_class_features if f.get("name")]
                       if npc_features_names:
                           creature_line += f", Class Features: {', '.join(npc_features_names)}"
               
               if creature_condition != "none":
                   creature_line += f", {creature_condition}"
               
               # Add spell slot information inline for NPCs if they have spellcasting
               if creature["type"] == "npc" and npc_data:
                   npc_spellcasting = npc_data.get("spellcasting", {})
                   if npc_spellcasting and "spellSlots" in npc_spellcasting:
                       npc_spell_slots = npc_spellcasting["spellSlots"]
                       npc_slot_parts = []
                       for level in range(1, 10):  # Spell levels 1-9
                           level_key = f"level{level}"
                           if level_key in npc_spell_slots:
                               slot_data = npc_spell_slots[level_key]
                               current_slots = slot_data.get("current", 0)
                               max_slots = slot_data.get("max", 0)
                               if max_slots > 0:  # Only show levels with available slots
                                   npc_slot_parts.append(f"L{level}:{current_slots}/{max_slots}")
                       if npc_slot_parts:
                           creature_line += f", Spell Slots: {' '.join(npc_slot_parts)}"
               
               # Group by control type
               if creature["type"] == "npc":
                   dm_controlled_parts.append(creature_line)
               elif creature["type"] == "enemy":
                   enemy_parts.append(creature_line)
               else:
                   # Fallback for any other types
                   dm_controlled_parts.append(creature_line)
       
       # Build the labeled sections
       if user_controlled_parts:
           dynamic_state_parts.append("Active Player Characters (User Controlled):")
           dynamic_state_parts.extend([f"  {p}" for p in user_controlled_parts])
       
       if dm_controlled_parts:
           dynamic_state_parts.append("Accompanied by Party NPCs (DM Controlled):")
           dynamic_state_parts.extend([f"  {p}" for p in dm_controlled_parts])
           
       if enemy_parts:
           dynamic_state_parts.append("Enemies (DM Controlled):")
           dynamic_state_parts.extend([f"  {p}" for p in enemy_parts])
       
       all_dynamic_state = "\n".join(dynamic_state_parts)

       # TABLETOP MODE: C4.2/C4.3 - Include active multi-PC roster so PCs are valid targets
       roster_entries = _collect_authoritative_combat_roster(
           encounter_data,
           multi_pc_manager=multi_pc_manager,
           party_tracker_data=party_tracker_data,
       )
       roster_list = [f"- {entry['name']} ({entry['type']})" for entry in roster_entries]
       roster_str = "\n".join(roster_list) if roster_list else "- None"
       all_dynamic_state += (
           f"\n\n++ VALID TARGETS & ACTORS (IMMUTABLE) ++\n{roster_str}\n"
           "RULES: This is the definitive list of all beings in the scene. "
           "Do NOT narrate actions for anyone not on this list. "
           "During ENEMY_PHASE, PCs remain forbidden as actors but are valid targets."
       )
       
       # Check if we need new prerolls based on round progression
       # Use combat_round as primary, fall back to current_round
       current_round = encounter_data.get('combat_round', encounter_data.get('current_round', 1))
       cached_round = encounter_data.get('preroll_cache', {}).get('round', 0)
       
       if current_round > cached_round:
           # Generate fresh prerolls for new round
           preroll_text = generate_prerolls(encounter_data, round_num=current_round)
           encounter_data['preroll_cache'] = {
               'round': current_round,
               'rolls': preroll_text,
               'preroll_id': f"{current_round}-{random.randint(1000,9999)}"
           }
           # Save the encounter data with preroll cache to disk
           save_json_file(json_file_path, encounter_data)
           debug(f"STATE_CHANGE: Generated new prerolls for round {current_round}", category="combat_events")
       else:
           # Use cached prerolls for current round
           preroll_text = encounter_data.get('preroll_cache', {}).get('rolls', '')
           if preroll_text:
               preroll_id = encounter_data.get('preroll_cache', {}).get('preroll_id', 'unknown')
               debug(f"STATE_CHANGE: Reusing cached prerolls for round {current_round} (ID: {preroll_id})", category="combat_events")
           else:
               # Fallback if cache missing
               preroll_text = generate_prerolls(encounter_data, round_num=current_round)
               encounter_data['preroll_cache'] = {
                   'round': current_round,
                   'rolls': preroll_text,
                   'preroll_id': f"{current_round}-{random.randint(1000,9999)}"
               }
               # Save the encounter data with preroll cache to disk
               save_json_file(json_file_path, encounter_data)
               debug(f"STATE_CHANGE: Generated fallback prerolls for round {current_round}", category="combat_events")
        
       # Generate initiative order for validation context
       # MULTI-PC MODE: Use deterministic multi_pc_manager tracker instead of AI tracker
       live_tracker = None
       turn_window_json = None
       initiative_display = None

       if multi_pc_manager:
           # Use deterministic multi-PC tracker (bypasses AI tracker which has single-PC limitation)
           debug("MULTI_PC_TRACKER: Using deterministic multi-PC initiative tracker", category="combat_events")
           try:
               live_tracker = multi_pc_manager.format_initiative_tracker(encounter_data)
               if live_tracker:
                   debug("MULTI_PC_TRACKER: Successfully generated initiative tracker", category="combat_events")
                   # Parse the tracker output for JSON metadata
                   json_start = live_tracker.find("```json")
                   if json_start != -1:
                       initiative_display = live_tracker[:json_start].strip()
                       json_end = live_tracker.find("```", json_start + 7)
                       if json_end != -1:
                           json_str = live_tracker[json_start + 7:json_end].strip()
                           try:
                               turn_window_json = json.loads(json_str)
                               debug(f"MULTI_PC_TRACKER: Extracted turn window: {turn_window_json.get('turn_window', [])}", category="combat_events")
                           except json.JSONDecodeError as e:
                               debug(f"MULTI_PC_TRACKER: Failed to parse JSON metadata: {e}", category="combat_events")
                   else:
                       initiative_display = live_tracker
           except Exception as e:
               debug(f"MULTI_PC_TRACKER: Failed to generate tracker: {e}", category="combat_events")
       
       # FALLBACK: Use AI tracker only if multi-PC tracker not available or failed
       if not live_tracker:
           try:
               from .initiative_tracker_ai import generate_live_initiative_tracker
               # Get recent conversation for analysis (last 6 messages - enough for current round context)
               recent_conversation = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
               live_tracker = generate_live_initiative_tracker(encounter_data, recent_conversation, current_round)
               if live_tracker:
                   debug("AI_TRACKER: Successfully generated live initiative tracker", category="combat_events")
                   # Parse the tracker output for both markdown and JSON
                   json_start = live_tracker.find("```json")
                   if json_start != -1:
                       initiative_display = live_tracker[:json_start].strip()
                       json_end = live_tracker.find("```", json_start + 7)
                       if json_end != -1:
                           json_str = live_tracker[json_start + 7:json_end].strip()
                           try:
                               turn_window_json = json.loads(json_str)
                               debug(f"AI_TRACKER: Extracted turn window: {turn_window_json.get('turn_window', [])}", category="combat_events")
                           except json.JSONDecodeError as e:
                               debug(f"AI_TRACKER: Failed to parse JSON metadata: {e}", category="combat_events")
                   else:
                       initiative_display = live_tracker
           except Exception as e:
               debug(f"AI_TRACKER: Failed to generate live tracker: {e}", category="combat_events")
       
       # Validate that we have a tracker
       if not live_tracker:
           error("INITIATIVE_TRACKER: Failed to generate initiative tracker - combat cannot proceed properly", category="combat_events")
           return None, None  # Exit early if tracker fails
       
       # Get the player's name from encounter data or turn_window JSON
       player_character_name = None
       if turn_window_json and "player_name" in turn_window_json:
           player_character_name = turn_window_json["player_name"]
       else:
           for creature in encounter_data["creatures"]:
               if creature["type"] == "player":
                   player_character_name = creature["name"]
                   break
       
       # Create a structured, machine-friendly prompt format
       # DON'T add (player) markers - the tracker handles this properly now
       marked_initiative_display = initiative_display
       
       # Extract current turn from initiative display if available
       current_turn_marker = "[>]"
       current_turn_line = ""
       if current_turn_marker in marked_initiative_display:
           for line in marked_initiative_display.split('\n'):
               if current_turn_marker in line:
                   current_turn_line = line.strip()
                   break
       
       # Build turn window info if available
       turn_window_text = ""
       if turn_window_json:
           turn_window_text = f"""
--- TURN WINDOW ---
process_until: {turn_window_json.get('process_until', 'unknown')}
turn_window: {json.dumps(turn_window_json.get('turn_window', []))}
"""
       
       # Generate AC block from encounter data
       ac_block = ""
       ac_values = {}
       
       # First pass: Get AC from encounter data
       for creature in encounter_data.get('creatures', []):
           name = creature.get('name')
           ac = creature.get('armorClass')
           
           if name and ac is not None:
               ac_values[name] = ac
           elif name and creature.get('type') == 'enemy':
               # Try to get AC from monster file
               monster_type = creature.get('monsterType', '').lower()
               if monster_type:
                   try:
                       path_manager = ModulePathManager(party_tracker_data.get("module", "").replace(" ", "_"))
                       monster_file = path_manager.get_monster_path(monster_type)
                       
                       if os.path.exists(monster_file):
                           monster_data = safe_json_load(monster_file)
                           if monster_data and 'armorClass' in monster_data:
                               ac_values[name] = monster_data['armorClass']
                   except:
                       # Silently skip if we can't load the monster file
                       pass
       
       # Build the AC block if we have values
       if ac_values:
           ac_block = "=== ARMOR CLASS (AC) ===\n"
           # Sort creatures by initiative (highest first)
           sorted_creatures = sorted(
               encounter_data.get('creatures', []), 
               key=lambda x: x.get('initiative', 0), 
               reverse=True
           )
           
           for creature in sorted_creatures:
               name = creature.get('name')
               if name in ac_values:
                   ac_block += f"{name}: {ac_values[name]}\n"
           ac_block += "\n"
       
       # BUG FIX: check_all_monsters_defeated() used wrong field names since
       # upstream commit 9b77d91 ('combatants' vs 'creatures', 'hitPoints' vs
       # 'currentHitPoints'). Encounter schema uses 'creatures'/'currentHitPoints'.
       # This fix also adds status check for robustness (matches xp.py logic).
       def check_all_monsters_defeated(encounter):
           """Check if all enemies have 0 or negative HP or defeated status"""
           if not encounter or 'creatures' not in encounter:
               return False

           has_enemies = False
           all_defeated = True

           for creature in encounter['creatures']:
               # Check if this is an enemy (not player or allied NPC)
               if creature.get('type') == 'enemy':
                   has_enemies = True
                   current_hp = creature.get('currentHitPoints', 0)
                   status = creature.get('status', 'alive').lower()
                   # Defeated if HP <= 0 OR status indicates defeat
                   if current_hp > 0 and status not in ('dead', 'defeated', 'unconscious'):
                       all_defeated = False
                       break

           # Only return True if there were enemies and all are defeated
           return has_enemies and all_defeated
       
       # Determine the required response based on combat state
       all_monsters_defeated = check_all_monsters_defeated(encounter_data)
       if all_monsters_defeated:
           debug("COMBAT_AUTO_EXIT: All monsters defeated, modifying required response", category="combat_events")
           print("[COMBAT_MANAGER] Auto-detecting combat end: All enemies defeated")
           required_response = """--- REQUIRED RESPONSE ---
All monsters have been defeated. Pass the exit action to end combat:
1. Return structured JSON with plan, narration, combat_round, and actions
2. Include exit action with encounterId and reason: 'All enemies defeated'"""
       elif multi_pc_manager:
           # Get current actor from the authoritative turn queue
           current_actor = multi_pc_manager.get_current_actor()
           
           # Use the dedicated MultiPC Prompt Generator (Plugin Architecture)
           # This encapsulates the Strict Turn Isolation logic outside this file
           required_response = multi_pc_manager.get_required_response_prompt()
           debug(f"PROMPT_LOGIC: Generated Multi-PC response requirement for {current_actor.name if current_actor else 'Unknown'}", category="combat_events")

       else:
           required_response = """--- REQUIRED RESPONSE ---
1. Narrate and resolve actions for all NPCs/monsters in initiative order until:
   - The LAST creature in this round has acted, OR
   - Initiative returns to the player
2. Stop narration at that point
3. Return structured JSON with plan, narration, combat_round, and actions"""
       
       # TABLETOP MODE: Inject multi-PC turn summary and active PC context
       multi_pc_context = ""
       if multi_pc_manager:
           active_pc = multi_pc_manager.current_pc_name

           initiative_mode = encounter_data.get("initiativeMode", "two_group_phase1")
           initiative_rolls = encounter_data.get("initiativeRolls", {})
           dm_group_roll = initiative_rolls.get("dmGroup", "pending")
           pc_group_roll = initiative_rolls.get("pcGroup", "pending")
           initiative_winner = encounter_data.get("initiativeWinner", "pending")
           round_starts_with = encounter_data.get("roundStartsWith", initiative_winner)
           
           # Get explicit phase state
           current_phase = multi_pc_manager.combat_phase
           pending_enemies = multi_pc_manager.get_remaining_enemies_for_round()
           pending_str = ", ".join(pending_enemies) if pending_enemies else "None"
           
           multi_pc_context = f"""
=== INITIATIVE STATE ===
MODE: {initiative_mode}
DM_GROUP_ROLL: {dm_group_roll}
PC_GROUP_ROLL: {pc_group_roll}
WINNER: {initiative_winner}
ROUND_STARTS_WITH: {round_starts_with}

=== COMBAT PHASE STATE ===
CURRENT_PHASE: {current_phase}
PC_PHASE_COMPLETE: {multi_pc_manager.pc_phase_complete}
PENDING_ENEMIES: [{pending_str}]
DETERMINISM: In {current_phase}, ONLY the specified actors have authority to act.

--- MULTI-PC COMBAT STATUS ---
{multi_pc_manager.format_party_turn_summary()}

{multi_pc_manager.format_pc_context_for_prompt(active_pc)}
"""

       # The tracker now always provides properly formatted output with ROUND INFO
       # Don't duplicate sections - use the tracker output as-is
       user_input_with_note = f"""{marked_initiative_display}

--- CREATURE STATES ---
{all_dynamic_state}

{ac_block}
{multi_pc_context}
--- DICE POOLS ---
Rules:
- Player characters always roll their own dice
- NPCs/monsters use pre-rolled dice pools exactly
- Do not reuse dice; consume in order
- For NPC/Monster ATTACK: use CREATURE ATTACKS list
- For NPC/Monster SAVES: use SAVING THROWS list  
- For damage/spells/other: use GENERIC DICE pool

{preroll_text}

--- RULES ---
- Initiative must be followed strictly
- Only increment combat_round after all alive creatures have acted
- Status updates must be reflected in JSON "actions"
- Do not narrate beyond current round

--- PLAYER ACTION ---
{user_input_text}

{required_response}"""
       
       # Clean old DM notes and combat state blocks before adding new user input
       conversation_history = clean_old_dm_notes(conversation_history)
       conversation_history = clean_combat_state_blocks(conversation_history)
       
       # Add user input to conversation history
       conversation_history.append({"role": "user", "content": user_input_with_note})
       save_json_file(conversation_history_file, conversation_history)
       
       # Get AI response with validation and retries
       max_retries = 5
       valid_response = False
       ai_response = None
       validation_attempts = []  # Store all validation attempts for logging
       initial_conversation_length = len(conversation_history)  # Mark where validation started
       retry_feedback_note = None

       for attempt in range(max_retries):
           try:
               print(f"[COMBAT_MANAGER] Making AI call for player action (attempt {attempt + 1}/{max_retries})")
               print(f"[COMBAT_MANAGER] Processing player input: {user_input_text[:50]}..." if len(user_input_text) > 50 else f"[COMBAT_MANAGER] Processing player input: {user_input_text}")

               retry_request_history = list(conversation_history)
               if retry_feedback_note:
                   retry_request_history.append({
                       "role": "user",
                       "content": retry_feedback_note,
                   })

               # Update status to show AI is processing
               try:
                   from core.managers.status_manager import status_manager
                   status_manager.update_status("Combat AI processing your action...", is_processing=True)
               except Exception as e:
                   debug(f"Could not update status: {e}", category="status")

               # Import GPT-5 config
               from config import USE_GPT5_MODELS, GPT5_MINI_MODEL, GPT5_USE_HIGH_REASONING_ON_RETRY

               if USE_GPT5_MODELS:
                   # GPT-5: Always use mini model, but increase reasoning effort after first failure
                   combat_model = GPT5_MINI_MODEL

                   # After first failure, use high reasoning effort
                   if attempt >= 1 and GPT5_USE_HIGH_REASONING_ON_RETRY:
                       print(f"DEBUG: [COMBAT] GPT-5 - Using HIGH reasoning effort after {attempt} attempts")
                       messages_to_send = combat_message_compressor.process_combat_conversation(retry_request_history)

                       # Export compressed conversation for review
                       with open("combat_messages_to_api.json", "w", encoding="utf-8") as f:
                           json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
                       print(f"DEBUG: [COMBAT] Exported compressed messages to combat_messages_to_api.json")

                       response = client.chat.completions.create(
                           model=combat_model,
                           messages=messages_to_send,
                           reasoning={"effort": "high"}
                       )
                   else:
                       # Default is medium reasoning (no need to specify)
                       print(f"DEBUG: [COMBAT] Using GPT-5 model: {combat_model} (default medium reasoning)")
                       messages_to_send = combat_message_compressor.process_combat_conversation(retry_request_history)

                       # Export compressed conversation for review
                       with open("combat_messages_to_api.json", "w", encoding="utf-8") as f:
                           json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
                       print(f"DEBUG: [COMBAT] Exported compressed messages to combat_messages_to_api.json")

                       response = client.chat.completions.create(
                           model=combat_model,
                           messages=messages_to_send
                       )
               else:
                   # GPT-4.1: Keep existing temperature escalation
                   temperature_used = get_combat_temperature(encounter_data, validation_attempt=attempt)

                   print(f"DEBUG: [COMBAT] Using GPT-4.1 model: {COMBAT_MAIN_MODEL} (temp: {temperature_used})")
                   messages_to_send = combat_message_compressor.process_combat_conversation(retry_request_history)

                   # Export compressed conversation for review
                   with open("combat_messages_to_api.json", "w", encoding="utf-8") as f:
                       json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
                   print(f"DEBUG: [COMBAT] Exported compressed messages to combat_messages_to_api.json")

                   response = client.chat.completions.create(
                       model=COMBAT_MAIN_MODEL,
                       temperature=temperature_used,
                       messages=messages_to_send,
                       timeout=COMBAT_API_TIMEOUT_SECONDS  # TABLETOP MODE: Prevent indefinite hang
                   )

               # Track usage
               if USAGE_TRACKING_AVAILABLE:
                   try:
                       track_response(response)
                   except Exception:
                       pass  # Silently ignore tracking errors

               ai_response = response.choices[0].message.content.strip()

               print(f"[COMBAT_MANAGER] AI response received ({len(ai_response)} chars)")

               # Write raw response to debug file
               os.makedirs("debug", exist_ok=True)
               with open("debug/debug_ai_response.json", "w") as debug_file:
                   json.dump({"raw_ai_response": ai_response}, debug_file, indent=2)

               # Keep retry context local (do not persist validation chatter in canonical history).
               retry_validation_history = list(retry_request_history)
               retry_validation_history.append({"role": "assistant", "content": ai_response})

               # Check if the response is valid JSON
               if not is_valid_json(ai_response):
                   debug(f"VALIDATION: Invalid JSON response from AI (Attempt {attempt + 1}/{max_retries})", category="combat_validation")
                   if attempt < max_retries - 1:
                       # Keep invalid JSON correction local to retry flow.
                       error_msg = "Your previous response was not a valid JSON object with 'narration' and 'actions' fields. Please provide a valid JSON response."
                       retry_feedback_note = error_msg
                       validation_attempts.append({
                           "attempt": attempt + 1,
                           "assistant_response": ai_response,
                           "validation_error": error_msg,
                           "error_type": "json_format",
                           "temperature_used": temperature_used
                       })
                       continue
                   warning("VALIDATION: Max retries exceeded for JSON validation. Skipping this response.", category="combat_validation")
                   break

               # Parse the JSON response
               parsed_response = json.loads(ai_response)
               narration = parsed_response["narration"]
               actions = parsed_response["actions"]

               # Check for multiple updateEncounter actions
               if check_multiple_update_encounter(actions):
                   debug(f"VALIDATION: Multiple updateEncounter actions detected (Attempt {attempt + 1}/{max_retries})", category="combat_validation")
                   if attempt < max_retries - 1:
                       # Keep requery correction local to retry flow.
                       requery_msg = create_multiple_update_requery_prompt(parsed_response)
                       retry_feedback_note = requery_msg
                       validation_attempts.append({
                           "attempt": attempt + 1,
                           "assistant_response": ai_response,
                           "validation_error": requery_msg,
                           "error_type": "multiple_update_encounter",
                           "temperature_used": temperature_used
                       })
                       continue
                   warning("VALIDATION: Max retries exceeded for multiple updateEncounter correction. Using last response.", category="combat_validation")

               # Validate the combat logic
               print(f"[COMBAT_MANAGER] Validating combat response (Attempt {attempt + 1}/{max_retries})")

               # Update status to show validation is happening
               try:
                   from core.managers.status_manager import status_manager
                   status_manager.update_status("Validating combat actions...", is_processing=True)
               except Exception as e:
                   debug(f"Could not update status: {e}", category="status")

               # ---------------------------------------------------------
               # NEW VALIDATION STEP: Combatant Integrity Check
               # ---------------------------------------------------------
               # This catches hallucinations where the AI invents new creatures or acts for
               # creatures that are not in the encounter.
               integrity_check = validate_combatant_integrity(
                   ai_response,
                   encounter_data,
                   multi_pc_manager=multi_pc_manager,
                   party_tracker_data=party_tracker_data,
               )
               if integrity_check is not True:
                   debug(f"VALIDATION: Combatant Integrity Failed (Attempt {attempt + 1}/{max_retries})", category="combat_validation")
                   debug(f"INTEGRITY_FAIL: {integrity_check}", category="combat_validation")

                   if attempt < max_retries - 1:
                       # Keep integrity correction local to retry flow.
                       retry_feedback_note = integrity_check
                       validation_attempts.append({
                           "attempt": attempt + 1,
                           "assistant_response": ai_response,
                           "validation_error": integrity_check,
                           "error_type": "integrity_check",
                           "temperature_used": temperature_used
                       })
                       continue
                   warning("VALIDATION: Max retries exceeded for Integrity Check. Skipping.", category="combat_validation")
                   break
               # ---------------------------------------------------------

               # PASS MULTI-PC MANAGER FOR VALIDATION GUARDRAIL
               validation_result = validate_combat_response(
                   ai_response,
                   encounter_data,
                   user_input_text,
                   retry_validation_history,
                   multi_pc_manager=multi_pc_manager,
               )

               if validation_result is True:
                   valid_response = True
                   retry_feedback_note = None
                   print(f"[COMBAT_MANAGER] Combat response validation PASSED on attempt {attempt + 1}")
                   debug(f"SUCCESS: Response validated successfully on attempt {attempt + 1}", category="combat_validation")
                   break

               debug(f"VALIDATION: Response validation failed (Attempt {attempt + 1}/{max_retries})", category="combat_validation")
               feedback = validation_result
               debug(f"VALIDATION_ATTEMPT: {attempt + 1} failed", category="combat_validation")

               if attempt < max_retries - 1:
                   # Keep validation correction local to retry flow.
                   retry_feedback_note = feedback
                   validation_attempts.append({
                       "attempt": attempt + 1,
                       "assistant_response": ai_response,
                       "validation_error": feedback,
                       "error_type": "combat_logic",
                       "temperature_used": temperature_used
                   })
                   continue

               warning("VALIDATION: Max retries exceeded for combat validation. Using last response.", category="combat_validation")
               break

           except Exception as e:
               error(f"FAILURE: Failed to get or validate AI response (Attempt {attempt + 1}/{max_retries})", exception=e, category="combat_events")
               if attempt < max_retries - 1:
                   continue
               warning("VALIDATION: Max retries exceeded. Skipping this response.", category="combat_validation")
               break
       
       # Clean up conversation history based on validation outcome
       if valid_response or ai_response:
           # Remove all validation attempts from conversation history
           conversation_history = conversation_history[:initial_conversation_length]
           
           # Add only the final assistant response
           if ai_response:
               conversation_history.append({"role": "assistant", "content": ai_response})
           
           # Log successful validation if it occurred
           if valid_response and validation_attempts:
               validation_attempts.append({
                   "attempt": "final",
                   "assistant_response": ai_response,
                   "validation_result": "success",
                   "temperature_used": temperature_used
               })
       
       # Write validation attempts to log file
       if validation_attempts:
           # Create debug/combat directory if it doesn't exist
           debug_combat_dir = os.path.join("debug", "combat")
           os.makedirs(debug_combat_dir, exist_ok=True)
           
           # Create timestamped filename
           from datetime import datetime
           timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Remove last 3 digits of microseconds
           encounter_id = encounter_data.get("encounterId", "unknown").replace("/", "_")
           validation_count = len(validation_attempts)
           validation_filename = f"validation_session_{timestamp}_{encounter_id}_attempts{validation_count}.json"
           validation_log_path = os.path.join(debug_combat_dir, validation_filename)
           try:
               # Create new validation log for this session
               validation_log = []
               
               # Add current validation session
               validation_log.append({
                   "timestamp": datetime.now().isoformat(),
                   "encounter_id": encounter_data.get("encounter_id", "unknown"),
                   "user_input": user_input_text,
                   "validation_attempts": validation_attempts,
                   "final_outcome": "success" if valid_response else "failed_after_retries"
               })
               
               # Write updated log
               with open(validation_log_path, 'w') as f:
                   json.dump(validation_log, f, indent=2)
                   
           except Exception as e:
               warning(f"FAILURE: Failed to write validation log", category="file_operations")
       
       # Save the cleaned conversation history
       save_json_file(conversation_history_file, conversation_history)
       
       if not ai_response:
           error("FAILURE: Failed to get a valid AI response after multiple attempts", category="combat_events")
           continue
       
       # Process the validated response
       try:
           parsed_response = json.loads(ai_response)
           narration = parsed_response["narration"]
           actions = parsed_response["actions"]
           
           print(f"[COMBAT_MANAGER] Processing {len(actions)} combat actions")
           
           # Update status to show actions are being processed
           if len(actions) > 0:
               try:
                   from core.managers.status_manager import status_manager
                   status_manager.update_status("Processing combat outcomes...", is_processing=True)
               except Exception as e:
                   debug(f"Could not update status: {e}", category="status")
           
           for i, action in enumerate(actions):
               action_type = action.get('action', action.get('type', 'unknown'))
               print(f"[COMBAT_MANAGER] Action {i+1}: {action_type}")
           
           # Extract and update combat round if provided
           if 'combat_round' in parsed_response:
               new_round = parsed_response['combat_round']
               # Use combat_round from encounter data, not current_round
               current_combat_round = encounter_data.get('combat_round', encounter_data.get('current_round', 1))
               
               debug(f"ROUND_TRACKING: parsed_response has combat_round={new_round}, encounter has combat_round={current_combat_round}", category="combat_events")
               
               # Only update if round advances (never go backward)
               if isinstance(new_round, int) and new_round > current_combat_round:
                   debug(f"STATE_CHANGE: Combat advancing from round {current_combat_round} to round {new_round}", category="combat_events")
                   encounter_data['combat_round'] = new_round
                   # Also update current_round for backwards compatibility
                   encounter_data['current_round'] = new_round
                   
                   # TABLETOP MODE: Sync round state to manager
                   if multi_pc_manager:
                        debug(f"STATE_CHANGE: Syncing MultiPCManager to Round {new_round}", category="combat_events")
                        multi_pc_manager.start_new_round()
                        # Ensure manager round matches (start_new_round increments, but let's be safe)
                        multi_pc_manager.current_round = new_round

                        # TABLETOP MODE: Phase 1 deterministic round start.
                        # Persisted roundStartsWith controls which phase opens each new round.
                        round_starts_with = encounter_data.get("roundStartsWith", "pcGroup")
                        if round_starts_with == "dmGroup":
                            multi_pc_manager.pc_phase_complete = True
                            # TABLETOP MODE: Set opening batch marker for dmGroup round starts
                            if COMBAT_STATE_SYNC_AVAILABLE:
                                apply_opening_batch_marker(encounter_data, "dmGroup")
                            debug(
                                "STATE_CHANGE: Applied roundStartsWith=dmGroup -> ENEMY_PHASE start",
                                category="combat_events"
                            )
                            debug(
                                "PHASE_MARKER: Set openingEnemyBatchPending=True via round-start dmGroup path",
                                category="combat_events"
                            )
                        else:
                            multi_pc_manager.pc_phase_complete = False
                            # TABLETOP MODE: Clear opening batch marker for pcGroup round starts
                            if COMBAT_STATE_SYNC_AVAILABLE:
                                apply_opening_batch_marker(encounter_data, "pcGroup")
                            debug(
                                "STATE_CHANGE: Applied roundStartsWith=pcGroup -> PC_PHASE start",
                                category="combat_events"
                            )
                            debug(
                                "PHASE_MARKER: Cleared openingEnemyBatchPending via round-start pcGroup path",
                                category="combat_events"
                            )

                   # Save the updated encounter data
                   save_json_file(f"modules/encounters/encounter_{encounter_id}.json", encounter_data)
                   
                   # Compress old combat rounds more aggressively - compress after each round
                   # When we start round 3, compress round 1; when we start round 4, compress round 2, etc.
                   if new_round >= 2:
                       debug(f"COMPRESSION: Checking for round compression (current round: {new_round})", category="combat_events")
                       debug(f"COMPRESSION: About to call compress_old_combat_rounds with round {new_round}", category="combat_events")
                       compressed_history = compress_old_combat_rounds(
                           conversation_history, 
                           new_round, 
                           keep_recent_rounds=1  # Changed from 2 to 1 for more aggressive compression
                       )
                       
                       # Save compressed history
                       if len(compressed_history) < len(conversation_history):
                           debug(f"COMPRESSION: History compressed from {len(conversation_history)} to {len(compressed_history)} messages", category="combat_events")
                           conversation_history = compressed_history
                           save_json_file(conversation_history_file, conversation_history)
                           info(f"COMPRESSION: Combat history compressed and saved", category="combat_events")
                       else:
                           debug(f"COMPRESSION: No compression occurred (still {len(conversation_history)} messages)", category="combat_events")
                           
               elif isinstance(new_round, int) and new_round < current_combat_round:
                   warning(f"VALIDATION: Ignoring backward round progression from {current_combat_round} to {new_round}", category="combat_events")
           
               
       except json.JSONDecodeError as e:
           debug(f"VALIDATION: JSON parsing error - {str(e)}", category="combat_events")
           debug("VALIDATION: Raw AI response:", category="combat_events")
           debug(ai_response, category="combat_events")
           continue
       
       # --- ACTION PROCESSING: CONSOLIDATE AND EXECUTE ---
       # This new block prevents race conditions by consolidating all character
       # updates into a single, authoritative save at the end of combat.

       # A dictionary to hold queued character update payloads for each actor.
       final_character_updates = {}

       # Check if combat is ending in this turn.
       is_combat_ending = any(a.get("action", "").lower() == "exit" for a in actions)

       # Display narration immediately, as it describes the events of the turn.
       print(f"Dungeon Master: {narration}")
       import sys
       sys.stdout.flush()

       # STEP 1: GATHER all intended changes from the AI's actions.
       for action in actions:
           action_type = action.get("action", "").lower()
           parameters = action.get("parameters", {})

           if action_type in ["updateplayerinfo", "updatecharacterinfo", "updatenpcinfo"]:
               char_name_key = "characterName" if "characterName" in parameters else "npcName"
               character_name = parameters.get(char_name_key)
               changes = parameters.get("changes")
               ops = parameters.get("ops")

               if character_name and (changes or ops):
                   _queue_final_character_update(final_character_updates, character_name, changes, ops)
                   if changes:
                       info(f"CONSOLIDATING: Queued change for {character_name}: '{changes}'", category="combat_events")

                       if any(word in changes.lower() for word in ["arrow", "bolt", "ammunition", "ammo", "expended"]):
                           debug(f"AMMO_DEBUG: Detected ammunition change for {character_name}", category="ammunition")
                           debug(f"AMMO_DEBUG: Action type: {action_type}", category="ammunition")
                           debug(f"AMMO_DEBUG: Changes text: '{changes}'", category="ammunition")
                           debug(f"AMMO_DEBUG: Added to final_character_updates queue", category="ammunition")
                   else:
                       info(f"CONSOLIDATING: Queued deterministic ops for {character_name}", category="combat_events")

           elif action_type == "updateencounter":
               encounter_id_for_update = parameters.get("encounterId", encounter_id)
               changes = parameters.get("changes", "")
               ops = parameters.get("ops")
               info(f"STATE_UPDATE: Processing immediate encounter update: {changes}", category="encounter_management")
               try:
                   updated_encounter_data = update_encounter.update_encounter(
                       encounter_id_for_update,
                       changes,
                       ops=ops,
                   )
                   if updated_encounter_data:
                       encounter_data = normalize_encounter_status(updated_encounter_data)
               except Exception as e:
                   error(f"FAILURE: Failed to update encounter", exception=e, category="encounter_management")

           elif action_type == "exit" and is_combat_ending:
               info("CONSOLIDATING: 'exit' action detected. Calculating final HP and XP.", category="combat_events")
               xp_narrative, xp_awarded = calculate_xp()
               info(f"XP_AWARD: Calculated {xp_awarded} XP per participant.", category="xp_tracking")
               conversation_history.append({"role": "user", "content": f"XP Awarded: {xp_narrative}"})
               save_json_file(conversation_history_file, conversation_history)

               for creature in encounter_data.get("creatures", []):
                   if creature.get("type") in ["player", "npc"]:
                       character_name = creature.get("name")
                       if xp_awarded > 0:
                           _queue_final_character_update(
                               final_character_updates,
                               character_name,
                               f"awarded {xp_awarded} experience points",
                           )

           if not is_combat_ending and check_all_monsters_defeated(encounter_data):
               info("AUTO_EXIT: All enemies defeated after action processing. LLM failed to call exit - forcing combat end.", category="combat_events")
               is_combat_ending = True

               xp_narrative, xp_awarded = calculate_xp()
               info(f"XP_AWARD: Auto-exit calculated {xp_awarded} XP per participant.", category="xp_tracking")
               conversation_history.append({"role": "user", "content": f"XP Awarded: {xp_narrative}"})
               save_json_file(conversation_history_file, conversation_history)

               for creature in encounter_data.get("creatures", []):
                   if creature.get("type") in ["player", "npc"]:
                       character_name = creature.get("name")
                       if xp_awarded > 0:
                           _queue_final_character_update(
                               final_character_updates,
                               character_name,
                               f"awarded {xp_awarded} experience points",
                           )

           # TABLETOP MODE: Turn Queue Advancement
           if multi_pc_manager and not is_combat_ending:
               current_actor = multi_pc_manager.get_current_actor()
               if current_actor and (current_actor.type == CombatantType.NPC):
                   if actions:
                       debug(f"[COMBAT_MANAGER] Auto-advancing turn for NPC {current_actor.name}", category="combat_events")
                       next_actor = multi_pc_manager.advance_turn()

                       if next_actor.type == CombatantType.PC:
                           party_tracker_data["active_character"] = next_actor.name
                           safe_write_json("party_tracker.json", party_tracker_data)
                           if MULTI_PC_COMBAT_AVAILABLE:
                               emit_combat_event("active_character_update", {"character": next_actor.name})
                           debug(f"[COMBAT_MANAGER] Advanced active character to {next_actor.name}", category="combat_events")
                       else:
                           debug(f"[COMBAT_MANAGER] Advanced turn to next enemy/NPC: {next_actor.name}", category="combat_events")

               active_pc_name = multi_pc_manager.current_pc_name
               if active_pc_name:
                   active_state = multi_pc_manager.pc_states.get(active_pc_name)

                   if active_state and active_state.status == PCStatus.ACTED:
                       debug(f"[COMBAT_MANAGER] Detected ACTED status for {active_pc_name}, advancing turn queue", category="combat_events")
                       next_actor = multi_pc_manager.advance_turn()

                       if next_actor.type == CombatantType.PC:
                           party_tracker_data["active_character"] = next_actor.name
                           safe_write_json("party_tracker.json", party_tracker_data)
                           if MULTI_PC_COMBAT_AVAILABLE:
                               emit_combat_event("active_character_update", {"character": next_actor.name})
                           debug(f"[COMBAT_MANAGER] Advanced active character to {next_actor.name}", category="combat_events")
                       else:
                           debug(f"[COMBAT_MANAGER] Advanced turn to enemy/NPC: {next_actor.name}", category="combat_events")

       # TABLETOP MODE: Section 1.2 - Opening enemy batch completion transition
       # If DM_GROUP opened the round, clear marker and return control to PC_PHASE after batch resolves.
       if multi_pc_manager:
           if encounter_data.get("openingEnemyBatchPending", False):
               encounter_data["openingEnemyBatchPending"] = False
               multi_pc_manager.pc_phase_complete = False
               debug(
                   "PHASE_MARKER: Cleared openingEnemyBatchPending after opening enemy batch resolution",
                   category="combat_events"
               )
               debug(
                   "STATE_CHANGE: Opening batch complete -> PC_PHASE",
                   category="combat_events"
               )
               save_json_file(f"modules/encounters/encounter_{encounter_id}.json", encounter_data)

       # STEP 2: EXECUTE the consolidated updates. This is the only place character files are saved.
       _apply_final_character_updates(final_character_updates, multi_pc_manager)

       # STEP 3: If combat ended, perform final cleanup and exit the simulation.
       if is_combat_ending:
           # Store the encounter ID before clearing it
           last_encounter_id = party_tracker_data.get("worldConditions", {}).get("activeCombatEncounter", "")

           # IMPORTANT: Generate summary BEFORE clearing the active encounter ID
           info("AI_CALL: Generating final combat summary...", category="ai_operations")
           dialogue_summary_result = summarize_dialogue(conversation_history, location_info, party_tracker_data)

           # NOW clear the active encounter after summary is generated
           if 'worldConditions' in party_tracker_data and 'activeCombatEncounter' in party_tracker_data['worldConditions']:
               if last_encounter_id:
                   party_tracker_data["worldConditions"]["lastCompletedEncounter"] = last_encounter_id
               party_tracker_data['worldConditions']['activeCombatEncounter'] = ""
               debug(f"STATE_CHANGE: Cleared active combat encounter. Last completed is now {last_encounter_id}", category="combat_events")
               safe_write_json("party_tracker.json", party_tracker_data)

           info("FILE_OP: Saving final combat chat history log...", category="combat_logs")
           generate_chat_history(conversation_history, encounter_id)

           # Reload the player_info object from disk one last time before returning it.
           # This ensures the main loop receives the fully updated state.
           player_info = safe_json_load(player_file)

           info("SUCCESS: Combat complete. Exiting simulation.", category="combat_events")
           return dialogue_summary_result, player_info

       # Save updated conversation history after processing all actions
       save_json_file(conversation_history_file, conversation_history)

def main():
    debug("INITIALIZATION: Starting main function in combat_manager", category="combat_events")
    
    # Load party tracker
    try:
        party_tracker_data = safe_json_load("party_tracker.json")
        if not party_tracker_data:
            error("FAILURE: Failed to load party_tracker.json", category="file_operations")
            return
    except Exception as e:
        error(f"FAILURE: Failed to load party tracker", exception=e, category="file_operations")
        return
    
    # Get active combat encounter
    active_combat_encounter = party_tracker_data["worldConditions"].get("activeCombatEncounter")
    
    if not active_combat_encounter:
        info("STATE_CHANGE: No active combat encounter located.", category="combat_events")
        return
    
    # Get location data to pass to the simulation
    current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
    location_data = get_location_data(current_location_id)
    
    if not location_data:
        error(f"FAILURE: Failed to find location {current_location_id}", category="location_transitions")
        return
    
    # Run the combat simulation, passing the loaded location_data
    dialogue_summary, updated_player_info = run_combat_simulation(active_combat_encounter, party_tracker_data, location_data)
    
    info("SUCCESS: Combat simulation completed.", category="combat_events")
    if dialogue_summary:
        info(f"SUMMARY: Dialogue Summary: {dialogue_summary}", category="combat_events")

if __name__ == "__main__":
    main()
