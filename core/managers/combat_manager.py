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
import time
import re
import random
import subprocess
from model_config import USE_COMPRESSED_COMBAT
from datetime import datetime
from utils.xp import main as calculate_xp
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T040", "core/managers/combat_manager.py", 787)
register_callsite("T041", "core/managers/combat_manager.py", 1028)
register_callsite("T042", "core/managers/combat_manager.py", 1841)
register_callsite("T043", "core/managers/combat_manager.py", 2243)
register_callsite("T044", "core/managers/combat_manager.py", 2340)
register_callsite("T045", "core/managers/combat_manager.py", 2892)

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
)
from updates.update_character_info import update_character_info, normalize_character_name
import updates.update_encounter as update_encounter
import updates.update_party_tracker as update_party_tracker
# Import the preroll generator
from core.generators.generate_prerolls import generate_prerolls
# Import safe JSON functions
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
import core.ai.cumulative_summary as cumulative_summary
from utils.enhanced_logger import debug, info, warning, error, game_event, set_script_name
# Import combat message compressor for optimizing conversation history
from core.ai.combat_compressor import CombatUserMessageCompressor
# Import inventory context matcher for enhancing player combat actions
from core.ai.inventory_context_integration import enhance_player_input_with_inventory

# Set script name for logging
set_script_name(__name__)

# Remove color constants - no longer used
# Color codes removed per CLAUDE.md guidelines

# Temperature
TEMPERATURE = 0.8

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
    if filename == 'combat/combat_sim_prompt.txt' and USE_COMPRESSED_COMBAT:
        filename = 'combat/combat_sim_prompt_compressed.txt'
        debug("Using compressed combat prompt", category="combat_events")
    
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

