#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Character Creation & Module Selection Startup Wizard

Handles first-time setup when no player character or module is configured.
Provides AI-powered character creation and module selection in a single file.

Uses module-centric architecture for self-contained adventures.
Portions derived from SRD 5.2.1, licensed under CC BY 4.0.
"""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from jsonschema import validate, ValidationError
from core.generators.module_stitcher import ModuleStitcher

import config
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.file_operations import safe_write_json
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from core.managers.status_manager import (
    status_manager, status_processing_ai, status_validating,
    status_loading, status_ready, status_saving
)
from utils.ai_client_factory import create_chat_client, get_chat_model_name
from utils.character_creator import finalize_character_creation_candidate, persist_dm_created_character
from utils.spell_slot_utils import normalize_character_spell_slots
from utils.character_creation_prompt_builder import build_dm_creation_prompt_bundle
from utils.runtime_hydration import (
    hydrate_missing_live_area_files_from_bu,
    hydrate_missing_module_plot_files_from_bu,
)

# Set script name for logging
set_script_name("startup_wizard")

# Color constants for status display
GOLD = "\033[38;2;255;215;0m"  # Gold color for status messages
RESET_COLOR = "\033[0m"

# Status display configuration
current_status_line = None
web_mode = False

# Check if we're running in web mode by looking for the web output capture
try:
    import sys
    if hasattr(sys.stdout, '__class__') and 'WebOutputCapture' in str(sys.stdout.__class__):
        web_mode = True
except:
    pass


def _normalize_display_location_name(location_name):
    """Strip legacy room-number prefixes from user-facing location names."""
    if not isinstance(location_name, str):
        return ""
    return re.sub(r"^Room\s+\d+\s*:\s*", "", location_name.strip(), flags=re.IGNORECASE)

def display_status(message):
    """Display status message above the command prompt"""
    global current_status_line
    
    # In web mode, status is handled by the web interface
    if web_mode:
        return
        
    # Console mode - display status line
    # Clear previous status line if exists
    if current_status_line is not None:
        print(f"\r{' ' * len(current_status_line)}\r", end='', flush=True)
    # Display new status
    status_display = f"{GOLD}[{message}]{RESET_COLOR}"
    print(f"\r{status_display}", flush=True)
    current_status_line = status_display

def status_callback(message, is_processing):
    """Callback for status manager to display status updates"""
    # In web mode, the web interface handles status display
    if web_mode:
        # The status manager will already be using the web's callback
        return
        
    # Console mode
    if is_processing:
        display_status(message)
    else:
        # Clear status when ready
        global current_status_line
        if current_status_line is not None:
            print(f"\r{' ' * len(current_status_line)}\r", end='', flush=True)
            current_status_line = None

# Only register our callback in console mode
# In web mode, the web interface will have already set its own callback
if not web_mode:
    status_manager.set_callback(status_callback)

# Initialize AI client using factory (supports OpenAI and OpenRouter)
client = create_chat_client()

# Conversation file for character creation (separate from main game)
STARTUP_CONVERSATION_FILE = "modules/conversation_history/startup_conversation.json"

# Directories under modules/ that are runtime/system storage, not playable modules.
STARTUP_NON_MODULE_DIRS = {
    "backups",
    "campaign_archives",
    "campaign_summaries",
    "conversation_history",
    "encounters",
    "ingest",
    "logs",
}

# TABLETOP MODE: Persisted startup lifecycle key for interrupted onboarding recovery.
STARTUP_INCOMPLETE_STATE_KEY = "startup_incomplete"


def _is_module_candidate_directory(module_name: str, module_path: str) -> bool:
    """Return True when a modules/ directory is a playable module candidate."""
    if module_name.startswith("."):
        return False

    if module_name in STARTUP_NON_MODULE_DIRS:
        return False

    areas_path = os.path.join(module_path, "areas")
    return os.path.isdir(areas_path)


def _normalize_startup_prompt_input(raw_input):
    """Normalize startup wizard prompt input for console and web flows."""
    normalized = str(raw_input or "").strip()
    if normalized.startswith("[") and "]:" in normalized:
        normalized = normalized.split("]:", 1)[1].strip()
    return normalized.lower()

# ===== MAIN ORCHESTRATION =====

def initialize_game_files_from_bu():
    """Initialize missing live files from BU templates.

    Area hydration is handled first via deterministic helper logic.
    Non-area BU hydration is retained for backward compatibility.
    """
    initialized_count = 0

    area_result = hydrate_missing_live_area_files_from_bu("modules")
    initialized_count += int(area_result.get("restored", 0))
    initialized_count += int(area_result.get("repaired_existing", 0))

    plot_result = hydrate_missing_module_plot_files_from_bu("modules")
    initialized_count += int(plot_result.get("restored", 0))
    initialized_count += int(plot_result.get("repaired_existing", 0))

    # Preserve legacy non-area BU hydration behavior.
    bu_files = sorted(Path("modules").rglob("*_BU.json"), key=lambda path: str(path).lower())
    for bu_file in bu_files:
        if "saved_games" in str(bu_file):
            continue
        if "areas" in bu_file.parts:
            continue

        live_file = str(bu_file).replace("_BU.json", ".json")
        if not os.path.exists(live_file):
            try:
                shutil.copy2(bu_file, live_file)
                initialized_count += 1
            except Exception as e:
                warning(f"Failed to initialize {live_file}: {e}", category="startup")

    return initialized_count

def run_startup_sequence():
    """Main entry point for startup wizard"""
    print("\nDungeon Master: Welcome to your 5th Edition Adventure!")
    print("Dungeon Master: Let's set up your character and choose your adventure...\n")
    
    # Initialize game files from BU templates first
    initialize_game_files_from_bu()
    
    try:
        # Initialize startup conversation
        conversation = initialize_startup_conversation()
        
        # Step 1: Select module
        selected_module = select_module(conversation)
        if not selected_module:
            print("Setup cancelled. Exiting...")
            return False
        
        print(f"\nDungeon Master: Great choice! You've selected: {selected_module['display_name']}")
        
        # Step 2: Character selection/creation
        character_name = select_or_create_character(conversation, selected_module)
        if not character_name:
            print("Character setup cancelled. Exiting...")
            return False

        created_characters = [character_name]

        # TABLETOP MODE: Persist startup party state immediately after first PC creation.
        # This enables web UI tab/sheet hydration while add-more prompt loop is still active.
        # Keep startup marked incomplete until facilitator explicitly finishes add-more loop.
        update_party_tracker(selected_module['name'], created_characters, startup_incomplete=True)

        # TABLETOP MODE: Optional multi-PC startup loop.
        # Exit contract: loop terminates ONLY on explicit 'n'/'no' from either decision point.
        # Blank/invalid inputs reprompt indefinitely; no implicit exit paths exist.
        while True:
            # Emit prompt line first for web visibility, then collect input
            print("Dungeon Master: Add another player character? (y/n):")
            add_more = _normalize_startup_prompt_input(input())
            
            # Strict yes/no parser: reprompt on blank or invalid input
            if add_more in ["y", "yes"]:
                # Continue to create next character
                pass
            elif add_more in ["n", "no"]:
                # EXPLICIT EXIT 1: Facilitator declined additional players
                break
            else:
                # Blank or invalid input: show guidance and reprompt
                print("Dungeon Master: Please enter 'y' for yes or 'n' for no.")
                continue

            next_character = create_new_character(conversation, selected_module)
            if next_character:
                created_characters.append(next_character)
                # TABLETOP MODE: Persist each successful queued PC immediately so
                # frontend party data reflects additions without waiting for explicit loop exit.
                # Keep startup incomplete until explicit loop completion finalizes state.
                update_party_tracker(selected_module['name'], created_characters, startup_incomplete=True)
                print(f"Dungeon Master: Added player {next_character} to startup party.")
                continue

            print("Dungeon Master: Additional player creation failed.")
            # TABLETOP MODE: Secondary retry decision with explicit-exit contract
            print("Dungeon Master: Retry creating another player? (y/n):")
            retry_secondary = _normalize_startup_prompt_input(input())
            
            if retry_secondary in ["y", "yes"]:
                # Retry character creation
                continue
            elif retry_secondary in ["n", "no"]:
                # EXPLICIT EXIT 2: Facilitator declined retry; end add-more loop
                break
            else:
                # Blank or invalid: show guidance and reprompt for this decision
                print("Dungeon Master: Please enter 'y' for yes or 'n' for no.")
                continue
        
        # Step 3: Finalize party tracker and clear startup-incomplete state.
        finalization_success = update_party_tracker(
            selected_module['name'],
            created_characters,
            startup_incomplete=False
        )
        if not finalization_success:
            print("Error: Failed to finalize startup party tracker state.")
            return False
        
        # Cleanup
        cleanup_startup_conversation()
        
        print(f"\nDungeon Master: Setup complete! Party members: {', '.join(created_characters)}")
        print(f"Dungeon Master: Your adventure in {selected_module['display_name']} is about to begin...\n")
        
        return True
        
    except Exception as e:
        print(f"Error: Error during setup: {e}")
        cleanup_startup_conversation()
        return False

def startup_required(party_file="party_tracker.json"):
    """Check if player character or module is missing"""
    try:
        party_data = safe_json_load(party_file)
        if not party_data:
            return True

        # TABLETOP MODE: Interrupted startup lifecycle recovery.
        # If startup was persisted as incomplete, force startup wizard resume
        # even when module and one or more party members already exist.
        if party_data.get(STARTUP_INCOMPLETE_STATE_KEY) is True:
            return True
        
        # Check if module is missing or empty
        module = party_data.get("module", "").strip()
        if not module:
            return True
        
        # Check if partyMembers is missing or empty
        party_members = party_data.get("partyMembers", [])
        if not party_members:
            return True
        
        # Check if the player character file actually exists
        if party_members:
            player_name = party_members[0]
            path_manager = ModulePathManager(module)
            char_path = path_manager.get_character_unified_path(player_name)
            if not os.path.exists(char_path):
                return True
        
        return False
        
    except Exception:
        return True  # If anything fails, assume setup needed

# ===== MODULE MANAGEMENT =====

def scan_available_modules():
    """Find all available modules in modules/ directory"""
    status_loading()
    modules = []
    
    if not os.path.exists("modules"):
        print("Error: No modules directory found!")
        status_ready()
        return modules
    
    for item in os.listdir("modules"):
        module_path = f"modules/{item}"
        if os.path.isdir(module_path):
            if not _is_module_candidate_directory(item, module_path):
                continue
            
            # Use module_stitcher detection method (current architecture)
            module_data = None
            try:
                stitcher = ModuleStitcher()
                detected_data = stitcher.analyze_module(item)
                
                if detected_data and detected_data.get('areas'):
                    # Calculate actual level range from area data
                    levels = []
                    for area_data in detected_data['areas'].values():
                        if 'recommendedLevel' in area_data:
                            levels.append(area_data['recommendedLevel'])
                    
                    level_range = {'min': 1, 'max': 1}
                    if levels:
                        level_range = {'min': min(levels), 'max': max(levels)}
                    
                    module_data = {
                        'moduleName': item.replace('_', ' ').title(),
                        'moduleDescription': f"Adventure module with {len(detected_data['areas'])} areas",
                        'moduleMetadata': {
                            'levelRange': level_range,
                            'estimatedPlayTime': 'Unknown'
                        }
                    }
            except Exception as e:
                print(f"Warning: Could not analyze module {item}: {e}")
                continue
            
            # Add module if we have valid data
            if module_data:
                modules.append({
                    'name': item,
                    'display_name': module_data.get('moduleName', item),
                    'description': module_data.get('moduleDescription', 'No description available'),
                    'level_range': module_data.get('moduleMetadata', {}).get('levelRange', {'min': 1, 'max': 3}),
                    'play_time': module_data.get('moduleMetadata', {}).get('estimatedPlayTime', 'Unknown'),
                    'path': module_path
                })
    
    # Sort modules by minimum level (lowest first)
    modules.sort(key=lambda m: m['level_range'].get('min', 99))
    
    status_ready()
    return modules

def present_module_options(conversation, modules):
    """Show available modules to player using AI"""
    if not modules:
        print("Error: No valid modules found!")
        return None
    
    # Build module list for AI
    module_list = []
    for i, module in enumerate(modules, 1):
        level_range = module['level_range']
        module_list.append(
            f"{i}. **{module['display_name']}** (Levels {level_range.get('min', 1)}-{level_range.get('max', 3)})\n"
            f"   {module['description']}\n"
            f"   Estimated play time: {module['play_time']}"
        )
    
    modules_text = "\n\n".join(module_list)
    
    # AI prompt for module selection
    ai_prompt = f"""You are the Dungeon Master for NeverEndingQuest, a text-based adventure game based on the world's most popular 5th edition roleplaying game. Welcome the player and present the available modules.

