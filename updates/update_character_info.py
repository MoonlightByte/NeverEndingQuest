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
# - Ammunition: Additive updates (+20 arrows, -10 bolts)
# - Currency: Always return final values after transactions
# 
# COMMON ISSUES & SOLUTIONS:
# =========================
# 1. "Invalid format specifier" - Check debug log for malformed AI response
# 2. Effects not clearing - Verify temporaryEffects is in complete_replacement_arrays
# 3. Currency not updating - Ensure all denominations (gold/silver/copper) returned
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
from datetime import datetime
from jsonschema import validate, ValidationError
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
# Import model configuration from config.py
from config import PLAYER_INFO_UPDATE_MODEL, NPC_INFO_UPDATE_MODEL
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_write_json, safe_read_json
from utils.encoding_utils import safe_json_load
from core.validation.character_validator import AICharacterValidator
from core.validation.character_effects_validator import AICharacterEffectsValidator
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.ai_client_factory import (
    create_chat_client,
    get_chat_model_name,
    handle_provider_error,
    get_fallback_notification
)
from utils.character_ops_routing import (
    normalize_character_ops_payload,
    classify_character_update_payload,
)
from core.managers.world_observer import get_world_observer

# Set script name for logging
set_script_name(__name__)

# Initialize client using factory (supports OpenAI and OpenRouter)
client = create_chat_client()

# Constants
TEMPERATURE = 0.7
VALIDATION_TEMPERATURE = 0.1  # Lower temperature for validation

# Standard 5e Weapon Database for auto-synchronization
WEAPON_DATABASE = {
    "club": {"dice": "1d4", "type": "bludgeoning", "category": "simple", "properties": ["light"]},
    "dagger": {"dice": "1d4", "type": "piercing", "category": "simple", "properties": ["finesse", "light", "thrown"]},
    "greatclub": {"dice": "1d8", "type": "bludgeoning", "category": "simple", "properties": ["two-handed"]},
    "handaxe": {"dice": "1d6", "type": "slashing", "category": "simple", "properties": ["light", "thrown"]},
    "javelin": {"dice": "1d6", "type": "piercing", "category": "simple", "properties": ["thrown"]},
    "light hammer": {"dice": "1d4", "type": "bludgeoning", "category": "simple", "properties": ["light", "thrown"]},
    "mace": {"dice": "1d6", "type": "bludgeoning", "category": "simple", "properties": []},
    "quarterstaff": {"dice": "1d6", "type": "bludgeoning", "category": "simple", "properties": ["versatile"]},
    "sickle": {"dice": "1d4", "type": "slashing", "category": "simple", "properties": ["light"]},
    "spear": {"dice": "1d6", "type": "piercing", "category": "simple", "properties": ["thrown", "versatile"]},
    "crossbow, light": {"dice": "1d8", "type": "piercing", "category": "simple", "properties": ["ammunition", "loading", "two-handed"]},
    "dart": {"dice": "1d4", "type": "piercing", "category": "simple", "properties": ["finesse", "thrown"]},
    "shortbow": {"dice": "1d6", "type": "piercing", "category": "simple", "properties": ["ammunition", "two-handed"]},
    "sling": {"dice": "1d4", "type": "bludgeoning", "category": "simple", "properties": ["ammunition"]},
    "battleaxe": {"dice": "1d8", "type": "slashing", "category": "martial", "properties": ["versatile"]},
    "flail": {"dice": "1d8", "type": "bludgeoning", "category": "martial", "properties": []},
    "glaive": {"dice": "1d10", "type": "slashing", "category": "martial", "properties": ["heavy", "reach", "two-handed"]},
    "greataxe": {"dice": "1d12", "type": "slashing", "category": "martial", "properties": ["heavy", "two-handed"]},
    "great axe": {"dice": "1d12", "type": "slashing", "category": "martial", "properties": ["heavy", "two-handed"]},
    "greatsword": {"dice": "2d6", "type": "slashing", "category": "martial", "properties": ["heavy", "two-handed"]},
    "halberd": {"dice": "1d10", "type": "slashing", "category": "martial", "properties": ["heavy", "reach", "two-handed"]},
    "lance": {"dice": "1d12", "type": "piercing", "category": "martial", "properties": ["reach", "special"]},
    "longsword": {"dice": "1d8", "type": "slashing", "category": "martial", "properties": ["versatile"]},
    "maul": {"dice": "2d6", "type": "bludgeoning", "category": "martial", "properties": ["heavy", "two-handed"]},
    "morningstar": {"dice": "1d8", "type": "piercing", "category": "martial", "properties": []},
    "pike": {"dice": "1d10", "type": "piercing", "category": "martial", "properties": ["heavy", "reach", "two-handed"]},
    "rapier": {"dice": "1d8", "type": "piercing", "category": "martial", "properties": ["finesse"]},
    "scimitar": {"dice": "1d6", "type": "slashing", "category": "martial", "properties": ["finesse", "light"]},
    "shortsword": {"dice": "1d6", "type": "piercing", "category": "martial", "properties": ["finesse", "light"]},
    "short sword": {"dice": "1d6", "type": "piercing", "category": "martial", "properties": ["finesse", "light"]},
    "trident": {"dice": "1d6", "type": "piercing", "category": "martial", "properties": ["thrown", "versatile"]},
    "war pick": {"dice": "1d8", "type": "piercing", "category": "martial", "properties": []},
    "warhammer": {"dice": "1d8", "type": "bludgeoning", "category": "martial", "properties": ["versatile"]},
    "whip": {"dice": "1d4", "type": "slashing", "category": "martial", "properties": ["finesse", "reach"]},
    "blowgun": {"dice": "1", "type": "piercing", "category": "martial", "properties": ["ammunition", "loading"]},
    "crossbow, hand": {"dice": "1d6", "type": "piercing", "category": "martial", "properties": ["ammunition", "light", "loading"]},
    "crossbow, heavy": {"dice": "1d10", "type": "piercing", "category": "martial", "properties": ["ammunition", "heavy", "loading", "two-handed"]},
    "longbow": {"dice": "1d8", "type": "piercing", "category": "martial", "properties": ["ammunition", "heavy", "two-handed"]},
    "net": {"dice": "-", "type": "bludgeoning", "category": "martial", "properties": ["special", "thrown"]}
}

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
- "armor" - armor pieces, shields, cloaks, boots, gloves, protective wear
- "ammunition" - arrows, bolts, sling bullets, thrown weapon ammo
- "consumable" - potions, scrolls, food, rations, anything consumed when used
- "equipment" - tools, torches, rope, containers, utility items
- "miscellaneous" - rings, amulets, wands, truly miscellaneous items only

NEVER use: "wondrous item", "magic item", "magical" or any other value!

NOTE: Enhanced categorization system fixes GitHub issue #45 (inconsistent item storage)

Enhanced Item Type Mappings:
- Arrows/Bolts/Bullets -> item_type: "ammunition"
- Travel Ration/Food -> item_type: "consumable", item_subtype: "food"
- Torch/Rope/Tools -> item_type: "equipment", item_subtype: "tool"
- Studded Leather Armor -> item_type: "armor", description: "Light armor. AC 12 + Dex modifier."
- Cloak of Elvenkind -> item_type: "armor", item_subtype: "cloak"
- Ring of Protection -> item_type: "miscellaneous", item_subtype: "ring"
- Wand of Magic Missiles -> item_type: "miscellaneous", item_subtype: "wand"
- Potion of Healing -> item_type: "consumable", item_subtype: "potion"
- Scroll of Fireball -> item_type: "consumable", item_subtype: "scroll"
"""
    
    if character_role == 'player':
        schema_info += """
