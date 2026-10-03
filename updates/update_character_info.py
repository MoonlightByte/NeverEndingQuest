# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# UPDATE_CHARACTER_INFO.PY - CHARACTER DATA MANAGEMENT LAYER
# ============================================================================
# 
# ARCHITECTURE ROLE: Character State Management - AI-Driven Updates with Validation
# 
# DEBUG & TROUBLESHOOTING:
# =======================
# - All character updates are logged to: debug/character_updates_log.json
# - Each log entry contains:
#   - timestamp: When the update occurred
#   - character_name: Character being updated
#   - changes_requested: What the user/DM requested
#   - raw_ai_response: EXACT JSON returned by AI (shows delta-only efficiency)
#   - parsed_updates: Parsed version of the response
#   - validation_results: Schema validation outcome
#   - final_outcome: success/failure
# 
# PERFORMANCE MONITORING:
# ======================
# To check update efficiency:
#   jq '.updates[-10:] | .[] | {character: .character_name, size: (.raw_ai_response | length)}' debug/character_updates_log.json
# 
# Common update sizes (delta-only):
# - Currency only: ~60 characters
# - HP only: ~40 characters  
# - Single spell slot: ~120 characters
# - Full spell restoration: ~1200 characters
# 
# SPECIAL HANDLING:
# ================
# - temporaryEffects: Complete array replacement (not merged)
# - Equipment: Smart merging by item_name
# - Ammunition: engine-owned stock (core/nql/ammunition); T079 returns quantityDelta per row, never totals
# - Currency: engine-owned (core/nql/currency); T079 returns currencyDelta (signed per coin), never totals
# 
# COMMON ISSUES & SOLUTIONS:
# =========================
# 1. "Invalid format specifier" - Check debug log for malformed AI response
# 2. Effects not clearing - Verify temporaryEffects is in complete_replacement_arrays
# 3. Currency not updating - T079 must return currencyDelta; a 'currency' totals object is refused
# 4. Equipment not merging - Check item_name matches exactly
# 
# This module provides secure, validated character data updates using AI to
# interpret natural language change requests while preventing data corruption
# through intelligent merging and validation strategies.
# 
# KEY RESPONSIBILITIES:
# - AI-driven character data interpretation and updates
# - Deep merge functionality to prevent data loss
# - Critical field validation and corruption prevention  
# - Schema validation and data integrity enforcement
# - Character backup and rollback capabilities
# 
# DATA INTEGRITY DESIGN:
# - DEEP MERGE STRATEGY: Preserves nested object data during partial updates
# - CRITICAL FIELD PROTECTION: Validates essential fields aren't deleted
# - CORRUPTION PREVENTION: Blocks updates that would destroy important data
# - ROLLBACK CAPABILITY: Maintains original data for recovery if needed
# 
# AI INTEGRATION ARCHITECTURE:
# - Natural language change processing via OpenAI models
# - Model-specific optimization (different models for players vs NPCs)
# - Intelligent prompt engineering to prevent partial object replacement
# - Multi-attempt processing with validation between attempts
# 
# VALIDATION LAYERS:
# 1. Schema Validation: Ensures data structure compliance
# 2. Critical Field Validation: Prevents accidental deletion of key data
# 3. AI Character Validation: Post-update character sheet validation
# 4. Character Effects Validation: Equipment and ability effects validation
# 
# DATA CORRUPTION PREVENTION:
# - Problem: AI returning partial objects that replace entire nested structures
# - Solution: Deep merge + critical field validation + enhanced prompting
# - Example: Spell slot updates preserve spellcasting ability, DC, spells list
# - Debugging: Comprehensive logging of problematic updates for analysis
# 
# ARCHITECTURAL INTEGRATION:
# - Core dependency for main.py character update actions
# - Integrates with conversation_utils.py for character data display
# - Uses module_path_manager.py for file location resolution
# - Supports character_validator.py for post-update validation
# 
# DESIGN PATTERNS:
# - Command Pattern: Encapsulated character update operations
# - Template Method: Standardized update workflow with role-specific variations
# - Strategy Pattern: Different AI models for different character types
# - Guard Pattern: Multiple validation layers preventing corruption
# 
# This module ensures character data integrity while providing flexible,
# AI-driven updates that understand natural language change requests.
# ============================================================================

import json
import copy
import shutil
import os
import threading
from datetime import datetime
from jsonschema import validate, ValidationError
import config
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.capture.live_provider_call import (
    LiveProviderCompletedError,
    LiveProviderSuperseded,
)
register_callsite("T079", "updates/update_character_info.py", 1692)
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any, Optional

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass
import time
import re
# Model configuration loaded via config dicts in model_config.py
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_write_json, safe_read_json
from utils.encoding_utils import safe_json_load
from core.validation.character_validator import AICharacterValidator, armor_contract_errors
from core.validation.character_effects_validator import AICharacterEffectsValidator
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name(__name__)

# Constants
TEMPERATURE = 0.7
VALIDATION_TEMPERATURE = 0.1  # Lower temperature for validation

# A character update is a read -> model decision -> merge -> write transaction.
# Atomic writes prevent truncated JSON, but they do not prevent two transactions
# from reading the same snapshot and overwriting one another. Keep distinct
# characters parallel while serializing the complete transaction per file.
_CHARACTER_UPDATE_LOCKS = {}
_CHARACTER_UPDATE_LOCKS_GUARD = threading.Lock()

# ANSI escape codes - REMOVED per CLAUDE.md guidelines
# All color codes have been removed to prevent Windows console encoding errors

def load_schema():
    """Load the unified character schema"""
    with open("schemas/char_schema.json", "r") as schema_file:
        return json.load(schema_file)

def load_conversation_history():
    data = safe_read_json("modules/conversation_history/conversation_history.json")
    return data if data else []

def normalize_character_name(character_name):
    """Convert character name to safe filename format"""
    import re
    
    # Convert to lowercase and replace problematic characters
    name = character_name.strip().lower()
    
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    
    # Replace apostrophes with underscores (handles names like "Mac'Davier")
    name = name.replace("'", "_")
    
    # Replace any other non-alphanumeric characters with underscores
    name = re.sub(r'[^a-z0-9_]', '_', name)
    
    # Remove multiple consecutive underscores
    name = re.sub(r'_+', '_', name)
    
    # Remove leading/trailing underscores
    name = name.strip('_')
    
    return name

def find_character_file_fuzzy(character_name):
    """Find a character file using fuzzy matching
    
    This function attempts to find a character file that matches the given name,
    even if the file name doesn't exactly match the character name.
    
    Args:
        character_name (str): The character name to search for
        
    Returns:
        str: The matched filename (without .json extension) or None if no match found
        
    Examples:
        - "Ranger Thane" might match "corrupted_ranger_thane.json"
        - "Scout Kira" would match "scout_kira.json"
    """
    import glob
    import os
    from difflib import SequenceMatcher
    from utils.enhanced_logger import debug
    
    # First try exact match with normalized name
    normalized_name = normalize_character_name(character_name)
    
    # Use the unified characters directory
    character_dir = "characters"
    character_files = glob.glob(os.path.join(character_dir, "*.json"))
    
    # Try exact match first
    exact_match_file = os.path.join(character_dir, f"{normalized_name}.json")
    if os.path.exists(exact_match_file):
        # Suppress routine exact match logging - this is expected behavior
        # debug(f"FUZZY_MATCH: Exact match found for '{character_name}' -> '{normalized_name}'", category="character_updates")
        return normalized_name
    
    # Prepare for fuzzy matching
    input_lower = character_name.lower()
    input_words = set(input_lower.split())
    input_normalized = input_lower.replace("_", " ")
    
    best_match = None
    best_score = 0.0
    
    for char_file in character_files:
        filename = os.path.splitext(os.path.basename(char_file))[0]
        
        # Skip player character files (they should match exactly)
        if filename in ['eirik_hearthwise', 'wizard_player']:
            continue
            
        # Check various matching strategies
        file_lower = filename.lower()
        file_words = set(file_lower.replace("_", " ").split())
        
        # Strategy 1: Word subset matching
        if input_words.issubset(file_words) or file_words.issubset(input_words):
            score = len(input_words.intersection(file_words)) / max(len(input_words), len(file_words))
            if score > best_score:
                best_score = score
                best_match = filename
                # debug(f"FUZZY_MATCH: Word subset match '{character_name}' -> '{filename}' (score: {score:.2f})", category="character_updates")
        
        # Strategy 2: Normalized partial match
        if input_normalized in file_lower.replace("_", " "):
            score = len(input_normalized) / len(file_lower)
            if score > best_score:
                best_score = score
                best_match = filename
                # debug(f"FUZZY_MATCH: Partial match '{character_name}' -> '{filename}' (score: {score:.2f})", category="character_updates")
        
        # Strategy 3: Sequence matching
        sequence_score = SequenceMatcher(None, input_lower, file_lower).ratio()
        if sequence_score > best_score:
            best_score = sequence_score
            best_match = filename
            # debug(f"FUZZY_MATCH: Sequence match '{character_name}' -> '{filename}' (score: {sequence_score:.2f})", category="character_updates")
    
    # Return match if score is high enough
    # Note: Threshold increased from 0.5 to 0.65 to prevent false matches like "Scout Elen" -> "Scout Kira"
    # while still allowing valid matches like "Ranger Thane" -> "corrupted_ranger_thane" (0.667)
    if best_match and best_score >= 0.65:
        # debug(f"FUZZY_MATCH: Best match for '{character_name}' is '{best_match}' (score: {best_score:.2f})", category="character_updates")
        return best_match
    else:
        # debug(f"FUZZY_MATCH: No suitable match found for '{character_name}' (best score: {best_score:.2f})", category="character_updates")
        return None