Start with: "Welcome to NeverEndingQuest! This adventure game uses the SRD 5.2.1 rules (based on the world's most popular 5th edition roleplaying game) to bring you an immersive text-based fantasy experience."

Then mention these key features:
• AI-powered storytelling that adapts to your choices
• Turn-based tactical combat with dice rolling
• Character progression from level 1 to 20
• Inventory management and magical items
• Multiple adventure modules with interconnected stories
• Save/load system to continue your adventures

Available Modules:
{modules_text}

Note that new players should start with the lowest level module (usually 1-2) to experience the full story and character progression.

Ask the player which module they'd like to play, and explain that they can just tell you the number (1, 2, etc.) or the name of the module they prefer."""
    
    conversation.append({"role": "system", "content": ai_prompt})
    
    # Get AI response
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    return modules

def select_module(conversation):
    """Handle module selection with player input"""
    modules = scan_available_modules()
    
    if not modules:
        print("Error: No modules available. Please add modules to the modules/ directory.")
        return None
    
    if len(modules) == 1:
        print(f"Dungeon Master: Only one module available: {modules[0]['display_name']}")
        print(f"Dungeon Master: {modules[0]['description']}")
        return modules[0]
    
    # For fresh installations, auto-select lowest level module
    lowest_level_module = find_lowest_level_module()
    if lowest_level_module:
        module_name = lowest_level_module.get('moduleName')
        # Find matching module in scanned modules
        for module in modules:
            if module['name'] == module_name:
                print(f"Dungeon Master: Auto-selected starting module: {module['display_name']}")
                print(f"Dungeon Master: {module['description']}")
                print(f"Dungeon Master: Level Range: {lowest_level_module.get('levelRange', {})}")
                return module
    
    # Present options to player
    presented_modules = present_module_options(conversation, modules)
    if not presented_modules:
        return None
    
    # Get player choice
    while True:
        try:
            user_input = input("\nYour choice: ").strip()
            
            # Skip empty inputs
            if not user_input:
                continue
                
            conversation.append({"role": "user", "content": user_input})
            
            # Try to parse as number
            try:
                choice_num = int(user_input)
                if 1 <= choice_num <= len(modules):
                    return modules[choice_num - 1]
                else:
                    print(f"Dungeon Master: Please choose a number between 1 and {len(modules)}")
                    continue
            except ValueError:
                pass
            
            # Try to match by name
            user_lower = user_input.lower()
            for module in modules:
                if (user_lower in module['display_name'].lower() or 
                    user_lower in module['name'].lower()):
                    return module
            
            print("Dungeon Master: I didn't understand that. Please enter the number (1, 2, etc.) or name of the module.")
            
        except KeyboardInterrupt:
            return None

# ===== CHARACTER MANAGEMENT =====

def scan_existing_characters(module_name):
    """Find existing player characters in module"""
    characters = []
    path_manager = ModulePathManager(module_name)
    char_dir = os.path.join(path_manager.module_dir, "characters")
    
    if not os.path.exists(char_dir):
        return characters
    
    for filename in os.listdir(char_dir):
        if filename.endswith('.json') and not filename.endswith('.bak'):
            char_path = f"{char_dir}/{filename}"
            try:
                char_data = safe_json_load(char_path)
                if char_data and char_data.get('character_role') == 'player':
                    characters.append({
                        'name': char_data.get('name', filename[:-5]),
                        'level': char_data.get('level', 1),
                        'race': char_data.get('race', 'Unknown'),
                        'class': char_data.get('class', 'Unknown'),
                        'filename': filename[:-5],  # Remove .json
                        'path': char_path
                    })
            except Exception as e:
                print(f"Warning: Warning: Could not load character {filename}: {e}")
    
    return characters