Equipment Array Example:
[{"item_name": "Sword", "item_type": "weapon", "description": "Sharp blade", "quantity": 1}]

Currency Example: 
{"gold": 50, "silver": 10, "copper": 25}

Ammunition Example:
[{"name": "Arrows", "quantity": 20, "description": "Standard arrows"}]
"""
    else:
        schema_info += """
Equipment Array Example:
[{"item_name": "Chain Mail", "item_type": "armor", "description": "Heavy armor", "quantity": 1}]

AttacksAndSpellcasting vs Actions:
- Use attacksAndSpellcasting for standard attack format
- Actions array is for 5e standard format (optional)

Combat Damage Note:
When NPCs deal damage in combat, do NOT update their action arrays. Only update when the NPC gains new abilities or equipment.
"""
    
    return schema_info

def get_model_for_character(character_role):
    """Get the appropriate model based on character role"""
    # Use factory to get model name (supports OpenAI and OpenRouter)
    model = get_chat_model_name()
    if character_role == 'player':
        return model
    else:
        # For NPCs, use the mini model if available to save costs
        return NPC_INFO_UPDATE_MODEL if model.startswith('gpt-') else model

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

def deep_merge_dict(base_dict, update_dict):
    """Recursively merge update_dict into base_dict, preserving nested structures"""
    result = copy.deepcopy(base_dict)
    
    # Define arrays that need special merge handling (identified by name fields)
    named_arrays = {
        'ammunition': 'name',
        'attacksAndSpellcasting': 'name', 
        'classFeatures': 'name',
        'equipment': 'item_name',
        'equipment_effects': 'name',
        'feats': 'name',
        'racialTraits': 'name',
        'savingThrows': None, # special case
        'languages': None,
        'damageVulnerabilities': None,
        'damageResistances': None,
        'damageImmunities': None,
        'conditionImmunities': None
    }
    
    # Arrays that should be completely replaced, not merged
    complete_replacement_arrays = ['temporaryEffects']
    
    for key, value in update_dict.items():
        if key in complete_replacement_arrays:
            # Complete replacement for these arrays
            result[key] = copy.deepcopy(value)
        elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = deep_merge_dict(result[key], value)
        elif key in named_arrays and isinstance(result.get(key), list) and isinstance(value, list):
            # Special handling for arrays
            name_field = named_arrays[key]
            
            if name_field is None:
                # Simple list of strings - unique merge
                result[key] = list(set(result[key] + value))
            elif key == 'equipment':
                result[key] = merge_equipment_arrays(result[key], value)
            elif key == 'ammunition':
                result[key] = merge_ammunition_arrays(result[key], value)
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
    
    # Convert back to array and filter out zero/negative quantities
    result = []
    for ammo in ammo_lookup.values():
        if ammo.get('quantity', 0) > 0:
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
        # Robust check for dict type
        if not isinstance(item, dict):
            continue
            
        key = item.get(name_field, '').lower().strip()
        if key:
            lookup[key] = copy.deepcopy(item)
    
    # Process updates
    for update_item in update_array:
        # Handle cases where AI returns a string instead of an object in an array
        if isinstance(update_item, str):
            # Try to treat the string as the name
            update_name = update_item.strip()
            update_item = {name_field: update_name, "description": update_name}
        
        if not isinstance(update_item, dict):
            continue
            
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

def calculate_ability_modifier(score):
    """Calculate 5e ability modifier from score"""
    try:
        return (int(score) - 10) // 2
    except:
        return 0

def synchronize_weapons(character_data):
    """
    Ensure all equipped weapons in equipment have a corresponding entry in attacksAndSpellcasting.
    Uses WEAPON_DATABASE to fill in missing details.
    """
    if 'equipment' not in character_data or not isinstance(character_data['equipment'], list):
        return character_data
    
    if 'attacksAndSpellcasting' not in character_data:
        character_data['attacksAndSpellcasting'] = []
    
    # Get ability modifiers for bonus calculation
    abilities = character_data.get('abilities', {})
    str_mod = calculate_ability_modifier(abilities.get('strength', 10))
    dex_mod = calculate_ability_modifier(abilities.get('dexterity', 10))
    prof_bonus = character_data.get('proficiencyBonus', 2)
    
    equipped_weapons = [item for item in character_data['equipment'] 
                       if item.get('item_type') == 'weapon' and item.get('equipped', False)]
    
    existing_attacks = {attack.get('name', '').lower(): attack for attack in character_data['attacksAndSpellcasting']}
    
    for weapon in equipped_weapons:
        weapon_name = weapon.get('item_name', '')
        if not weapon_name:
            continue
            
        name_lower = weapon_name.lower()
        
        # Check if attack exists but is incomplete (missing required schema fields)
        attack_to_repair = None
        if name_lower in existing_attacks:
            attack_to_repair = existing_attacks[name_lower]
            required_fields = ["name", "attackBonus", "damageDice", "damageBonus", "damageType", "type", "description"]
            is_complete = all(field in attack_to_repair for field in required_fields)
            if is_complete:
                continue
            else:
                debug(f"SYNC: Repairing incomplete attack entry for: {weapon_name}", category="character_updates")
            
        # Try to find weapon stats in database
        # Fuzzy match: check if weapon_name contains any key in WEAPON_DATABASE
        db_stats = None
        for db_name, stats in WEAPON_DATABASE.items():
            if db_name in name_lower:
                db_stats = stats
                break
        
        # Default stats if not found
        if not db_stats:
            db_stats = {"dice": "1d4", "type": "bludgeoning", "category": "simple", "properties": []}
            
        # Determine attack type and modifiers
        is_ranged = "ranged" in weapon.get('weapon_type', '').lower() or "ammunition" in db_stats.get('properties', [])
        is_finesse = "finesse" in db_stats.get('properties', [])
        is_thrown = "thrown" in db_stats.get('properties', [])
        
        # Logic for bonuses
        if is_ranged and not is_thrown:
            # Pure ranged weapons use DEX
            mod = dex_mod
            atk_type = "ranged"
        elif is_finesse:
            # Finesse uses higher of STR or DEX
            mod = max(str_mod, dex_mod)
            atk_type = "melee" # Usually melee
        else:
            # Default to melee STR
            mod = str_mod
            atk_type = "melee"
            
        # Construct attack entry
        attack_entry = {
            "name": weapon_name,
            "attackBonus": mod + prof_bonus + weapon.get('attack_bonus', 0),
            "damageDice": weapon.get('damage', db_stats['dice']),
            "damageBonus": mod + weapon.get('attack_bonus', 0), # Simplified, usually damage bonus matches attack bonus without prof
            "damageType": db_stats['type'],
            "type": atk_type,
            "description": weapon.get('description', f"A standard {weapon_name}.")
        }
        
        # Final schema check: ensure all required fields present
        required_fields = ["name", "attackBonus", "damageDice", "damageBonus", "damageType", "type", "description"]
        for field in required_fields:
            if field not in attack_entry:
                # This shouldn't happen with the logic above but good as a safety
                if field == "damageBonus": attack_entry[field] = 0
                elif field == "attackBonus": attack_entry[field] = 0
                else: attack_entry[field] = "None"
        
        if attack_to_repair:
            # Update existing attack in place
            attack_to_repair.update(attack_entry)
        else:
            # Add new entry
            character_data['attacksAndSpellcasting'].append(attack_entry)
            debug(f"SYNC: Added missing attack entry for equipped weapon: {weapon_name}", category="character_updates")
        
    return character_data

def repair_character_data(character_data):
    """
    Repair common schema issues in character data before processing
    
    Args:
        character_data (dict): Character data to repair
    
    Returns:
        dict: Repaired character data
    """
    # Ensure background is a string (AI sometimes sends object or list)
    if 'background' in character_data:
        if isinstance(character_data['background'], list):
            character_data['background'] = ", ".join([str(x) for x in character_data['background']])
        elif isinstance(character_data['background'], dict):
            character_data['background'] = character_data['background'].get('name', str(character_data['background']))

    # Synchronize weapons with attacks
    character_data = synchronize_weapons(character_data)
    
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


SUPPORTED_CHARACTER_OPS = {
    "set_hp",
    "hp_delta",
    "spell_slot_delta",
    "inventory_add",
    "inventory_remove",
    "currency_delta",
    "condition_add",
    "condition_remove",
}

_last_ops_routing_marker = {
    "mode": "unknown",
    "reason": "unknown",
}

# TABLETOP MODE: Deterministic routing reason markers for ops pilot telemetry.
# Keep these as explicit string constants so tests can lock source contracts.
OPS_ROUTING_REASON_OPS_ABSENT = "ops_absent"
OPS_ROUTING_REASON_INVALID_WITH_CHANGES = "ops_invalid_with_changes_fallback"
OPS_ROUTING_REASON_UNSUPPORTED_WITH_CHANGES = "ops_unsupported_with_changes_fallback"


def _set_last_ops_routing_marker(mode: str, reason: str) -> None:
    global _last_ops_routing_marker
    _last_ops_routing_marker = {
        "mode": str(mode),
        "reason": str(reason),
    }


def get_last_ops_routing_marker() -> Dict[str, str]:
    """Return the last ops routing marker for diagnostics."""
    return dict(_last_ops_routing_marker)


def _normalize_spell_slot_level(level_value: Any) -> str:
    level_str = str(level_value).strip().lower()
    if level_str.startswith("level"):
        return level_str
    return f"level{level_str}"


def _resolve_op_type(op: Dict[str, Any]) -> str:
    op_type = op.get("op")
    if not isinstance(op_type, str) or not op_type.strip():
        op_type = op.get("type")
    if not isinstance(op_type, str):
        return ""
    return op_type.strip().lower()


def _find_equipment_entry(equipment: List[Dict[str, Any]], item_name: str) -> Optional[Dict[str, Any]]:
    target = item_name.strip().lower()
    for item in equipment:
        if not isinstance(item, dict):
            continue
        existing_name = str(item.get("item_name") or item.get("name") or "").strip().lower()
        if existing_name == target:
            return item
    return None


def _find_ammunition_entry(ammunition: List[Dict[str, Any]], item_name: str) -> Optional[Dict[str, Any]]:
    target = item_name.strip().lower()
    for item in ammunition:
        if not isinstance(item, dict):
            continue
        existing_name = str(item.get("name") or "").strip().lower()
        if existing_name == target:
            return item
    return None


def _to_int(value: Any, field_name: str, op_type: str) -> int:
    try:
        return int(value)
    except Exception:
        raise ValueError(f"Invalid integer for {op_type}.{field_name}: {value}")


def _apply_character_ops_deterministic(character_data: Dict[str, Any], ops: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any], str, List[str]]:
    """Apply supported structured ops directly to character data.

    Returns:
        (success, updated_data, error_message, unsupported_ops)
    """
    unsupported_ops: List[str] = []
    for op in ops:
        op_type = _resolve_op_type(op)
        if not op_type or op_type not in SUPPORTED_CHARACTER_OPS:
            unsupported_ops.append(op_type or "unknown")

    if unsupported_ops:
        return (False, character_data, "unsupported_ops", unsupported_ops)

    updated_data = copy.deepcopy(character_data)

    for op in ops:
        op_type = _resolve_op_type(op)

        if op_type == "set_hp":
            hp_value = _to_int(op.get("value", op.get("hp")), "value", op_type)
            max_hp = _to_int(updated_data.get("maxHitPoints", hp_value), "maxHitPoints", op_type)
            updated_data["hitPoints"] = max(0, min(hp_value, max_hp))

        elif op_type == "hp_delta":
            delta = _to_int(op.get("delta"), "delta", op_type)
            current_hp = _to_int(updated_data.get("hitPoints", 0), "hitPoints", op_type)
            max_hp = _to_int(updated_data.get("maxHitPoints", current_hp), "maxHitPoints", op_type)
            updated_data["hitPoints"] = max(0, min(current_hp + delta, max_hp))

        elif op_type == "spell_slot_delta":
            level_key = _normalize_spell_slot_level(op.get("level", ""))
            delta = _to_int(op.get("delta"), "delta", op_type)

            spellcasting = updated_data.get("spellcasting", {})
            if not isinstance(spellcasting, dict):
                spellcasting = {}
                updated_data["spellcasting"] = spellcasting

            spell_slots = spellcasting.get("spellSlots", {})
            if not isinstance(spell_slots, dict):
                return (False, character_data, "spellcasting.spellSlots missing or invalid", [])

            slot_data = spell_slots.get(level_key)
            if not isinstance(slot_data, dict):
                return (False, character_data, f"unknown spell slot level: {level_key}", [])

            current = _to_int(slot_data.get("current", 0), "current", op_type)
            maximum = _to_int(slot_data.get("max", 0), "max", op_type)
            new_value = current + delta
            if new_value < 0 or new_value > maximum:
                return (False, character_data, f"invalid spell slot delta for {level_key}: {current}+{delta} outside [0,{maximum}]", [])
            slot_data["current"] = new_value

        elif op_type in ["inventory_add", "inventory_remove"]:
            item_name = str(op.get("item_name") or op.get("name") or op.get("item") or "").strip()
            if not item_name:
                return (False, character_data, f"{op_type} missing item name", [])

            quantity = _to_int(op.get("quantity", 1), "quantity", op_type)
            if quantity <= 0:
                return (False, character_data, f"{op_type} quantity must be > 0", [])

            container = str(op.get("container", "equipment")).strip().lower()
            is_ammo = container == "ammunition" or str(op.get("item_type", "")).strip().lower() == "ammunition"

            if is_ammo:
                ammunition = updated_data.get("ammunition", [])
                if not isinstance(ammunition, list):
                    ammunition = []
                    updated_data["ammunition"] = ammunition

                entry = _find_ammunition_entry(ammunition, item_name)
                if entry is None and op_type == "inventory_remove":
                    return (False, character_data, f"cannot remove ammunition not present: {item_name}", [])

                if entry is None:
                    ammunition.append({"name": item_name, "quantity": quantity})
                else:
                    current_qty = _to_int(entry.get("quantity", 0), "quantity", op_type)
                    if op_type == "inventory_add":
                        entry["quantity"] = current_qty + quantity
                    else:
                        if quantity > current_qty:
                            return (False, character_data, f"cannot remove {quantity} {item_name}; only {current_qty} available", [])
                        entry["quantity"] = current_qty - quantity
            else:
                equipment = updated_data.get("equipment", [])
                if not isinstance(equipment, list):
                    equipment = []
                    updated_data["equipment"] = equipment

                entry = _find_equipment_entry(equipment, item_name)
                if entry is None and op_type == "inventory_remove":
                    return (False, character_data, f"cannot remove equipment not present: {item_name}", [])

                if entry is None:
                    equipment.append({
                        "item_name": item_name,
                        "item_type": str(op.get("item_type", "miscellaneous")),
                        "quantity": quantity,
                    })
                else:
                    current_qty = _to_int(entry.get("quantity", 0), "quantity", op_type)
                    if op_type == "inventory_add":
                        entry["quantity"] = current_qty + quantity
                    else:
                        if quantity > current_qty:
                            return (False, character_data, f"cannot remove {quantity} {item_name}; only {current_qty} available", [])
                        entry["quantity"] = current_qty - quantity

        elif op_type == "currency_delta":
            currency = updated_data.get("currency", {})
            if not isinstance(currency, dict):
                currency = {}
                updated_data["currency"] = currency

            deltas = op.get("deltas")
            if isinstance(deltas, dict):
                delta_map = deltas
            else:
                coin_type = str(op.get("currency") or op.get("coin") or "").strip().lower()
                delta_value = op.get("delta")
                if not coin_type:
                    return (False, character_data, "currency_delta missing currency key", [])
                delta_map = {coin_type: delta_value}

            for coin_type, delta_value in delta_map.items():
                coin = str(coin_type).strip().lower()
                if coin not in ["gold", "silver", "copper"]:
                    return (False, character_data, f"unsupported currency type: {coin}", [])
                delta = _to_int(delta_value, coin, op_type)
                current_value = _to_int(currency.get(coin, 0), coin, op_type)
                new_value = current_value + delta
                if new_value < 0:
                    return (False, character_data, f"currency underflow for {coin}: {current_value}+{delta}", [])
                currency[coin] = new_value

        elif op_type in ["condition_add", "condition_remove"]:
            condition_name = str(op.get("condition") or op.get("name") or "").strip()
            if not condition_name:
                return (False, character_data, f"{op_type} missing condition", [])

            conditions = updated_data.get("condition_affected", [])
            if not isinstance(conditions, list):
                conditions = []

            normalized = [str(c).strip().lower() for c in conditions]
            target = condition_name.lower()

            if op_type == "condition_add":
                if target not in normalized:
                    conditions.append(condition_name)
            else:
                conditions = [c for c in conditions if str(c).strip().lower() != target]

            updated_data["condition_affected"] = conditions
            updated_data["condition"] = conditions[0] if conditions else "none"

    return (True, updated_data, "", [])


def update_character_info(character_name, changes, character_role=None, ops=None):
    """
    Unified function to update character information for both players and NPCs
    
    Args:
        character_name (str): Name of the character to update
        changes (str): Description of changes to make
        character_role (str, optional): 'player' or 'npc', auto-detected if None
        ops (list, optional): Additive structured operations for deterministic mechanics updates
    
    Returns:
        bool: True if successful, False otherwise
    """

    global client  # Required because fallback reassigns client at line 2110

    debug(f"STATE_CHANGE: Updating character info for: {character_name}", category="character_updates")

    normalized_ops = normalize_character_ops_payload(ops)
    if isinstance(changes, dict):
        changes = json.dumps(changes)
    elif changes is None:
        changes = ""
    elif not isinstance(changes, str):
        changes = str(changes)
    changes_text = changes

    payload_route = classify_character_update_payload(changes_text, ops)
    _set_last_ops_routing_marker(payload_route["mode"], payload_route["reason"])

    if payload_route["mode"] == "prose_fallback":
        info(
            f"CHAR_OPS_FALLBACK reason={payload_route['reason']} character={character_name}",
            category="character_updates",
        )
    elif payload_route["mode"] == "hard_fail" and payload_route["reason"] == "ops_invalid_no_fallback":
        error(
            f"FAILURE: Invalid ops payload without prose fallback for {character_name} (reason=ops_invalid_no_fallback)",
            category="character_updates",
        )
        return False
    
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
        
        # Repair common schema issues before processing
        character_data = repair_character_data(character_data)
            
    except Exception as e:
        error(f"FAILURE: Error loading character data", exception=e, category="file_operations")
        return False
    
    # Create file backup before any changes
    backup_path = create_character_backup(character_path, "update")
    if backup_path is None:
        warning("FILE_OP: Could not create backup, but proceeding with update", category="file_operations")
    else:
        # Clean up old backups to prevent accumulation
        cleanup_old_backups(character_path)
    
    # Create in-memory backup
    original_data = copy.deepcopy(character_data)

    # TABLETOP MODE: Additive structured "ops" contract (Phase 3 pilot)
    # If supported ops are present, apply deterministically in Python.
    if normalized_ops is not None:
        if not normalized_ops:
            if not changes_text.strip():
                error(
                    f"FAILURE: Invalid or empty structured ops payload for {character_name} with no prose fallback",
                    category="character_updates",
                )
                return False
            warning(
                f"CHAR_OPS: Structured ops invalid/empty for {character_name}; falling back to legacy changes",
                category="character_updates",
            )
            _set_last_ops_routing_marker("prose_fallback", "ops_invalid_with_changes_fallback")
        else:
            ops_success, ops_updated_data, ops_error, unsupported_ops = _apply_character_ops_deterministic(
                character_data,
                normalized_ops,
            )

            if unsupported_ops:
                if not changes_text.strip():
                    error(
                        f"FAILURE: Unsupported ops with no prose fallback for {character_name}: {unsupported_ops}",
                        category="character_updates",
                    )
                    return False
                warning(
                    f"CHAR_OPS: Unsupported ops for {character_name} ({unsupported_ops}); using legacy prose fallback",
                    category="character_updates",
                )
                _set_last_ops_routing_marker("prose_fallback", "ops_unsupported_with_changes_fallback")
            elif not ops_success:
                _set_last_ops_routing_marker("hard_fail", "ops_deterministic_apply_failed")
                error(
                    f"FAILURE: Deterministic ops application failed for {character_name}: {ops_error}",
                    category="character_updates",
                )
                return False
            else:
                _set_last_ops_routing_marker("structured_applied", "ops_applied")
                updated_data = normalize_status_and_condition(ops_updated_data, character_role)
                updated_data, removed_fields = purge_invalid_fields(updated_data, schema, character_name)
                if removed_fields:
                    warning(
                        f"VALIDATION: Purged {len(removed_fields)} invalid fields after ops application: {', '.join(removed_fields)}",
                        category="character_validation",
                    )

                is_valid, error_msg = validate_character_data(updated_data, schema, character_name)
                if not is_valid:
                    error(
                        f"VALIDATION: Deterministic ops update failed schema validation for {character_name}: {error_msg}",
                        category="character_validation",
                    )
                    return False

                updated_data = repair_character_data(updated_data)
                save_result = safe_write_json(character_path, updated_data)
                if not save_result:
                    error(f"FAILURE: Could not persist deterministic ops update for {character_name}", category="file_operations")
                    return False

                try:
                    observer = get_world_observer()
                    observer.record_event(
                        track="MECHANICAL",
                        event_type="CHARACTER_UPDATE",
                        actor=character_name,
                        action="structured_ops_update",
                        metadata={"ops": normalized_ops},
                    )
                except Exception as e:
                    warning(f"WorldObserver hook failed for structured ops update: {e}", category="world_observer")

                info(
                    f"SUCCESS: Applied deterministic structured ops update for {character_name}",
                    category="character_updates",
                )
                return True

    # Load and process conversation history
    history = load_conversation_history()
    if character_role == 'player':
        history = process_conversation_history(history, character_role)
    
    # Format schema for prompt
    schema_info = format_schema_for_prompt(schema, character_role)
    
    # Build the prompt
    system_message = f"""You are an assistant that updates character information in a 5th Edition roleplaying game. Given the current character information and a description of changes, you must return only the updated sections as a JSON object. Do not include unchanged fields. Your response should be a valid JSON object representing only the modified parts of the character sheet.

