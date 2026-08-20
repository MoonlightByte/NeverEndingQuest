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

import copy
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T092", "utils/startup_wizard.py", 1539)
register_callsite("T093", "utils/startup_wizard.py", 1665)
from jsonschema import validate, ValidationError
from core.generators.module_stitcher import ModuleStitcher
from utils.startup_prompt_builder import build_character_creation_system_prompt as _build_character_creation_system_prompt
from utils.character_sheet_contract import (
    extract_json_object,
    repair_required_ammunition_field,
    repair_startup_character_sheet,
)

import config
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from core.managers.status_manager import (
    status_manager, status_processing_ai, status_validating,
    status_loading, status_ready, status_saving
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

# Conversation file for character creation (separate from main game)
STARTUP_CONVERSATION_FILE = "modules/conversation_history/startup_conversation.json"

STARTUP_AI_MAX_ATTEMPTS = 3
STARTING_LOCATION_FIELDS = (
    "areaId",
    "areaName",
    "locationId",
    "locationName",
    "weather",
    "politicalClimate",
)


class StartupAIResponseError(RuntimeError):
    """Raised when a startup interview turn has no usable provider response."""

# ===== MAIN ORCHESTRATION =====

def initialize_game_files_from_bu():
    """Initialize game files from BU templates if they don't exist"""
    initialized_count = 0

    modules_root = Path("modules")
    if not modules_root.is_dir():
        return initialized_count

    # Walk only public module roots. Hidden lifecycle/forensic trees may hold
    # complete-looking candidates, but startup must never mutate or expose
    # them before transaction recovery authorizes promotion.
    support_roots = {
        "backups",
        "campaign_archives",
        "campaign_summaries",
        "conversation_history",
        "encounters",
        "logs",
    }
    public_module_roots = (
        entry
        for entry in modules_root.iterdir()
        if entry.is_dir()
        and not entry.name.startswith(".")
        and entry.name not in support_roots
    )
    for module_root in public_module_roots:
        for bu_file in module_root.rglob("*_BU.json"):
            # Skip files in saved_games directories
            if "saved_games" in bu_file.parts:
                continue

            # Determine the corresponding live file name
            live_file = str(bu_file).replace("_BU.json", ".json")

            # Only copy if the live file doesn't exist
            if not os.path.exists(live_file):
                try:
                    shutil.copy2(bu_file, live_file)
                    initialized_count += 1
                except Exception as e:
                    warning(
                        f"Failed to initialize {live_file}: {e}",
                        category="startup",
                    )
    
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
        
        # Step 3: Update party tracker
        update_party_tracker(selected_module['name'], character_name)
        
        # Cleanup
        cleanup_startup_conversation()
        
        print(f"\nDungeon Master: Setup complete! Welcome, {character_name}!")
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
    """Recover module lifecycle state, then read one stable public catalog."""
    from utils.commit_state import recover_incomplete_refresh_commit
    from utils.module_lifecycle import ModuleLifecycleStore, RecoveryStatus
    from utils.module_refresh_lock import module_refresh_lock

    with module_refresh_lock() as acquired:
        if not acquired:
            return []
        recover_incomplete_refresh_commit()
        recovery = ModuleLifecycleStore("modules").recover()
        if recovery.status is RecoveryStatus.INDETERMINATE:
            warning(
                "Module lifecycle recovery is required before startup scan",
                category="startup",
            )
            return []
        return _scan_available_modules_locked()


def _hydrate_module_from_masters(module_path):
    """Issue #167: create MISSING live module files from their shipped *_BU.json
    masters. The repository ships bundled adventures as _BU backups only (live
    files are runtime state, historically created only by an explicit campaign
    reset), so a completely fresh install had zero playable modules until the
    player discovered Settings -> Reset Campaign. Heal forward at scan time
    instead. STRICTLY additive: an existing live file is NEVER touched, so a
    campaign in progress is never reset or overwritten. Runs under
    module_refresh_lock (the caller holds it)."""
    hydrated = 0
    for root, _dirs, files in os.walk(module_path):
        for name in files:
            if not name.endswith("_BU.json"):
                continue
            master = os.path.join(root, name)
            live = master[: -len("_BU.json")] + ".json"
            if os.path.exists(live):
                continue
            try:
                shutil.copy2(master, live)
                hydrated += 1
            except OSError as copy_error:
                warning(
                    f"Could not hydrate {live} from its _BU master: {copy_error}",
                    category="startup",
                )
    if hydrated:
        info(
            f"First-run hydration: created {hydrated} live file(s) for "
            f"{os.path.basename(module_path)} from shipped _BU masters",
            category="startup",
        )


def _scan_available_modules_locked():
    """Find all available modules in modules/ directory"""
    status_loading()
    modules = []

    if not os.path.exists("modules"):
        print("Error: No modules directory found!")
        status_ready()
        return modules

    catalog_names = os.listdir("modules")
    registry_path = os.path.join("modules", "world_registry.json")
    if os.path.isfile(registry_path):
        try:
            registry = safe_json_load(registry_path)
            if isinstance(registry, dict) and isinstance(
                registry.get("modules"), dict
            ):
                registry_catalog = list(registry["modules"])
                # Issue #167 guard: the registry is the PREFERRED catalog, but an
                # empty or partial registry (fresh install, interrupted first
                # registration) must never SHADOW real module directories on
                # disk -- that made the game report "No modules available" while
                # both bundled adventures sat in modules/. Fall back to the
                # directory listing when the registry names nothing.
                if registry_catalog:
                    catalog_names = registry_catalog
        except Exception:
            # A corrupt registry must not hide on-disk modules either; keep the
            # directory listing.
            pass

    for item in catalog_names:
        module_path = f"modules/{item}"
        if os.path.isdir(module_path):
            if item.startswith('.'):
                continue
            # These directories contain runtime/support data, not playable
            # modules.  Analyzing them is both noisy and (historically) could
            # trigger an unnecessary creative travel-narration request.
            if item in {
                'backups',
                'campaign_archives',
                'campaign_summaries',
                'conversation_history',
                'default',
                'encounters',
                'logs',
            }:
                continue
            
            # Issue #167: fresh installs ship _BU masters only -- create any
            # missing live files before analysis (additive; never overwrites).
            _hydrate_module_from_masters(module_path)

            # Use module_stitcher detection method (current architecture)
            module_data = None
            try:
                from core.generators.module_stitcher import ModuleStitcher
                stitcher = ModuleStitcher()
                # Module selection only needs local metadata. Travel narration
                # belongs to integration/transition flows, not startup scans.
                detected_data = stitcher.analyze_module(
                    item, include_travel_narration=False
                )
                
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

    # The interview flow owns its own validation/requery loop.
    character_data = ai_character_interview(conversation, module)
    if not character_data:
        print("Error: Character creation failed.")
        return None

    # Final deterministic repair/validation pass before persistence.
    character_data, _ = repair_startup_character_sheet(character_data)
    valid, error = validate_character_with_recovery(character_data)
    if not valid:
        print(f"Error: Character validation failed after final repair: {error}")
        return None

    character_name = character_data['name']
    success = save_character_to_module(character_data, module['name'])
    if success:
        print(f"Dungeon Master: Character {character_name} created successfully!")
        from updates.update_character_info import normalize_character_name
        return normalize_character_name(character_name)

    print(f"Error: Failed to save character {character_name}")
    return None

def build_character_creation_system_prompt():
    """Build and return the startup wizard character-creation system prompt."""
    return _build_character_creation_system_prompt()

def _is_confirmation_trigger(user_input):
    if not isinstance(user_input, str):
        return False

    normalized = re.sub(r"\s+", " ", user_input.strip().lower())
    if not normalized:
        return False

    explicit_phrases = {
        "yes",
        "confirm",
        "confirmed",
        "looks good",
        "this looks good",
        "yes this looks good",
        "yes, this looks good",
        "please finalize",
        "finalize",
        "approved",
        "approve",
    }
    if normalized in explicit_phrases:
        return True

    if re.search(r"\b(confirm|finalize|approved?)\b", normalized):
        return True

    if re.fullmatch(r"yes[!. ]*", normalized):
        return True

    if re.search(r"\b(looks good|all looks good)\b", normalized):
        return True

    return False


def _build_json_retry_message(error_text):
    return (
        "INTERNAL SYSTEM STEP: Previous character JSON failed validation: "
        f"{error_text}. Return only a single valid JSON object that matches the "
        "character schema exactly. Include top-level \"ammunition\" as an array."
    )


def ai_character_interview(conversation, module):
    """AI-powered character creation interview using agentic approach"""
    
    try:
        enhanced_system_prompt = build_character_creation_system_prompt()

        # Continue on the active startup conversation so retries and confirmations
        # are preserved in the same history object the rest of startup uses.
        creation_conversation = conversation if isinstance(conversation, list) else []
        creation_conversation.append({"role": "system", "content": enhanced_system_prompt})
        creation_conversation.append({
            "role": "user",
            "content": (
                f"You are helping a new player create their first level 1 character for the "
                f"{module['display_name']} adventure. Welcome them to the adventure, set an "
                "immersive tone that brings them into the game world, and begin the character "
                "creation process. Start by finding out what kind of hero they want to become. "
                "Use phrases like 'Let's get you started by finding out a little bit about you' "
                "to engage them in the process."
            )
        })
        
        print("\nDungeon Master: Starting character creation with AI assistant...")
        print("=" * 50)
        
        awaiting_final_json = False
        final_json_attempts = 0
        nonfinal_json_attempts = 0

        # Interactive conversation loop
        while True:
            try:
                # Get AI response
                response = get_ai_response(
                    creation_conversation,
                    response_format={"type": "json_object"} if awaiting_final_json else None,
                )

                json_blob = extract_json_object(response)
                if json_blob:
                    nonfinal_json_attempts = 0
                    if not awaiting_final_json:
                        creation_conversation.append({
                            "role": "system",
                            "content": (
                                "INTERNAL SYSTEM STEP: You emitted machine-readable JSON during interview mode. "
                                "Do not expose JSON to the player. Continue in normal in-world prose and ask "
                                "for the next character-creation choice."
                            ),
                        })
                        continue

                    print("\nDungeon Master: Finalizing your hero...")
                    try:
                        # Additional JSON sanitization for safe character data
                        cleaned_response = sanitize_json_string(json_blob)

                        character_data = json.loads(cleaned_response)

                        # Further sanitize the loaded character data
                        character_data = sanitize_character_data(character_data)
                        character_data, _ = repair_required_ammunition_field(character_data)
                        character_data, _ = repair_startup_character_sheet(character_data)
                        valid, error = validate_character_with_recovery(character_data)
                        if valid:
                            print("\nDungeon Master: Character data received! Finalizing your hero...")
                            return character_data

                        final_json_attempts += 1
                        creation_conversation.append({
                            "role": "system",
                            "content": _build_json_retry_message(error),
                        })
                        awaiting_final_json = True
                        if final_json_attempts >= 3:
                            print(f"\nError: Unable to validate finalized character JSON after retries: {error}")
                            return None
                        continue
                    except json.JSONDecodeError as e:
                        print(f"\nError: Invalid JSON received: {e}")
                        print("Asking AI to try again...")
                        final_json_attempts += 1
                        creation_conversation.append({
                            "role": "system",
                            "content": _build_json_retry_message(
                                f"Invalid JSON: {e}"
                            ),
                        })
                        awaiting_final_json = True
                        if final_json_attempts >= 3:
                            return None
                        continue
                    except Exception as e:
                        print(f"\nError: Error processing character data: {e}")
                        final_json_attempts += 1
                        creation_conversation.append({
                            "role": "system",
                            "content": _build_json_retry_message(f"Processing error: {e}"),
                        })
                        awaiting_final_json = True
                        if final_json_attempts >= 3:
                            return None
                        continue

                if awaiting_final_json:
                    final_json_attempts += 1
                    creation_conversation.append({
                        "role": "system",
                        "content": _build_json_retry_message(
                            "The assistant returned prose instead of JSON."
                        ),
                    })
                    if final_json_attempts >= 3:
                        return None
                    continue
                else:
                    nonfinal_json_attempts = 0

                print(f"\nDungeon Master: {response}")

                # Get user input - empty input handled by outer loop
                user_input = input("\nYour response: ").strip()
                if not user_input:
                    # Empty input: continue outer loop without adding to conversation
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'cancel']:
                    print("Error: Character creation cancelled.")
                    return None
                
                # Add valid user input to conversation
                creation_conversation.append({"role": "user", "content": user_input})
                if _is_confirmation_trigger(user_input):
                    creation_conversation.append({
                        "role": "system",
                        "content": "INTERNAL SYSTEM STEP: The player has confirmed the character. Return only the finalized character JSON object. Use valid JSON only and include top-level \"ammunition\" as an array.",
                    })
                    awaiting_final_json = True
                    final_json_attempts = 0
                else:
                    awaiting_final_json = False
                
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
        character_data['spellSlots'] = {"1": {"current": 2, "max": 2}}
    elif class_name == 'rogue':
        character_data['classFeatures'].append({
            "name": "Sneak Attack",
            "description": "Deal extra 1d6 damage when you have advantage or an ally is within 5 feet of target",
            "source": "Rogue feature"
        })
    # Add more class features as needed...
    
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

    character_data, _ = repair_startup_character_sheet(character_data)

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
        character_data, _ = repair_startup_character_sheet(character_data)
        # Use ModulePathManager for proper path handling
        path_manager = ModulePathManager(module_name)
        from updates.update_character_info import normalize_character_name
        char_name = normalize_character_name(character_data['name'])
        char_file = path_manager.get_character_unified_path(char_name)
        
        # Create character directory if it doesn't exist
        char_dir = os.path.dirname(char_file)
        os.makedirs(char_dir, exist_ok=True)
        
        # Save character file atomically
        if not safe_write_json(char_file, character_data):
            status_ready()
            return False

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