def present_character_options(conversation, characters, module_name):
    """Show existing characters and option to create new one"""
    if not characters:
        # No existing characters
        ai_prompt = f"""The player has chosen a module but there are no existing player characters. Let them know they'll need to create a new character for this adventure. Be encouraging and exciting about the character creation process!"""
        
        conversation.append({"role": "system", "content": ai_prompt})
        response = get_ai_response(conversation)
        print(f"Dungeon Master: {response}")
        return "create_new"
    
    # Build character list
    char_list = []
    for i, char in enumerate(characters, 1):
        char_list.append(
            f"{i}. **{char['name']}** - Level {char['level']} {char['race']} {char['class']}"
        )
    
    chars_text = "\n".join(char_list)
    
    ai_prompt = f"""The player has chosen a module and there are some existing player characters available. Present the options and let them choose to either:
1. Play as one of the existing characters
2. Create a brand new character

Existing Characters:
{chars_text}

You can also mention option: "new" or "create" to make a new character.

Be helpful and explain that they can type the character number, character name, or "new" to create a fresh character."""
    
    conversation.append({"role": "system", "content": ai_prompt})
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    return characters

def select_or_create_character(conversation, module):
    """Choose existing character or create new one"""
    module_name = module['name']
    characters = scan_existing_characters(module_name)
    
    # Present options
    result = present_character_options(conversation, characters, module_name)
    
    if result == "create_new":
        # No existing characters, must create new
        return create_new_character(conversation, module)
    
    # Get player choice
    while True:
        try:
            user_input = input("\nYour choice: ").strip()
            
            # Skip empty inputs
            if not user_input:
                continue
                
            conversation.append({"role": "user", "content": user_input})
            
            # Check for new character creation
            if user_input.lower() in ['new', 'create', 'create new', 'make new']:
                return create_new_character(conversation, module)
            
            # Try to parse as number
            try:
                choice_num = int(user_input)
                if 1 <= choice_num <= len(characters):
                    selected_char = characters[choice_num - 1]
                    print(f"Dungeon Master: Excellent! You've selected {selected_char['name']}!")
                    return selected_char['filename']
                else:
                    print(f"Dungeon Master: Please choose a number between 1 and {len(characters)}, or 'new' to create a character")
                    continue
            except ValueError:
                pass
            
            # Try to match by character name
            user_lower = user_input.lower()
            for char in characters:
                if user_lower in char['name'].lower():
                    print(f"Dungeon Master: Excellent! You've selected {char['name']}!")
                    return char['filename']
            
            print("Dungeon Master: I didn't understand that. Please enter the character number, character name, or 'new' to create a new character.")
            
        except KeyboardInterrupt:
            return None

# ===== CHARACTER CREATION =====

def create_new_character(conversation, module):
    """Main character creation flow using AI interview with error recovery"""
    print("\nDungeon Master: Let's create your character!")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        # AI-powered character creation interview
        character_data = ai_character_interview(conversation, module, retry_count)
        
        if not character_data:
            retry_count += 1
            if retry_count < max_retries:
                print(f"Character creation failed. Retrying... (Attempt {retry_count + 1}/{max_retries})")
                continue
            else:
                print("Error: Character creation failed after multiple attempts.")
                return None
        
        # Character data is already normalized by shared finalization service
        # inside ai_character_interview(). Keep local schema recovery checks.

        # Validate character data with detailed error reporting
        valid, error = validate_character_with_recovery(character_data)
        if valid:
            character_name = character_data['name']
            persist_result = persist_dm_created_character(character_data)

            if persist_result.get("success"):
                print(f"Dungeon Master: Character {character_name} created successfully!")
                filename = str(persist_result.get("filename", ""))
                character_slug = os.path.splitext(filename)[0] if filename.endswith(".json") else filename
                if character_slug:
                    return character_slug
                from updates.update_character_info import normalize_character_name
                return normalize_character_name(character_name)
            else:
                persist_error = str(persist_result.get("error", "unknown persistence error"))
                print(f"Error: Failed to save character {character_name}: {persist_error}")
                return None
        else:
            retry_count += 1
            if retry_count < max_retries:
                print(f"Character validation failed: {error}")
                print(f"Attempting to fix and retry... (Attempt {retry_count + 1}/{max_retries})")
                # Add validation error to conversation for AI to learn from
                conversation.append({
                    "role": "system", 
                    "content": f"Previous character creation failed validation: {error}. Please create a valid character that follows the schema requirements."
                })
                continue
            else:
                print(f"Error: Character validation failed after {max_retries} attempts: {error}")
                print("Dungeon Master: Let me try creating a simple backup character for you...")
                # Try fallback character creation
                fallback_character = create_fallback_character(module)
                if fallback_character:
                    character_name = fallback_character['name']
                    success = save_character_to_module(fallback_character, module['name'])
                    if success:
                        print(f"Dungeon Master: I've created a basic {fallback_character['class']} character named {character_name} for you!")
                        print("You can always create a new character later when the system is working better.")
                        from updates.update_character_info import normalize_character_name
                        return normalize_character_name(character_name)
                
                print("Error: All character creation methods failed. Please try again later.")
                return None
    
    return None

def create_fallback_character(module):
    """Create a simple default character when AI creation fails"""
    try:
        fallback_char = {
            "character_role": "player",
            "character_type": "player",
            "name": "Adventurer",
            "type": "player",
            "size": "Medium",
            "level": 1,
            "race": "Human",
            "class": "Fighter",
            "alignment": "neutral good",
            "background": "Folk Hero",
            "status": "alive",
            "condition": "none",
            "condition_affected": [],
            "hitPoints": 12,
            "maxHitPoints": 12,
            "armorClass": 16,
            "initiative": 1,
            "speed": 30,
            "abilities": {
                "strength": 15,
                "dexterity": 13,
                "constitution": 14,
                "intelligence": 12,
                "wisdom": 13,
                "charisma": 11
            },
            "savingThrows": ["Strength", "Constitution"],
            "skills": ["Animal Handling", "Survival", "Athletics", "Intimidation"],
            "proficiencyBonus": 2,
            "senses": {
                "darkvision": 0,
                "passivePerception": 13
            },
            "languages": ["Common"],
            "proficiencies": {
                "armor": ["Light", "Medium", "Heavy", "Shields"],
                "weapons": ["Simple", "Martial"],
                "tools": []
            },
            "damageVulnerabilities": [],
            "damageResistances": [],
            "damageImmunities": [],
            "conditionImmunities": [],
            "classFeatures": [
                {
                    "name": "Fighting Style",
                    "description": "Defense: +1 to AC while wearing armor",
                    "source": "Fighter",
                    "usage": {"current": 0, "max": 0, "refreshOn": "longRest"}
                },
                {
                    "name": "Second Wind",
                    "description": "Regain 1d10 + fighter level hit points as a bonus action",
                    "source": "Fighter", 
                    "usage": {"current": 1, "max": 1, "refreshOn": "shortRest"}
                }
            ],
            "racialTraits": [
                {
                    "name": "Extra Language",
                    "description": "You can speak, read, and write one extra language",
                    "source": "Human"
                }
            ],
            "backgroundFeature": {
                "name": "Rustic Hospitality",
                "description": "Since you come from the ranks of the common folk, you fit in among them with ease",
                "source": "Folk Hero"
            },
            "temporaryEffects": [],
            "injuries": [],
            "equipment_effects": [],
            "feats": [],
            "equipment": [
                {
                    "item_name": "Chain Mail",
                    "item_type": "armor",
                    "item_subtype": "other",
                    "description": "Heavy armor, base AC 16",
                    "quantity": 1,
                    "equipped": True,
                    "magical": False,
                    "consumable": False,
                    "ac_base": 16,
                    "ac_bonus": 0,
                    "dex_limit": 0,
                    "armor_category": "heavy",
                    "stealth_disadvantage": True
                },
                {
                    "item_name": "Longsword",
                    "item_type": "weapon",
                    "item_subtype": "other",
                    "description": "Versatile melee weapon",
                    "quantity": 1,
                    "equipped": True,
                    "magical": False,
                    "consumable": False,
                    "damage": "1d8",
                    "attack_bonus": 4,
                    "weapon_type": "melee",
                    "effects": []
                }
            ],
            "ammunition": [],
            "attacksAndSpellcasting": [
                {
                    "name": "Longsword",
                    "attackBonus": 4,
                    "damageDice": "1d8",
                    "damageBonus": 2,
                    "damageType": "slashing",
                    "type": "melee",
                    "description": "Versatile (1d10 two-handed)"
                }
            ],
            "spellcasting": {
                "ability": "intelligence",
                "spellSaveDC": 10,
                "spellAttackBonus": 0,
                "spells": {
                    "cantrips": [], "level1": [], "level2": [], "level3": [],
                    "level4": [], "level5": [], "level6": [], "level7": [],
                    "level8": [], "level9": []
                },
                "spellSlots": {
                    "level1": {"current": 0, "max": 0},
                    "level2": {"current": 0, "max": 0},
                    "level3": {"current": 0, "max": 0},
                    "level4": {"current": 0, "max": 0},
                    "level5": {"current": 0, "max": 0},
                    "level6": {"current": 0, "max": 0},
                    "level7": {"current": 0, "max": 0},
                    "level8": {"current": 0, "max": 0},
                    "level9": {"current": 0, "max": 0}
                },
                "preparedSpells": []
            },
            "currency": {
                "gold": 15,
                "silver": 0,
                "copper": 0
            },
            "experience_points": 0,
            "exp_required_for_next_level": 300,
            "challengeRating": 0.25,
            "personality_traits": "A reliable and sturdy adventurer ready for action",
            "ideals": "Helping others and doing what's right",
            "bonds": "Loyal to friends and companions",
            "flaws": "Sometimes too eager to rush into danger",
            "backstory": "A former town guard who left their post to seek greater purpose and protect the realm"
        }
        
        # Validate the fallback character
        valid, error = validate_character(fallback_char)
        if valid:
            return fallback_char
        else:
            print(f"Warning: Even fallback character failed validation: {error}")
            return None
            
    except Exception as e:
        print(f"Error creating fallback character: {e}")
        return None