def validate_combat_response(response, encounter_data, user_input, conversation_history=None):
    """
    Validate a combat response for accuracy in HP tracking, combat flow, etc.
    Returns True if valid, or a string with the reason for failure if invalid.
    """
    print(f"[COMBAT_MANAGER] Starting validation for combat response")
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
    from model_config import USE_COMPRESSED_COMBAT
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
    
    # Add previous user/assistant pairs for context with compression
    if conversation_history and len(conversation_history) > (context_pairs * 2):
        # Get the last 12 messages (6 pairs)
        # +1 to exclude current user input since we'll add it separately
        recent_messages = conversation_history[-(context_pairs * 2 + 1):-1]
        
        # Filter to only user/assistant messages (no system messages)
        context_messages = [
            msg for msg in recent_messages 
            if msg["role"] in ["user", "assistant"]
        ][-(context_pairs * 2):]  # Ensure we only get exactly 12 messages
        
        # Apply compression to user messages except the last 2
        compressed_context = []
        user_message_count = 0
        total_user_messages = sum(1 for msg in context_messages if msg["role"] == "user")
        
        for msg in context_messages:
            if msg["role"] == "user":
                user_message_count += 1
                # Compress all user messages except the last 2
                if user_message_count <= total_user_messages - 2:
                    # Check if this is a combat message that should be compressed
                    if combat_message_compressor.should_compress_user_message(msg, 0, 999):  # Use dummy index since we're just checking content
                        compressed_content = combat_message_compressor.compress_message((0, msg["content"]))[1]
                        compressed_context.append({
                            "role": "user",
                            "content": compressed_content
                        })
                        debug(f"VALIDATION: Compressed user message {user_message_count}/{total_user_messages}", category="combat_validation")
                    else:
                        # Not a combat message, keep as-is
                        compressed_context.append(msg)
                else:
                    # Keep last 2 user messages uncompressed
                    compressed_context.append(msg)
                    debug(f"VALIDATION: Keeping user message {user_message_count}/{total_user_messages} uncompressed", category="combat_validation")
            else:
                # Keep assistant messages as-is
                compressed_context.append(msg)
        
        # Add context header and compressed messages
        validation_conversation.append({
            "role": "system", 
            "content": f"=== PREVIOUS COMBAT CONTEXT (last {context_pairs} exchanges with compression) ==="
        })
        validation_conversation.extend(compressed_context)
    
    # Add current validation data BEFORE the response to validate
    validation_conversation.extend([
        {"role": "system", "content": "=== CURRENT VALIDATION DATA ==="},
        {"role": "system", "content": f"Encounter Data:\n{json.dumps(encounter_data, indent=2)}"}
    ])
    
    # Now add the user input and AI response to validate
    validation_conversation.extend([
        {"role": "user", "content": f"Player Input: {user_input}"},
        {"role": "assistant", "content": response}
    ])

    # Export validation conversation for review
    with open("validation_messages_to_api.json", "w", encoding="utf-8") as f:
        json.dump(validation_conversation, f, indent=2, ensure_ascii=False)
    
    # Calculate size for debugging
    validation_size = sum(len(json.dumps(msg)) for msg in validation_conversation)
    print(f"DEBUG: [VALIDATION] Exported validation messages to validation_messages_to_api.json")
    print(f"DEBUG: [VALIDATION] Total validation context size: {validation_size:,} characters ({len(validation_conversation)} messages)")

    # Select model config per provider
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        validation_config = config.COMBAT_VALID_GPT54_NONE
    elif MODEL_PROVIDER == "gemini":
        validation_config = config.COMBAT_VALID_GEMINI_FLASH_LOW
    elif MODEL_PROVIDER == "lmstudio":
        validation_config = config.COMBAT_VALID_LMSTUDIO
    else:  # legacy
        validation_config = config.COMBAT_VALID_LEGACY

    max_validation_retries = 5
    for attempt in range(max_validation_retries):
        try:
            validation_result = capture_and_fanout("T040", api_client.create_completion,
                messages=validation_conversation,
                model=validation_config["model"],
                temperature=0.3,
                **{k: v for k, v in validation_config.items() if k != "model"})

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
        {"role": "system", "content": "Your task is to create a vivid, colorful narrative summary of this combat encounter. Capture the dramatic highs and lows - critical hits, narrow misses, clever tactics, desperate moments, and heroic actions. Write it as an exciting story paragraph that captures the flow and feel of the battle. Include: the initial setup, key turning points, memorable moments, the final blow, total XP awarded, and what remains after combat (defeated foes, environmental changes). Write in past tense as a complete narrative summary, not a play-by-play. Make it engaging and memorable - this will be the permanent record of this battle. Do NOT use markdown formatting (no **, no headers, no bullet points) -- weave XP totals and aftermath into the flowing narrative prose. Keep the summary to 1-2 paragraphs (150-250 words). Use only standard ASCII characters -- no smart quotes, no Unicode, no non-English words."},
        {"role": "user", "content": clean_text}
    ]

    # Generate dialogue summary -- select model config per provider
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        summary_config = config.COMBAT_SUMMARY_GPT54MINI_NONE
    elif MODEL_PROVIDER == "gemini":
        summary_config = config.COMBAT_SUMMARY_GEMINI_FLASH_LOW
    elif MODEL_PROVIDER == "lmstudio":
        summary_config = config.COMBAT_SUMMARY_LMSTUDIO
    else:  # legacy
        summary_config = config.COMBAT_SUMMARY_LEGACY

    response = capture_and_fanout("T041", api_client.create_completion,
        messages=dialogue_summary_prompt,
        model=summary_config["model"],
        temperature=TEMPERATURE,
        response_format=None,
        **{k: v for k, v in summary_config.items() if k != "model"})

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
    
    # MED-7 (#127): the prompt requests prose, but if a model (esp. Gemini flash
    # with no schema) wraps it in JSON, extract the prose from any common field
    # name instead of archiving the raw JSON string.
    try:
        parsed_summary = json.loads(dialogue_summary)
        if isinstance(parsed_summary, dict):
            for _field in ("narration", "summary", "text", "content", "message"):
                if _field in parsed_summary and isinstance(parsed_summary[_field], str):
                    dialogue_summary = parsed_summary[_field]
                    debug(f"Extracted '{_field}' from JSON combat summary", category="combat_summary")
                    break
    except (json.JSONDecodeError, KeyError, TypeError):
        # Not JSON, use as-is
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
  "deaths": ["ALL creatures with HP 0 or listed as dead in the creature states -- include every dead creature regardless of when they died"],
  "status_changes": ["new conditions or effects applied this round"],
  "resource_usage": {{"character": "resources used (spell slots, abilities, etc)"}},
  "narrative_highlights": ["2-4 evocative single sentences capturing key dramatic moments, critical hits, deaths, powerful spells, or memorable character actions"],
  "round_end_state": {{
    "alive": ["Name (current/max HP)"],
    "dead": ["Name"],
    "conditions": {{"Name": ["conditions"]}}
  }}
}}