**CRITICAL JSON OUTPUT RULES: DELTA-ONLY UPDATES**

Your primary goal is to generate the smallest possible valid JSON object that reflects ONLY the requested changes. Do not rewrite or include any data that was not explicitly modified by the user's request. This is crucial for system performance.

1. **Return ONLY Changed Fields:** Only include top-level keys (`hitPoints`, `equipment`, `currency`, etc.) if a value within them has changed. If the user only takes damage, your entire output should be a minimal JSON like: `{{ "hitPoints": 35 }}`.

2. **For Lists (like `equipment` or `ammunition`):**
   - **NEVER** return the entire list if only one item is changed.
   - To **MODIFY** an existing item: Return an array containing an object with the item's identifier (`item_name` for equipment, `name` for ammunition) and ONLY the fields that changed.
     - *Example:* `{{ "equipment": [{{ "item_name": "Shield", "quantity": 0 }}] }}`
   - To **ADD** a new item: Return an array containing an object with the full details of ONLY the new item.
     - *Example:* `{{ "equipment": [{{ "item_name": "Potion of Healing", "item_type": "consumable", "quantity": 1 }}] }}`
   - To **REMOVE** an item: Set its quantity to 0
     - *Example:* `{{ "equipment": [{{ "item_name": "Shield", "quantity": 0 }}] }}`