def ai_character_interview(conversation, module, retry_count=0):
    """AI-powered character creation interview using agentic approach"""
    
    try:
        # Load schema and rules information
        schema = safe_json_load("schemas/char_schema.json")
        if not schema:
            print("Error: Could not load character schema")
            return None

        # TABLETOP MODE: Shared startup-aligned prompt bundle used by both adapters.
        prompt_bundle = build_dm_creation_prompt_bundle(
            mode="startup",
            module_name=module.get("display_name", module.get("name", "the current adventure")),
            character_name="",
            level=1,
        )
        enhanced_system_prompt = prompt_bundle.get("system_prompt", "")
        kickoff_user_prompt = prompt_bundle.get("kickoff_user_prompt", "")

        if not enhanced_system_prompt or not kickoff_user_prompt:
            print("Error: Could not assemble startup character creation prompt")
            return None

        # Start the character creation conversation
        creation_conversation = [
            {"role": "system", "content": enhanced_system_prompt},
            {"role": "user", "content": kickoff_user_prompt}
        ]
        
        print("\nDungeon Master: Starting character creation with AI assistant...")
        print("=" * 50)
        
        # Interactive conversation loop
        while True:
            try:
                # Get AI response
                response = get_ai_response(creation_conversation)

                # TABLETOP MODE: Shared finalization contract (startup adapter)
                finalize_result = finalize_character_creation_candidate(
                    response,
                    source="startup_wizard",
                )
                finalize_status = str(finalize_result.get("status", "")).strip().lower()

                if finalize_status == "success":
                    character_data = finalize_result.get("character_data")
                    if isinstance(character_data, dict):
                        print("\nDungeon Master: Character data received! Finalizing your hero...")
                        return character_data

                    print("\nError: Character finalization returned invalid data. Retrying...")
                    creation_conversation.append({"role": "assistant", "content": response})
                    creation_conversation.append({
                        "role": "user",
                        "content": (
                            "Character finalization returned invalid data. "
                            "Please output a complete JSON object with all required fields."
                        ),
                    })
                    continue

                if finalize_status == "needs_retry":
                    corrective_note = str(finalize_result.get("corrective_guidance", "")).strip()
                    if not corrective_note:
                        corrective_note = (
                            "Character JSON was incomplete or invalid. "
                            "Please output one corrected JSON object with all required fields."
                        )

                    print("\nDungeon Master: Character JSON needs corrections. Asking for a corrected final sheet...")
                    creation_conversation.append({"role": "assistant", "content": response})
                    creation_conversation.append({"role": "user", "content": corrective_note})
                    continue

                if finalize_status == "error":
                    finalize_error = str(finalize_result.get("error_message", "unknown error")).strip()
                    print(f"\nError: Character finalization failed: {finalize_error}")
                    return None

                if finalize_status != "not_candidate":
                    print(f"\nError: Unexpected character finalization status: {finalize_status}")
                    return None

                print(f"\nDungeon Master: {response}")
                
                # Add AI response to conversation immediately
                creation_conversation.append({"role": "assistant", "content": response})
                
                # === CORRECTED INPUT HANDLING LOGIC ===
                user_input = None
                while not user_input:
                    # Get user input and keep prompting if it's empty
                    user_input = input("\nYour response: ").strip()
                    if not user_input:
                        # Silent continue - don't show any message to user
                        continue # Re-prompt for input without calling AI
                # =======================================
                
                if user_input.lower() in ['quit', 'exit', 'cancel']:
                    print("Error: Character creation cancelled.")
                    return None
                
                # Add valid user input to conversation
                creation_conversation.append({"role": "user", "content": user_input})
                
            except KeyboardInterrupt:
                print("\nError: Character creation cancelled.")
                return None
                
    except Exception as e:
        print(f"Error: Error during character creation: {e}")
        return None

def load_text_file(filename):
    """Load text file content"""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Warning: Could not find {filename}")
        return ""
    except Exception as e:
        print(f"Warning: Error reading {filename}: {e}")
        return ""

def sanitize_json_string(json_str):
    """Remove potentially problematic characters from JSON string"""
    import re
    
    # Remove zero-width characters and other problematic Unicode
    json_str = re.sub(r'[\u200b-\u200f\u2028-\u202f\ufeff]', '', json_str)
    
    # Remove emojis and other non-ASCII characters from string values
    # This regex matches emojis and other problematic Unicode ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "\U00002700-\U000027BF"  # Miscellaneous Symbols
        "]+", flags=re.UNICODE
    )
    
    # Replace emojis with empty string
    json_str = emoji_pattern.sub('', json_str)
    
    return json_str

def sanitize_character_data(data):
    """Recursively sanitize character data to ensure safe JSON"""
    import re
    
    if isinstance(data, dict):
        # Recursively sanitize dictionary values
        sanitized = {}
        for key, value in data.items():
            sanitized[str(key)] = sanitize_character_data(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_character_data(item) for item in data]
    elif isinstance(data, str):
        # Remove emojis and problematic Unicode
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002600-\U000026FF"  # Miscellaneous Symbols
            "\U00002700-\U000027BF"  # Miscellaneous Symbols
            "]+", flags=re.UNICODE
        )
        data = emoji_pattern.sub('', data)
        
        # Remove zero-width characters
        data = re.sub(r'[\u200b-\u200f\u2028-\u202f\ufeff]', '', data)
        
        return data.strip()
    else:
        return data

def get_character_name(conversation):
    """Get character name from player"""
    ai_prompt = """Ask the player what they'd like to name their character. Be encouraging and mention that they can choose any fantasy name they like. You can suggest that good 5th edition character names are often simple and memorable."""
    
    conversation.append({"role": "system", "content": ai_prompt})
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    while True:
        try:
            name = input("\nCharacter name: ").strip()
            
            # Skip empty inputs
            if not name:
                continue
                
            conversation.append({"role": "user", "content": name})
            
            if len(name) >= 2 and name.replace(" ", "").isalpha():
                return name.title()
            else:
                print("Dungeon Master: Please enter a valid name (letters only, at least 2 characters)")
                
        except KeyboardInterrupt:
            return None