def update_party_tracker(module_name, character_name):
    """Update party_tracker.json with module and character selections"""
    try:
        # Load existing party tracker or create new one
        party_data = safe_json_load("party_tracker.json") or {}
        
        # Update module
        party_data["module"] = module_name
        
        # Update party members - store display name
        party_data["partyMembers"] = [character_name]
        
        # Initialize other required fields if they don't exist
        if "partyNPCs" not in party_data:
            party_data["partyNPCs"] = []
        
        if "worldConditions" not in party_data:
            # Get AI-determined starting location for the selected module
            starting_location = get_ai_starting_location({'moduleName': module_name})
            starting_location = (
                _validate_starting_location(starting_location)
                or get_fallback_starting_location()
            )
            
            party_data["worldConditions"] = {
                "year": 1492,
                "month": "Springmonth", 
                "day": 1,
                "time": "09:00:00",
                "weather": starting_location.get("weather", "Clear skies"),
                "season": "Spring",
                "dayNightCycle": "Day",
                "moonPhase": "New Moon",
                "currentLocation": starting_location.get("locationName", ""),
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
        return success
        
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
            "content": "You are a helpful 5th edition assistant guiding a new player through character creation and module selection. Be friendly, encouraging, and clear in your explanations. Keep responses concise but informative. Do not use emojis or special characters in your responses. Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols."
        }
    ]
    
    safe_write_json(STARTUP_CONVERSATION_FILE, conversation)
    return conversation