3. **For Nested Objects (like `currency` or `spellcasting.spellSlots`):**
   - Only return the specific key-value pairs that were modified.
   - *Example (Spending Gold):* `{{ "currency": {{ "gold": 125 }} }}` (Do NOT include silver and copper if they are unchanged).
   - *Example (Using a Spell Slot):* `{{ "spellcasting": {{ "spellSlots": {{ "level1": {{ "current": 3 }} }} }} }}` (Do NOT include other spell slot levels).

4. **For Complex Updates Affecting Multiple Systems:**
   - When an action affects multiple character aspects, you MUST include ALL affected fields in your minimal JSON response.
   - Equipment removal/damage affecting AC: Always include the updated `armorClass`.
   - Weapon changes: Always include updated `attacksAndSpellcasting` array entries for the affected weapons.
   - Shield/armor changes: Include `armorClass` and any affected `equipment_effects`.
   - Status changes: Always synchronize `status`, `condition`, and `condition_affected`.

   - **Example - Shield is destroyed:**
     ```json
     {{
       "equipment": [{{ "item_name": "Shield", "quantity": 0, "equipped": false }}],
       "armorClass": 15,
       "equipment_effects": [{{ "name": "Shield AC Bonus", "value": 0 }}]
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
   - When applying conditions (poisoned, frightened, paralyzed, etc.), update BOTH arrays:
     - Add the condition name to the `condition_affected` array (e.g., ["poisoned"])
     - Update the `condition` field with the condition name (e.g., "poisoned")
   - For multiple conditions, `condition` should contain the most severe, while `condition_affected` lists all
   - **Example - Applying poisoned condition:**
     ```json
     {{
       "condition": "poisoned",
       "condition_affected": ["poisoned"]
     }}
     ```

6. **Standard Ammunition Names (ALWAYS use these exact names):**
   - "Arrows" (plural) - for bow ammunition
   - "Crossbow bolts" (plural) - for crossbow ammunition
   - "Sling bullets" (plural) - for sling ammunition
   - "Darts" (plural) - for thrown darts
   - "Blowgun needles" (plural) - for blowgun ammunition
   - Always use plural form for consistency

**CRITICAL EDGE CASES:**
- When equipment that affects AC (shields, armor, rings of protection) is added, removed, equipped, or unequipped, you **MUST** calculate and return the new total `armorClass`.
- When a weapon is changed, you **MUST** update the relevant entry in the `attacksAndSpellcasting` array.
- When a temporary effect is added or removed, you **MUST** return the **complete** `temporaryEffects` array, containing only the effects that should remain active. This is the one exception to the delta-only rule for lists.
- Death/unconscious: Update `hitPoints`, `status`, `condition`, and `deathSaves` as needed
- Conditions: Always update BOTH `condition` and `condition_affected` when applying conditions

**Your adherence to these delta-only rules is paramount. Generate the most minimal, targeted JSON possible while ensuring ALL logically affected fields are included.**

**CRITICAL: The examples above are for learning purposes only. Do NOT include example JSON in your response. Only return the specific updates needed for the requested changes.**

**HEALING AND DAMAGE CALCULATIONS:**
- When a character "regains X hit points" or "is healed for X hit points": ADD X to their current hitPoints value (capped at maxHitPoints)
- When a character "takes X damage" or "loses X hit points": SUBTRACT X from their current hitPoints value (minimum 0)
- NEVER return the current HP value when healing is mentioned - always calculate the new value
- Example: If character has 22 HP and "regains 13 hit points", return {{"hitPoints": 35}} NOT {{"hitPoints": 22}}
- Example: If character has 31 HP out of 40 max and "regains 13 hit points", return {{"hitPoints": 40}} (capped at max)
- Always respect maxHitPoints as the upper limit for healing

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
8. If updating spell slots, always include ability, spellSaveDC, spellAttackBonus, and spells fields
9. SPELL SLOT RULE: Cantrips (0-level spells) do NOT consume spell slots. Only deduct spell slots for leveled spells (1st-9th level).
10. HIT DICE RULE: IGNORE all references to hit dice, Hit Dice, HD, or hit dice restoration. Do NOT add hitDice, hitDiceRestored, or maxHitDice fields. The system does not track hit dice.
11. REST HEALING: For long rests, simply restore hitPoints to maxHitPoints and restore spell slots. For short rests, restore some hitPoints based on the description. Do not implement hit dice mechanics.
12. CURRENCY MANAGEMENT - CRITICAL RULES:
    a) ALWAYS return the FINAL currency values after ANY transaction
    b) NEVER return just the change amount or partial currency objects
    c) Include ALL currency types (gold, silver, copper) even if unchanged
    
    TRANSACTION TYPES:
    - SPENDING/PAYING: Subtract from current amount
      Example: Has 367 gold, pays 100 gold -> Return {{"currency": {{"gold": 267, "silver": 61, "copper": 14}}}}
    - RECEIVING/FINDING: Add to current amount  
      Example: Has 267 gold, finds 50 gold -> Return {{"currency": {{"gold": 317, "silver": 61, "copper": 14}}}}
    - TRADING/EXCHANGING: Update all affected denominations
      Example: Trades 100 silver for 10 gold -> Calculate and return new totals
    
    CRITICAL: Look at the current currency values in the character data and calculate the FINAL amount after the transaction. Do NOT return the amount found/paid, return the TOTAL after adding/subtracting.
13. STATUS-CONDITION SYNCHRONIZATION: Always maintain consistency between status, condition, and hitPoints fields:
    - When status changes to "alive" and hitPoints > 0, automatically set condition to "none" and clear condition_affected array
    - When hitPoints > 0 and status is "alive", condition cannot be "unconscious"
    - When status is "unconscious", condition must be "unconscious" and condition_affected must include "unconscious"
    - When healing an unconscious character above 0 HP, clear unconscious from both condition and condition_affected fields
14. RESOURCE TRACKING RULES:
    - "spell slot" or "expends [level] spell slot" -> Update spellSlots only
    - "Channel Divinity" or "[ability name] (X uses)" -> Update classFeatures[].usage
    - "uses [ability]" without spell slot mention -> Find in classFeatures and track usage
    - If ability description mentions "expending a spell slot" -> ONLY update spellSlots
15. CLASS FEATURE USAGE TRACKING:
    When updating ability uses (not spell slots):
    a) Find the feature in classFeatures array by name
    b) If usage field exists, update it: {{"current": X, "max": Y, "refreshOn": "shortRest/longRest"}}
    c) If usage field doesn't exist, add it based on context:
       - "(0 uses until rest)" -> {{"current": 0, "max": 1, "refreshOn": "shortRest"}}
       - "(1/day)" -> {{"current": 0, "max": 1, "refreshOn": "longRest"}}
       - "(X uses remaining)" -> {{"current": X, "max": [infer from context]}}
    d) NEVER deduct spell slots for Channel Divinity or similar abilities
16. RESOURCE UPDATE EXAMPLES:
    Input: "Uses Channel Divinity ability Preserve Life (0 uses until rest)"
    Update: Find "Preserve Life" or "Channel Divinity" in classFeatures, set/add usage: {{"current": 0, "max": 1, "refreshOn": "shortRest"}}
    
    Input: "Expends one 1st-level spell slot"  
    Update: {{"spellcasting": {{"spellSlots": {{"level1": {{"current": [reduced by 1]}}}}}}}}
    
    Input: "Uses Divine Smite by expending a 2nd-level spell slot"
    Update: {{"spellcasting": {{"spellSlots": {{"level2": {{"current": [reduced by 1]}}}}}}}}
    Note: Do NOT update any Divine Smite usage counter - only the spell slot
17. AMMUNITION MANAGEMENT - CRITICAL:
    - When ADDING ammunition: Return the quantity to ADD as a positive number
      Example: "Added 20 arrows" -> {{"ammunition": [{{"name": "arrows", "quantity": 20}}]}}
    - When REMOVING/SELLING ammunition: Return the quantity to REMOVE as a NEGATIVE number
      Example: "Removed 100 crossbow bolts" -> {{"ammunition": [{{"name": "crossbow bolts", "quantity": -100}}]}}
      Example: "Sold 50 arrows" -> {{"ammunition": [{{"name": "arrows", "quantity": -50}}]}}
    - NEVER return the final quantity after removal - return the CHANGE amount
    - The system will automatically calculate the final quantity
18. LEVEL UP RESTRICTION - CRITICAL:
    - NEVER modify experience_points during level up operations
    - Level up should ONLY change: level, maxHitPoints, hitPoints, classFeatures, etc.
    - The experience_points field must NOT be included in level up changes
    - XP is managed separately and should never be altered during level advancement
    - IMPORTANT: This restriction ONLY applies to level up operations. You MUST update experience_points when explicitly requested (e.g., "Add 50 experience points", "Award XP")
19. TEMPORARY EFFECTS - CRITICAL RULES:
    - ONLY add effects with durations of 1 MINUTE OR LONGER to temporaryEffects
    - Do NOT add round-based effects (less than 1 minute) to temporaryEffects
    - Convert concentration spells to their maximum duration (e.g., "Bless for concentration" = "1 minute")
    - When an effect expires (e.g., "loses X as Y expires", "Y effect ends"), return the COMPLETE temporaryEffects array
    - The returned array must contain ALL effects that should remain active
    - DO NOT include the expired effect in the returned array
    - Example: Character has Shield of Faith and Bless. Shield of Faith expires.
      CORRECT: {{"temporaryEffects": [{{"name": "Bless", "description": "...", "source": "...", "duration": "..."}}]}}
      WRONG: Not returning temporaryEffects (would leave expired effect in place)
    - Round-based effects should be narrated but NOT tracked in temporaryEffects

EQUIPMENT UPDATE EXAMPLES:
CORRECT (updating one item): {{"equipment": [{{"item_name": "Jeweled dagger", "description": "updated description", "magical": true}}]}}
WRONG (would delete all other items): {{"equipment": [...]}} with multiple items

DANGEROUS EXAMPLE (DO NOT DO):
{{"spellcasting": {{"spellSlots": {{...}}}}}} // This deletes ability, DC, bonus, and spells!

SAFE EXAMPLE:
{{"spellcasting": {{"ability": "wisdom", "spellSaveDC": 13, "spellAttackBonus": 5, "spells": {{...}}, "spellSlots": {{...}}}}}} // This preserves all data

CONDITION MANAGEMENT EXAMPLES:
CORRECT (healing unconscious character): {{"hitPoints": 12, "status": "alive", "condition": "none", "condition_affected": []}}
WRONG (inconsistent state): {{"hitPoints": 12, "status": "alive", "condition": "unconscious"}} // Condition contradicts status!

RESOURCE TRACKING EXAMPLES:

Example 1 - Channel Divinity (NO spell slots):
Changes: "Uses Channel Divinity ability Preserve Life (0 uses until rest)"
Current classFeatures includes: {{"name": "Preserve Life (Channel Divinity Option)", "description": "As an action, restore HP..."}}
Update: {{"classFeatures": [{{"name": "Preserve Life (Channel Divinity Option)", "usage": {{"current": 0, "max": 1, "refreshOn": "shortRest"}}}}]}}

Example 2 - Regular Spell:
Changes: "Casts Cure Wounds, expending one 1st-level spell slot"
Current spellSlots: {{"level1": {{"current": 3, "max": 3}}}}
Update: {{"spellcasting": {{"spellSlots": {{"level1": {{"current": 2, "max": 3}}}}}}}}

Example 3 - Ability Using Spell Slots:
Changes: "Uses Divine Smite by expending a 2nd-level spell slot for extra damage"
Current spellSlots: {{"level2": {{"current": 2, "max": 2}}}}
Update: {{"spellcasting": {{"spellSlots": {{"level2": {{"current": 1, "max": 2}}}}}}}}
Note: Divine Smite is an ability that costs spell slots - update ONLY the spell slots, not any ability usage

AMMUNITION EXAMPLES:
Example 1 - Adding ammunition:
Changes: "Added 25 crossbow bolts to inventory"
Update: {{"ammunition": [{{"name": "crossbow bolts", "quantity": 25}}]}}

Example 2 - Removing/Selling ammunition:  
Changes: "Sold 100 crossbow bolts to Trader Sila"
Update: {{"ammunition": [{{"name": "crossbow bolts", "quantity": -100}}]}}

Example 3 - Multiple ammunition changes:
Changes: "Bought 30 arrows, sold 50 crossbow bolts"
Update: {{"ammunition": [{{"name": "arrows", "quantity": 30}}, {{"name": "crossbow bolts", "quantity": -50}}]}}

EXPERIENCE POINTS EXAMPLES:
Example 1 - Adding XP:
Changes: "Add 50 experience points" or "Awarded 50 experience points for successfully concluding a combat encounter"
Current experience_points: 2675
Update: {{"experience_points": 2725}}

Example 2 - Setting XP:
Changes: "Set experience points to 1000"
Update: {{"experience_points": 1000}}

Character Role: {character_role}
"""

    # Debug log the character's current currency and ammunition
    debug(f"CURRENCY_CHECK: {character_name} current currency: {character_data.get('currency', {})}", category="character_updates")
    debug(f"AMMUNITION_CHECK: {character_name} current ammunition: {character_data.get('ammunition', [])}", category="character_updates")
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Current character data:\n{json.dumps(character_data, indent=2)}"},
        {"role": "user", "content": f"Changes to make: {changes}"}
    ]
    
    # Add conversation history for context (last 10 messages)
    if history:
        recent_history = history[-10:]
        for msg in recent_history:
            if msg.get('role') in ['user', 'assistant']:
                messages.insert(-2, {"role": msg['role'], "content": msg['content']})
    
    max_attempts = 3
    attempt = 1
    
    # Get appropriate model for character type
    model = get_model_for_character(character_role)
    
    while attempt <= max_attempts:
        try:
            debug(f"STATE_CHANGE: Attempt {attempt} of {max_attempts}", category="character_updates")
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=TEMPERATURE
            )
            
            # Track usage
            if USAGE_TRACKING_AVAILABLE:
                try:
                    track_response(response)
                except:
                    pass
            
            raw_response = response.choices[0].message.content.strip()
            
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
                "model_used": model,
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
            
            # Clean and parse JSON response
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON object found in response")
            
            clean_response = json_match.group()
            updates = json.loads(clean_response)
            
            # Update debug data with parsed updates
            debug_data["parsed_updates"] = updates
            
            # Log the parsed JSON update - Commented out to prevent debug leak to player screen
            # print(f"[DEBUG PARSED JSON] {character_name}")
            # print(f"Updates to apply: {json.dumps(updates, indent=2)[:1000]}{'...' if len(json.dumps(updates)) > 1000 else ''}\n")
            
            # DEBUG: Check if XP update is in the updates
            if 'experience' in changes.lower() and 'experience_points' not in updates:
                print(f"DEBUG: [XP Warning] XP change requested but experience_points not in updates!")
                print(f"DEBUG: [XP Warning] AI returned: {updates}")
            
            # Fix common item_type mistakes before applying updates
            updates = fix_item_types(updates)
            
            # Fix common injury type mistakes before applying updates
            updates = fix_injury_types(updates)
            
            # CRITICAL FIX: Prevent AI from setting negative HP in updates
            if 'hitPoints' in updates and updates['hitPoints'] < 0:
                debug(f"HP_FIX: AI attempted to set negative HP ({updates['hitPoints']}) for {character_name}, clamping to 0", category="character_updates")
                updates['hitPoints'] = 0
            
            # Apply updates to character data using deep merge
            # print(f"[DEBUG] About to call deep_merge_dict for {character_name}")
            # print(f"[DEBUG] Character has ammunition: {'ammunition' in character_data}")
            # if 'ammunition' in character_data:
            #     print(f"[DEBUG] Current ammunition: {character_data['ammunition']}")
            # print(f"[DEBUG] Updates contain ammunition: {'ammunition' in updates}")
            # if 'ammunition' in updates:
            #     print(f"[DEBUG] Ammunition updates: {updates['ammunition']}")
            
            # CRITICAL FIX: Prevent XP loss during post-combat processing
            # This protects against stale character data overwriting recently awarded XP
            if 'experience_points' in updates:
                current_xp = character_data.get('experience_points', 0)
                new_xp = updates['experience_points']
                
                # If the update would reduce XP, check if this might be stale data
                if new_xp < current_xp:
                    print(f"DEBUG: [XP Protection] Preventing XP reduction: {current_xp} -> {new_xp} for {character_name}")
                    print(f"DEBUG: [XP Protection] This may be stale data from post-combat processing")
                    # Remove the XP update to preserve current XP
                    del updates['experience_points']
                    print(f"DEBUG: [XP Protection] XP update removed, preserving current XP: {current_xp}")
            
            # Currency reduction validation
            if 'currency' in updates:
                current_currency = character_data.get('currency', {})
                new_currency = updates.get('currency', {})
                needs_verification = False
                reduction_details = []
                
                for coin_type in ['gold', 'silver', 'copper']:
                    current_val = current_currency.get(coin_type, 0)
                    new_val = new_currency.get(coin_type, current_val)
                    
                    if new_val < current_val:
                        needs_verification = True
                        reduction_amount = current_val - new_val
                        reduction_details.append(f"{coin_type}: {current_val} -> {new_val} (-{reduction_amount})")
                
                if needs_verification:
                    print(f"DEBUG: [Currency Update] Currency reduction detected for {character_name}: {', '.join(reduction_details)}")
                    warning(f"CURRENCY REDUCTION: {character_name} - {', '.join(reduction_details)}", category="character_updates")
                    
                    # Create verification prompt
                    verification_prompt = f"""CURRENCY REDUCTION VERIFICATION REQUIRED:

Character: {character_name}
Detected reductions: {', '.join(reduction_details)}
Original request: {changes}

IMPORTANT: Currency should ONLY be reduced in these cases:
- Making a purchase or trade
- Giving money away intentionally
- Losing money (theft, gambling, penalties)
- Explicit command to remove currency

Currency should NOT be reduced when:
- Finding coins in containers/coffers
- Receiving rewards or payment
- Looting enemies or discovering treasure
- Opening chests with coins inside

Based on the context, is this currency reduction correct?
If this was FINDING coins, you should ADD to existing currency, not replace it.

Please provide the CORRECT currency values:
- Current gold: {current_currency.get('gold', 0)}, silver: {current_currency.get('silver', 0)}, copper: {current_currency.get('copper', 0)}
- If adding found coins, return the sum of current + found amounts"""
                    
                    # Currency validation: Allow the transaction but monitor it
                    info(f"CURRENCY TRANSACTION: Allowing currency change for {character_name}", category="character_updates")
                    info(f"CURRENCY TRANSACTION: Details - {', '.join(reduction_details)}", category="character_updates")
                    
                    # The improved prompting should prevent calculation errors
                    # We allow the transaction to proceed per the agentic approach
            
            # Debug HP changes BEFORE merge
            if 'hitPoints' in updates:
                debug(f"HP_DEBUG: {character_name} - Before merge HP: {character_data.get('hitPoints')}/{character_data.get('maxHitPoints')}, Update wants HP: {updates.get('hitPoints')}", category="character_updates")
            
            updated_data = deep_merge_dict(character_data, updates)
            
            # Debug HP changes AFTER merge
            if 'hitPoints' in updates:
                debug(f"HP_DEBUG: {character_name} - After merge HP: {updated_data.get('hitPoints')}/{updated_data.get('maxHitPoints')}", category="character_updates")
            
            # print(f"[DEBUG] deep_merge_dict completed successfully")
            
            # CRITICAL FIX: Ensure hitPoints never go below 0
            if 'hitPoints' in updated_data:
                current_hp = updated_data.get('hitPoints', 0)
                if current_hp < 0:
                    debug(f"HP_FIX: Clamping negative HP ({current_hp}) to 0 for {character_name}", category="character_updates")
                    updated_data['hitPoints'] = 0
            
            # print(f"[DEBUG] Checking ammunition after merge:")
            # if 'ammunition' in updated_data:
            #     print(f"[DEBUG] Updated ammunition: {updated_data['ammunition']}")
            
            # Validate that critical fields weren't accidentally deleted
            # print(f"[DEBUG] About to validate critical fields")
            critical_warnings = validate_critical_fields_preserved(character_data, updated_data, character_name)
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
                
                if attempt == max_attempts:
                    error("FAILURE: Max attempts reached. Update failed to preserve critical data.", category="character_validation")
                    return False
                attempt += 1
                continue
            
            # Role-specific normalization
            updated_data = normalize_status_and_condition(updated_data, character_role)
            
            # Purge invalid fields before validation
            # print(f"[DEBUG] About to purge invalid fields")
            updated_data, removed_fields = purge_invalid_fields(updated_data, schema, character_name)
            # print(f"[DEBUG] Field purging completed. Removed fields: {removed_fields}")
            if removed_fields:
                warning(f"VALIDATION: Purged {len(removed_fields)} invalid fields: {', '.join(removed_fields)}", category="character_validation")
            
            # Validate updated data
            # print(f"[DEBUG] About to validate character data against schema")
            is_valid, error_msg = validate_character_data(updated_data, schema, character_name)
            # print(f"[DEBUG] Schema validation completed. Valid: {is_valid}, Error: {error_msg}")
            
            # Update debug data with validation results
            debug_data["validation_results"] = {
                "schema_valid": is_valid,
                "error_message": error_msg if not is_valid else None,
                "removed_fields": removed_fields if removed_fields else []
            }
            
            if not is_valid:
                error(f"VALIDATION: Validation failed: {error_msg}", category="character_validation")
                if attempt == max_attempts:
                    error("FAILURE: Max attempts reached. Reverting changes.", category="character_updates")
                    return False
                
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
            
            # Final repair pass before saving to ensure schema compliance
            updated_data = repair_character_data(updated_data)
            
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
            
            save_result = safe_write_json(character_path, updated_data)
            print(f"DEBUG: [SAVE] safe_write_json returned: {save_result}")
            
            if save_result:
                # print(f"[DEBUG] Character data saved successfully!")
                info(f"SUCCESS: Successfully updated {character_name} ({character_role})!", category="character_updates")
                
                # EGO SYSTEM: Record Mechanical Truth
                try:
                    observer = get_world_observer()
                    observer.record_event(
                        track="MECHANICAL",
                        event_type="CHARACTER_UPDATE",
                        actor=character_name,
                        action="sheet_update",
                        metadata=updates  # Contains the verified changes (HP, Inventory, etc.)
                    )
                except Exception as e:
                    error(f"WorldObserver hook failed: {e}", category="world_observer")
                
                # CRITICAL FIX: Ensure players are added to partyMembers
                if character_role == 'player':
                    try:
                        party_tracker = safe_read_json("party_tracker.json")
                        if party_tracker:
                            party_members = party_tracker.get("partyMembers", [])
                            # Check normalized name or original name
                            if character_name not in party_members and updated_data.get('name') not in party_members:
                                print(f"DEBUG: [Auto-Register] Adding {character_name} to partyMembers list")
                                party_members.append(character_name)
                                party_tracker["partyMembers"] = party_members
                                
                                # Set as active if none active
                                if not party_tracker.get("active_character"):
                                    party_tracker["active_character"] = character_name
                                    
                                safe_write_json("party_tracker.json", party_tracker)
                                info(f"SUCCESS: Auto-registered {character_name} as party member", category="character_updates")
                    except Exception as e:
                        print(f"ERROR: Failed to auto-register player: {e}")

                # Debug HP after save
                if 'hitPoints' in updates:
                    saved_data = safe_read_json(character_path)
                    debug(f"HP_DEBUG: {character_name} - After save HP: {saved_data.get('hitPoints')}/{saved_data.get('maxHitPoints')}", category="character_updates")
                
                # Update debug data with success
                debug_data["final_outcome"] = "success"
                debug_data["validation_results"]["ai_validator_run"] = validation_success if 'validation_success' in locals() else None
                
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
                
                # AI Character Validation after successful update
                try:
                    print(f"DEBUG: [Character Validator] Starting validation for {character_name}...")
                    
                    # DEBUG: Check XP before validation
                    pre_validation_data = safe_read_json(character_path)
                    pre_validation_xp = pre_validation_data.get('experience_points', 0) if pre_validation_data else 0
                    print(f"DEBUG: [XP Tracking] {character_name} XP BEFORE validation: {pre_validation_xp}")
                    
                    info(f"[Character Validator] Starting smart validation for {character_name}...", category="character_validation")
                    validator = AICharacterValidator()

                    # Load character data for smart validation
                    char_data = safe_read_json(character_path)
                    if char_data:
                        # Use smart validation that checks cache first
                        validated_data = validator.validate_and_correct_character_smart(char_data)

                        # Save the validated data back with better error handling
                        if validated_data != char_data:
                            # Ensure write completes successfully
                            write_success = safe_write_json(character_path, validated_data)
                            if write_success:
                                debug("VALIDATION: Character auto-validated with corrections (using cache where possible)...", category="character_validation")
                                validation_success = True
                            else:
                                error(f"VALIDATION: Failed to write validated data for {character_name}", category="character_validation")
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
                    warning(f"VALIDATION: Character validation error", category="character_validation")
                    # Don't fail the update if validation has issues
                
                # AI Character Effects Validation after AC validation
                try:
                    effects_validator = AICharacterEffectsValidator()
                    effects_validated_data, effects_success = effects_validator.validate_character_effects_safe(character_path)
                    
                    if effects_success and effects_validator.corrections_made:
                        debug("VALIDATION: Character effects auto-validated with corrections...", category="character_validation")
                    elif effects_success:
                        debug("VALIDATION: Character effects validated - no corrections needed", category="character_validation")
                    else:
                        warning("VALIDATION: Character effects validation failed, but update completed", category="character_validation")
                        
                except Exception as e:
                    warning(f"VALIDATION: Character effects validation error", category="character_validation")
                    # Don't fail the update if validation has issues
                
                return True
            else:
                error("FAILURE: Failed to save character data", category="file_operations")
                return False
                
        except json.JSONDecodeError as e:
            error(f"FAILURE: JSON decode error (attempt {attempt})", exception=e, category="ai_processing")
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
            
        except Exception as e:
            error(f"FAILURE: Error during update (attempt {attempt})", exception=e, category="character_updates")
            
            # Check if this is a provider error that should trigger fallback
            error_result = handle_provider_error(e, f"character_update_{character_name}")
            if error_result['should_fallback'] and attempt < max_attempts:
                warning(f"Provider error detected, attempting fallback for attempt {attempt + 1}", category="character_updates")
                # Recreate client with fallback provider
                client = create_chat_client(use_fallback=True)
                attempt += 1
                continue
            
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
        
        if attempt < max_attempts:
            attempt += 1
            time.sleep(1)
        else:
            break
    
    # Log failure state
    if 'debug_data' in locals():
        debug_data["final_outcome"] = "failure"
        debug_data["failure_reason"] = str(e) if 'e' in locals() else "Max attempts reached"
        # Add to consolidated debug log
        debug_log["updates"].append(debug_data)
        if len(debug_log["updates"]) > 100:
            debug_log["updates"] = debug_log["updates"][-100:]
        safe_write_json(debug_log_file, debug_log)
        debug(f"Debug log updated: {debug_log_file}", category="character_updates")
    
    error(f"FAILURE: Failed to update character {character_name} after {max_attempts} attempts", category="character_updates")
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