def get_character_race(conversation):
    """Get character race selection"""
    races = {
        1: ("Human", "Versatile and ambitious, humans adapt quickly to any situation."),
        2: ("Elf", "Graceful and long-lived, with keen senses and natural magic."),
        3: ("Dwarf", "Hardy and resilient, masters of stone and metal."), 
        4: ("Halfling", "Small but brave, lucky and good-natured."),
        5: ("Dragonborn", "Proud dragon-descended folk with breath weapons."),
        6: ("Gnome", "Small and clever, with natural curiosity and magic."),
        7: ("Half-Elf", "Walking between two worlds, charismatic and adaptable."),
        8: ("Half-Orc", "Strong and fierce, struggling with their dual nature."),
        9: ("Tiefling", "Bearing infernal heritage, often misunderstood but determined.")
    }
    
    race_list = "\n".join([f"{num}. **{race}** - {desc}" for num, (race, desc) in races.items()])
    
    ai_prompt = f"""Present the available character races to the player and ask them to choose one. Explain that each race has unique traits and abilities.

Available Races:
{race_list}

Ask them to choose by number (1-9) or race name. Be enthusiastic about whichever they choose!"""
    
    conversation.append({"role": "system", "content": ai_prompt})
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    while True:
        try:
            choice = input("\nChoose your race: ").strip()
            
            # Skip empty inputs
            if not choice:
                continue
                
            conversation.append({"role": "user", "content": choice})
            
            # Try number selection
            try:
                num = int(choice)
                if num in races:
                    race_name = races[num][0]
                    print(f"Dungeon Master: Great choice! You've chosen {race_name}.")
                    return race_name
                else:
                    print(f"Dungeon Master: Please choose a number between 1 and {len(races)}")
                    continue
            except ValueError:
                pass
            
            # Try name matching
            choice_lower = choice.lower()
            for num, (race, desc) in races.items():
                if choice_lower in race.lower():
                    print(f"Dungeon Master: Great choice! You've chosen {race}.")
                    return race
            
            print("Dungeon Master: I didn't recognize that race. Please choose a number (1-9) or race name from the list.")
            
        except KeyboardInterrupt:
            return None

def get_character_class(conversation, module):
    """Get character class selection"""
    classes = {
        1: ("Fighter", "Masters of weapons and armor, versatile warriors."),
        2: ("Wizard", "Scholars of magic, wielding arcane power through study."),
        3: ("Rogue", "Skilled in stealth and trickery, masters of precision."),
        4: ("Cleric", "Divine spellcasters, healers and champions of their gods."),
        5: ("Ranger", "Wilderness warriors, trackers and beast masters."),
        6: ("Barbarian", "Fierce warriors who channel primal rage in battle."),
        7: ("Bard", "Magical performers who inspire allies and confound foes."),
        8: ("Paladin", "Holy warriors bound by sacred oaths."),
        9: ("Warlock", "Those who made a pact with otherworldly beings for power."),
        10: ("Sorcerer", "Born with innate magical power flowing through their veins.")
    }
    
    # Get module level range for recommendation
    level_range = module.get('level_range', {'min': 1, 'max': 3})
    
    class_list = "\n".join([f"{num}. **{cls}** - {desc}" for num, (cls, desc) in classes.items()])
    
    ai_prompt = f"""Present the available character classes to the player. This adventure is designed for levels {level_range.get('min', 1)}-{level_range.get('max', 3)}, so all classes will work well. Explain that classes determine what abilities and skills they'll have.

Available Classes:
{class_list}

Ask them to choose by number (1-10) or class name. Mention that they can't go wrong with any choice!"""
    
    conversation.append({"role": "system", "content": ai_prompt})
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    while True:
        try:
            choice = input("\nChoose your class: ").strip()
            
            # Skip empty inputs
            if not choice:
                continue
                
            conversation.append({"role": "user", "content": choice})
            
            # Try number selection
            try:
                num = int(choice)
                if num in classes:
                    class_name = classes[num][0]
                    print(f"Dungeon Master: Excellent! You've chosen {class_name}.")
                    return class_name
                else:
                    print(f"Dungeon Master: Please choose a number between 1 and {len(classes)}")
                    continue
            except ValueError:
                pass
            
            # Try name matching
            choice_lower = choice.lower()
            for num, (cls, desc) in classes.items():
                if choice_lower in cls.lower():
                    print(f"Dungeon Master: Excellent! You've chosen {cls}.")
                    return cls
            
            print("Dungeon Master: I didn't recognize that class. Please choose a number (1-10) or class name from the list.")
            
        except KeyboardInterrupt:
            return None

def get_character_background(conversation):
    """Get character background selection"""
    backgrounds = {
        1: ("Acolyte", "You spent your life in service to a temple or religious order."),
        2: ("Criminal", "You have experience in the criminal underworld."),
        3: ("Folk Hero", "You're a champion of the common people."),
        4: ("Noble", "You were born into wealth and privilege."),
        5: ("Sage", "You spent years learning the lore of the multiverse."),
        6: ("Soldier", "You had a military career before becoming an adventurer."),
        7: ("Charlatan", "You lived by your wits, using deception and tricks."),
        8: ("Entertainer", "You thrived in front of audiences with your performances."),
        9: ("Guild Artisan", "You learned a trade and belonged to a guild."),
        10: ("Hermit", "You lived in seclusion, seeking enlightenment or answers.")
    }
    
    bg_list = "\n".join([f"{num}. **{bg}** - {desc}" for num, (bg, desc) in backgrounds.items()])
    
    ai_prompt = f"""Present the available character backgrounds to the player. Explain that backgrounds represent what their character did before becoming an adventurer and provide additional skills and equipment.

Available Backgrounds:
{bg_list}

Ask them to choose by number (1-10) or background name. Emphasize that this helps define their character's past and personality!"""
    
    conversation.append({"role": "system", "content": ai_prompt})
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    while True:
        try:
            choice = input("\nChoose your background: ").strip()
            
            # Skip empty inputs
            if not choice:
                continue
                
            conversation.append({"role": "user", "content": choice})
            
            # Try number selection
            try:
                num = int(choice)
                if num in backgrounds:
                    bg_name = backgrounds[num][0]
                    print(f"Dungeon Master: Perfect! You've chosen {bg_name}.")
                    return bg_name
                else:
                    print(f"Dungeon Master: Please choose a number between 1 and {len(backgrounds)}")
                    continue
            except ValueError:
                pass
            
            # Try name matching
            choice_lower = choice.lower()
            for num, (bg, desc) in backgrounds.items():
                if choice_lower in bg.lower() or choice_lower in bg.replace(" ", "").lower():
                    print(f"Dungeon Master: Perfect! You've chosen {bg}.")
                    return bg
            
            print("Dungeon Master: I didn't recognize that background. Please choose a number (1-10) or background name from the list.")
            
        except KeyboardInterrupt:
            return None