def get_ai_response(conversation, response_format=None):
    """Return one persisted assistant turn, retrying provider failures safely.

    Provider failures never become assistant prose. Each retry receives the same
    message snapshot, and the live conversation is mutated only after a usable
    response has been received.
    """
    status_processing_ai()
    try:
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            main_cfg = config.DM_MAIN_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            main_cfg = config.DM_MAIN_GEMINI_PRO_LOW
        elif MODEL_PROVIDER == "lmstudio":
            main_cfg = config.DM_MAIN_LMSTUDIO
        else:  # legacy
            main_cfg = config.DM_MAIN_LEGACY

        request_messages = copy.deepcopy(conversation)
        last_error = None
        content = None
        for attempt in range(1, STARTUP_AI_MAX_ATTEMPTS + 1):
            try:
                response = capture_and_fanout("T092", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=copy.deepcopy(request_messages),
                    model=main_cfg["model"],
                    temperature=0.7,
                    response_format=response_format,
                    **{k: v for k, v in main_cfg.items() if k != "model"})

                raw_content = response.choices[0].message.content
                if not isinstance(raw_content, str) or not raw_content.strip():
                    raise ValueError("provider returned no usable text")
                content = raw_content.strip()
                break
            except Exception as exc:
                last_error = exc
                warning(
                    f"Startup AI turn failed for provider {MODEL_PROVIDER} "
                    f"(attempt {attempt}/{STARTUP_AI_MAX_ATTEMPTS}): {exc}",
                    category="startup",
                )

        if content is None:
            raise StartupAIResponseError(
                f"Startup AI turn failed for provider {MODEL_PROVIDER} after "
                f"{STARTUP_AI_MAX_ATTEMPTS} attempts"
            ) from last_error

        conversation.append({"role": "assistant", "content": content})

        # Save conversation
        status_saving()
        history_error = None
        try:
            history_saved = safe_write_json(STARTUP_CONVERSATION_FILE, conversation)
        except Exception as exc:
            history_saved = False
            history_error = exc
        if not history_saved:
            detail = f": {history_error}" if history_error is not None else ""
            warning(
                "Could not persist startup conversation; continuing with in-memory history"
                f"{detail}",
                category="startup",
            )

        return content
    finally:
        status_ready()