CRITICAL RULES:
- The "deaths" array MUST include every creature shown as dead or at 0 HP in the creature states, even if they died in a prior round. This is a complete death list for state tracking.
- Focus on mechanical accuracy for the actions -- exact roll values, damage numbers, and HP totals.
- For narrative_highlights, extract the most dramatic moments. Keep each highlight to one evocative sentence.
- Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols."""

        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
        elif MODEL_PROVIDER == "gemini":
            mini_cfg = config.MINI_UTIL_GEMINI_FLASH_MINIMAL
        elif MODEL_PROVIDER == "lmstudio":
            mini_cfg = config.MINI_UTIL_LMSTUDIO
        else:  # legacy
            mini_cfg = config.MINI_UTIL_LEGACY

        response = capture_and_fanout("T042", api_client.create_completion,
            messages=[
                {"role": "system", "content": "You are a combat log analyzer. Extract mechanical game information and key narrative moments. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model=mini_cfg["model"],
            temperature=0.1,
            response_format={"type": "json_object"},
            **{k: v for k, v in mini_cfg.items() if k != "model"})
        
        # Track usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(response, context={'endpoint': 'combat_dm', 'purpose': 'combat_round_summary', 'model': mini_cfg["model"]})
            except:
                pass
        
        summary = json.loads(response.choices[0].message.content)
        return summary
        
    except Exception as e:
        error(f"COMPRESSION: Failed to generate round {round_num} summary", exception=e, category="combat_events")
        return None

def run_combat_simulation(encounter_id, party_tracker_data, location_info):
   """Main function to run the combat simulation"""
   print(f"\n[COMBAT_MANAGER] ========== COMBAT SIMULATION START ==========")
   print(f"[COMBAT_MANAGER] Encounter ID: {encounter_id}")
   print(f"[COMBAT_MANAGER] Location: {location_info.get('name', 'Unknown')}")
   debug(f"INITIALIZATION: Starting combat simulation for encounter {encounter_id}", category="combat_events")
   
   # Initialize path manager
   from utils.module_path_manager import ModulePathManager
   from utils.encoding_utils import safe_json_load
   try:
       party_tracker = safe_json_load("party_tracker.json")
       current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
       path_manager = ModulePathManager(current_module)
   except:
       path_manager = ModulePathManager()

   # Check if combat history file exists and has content to determine if we are resuming.
   if os.path.exists(conversation_history_file) and os.path.getsize(conversation_history_file) > 100:
       conversation_history = load_json_file(conversation_history_file)
       is_resuming = True
       print("[COMBAT_MANAGER] Resuming existing combat session.")
   else:
       is_resuming = False
       conversation_history = [
           {"role": "system", "content": read_prompt_from_file('combat/combat_sim_prompt.txt')},
           {"role": "system", "content": f"Current Combat Encounter: {encounter_id}"},
           {"role": "system", "content": ""}, # Player data placeholder
           {"role": "system", "content": ""}, # Monster templates placeholder
           {"role": "system", "content": ""}, # Location info placeholder
       ]
       print("[COMBAT_MANAGER] Starting new combat session.")
   
   # Initialize and reset secondary model histories
   second_model_history = []
   third_model_history = []
   save_json_file(second_model_history_file, second_model_history)
   save_json_file(third_model_history_file, third_model_history)
   
   # Load encounter data
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
       
       # First, update the player character format
       for i in range(len(conversation_history)):
           msg = conversation_history[i]
           # Check for either old format (with json) or new format (with "Here's the player character data")
           if msg.get("role") == "system" and ("Player Character:" in msg.get("content", "") or "Here's the player character data:" in msg.get("content", "")):
               # Found player format - update it to ensure it's current
               print(f"[COMBAT_MANAGER] Updating player character format at index {i}")
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
   
   dynamic_state_parts.append(state_line)
   
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
           dynamic_state_parts.append(creature_line)
   
   all_dynamic_state = "\n".join(dynamic_state_parts)
   
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

       # Get the AI's re-engagement response.
       # Error handling is split by failing stage so logs distinguish an API
       # failure from a non-JSON response from generic post-processing errors.
       # The user-facing fallback is identical in every stage.
       resume_response = None
       resume_stage_failed = False

       # Stage 1: API call (model never responded -> API failure)
       try:
           print("[COMBAT_MANAGER] Getting re-engagement narration from AI...")
           debug("RESUME: Requesting AI re-engagement response", category="combat_events")
           print("DEBUG: [RESUME] About to call AI for re-engagement")
           # Use base temperature for re-engagement (no validation failures)
           # Select model config per provider
           from model_config import MODEL_PROVIDER
           if MODEL_PROVIDER == "openai":
               combat_config = config.COMBAT_MAIN_GPT54_NONE
           elif MODEL_PROVIDER == "gemini":
               combat_config = config.COMBAT_MAIN_GEMINI_PRO_LOW
           elif MODEL_PROVIDER == "lmstudio":
               combat_config = config.COMBAT_MAIN_LMSTUDIO
           else:  # legacy
               combat_config = config.COMBAT_MAIN_LEGACY

           temperature_used = get_combat_temperature(encounter_data, validation_attempt=0)

           # Compress conversation history before sending to AI
           messages_to_send = combat_message_compressor.process_combat_conversation(conversation_history)

           resume_response = capture_and_fanout("T043", api_client.create_completion,
               messages=messages_to_send,
               model=combat_config["model"],
               temperature=temperature_used,
               **{k: v for k, v in combat_config.items() if k != "model"})

           # Log API call to master log
           try:
               from utils.api_logger import log_api_call
               log_api_call("combat", messages_to_send, resume_response,
                           metadata={"temperature": temperature_used, "branch": MODEL_PROVIDER, "context": "re-engage"})
           except Exception as e:
               print(f"[API_LOG] Warning: Failed to log combat call: {e}")

           # Track usage if available
           if USAGE_TRACKING_AVAILABLE:
               try:
                   track_response(resume_response)
               except:
                   pass  # Silently ignore tracking errors

       except Exception as e:
           resume_stage_failed = True
           error("FAILURE: T043 re-engagement API call failed.", exception=e, category="combat_events")
           print(f"DEBUG: [RESUME] Error getting re-engagement: {str(e)}")
           print("Dungeon Master: The battle continues! What will you do next?")
           import sys
           sys.stdout.flush()
           debug(f"RESUME: Using fallback narration due to error: {str(e)}", category="combat_events")

       # Stage 2: Parse + display (model responded but content is bad)
       if not resume_stage_failed:
           try:
               resume_response_content = resume_response.choices[0].message.content.strip()
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

           except json.JSONDecodeError as e:
               error("FAILURE: T043 returned non-JSON re-engagement response.", exception=e, category="combat_events")
               print(f"DEBUG: [RESUME] Error getting re-engagement: {str(e)}")
               print("Dungeon Master: The battle continues! What will you do next?")
               import sys
               sys.stdout.flush()
               debug(f"RESUME: Using fallback narration due to error: {str(e)}", category="combat_events")

           except Exception as e:
               error("FAILURE: T043 re-engagement post-processing failed.", exception=e, category="combat_events")
               print(f"DEBUG: [RESUME] Error getting re-engagement: {str(e)}")
               print("Dungeon Master: The battle continues! What will you do next?")
               import sys
               sys.stdout.flush()
               debug(f"RESUME: Using fallback narration due to error: {str(e)}", category="combat_events")
   else:
       # This is a new combat. Use the original logic to get the initial scene.
       debug("AI_CALL: Getting initial scene description...", category="combat_events")
       initiative_order = get_initiative_order(encounter_data)
       
       initial_prompt_text = f"""The setup scene for the combat has already been given and described to the party. Now, describe the combat situation and the enemies the party faces."""

       initial_prompt = f"""Dungeon Master Note: Respond with valid JSON containing a 'narration' field, 'combat_round' field, and an 'actions' array. This is the start of combat, so please describe the scene and set initiative order, but don't take any actions yet. Start off by hooking the player and engaging them for the start of combat the way any world class dungeon master would.

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

       conversation_history.append({"role": "user", "content": initial_prompt})
       save_json_file(conversation_history_file, conversation_history)

       max_retries = 3
       initial_response = None
       initial_conversation_length = len(conversation_history)

       # Select model config per provider (before retry loop)
       from model_config import MODEL_PROVIDER
       if MODEL_PROVIDER == "openai":
           combat_config = config.COMBAT_MAIN_GPT54_NONE
       elif MODEL_PROVIDER == "gemini":
           combat_config = config.COMBAT_MAIN_GEMINI_PRO_LOW
       elif MODEL_PROVIDER == "lmstudio":
           combat_config = config.COMBAT_MAIN_LMSTUDIO
       else:  # legacy
           combat_config = config.COMBAT_MAIN_LEGACY

       for attempt in range(max_retries):
           try:
               # Calculate temperature with attempt number for dynamic adjustment
               temperature_used = get_combat_temperature(encounter_data, validation_attempt=attempt)

               # Compress conversation history before sending to AI
               messages_to_send = combat_message_compressor.process_combat_conversation(conversation_history)

               response = capture_and_fanout("T044", api_client.create_completion,
                   messages=messages_to_send,
                   model=combat_config["model"],
                   temperature=temperature_used,
                   **{k: v for k, v in combat_config.items() if k != "model"})
               
               # Track usage
               if USAGE_TRACKING_AVAILABLE:
                   try:
                       track_response(response)
                   except:
                       pass
               
               initial_response = response.choices[0].message.content.strip()
               conversation_history.append({"role": "assistant", "content": initial_response})
               
               if not is_valid_json(initial_response):
                   if attempt < max_retries - 1:
                       conversation_history.append({"role": "user", "content": "Invalid JSON format. Please try again."})
                       continue
                   else: break

               # FIX: Use the correct variable for the user input parameter
               validation_result = validate_combat_response(initial_response, encounter_data, initial_prompt_text, conversation_history)
               
               if validation_result is True:
                   break
               else:
                   if attempt < max_retries - 1:
                       # validation_result is now the full feedback string
                       conversation_history.append({"role": "user", "content": validation_result})
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
       
       # Clear processing status when ready for player input
       try:
           from core.managers.status_manager import status_manager
           status_manager.update_status("", is_processing=False)
       except Exception as e:
           debug(f"Could not clear status: {e}", category="status")
       sync_active_encounter()
       
       # REFRESH CONVERSATION HISTORY WITH LATEST DATA
       debug("STATE_CHANGE: Refreshing conversation history with latest character data...", category="combat_events")
       
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
       
       dynamic_state_parts.append(state_line)
       
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
               
               dynamic_state_parts.append(creature_line)
       
       all_dynamic_state = "\n".join(dynamic_state_parts)
       
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
       # Try to use AI-powered live initiative tracker
       live_tracker = None
       try:
           from .initiative_tracker_ai import generate_live_initiative_tracker
           # Get recent conversation for analysis (last 6 messages - enough for current round context)
           recent_conversation = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
           live_tracker = generate_live_initiative_tracker(encounter_data, recent_conversation, current_round)
           if live_tracker:
               debug("AI_TRACKER: Successfully generated live initiative tracker", category="combat_events")
       except Exception as e:
           debug(f"AI_TRACKER: Failed to generate live tracker: {e}", category="combat_events")
       
       # Parse the tracker output for both markdown and JSON
       turn_window_json = None
       if live_tracker:
           # Extract markdown tracker (everything before ```json)
           json_start = live_tracker.find("```json")
           if json_start != -1:
               initiative_display = live_tracker[:json_start].strip()
               # Extract JSON metadata
               json_end = live_tracker.find("```", json_start + 7)
               if json_end != -1:
                   json_str = live_tracker[json_start + 7:json_end].strip()
                   try:
                       turn_window_json = json.loads(json_str)
                       debug(f"AI_TRACKER: Extracted turn window: {turn_window_json.get('turn_window', [])}", category="combat_events")
                   except json.JSONDecodeError as e:
                       debug(f"AI_TRACKER: Failed to parse JSON metadata: {e}", category="combat_events")
           else:
               # No JSON found, use whole output as markdown
               initiative_display = live_tracker
       else:
           # Tracker is required for proper combat flow
           error("AI_TRACKER: Failed to generate initiative tracker - combat cannot proceed properly", category="combat_events")
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
       
       # Check if all monsters are defeated
       def check_all_monsters_defeated(encounter):
           """Check if all monsters/enemies have 0 or negative HP"""
           if not encounter or 'combatants' not in encounter:
               return False
           
           has_monsters = False
           all_defeated = True
           
           for combatant in encounter['combatants']:
               # Check if this is a monster/enemy (not player or allied NPC)
               if combatant.get('type') == 'enemy':
                   has_monsters = True
                   current_hp = combatant.get('hitPoints', 0)
                   if current_hp > 0:
                       all_defeated = False
                       break
           
           # Only return True if there were monsters and all are defeated
           return has_monsters and all_defeated
       
       # Determine the required response based on combat state
       all_monsters_defeated = check_all_monsters_defeated(encounter_data)
       if all_monsters_defeated:
           debug("COMBAT_AUTO_EXIT: All monsters defeated, modifying required response", category="combat_events")
           print("[COMBAT_MANAGER] Auto-detecting combat end: All enemies defeated")
           required_response = """--- REQUIRED RESPONSE ---
All monsters have been defeated. Pass the exit action to end combat:
1. Return structured JSON with plan, narration, combat_round, and actions
2. Include exit action with encounterId and reason: 'All enemies defeated'"""
       else:
           required_response = """--- REQUIRED RESPONSE ---
1. Narrate and resolve actions for all NPCs/monsters in initiative order until:
   - The LAST creature in this round has acted, OR
   - Initiative returns to the player
2. Stop narration at that point
3. Return structured JSON with plan, narration, combat_round, and actions"""
       
       # The tracker now always provides properly formatted output with ROUND INFO
       # Don't duplicate sections - use the tracker output as-is
       user_input_with_note = f"""{marked_initiative_display}
--- CREATURE STATES ---
{all_dynamic_state}

{ac_block}--- DICE POOLS ---
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
       
       for attempt in range(max_retries):
           try:
               print(f"[COMBAT_MANAGER] Making AI call for player action (attempt {attempt + 1}/{max_retries})")
               print(f"[COMBAT_MANAGER] Processing player input: {user_input_text[:50]}..." if len(user_input_text) > 50 else f"[COMBAT_MANAGER] Processing player input: {user_input_text}")
               
               # Update status to show AI is processing
               try:
                   from core.managers.status_manager import status_manager
                   status_manager.update_status("Combat AI processing your action...", is_processing=True)
               except Exception as e:
                   debug(f"Could not update status: {e}", category="status")
               
               # Select model config per provider
               from model_config import MODEL_PROVIDER
               if MODEL_PROVIDER == "openai":
                   combat_config = config.COMBAT_MAIN_GPT54_NONE
               elif MODEL_PROVIDER == "gemini":
                   combat_config = config.COMBAT_MAIN_GEMINI_PRO_LOW
               elif MODEL_PROVIDER == "lmstudio":
                   combat_config = config.COMBAT_MAIN_LMSTUDIO
               else:  # legacy
                   combat_config = config.COMBAT_MAIN_LEGACY

               temperature_used = get_combat_temperature(encounter_data, validation_attempt=attempt)

               print(f"DEBUG: [COMBAT] Using model: {combat_config['model']} (temp: {temperature_used}, provider: {MODEL_PROVIDER}, attempt: {attempt + 1})")

               # Compress conversation history before sending to AI
               messages_to_send = combat_message_compressor.process_combat_conversation(conversation_history)

               response = capture_and_fanout("T045", api_client.create_completion,
                   messages=messages_to_send,
                   model=combat_config["model"],
                   temperature=temperature_used,
                   **{k: v for k, v in combat_config.items() if k != "model"})
               
               # Track usage
               if USAGE_TRACKING_AVAILABLE:
                   try:
                       track_response(response)
                   except:
                       pass  # Silently ignore tracking errors
               
               ai_response = response.choices[0].message.content.strip()
               
               print(f"[COMBAT_MANAGER] AI response received ({len(ai_response)} chars)")
               
               
               # Write raw response to debug file
               os.makedirs("debug", exist_ok=True)
               with open("debug/debug_ai_response.json", "w") as debug_file:
                   json.dump({"raw_ai_response": ai_response}, debug_file, indent=2)
               
               # Temporarily add AI response for validation context
               conversation_history.append({"role": "assistant", "content": ai_response})
               
               # Check if the response is valid JSON
               if not is_valid_json(ai_response):
                   debug(f"VALIDATION: Invalid JSON response from AI (Attempt {attempt + 1}/{max_retries})", category="combat_validation")
                   if attempt < max_retries - 1:
                       # Add error feedback temporarily for next attempt
                       error_msg = "Your previous response was not a valid JSON object with 'narration' and 'actions' fields. Please provide a valid JSON response."
                       conversation_history.append({
                           "role": "user",
                           "content": error_msg
                       })
                       # Log this validation attempt
                       validation_attempts.append({
                           "attempt": attempt + 1,
                           "assistant_response": ai_response,
                           "validation_error": error_msg,
                           "error_type": "json_format",
                           "temperature_used": temperature_used
                       })
                       continue
                   else:
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
                       # Add requery feedback for next attempt
                       requery_msg = create_multiple_update_requery_prompt(parsed_response)
                       conversation_history.append({
                           "role": "user",
                           "content": requery_msg
                       })
                       # Log this validation attempt
                       validation_attempts.append({
                           "attempt": attempt + 1,
                           "assistant_response": ai_response,
                           "validation_error": requery_msg,
                           "error_type": "multiple_update_encounter",
                           "temperature_used": temperature_used
                       })
                       continue
                   else:
                       warning("VALIDATION: Max retries exceeded for multiple updateEncounter correction. Using last response.", category="combat_validation")
               
               # Validate the combat logic
               print(f"[COMBAT_MANAGER] Validating combat response (Attempt {attempt + 1}/{max_retries})")
               
               # Update status to show validation is happening
               try:
                   from core.managers.status_manager import status_manager
                   status_manager.update_status("Validating combat actions...", is_processing=True)
               except Exception as e:
                   debug(f"Could not update status: {e}", category="status")
               
               validation_result = validate_combat_response(ai_response, encounter_data, user_input_text, conversation_history)
               
               if validation_result is True:
                   valid_response = True
                   print(f"[COMBAT_MANAGER] Combat response validation PASSED on attempt {attempt + 1}")
                   debug(f"SUCCESS: Response validated successfully on attempt {attempt + 1}", category="combat_validation")
                   break
               else:
                   debug(f"VALIDATION: Response validation failed (Attempt {attempt + 1}/{max_retries})", category="combat_validation")
                   
                   # The validation result is now the full feedback string
                   feedback = validation_result
                   
                   # Log the specific validation failure for debugging
                   debug(f"VALIDATION_ATTEMPT: {attempt + 1} failed", category="combat_validation")
                   
                   if attempt < max_retries - 1:
                       # Add error feedback temporarily for next attempt
                       conversation_history.append({
                           "role": "user",
                           "content": feedback
                       })
                       # Log this validation attempt
                       validation_attempts.append({
                           "attempt": attempt + 1,
                           "assistant_response": ai_response,
                           "validation_error": feedback,
                           "error_type": "combat_logic",
                           "temperature_used": temperature_used
                       })
                       continue
                   else:
                       warning("VALIDATION: Max retries exceeded for combat validation. Using last response.", category="combat_validation")
                       break
           except Exception as e:
               error(f"FAILURE: Failed to get or validate AI response (Attempt {attempt + 1}/{max_retries})", exception=e, category="combat_events")
               if attempt < max_retries - 1:
                   continue
               else:
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
                           
               elif isinstance(new_round, int) and new_round < current_round:
                   warning(f"VALIDATION: Ignoring backward round progression from {current_round} to {new_round}", category="combat_events")
           
               
       except json.JSONDecodeError as e:
           debug(f"VALIDATION: JSON parsing error - {str(e)}", category="combat_events")
           debug("VALIDATION: Raw AI response:", category="combat_events")
           debug(ai_response, category="combat_events")
           continue
       
       # --- ACTION PROCESSING: CONSOLIDATE AND EXECUTE ---
       # This new block prevents race conditions by consolidating all character
       # updates into a single, authoritative save at the end of combat.

       # A dictionary to hold all change descriptions for each character.
       # e.g., {'eirik_hearthwise': ['used a crossbow bolt', 'took 5 damage'], ...}
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

               if character_name and changes:
                   if character_name not in final_character_updates:
                       final_character_updates[character_name] = []
                   final_character_updates[character_name].append(changes)
                   info(f"CONSOLIDATING: Queued change for {character_name}: '{changes}'", category="combat_events")
                   
                   # AMMUNITION DEBUG LOGGING
                   if any(word in changes.lower() for word in ["arrow", "bolt", "ammunition", "ammo", "expended"]):
                       debug(f"AMMO_DEBUG: Detected ammunition change for {character_name}", category="ammunition")
                       debug(f"AMMO_DEBUG: Action type: {action_type}", category="ammunition")
                       debug(f"AMMO_DEBUG: Changes text: '{changes}'", category="ammunition")
                       debug(f"AMMO_DEBUG: Added to final_character_updates queue", category="ammunition")

           elif action_type == "updateencounter":
               # Encounter updates are separate and can be processed immediately.
               encounter_id_for_update = parameters.get("encounterId", encounter_id)
               changes = parameters.get("changes", "")
               info(f"STATE_UPDATE: Processing immediate encounter update: {changes}", category="encounter_management")
               try:
                   updated_encounter_data = update_encounter.update_encounter(encounter_id_for_update, changes)
                   if updated_encounter_data:
                       encounter_data = normalize_encounter_status(updated_encounter_data)
               except Exception as e:
                   error(f"FAILURE: Failed to update encounter", exception=e, category="encounter_management")
           
           elif action_type == "exit" and is_combat_ending:
               # If combat is ending, add the authoritative HP and XP to our dictionary.
               info("CONSOLIDATING: 'exit' action detected. Calculating final HP and XP.", category="combat_events")
               xp_narrative, xp_awarded = calculate_xp()
               info(f"XP_AWARD: Calculated {xp_awarded} XP per participant.", category="xp_tracking")
               conversation_history.append({"role": "user", "content": f"XP Awarded: {xp_narrative}"})
               save_json_file(conversation_history_file, conversation_history)

               for creature in encounter_data.get("creatures", []):
                   if creature.get("type") in ["player", "npc"]:
                       character_name = creature.get("name")
                       if character_name:
                           if character_name not in final_character_updates:
                               final_character_updates[character_name] = []

                           # CRITICAL FIX: Don't set HP from encounter file - character file is source of truth
                           # The encounter file may have stale HP values that would overwrite healing done during combat
                           # Only award XP when combat ends

                           # COMMENTED OUT: This line was setting HP from the encounter file, which can be stale
                           # final_hp = creature.get("currentHitPoints")
                           # final_character_updates[character_name].append(f"set hitPoints to {final_hp}")

                           if xp_awarded > 0:
                               final_character_updates[character_name].append(f"awarded {xp_awarded} experience points")

       # STEP 2: EXECUTE the consolidated updates. This is the only place character files are saved.
       if final_character_updates:
           info("STATE_UPDATE: Applying all consolidated updates.", category="character_updates")
           
           # AMMUNITION DEBUG
           debug(f"AMMO_DEBUG: Processing {len(final_character_updates)} character updates", category="ammunition")
           
           for character_name, changes_list in final_character_updates.items():
               # Join all changes into one comprehensive request string.
               final_change_string = "Following the turn's events: " + ", and ".join(changes_list) + "."
               info(f"FINAL_CHANGE_STRING for {character_name}: {final_change_string}", category="character_updates")
               
               # AMMUNITION DEBUG
               if any(word in final_change_string.lower() for word in ["arrow", "bolt", "ammunition", "ammo", "expended"]):
                   debug(f"AMMO_DEBUG: About to update ammunition for {character_name}", category="ammunition")
                   debug(f"AMMO_DEBUG: Final change string: '{final_change_string}'", category="ammunition")

               try:
                   update_success = update_character_info(character_name, final_change_string)
                   if not update_success:
                       error(f"FAILURE: Final consolidated update failed for {character_name}.", category="character_updates")
                   else:
                       # AMMUNITION DEBUG
                       if any(word in final_change_string.lower() for word in ["arrow", "bolt", "ammunition", "ammo", "expended"]):
                           debug(f"AMMO_DEBUG: Successfully processed ammunition update for {character_name}", category="ammunition")
               except Exception as e:
                   error(f"FAILURE: Critical error during consolidated update for {character_name}", exception=e, category="character_updates")
                   # AMMUNITION DEBUG
                   if any(word in final_change_string.lower() for word in ["arrow", "bolt", "ammunition", "ammo", "expended"]):
                       debug(f"AMMO_DEBUG: Exception during ammunition update: {str(e)}", category="ammunition")

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