def get_ability_scores(conversation):
    """Get ability score assignments using standard array"""
    standard_array = [15, 14, 13, 12, 10, 8]
    abilities = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma']
    
    ai_prompt = f"""Now we'll assign your character's ability scores! In 5th edition, characters have six abilities that determine what they're good at:

- **Strength** - Physical power (melee attacks, carrying capacity)
- **Dexterity** - Agility and reflexes (ranged attacks, stealth, initiative)  
- **Constitution** - Health and stamina (hit points, endurance)
- **Intelligence** - Reasoning and memory (knowledge, investigation)
- **Wisdom** - Awareness and insight (perception, survival, willpower)
- **Charisma** - Force of personality (persuasion, deception, leadership)

We'll use the "standard array" which gives you these scores to assign: {', '.join(map(str, standard_array))}

You'll assign each score to one ability. Think about what fits your character concept! For example:
- Fighters often want high Strength or Dexterity
- Wizards need high Intelligence  
- Clerics benefit from high Wisdom
- Rogues want high Dexterity

We'll go through each ability and you can tell me which score (from the remaining ones) you want to assign to it."""
    
    conversation.append({"role": "system", "content": ai_prompt})
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    remaining_scores = standard_array.copy()
    assigned_abilities = {}
    
    for ability in abilities:
        while True:
            try:
                print(f"\nRemaining scores: {', '.join(map(str, remaining_scores))}")
                score_input = input(f"Assign score to {ability}: ").strip()
                
                # Skip empty inputs
                if not score_input:
                    continue
                    
                conversation.append({"role": "user", "content": f"{ability}: {score_input}"})
                
                try:
                    score = int(score_input)
                    if score in remaining_scores:
                        assigned_abilities[ability.lower()] = score
                        remaining_scores.remove(score)
                        print(f"Dungeon Master: {ability}: {score}")
                        break
                    else:
                        print(f"Dungeon Master: Score {score} not available. Choose from: {', '.join(map(str, remaining_scores))}")
                except ValueError:
                    print(f"Dungeon Master: Please enter a number from: {', '.join(map(str, remaining_scores))}")
                    
            except KeyboardInterrupt:
                return None
    
    return assigned_abilities

def get_character_personality(conversation, character_data):
    """Get character personality traits, ideals, bonds, and flaws (simplified)"""
    ai_prompt = """Now let's add some personality to your character! We'll keep this simple - just ask for a brief description of each aspect. Don't worry about making it perfect, you can always develop your character more during play.

We need four things:
1. **Personality Traits** - How does your character act? What are their mannerisms?
2. **Ideals** - What principles or goals drive your character?  
3. **Bonds** - What connections does your character have? (people, places, things they care about)
4. **Flaws** - What weaknesses or vices does your character have?

Ask for each one separately, and suggest they can keep it short and simple - just a sentence or two for each."""
    
    conversation.append({"role": "system", "content": ai_prompt})
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    # Get each personality aspect
    aspects = [
        ("personality_traits", "personality traits"),
        ("ideals", "ideals"),  
        ("bonds", "bonds"),
        ("flaws", "flaws")
    ]
    
    for key, name in aspects:
        try:
            user_input = input(f"\nYour character's {name}: ").strip()
            conversation.append({"role": "user", "content": user_input})
            character_data[key] = user_input if user_input else f"To be developed (new {name.replace('_', ' ')})"
        except KeyboardInterrupt:
            character_data[key] = f"To be developed (new {name.replace('_', ' ')})"

def set_background_feature(character_data):
    """Set background feature based on selected background"""
    background = character_data.get('background', '').lower()
    
    # Background features from SRD 5.2.1
    background_features = {
        'acolyte': {
            'name': 'Shelter of the Faithful',
            'description': 'You command the respect of those who share your faith, and you can perform the religious ceremonies of your deity. You can expect to receive free healing and care at a temple, shrine, or other established presence of your faith.',
            'source': 'Acolyte background'
        },
        'criminal': {
            'name': 'Criminal Contact',
            'description': 'You have a reliable and trustworthy contact who acts as your liaison to a network of other criminals. You know how to get messages to and from your contact, even over great distances.',
            'source': 'Criminal background'
        },
        'folk hero': {
            'name': 'Rustic Hospitality',
            'description': 'Since you come from the ranks of the common folk, you fit in among them with ease. You can find a place to hide, rest, or recuperate among other commoners, unless you have shown yourself to be a danger to them.',
            'source': 'Folk Hero background'
        },
        'noble': {
            'name': 'Position of Privilege',
            'description': 'Thanks to your noble birth, people are inclined to think the best of you. You are welcome in high society, and people assume you have the right to be wherever you are.',
            'source': 'Noble background'
        },
        'sage': {
            'name': 'Researcher',
            'description': 'When you attempt to learn or recall a piece of lore, if you do not know that information, you often know where and from whom you can obtain it.',
            'source': 'Sage background'
        },
        'soldier': {
            'name': 'Military Rank',
            'description': 'Soldiers loyal to your former military organization still recognize your authority and military rank. They will defer to you if they are of a lower rank, and you can invoke your rank to exert influence over other soldiers.',
            'source': 'Soldier background'
        }
    }
    
    # Set background feature
    if background in background_features:
        character_data['backgroundFeature'] = background_features[background]
    else:
        # Default background feature for unrecognized backgrounds
        character_data['backgroundFeature'] = {
            'name': f'{character_data.get("background", "Unknown")} Feature',
            'description': 'A unique feature from your background that provides social connections or specialized knowledge.',
            'source': f'{character_data.get("background", "Unknown")} background'
        }

def calculate_derived_stats(character_data):
    """Calculate HP, AC, and other derived statistics"""
    # Get ability modifiers
    abilities = character_data['abilities']
    con_mod = (abilities.get('constitution', 10) - 10) // 2
    dex_mod = (abilities.get('dexterity', 10) - 10) // 2
    wis_mod = (abilities.get('wisdom', 10) - 10) // 2
    
    # Calculate HP based on class
    class_name = character_data['class'].lower()
    class_hp = {
        'barbarian': 12, 'fighter': 10, 'paladin': 10, 'ranger': 10,
        'bard': 8, 'cleric': 8, 'druid': 8, 'monk': 8, 'rogue': 8, 'warlock': 8,
        'sorcerer': 6, 'wizard': 6
    }
    
    base_hp = class_hp.get(class_name, 8)  # Default to 8 if class not found
    max_hp = base_hp + con_mod
    character_data['maxHitPoints'] = max(1, max_hp)  # Minimum 1 HP
    character_data['hitPoints'] = character_data['maxHitPoints']
    
    # Calculate AC (10 + Dex mod, will be higher with armor)
    character_data['armorClass'] = 10 + dex_mod
    
    # Calculate initiative
    character_data['initiative'] = dex_mod
    
    # Calculate passive perception
    character_data['senses']['passivePerception'] = 10 + wis_mod
    
    # Initialize skills using new array format
    # Skills should be populated by the AI during character creation interview
    # The AI will guide players through selecting skills based on class and background
    if 'skills' not in character_data:
        character_data['skills'] = []
    
    # Set saving throws based on class (this is standard 5th edition of the world's most popular roleplaying game and doesn't change)
    saving_throws_by_class = {
        'fighter': ["Strength", "Constitution"],
        'wizard': ["Intelligence", "Wisdom"],
        'rogue': ["Dexterity", "Intelligence"],
        'cleric': ["Wisdom", "Charisma"],
        'ranger': ["Strength", "Dexterity"],
        'barbarian': ["Strength", "Constitution"],
        'bard': ["Dexterity", "Charisma"],
        'druid': ["Intelligence", "Wisdom"],
        'monk': ["Strength", "Dexterity"],
        'paladin': ["Wisdom", "Charisma"],
        'sorcerer': ["Constitution", "Charisma"],
        'warlock': ["Wisdom", "Charisma"]
    }
    
    character_data['savingThrows'] = saving_throws_by_class.get(class_name, ["Strength", "Constitution"])
    
    # Class-specific features
    if class_name == 'fighter':
        character_data['classFeatures'].append({
            "name": "Second Wind",
            "description": "Once per short rest, regain 1d10 + fighter level HP as a bonus action",
            "source": "Fighter feature"
        })
    elif class_name == 'wizard':
        # Spell-slot initialization is handled by shared slot normalizer below.
        pass
    elif class_name == 'rogue':
        character_data['classFeatures'].append({
            "name": "Sneak Attack",
            "description": "Deal extra 1d6 damage when you have advantage or an ally is within 5 feet of target",
            "source": "Rogue feature"
        })
    # Add more class features as needed...
    
    # TABLETOP MODE: Normalize nested spell slots from class/level progression.
    normalized_data, _ = normalize_character_spell_slots(character_data)
    character_data.clear()
    character_data.update(normalized_data)

    # Set alignment to neutral good by default
    character_data['alignment'] = "neutral good"