def detect_character_role(character_name):
    """Detect character role from existing data or file location"""
    # Get current module from party tracker for consistent path resolution
    try:
        party_tracker_data = safe_json_load("party_tracker.json")
        current_module = party_tracker_data.get("module", "").replace(" ", "_") if party_tracker_data else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    
    # First try player path
    player_path = path_manager.get_character_path(character_name)
    try:
        with open(player_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('character_role', 'player')
    except FileNotFoundError:
        pass
    
    # Then try NPC path
    npc_path = path_manager.get_character_path(character_name)
    try:
        with open(npc_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('character_role', 'npc')
    except FileNotFoundError:
        pass
    
    # Default to NPC if not found (most characters created are NPCs)
    return 'npc'

def fuzzy_match_character_name(input_name, party_tracker_data):
    """
    Try to find a character using fuzzy matching logic.
    Returns the correct character name if found, None otherwise.
    """
    input_lower = input_name.lower().strip()
    
    # Check party members (exact match first)
    for member in party_tracker_data.get("partyMembers", []):
        if member.lower() == input_lower:
            return member
    
    # Check party NPCs (exact match first)
    for npc in party_tracker_data.get("partyNPCs", []):
        npc_name = npc.get("name", "")
        if npc_name.lower() == input_lower:
            return npc_name
    
    # Try partial matches for party NPCs (e.g., "kira" matches "Scout Kira")
    for npc in party_tracker_data.get("partyNPCs", []):
        npc_name = npc.get("name", "")
        npc_lower = npc_name.lower()
        # Check if input is contained in the NPC name
        if input_lower in npc_lower:
            # debug(f"FUZZY_MATCH: Matched '{input_name}' to '{npc_name}' via partial match", category="character_updates")
            return npc_name
        # Check if any word in NPC name matches input
        npc_words = npc_lower.split()
        if input_lower in npc_words:
            # debug(f"FUZZY_MATCH: Matched '{input_name}' to '{npc_name}' via word match", category="character_updates")
            return npc_name
        
        # Check if normalized input matches part of normalized NPC name
        # This handles cases like "ranger_thane" matching "Corrupted Ranger Thane"
        input_normalized = input_lower.replace("_", " ")
        if input_normalized in npc_lower:
            # debug(f"FUZZY_MATCH: Matched '{input_name}' to '{npc_name}' via normalized partial match", category="character_updates")
            return npc_name
        
        # Check each word in the normalized input against the NPC name
        input_words = input_normalized.split()
        for word in input_words:
            if word in npc_lower and len(word) > 2:  # Skip very short words
                # debug(f"FUZZY_MATCH: Matched '{input_name}' to '{npc_name}' via word '{word}'", category="character_updates")
                return npc_name
    
    # Try checking character files in the module
    try:
        current_module = party_tracker_data.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(current_module)
        import glob
        import os
        
        # Get all character files
        character_files = glob.glob(os.path.join(path_manager.module_dir, "characters", "*.json"))
        
        for char_file in character_files:
            try:
                char_data = safe_read_json(char_file)
                if char_data and "name" in char_data:
                    char_name = char_data["name"]
                    if char_name.lower() == input_lower:
                        return char_name
                    # Check partial match
                    if input_lower in char_name.lower():
                        # debug(f"FUZZY_MATCH: Matched '{input_name}' to '{char_name}' via file search", category="character_updates")
                        return char_name
            except:
                continue
    except Exception as e:
        # debug(f"FUZZY_MATCH: Error searching character files: {str(e)}", category="character_updates")
        pass

    return None

def get_character_path(character_name, character_role=None):
    """Get the appropriate file path for a character"""
    # Get current module from party tracker for consistent path resolution
    try:
        party_tracker_data = safe_json_load("party_tracker.json")
        current_module = party_tracker_data.get("module", "").replace(" ", "_") if party_tracker_data else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    
    # Use the updated path manager that handles unified/legacy fallback
    return path_manager.get_character_path(character_name)

def process_conversation_history(history, character_role):
    """Process conversation history based on character role"""
    if character_role == 'player':
        # Player-specific processing
        for message in history:
            if message["role"] == "user" and message["content"].startswith("Leveling Dungeon Master Guidance"):
                message["content"] = "DM Guidance: Proceed with leveling up the player character given the 5th Edition role playing game rules. Only level the player one level at a time to ensure no mistakes are made. You must ask the player for important decisions and choices they would have control over. After the player has provided the needed information then use the 'updatePlayerInfo' to pass all changes to the players character sheet and include the experience goal for the next level. Do not update the player's information in segments."
    # NPC processing can be added here if needed
    return history

def format_schema_for_prompt(schema, character_role):
    """Format schema information for inclusion in the prompt"""
    if character_role == 'player':
        schema_info = "Character Schema - Valid fields and values:\n\n"
    else:
        schema_info = "NPC Schema - Valid fields and values:\n\n"
    
    properties = schema.get('properties', {})
    
    # Group fields by type for better readability
    simple_fields = []
    enum_fields = []
    array_fields = []
    object_fields = []
    
    for field, definition in properties.items():
        field_type = definition.get('type', 'unknown')
        
        if 'enum' in definition:
            enum_fields.append(f"- {field}: Must be one of {definition['enum']}")
        elif field_type == 'array':
            items_type = definition.get('items', {}).get('type', 'object')
            if items_type == 'object':
                array_fields.append(f"- {field}: Array of objects")
            else:
                array_fields.append(f"- {field}: Array of {items_type}")
        elif field_type == 'object':
            object_fields.append(f"- {field}: Object with specific structure")
        else:
            simple_fields.append(f"- {field}: {field_type}")
    
    # Add field categories to schema info
    if enum_fields:
        schema_info += "Enum Fields (must match exactly):\n" + "\n".join(enum_fields) + "\n\n"
    
    if simple_fields:
        schema_info += "Simple Fields:\n" + "\n".join(simple_fields) + "\n\n"
    
    if array_fields:
        schema_info += "Array Fields:\n" + "\n".join(array_fields) + "\n\n"
    
    if object_fields:
        schema_info += "Object Fields:\n" + "\n".join(object_fields) + "\n\n"
    
    # Add role-specific examples
    # Add common item type guidance
    schema_info += """
CRITICAL - Valid item_type values (MUST use one of these EXACTLY):
- "weapon" - swords, bows, daggers, melee and ranged weapons
- "armor" - body armor and shields only (armor_category and ac_base required); cloaks, boots, gloves and other worn magic items are "miscellaneous" with an item_subtype
- "ammunition" - arrows, bolts, sling bullets, thrown weapon ammo
- "consumable" - potions, scrolls, food, rations, anything consumed when used
- "equipment" - tools, torches, rope, containers, utility items
- "miscellaneous" - rings, amulets, wands, truly miscellaneous items only

NEVER use: "wondrous item", "magic item", "magical" or any other value!
Every equipment entry carries all four of item_name, item_type, description and quantity (the schema refuses an entry missing any of them).
Valid item_subtype values (when given): scroll, potion, wand, ring, amulet, cloak, boots, gloves, helmet, rod, staff, food, other.

NOTE: Enhanced categorization system fixes GitHub issue #45 (inconsistent item storage)

Enhanced Item Type Mappings:
- Arrows/Bolts/Bullets -> item_type: "ammunition"
- Travel Ration/Food -> item_type: "consumable", item_subtype: "food"
- Torch/Rope/Tools -> item_type: "equipment", item_subtype: "other"
- Studded Leather Armor -> item_type: "armor", description: "Light armor. AC 12 + Dex modifier."
- Cloak of Elvenkind -> item_type: "miscellaneous", item_subtype: "cloak"
- Ring of Protection -> item_type: "miscellaneous", item_subtype: "ring"
- Wand of Magic Missiles -> item_type: "miscellaneous", item_subtype: "wand"
- Potion of Healing -> item_type: "consumable", item_subtype: "potion"
- Scroll of Fireball -> item_type: "consumable", item_subtype: "scroll"
"""
    
    if character_role == 'player':
        schema_info += """
Equipment Array Example (a NEW item: quantity = how many were acquired):
[{"item_name": "Sword", "item_type": "weapon", "description": "Sharp blade", "quantity": 1}]

Equipment Stock Change Example (an item ALREADY on the sheet: signed change, never the new count):
[{"item_name": "Travel Ration", "quantityDelta": 3}]   or   [{"item_name": "Torch", "quantityDelta": -1}]

Currency Delta Example (signed change per coin, never totals):
{"currencyDelta": {"gold": -50, "silver": 10}}

Pool Delta Examples (signed change, never a resulting count):
{"hpDelta": -7}
{"spellSlotDelta": {"level2": -1}}
{"featureUseDelta": {"Channel Divinity (2/rest)": -1}}
{"tempHpGrant": 10}

Ammunition Stock Change Example (a row ALREADY on the sheet: signed change, never the new count):
[{"name": "Crossbow bolt", "quantityDelta": -3}]

Ammunition Example (a NEW row only: quantity = how many were acquired):
[{"name": "Arrows", "quantity": 20, "description": "Standard arrows"}]
"""
    else:
        schema_info += """
Equipment Array Example (a NEW item: quantity = how many were acquired):
[{"item_name": "Chain Mail", "item_type": "armor", "description": "Heavy armor", "quantity": 1}]

Equipment Stock Change Example (an item ALREADY on the sheet: signed change, never the new count):
[{"item_name": "Travel Ration", "quantityDelta": -1}]

AttacksAndSpellcasting vs Actions:
- Use attacksAndSpellcasting for standard attack format
- Actions array is for 5e standard format (optional)

Combat Damage Note:
When NPCs deal damage in combat, do NOT update their action arrays. Only update when the NPC gains new abilities or equipment.
"""
    
    return schema_info

def normalize_status_and_condition(data, character_role):
    """Normalize status and condition fields based on character role"""
    # This fix applies to all character types
    
    # Force 'status' to lowercase if it exists
    if 'status' in data and isinstance(data.get('status'), str):
        data['status'] = data['status'].lower()

    # Force 'condition' to lowercase if it exists
    if 'condition' in data and isinstance(data.get('condition'), str):
        data['condition'] = data['condition'].lower()
        
        # Also correct common synonyms to match the schema
        if data['condition'] == 'normal':
            data['condition'] = 'none'

    # Ensure all items in 'condition_affected' are lowercase
    if 'condition_affected' in data and isinstance(data.get('condition_affected'), list):
        data['condition_affected'] = [str(c).lower() for c in data['condition_affected']]

    return data

CHARACTER_NAMED_ARRAYS = {
    'ammunition': 'name',
    'attacksAndSpellcasting': 'name',
    'classFeatures': 'name',
    'equipment': 'item_name',
    'equipment_effects': 'name',
    'feats': 'name',
    'racialTraits': 'name',
}


def deep_merge_dict(base_dict, update_dict):
    """Recursively merge update_dict into base_dict, preserving nested structures"""
    result = copy.deepcopy(base_dict)
    
    # Define arrays that need special merge handling (identified by name fields)
    named_arrays = CHARACTER_NAMED_ARRAYS
    
    # Arrays that should be completely replaced, not merged
    complete_replacement_arrays = ['temporaryEffects']
    
    for key, value in update_dict.items():
        if key in complete_replacement_arrays:
            # Complete replacement for these arrays
            result[key] = copy.deepcopy(value)
        elif key == "equipment_effects" and value == []:
            # Delta-only responses omit unchanged fields. An explicitly
            # present empty effect list therefore means all equipment effects
            # were removed (for example, a destroyed shield), not "no-op".
            result[key] = []
        elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = deep_merge_dict(result[key], value)
        elif key in named_arrays and isinstance(result.get(key), list) and isinstance(value, list):
            # Special handling for arrays with named items
            name_field = named_arrays[key]
            # print(f"[DEBUG deep_merge_dict] Processing named array: {key}")
            if key == 'equipment':
                result[key] = merge_equipment_arrays(result[key], value)
            elif key == 'ammunition':
                # print(f"[DEBUG deep_merge_dict] Calling merge_ammunition_arrays")
                result[key] = merge_ammunition_arrays(result[key], value)
                # print(f"[DEBUG deep_merge_dict] merge_ammunition_arrays returned successfully")
            else:
                # For other named arrays, use generic merge
                result[key] = merge_named_arrays(result[key], value, name_field)
        else:
            # Replace or add the value
            result[key] = copy.deepcopy(value)
    
    return result

def merge_equipment_arrays(base_equipment, update_equipment):
    """Merge equipment arrays by item name, preserving existing items and removing zero-quantity items"""
    result = copy.deepcopy(base_equipment)
    
    # Create a mapping of item names to indices in the base equipment
    item_name_to_index = {}
    for i, item in enumerate(result):
        item_name = item.get('item_name', '')
        if item_name:
            item_name_to_index[item_name] = i
    
    # Process updates
    for update_item in update_equipment:
        update_item_name = update_item.get('item_name', '')
        if not update_item_name:
            continue
            
        if update_item_name in item_name_to_index:
            # Update existing item by merging dictionaries
            index = item_name_to_index[update_item_name]
            result[index] = deep_merge_dict(result[index], update_item)
        else:
            # Add new item if it doesn't exist
            result.append(copy.deepcopy(update_item))
    
    # Remove items with zero or negative quantity or marked with _remove flag
    result = [item for item in result if item.get('quantity', 1) > 0 and not item.get('_remove', False)]
    
    return result

def merge_ammunition_arrays(base_ammunition, update_ammunition):
    """Merge ammunition arrays by name, adding quantities for existing items and ensuring schema compliance"""
    # DEBUG: Check what we're receiving
    # print(f"[DEBUG merge_ammunition_arrays] base_ammunition type: {type(base_ammunition)}, value: {base_ammunition}")
    # print(f"[DEBUG merge_ammunition_arrays] update_ammunition type: {type(update_ammunition)}, value: {update_ammunition}")
    
    # Create a lookup map from the base ammunition array
    ammo_lookup = {}
    for ammo in base_ammunition:
        # Use lowercase name as key for case-insensitive matching
        key = ammo.get('name', '').lower().strip()
        if key:
            ammo_lookup[key] = copy.deepcopy(ammo)
    
    # Process updates
    for update_ammo in update_ammunition:
        update_name = update_ammo.get('name', '').strip()
        update_name_lower = update_name.lower()
        update_quantity = update_ammo.get('quantity', 0)
        
        if not update_name:
            continue
        
        # Check if this ammunition already exists (case-insensitive)
        if update_name_lower in ammo_lookup:
            if update_ammo.get('_remove'):
                # AM-b: a model-authored quantity 0 removes the row entirely.
                del ammo_lookup[update_name_lower]
                continue
            # Add to existing ammunition quantity (supports negative for removals)
            ammo_lookup[update_name_lower]['quantity'] += update_quantity
            # If the update includes a description and the base doesn't have one, add it
            if 'description' in update_ammo and 'description' not in ammo_lookup[update_name_lower]:
                ammo_lookup[update_name_lower]['description'] = update_ammo['description']
        else:
            # New ammunition type - only add if positive quantity
            if update_quantity > 0:
                # Ensure schema compliance
                new_ammo = {
                    'name': update_name,  # Use original casing
                    'quantity': update_quantity,
                    'description': update_ammo.get('description', 'Standard ammunition.')
                }
                ammo_lookup[update_name_lower] = new_ammo
    
    # Convert back to array. AM-b: an empty quiver stays on the sheet at 0 (the
    # engine stock keeps its id and any recovery count); only a negative row,
    # which no engine answer produces, is dropped.
    result = []
    for ammo in ammo_lookup.values():
        if ammo.get('quantity', 0) >= 0:
            # Ensure description field exists for schema compliance
            if 'description' not in ammo:
                ammo['description'] = f"Standard {ammo.get('name', 'ammunition').lower()}."
            result.append(ammo)
    
    # Sort by name for consistent ordering
    result.sort(key=lambda x: x.get('name', '').lower())
    
    return result

def merge_named_arrays(base_array, update_array, name_field):
    """Generic merge for arrays of objects identified by a name field"""
    # Create lookup map from base array
    lookup = {}
    for item in base_array:
        key = item.get(name_field, '').lower().strip()
        if key:
            lookup[key] = copy.deepcopy(item)
    
    # Process updates
    for update_item in update_array:
        update_name = update_item.get(name_field, '').strip()
        update_name_lower = update_name.lower()
        
        if not update_name:
            continue
        
        if update_name_lower in lookup:
            # Update existing item - merge all fields
            for field, value in update_item.items():
                lookup[update_name_lower][field] = value
        else:
            # Add new item
            lookup[update_name_lower] = copy.deepcopy(update_item)
    
    # Convert back to array and sort by name
    result = list(lookup.values())
    result.sort(key=lambda x: x.get(name_field, '').lower())
    
    return result

def fix_item_types(updates):
    """Fix common item_type mistakes before validation"""
    # Map of common wrong values to correct values
    item_type_fixes = {
        # Existing fixes
        "wondrous item": "miscellaneous",
        "wondrous": "miscellaneous",
        "magic item": "miscellaneous",
        "magical item": "miscellaneous",
        "magical": "miscellaneous",
        "equipment": "equipment",  # Allow equipment instead of forcing to miscellaneous
        "potion": "consumable",
        "scroll": "consumable",
        # New fixes for common issues
        "arrows": "ammunition",
        "ammunition": "ammunition",
        "ammo": "ammunition",
        "ration": "consumable",
        "food": "consumable",
        "torch": "equipment",
        "tool": "equipment",
        "rope": "equipment",
        "container": "equipment",
        # Keep existing
        "cloak": "armor",
        "ring": "miscellaneous",
        "amulet": "miscellaneous",
        "wand": "miscellaneous",
        "rod": "miscellaneous",
        "staff": "weapon"
    }
    
    # Fix equipment array if present
    if 'equipment' in updates and isinstance(updates['equipment'], list):
        for item in updates['equipment']:
            if 'item_type' in item and isinstance(item['item_type'], str):
                item_type_lower = item['item_type'].lower()
                if item_type_lower in item_type_fixes:
                    old_type = item['item_type']
                    item['item_type'] = item_type_fixes[item_type_lower]
                    debug(f"VALIDATION: Auto-corrected item_type: '{old_type}' -> '{item['item_type']}' for {item.get('item_name', 'unknown item')}", category="character_validation")
    
    return updates

def fix_injury_types(updates):
    """Fix common injury type mistakes before validation"""
    # Map of common wrong values to correct values
    valid_injury_types = ["wound", "poison", "disease", "curse", "other"]
    
    if 'injuries' in updates and isinstance(updates['injuries'], list):
        for injury in updates['injuries']:
            if isinstance(injury, dict) and 'type' in injury:
                injury_type = injury['type'].lower()
                
                # Map common invalid types to valid ones
                injury_type_fixes = {
                    "scar": "other",
                    "scars": "other",
                    "burn": "wound",
                    "burns": "wound",
                    "cut": "wound",
                    "cuts": "wound",
                    "bruise": "wound",
                    "bruises": "wound",
                    "fracture": "wound",
                    "break": "wound",
                    "broken": "wound",
                    "infection": "disease",
                    "infected": "disease",
                    "poisoned": "poison",
                    "cursed": "curse",
                    "hex": "curse",
                    "hexed": "curse",
                    "other": "other"
                }
                
                # Fix the injury type if it's invalid
                if injury_type not in valid_injury_types:
                    fixed_type = injury_type_fixes.get(injury_type, "other")
                    warning(f"VALIDATION: Fixed invalid injury type '{injury['type']}' to '{fixed_type}'", category="character_validation")
                    injury['type'] = fixed_type
                else:
                    # Ensure the type is in lowercase even if it's valid
                    injury['type'] = injury_type
    
    return updates

def validate_critical_fields_preserved(original_data, updated_data, character_name):
    """Validate that critical nested fields are not accidentally deleted"""
    critical_paths = [
        ('spellcasting', 'ability'),
        ('spellcasting', 'spellSaveDC'),
        ('spellcasting', 'spellAttackBonus'),
        ('spellcasting', 'spells'),
    ]
    
    # Also check for equipment array preservation
    critical_arrays = ['equipment', 'ammunition']
    
    warnings = []
    
    for path in critical_paths:
        # Check if the field existed in original but is missing in updated
        original_value = original_data
        updated_value = updated_data
        path_exists_in_original = True
        path_exists_in_updated = True
        
        try:
            for key in path:
                original_value = original_value[key]
        except (KeyError, TypeError):
            path_exists_in_original = False
        
        try:
            for key in path:
                updated_value = updated_value[key]
        except (KeyError, TypeError):
            path_exists_in_updated = False
        
        if path_exists_in_original and not path_exists_in_updated:
            field_path = '.'.join(path)
            warnings.append(f"Critical field '{field_path}' was deleted from {character_name}")
    
    # Check for massive array reductions (potential data loss)
    for array_name in critical_arrays:
        if array_name in original_data and array_name in updated_data:
            original_array = original_data[array_name]
            updated_array = updated_data[array_name]
            
            if isinstance(original_array, list) and isinstance(updated_array, list):
                original_count = len(original_array)
                updated_count = len(updated_array)
                
                # Warn if we lost more than 80% of items (likely indicates replacement instead of merge)
                if original_count > 5 and updated_count < (original_count * 0.2):
                    warnings.append(f"Critical array reduction: {array_name} went from {original_count} to {updated_count} items in {character_name}")
    
    return warnings

def validate_character_data(data, schema, character_name):
    """Validate character data against schema"""
    try:
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        error_msg = f"Validation error for {character_name}: {e.message}"
        if e.path:
            error_msg += f" at path: {'.'.join(map(str, e.path))}"
        return False, error_msg

def purge_invalid_fields(data, schema, character_name=""):
    """
    Remove fields from character data that are not in the schema.
    This prevents validation failures from AI-added invalid fields.
    
    Args:
        data (dict): Character data to clean
        schema (dict): Schema to validate against
        character_name (str): Character name for logging
    
    Returns:
        tuple: (cleaned_data, removed_fields_list)
    """
    if not isinstance(data, dict) or not isinstance(schema, dict):
        return data, []
    
    schema_properties = schema.get('properties', {})
    removed_fields = []
    cleaned_data = {}
    
    for field, value in data.items():
        if field in schema_properties:
            # Field exists in schema - keep it (but recursively clean if it's an object)
            field_schema = schema_properties[field]
            if isinstance(value, dict) and field_schema.get('type') == 'object':
                # Recursively clean nested objects
                if 'properties' in field_schema:
                    cleaned_value, nested_removed = purge_invalid_fields(value, field_schema, f"{character_name}.{field}")
                    cleaned_data[field] = cleaned_value
                    if nested_removed:
                        removed_fields.extend([f"{field}.{nf}" for nf in nested_removed])
                else:
                    cleaned_data[field] = value
            else:
                cleaned_data[field] = value
        else:
            # Field not in schema - remove it
            removed_fields.append(field)
            warning(f"VALIDATION: PURGED invalid field '{field}' from {character_name}", category="character_validation")
    
    return cleaned_data, removed_fields

def create_character_backup(character_path, backup_reason="update"):
    """
    Create a timestamped backup of a character file before making changes
    
    Args:
        character_path (str): Path to the character file
        backup_reason (str): Reason for backup (for naming)
    
    Returns:
        str: Path to the backup file, or None if backup failed
    """
    if not os.path.exists(character_path):
        error(f"FAILURE: Cannot backup: Character file does not exist: {character_path}", category="file_operations")
        return None
    
    try:
        # Generate timestamp for unique backup naming
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create backup filename
        base_name = os.path.basename(character_path)
        name_without_ext = os.path.splitext(base_name)[0]
        backup_filename = f"{name_without_ext}.backup_{backup_reason}_{timestamp}.json"
        backup_path = os.path.join(os.path.dirname(character_path), backup_filename)
        
        # Copy the file
        shutil.copy2(character_path, backup_path)
        debug(f"FILE_OP: Created backup: {backup_filename}", category="file_operations")
        
        # Also create a "latest" backup that's easier to find
        latest_backup_path = character_path + ".backup_latest"
        shutil.copy2(character_path, latest_backup_path)
        
        return backup_path
        
    except Exception as e:
        error(f"FAILURE: Failed to create backup", exception=e, category="file_operations")
        return None

def cleanup_old_backups(character_path, max_backups=5):
    """
    Clean up old backup files, keeping only the most recent ones
    
    Args:
        character_path (str): Path to the character file
        max_backups (int): Maximum number of backup files to keep
    """
    try:
        directory = os.path.dirname(character_path)
        base_name = os.path.basename(character_path)
        name_without_ext = os.path.splitext(base_name)[0]
        
        # Find all backup files for this character
        backup_files = []
        for file in os.listdir(directory):
            if file.startswith(f"{name_without_ext}.backup_") and file.endswith(".json"):
                # Skip the "latest" backup file
                if not file.endswith(".backup_latest"):
                    backup_path = os.path.join(directory, file)
                    # Get file modification time for sorting
                    mtime = os.path.getmtime(backup_path)
                    backup_files.append((mtime, backup_path))
        
        # Sort by modification time (newest first)
        backup_files.sort(reverse=True)
        
        # Remove old backups if we have too many
        if len(backup_files) > max_backups:
            files_to_remove = backup_files[max_backups:]
            for _, file_path in files_to_remove:
                try:
                    os.remove(file_path)
                    debug(f"FILE_OP: Removed old backup: {os.path.basename(file_path)}", category="file_operations")
                except Exception as e:
                    warning(f"FILE_OP: Could not remove old backup {file_path}", category="file_operations")
                    
    except Exception as e:
        warning(f"FILE_OP: Backup cleanup failed", category="file_operations")

def restore_character_from_backup(character_name, backup_type="latest", character_role=None):
    """
    Restore a character from a backup file
    
    Args:
        character_name (str): Name of the character to restore
        backup_type (str): Type of backup to restore ("latest", or specific timestamp)
        character_role (str, optional): Character role, auto-detected if None
    
    Returns:
        bool: True if successful, False otherwise
    """
    info(f"STATE_CHANGE: Restoring character: {character_name}", category="character_updates")
    
    # Auto-detect character role if not provided
    if character_role is None:
        character_role = detect_character_role(character_name)
        debug(f"STATE_CHANGE: Detected character role: {character_role}", category="character_updates")
    
    character_path = get_character_path(character_name, character_role)
    
    if backup_type == "latest":
        backup_path = character_path + ".backup_latest"
    else:
        # Look for specific backup file
        directory = os.path.dirname(character_path)
        base_name = os.path.basename(character_path)
        name_without_ext = os.path.splitext(base_name)[0]
        backup_path = os.path.join(directory, f"{name_without_ext}.backup_{backup_type}.json")
    
    if not os.path.exists(backup_path):
        error(f"FAILURE: Backup file not found: {backup_path}", category="file_operations")
        return False
    
    try:
        # Create a backup of current state before restoration
        restoration_backup = create_character_backup(character_path, "pre_restoration")
        
        # Copy backup to main file
        shutil.copy2(backup_path, character_path)
        info(f"SUCCESS: Successfully restored {character_name} from backup", category="character_updates")
        
        if restoration_backup:
            info(f"FILE_OP: Previous state backed up as: {os.path.basename(restoration_backup)}", category="file_operations")
        
        return True
        
    except Exception as e:
        error(f"FAILURE: Error restoring from backup", exception=e, category="character_updates")
        return False

def repair_character_data(character_data):
    """
    Repair common schema issues in character data before processing
    
    Args:
        character_data (dict): Character data to repair
    
    Returns:
        dict: Repaired character data
    """
    # Ensure the required top-level ammunition contract exists before validation.
    if 'ammunition' not in character_data or character_data['ammunition'] is None:
        character_data['ammunition'] = []
        debug("REPAIR: Added missing top-level ammunition list", category="character_updates")
    elif not isinstance(character_data['ammunition'], list):
        character_data['ammunition'] = []
        debug("REPAIR: Coerced invalid top-level ammunition field to list", category="character_updates")

    # Ensure ammunition has descriptions
    if 'ammunition' in character_data and isinstance(character_data['ammunition'], list):
        for ammo in character_data['ammunition']:
            if 'description' not in ammo or not ammo['description']:
                # Add a default description based on the ammunition name
                ammo_name = ammo.get('name', 'ammunition').lower()
                if 'arrow' in ammo_name:
                    ammo['description'] = "Standard arrows for use with a longbow or shortbow"
                elif 'bolt' in ammo_name:
                    ammo['description'] = "Standard crossbow bolts for use with crossbows"
                elif 'bullet' in ammo_name:
                    ammo['description'] = "Standard sling bullets for use with a sling"
                else:
                    ammo['description'] = f"Standard {ammo_name}"
                debug(f"REPAIR: Added missing description to ammunition: {ammo['name']}", category="character_updates")
    
    # Ensure equipment has required fields
    if 'equipment' in character_data and isinstance(character_data['equipment'], list):
        for item in character_data['equipment']:
            # Ensure all equipment has a description
            if 'description' not in item or not item['description']:
                item['description'] = f"A {item.get('item_name', 'item')}"
                debug(f"REPAIR: Added missing description to equipment: {item.get('item_name', 'unknown')}", category="character_updates")
            
            # Ensure quantity exists
            if 'quantity' not in item:
                item['quantity'] = 1
                debug(f"REPAIR: Added missing quantity to equipment: {item.get('item_name', 'unknown')}", category="character_updates")
    
    # Ensure injuries have valid types
    if 'injuries' in character_data and isinstance(character_data['injuries'], list):
        valid_injury_types = ["wound", "poison", "disease", "curse", "other"]
        for injury in character_data['injuries']:
            if isinstance(injury, dict) and 'type' in injury:
                if injury['type'] not in valid_injury_types:
                    old_type = injury['type']
                    # Map common invalid types
                    injury_type_map = {
                        "scar": "other",
                        "scars": "other",
                        "burn": "wound",
                        "burns": "wound"
                    }
                    injury['type'] = injury_type_map.get(old_type.lower(), "other")
                    debug(f"REPAIR: Fixed invalid injury type '{old_type}' to '{injury['type']}'", category="character_updates")
    
    return character_data


# Engine-owned pools a model reports as signed changes (core/nql/currency and
# core/nql/resources). The value is the sheet field the engine writes for it.
ENGINE_DELTA_FIELDS = {
    'currencyDelta': 'currency',
    'hpDelta': 'hitPoints',
    'spellSlotDelta': 'spellcasting',
    'featureUseDelta': 'classFeatures',
    'tempHpGrant': 'temporaryHitPoints',
}
ENGINE_DELTA_KEYS = tuple(ENGINE_DELTA_FIELDS)


def _engine_owned_total(character_data, updates):
    """The reason a model-authored delta states a pool total instead of a change, or None.

    Hit points, spell slot counts and feature use counts are engine resources:
    the model reports the change and the engine produces the value. A stated
    total is refused so the next attempt states the change. Only counts are
    refused; maximums, new pools and usage:null corrections pass unchanged.
    """
    if 'hitPoints' in updates:
        return "hitPoints totals are not accepted; report the change as hpDelta (signed whole number)"
    if 'temporaryHitPoints' in updates:
        return ("temporaryHitPoints totals are not accepted; report a grant as tempHpGrant (positive whole "
                "number); damage drains them automatically")
    slots = updates.get('spellcasting', {}).get('spellSlots') if isinstance(updates.get('spellcasting'), dict) else None
    if isinstance(slots, dict):
        for key, pool in slots.items():
            if isinstance(pool, dict) and 'current' in pool:
                return ("spell slot totals are not accepted; report the change as spellSlotDelta "
                        "{levelN: signed whole number}")
    stored = {f.get('name'): f.get('usage') for f in character_data.get('classFeatures') or []
              if isinstance(f, dict)}
    for feature in updates.get('classFeatures') or [] if isinstance(updates.get('classFeatures'), list) else []:
        if not isinstance(feature, dict) or not isinstance(feature.get('usage'), dict):
            continue
        before = stored.get(feature.get('name'))
        if isinstance(before, dict) and 'current' in feature['usage'] and \
                feature['usage'].get('current') != before.get('current'):
            return ("feature use totals are not accepted; report the change as featureUseDelta "
                    "{\"<exact feature name>\": signed whole number}")
    return None


def _stored_item_name(character_data, name):
    """The stored equipment name for a delta entry: exact, then unique case-insensitive."""
    names = [e.get('item_name') for e in character_data.get('equipment') or []
             if isinstance(e, dict) and e.get('item_name')]
    if name in names:
        return name, None
    folded = [n for n in names if str(n).strip().lower() == str(name).strip().lower()]
    if len(folded) == 1:
        return folded[0], None
    if folded:
        return None, f"{name!r} matches several equipment entries; name it exactly as on the sheet"
    return None, None


def _split_equipment_quantity_deltas(character_data, updates, model_authored):
    """Pull ``quantityDelta`` out of equipment entries before the merge.

    Stock is engine-owned (core/nql/equipment): the model reports how many
    of an item were gained or lost, never the resulting stack. Returns
    (pending {stored name: signed delta}, error or None). An entry for an item
    not yet on the sheet with a positive delta becomes a new item of that many.
    A model-authored ``quantity`` on an existing item other than 0 (remove all)
    is refused so the next attempt states the change.
    """
    pending = {}
    entries = updates.get('equipment')
    if not isinstance(entries, list):
        return pending, None
    stock = {e.get('item_name'): e.get('quantity', 1) for e in character_data.get('equipment') or []
             if isinstance(e, dict) and e.get('item_name')}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get('item_name'):
            continue
        stored, ambiguous = _stored_item_name(character_data, entry['item_name'])
        if ambiguous:
            return pending, ambiguous
        if 'quantityDelta' in entry:
            delta = entry.pop('quantityDelta')
            if type(delta) is bool or type(delta) is not int:
                return pending, f"quantityDelta for {entry['item_name']!r} must be a signed whole number"
            if 'quantity' in entry:
                return pending, (f"{entry['item_name']!r} has both quantity and quantityDelta; for an item "
                                 "already on the sheet send only quantityDelta")
            if stored is None:
                if delta <= 0:
                    return pending, (f"{entry['item_name']!r} is not on the sheet, so it cannot lose stock; "
                                     "use the exact item_name from the sheet")
                entry['quantity'] = delta          # a new item: the number acquired
                continue
            entry['item_name'] = stored
            if delta:
                pending[stored] = pending.get(stored, 0) + delta
        elif stored is not None and 'quantity' in entry:
            if entry['quantity'] == 0:
                entry['item_name'] = stored        # remove all: unambiguous
            elif entry['quantity'] == stock.get(stored):
                entry.pop('quantity')              # unchanged count restated: no stock change
                entry['item_name'] = stored
            elif model_authored:
                return pending, (f"equipment quantity totals are not accepted for items already on the sheet "
                                 f"({entry['item_name']!r}); report the change as quantityDelta (signed whole "
                                 "number), or quantity 0 to remove it entirely")
    return pending, None


def _stored_ammunition_name(character_data, name):
    """The stored ammunition row name for a delta entry: exact, then unique case-insensitive."""
    names = [r.get('name') for r in character_data.get('ammunition') or []
             if isinstance(r, dict) and r.get('name')]
    if name in names:
        return name, None
    folded = [n for n in names if str(n).strip().lower() == str(name).strip().lower()]
    if len(folded) == 1:
        return folded[0], None
    if folded:
        return None, f"{name!r} matches several ammunition rows; name it exactly as on the sheet"
    return None, None


def _split_ammunition_quantity_deltas(character_data, updates, model_authored):
    """Pull ``quantityDelta`` out of ammunition rows before the merge (AM-b).

    Ammunition stock is engine-owned (core/nql/ammunition): the model reports
    how many were fired, bought, found or sold, never the resulting count.
    Returns (pending {stored name: signed delta}, error or None). A row not yet
    on the sheet with a positive delta becomes a new row of that many. A
    model-authored ``quantity`` on an existing row other than 0 (remove the
    row) is refused so the next attempt states the change. Non-model input
    (level-up, repair tools) keeps the legacy additive merge untouched.
    """
    pending = {}
    rows = updates.get('ammunition')
    if not isinstance(rows, list):
        return pending, None
    for entry in rows:
        if not isinstance(entry, dict) or not entry.get('name'):
            continue
        stored, ambiguous = _stored_ammunition_name(character_data, entry['name'])
        if ambiguous:
            return pending, ambiguous
        if 'quantityDelta' in entry:
            delta = entry.pop('quantityDelta')
            if type(delta) is bool or type(delta) is not int:
                return pending, f"quantityDelta for ammunition {entry['name']!r} must be a signed whole number"
            if 'quantity' in entry:
                return pending, (f"ammunition {entry['name']!r} has both quantity and quantityDelta; for a row "
                                 "already on the sheet send only quantityDelta")
            if stored is None:
                if delta <= 0:
                    names = [r.get('name') for r in character_data.get('ammunition') or []
                             if isinstance(r, dict) and r.get('name')]
                    return pending, (f"ammunition {entry['name']!r} is not on the sheet, so it cannot be spent; "
                                     f"the sheet's rows are {names}; use the exact name")
                entry['quantity'] = delta          # a new row: the number acquired
                continue
            entry['name'] = stored
            if delta:
                pending[stored] = pending.get(stored, 0) + delta
        elif stored is not None and 'quantity' in entry and model_authored:
            if entry['quantity'] == 0:
                entry['name'] = stored
                entry['_remove'] = True            # remove the row entirely: unambiguous
            else:
                return pending, (f"ammunition quantity totals are not accepted for rows already on the sheet "
                                 f"({entry['name']!r}); report the change as quantityDelta (signed whole "
                                 "number), or quantity 0 to remove the row entirely")
    return pending, None


def _engine_ammunition_stock(character_data, pending, character_name):
    """AM-b: each pending ammunition change through the engine on the before sheet.

    Returns ({stored name: engine quantity}, refusal reason or None). A short
    stock (E_QUANTITY) is the refusal; an unavailable engine keeps today's
    addition with a warning so play never stops.
    """
    from core.nql import ammunition as nql_ammunition

    stock = {}
    for name, delta in pending.items():
        if delta < 0:
            outcome = nql_ammunition.spend(character_data, name, -delta, recoverable=False)
        else:
            outcome = nql_ammunition.add(character_data, name, delta)
        if outcome.ok:
            stock[name] = int(outcome.quantity or 0)
            info(f"AM: {character_name} {name} {delta:+d} -> {stock[name]} [engine]", category="character_updates")
            continue
        if (outcome.fault or {}).get('code') == 'E_QUANTITY':
            return stock, outcome.reason
        row = nql_ammunition.row_of(character_data, name)
        before = row.get('quantity', 0) if isinstance(row, dict) and type(row.get('quantity')) is int else 0
        stock[name] = max(0, before + delta)
        warning(f"AM: {character_name} {name} {delta:+d} -> {stock[name]} by arithmetic; engine unavailable ({outcome.reason})",
                category="character_updates")
    return stock, None


def _copy_engine_pools(engine_sheet, target):
    """Write the engine's pool values (hit points, slot and use counts) onto the merged sheet."""
    if 'hitPoints' in engine_sheet:
        target['hitPoints'] = engine_sheet['hitPoints']
    if 'temporaryHitPoints' in engine_sheet:
        target['temporaryHitPoints'] = engine_sheet['temporaryHitPoints']
    engine_slots = (engine_sheet.get('spellcasting') or {}).get('spellSlots') \
        if isinstance(engine_sheet.get('spellcasting'), dict) else None
    target_slots = (target.get('spellcasting') or {}).get('spellSlots') \
        if isinstance(target.get('spellcasting'), dict) else None
    if isinstance(engine_slots, dict) and isinstance(target_slots, dict):
        for key, pool in engine_slots.items():
            if isinstance(pool, dict) and isinstance(target_slots.get(key), dict):
                target_slots[key]['current'] = pool['current']
    engine_uses = {f['name']: f['usage']['current'] for f in engine_sheet.get('classFeatures') or []
                   if isinstance(f, dict) and isinstance(f.get('usage'), dict) and f.get('name')}
    for feature in target.get('classFeatures') or []:
        if isinstance(feature, dict) and isinstance(feature.get('usage'), dict) and feature.get('name') in engine_uses:
            feature['usage']['current'] = engine_uses[feature['name']]


def prepare_character_delta(character_data, updates, character_role, schema,
                            character_name, managed_effect_operation=None,
                            model_authored=False):
    """Shared provider-free stored-value preparation (#323 D-323-10).

    Ordinary T079 input joins after effective-to-base normalization. Typed
    level-up input joins in its stored frame. No model calls or persistence;
    callers retain their different pre/postcommit review obligations.
    ``model_authored`` marks T079 output: pool totals are then refused in
    favour of the signed delta keys (level-up keeps its typed totals).
    """
    updates = fix_injury_types(fix_item_types(copy.deepcopy(updates)))
    if model_authored:
        total_reason = _engine_owned_total(character_data, updates)
        if total_reason:
            return updates, character_data, {
                'critical_warnings': [], 'removed_fields': [], 'schema_valid': False,
                'error_message': total_reason,
            }
    if model_authored:
        # Derived totals are the engine's (core/nql/stats): a value the model
        # wrote for one is dropped and the engine's stands.
        from core.nql import stats as nql_stats

        dropped_totals = nql_stats.drop_model_totals(character_data, updates)
        if dropped_totals:
            info(f"STATS: {character_name}: dropped model-written totals {dropped_totals}; the engine derives them",
                 category="character_updates")
        # Unconscious at 0 hit points and alive on healing are the engine's
        # (C1): a status the model wrote for them is dropped the same way.
        dropped_states = nql_stats.drop_model_states(updates)
        if dropped_states:
            info(f"STATES: {character_name}: dropped model-written {dropped_states}; the engine sets unconscious and alive from hit points",
                 category="character_updates")
    stock_deltas, stock_reason = _split_equipment_quantity_deltas(character_data, updates, model_authored)
    if stock_reason:
        return updates, character_data, {
            'critical_warnings': [], 'removed_fields': [], 'schema_valid': False,
            'error_message': stock_reason,
        }
    # Ammunition stock is engine-owned (core/nql/ammunition, AM-b): the signed
    # change per row goes through the engine on the before sheet and the
    # engine's quantity replaces the merged one. A short stock is refused and
    # the DM is told; the row is never silently emptied or dropped.
    ammo_deltas, ammo_reason = _split_ammunition_quantity_deltas(character_data, updates, model_authored)
    if ammo_reason:
        return updates, character_data, {
            'critical_warnings': [], 'removed_fields': [], 'schema_valid': False,
            'error_message': ammo_reason,
        }
    ammo_stock = {}
    if ammo_deltas:
        ammo_stock, ammo_refusal = _engine_ammunition_stock(character_data, ammo_deltas, character_name)
        if ammo_refusal:
            return updates, character_data, {
                'critical_warnings': [], 'removed_fields': [], 'schema_valid': False,
                'error_message': f"the ammunition change was refused by the rules engine: {ammo_refusal}",
                'engine_refusal': ammo_refusal,
            }
    if 'hitPoints' in updates and updates['hitPoints'] < 0:
        updates['hitPoints'] = 0
    if ('experience_points' in updates and
            updates['experience_points'] < character_data.get('experience_points', 0)):
        del updates['experience_points']
    # Coins are engine-owned (core/nql/currency): the model reports a signed
    # change per coin type and the engine produces the balance, refusing a
    # payment the sheet cannot cover. A totals object is refused so the next
    # attempt states the change instead of a balance.
    currency_delta = updates.pop('currencyDelta', None)
    if 'currency' in updates:
        return updates, character_data, {
            'critical_warnings': [], 'removed_fields': [], 'schema_valid': False,
            'error_message': ("currency totals are not accepted; report the change as "
                              "currencyDelta {gold, silver, copper} signed whole numbers"),
        }
    if currency_delta is not None:
        from core.nql import currency as nql_currency

        outcome = nql_currency.apply_delta(character_data, currency_delta)
        if not outcome.ok:
            return updates, character_data, {
                'critical_warnings': [], 'removed_fields': [], 'schema_valid': False,
                'error_message': f"the currency change was refused by the rules engine: {outcome.reason}",
                'engine_refusal': outcome.reason,
            }
        updates['currency'] = dict(outcome.sheets[0]['currency'])
        for gap in outcome.gaps:
            debug(f"[Currency Engine] {character_name}: {gap}", category="character_updates")
    # Hit points, spell slots and feature uses are engine-owned pools
    # (core/nql/resources): signed changes go through the engine, which clamps
    # healing at the effective maximum, drops a character to zero, and refuses
    # a spend the pool cannot cover. The engine's values replace the merged ones.
    resource_updates = {k: updates.pop(k) for k in ('hpDelta', 'spellSlotDelta', 'featureUseDelta', 'tempHpGrant')
                        if k in updates}
    engine_pools = None
    if resource_updates:
        from core.effects.effective import effective_sheet
        from core.nql import resources as nql_resources

        effective_max = effective_sheet(character_data).get('maxHitPoints')
        outcome = nql_resources.apply_deltas(
            character_data, resource_updates,
            max_hp=effective_max if type(effective_max) is int else None)
        if not outcome.ok:
            return updates, character_data, {
                'critical_warnings': [], 'removed_fields': [], 'schema_valid': False,
                'error_message': f"the change was refused by the rules engine: {outcome.reason}",
                'engine_refusal': outcome.reason,
            }
        engine_pools = outcome.sheet
        for gap in outcome.gaps:
            debug(f"[Resource Engine] {character_name}: {gap}", category="character_updates")
        # CN: the Constitution save the engine made for the caster's concentration
        # reaches the next DM note (CHECK RESULTS) like a scored check.
        for line in outcome.concentration_lines:
            from core.managers import checks_state
            checks_state.add_result(line)
            info(f"CONCENTRATION: {line}", category="character_updates")
        concentration_ended = outcome.concentration_ended
    else:
        concentration_ended = None
    updated_data = deep_merge_dict(character_data, updates)
    for row in updated_data.get('ammunition') or []:
        if isinstance(row, dict) and row.get('name') in ammo_stock:
            row['quantity'] = ammo_stock[row['name']]
    if engine_pools is not None:
        _copy_engine_pools(engine_pools, updated_data)
        # The engine's unconscious/alive verdict for this hit point change
        # (core/nql/stats) rides with the pools; the model's other condition
        # edits in the same delta stay.
        from core.nql import stats as nql_stats

        carried = nql_stats.carry_states(engine_pools, updated_data)
        if carried:
            info(f"STATES: {character_name}: " + "; ".join(carried), category="character_updates")
    # CN: the engine ended the concentration (failed save, knocked out), or the
    # delta put the caster in an incapacitating state: the spell ends everywhere.
    from core.nql import stats as nql_stats
    focus = nql_stats.concentration_of(updated_data)
    if focus:
        why = concentration_ended or nql_stats.concentration_blocked(updated_data)
        if why:
            from core.managers.concentration_runtime import clear_record, end_group
            clear_record(updated_data, focus["group"])
            end_group(focus["group"], {"minimum": "knocked unconscious"}.get(why, why), skip_caster=character_name)
    if stock_deltas:
        # The requested change reaches the engine unclamped: a stack that
        # would go below zero stays in the merged sheet so the engine sees
        # the exact consume and refuses it (never silently emptied).
        for entry in updated_data.get('equipment') or []:
            if isinstance(entry, dict) and entry.get('item_name') in stock_deltas:
                base = entry.get('quantity', 1) if type(entry.get('quantity')) is int else 1
                entry['quantity'] = base + stock_deltas.pop(entry['item_name'])
    # Temporary effects: the classifier's add/remove operation, and any live
    # effect the engine does not hold yet (a sheet written before E12), go
    # through the lifecycle so the engine's armor class and maximum hit
    # points are the stored values. No operation and nothing pending makes
    # no engine call.
    from core.effects.lifecycle import apply_effect_ops
    updated_data = apply_effect_ops(updated_data, _effect_operations(managed_effect_operation))
    if 'hitPoints' in updated_data and updated_data['hitPoints'] < 0:
        updated_data['hitPoints'] = 0
    critical_warnings = validate_critical_fields_preserved(character_data, updated_data, character_name)
    checks = {'critical_warnings': critical_warnings, 'removed_fields': [],
              'schema_valid': False, 'error_message': None}
    if critical_warnings:
        return updates, updated_data, checks
    if isinstance(updates.get('equipment'), list):
        # Equipment is engine-owned (core/nql): the merged delta becomes equip,
        # unequip, consume and create operations on the sheet's world. A refusal
        # is reported like a schema failure so the model can correct its delta.
        from core.nql import equipment as nql_equipment

        outcome = nql_equipment.reconcile(character_data, updated_data)
        if not outcome.ok:
            checks.update(error_message=(
                "the equipment change was refused by the rules engine: "
                f"{outcome.reason}. Operations attempted: {' '.join(outcome.operations)}"))
            if (outcome.fault or {}).get('code') == 'E_QUANTITY':
                # Not enough stock: a restated delta cannot fix it, the DM must.
                checks['engine_refusal'] = outcome.reason
            return updates, updated_data, checks
        updated_data['equipment'] = outcome.equipment
        for gap in outcome.gaps:
            debug(f"[Equipment Engine] {character_name}: {gap}", category="character_updates")
    updated_data = normalize_status_and_condition(updated_data, character_role)
    updated_data, removed_fields = purge_invalid_fields(updated_data, schema, character_name)
    if model_authored:
        # A change of facts (level, abilities, proficiencies, expertise, feats,
        # casting ability) with no other engine request in this delta: one
        # genesis+status request stores the engine's totals.
        from core.nql import stats as nql_stats

        if nql_stats.facts_changed(character_data, updated_data):
            problem = nql_stats.refresh(updated_data)
            if problem:
                warning(f"STATS: {character_name}: totals not refreshed ({problem}); stored values kept until the next engine touch",
                        category="character_updates")
    is_valid, error_msg = validate_character_data(updated_data, schema, character_name)
    checks.update(schema_valid=is_valid, error_message=error_msg, removed_fields=removed_fields)
    if is_valid:
        updated_data = repair_character_data(updated_data)
    return updates, updated_data, checks


class EngineRefusedChange(Exception):
    """The rules engine refused the requested change and the model could not
    restate it (E6): the update did not happen and the caller reports why."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class CharacterSnapshotChanged(ValueError):
    """A prepared proposal consumed different canonical values (#323)."""

    def __init__(self, current):
        super().__init__('canonical character changed during preparation; reconcile the current values')
        self.current = current


def commit_character_sheet(character_path, updated_data, *, commit_guard=None, expected_before=None):
    """One atomic write leaf, with locked value comparison for prepared work.

    Ordinary callers already own their transaction and retain the existing
    safe-write behavior. Prepared callers additionally own character/effects
    locks and supply their exact consumed canonical snapshot. No provider work.
    """
    from utils.file_operations import atomic_writer
    from utils.level_up_workspace import _same_value
    locked = False
    try:
        if expected_before is not None:
            atomic_writer.acquire_lock(character_path, commit_guard=commit_guard)
            locked = True
            current = safe_read_json(character_path)
            if not _same_value(current, expected_before):
                raise CharacterSnapshotChanged(current)
        return safe_write_json(character_path, updated_data, acquire_lock=not locked,
                               commit_guard=commit_guard)
    finally:
        if locked:
            atomic_writer.release_lock(character_path)


def _is_meaningful_character_delta(updates, schema):
    """Return whether T079 produced a usable delta: {} (the typed "no change"
    answer, confirmed by the caller) or at least one recognized field update."""
    if not isinstance(updates, dict):
        return False
    if not updates:
        return True
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    return isinstance(properties, dict) and any(
        field in properties or field in ENGINE_DELTA_KEYS for field in updates
    )


def infer_requested_character_update_fields(changes):
    """Infer only explicit, mechanically coupled T079 update categories.

    This is deliberately narrower than general natural-language intent parsing.
    It recognizes high-risk phrases where accepting only one part of the model's
    delta would leave a character sheet internally inconsistent. Ambiguous
    narration is left to the model and the existing schema validators.
    """
    if not isinstance(changes, str) or not changes.strip():
        return set()

    text = re.sub(r"\s+", " ", changes.strip().lower())
    required = set()

    currency_amount = re.search(
        r"\b\d+\s*(?:gp|gold|sp|silver|cp|copper|g|s|c)\b",
        text,
    )
    explicit_trade = re.search(r"\btrade(?:d|s)?\b.{0,100}\bfor\b", text)
    negated_trade = re.search(
        r"\b(?:do|does|did)\s+not\s+trade\b|"
        r"\b(?:don't|doesn't|didn't)\s+trade\b",
        text,
    )
    if explicit_trade and currency_amount and not negated_trade:
        required.update(("currency", "equipment"))

    hp_transition = re.search(r"\bhp\s*(?:\d+\s*)?->\s*\d+\b", text)
    if hp_transition:
        required.add("hitPoints")

    potion_consumption = re.search(
        r"\b(?:use[ds]?|drank|drink|consum(?:e|ed|es))\s+"
        r"(?:\d+\s+|an?\s+)?(?:healing\s+)?potion\b",
        text,
    )
    if potion_consumption:
        required.add("equipment")

    shield_destroyed = (
        re.search(
            r"\bshield\s+(?:(?:was|is)\s+|has\s+been\s+)?"
            r"(?:destroyed|broken|dissolved|removed|lost)\b",
            text,
        )
        or re.search(
            r"\b(?:destroyed|broken|dissolved|removed|lost)\s+(?:the\s+)?shield\b",
            text,
        )
    )
    if shield_destroyed:
        # armorClass and equipment_effects are engine-owned (core/nql); only
        # the equipment change itself is a required part of the delta.
        required.add("equipment")

    weapon_swap = re.search(
        r"\b(?:swapped?|replaced|exchanged)\b.{0,100}\b"
        r"(?:weapon|(?:short|long|great)?sword|dagger|bow|axe|mace|staff|spear|crossbow)\b",
        text,
    )
    if weapon_swap:
        required.update(("equipment", "attacksAndSpellcasting"))

    poison_applied = re.search(
        r"(?:^|[.;]\s*)poisoned\b|\b(?:became|now|is|was)\s+poisoned\b",
        text,
    )
    if poison_applied:
        required.update(("condition", "condition_affected"))

    death_save_change = re.search(
        r"\b(?:first|second|third|\d+(?:st|nd|rd|th)?)\s+death\s+save\s+"
        r"(?:failed|succeeded|success|failure)\b",
        text,
    )
    if death_save_change:
        required.add("deathSaves")

    spell_slot_change = (
        "spell slot" in text
        and (
            re.search(r"\bspell slot\b.{0,80}\bcurrent\s+\d+\s*->\s*\d+\b", text)
            or re.search(
                r"\b(?:cast|casts|expended|expends|used|uses)\b.{0,100}\bspell slot\b",
                text,
            )
        )
    )
    if spell_slot_change:
        required.add("spellcasting")

    return required


def validate_requested_character_update_completeness(changes, updates):
    """Return ``(is_complete, missing_fields)`` for explicit T079 requests."""
    required = infer_requested_character_update_fields(changes)
    present = set(updates) if isinstance(updates, dict) else set()
    for delta_key, owned_field in ENGINE_DELTA_FIELDS.items():
        if delta_key in present:
            present.add(owned_field)
    missing = sorted(required - present)
    return not missing, missing


def build_requested_character_delta_gemini_schema(changes, character_schema):
    """Build a strict Gemini schema for the fields this update must return."""
    from model_config import convert_to_gemini_schema

    required_fields = sorted(infer_requested_character_update_fields(changes))
    properties = character_schema.get("properties", {})
    missing_schema_fields = [
        field for field in required_fields if field not in properties
    ]
    if missing_schema_fields:
        raise ValueError(
            "T079 requested fields are missing from character schema: "
            + ", ".join(missing_schema_fields)
        )
    if not required_fields:
        return None

    delta_schema = {
        "type": "object",
        "properties": {
            field: copy.deepcopy(properties[field]) for field in required_fields
        },
        "required": required_fields,
    }
    return convert_to_gemini_schema(delta_schema, preserve_required=True)


def _character_update_lock_key(character_name, character_role=None):
    """Resolve aliases to the character file used as the transaction key."""
    resolved_name = character_name
    try:
        character_path = get_character_path(resolved_name, character_role)
        if not os.path.exists(character_path):
            party_tracker_data = safe_json_load("party_tracker.json") or {}
            fuzzy_name = fuzzy_match_character_name(resolved_name, party_tracker_data)
            if fuzzy_name:
                resolved_name = fuzzy_name
            else:
                resolved_name = normalize_character_name(resolved_name)
        character_path = get_character_path(resolved_name, character_role)
        return os.path.normcase(os.path.realpath(character_path))
    except Exception:
        # Locking must remain available even when path discovery is itself the
        # reason the update will fail. The update implementation reports the
        # underlying path/data error through its normal return contract.
        return f"character:{normalize_character_name(str(resolved_name))}"


def _get_character_update_lock(character_name, character_role=None):
    key = _character_update_lock_key(character_name, character_role)
    with _CHARACTER_UPDATE_LOCKS_GUARD:
        lock = _CHARACTER_UPDATE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _CHARACTER_UPDATE_LOCKS[key] = lock
        return lock


def _effect_operations(operation):
    """A managed effect operation as a list: one dict, a list of dicts, or none."""
    if isinstance(operation, dict):
        return [operation]
    if isinstance(operation, list):
        return [item for item in operation if isinstance(item, dict)]
    return []


def _translate_declarative_effect_delta(character_data, updates, operation):
    """Translate player-visible T079 values back to durable base storage.

    The model reads effective values.  The character file stores base values,
    while the lifecycle operation owns one-time resource adjustments.  Reverse
    those adjustments here so applying the operation below reaches the exact
    visible value once, never twice.
    """
    from core.effects.effective import storage_delta_from_effective
    from core.effects.lifecycle import apply_effect_ops

    # One classification may carry several operations (a removal that ends
    # every record of one name); each contributes its effect and hp changes.
    operations = copy.deepcopy(_effect_operations(operation))
    resource_operations = []
    managed_effects = []
    for item in operations:
        if item.get("op") == "add":
            managed_effect = item.get("effect") or {}
            managed_effects.append(managed_effect)
            resource_operations.extend(managed_effect.get("onApply", []) or [])
        elif item.get("op") == "remove":
            effect_id = item.get("effectId")
            name = item.get("name")
            for effect in character_data.get("temporaryEffects", []) or []:
                if not isinstance(effect, dict):
                    continue
                if (effect_id and effect.get("effectId") == effect_id) or (
                    not effect_id and name and effect.get("name") == name
                ):
                    managed_effects.append(effect)
                    resource_operations.extend(effect.get("onRemove", []) or [])

    preview = apply_effect_ops(character_data, operations) if operations else character_data
    translated = storage_delta_from_effective(preview, updates)
    from core.effects.model import canonical_stat

    stripped_effect_fields = []
    managed_modifiers = [m for e in managed_effects for m in (e.get("modifiers", []) or [])]
    for modifier in managed_modifiers:
        stat = canonical_stat(modifier.get("stat")) if isinstance(modifier, dict) else None
        if stat and stat.startswith("abilities."):
            ability = stat.split(".", 1)[1]
            abilities = translated.get("abilities")
            if isinstance(abilities, dict):
                if ability in abilities:
                    stripped_effect_fields.append(
                        "abilities.%s=%r" % (ability, abilities.get(ability))
                    )
                abilities.pop(ability, None)
                if not abilities:
                    translated.pop("abilities", None)
        elif stat in ("armorClass", "speed", "hitPoints", "maxHitPoints"):
            # Derived values belong to the effect overlay. T079 may describe
            # the same visible change, but it cannot bake or cancel it.
            if stat in translated:
                stripped_effect_fields.append("%s=%r" % (stat, translated.get(stat)))
                translated.pop(stat, None)
            if stat == "hitPoints" and "hpDelta" in translated:
                # The engine-owned change is the effect's; a model copy of the
                # same visible change would apply it twice.
                stripped_effect_fields.append("hpDelta=%r" % translated.get("hpDelta"))
                translated.pop("hpDelta", None)
    for resource in resource_operations:
        if not isinstance(resource, dict):
            continue
        stat = resource.get("stat")
        if stat in translated:
            # The classifier's validated lifecycle operation is authoritative
            # for this one-time resource change. Dropping T079's copy prevents
            # both double application and a weaker model cancelling the
            # deterministic operation by returning the pre-effect value.
            stripped_effect_fields.append("%s=%r" % (stat, translated.get(stat)))
            translated.pop(stat, None)
        if stat == "hitPoints" and "hpDelta" in translated:
            stripped_effect_fields.append("hpDelta=%r" % translated.get("hpDelta"))
            translated.pop("hpDelta", None)
    if stripped_effect_fields:
        debug(
            "EFFECTS: Removed T079 copies of engine-owned values: %s"
            % ", ".join(stripped_effect_fields),
            category="effects_tracking",
        )
    return translated


def update_character_info(
    character_name,
    changes,
    character_role=None,
    managed_effect_operation=None,
    action_context=None,
    *,
    commit_guard=None,
):
    """Run one complete character update transaction under a per-file lock."""
    lock = _get_character_update_lock(character_name, character_role)
    with lock:
        if commit_guard is not None:
            with commit_guard():
                pass
        resolved_role = character_role or detect_character_role(character_name)
        character_path = get_character_path(character_name, resolved_role)
        from utils.path_transaction_lock import path_transaction_lock

        with path_transaction_lock(
            character_path,
            suffix=".effects.lock",
            timeout_seconds=None if commit_guard is not None else 30.0,
        ) as acquired:
            if acquired is None:
                warning(
                    f"EFFECTS: Timed out acquiring character lease for {character_name}",
                    category="effects_tracking",
                )
                return False
            if managed_effect_operation is None:
                return _update_character_info_unlocked(
                    character_name,
                    changes,
                    character_role=character_role,
                    action_context=action_context,
                    structural_reissue=commit_guard is not None,
                    commit_guard=commit_guard,
                )
            return _update_character_info_unlocked(
                character_name,
                changes,
                character_role=character_role,
                managed_effect_operation=managed_effect_operation,
                action_context=action_context,
                structural_reissue=commit_guard is not None,
                commit_guard=commit_guard,
            )


def _update_character_info_unlocked(
    character_name,
    changes,
    character_role=None,
    managed_effect_operation=None,
    prepare_only=False,
    structural_reissue=False,
    action_context=None,
    *,
    commit_guard=None,
):
    """
    Unified function to update character information for both players and NPCs
    
    Args:
        character_name (str): Name of the character to update
        changes (str): Description of changes to make
        character_role (str, optional): 'player' or 'npc', auto-detected if None
    
    Returns:
        bool: True if successful, False otherwise
    """
    
    if commit_guard is not None:
        with commit_guard():
            pass
    debug(f"STATE_CHANGE: Updating character info for: {character_name}", category="character_updates")
    
    # Try fuzzy matching first if the character isn't found
    original_name = character_name
    party_tracker_data = safe_json_load("party_tracker.json")
    
    # First try with the original name
    character_path = get_character_path(character_name, character_role)
    if not os.path.exists(character_path):
        # Try fuzzy matching
        fuzzy_matched_name = fuzzy_match_character_name(character_name, party_tracker_data)
        if fuzzy_matched_name and fuzzy_matched_name != character_name:
            info(f"FUZZY_MATCH: Resolved '{character_name}' to '{fuzzy_matched_name}'", category="character_updates")
            character_name = fuzzy_matched_name
        else:
            # Still try normalization as a fallback
            normalized_name = normalize_character_name(character_name)
            if normalized_name != character_name:
                debug(f"STATE_CHANGE: Normalized character name from '{character_name}' to '{normalized_name}'", category="character_updates")
                character_name = normalized_name
    
    # Auto-detect character role if not provided
    if character_role is None:
        character_role = detect_character_role(character_name)
        debug(f"STATE_CHANGE: Detected character role: {character_role}", category="character_updates")
    
    # Load schema and character data
    schema = load_schema()
    character_path = get_character_path(character_name, character_role)
    
    try:
        character_data = safe_read_json(character_path)
        if not character_data:
            error(f"FAILURE: Could not load character data for {character_name}", category="file_operations")
            return False
        
        # Validate that character_data is a dictionary
        if not isinstance(character_data, dict):
            error(f"FAILURE: Character data for {character_name} is corrupted (not a dictionary)", category="file_operations")
            error(f"FAILURE: Loaded data type: {type(character_data)}, value: {character_data}", category="file_operations")
            return False
        
        persisted_character_data = copy.deepcopy(character_data)
        # Repair common schema issues before processing
        character_data = repair_character_data(character_data)
            
    except Exception as e:
        error(f"FAILURE: Error loading character data", exception=e, category="file_operations")
        return False
    
    # A sheet whose armor projection is already outside the frozen schema would
    # be refused by the whole-sheet gate below on every ordinary update that
    # leaves the value in place (issue #357). Offer it to the existing T051 armor
    # agent first, in memory only, so the model's correction and the requested
    # change share the one atomic write; nothing here touches the file.
    validator = AICharacterValidator()
    armor_errors = armor_contract_errors(
        validator.extract_ac_relevant_data(character_data)['equipment'],
        schema['properties']['equipment']['items'],
    )
    if armor_errors:
        warning(
            "VALIDATION: %s carries out-of-schema armor data; asking T051 to "
            "correct it before the update: %s" % (character_name, armor_errors),
            category="character_validation",
        )
        armor_result = validator.ai_validate_armor_class_with_result(character_data)
        if armor_result.success and armor_result.changed:
            info(
                "VALIDATION: T051 corrected %s before the update: %s"
                % (character_name, validator.corrections_made),
                category="character_validation",
            )
            character_data = armor_result.data
        else:
            warning(
                "VALIDATION: T051 could not correct %s before the update (%s); "
                "continuing with the unrepaired sheet"
                % (character_name, armor_result.error or armor_result.status.value),
                category="character_validation",
            )

    # Create file backup before any changes
    if not prepare_only:
        backup_path = create_character_backup(character_path, "update")
        if backup_path is None:
            warning("FILE_OP: Could not create backup, but proceeding with update", category="file_operations")
        else:
            # Clean up old backups to prevent accumulation
            cleanup_old_backups(character_path)
    
    # Create in-memory backup
    original_data = copy.deepcopy(character_data)
    
    # Load and process conversation history
    history = load_conversation_history()
    if character_role == 'player':
        history = process_conversation_history(history, character_role)
    
    # Format schema for prompt
    schema_info = format_schema_for_prompt(schema, character_role)
    
    declarative_effects = False
    effective_projection = any(
        isinstance(effect, dict)
        and effect.get("authoredBy") in ("engine", "classifier")
        for effect in character_data.get("temporaryEffects", []) or []
    )
    prompt_character_data = character_data
    try:
        from core.managers.effects_state import campaign_effects_migrated
        from core.effects.effective import effective_sheet

        declarative_effects = campaign_effects_migrated()
        effective_projection = declarative_effects or effective_projection
        if effective_projection:
            prompt_character_data = effective_sheet(character_data)
    except Exception as effects_mode_exc:
        warning(
            f"EFFECTS: Could not prepare effective character view: {effects_mode_exc}",
            category="effects_tracking",
        )

    if declarative_effects:
        effects_update_rules = """19. DECLARATIVE EFFECT OWNERSHIP:
    - The game engine owns temporaryEffects, their duration, and their numeric modifiers.
    - NEVER return temporaryEffects.
    - Read the supplied effective values as the character's current player-visible values.
    - If the requested change adds or removes a temporary effect, return any other
      one-time costs or permanent changes only. Do not manually reverse an expired effect.
    - When the change creates, ends or alters a temporary effect (a spell buff or debuff, a
      potion's lasting effect, a curse, a blessing, a condition with a duration), include
      "effectChange": true in your delta beside any other fields (or alone when nothing else
      changes). Omit it for everything else: damage, healing, coins, items, experience, rests,
      slot or resource spending with no lasting effect. The engine classifies the effect itself."""
    else:
        effects_update_rules = """19. TEMPORARY EFFECTS - CRITICAL RULES:
    - ONLY add effects with durations of 1 MINUTE OR LONGER to temporaryEffects
    - Do NOT add round-based effects (less than 1 minute) to temporaryEffects
    - Convert concentration spells to their maximum duration (e.g., "Bless for concentration" = "1 minute")
    - When an effect expires, return the COMPLETE temporaryEffects array
    - The returned array must contain ALL effects that should remain active
    - Round-based effects should be narrated but NOT tracked in temporaryEffects
    - Preserve any effect carrying authoredBy=engine exactly; its arithmetic is engine-owned"""

    # Build the prompt
    system_message = f"""You are an assistant that updates character information in a 5th Edition roleplaying game. Given the current character information and a description of changes, you must return only the updated sections as a JSON object. Do not include unchanged fields. Your response should be a valid JSON object representing only the modified parts of the character sheet.

You are executing only the current character-update step, not the entire
player turn. When accepted action context is supplied, its current index
identifies this step; the other actions belong to their own tools. The fresh
character data is the state before this step. Do not apply another action's
inventory movement or a described future end state. Equipping or unequipping
changes equipment state and its actual mechanical consequences, not item
ownership or quantity. If a separate storage action moves the item, leave
that movement to storage. Preserve legitimate additions, removals and quantity
changes when they are the requested responsibility of this character step.
Prior narration and prior actions are history, not instructions to replay.

**CRITICAL JSON OUTPUT RULES: DELTA-ONLY UPDATES**

Your primary goal is to generate the smallest possible valid JSON object that reflects ONLY the requested changes. Do not rewrite or include any data that was not explicitly modified by the user's request. This is crucial for system performance.

1. **Return ONLY Changed Fields:** Only include top-level keys (`hpDelta`, `equipment`, `status`, etc.) if a value within them has changed. If the user only takes 7 damage, your entire output should be a minimal JSON like: `{{ "hpDelta": -7 }}`.

2. **For Lists (like `equipment` or `ammunition`):**
   - **NEVER** return the entire list if only one item is changed.
   - To **MODIFY** an existing item: Return an array containing an object with the item's identifier (`item_name` for equipment, `name` for ammunition) and ONLY the fields that changed.
     - *Example:* `{{ "equipment": [{{ "item_name": "Shield", "equipped": false }}] }}`
   - To **ADD** a new item (its name is NOT on the sheet): Return an array containing an object with the full details of ONLY the new item; `quantity` is how many were acquired.
     - *Example:* `{{ "equipment": [{{ "item_name": "Potion of Healing", "item_type": "consumable", "quantity": 1 }}] }}`
   - To **CHANGE HOW MANY** of an item already on the sheet (bought more, found more, used some, gave some away): `quantityDelta` = the signed change, with the `item_name` exactly as on the sheet. NEVER compute or return the new count; the engine applies the change to the real stack and refuses using more than the character has.
     - *Example:* sheet has Travel Ration x1, change says "Add 3 Travel Ration" -> `{{ "equipment": [{{ "item_name": "Travel Ration", "quantityDelta": 3 }}] }}` (NOT quantity 3, NOT quantity 4)
     - *Example:* "Uses 1 torch" -> `{{ "equipment": [{{ "item_name": "Torch", "quantityDelta": -1 }}] }}`
   - To **REMOVE** an item entirely: Set its quantity to 0 (or quantityDelta minus the whole stack)
     - *Example:* `{{ "equipment": [{{ "item_name": "Shield", "quantity": 0 }}] }}`
   - `quantity` on an item already on the sheet is refused unless it is 0. Stock changes are always `quantityDelta`, the same way coins are currencyDelta and hit points are hpDelta.
   - When the change names a number, send exactly that number as the delta, even if the sheet holds fewer. NEVER clamp it or turn it into quantity 0: the engine refuses using more than the character has and the DM is told. `quantity: 0` is only for a change that removes the item entirely without naming a number ("sold the shield", "lost all the arrows").
     - *Example:* sheet has Gemstones x5, change says "Remove 9 Gemstones" -> `{{ "equipment": [{{ "item_name": "Gemstones", "quantityDelta": -9 }}] }}` (NOT quantity 0, NOT quantityDelta -5)

3. **For Nested Objects (like `currency` or `spellcasting.spellSlots`):**
   - Only return the specific key-value pairs that were modified.
   - *Example (Spending Gold):* `{{ "currencyDelta": {{ "gold": -12 }} }}` (signed change per coin type; never a total, never a `currency` object; omit unchanged coins).
   - *Example (Using a Spell Slot):* `{{ "spellSlotDelta": {{ "level1": -1 }} }}` (signed change per slot level; never a `current` count, never a `spellcasting` object for a cast).

4. **For Complex Updates Affecting Multiple Systems:**
   - When an action affects multiple character aspects, you MUST include ALL affected fields in your minimal JSON response.
   - Weapon changes: Always include updated `attacksAndSpellcasting` array entries for the affected weapons.
   - Armor class: do NOT include `armorClass` or `equipment_effects`. The rules engine computes both from the equipped items' typed fields (`armor_category`, `ac_base`, `ac_bonus`, `dex_limit`) after your delta is applied. Give new armor those fields instead.
   - Item typing: `item_type` "armor" is only for body armor and shields, and such an entry MUST carry `armor_category` and `ac_base` (plus `dex_limit` for medium armor). An amulet, ring, cloak, robe, bracer or charm that gives no armor base is "miscellaneous" with an `item_subtype`; a magic item that adds to AC states that in its `effects` list, not by being typed armor.
   - Status: never write `status` for hit point reasons. The rules engine sets "unconscious" when hit points reach 0 and "alive" when they rise above 0; `dead` is the DM's call.

   - **Example - Shield is destroyed:**
     ```json
     {{
       "equipment": [{{ "item_name": "Shield", "quantity": 0, "equipped": false }}]
     }}
     ```
   - **Example - Swapping from a Mace to a Longsword:**
     ```json
     {{
       "equipment": [
         {{ "item_name": "Mace", "equipped": false }},
         {{ "item_name": "Longsword", "equipped": true }}
       ],
       "attacksAndSpellcasting": [
         {{ "name": "Longsword", "attackBonus": 4, "damageDice": "1d8", "damageBonus": 2 }}
       ]
     }}
     ```

5. **For Conditions and Status Effects:**
   - Conditions are facts you state: when a condition is gained or ends (poisoned, frightened, grappled, paralyzed, etc.), return the complete `condition_affected` list as it should now be, and `condition` naming the most severe entry ("none" when the list is empty). The rules engine holds each one and applies its numbers (speed, roll penalties).
   - The engine adds and removes "unconscious" itself from hit points: never add it because damage reached 0 and never remove it because of healing.
   - Exhaustion is a level, not a list entry: "gains a level of exhaustion" / "loses a level" -> return `exhaustion` as the new whole number (0-6) computed from the current sheet value. The engine lists it in `condition_affected`, applies the speed and d20 penalties, and removes one level at every Long Rest by itself (never do that from a rest note).
   - **Example - Applying poisoned condition:**
     ```json
     {{
       "condition": "poisoned",
       "condition_affected": ["poisoned"]
     }}
     ```

6. **Standard Ammunition Names (for a NEW row only; a row already on the sheet keeps its own name exactly as listed):**
   - "Arrows" (plural) - for bow ammunition
   - "Crossbow bolts" (plural) - for crossbow ammunition
   - "Sling bullets" (plural) - for sling ammunition
   - "Darts" (plural) - for thrown darts
   - "Blowgun needles" (plural) - for blowgun ammunition
   - Always use plural form for consistency

**CRITICAL EDGE CASES:**
- When equipment that affects AC is added, removed, equipped, or unequipped, return only the `equipment` change; the rules engine recomputes `armorClass` and `equipment_effects`. The engine refuses illegal states (two shields, three held weapons); if told a change was refused, propose a legal one.
- When a weapon is changed, you **MUST** update the relevant entry in the `attacksAndSpellcasting` array.
- When a temporary effect is added or removed, you **MUST** return the **complete** `temporaryEffects` array, containing only the effects that should remain active. This is the one exception to the delta-only rule for lists.
- Down/unconscious (house rule, NO death saves): damage that reaches 0 is an `hpDelta` and nothing else; the engine stops at 0 and marks the character unconscious; never write death saves; a character at 0 dies only if the whole party falls; a heal, potion, Medicine, or rest that restores them is a positive `hpDelta` and nothing else (the engine wakes them)
- Conditions: state the complete `condition_affected` list and the most severe `condition` whenever a condition (other than unconscious) is gained or ends

**Your adherence to these delta-only rules is paramount. Generate the most minimal, targeted JSON possible while ensuring ALL logically affected fields are included.**

**CRITICAL: The examples above are for learning purposes only. Do NOT include example JSON in your response. Only return the specific updates needed for the requested changes.**

**HIT POINTS, SPELL SLOTS AND FEATURE USES ARE ENGINE-OWNED (report the change, never the count):**
- Hit points: return {{"hpDelta": <signed int>}}. "takes 7 damage" / "loses 7 hit points" -> -7; "regains 13 hit points" / "healed for 13" -> 13.
  NEVER return `hitPoints`: the engine applies the change to the real sheet, stops healing at the maximum and stops damage at 0.
  A note that only states a resulting total ("now at 12 HP") with no amount is a balance statement: return {{}} and let it be corrected rather than guessing.
- Spell slots: return {{"spellSlotDelta": {{"levelN": -1}}}} per leveled spell cast (cantrips: nothing). NEVER return a slot `current`;
  the engine refuses a cast with no slot left and you are told.
- Feature uses: return {{"featureUseDelta": {{"<exact stored feature name>": -1}}}} for the resource-owning feature (a shared option spends
  its parent's pool). NEVER return `usage.current`; the engine refuses a use beyond the pool and you are told.
- Refills ("regains one use", "recovers two 1st-level slots") are positive amounts; the engine stops at each maximum.
- Temporary hit points: "gains 10 temporary hit points" -> {{"tempHpGrant": 10}} (positive only). NEVER return
  `temporaryHitPoints`. Damage drains temporary hit points before hit points automatically: report the damage taken
  as hpDelta and nothing else; never subtract temporary hit points yourself. A long rest clears them.
- Only the pools the note names, only the amounts it states. A cast note with no healing amount ("Expends one 1st-level
  spell slot to cast Cure Wounds") is the slot change only; never infer a heal from a spell's name or an earlier wound.

{schema_info}

MAGICAL ITEM RECOGNITION - AUTOMATIC EFFECTS:
When adding equipment that appears to be magical based on its name or description (contains +1/+2/+3, grants bonuses, provides resistance, etc.), you MUST include an 'effects' array with appropriate mechanical effects. Use your knowledge of 5th Edition rules.

Common magical items and their effects:
- Ring/Cloak of Protection: +1 to AC and saving throws
- Gauntlets of Ogre Power: Set Strength to 19
- Amulet of Health: Set Constitution to 19
- Boots of Speed: Double movement speed (speed x2)
- Cloak of Elvenkind: Advantage on Dexterity (Stealth) checks
- Bracers of Defense: +2 AC when not wearing armor
- Belt of Giant Strength: Set Strength (Hill=21, Stone=23, Frost=23, Fire=25, Cloud=27, Storm=29)
- Ring of Resistance: Resistance to specific damage type
- Periapt of Wound Closure: Stabilize automatically when dying
- Weapon +1/+2/+3: Bonus to attack and damage rolls
- Armor +1/+2/+3: Bonus to AC
- Shield +1/+2/+3: Additional AC bonus beyond base shield

MAGICAL ITEM EQUIPMENT ENTRY FORMAT:
{{
  "item_name": "Ring of Protection +1",
  "item_type": "miscellaneous",  // or appropriate type
  "item_subtype": "ring",        // ring, amulet, cloak, boots, gloves, etc.
  "description": "A magical ring that grants +1 bonus to AC and saving throws",
  "quantity": 1,
  "equipped": true,              // or false if just adding to inventory
  "effects": [
    {{
      "type": "bonus",           // bonus, resistance, immunity, advantage, disadvantage, ability_score, other
      "target": "AC",            // what it affects: AC, saves, specific save, ability check, etc.
      "value": 1,                // numeric value if applicable
      "description": "+1 bonus to Armor Class"
    }},
    {{
      "type": "bonus",
      "target": "saving throws",
      "value": 1,
      "description": "+1 bonus to all saving throws"
    }}
  ]
}}

EFFECT TYPE GUIDANCE:
- "bonus": Numerical bonuses (+1 AC, +2 attack, etc.)
- "resistance": Damage resistance (fire, cold, etc.)
- "immunity": Damage or condition immunity
- "advantage": Advantage on specific rolls
- "disadvantage": Disadvantage (usually imposed on enemies)
- "ability_score": Sets or modifies ability scores
- "other": Any other magical effect

IMPORTANT MAGICAL ITEM RULES:
1. If an item grants mechanical benefits, it MUST have an effects array
2. Non-magical items (regular sword, rope, torch) should NOT have effects
3. For items that set ability scores (Gauntlets of Ogre Power), ALSO update the abilities object
4. For AC bonuses, you may also update armorClass if appropriate
5. Custom magical items should have effects inferred from their description

CRITICAL INSTRUCTIONS:
1. Return ONLY a JSON object with the fields that need to be updated
2. Do not include unchanged fields
3. Ensure all values match the schema requirements exactly
4. IMPORTANT: For equipment arrays, return ONLY the specific items being modified, NOT the entire array
5. Maintain data integrity and consistency
6. IMPORTANT: When updating nested objects like 'spellcasting', include ALL existing subfields to prevent data loss
7. NEVER return partial nested objects that would delete existing important data
8. Spell slot counts never appear inside 'spellcasting'; a cast or a refill is spellSlotDelta. Edit 'spellcasting' only for spells known/prepared or a change of casting ability, and then include ability, spellSaveDC, spellAttackBonus, and spells fields as they are (the DC and bonus are derived by the rules engine; any value you write for them is replaced)
9. SPELL SLOT RULE: Cantrips (0-level spells) do NOT consume spell slots. Only deduct spell slots for leveled spells (1st-9th level).
10. HIT DICE RULE: IGNORE all references to hit dice, Hit Dice, HD, or hit dice restoration. Do NOT add hitDice, hitDiceRestored, or maxHitDice fields. The system does not track hit dice.
11. REST HEALING: Rests are applied by the rest action, not by you. A rest note reaching you carries only an extra narrated amount ("Regains 9 hit points"): return it as a positive hpDelta. Never refill slots or pools from a rest note; the engine already did. Do not implement hit dice mechanics.
12. CURRENCY MANAGEMENT - CRITICAL RULES:
    a) Coins are owned by the rules engine. Report the CHANGE, never the balance: return
       {{"currencyDelta": {{"gold": <signed int>, "silver": <signed int>, "copper": <signed int>}}}}
       with only the coin types that change. Negative = paid or given away, positive = received or found.
    b) NEVER return a "currency" object and never compute a final total; the engine applies the delta to
       the sheet's real balance and refuses a payment the character cannot cover.
    c) A payment in a coin the character lacks is two signed entries the DM stated (e.g. change a gold
       piece: {{"currencyDelta": {{"gold": -1, "silver": 8}}}} for a 2 silver fee). Do not invent a conversion
       the request did not describe.
    d) A verb governs every coin listed after it: "Remove 1 silver and 10 copper" is silver -1 AND copper -10;
       a coin is positive only when its own verb says add/receive/find/take back. "Pay 1 silver, take 8 copper
       in change" is silver -1, copper +8. Never flip a sign to make a transaction "balance".
    e) Examples: pays 100 gold -> {{"currencyDelta": {{"gold": -100}}}}; finds 50 gold and 20 silver ->
       {{"currencyDelta": {{"gold": 50, "silver": 20}}}}; "kept 38 gold" is a balance statement, not a change:
       return {{}} and let the request be corrected rather than guessing a delta.
13. STATUS AND HIT POINTS: `status` unconscious/alive follows hit points and is written by the rules engine, never by you. Report the `hpDelta` only. Conditions you state (poisoned, grappled...) stay until you remove them from `condition_affected`; a rest or the passing of time removes nothing by itself.
14. RESOURCE TRACKING RULES:
    - "spell slot" or "expends [level] spell slot" -> spellSlotDelta only
    - For an ability, read its actual cost and identify the exact resource-owning feature in the current sheet. A shared option spends its parent's classFeatures[].usage, not an independent option counter.
    - If ability description mentions "expending a spell slot" -> ONLY spellSlotDelta
15. CLASS FEATURE USAGE TRACKING:
    When updating ability uses (not spell slots):
    a) Spend or refill with featureUseDelta on the exact stored resource-owning feature name. A classFeatures usage object is only for a structural correction (a missing real pool, or usage:null); never for a count.
    b) Omitted usage preserves the saved value. Explicit usage:null is saved as no independent use pool, NOT free/unlimited use or a deletion operator. Emit it only when the requested rules-grounded correction explicitly calls for removing that obsolete independent counter; never clear a real pool by default.
    c) An option with usage:null describes its exact parent and cost. Spend that parent's counter. Do not create an option counter or rename an entry to evade the merge. Add a missing real independent pool only when the requested change and actual rules establish it, never from an old label alone.
    d) refreshOn is a trigger tag, not recovery amount or exclusivity. Preserve the description's actual partial/full recovery rules; use longRest for an applicable full reset. Do not refill resources during level-up or spend spell slots unless the actual cost requires them.
    e) Existing spell level lists/preparedSpells may include always-prepared grants. Exclude justified grants from ordinary preparation capacity without removing their spell access; do not invent alwaysPreparedSpells.
16. RESOURCE UPDATE EXAMPLES:
    Current: Pool has usage {{"current": 1, "max": 2, "refreshOn": "longRest"}}; Option has usage:null and description "Spend one use of Pool."
    Input: "Uses Option, spending one use of Pool"
    Update: {{"featureUseDelta": {{"Pool": -1}}}}
    
    Input: "Expends one 1st-level spell slot"  
    Update: {{"spellSlotDelta": {{"level1": -1}}}}
    
    Input: "Uses Divine Smite by expending a 2nd-level spell slot"
    Update: {{"spellSlotDelta": {{"level2": -1}}}}
    Note: Do NOT update any Divine Smite usage counter - only the spell slot
17. AMMUNITION IS THE ENGINE'S - CRITICAL:
    - A row ALREADY on the sheet changes only by quantityDelta: the signed number fired, bought, found, sold or lost. NEVER the resulting count.
      Example: sheet has Crossbow bolt x60, "Fired 3 crossbow bolts at the mark and recovered 2" -> {{"ammunition": [{{"name": "Crossbow bolt", "quantityDelta": -1}}]}}
      Example: "Bought 20 crossbow bolts" -> {{"ammunition": [{{"name": "Crossbow bolt", "quantityDelta": 20}}]}}
      Example: "Sold 100 crossbow bolts" -> {{"ammunition": [{{"name": "Crossbow bolt", "quantityDelta": -100}}]}} (send the number named even if the sheet holds fewer; the engine refuses and the DM is told)
    - name is the row's name EXACTLY as the sheet lists it (singular or plural as written), never a standard name
    - quantity on an existing row is refused, except quantity 0 to remove the row entirely ("lost all the bolts")
    - A NEW kind of ammunition (no such row on the sheet) is created with quantity = how many were acquired, plus a description
    - Never write recoverable: the rules engine keeps that count
18. EXPERIENCE POINTS ARE THE ENGINE'S - CRITICAL:
    - NEVER write experience_points, exp_required_for_next_level or levelUpsPending: XP is awarded through the awardExperience action and the rules engine adds it; any value you write for these fields is dropped
    - A change text that mentions XP ("Awarded 50 experience points") changes nothing here: return the other requested fields only (or {{}} when there are none)
    - Level up changes level, maxHitPoints, hitPoints, classFeatures, etc. and never XP
19. DERIVED TOTALS ARE THE ENGINE'S: proficiencyBonus, initiative, senses.passivePerception, every skill bonus, spellSaveDC and spellAttackBonus are computed by the rules engine from level, ability scores, proficiencies, expertise and feats. Never write them; a value you write is dropped. State the fact instead: a new skill proficiency is the skill added to 'skills' (any number), a new saving throw proficiency is the ability added to 'savingThrows', expertise is the skill added to 'expertise', a feat is added to 'feats', an ability score change is the new score in 'abilities'.
20. CONCENTRATION IS THE ENGINE'S: never write `concentration` (the caster's record is code-written) and never end a spell because its caster was hit; the engine makes the Constitution save when the damage you report lands and ends the spell everywhere on a failure. Report the hpDelta only.
{effects_update_rules}

EQUIPMENT UPDATE EXAMPLES:
CORRECT (updating one item): {{"equipment": [{{"item_name": "Jeweled dagger", "description": "updated description", "magical": true}}]}}
CORRECT (more of an item already carried): {{"equipment": [{{"item_name": "Travel Ration", "quantityDelta": 3}}]}}
WRONG (states a count for an item already carried): {{"equipment": [{{"item_name": "Travel Ration", "quantity": 4}}]}}
WRONG (would delete all other items): {{"equipment": [...]}} with multiple items

DANGEROUS EXAMPLE (DO NOT DO):
{{"spellcasting": {{"spellSlots": {{...}}}}}} // This deletes ability, DC, bonus, and spells!

SAFE EXAMPLE:
{{"spellcasting": {{"ability": "wisdom", "spellSaveDC": 13, "spellAttackBonus": 5, "spells": {{...}}, "spellSlots": {{...}}}}}} // This preserves all data

CONDITION MANAGEMENT EXAMPLES:
CORRECT (healing an unconscious character): {{"hpDelta": 12}} // the engine wakes them
WRONG: {{"hpDelta": 12, "status": "alive", "condition": "none", "condition_affected": []}} // status is the engine's
CORRECT (grappled by a bandit while already poisoned): {{"condition": "grappled", "condition_affected": ["grappled", "poisoned"]}}
CORRECT (the bandit lets go): {{"condition": "poisoned", "condition_affected": ["poisoned"]}}
CORRECT (a forced march, current exhaustion 1): {{"exhaustion": 2}}
WRONG: {{"condition_affected": ["exhaustion"]}} // exhaustion is the number, the engine lists it

RESOURCE TRACKING EXAMPLES:

Example 1 - Explicit obsolete option-counter correction (NO resource spending):
Changes: "Correct Option to use the existing Pool rather than an independent counter; preserve remaining Pool uses."
Current classFeatures includes Pool with usage {{"current": 1, "max": 2, "refreshOn": "longRest"}} and Option with an obsolete independent usage object.
Update: {{"classFeatures": [{{"name": "Option", "description": "Spend one use of Pool.", "usage": null}}]}}
Pool remains at 1/2 because it is omitted. Option's explicit null persists and prevents a separate use pool; the option still pays its actual parent cost. Preserve other existing description details when applying a real correction.

Example 2 - Regular Spell:
Changes: "Casts Cure Wounds, expending one 1st-level spell slot"
Current spellSlots: {{"level1": {{"current": 3, "max": 3}}}}
Update: {{"spellSlotDelta": {{"level1": -1}}}}

Example 3 - Ability Using Spell Slots:
Changes: "Uses Divine Smite by expending a 2nd-level spell slot for extra damage"
Current spellSlots: {{"level2": {{"current": 2, "max": 2}}}}
Update: {{"spellSlotDelta": {{"level2": -1}}}}
Note: Divine Smite is an ability that costs spell slots - only the slot delta, no featureUseDelta

AMMUNITION EXAMPLES (rows already on the sheet: quantityDelta with the sheet's own row name):
Example 1 - Buying more:
Changes: "Added 25 crossbow bolts to inventory" (sheet row: Crossbow bolt x60)
Update: {{"ammunition": [{{"name": "Crossbow bolt", "quantityDelta": 25}}]}}

Example 2 - Selling or firing:
Changes: "Sold 100 crossbow bolts to Trader Sila" (sheet row: Crossbow bolt x60)
Update: {{"ammunition": [{{"name": "Crossbow bolt", "quantityDelta": -100}}]}}  (not clamped: the engine refuses a short stock)

Example 3 - A new kind plus a change to an existing row:
Changes: "Bought 30 arrows, sold 50 crossbow bolts" (sheet rows: Crossbow bolt x60, no arrows)
Update: {{"ammunition": [{{"name": "Arrows", "quantity": 30, "description": "Standard arrows"}}, {{"name": "Crossbow bolt", "quantityDelta": -50}}]}}

EXPERIENCE POINTS EXAMPLE (engine-owned, never written here):
Changes: "Awarded 50 experience points for the ambush"
Update: {{}}
(XP reaches the sheet through the awardExperience action and the rules engine; this field is dropped if written.)

Character Role: {character_role}
"""

    # Debug log the character's current currency and ammunition
    debug(f"CURRENCY_CHECK: {character_name} current currency: {character_data.get('currency', {})}", category="character_updates")
    debug(f"AMMUNITION_CHECK: {character_name} current ammunition: {character_data.get('ammunition', [])}", category="character_updates")
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Current character data:\n{json.dumps(prompt_character_data, indent=2)}"},
        {"role": "user", "content": f"Changes to make: {changes}"}
    ]
    
    # Add conversation history for context (last 10 messages)
    if history:
        recent_history = history[-10:]
        for msg in recent_history:
            if msg.get('role') in ['user', 'assistant']:
                messages.insert(-2, {"role": msg['role'], "content": msg['content']})

    if action_context is not None:
        messages.insert(-2, {
            "role": "user",
            "content": f"Accepted action context (current_index identifies this step, not a commit receipt):\n{json.dumps(action_context, indent=2)}",
        })
    
    # #432 (D-432-1): only unusable answers count toward the bound. A provider
    # refusal and a supersession leave the loop at once; a confirmation
    # request for a {} answer is not a failure.
    bounded_failure_limit = 3
    bounded_failure_count = 0
    attempt = 1
    
    # T079 MIGRATION NOTE: Gemini requires response_schema forcing on this callsite.
    # The schema is auto-converted from schemas/char_schema.json at runtime and
    # passed via the config dict. purge_invalid_fields() strips spurious extra keys.
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        char_update_config = config.CHAR_UPDATE_GPT5MINI_LOW
    elif MODEL_PROVIDER == "gemini":
        char_update_config = copy.deepcopy(
            config.CHAR_UPDATE_GEMINI_FLASHLITE_LOW
        )
        requested_delta_schema = build_requested_character_delta_gemini_schema(
            changes,
            schema,
        )
        if requested_delta_schema is not None:
            char_update_config["response_schema"] = requested_delta_schema
        response_schema = char_update_config.get("response_schema")
        if response_schema is not None:
            feature_usage = (response_schema.get("properties", {})
                .get("classFeatures", {}).get("items", {})
                .get("properties", {}).get("usage"))
            if feature_usage is not None:
                feature_usage["nullable"] = True
    elif MODEL_PROVIDER == "lmstudio":
        char_update_config = config.CHAR_UPDATE_LMSTUDIO
    else:  # legacy
        char_update_config = config.CHAR_UPDATE_LEGACY

    # HIGH-6: fail loudly (not silently) if the Gemini char-update schema failed
    # to load at import. Without response_schema, Gemini-flash-lite emits
    # narration instead of a character delta, purge_invalid_fields strips
    # everything, and the update silently no-ops (the False return is swallowed
    # by the ThreadPoolExecutor consumer). This guard trips ONLY under the gemini
    # provider, so openai/legacy/lmstudio are unaffected, and it lives at the
    # callsite -- NOT a hard import raise, which would break every provider if the
    # schema file were missing.
    if MODEL_PROVIDER == "gemini" and char_update_config.get("response_schema") is None:
        raise RuntimeError(
            "T079 character update aborted: Gemini response_schema is None "
            "(schemas/char_schema.json failed to load at import). Refusing to run "
            "-- Gemini would emit narration and silently drop all character "
            "updates. Restore the schema file or set MODEL_PROVIDER off gemini."
        )

    primary_committed = False
    validation_success = None
    last_update_error = None
    # The engine-owned effect operation is itself the change, so an empty
    # delta beside it needs no confirmation.
    # A callable operation is a lazy T078 classifier (core/managers/effects_runtime):
    # it is resolved on each parsed T079 delta below and runs the classifier only
    # when the delta carries "effectChange" or is empty.
    lazy_classifier = managed_effect_operation if callable(managed_effect_operation) else None
    if lazy_classifier is not None:
        managed_effect_operation = None
    engine_owned_change = declarative_effects and managed_effect_operation
    # A {} answer is accepted only when the immediately preceding T079 answer
    # in this update was also {} (#432): the first one is asked to confirm.
    previous_answer_was_empty = False
    # An engine refusal that the model then abandons with {} (or that outlasts
    # the attempt bound) is reported to the caller as a refusal, not accepted
    # as "no change".
    last_engine_refusal = None
    while structural_reissue or bounded_failure_count < bounded_failure_limit:
        try:
            if commit_guard is not None:
                with commit_guard():
                    pass
            debug(
                f"STATE_CHANGE: Attempt {attempt} (bounded failures "
                f"{bounded_failure_count} of {bounded_failure_limit})",
                category="character_updates",
            )

            response = capture_and_fanout("T079", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=messages,
                model=char_update_config["model"],
                temperature=TEMPERATURE,
                **{k: v for k, v in char_update_config.items() if k != "model"})
            
            # Track usage
            if USAGE_TRACKING_AVAILABLE:
                try:
                    track_response(response)
                except:
                    pass
            
            raw_response = response.choices[0].message.content.strip()
            prior_answer_was_empty = previous_answer_was_empty
            previous_answer_was_empty = False

            # Log the raw LLM response for debugging ammunition issues
            if "ammunition" in changes.lower() or "bolt" in changes.lower() or "arrow" in changes.lower():
                debug(f"LLM_RESPONSE for ammunition update: {raw_response[:500]}...", category="character_updates")
            
            # Enhanced debug logging for NPCs
            if character_role == 'npc':
                debug_info = {
                    "attempt": attempt,
                    "npc_name": character_name,
                    "changes": changes,
                    "raw_ai_response": raw_response
                }
                os.makedirs("debug", exist_ok=True)
                safe_write_json("debug/debug_npc_update.json", debug_info)
            
            # COMPREHENSIVE DEBUG LOGGING FOR ALL CHARACTER UPDATES
            # Initialize debug data that will be updated throughout the process
            debug_data = {
                "timestamp": datetime.now().isoformat(),
                "character_name": character_name,
                "character_role": character_role,
                "attempt": attempt,
                "changes_requested": changes,
                "raw_ai_response": raw_response,
                # Actual model: capture_and_fanout overrides to the registry binding
                # before the call, so read it from the response, not the pre-override
                # char_update_config (which holds a stale compatibility model string).
                "model_used": getattr(response, "model", None) or char_update_config["model"],
                "parsed_updates": None,
                "validation_results": {},
                "final_outcome": "pending"
            }
            
            # Create debug directory if needed
            os.makedirs("debug", exist_ok=True)
            
            # Use a single debug log file that gets appended to
            debug_log_file = "debug/character_updates_log.json"
            
            # Load existing debug log or create new one
            if os.path.exists(debug_log_file):
                try:
                    # Check file size first - if it's over 10MB, just start fresh
                    file_size = os.path.getsize(debug_log_file)
                    if file_size > 10 * 1024 * 1024:  # 10MB limit
                        print(f"DEBUG: Character updates log too large ({file_size} bytes), starting fresh")
                        debug_log = {"updates": []}
                    else:
                        with open(debug_log_file, 'r') as f:
                            debug_log = json.load(f)
                            # Immediately trim to last 20 entries when loading
                            if len(debug_log.get("updates", [])) > 20:
                                debug_log["updates"] = debug_log["updates"][-20:]
                except Exception as e:
                    print(f"DEBUG: Error loading debug log: {e}")
                    debug_log = {"updates": []}
            else:
                debug_log = {"updates": []}
            
            # Also print to console for immediate visibility
            # print(f"\n[DEBUG CHARACTER UPDATE] {character_name}")
            # print(f"Changes requested: {changes}")
            # print(f"AI Response: {raw_response[:500]}{'...' if len(raw_response) > 500 else ''}")
            # print(f"Full response saved to: {debug_filename}\n")
            
            # Parse the typed response directly; never mine brace-shaped prose
            # for gameplay state.
            clean_response = raw_response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[len("```json") :]
            if clean_response.endswith("```"):
                clean_response = clean_response[: -len("```")]
            clean_response = clean_response.strip()
            updates = json.loads(clean_response)
            effect_flag = None
            if isinstance(updates, dict):
                effect_flag = updates.pop("effectChange", None)
            if lazy_classifier is not None and isinstance(updates, dict):
                managed_effect_operation = lazy_classifier(updates, effect_flag)
                engine_owned_change = declarative_effects and managed_effect_operation
            if not _is_meaningful_character_delta(updates, schema) and not (
                engine_owned_change
            ):
                raise ValueError(
                    "T079 returned an empty or unrecognized character delta"
                )
            if updates == {}:
                if last_engine_refusal:
                    raise EngineRefusedChange(last_engine_refusal)
                previous_answer_was_empty = True
                if not engine_owned_change:
                    if not prior_answer_was_empty:
                        confirmation_note = (
                            "\n\nYour previous answer was {} (no character-sheet "
                            "field changes). If the described change alters any "
                            "field on this sheet (hit points, spell slots, "
                            "equipment, ammunition, currency, experience, "
                            "conditions or any other field), return those fields "
                            "now. Narrative descriptions that no rule tracks, such "
                            "as being wet or muddy, are not sheet changes. If it "
                            "changes nothing on the sheet, return {} again."
                        )
                        messages[-1]["content"] += confirmation_note
                        attempt += 1
                        continue
                    info(
                        f"T079 confirmed no mechanical change for {character_name}",
                        category="character_updates",
                    )

            if declarative_effects:
                # T079 is never an effects authority after cutover, even when a
                # weaker model ignores the ownership instruction.
                updates.pop("temporaryEffects", None)
            elif "temporaryEffects" in updates:
                from core.effects.model import preserve_engine_effects

                updates["temporaryEffects"] = preserve_engine_effects(
                    character_data.get("temporaryEffects", []),
                    updates.get("temporaryEffects", []),
                )
            if effective_projection:
                updates = _translate_declarative_effect_delta(
                    character_data,
                    updates,
                    managed_effect_operation if declarative_effects else None,
                )

            is_complete, missing_fields = validate_requested_character_update_completeness(
                changes,
                updates,
            )
            if not is_complete:
                missing_list = ", ".join(missing_fields)
                feedback_message = (
                    "\n\nPREVIOUS ATTEMPT INCOMPLETE: The requested change affects "
                    f"these missing top-level fields: {missing_list}. Return one "
                    "delta JSON object containing every listed field together with "
                    "the fields you already returned. Do not apply only part of the "
                    "requested state change."
                )
                messages[-1]["content"] += feedback_message
                warning(
                    f"T079 incomplete delta on attempt {attempt}; missing: {missing_list}",
                    category="character_validation",
                )
                debug_data["validation_results"] = {
                    "requested_fields_complete": False,
                    "missing_requested_fields": missing_fields,
                }
                bounded_failure_count += 1
                attempt += 1
                continue
            
            # Update debug data with parsed updates
            debug_data["parsed_updates"] = updates
            
            # Log the parsed JSON update - Commented out to prevent debug leak to player screen
            # print(f"[DEBUG PARSED JSON] {character_name}")
            # print(f"Updates to apply: {json.dumps(updates, indent=2)[:1000]}{'...' if len(json.dumps(updates)) > 1000 else ''}\n")
            
            # DEBUG: Check if XP update is in the updates
            if 'experience' in changes.lower() and 'experience_points' not in updates:
                print(f"DEBUG: [XP Warning] XP change requested but experience_points not in updates!")
                print(f"DEBUG: [XP Warning] AI returned: {updates}")
            
            
            # Apply updates to character data using deep merge
            # print(f"[DEBUG] About to call deep_merge_dict for {character_name}")
            # print(f"[DEBUG] Character has ammunition: {'ammunition' in character_data}")
            # if 'ammunition' in character_data:
            #     print(f"[DEBUG] Current ammunition: {character_data['ammunition']}")
            # print(f"[DEBUG] Updates contain ammunition: {'ammunition' in updates}")
            # if 'ammunition' in updates:
            #     print(f"[DEBUG] Ammunition updates: {updates['ammunition']}")
            
            
            # Currency is engine-owned: prepare_character_delta applies a
            # currencyDelta through core/nql/currency and refuses totals.
            
            # Debug HP changes BEFORE merge
            if 'hitPoints' in updates:
                debug(f"HP_DEBUG: {character_name} - Before merge HP: {character_data.get('hitPoints')}/{character_data.get('maxHitPoints')}, Update wants HP: {updates.get('hitPoints')}", category="character_updates")
            
            updates, updated_data, preparation_checks = prepare_character_delta(
                character_data, updates, character_role, schema, character_name,
                managed_effect_operation if declarative_effects else None,
                model_authored=True,
            )
            
            # Debug HP changes AFTER merge
            if 'hitPoints' in updates:
                debug(f"HP_DEBUG: {character_name} - After merge HP: {updated_data.get('hitPoints')}/{updated_data.get('maxHitPoints')}", category="character_updates")
            
            # print(f"[DEBUG] deep_merge_dict completed successfully")
            
            
            # print(f"[DEBUG] Checking ammunition after merge:")
            # if 'ammunition' in updated_data:
            #     print(f"[DEBUG] Updated ammunition: {updated_data['ammunition']}")
            
            # Validate that critical fields weren't accidentally deleted
            # print(f"[DEBUG] About to validate critical fields")
            critical_warnings = preparation_checks['critical_warnings']
            # print(f"[DEBUG] Critical field validation completed. Warnings: {critical_warnings}")
            if critical_warnings:
                for crit_warning in critical_warnings:
                    error(f"CRITICAL WARNING: {crit_warning}", category="character_validation")
                error("FAILURE: Aborting update to prevent data loss. AI response may be incomplete.", category="character_validation")
                
                # Log the problematic update for debugging
                debug_info = {
                    "character_name": character_name,
                    "attempt": attempt,
                    "warnings": critical_warnings,
                    "original_spellcasting": character_data.get('spellcasting', {}),
                    "update_data": updates,
                    "ai_response": raw_response
                }
                os.makedirs("debug", exist_ok=True)
                safe_write_json("debug/debug_critical_field_loss.json", debug_info)
                debug("FILE_OP: Debug info saved to debug/debug_critical_field_loss.json", category="file_operations")
                
                bounded_failure_count += 1
                attempt += 1
                continue
            
            # Shared provider-free preparation retains the ordinary error policy.
            removed_fields = preparation_checks['removed_fields']
            # print(f"[DEBUG] Field purging completed. Removed fields: {removed_fields}")
            if removed_fields:
                warning(f"VALIDATION: Purged {len(removed_fields)} invalid fields: {', '.join(removed_fields)}", category="character_validation")
            
            # Validate updated data
            # print(f"[DEBUG] About to validate character data against schema")
            is_valid = preparation_checks['schema_valid']
            error_msg = preparation_checks['error_message']
            last_engine_refusal = preparation_checks.get('engine_refusal') if not is_valid else None
            # print(f"[DEBUG] Schema validation completed. Valid: {is_valid}, Error: {error_msg}")
            
            # Update debug data with validation results
            debug_data["validation_results"] = {
                "schema_valid": is_valid,
                "error_message": error_msg if not is_valid else None,
                "removed_fields": removed_fields if removed_fields else []
            }
            
            if not is_valid:
                error(f"VALIDATION: Validation failed: {error_msg}", category="character_validation")
                if last_engine_refusal:
                    # The engine refused the amount the change stated (not
                    # enough coins, stock, slots or uses). T079 must not
                    # reinterpret the amount: a retry that sees the refusal
                    # clamps it to what the sheet holds (observed live). The
                    # DM decides what happens instead; nothing was written.
                    raise EngineRefusedChange(last_engine_refusal)
                bounded_failure_count += 1
                
                # Add validation error feedback to the prompt for next attempt
                if "item_subtype" in error_msg and "is not one of" in error_msg:
                    # Extract the problematic subtype
                    subtype_start = error_msg.find("'") + 1
                    subtype_end = error_msg.find("'", subtype_start)
                    invalid_subtype = error_msg[subtype_start:subtype_end] if subtype_start > 0 and subtype_end > subtype_start else "unknown"
                    
                    feedback_message = f"\n\nPREVIOUS ATTEMPT FAILED: The item_subtype '{invalid_subtype}' is not valid. Valid item_subtype values are: ['scroll', 'potion', 'wand', 'ring', 'amulet', 'cloak', 'boots', 'gloves', 'helmet', 'rod', 'staff', 'food', 'other']. For food items like trail rations, use 'food' as the item_subtype."
                    messages[-1]["content"] += feedback_message
                else:
                    # Generic validation error feedback
                    feedback_message = f"\n\nPREVIOUS ATTEMPT FAILED: {error_msg}. Please fix the validation error in your next response."
                    messages[-1]["content"] += feedback_message
                
                attempt += 1
                continue
            
            # Final repair is included in the shared preparation result.
            
            if prepare_only:
                return {
                    "kind": "updateCharacterInfo",
                    "owner": character_name,
                    "role": character_role,
                    "path": character_path,
                    "before": persisted_character_data,
                    "after": updated_data,
                    "changes": changes,
                }

            # Save updated character data
            # print(f"[DEBUG] Validation passed! About to save character data to: {character_path}")
            
            # DEBUG: Log XP before saving
            if 'experience_points' in updated_data:
                print(f"DEBUG: [XP Save] About to save {character_name} with XP: {updated_data.get('experience_points')}")
            
            # Enhanced debugging for save failures
            print(f"DEBUG: [SAVE] Attempting to save {character_name} to {character_path}")
            print(f"DEBUG: [SAVE] File exists: {os.path.exists(character_path)}")
            
            # Check for lock files that might block the save
            lock_file = f"{character_path}.lock"
            if os.path.exists(lock_file):
                print(f"DEBUG: [SAVE] WARNING - Lock file exists: {lock_file}")
                try:
                    lock_age = time.time() - os.path.getmtime(lock_file)
                    print(f"DEBUG: [SAVE] Lock file age: {lock_age:.2f} seconds")
                    with open(lock_file, 'r') as f:
                        lock_pid = f.read().strip()
                        print(f"DEBUG: [SAVE] Lock held by PID: {lock_pid}")
                except Exception as e:
                    print(f"DEBUG: [SAVE] Could not read lock file: {e}")
            
            save_result = commit_character_sheet(character_path, updated_data, commit_guard=commit_guard)
            if save_result:
                primary_committed = True
            try:
                print(f"DEBUG: [SAVE] safe_write_json returned: {save_result}")
            except Exception as exc:
                if commit_guard is None or isinstance(exc, LiveProviderSuperseded):
                    raise
                warning(f"Save-result diagnostic failed: {exc}", category="character_updates")
            
            if save_result:
                try:
                    # print(f"[DEBUG] Character data saved successfully!")
                    info(f"SUCCESS: Successfully updated {character_name} ({character_role})!", category="character_updates")

                    # Debug HP after save
                    if 'hitPoints' in updates:
                        saved_data = safe_read_json(character_path) or {}
                        debug(f"HP_DEBUG: {character_name} - After save HP: {saved_data.get('hitPoints')}/{saved_data.get('maxHitPoints')}", category="character_updates")

                    # Update debug data with success
                    debug_data["final_outcome"] = "success"
                    debug_data["validation_results"]["ai_validator_run"] = validation_success

                    # Add to consolidated debug log
                    debug_log["updates"].append(debug_data)
                    # Keep only last 20 entries to prevent file from growing too large
                    if len(debug_log["updates"]) > 20:
                        debug_log["updates"] = debug_log["updates"][-20:]
                    safe_write_json(debug_log_file, debug_log)
                    debug(f"Debug log updated: {debug_log_file}", category="character_updates")

                    # DEBUG: Verify XP was saved correctly
                    if 'experience_points' in updates:
                        saved_data = safe_read_json(character_path)
                        if saved_data:
                            saved_xp = saved_data.get('experience_points', 0)
                            expected_xp = updated_data.get('experience_points', 0)
                            print(f"DEBUG: [XP Verify] After save - Expected XP: {expected_xp}, Actual XP in file: {saved_xp}")
                            if saved_xp != expected_xp:
                                print(f"DEBUG: [XP Verify] WARNING: XP mismatch after save!")

                    # Log the changes with more detail for user feedback
                    changed_fields = list(updates.keys())
                    debug(f"STATE_CHANGE: Updated fields: {', '.join(changed_fields)}", category="character_updates")

                    # Provide user-friendly update notification
                    if 'equipment' in changed_fields:
                        info(f"[Character Update] {character_name}'s equipment/inventory updated", category="character_updates")
                    elif 'currency' in changed_fields:
                        info(f"[Character Update] {character_name}'s currency updated", category="character_updates")
                    else:
                        info(f"[Character Update] {character_name}'s {', '.join(changed_fields)} updated", category="character_updates")
                except Exception as exc:
                    if commit_guard is None or isinstance(exc, LiveProviderSuperseded):
                        raise
                    warning(f"Post-save diagnostics failed: {exc}", category="character_updates")
                
                # AI Character Validation after successful update
                try:
                    pre_validation_xp = None
                    try:
                        print(f"DEBUG: [Character Validator] Starting validation for {character_name}...")
                        pre_validation_data = safe_read_json(character_path)
                        pre_validation_xp = pre_validation_data.get('experience_points', 0) if pre_validation_data else 0
                        print(f"DEBUG: [XP Tracking] {character_name} XP BEFORE validation: {pre_validation_xp}")
                        info(f"[Character Validator] Starting smart validation for {character_name}...", category="character_validation")
                    except Exception as exc:
                        if commit_guard is None or isinstance(exc, LiveProviderSuperseded):
                            raise
                        warning(f"Pre-validation diagnostics failed: {exc}", category="character_validation")
                    validator = AICharacterValidator(commit_guard=commit_guard)

                    # Load character data for smart validation
                    char_data = safe_read_json(character_path)
                    if char_data:
                        # Use smart validation that checks cache first
                        validation_result = (
                            validator.validate_and_correct_character_smart_with_result(
                                char_data, before=persisted_character_data
                            )
                        )
                        validated_data = validation_result.data

                        # Save the validated data back with better error handling
                        if validation_result.changed:
                            # Ensure write completes successfully
                            write_success = safe_write_json(character_path, validated_data, commit_guard=commit_guard)
                            if write_success:
                                if validation_result.success:
                                    debug("VALIDATION: Character auto-validated with corrections (using cache where possible)...", category="character_validation")
                                else:
                                    warning(
                                        f"VALIDATION: Provider validation failed for "
                                        f"{character_name}, but deterministic repairs "
                                        f"were saved: {validation_result.error}",
                                        category="character_validation",
                                    )
                                validation_success = validation_result.success
                            else:
                                error(f"VALIDATION: Failed to write validated data for {character_name}", category="character_validation")
                                validation_success = False
                        elif not validation_result.success:
                            warning(
                                f"VALIDATION: Character validation failed for "
                                f"{character_name}: {validation_result.error}",
                                category="character_validation",
                            )
                            validation_success = False
                        else:
                            debug("VALIDATION: Character validated - no corrections needed (cache hits used)", category="character_validation")
                            validation_success = True
                    else:
                        warning("VALIDATION: Could not load character data for validation", category="character_validation")
                        validation_success = False
                    
                    # DEBUG: Check XP after validation
                    post_validation_data = safe_read_json(character_path)
                    post_validation_xp = post_validation_data.get('experience_points', 0) if post_validation_data else 0
                    print(f"DEBUG: [XP Tracking] {character_name} XP AFTER validation: {post_validation_xp}")
                    if pre_validation_xp != post_validation_xp:
                        print(f"DEBUG: [XP Tracking] WARNING: XP changed during validation! {pre_validation_xp} -> {post_validation_xp}")
                        
                except Exception as e:
                    if commit_guard is not None and isinstance(e, LiveProviderSuperseded):
                        raise
                    warning(f"VALIDATION: Character validation error", category="character_validation")
                    # Don't fail the update if validation has issues
                
                # AI Character Effects Validation after AC validation
                try:
                    effects_validator = AICharacterEffectsValidator(commit_guard=commit_guard)
                    effects_validated_data, effects_success = effects_validator.validate_character_effects_safe(character_path)
                    
                    if effects_success and effects_validator.corrections_made:
                        debug("VALIDATION: Character effects auto-validated with corrections...", category="character_validation")
                    elif effects_success:
                        debug("VALIDATION: Character effects validated - no corrections needed", category="character_validation")
                    else:
                        warning("VALIDATION: Character effects validation failed, but update completed", category="character_validation")
                        
                except Exception as e:
                    if commit_guard is not None and isinstance(e, LiveProviderSuperseded):
                        raise
                    warning(f"VALIDATION: Character effects validation error", category="character_validation")
                    # Don't fail the update if validation has issues
                
                if commit_guard is not None:
                    with commit_guard():
                        pass
                return True
            else:
                error("FAILURE: Failed to save character data", category="file_operations")
                return False
                
        except json.JSONDecodeError as e:
            last_update_error = e
            if commit_guard is not None and primary_committed:
                with commit_guard():
                    pass
                return True
            error(f"FAILURE: JSON decode error (attempt {attempt})", exception=e, category="ai_processing")
            bounded_failure_count += 1
            debug(f"AI_CALL: Raw response: {raw_response}", category="ai_processing")
            # print(f"\n[DEBUG ERROR] JSON decode error for {character_name}")
            # print(f"Raw response that failed to parse: {raw_response}")
            # print(f"Error: {str(e)}\n")
            
            # Save the problematic response for debugging
            debug_error_file = f"debug/json_error_{character_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            os.makedirs("debug", exist_ok=True)
            with open(debug_error_file, 'w') as f:
                f.write(f"Character: {character_name}\n")
                f.write(f"Changes requested: {changes}\n")
                f.write(f"JSON Parse Error: {str(e)}\n\n")
                f.write(f"Raw AI Response:\n{raw_response}\n\n")
                f.write(f"Clean response attempt:\n{clean_response if 'clean_response' in locals() else 'Not extracted'}\n")
            debug(f"JSON parse error details saved to: {debug_error_file}", category="character_updates")
            
        except EngineRefusedChange:
            raise
        except Exception as e:
            if isinstance(e, LiveProviderCompletedError):
                # A deterministic provider refusal cannot heal by reissuing the
                # same request (#240); hand it to the caller with its envelope.
                error(
                    f"FAILURE: T079 provider refused {character_name} "
                    f"(deterministic, {e.http_status})",
                    category="character_updates",
                )
                raise
            if isinstance(e, LiveProviderSuperseded):
                raise
            last_update_error = e
            if commit_guard is not None and primary_committed:
                with commit_guard():
                    pass
                return True
            error(f"FAILURE: Error during update (attempt {attempt})", exception=e, category="character_updates")
            bounded_failure_count += 1
            
            # Update debug data with exception details
            if 'debug_data' in locals():
                debug_data["final_outcome"] = "exception"
                debug_data["exception_type"] = type(e).__name__
                debug_data["exception_message"] = str(e)
                # Add to consolidated debug log
                debug_log["updates"].append(debug_data)
                if len(debug_log["updates"]) > 100:
                    debug_log["updates"] = debug_log["updates"][-100:]
                safe_write_json(debug_log_file, debug_log)
                debug(f"Debug log updated: {debug_log_file}", category="character_updates")
            
            # Special handling for format string errors
            if "Invalid format specifier" in str(e) or "unsupported format string" in str(e):
                error_file = f"debug/format_error_{character_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                os.makedirs("debug", exist_ok=True)
                with open(error_file, 'w') as f:
                    f.write(f"Format String Error Debug\n")
                    f.write(f"========================\n\n")
                    f.write(f"Character: {character_name}\n")
                    f.write(f"Changes requested: {changes}\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(f"Error type: {type(e).__name__}\n\n")
                    if 'raw_response' in locals():
                        f.write(f"Raw AI Response:\n{raw_response}\n\n")
                    if 'updates' in locals():
                        f.write(f"Parsed updates:\n{json.dumps(updates, indent=2)}\n\n")
                debug(f"Format string error details saved to: {error_file}", category="character_updates")
            
            # print(f"\n[DEBUG ERROR] Exception during character update for {character_name}")
            # print(f"Error type: {type(e).__name__}")
            # print(f"Error message: {str(e)}")
            # print(f"Changes requested: {changes}")
            # if 'raw_response' in locals():
            #     print(f"AI response received: {raw_response[:500]}...")
            # print(f"Stack trace will be in logs\n")
        
        attempt += 1
        time.sleep(1)
    
    if last_engine_refusal:
        raise EngineRefusedChange(last_engine_refusal)

    # Log failure state
    if 'debug_data' in locals():
        debug_data["final_outcome"] = "failure"
        debug_data["failure_reason"] = str(last_update_error) if last_update_error is not None else "Max attempts reached"
        # Add to consolidated debug log
        debug_log["updates"].append(debug_data)
        if len(debug_log["updates"]) > 100:
            debug_log["updates"] = debug_log["updates"][-100:]
        safe_write_json(debug_log_file, debug_log)
        debug(f"Debug log updated: {debug_log_file}", category="character_updates")
    
    error(
        f"FAILURE: T079 answers stayed invalid for {character_name} "
        f"({bounded_failure_count} bounded failures)",
        category="character_updates",
    )
    error(f"FAILURE: Last validation error was: {error_msg if 'error_msg' in locals() else 'Unknown error'}", category="character_updates")
    return False

# Backward compatibility functions
def updatePlayerInfo(player_name, changes):
    """Backward compatibility wrapper for player updates"""
    return update_character_info(player_name, changes, character_role='player')

def updateNPCInfo(npc_name, changes):
    """Backward compatibility wrapper for NPC updates"""
    return update_character_info(npc_name, changes, character_role='npc')

# Utility functions for backup management
def list_character_backups(character_name, character_role=None):
    """
    List all available backups for a character
    
    Args:
        character_name (str): Name of the character
        character_role (str, optional): Character role, auto-detected if None
    
    Returns:
        list: List of backup file information
    """
    if character_role is None:
        character_role = detect_character_role(character_name)
    
    character_path = get_character_path(character_name, character_role)
    directory = os.path.dirname(character_path)
    base_name = os.path.basename(character_path)
    name_without_ext = os.path.splitext(base_name)[0]
    
    backups = []
    try:
        for file in os.listdir(directory):
            if file.startswith(f"{name_without_ext}.backup_") and file.endswith(".json"):
                backup_path = os.path.join(directory, file)
                mtime = os.path.getmtime(backup_path)
                backups.append({
                    'filename': file,
                    'path': backup_path,
                    'modified': datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    'size': os.path.getsize(backup_path)
                })
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x['modified'], reverse=True)
        
    except Exception as e:
        error(f"FAILURE: Error listing backups", exception=e, category="file_operations")
    
    return backups


def update_multiple_characters_parallel(
    character_updates_list: List[Tuple[str, str, Optional[str]]], 
    max_workers: int = 4
) -> Dict[str, bool]:
    """
    Update multiple characters in parallel using ThreadPoolExecutor.
    Reduces total processing time when updating multiple characters.
    
    Args:
        character_updates_list: List of tuples (character_name, changes, character_role)
                               character_role can be None for auto-detection
        max_workers: Maximum number of parallel threads (default 4)
    
    Returns:
        Dict mapping character names to update results (True/False)
    
    Example:
        updates = [
            ("Eirik Hearthwise", "Restore all spell slots after long rest", "player"),
            ("Ranger Thane", "Heal to full HP after long rest", "player"),
            ("Lyra Nyx", "Restore all spell slots after long rest", "player"),
            ("Thorin Ironforge", "Heal to full HP after long rest", "player")
        ]
        results = update_multiple_characters_parallel(updates)
        # All 4 characters updated simultaneously instead of sequentially
    """
    info(f"[PARALLEL UPDATE] Starting parallel update for {len(character_updates_list)} characters", 
         category="character_updates")
    start_time = time.time()
    
    results = {}
    errors = {}
    
    # Create a thread pool executor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all character updates to the thread pool
        future_to_char = {}
        for char_name, changes, role in character_updates_list:
            future = executor.submit(
                update_character_info,
                char_name,
                changes,
                character_role=role
            )
            future_to_char[future] = char_name
            debug(f"[PARALLEL UPDATE] Submitted task for {char_name}: {changes[:50]}...", 
                  category="character_updates")
        
        # Collect results as they complete
        for future in as_completed(future_to_char):
            char_name = future_to_char[future]
            try:
                result = future.result()
                results[char_name] = result
                info(f"[PARALLEL UPDATE] Completed {char_name}: {'Success' if result else 'Failed'}", 
                     category="character_updates")
            except Exception as e:
                error_msg = f"Error updating {char_name}: {str(e)}"
                error(f"[PARALLEL UPDATE] {error_msg}", category="character_updates")
                errors[char_name] = error_msg
                results[char_name] = False
    
    elapsed = time.time() - start_time
    info(f"[PARALLEL UPDATE] Completed all updates in {elapsed:.2f} seconds", 
         category="character_updates")
    
    # Report summary
    successful = sum(1 for r in results.values() if r)
    failed = len(results) - successful
    info(f"[PARALLEL UPDATE] Summary: {successful} successful, {failed} failed", 
         category="character_updates")
    
    if errors:
        warning(f"[PARALLEL UPDATE] Errors: {list(errors.keys())}", 
                category="character_updates")
    
    return results


def validate_multiple_characters_parallel(
    character_list: List[Dict[str, Any]] = None,
    character_names: List[str] = None,
    max_workers: int = 4
) -> Dict[str, Dict[str, Any]]:
    """
    Validate multiple characters in parallel using the optimized AICharacterValidator.
    Uses smart batching and caching to minimize API calls.
    
    Args:
        character_list: List of character data dictionaries (if already loaded)
        character_names: List of character names to load and validate
        max_workers: Maximum number of parallel validation workers
    
    Returns:
        Dict mapping character names to validation results
    
    Example:
        # After combat, validate all party members
        results = validate_multiple_characters_parallel(
            character_names=["Eirik Hearthwise", "Ranger Thane", "Lyra Nyx", "Thorin Ironforge"]
        )
        # Smart validator checks cache first, only calls API for changed data
    """
    # Load character data if names provided
    if character_names and not character_list:
        info(f"[PARALLEL VALIDATION] Loading {len(character_names)} characters", 
             category="character_validation")
        
        character_list = []
        party_tracker_data = safe_json_load("party_tracker.json")
        current_module = party_tracker_data.get("module", "").replace(" ", "_") if party_tracker_data else None
        path_manager = ModulePathManager(current_module)
        
        for char_name in character_names:
            char_path = get_character_path(char_name)
            if char_path and os.path.exists(char_path):
                char_data = safe_read_json(char_path)
                if char_data:
                    character_list.append(char_data)
                    debug(f"[PARALLEL VALIDATION] Loaded {char_name}", 
                          category="character_validation")
            else:
                warning(f"[PARALLEL VALIDATION] Could not find: {char_name}", 
                        category="character_validation")
    
    if not character_list:
        warning("[PARALLEL VALIDATION] No characters to validate", 
                category="character_validation")
        return {}
    
    info(f"[PARALLEL VALIDATION] Starting smart validation for {len(character_list)} characters", 
         category="character_validation")
    start_time = time.time()
    
    # Use the optimized smart batching validator with caching
    validator = AICharacterValidator()
    
    # Check what needs validation first (cache check)
    validation_needs = {}
    for char in character_list:
        char_name = char.get('name', 'Unknown')
        needs = validator.check_validation_needs(char)
        validation_needs[char_name] = needs
        
        # Log what will be validated
        validators_needed = [v for v, needed in needs.items() if needed]
        if validators_needed:
            info(f"[PARALLEL VALIDATION] {char_name} needs: {', '.join(validators_needed)}", 
                 category="character_validation")
        else:
            info(f"[PARALLEL VALIDATION] {char_name} fully cached - no API calls", 
                 category="character_validation")
    
    # Run smart batched validation (only calls API for non-cached data)
    results = validator.validate_multiple_characters_smart(character_list)
    
    elapsed = time.time() - start_time
    info(f"[PARALLEL VALIDATION] Completed in {elapsed:.2f} seconds", 
         category="character_validation")
    
    # Count actual API calls made
    api_calls_made = sum(
        sum(1 for v, needed in needs.items() if needed)
        for needs in validation_needs.values()
    )
    api_calls_without_cache = len(character_list) * 3  # AC, inventory, currency
    
    info(f"[PARALLEL VALIDATION] API calls: {api_calls_made}/{api_calls_without_cache} " +
         f"(saved {api_calls_without_cache - api_calls_made} calls via cache)", 
         category="character_validation")
    
    return results


def update_party_parallel(changes_dict: Dict[str, str], max_workers: int = 4) -> Dict[str, bool]:
    """
    Convenience function to update all party members in parallel.
    Common use cases: party rest, area effects, XP distribution.
    
    Args:
        changes_dict: Dict mapping character names to their changes
        max_workers: Maximum number of parallel threads
    
    Returns:
        Dict mapping character names to update results
    
    Example - Party Long Rest:
        changes = {
            "Eirik Hearthwise": "Long rest: Restore all HP and spell slots",
            "Ranger Thane": "Long rest: Restore all HP",
            "Lyra Nyx": "Long rest: Restore all HP and spell slots",
            "Thorin Ironforge": "Long rest: Restore all HP"
        }
        results = update_party_parallel(changes)
    
    Example - Combat XP Distribution:
        changes = {
            "Eirik Hearthwise": "Gain 250 XP from defeating goblins",
            "Ranger Thane": "Gain 250 XP from defeating goblins",
            "Lyra Nyx": "Gain 250 XP from defeating goblins",
            "Thorin Ironforge": "Gain 250 XP from defeating goblins"
        }
        results = update_party_parallel(changes)
    """
    # Convert dict to list of tuples for parallel processing
    updates_list = [(name, change, None) for name, change in changes_dict.items()]
    return update_multiple_characters_parallel(updates_list, max_workers)


def validate_party_parallel(max_workers: int = 4) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to validate all party members in parallel.
    Uses smart caching to minimize API calls - only validates changed data.
    
    Args:
        max_workers: Maximum number of parallel validation threads
    
    Returns:
        Dict mapping character names to validation results
    
    Example:
        # After combat ends, validate all party members
        results = validate_party_parallel()
        # Only makes API calls for data that changed during combat
    """
    # Get current party members from tracker
    party_tracker = safe_json_load("party_tracker.json")
    if not party_tracker or "partyMembers" not in party_tracker:
        warning("[PARALLEL VALIDATION] No party members found", 
                category="character_validation")
        return {}
    
    party_members = party_tracker["partyMembers"]
    info(f"[PARALLEL VALIDATION] Validating party: {', '.join(party_members)}", 
         category="character_validation")
    
    return validate_multiple_characters_parallel(
        character_names=party_members,
        max_workers=max_workers
    )


if __name__ == "__main__":
    # Test the unified system
    debug("INITIALIZATION: Testing unified character update system...", category="testing")
    
    # Test with a player character
    result = update_character_info("norn", "Add 100 experience points", character_role='player')
    debug(f"TEST: Player update result: {result}", category="testing")
    
    # Test with an NPC
    result = update_character_info("test_guard", "Increase level to 3", character_role='npc')
    debug(f"TEST: NPC update result: {result}", category="testing")