def save_startup_conversation(conversation):
    """Save startup conversation to file"""
    safe_write_json(STARTUP_CONVERSATION_FILE, conversation)

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

def _validate_starting_location(candidate):
    """Return a clean, complete starting location or ``None``.

    This is intentionally all-or-nothing: model fields are never merged into the
    deterministic fallback that can be persisted to ``party_tracker.json``.
    """
    if type(candidate) is not dict or set(candidate) != set(STARTING_LOCATION_FIELDS):
        return None

    validated = {}
    for field in STARTING_LOCATION_FIELDS:
        value = candidate[field]
        if type(value) is not str or not value.strip():
            return None
        validated[field] = value.strip()
    return validated


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

Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols.

Respond with ONLY a JSON object in this exact format:
{{
  "areaId": "area_id",
  "areaName": "area_name", 
  "locationId": "location_id",
  "locationName": "location_name",
  "weather": "brief weather description",
  "politicalClimate": "brief political situation"
}}"""

        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
        elif MODEL_PROVIDER == "gemini":
            mini_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            mini_cfg = config.MINI_UTIL_LMSTUDIO
        else:  # legacy
            mini_cfg = config.MINI_UTIL_LEGACY

        response = capture_and_fanout("T093", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=[{"role": "user", "content": prompt}],
            model=mini_cfg["model"],
            temperature=0.7,
            response_format=None,
            **{k: v for k, v in mini_cfg.items() if k != "model"})
        
        # Parse AI response
        ai_response = response.choices[0].message.content.strip()
        debug(f"AI_RESPONSE: Raw AI response: {ai_response}", category="startup_wizard")
        
        starting_location = _validate_starting_location(json.loads(ai_response))
        if starting_location is None:
            print("Warning: AI starting location was incomplete, using fallback")
            debug(f"AI_RESPONSE: Full AI response: {ai_response}", category="startup_wizard")
            return get_fallback_starting_location()

        debug(f"JSON_PROCESSING: Parsed object: {starting_location}", category="startup_wizard")
        print(f"AI selected starting location: {starting_location['areaName']} - {starting_location['locationName']}")
        return starting_location
            
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
    """Return the complete deterministic location persisted when T093 fails."""
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