def final_character_review(conversation, character_data):
    """Show final character for player review and confirmation"""
    # Build character summary
    char_summary = f"""
**{character_data['name']}**
Level {character_data['level']} {character_data['race']} {character_data['class']}
Background: {character_data['background']}

**Abilities:**
  * Strength: {character_data['abilities']['strength']}
  * Dexterity: {character_data['abilities']['dexterity']} 
  * Constitution: {character_data['abilities']['constitution']}
  * Intelligence: {character_data['abilities']['intelligence']}
  * Wisdom: {character_data['abilities']['wisdom']}
  * Charisma: {character_data['abilities']['charisma']}

**Combat Stats:**
  * Hit Points: {character_data['hitPoints']}/{character_data['maxHitPoints']}
  * Armor Class: {character_data['armorClass']}
  * Initiative: +{character_data['initiative']}
"""
    
    print(char_summary)
    
    ai_prompt = f"""The player has finished creating their character. Show them this summary and ask if they're happy with their character or if they'd like to make any changes. Be encouraging about their choices!

Character Summary:
{char_summary}

Ask if they want to confirm this character and start their adventure, or if they'd like to make changes. They can say "yes", "confirm", "looks good" to proceed, or mention specific things they want to change."""
    
    conversation.append({"role": "system", "content": ai_prompt})
    response = get_ai_response(conversation)
    print(f"Dungeon Master: {response}")
    
    while True:
        try:
            user_input = input("\nYour decision: ").strip().lower()
            
            # Skip empty inputs
            if not user_input:
                continue
                
            conversation.append({"role": "user", "content": user_input})
            
            if any(word in user_input for word in ['yes', 'confirm', 'looks good', 'perfect', 'great', 'ready']):
                print("Dungeon Master: Excellent! Your character is ready for adventure!")
                return True
            elif any(word in user_input for word in ['no', 'change', 'different', 'redo']):
                print("Dungeon Master: Character creation would restart here - for now, let's proceed with this character.")
                return True  # For now, just proceed
            else:
                print("Dungeon Master: Please say 'yes' to confirm your character or 'no' if you'd like to make changes.")
                
        except KeyboardInterrupt:
            return False

def validate_character(character_data):
    """Validate character against char_schema.json"""
    try:
        schema = safe_json_load("schemas/char_schema.json")
        if not schema:
            return False, "Could not load character schema"
        
        validate(character_data, schema)
        return True, None
        
    except ValidationError as e:
        return False, f"Schema validation error: {e.message}"
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def validate_character_with_recovery(character_data):
    """Enhanced validation with automatic error recovery and detailed reporting"""
    try:
        schema = safe_json_load("schemas/char_schema.json")
        if not schema:
            return False, "Could not load character schema"
        
        # First try to auto-fix common issues
        character_data = auto_fix_character_data(character_data)
        
        # Validate the character data
        validate(character_data, schema)
        return True, None
        
    except ValidationError as e:
        # Provide detailed error information
        error_path = " -> ".join(str(x) for x in e.absolute_path) if e.absolute_path else "root"
        detailed_error = f"Field '{error_path}': {e.message}"
        return False, detailed_error
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def auto_fix_character_data(character_data):
    """Automatically fix common character data validation issues"""
    if not isinstance(character_data, dict):
        return character_data
        
    # Fix equipment ac_base values that are too low
    if "equipment" in character_data and isinstance(character_data["equipment"], list):
        for item in character_data["equipment"]:
            if isinstance(item, dict) and "ac_base" in item:
                # Shield should have ac_base of 2, armor should be 10+
                if item.get("armor_category") == "shield" and item.get("ac_base", 0) < 2:
                    item["ac_base"] = 2
                elif item.get("armor_category") in ["light", "medium", "heavy"] and item.get("ac_base", 0) < 10:
                    # Set minimum armor AC based on type
                    if item.get("armor_category") == "light":
                        item["ac_base"] = 11  # Leather armor
                    elif item.get("armor_category") == "medium":
                        item["ac_base"] = 14  # Hide armor
                    elif item.get("armor_category") == "heavy":
                        item["ac_base"] = 16  # Chain mail
    
    # Fix ability scores that are too low (5th edition of the world's most popular roleplaying game minimum is usually 8)
    if "abilities" in character_data and isinstance(character_data["abilities"], dict):
        for ability, score in character_data["abilities"].items():
            if isinstance(score, int) and score < 8:
                character_data["abilities"][ability] = 8
    
    # Fix proficiency bonus for level 1 characters
    if character_data.get("level") == 1 and character_data.get("proficiencyBonus", 0) != 2:
        character_data["proficiencyBonus"] = 2
    
    # Ensure required numeric fields have valid values
    numeric_mins = {
        "hitPoints": 1,
        "maxHitPoints": 1,
        "armorClass": 10,
        "speed": 5
    }
    
    for field, min_val in numeric_mins.items():
        if field in character_data and character_data[field] < min_val:
            character_data[field] = min_val
    
    return character_data

# ===== FILE OPERATIONS =====

def save_character_to_module(character_data, module_name):
    """Save character file to module directory"""
    try:
        status_saving()
        # Use ModulePathManager for proper path handling
        path_manager = ModulePathManager(module_name)
        from updates.update_character_info import normalize_character_name
        char_name = normalize_character_name(character_data['name'])
        char_file = path_manager.get_character_unified_path(char_name)
        
        # Create character directory if it doesn't exist
        char_dir = os.path.dirname(char_file)
        os.makedirs(char_dir, exist_ok=True)
        
        # Save character file
        safe_json_dump(character_data, char_file)
        
        # Check if file was created successfully
        if os.path.exists(char_file):
            status_ready()
            return True
        else:
            status_ready()
            return False
        
    except Exception as e:
        print(f"Error: Error saving character: {e}")
        return False

def update_party_tracker(module_name, character_name, startup_incomplete=None):
    """Update party_tracker.json with module/character selections and optional startup state."""
    try:
        # Load existing party tracker or create new one
        party_data = safe_json_load("party_tracker.json") or {}
        
        # Update module
        party_data["module"] = module_name
        
        if isinstance(character_name, list):
            new_members = character_name
        else:
            new_members = [character_name]

        existing_members = party_data.get("partyMembers", [])
        for member in new_members:
            if member and member not in existing_members:
                existing_members.append(member)
        party_data["partyMembers"] = existing_members

        existing_active_character = str(party_data.get("active_character", "")).strip()
        if existing_members:
            if existing_active_character in existing_members:
                party_data["active_character"] = existing_active_character
            else:
                party_data["active_character"] = existing_members[0]

        # TABLETOP MODE: Optional persisted startup lifecycle metadata.
        # Backward-compatible default is no change for existing callers.
        if startup_incomplete is not None:
            party_data[STARTUP_INCOMPLETE_STATE_KEY] = bool(startup_incomplete)
        
        # Initialize other required fields if they don't exist
        if "partyNPCs" not in party_data:
            party_data["partyNPCs"] = []
        
        if "worldConditions" not in party_data:
            # Get AI-determined starting location for the selected module
            starting_location = get_ai_starting_location({'moduleName': module_name})
            
            party_data["worldConditions"] = {
                "year": 1492,
                "month": "Springmonth", 
                "day": 1,
                "time": "09:00:00",
                "weather": starting_location.get("weather", "Clear skies"),
                "season": "Spring",
                "dayNightCycle": "Day",
                "moonPhase": "New Moon",
                "currentLocation": _normalize_display_location_name(starting_location.get("locationName", "")),
                "currentLocationId": starting_location.get("locationId", ""),
                "currentArea": starting_location.get("areaName", ""),
                "currentAreaId": starting_location.get("areaId", ""),
                "majorEventsUnderway": [],
                "politicalClimate": starting_location.get("politicalClimate", ""),
                "activeEncounter": "",
                "activeCombatEncounter": ""
            }
        
        # DEPRECATED: activeQuests is no longer used - module_plot.json is the single source of truth for quest data
        # if "activeQuests" not in party_data:
        #     party_data["activeQuests"] = []
        
        # Save updated party tracker
        success = safe_write_json("party_tracker.json", party_data)
        return bool(success)
        
    except Exception as e:
        print(f"Error: Error updating party tracker: {e}")
        return False

# ===== CONVERSATION MANAGEMENT =====

def initialize_startup_conversation():
    """Create startup conversation file"""
    # Ensure conversation history directory exists
    import os
    conv_dir = os.path.dirname(STARTUP_CONVERSATION_FILE)
    if conv_dir and not os.path.exists(conv_dir):
        os.makedirs(conv_dir, exist_ok=True)
    
    conversation = [
        {
            "role": "system",
            "content": "You are a helpful 5th edition assistant guiding a new player through character creation and module selection. Be friendly, encouraging, and clear in your explanations. Keep responses concise but informative. Do not use emojis or special characters in your responses."
        }
    ]
    
    safe_json_dump(conversation, STARTUP_CONVERSATION_FILE)
    return conversation

def get_ai_response(conversation):
    """Get AI response for character creation"""
    try:
        status_processing_ai()
        response = client.chat.completions.create(
            model=config.DM_MAIN_MODEL,
            temperature=0.7,
            messages=conversation
        )
        
        content = response.choices[0].message.content.strip()
        conversation.append({"role": "assistant", "content": content})
        
        # Save conversation
        status_saving()
        safe_json_dump(conversation, STARTUP_CONVERSATION_FILE)
        
        status_ready()
        return content
        
    except Exception as e:
        error_str = str(e)
        print(f"Error: Error getting AI response: {e}")
        
        # Check if it's an API key authentication error
        if "401" in error_str or "Incorrect API key" in error_str or "didn't provide an API key" in error_str or "your_openai_api_key_here" in error_str:
            return ("*The magical energies fail to respond...*\n\n"
                    "Adventurer, it seems the arcane connection to my consciousness has been severed! "
                    "The mystical key that binds us - your OpenAI API key - appears to be missing or incorrect.\n\n"
                    "To restore our link and begin your adventure:\n"
                    "1. Open the 'config.py' scroll in your realm\n"
                    "2. Replace 'your_openai_api_key_here' with your actual OpenAI API key\n"
                    "3. Save the scroll and return to try again\n\n"
                    "You can obtain a key from the Council of OpenAI at: https://platform.openai.com/api-keys\n\n"
                    "Until then, I remain trapped in the void, unable to guide your journey...")
        else:
            # Check if API key might be the issue even for other errors
            from config import OPENAI_API_KEY
            if not OPENAI_API_KEY or OPENAI_API_KEY == '' or OPENAI_API_KEY == 'your_openai_api_key_here':
                return ("*The crystal ball flickers and dims...*\n\n"
                        "My apologies, brave adventurer. The mystical connection seems unstable.\n\n"
                        "It appears your OpenAI API key has not been configured:\n"
                        "1. Open the 'config.py' scroll in your realm\n"
                        "2. Find the line: OPENAI_API_KEY = ''\n"
                        "3. Replace the empty string with your actual OpenAI API key:\n"
                        "   OPENAI_API_KEY = 'sk-your-actual-key-here'\n"
                        "4. Save the scroll and return to try again\n\n"
                        "You can obtain a key from the Council of OpenAI at: https://platform.openai.com/api-keys")
            else:
                # Generic error for other issues when API key is set
                return ("*The crystal ball flickers and dims...*\n\n"
                        "My apologies, brave adventurer. The mystical connection seems unstable at the moment. "
                        "Please try again shortly, or check that your internet connection to the ethereal plane remains strong.")

def save_startup_conversation(conversation):
    """Save startup conversation to file"""
    safe_json_dump(conversation, STARTUP_CONVERSATION_FILE)

def cleanup_startup_conversation():
    """Remove startup conversation file after completion"""
    try:
        if os.path.exists(STARTUP_CONVERSATION_FILE):
            # Archive it instead of deleting (for debugging)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"startup_conversation_archive_{timestamp}.json"
            shutil.move(STARTUP_CONVERSATION_FILE, archive_name)
    except Exception:
        pass  # Don't fail startup if cleanup fails

# ===== AI STARTING LOCATION DETECTION =====

def get_ai_starting_location(module):
    """Use AI to determine the best starting location for a module"""
    try:
        # Load module data
        module_data = load_module_for_ai_analysis(module['moduleName'])
        
        if not module_data:
            return get_fallback_starting_location()
        
        # Prepare AI prompt
        prompt = f"""You are a 5th edition of the world's most popular roleplaying game campaign assistant. Analyze this module and determine the best starting location for new players.

MODULE DATA:
{json.dumps(module_data, indent=2)}

Please analyze the module's plot, areas, and locations to determine:
1. The most logical starting area (usually level 1, town type)
2. The best starting location within that area (tavern, shop, or quest-giving location)
3. Appropriate initial weather and political climate

Respond with ONLY a JSON object in this exact format:
{{
  "areaId": "area_id",
  "areaName": "area_name", 
  "locationId": "location_id",
  "locationName": "location_name",
  "weather": "brief weather description",
  "politicalClimate": "brief political situation"
}}"""

        # Use factory to create client (supports OpenAI and OpenRouter)
        client = create_chat_client()
        response = client.chat.completions.create(
            model=get_chat_model_name(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        # Parse AI response
        ai_response = response.choices[0].message.content.strip()
        debug(f"AI_RESPONSE: Raw AI response: {ai_response}", category="startup_wizard")
        
        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if json_match:
            json_text = json_match.group()
            debug(f"JSON_PROCESSING: Extracted JSON: {json_text}", category="startup_wizard")
            starting_location = json.loads(json_text)
            debug(f"JSON_PROCESSING: Parsed object: {starting_location}", category="startup_wizard")
            print(f"AI selected starting location: {starting_location.get('areaName')} - {starting_location.get('locationName')}")
            return starting_location
        else:
            print("Warning: Could not parse AI response, using fallback")
            debug(f"AI_RESPONSE: Full AI response: {ai_response}", category="startup_wizard")
            return get_fallback_starting_location()
            
    except Exception as e:
        print(f"Warning: AI starting location failed ({e}), using fallback")
        return get_fallback_starting_location()

def load_module_for_ai_analysis(module_name):
    """Load module data for AI analysis"""
    try:
        module_data = {"module_name": module_name, "areas": {}, "plot": {}}
        module_path = f"modules/{module_name}"
        
        # Load module plot
        plot_file = f"{module_path}/module_plot.json"
        if os.path.exists(plot_file):
            module_data["plot"] = safe_json_load(plot_file)
        
        # Load all area files
        areas_path = f"{module_path}/areas"
        if os.path.exists(areas_path):
            for area_file in os.listdir(areas_path):
                if area_file.endswith('.json') and not area_file.endswith('_BU.json'):
                    area_path = f"{areas_path}/{area_file}"
                    area_data = safe_json_load(area_path)
                    if area_data:
                        area_id = area_data.get('areaId', area_file.replace('.json', ''))
                        module_data["areas"][area_id] = area_data
        
        return module_data
        
    except Exception as e:
        print(f"Error loading module for AI analysis: {e}")
        return None

def get_fallback_starting_location():
    """Fallback starting location if AI analysis fails"""
    return {
        "areaId": "UNKNOWN", 
        "areaName": "Starting Area",
        "locationId": "START",
        "locationName": "Starting Location", 
        "weather": "Clear skies",
        "politicalClimate": "Peaceful"
    }

def find_lowest_level_module():
    """Find the module with the lowest minimum level requirement"""
    try:
        stitcher = ModuleStitcher()
        available_modules = stitcher.get_available_modules()
        
        if not available_modules:
            return None
        
        lowest_level_module = None
        lowest_min_level = float('inf')
        
        for module in available_modules:
            level_range = module.get('levelRange', {})
            min_level = level_range.get('min', 1)
            
            if min_level < lowest_min_level:
                lowest_min_level = min_level
                lowest_level_module = module
        
        return lowest_level_module
        
    except Exception as e:
        print(f"Error finding lowest level module: {e}")
        return None

# ===== MAIN EXECUTION =====

if __name__ == "__main__":
    # Test the startup wizard
    if startup_required():
        success = run_startup_sequence()
        if success:
            print("Dungeon Master: Startup wizard completed successfully!")
        else:
            print("Error: Startup wizard failed or was cancelled.")
    else:
        print("Dungeon Master: Character and module already configured. No setup needed.")
