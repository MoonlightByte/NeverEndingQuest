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
from contextlib import contextmanager
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T092", "utils/startup_wizard.py", 1539)
register_callsite("T093", "utils/startup_wizard.py", 1665)
from jsonschema import validate, ValidationError
from core.generators.module_stitcher import ModuleStitcher
from utils.startup_prompt_builder import build_character_creation_system_prompt as _build_character_creation_system_prompt
from utils.startup_prompt_builder import build_startup_review_prompt
from utils.startup_contract import (
    parse_startup_response, parse_startup_review, parse_startup_checkpoint,
)
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

STARTING_LOCATION_FIELDS = (
    "areaId",
    "areaName",
    "locationId",
    "locationName",
    "weather",
    "politicalClimate",
)


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
    """Resume the shared setup, publishing success only from verified files."""
    from utils.capture.live_provider_call import LiveProviderSuperseded

    print("\nDungeon Master: Welcome! Choose your adventure, then build your character.")
    initialize_game_files_from_bu()
    try:
        conversation = initialize_startup_conversation()
        module = select_module(conversation)
        if not module:
            return False
        progress = _startup_progress(conversation) or {}
        if progress.get("candidate") and progress.get("phase") in {"approved", "character_saved", "ready"}:
            with _startup_operation() as scope:
                _commit_startup_build(conversation, module, progress["candidate"],
                                      live_scope=scope, preserve_existing=True)
            character = progress["candidate"]
        else:
            name = select_or_create_character(conversation, module)
            if not name:
                return False
            character = safe_json_load(ModulePathManager(module["name"]).get_character_unified_path(name))
        if not _startup_build_ready(module["name"], character):
            raise LiveProviderSuperseded("Startup state changed before handoff")
        cleanup_startup_conversation()
        print(f"\nDungeon Master: Your character setup is saved and verified. Welcome, {character['name']}!")
        return True
    except LiveProviderSuperseded:
        raise
    except (KeyboardInterrupt, EOFError):
        print("Dungeon Master: Setup paused. Your choices are retained.")
        return False


def startup_required(party_file="party_tracker.json"):
    """Check if player character or module is missing"""
    try:
        history = safe_json_load(STARTUP_CONVERSATION_FILE)
        if isinstance(history, list):
            progress = _startup_progress(history)
            if progress and progress["phase"] != "ready":
                return True
            # A ready checkpoint already passed commit/read-back. If archiving
            # failed, it is history, not authority over subsequent HP, XP or
            # travel. Resume from the current campaign below, not its old build.
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
    """List playable modules from disk.

    P1 strip (post-715732d5 regression review): listing the adventures a player
    can start is a READ-ONLY operation. Commit 715732d5 gated it behind
    ModuleLifecycleStore.recover(), which returns INDETERMINATE for ANY leftover
    build-transaction residue (or a stray desktop.ini under
    modules/.module_transactions) and made the scan return [] -> "No modules
    available" with both bundled adventures sitting on disk (issues #167/#172/
    #173). The legacy scan (pre-715732d5) was a plain os.listdir and never had
    this failure mode. We restore that: NO recover() gate on the read-only scan.
    Crash-safe recovery still runs where it belongs -- in the module BUILD/publish
    paths (createNewModule, campaign integration), which are unchanged.

    The module_refresh_lock is kept (benign single-writer; guarantees any
    downstream lock-ownership assertions pass and serializes against a
    concurrent build). Contention retains the scan and remains cancellable;
    a busy catalog is not an empty catalog.
    """
    from utils.module_refresh_lock import module_refresh_lock
    from utils.capture.live_provider_call import _interruptible_wait, drain_live_saves
    from utils.transient_filesystem import is_transient_filesystem_error

    with _startup_operation() as scope:
        while True:
            with _startup_commit_guard(scope):
                pass
            try:
                with module_refresh_lock(max_wait_seconds=0.1) as acquired:
                    if acquired:
                        with _startup_commit_guard(scope):
                            pass
                        return _scan_available_modules_locked()
            except OSError as exc:
                if not is_transient_filesystem_error(exc):
                    raise
            drain_live_saves(scope)
            _interruptible_wait(
                0.2, scope,
                "Waiting for the module catalog; your startup choices are retained.",
                display_status,
            )


def _scan_available_modules_locked():
    """Find all available modules in modules/ directory"""
    status_loading()
    modules = []

    if not os.path.exists("modules"):
        print("Error: No modules directory found!")
        status_ready()
        return modules

    # Issue #167: a completely fresh install ships the bundled adventures as
    # *_BU.json masters only (live files are runtime state). Reuse the existing
    # guarded hydrator (skips saved_games snapshots + support dirs; strictly
    # only-if-missing, never overwrites) so any scan caller sees playable
    # modules even if its entry path did not run the wizard's own hydration.
    initialize_game_files_from_bu()

    # P1 strip: the catalog is ALWAYS derived from disk (legacy behavior). Commit
    # 715732d5 made world_registry.json the PREFERRED catalog, so an empty or
    # partial registry (fresh install, or interrupted/failed registration) shadowed
    # the real on-disk modules -> "No modules available" (#167/#173). The registry
    # is metadata written by the build/integration path; it is NOT the source of
    # truth for "what can I play". Reverting to os.listdir removes the shadow class
    # entirely (including the partial-registry case a preference check can't cover).
    catalog_names = os.listdir("modules")

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
                    # The analyzer fills absent levels with 1; use actual data
                    # rather than treating that default as a recommendation.
                    actual_data = load_module_for_ai_analysis(item) or {}
                    levels = [area['recommendedLevel']
                              for area in actual_data.get('areas', {}).values()
                              if type(area.get('recommendedLevel')) is int]
                    
                    level_range = {}
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
                    'level_range': module_data.get('moduleMetadata', {}).get('levelRange', {}),
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
        level_label = (f"Levels {level_range['min']}-{level_range['max']}"
                       if 'min' in level_range and 'max' in level_range else 'Level range unknown')
        module_list.append(
            f"{i}. **{module['display_name']}** ({level_label})\n"
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

Present EVERY listed module with its exact menu number. Recommend an adventure
only from its actual known level metadata; unknown is not level 1. Never choose
for the player. Even a sole installed module needs the player's confirmation.

Ask the player which module they'd like to play, and explain that they can just tell you the number (1, 2, etc.) or the name of the module they prefer."""
    
    conversation.append({"role": "system", "content": ai_prompt})
    
    # Get AI response
    response = get_ai_response(conversation, startup_phase="startup_module_selection")
    print(f"Dungeon Master: {response}")
    
    return modules

def select_module(conversation):
    """Handle module selection with player input"""
    modules = scan_available_modules()
    
    if not modules:
        print("Error: No modules available. Please add modules to the modules/ directory.")
        return None
    
    checkpoint = _startup_progress(conversation)
    if checkpoint and checkpoint.get('module'):
        for module in modules:
            if module['name'] == checkpoint['module']:
                return module
        print("Dungeon Master: Your selected adventure is no longer installed. Please choose an available adventure; your character choices are retained.")

    # Module replacement invalidates location readiness, not player approval.
    # Resume the existing commit/read-back path for an already approved build.
    selection_phase = 'approved' if (
        checkpoint and checkpoint.get('candidate') and checkpoint.get('phase') in
        {'approved', 'character_saved', 'ready'}
    ) else 'interview'
    
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
                    selected = modules[choice_num - 1]
                    _set_startup_progress(conversation, module=selected['name'],
                                          phase=selection_phase, location=None)
                    return selected
                else:
                    print(f"Dungeon Master: Please choose a number between 1 and {len(modules)}")
                    continue
            except ValueError:
                pass
            
            # Try to match by name
            user_lower = user_input.lower()
            matches = [module for module in modules
                       if user_lower in module['display_name'].lower()
                       or user_lower in module['name'].lower()]
            if len(matches) == 1:
                selected = matches[0]
                _set_startup_progress(conversation, module=selected['name'],
                                      phase=selection_phase, location=None)
                return selected
            if len(matches) > 1:
                print("Dungeon Master: That name matches more than one adventure. Please choose its displayed number.")
                continue
            
            print("Dungeon Master: I didn't understand that. Please enter the number (1, 2, etc.) or name of the module.")
            
        except KeyboardInterrupt:
            return None

# ===== CHARACTER MANAGEMENT =====

def scan_existing_characters(module_name):
    """List player identities, with canonical root files taking precedence."""
    characters = []
    path_manager = ModulePathManager(module_name)
    identities = set()
    for char_dir in ("characters", os.path.join(path_manager.module_dir, "characters")):
        if not os.path.isdir(char_dir):
            continue
        for filename in sorted(os.listdir(char_dir)):
            if not filename.endswith('.json') or filename.endswith('_BU.json'):
                continue
            char_path = os.path.join(char_dir, filename)
            try:
                char_data = safe_json_load(char_path)
                if char_data and char_data.get('character_role') == 'player':
                    identity = path_manager.format_filename(char_data.get('name') or filename[:-5])
                    if identity in identities:
                        continue
                    identities.add(identity)
                    characters.append({
                        'name': char_data.get('name', filename[:-5]),
                        'level': char_data.get('level', 1),
                        'race': char_data.get('race', 'Unknown'),
                        'class': char_data.get('class', 'Unknown'),
                        'filename': identity,
                        'path': char_path
                    })
            except Exception as e:
                print(f"Warning: Could not load character {filename}: {e}")
    
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
                    return _use_existing_startup_character(conversation, module, selected_char)
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
                    return _use_existing_startup_character(conversation, module, char)
            
            print("Dungeon Master: I didn't understand that. Please enter the character number, character name, or 'new' to create a new character.")
            
        except KeyboardInterrupt:
            return None

# ===== CHARACTER CREATION =====

def create_new_character(conversation, module):
    """The shared interview owns validation and durable finalization."""
    character = ai_character_interview(conversation, module)
    return character["name"] if character else None


def _use_existing_startup_character(conversation, module, selected):
    character = safe_json_load(selected["path"])
    if not character:
        print("Dungeon Master: That character file is unavailable. Please choose again.")
        return None
    with _startup_operation() as scope:
        _set_startup_progress(conversation, live_scope=scope, phase="approved",
                              candidate=character, character_path=selected["path"])
        _commit_startup_build(conversation, module, character,
                              live_scope=scope, preserve_existing=True)
    return character["name"]

def build_character_creation_system_prompt():
    """Build and return the startup wizard character-creation system prompt."""
    return _build_character_creation_system_prompt()

def _latest_player_index(conversation):
    return next((i for i in range(len(conversation) - 1, -1, -1)
                 if conversation[i].get("role") == "user"), None)


def _startup_progress(conversation):
    try:
        return parse_startup_checkpoint(conversation)
    except ValueError as exc:
        warning(f"Startup progress needs reconciliation: {exc}", category="startup")
        return None


def _set_startup_progress(conversation, *, live_scope=None, **changes):
    record = copy.deepcopy(_startup_progress(conversation)) or {
        "startup_checkpoint_version": 1, "startup_id": str(uuid4()),
        "phase": "module_selection", "module": None, "latest_user_index": None,
        "candidate": None, "location": None, "character_path": None,
    }
    record.update(changes)
    record["latest_user_index"] = _latest_player_index(conversation)
    conversation.append({"role": "system", "content": json.dumps(record, ensure_ascii=True)})
    save_startup_conversation(conversation, live_scope=live_scope)
    return record


def _review_startup_response(conversation, proposal, committed_facts, *, live_scope):
    review_messages = [
        {"role": "system", "content": build_startup_review_prompt()},
        {"role": "user", "content": json.dumps({
            "task_purpose": "startup_semantic_review",
            "interview": conversation, "proposal": proposal,
            "latest_user_index": _latest_player_index(conversation),
            "committed_facts": committed_facts,
        }, ensure_ascii=True)},
    ]
    while True:
        raw = get_ai_response(review_messages, {"type": "json_object"},
                              persist_response=False, live_scope=live_scope,
                              startup_phase="startup_review")
        try:
            return parse_startup_review(raw)
        except ValueError as exc:
            review_messages.append({"role": "system", "content": (
                f"The rejected review has invalid structure: {exc}. "
                "Return the complete corrected review object."
            )})


def ai_character_interview(conversation, module):
    """One agent-authored, independently reviewed startup turn at a time."""
    from utils.capture.live_provider_call import (
        LiveProviderSuperseded, open_live_turn_scope, finish_live_turn_scope,
    )

    conversation.append({"role": "system", "content": build_character_creation_system_prompt()})
    conversation.append({"role": "system", "content": json.dumps({
        "task_purpose": "startup_character_interview",
        "selected_adventure": module,
        "instruction": "Continue the actual interview or begin with an identity question. "
                       "Old history is context, not proof of approval or saved state. "
                       "Follow the current startup response contract.",
    }, ensure_ascii=True)})
    print("\nDungeon Master: Let's build your character together.")
    while True:
        scope = open_live_turn_scope()
        try:
            save_startup_conversation(conversation, live_scope=scope)
            correction_context = copy.deepcopy(conversation)
            while True:
                current_index = _latest_player_index(conversation)
                facts = {
                    "selected_module": module["name"],
                    "phase": (_startup_progress(conversation) or {}).get("phase", "interview"),
                    "character_saved": False, "adventure_ready": False,
                }
                request = correction_context + [{"role": "system", "content": json.dumps({
                    "latest_user_index": current_index, "committed_facts": facts,
                    "instruction": "Return the complete startup response object, not a bare sheet.",
                }, ensure_ascii=True)}]
                raw = get_ai_response(request, {"type": "json_object"},
                                      persist_response=False, live_scope=scope)
                try:
                    proposal = parse_startup_response(raw, latest_user_index=current_index)
                    if proposal["decision"] == "finalize_character":
                        # Preserve the existing narrow repairs before schema and
                        # semantic review so the reviewer sees the actual candidate.
                        character = sanitize_character_data(proposal["character"])
                        character, _ = repair_required_ammunition_field(character)
                        character, _ = repair_startup_character_sheet(character)
                        valid, detail = validate_character_with_recovery(character)
                        if not valid:
                            raise ValueError(detail)
                        try:
                            validate(character, safe_json_load("schemas/char_schema.json"))
                        except ValidationError as exc:
                            raise ValueError(exc.message) from exc
                        proposal["character"] = character
                    review = _review_startup_response(request, proposal, facts, live_scope=scope)
                except ValueError as exc:
                    correction_context.append({"role": "system", "content": (
                        f"Rejected startup proposal (not approved): {exc}. "
                        f"Correct this response using the retained player choices: {raw}"
                    )})
                    continue
                if not review["accepted"]:
                    correction_context.append({"role": "system", "content": json.dumps({
                        "rejected_proposal": proposal, "review_feedback": review["feedback"],
                        "needs_player_clarification": review["needs_player_clarification"],
                        "instruction": ("Propose a continue_interview question; do not finalize."
                                        if review["needs_player_clarification"]
                                        else "Correct the proposal without inventing a new player choice."),
                    }, ensure_ascii=True)})
                    continue
                if scope.is_superseded():
                    raise LiveProviderSuperseded("startup review superseded")
                conversation.append({"role": "assistant", "content": json.dumps(proposal, ensure_ascii=True)})
                if proposal["decision"] == "finalize_character":
                    _set_startup_progress(conversation, live_scope=scope, phase="approved",
                                          candidate=proposal["character"], character_path=None)
                    try:
                        _commit_startup_build(conversation, module, proposal["character"],
                                              live_scope=scope)
                    except FileExistsError as exc:
                        _set_startup_progress(conversation, live_scope=scope, phase="interview",
                                              candidate=None, character_path=None)
                        correction_context.append({"role": "system", "content": (
                            f"Character identity conflict: {exc}. Ask the player for a distinct "
                            "name, retaining the rest of the build. Nothing was overwritten."
                        )})
                        continue
                    return proposal["character"]
                _set_startup_progress(conversation, live_scope=scope, phase="interview")
                print(f"\nDungeon Master: {proposal['narration']}")
                break
        except LiveProviderSuperseded:
            raise
        finally:
            finish_live_turn_scope(scope)

        # No active provider scope while waiting for the next player answer.
        try:
            while True:
                user_input = input("\nYour response: ").strip()
                if user_input:
                    break
        except (EOFError, KeyboardInterrupt):
            return None
        if user_input.lower() in {"quit", "exit", "cancel"}:
            print("Dungeon Master: Character creation paused. Your choices are retained.")
            return None
        conversation.append({"role": "user", "content": user_input})

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

def _emit_startup_phase(phase):
    """Use the shared marker stream without importing main or a web surface."""
    print("STARTUP_MARKER: " + json.dumps({"phase": phase}, ensure_ascii=True))


@contextmanager
def _startup_commit_guard(scope):
    with scope.lock:
        from utils.capture.live_provider_call import LiveProviderSuperseded
        if scope.is_superseded():
            raise LiveProviderSuperseded("startup publication superseded")
        yield


@contextmanager
def _startup_operation(live_scope=None):
    from utils.capture.live_provider_call import (
        get_live_turn_scope, open_live_turn_scope, finish_live_turn_scope,
    )
    scope = live_scope or get_live_turn_scope()
    owned = scope is None
    if owned:
        scope = open_live_turn_scope()
    try:
        yield scope
    finally:
        if owned:
            finish_live_turn_scope(scope)


def _startup_write_wait(scope, detail):
    from utils.capture.live_provider_call import _interruptible_wait, drain_live_saves
    # A completed per-file boundary can service Save without ending the build.
    drain_live_saves(scope)
    warning(f"Startup write remains pending: {detail}", category="startup")
    _interruptible_wait(1.0, scope,
                        "Still saving your character setup; your choices are retained.",
                        display_status)


def save_character_to_module(character_data, module_name, *, live_scope=None, preserve_existing=False):
    """Publish one canonical root sheet, never replace a different identity."""
    from utils.file_operations import atomic_writer
    from utils.capture.live_provider_call import LiveProviderSuperseded
    with _startup_operation(live_scope) as scope:
        _emit_startup_phase("startup_character_commit")
        data = copy.deepcopy(character_data)
        if not preserve_existing:
            data, _ = repair_startup_character_sheet(data)
            validate(data, safe_json_load("schemas/char_schema.json"))
        path_manager = ModulePathManager(module_name)
        char_file = path_manager.get_character_unified_path(data['name'])
        os.makedirs(os.path.dirname(char_file), exist_ok=True)
        guard = lambda: _startup_commit_guard(scope)
        acquired = False
        try:
            atomic_writer.acquire_lock(char_file, commit_guard=guard)
            acquired = True
            if os.path.exists(char_file):
                # Equality is values, not prose or a digest. Existing sheets do
                # not receive defaults; an interrupted equal write just resumes.
                if safe_json_load(char_file) != data:
                    raise FileExistsError(f"A different character already exists at {char_file}")
                return True
            if not safe_write_json(char_file, data, acquire_lock=False, commit_guard=guard):
                return False
            return safe_json_load(char_file) == data
        except (LiveProviderSuperseded, FileExistsError):
            raise
        except Exception as exc:
            warning(f"Character publication pending: {exc}", category="startup")
            return False
        finally:
            if acquired:
                atomic_writer.release_lock(char_file)


def _resolve_startup_location(module_name, candidate):
    """Resolve exact area/location IDs from this installed adventure."""
    if not isinstance(candidate, dict):
        return None
    module_data = load_module_for_ai_analysis(module_name) or {}
    area = module_data.get("areas", {}).get(candidate.get("areaId"))
    if not isinstance(area, dict):
        return None
    locations = area.get("locations", [])
    if isinstance(locations, dict):
        locations = list(locations.values())
    location = next((item for item in locations if isinstance(item, dict)
                     and item.get("locationId") == candidate.get("locationId")), None)
    if location is None or not area.get("areaName") or not location.get("name"):
        return None
    return dict(candidate, areaName=area["areaName"], locationName=location["name"])


def update_party_tracker(module_name, character_name, *, live_scope=None, starting_location=None):
    """Commit the selected identity and a real location through the shared writer."""
    with _startup_operation(live_scope) as scope:
        _emit_startup_phase("startup_party_commit")
        party_data = safe_json_load("party_tracker.json") or {}
        same_module = party_data.get("module") == module_name
        world = copy.deepcopy(party_data.get("worldConditions") or {})
        current = {
            "areaId": world.get("currentAreaId"), "locationId": world.get("currentLocationId"),
            "areaName": world.get("currentArea"), "locationName": world.get("currentLocation"),
            "weather": world.get("weather"), "politicalClimate": world.get("politicalClimate"),
        }
        location = _resolve_startup_location(module_name, starting_location)
        if location is None and same_module:
            location = _resolve_startup_location(module_name, current)
        if location is None:
            location = get_ai_starting_location({"moduleName": module_name}, live_scope=scope)

        defaults = {
            "year": 1492, "month": "Springmonth", "day": 1, "time": "09:00:00",
            "season": "Spring", "dayNightCycle": "Day", "moonPhase": "New Moon",
            "majorEventsUnderway": [], "activeEncounter": "", "activeCombatEncounter": "",
            "weatherConditions": "",
        }
        for key, value in defaults.items():
            world.setdefault(key, value)
        world.update({
            "currentLocation": location["locationName"], "currentLocationId": location["locationId"],
            "currentArea": location["areaName"], "currentAreaId": location["areaId"],
        })
        for key in ("weather", "politicalClimate"):
            if location.get(key):
                world[key] = location[key]
        party_data["module"] = module_name
        party_data["partyMembers"] = [character_name]
        party_data.setdefault("partyNPCs", [])
        party_data["worldConditions"] = world
        validate(party_data, safe_json_load("schemas/party_schema.json"))
        success = safe_write_json("party_tracker.json", party_data,
                                  commit_guard=lambda: _startup_commit_guard(scope))
        return success and safe_json_load("party_tracker.json") == party_data


def _startup_build_ready(module_name, character):
    if not isinstance(character, dict) or not character.get("name"):
        return False
    path = ModulePathManager(module_name).get_character_unified_path(character["name"])
    sheet = safe_json_load(path)
    party = safe_json_load("party_tracker.json") or {}
    if sheet != character or party.get("module") != module_name:
        return False
    if party.get("partyMembers") != [character["name"]]:
        return False
    world = party.get("worldConditions") or {}
    if _resolve_startup_location(module_name, {
        "areaId": world.get("currentAreaId"), "locationId": world.get("currentLocationId"),
    }) is None:
        return False
    try:
        validate(party, safe_json_load("schemas/party_schema.json"))
    except ValidationError:
        return False
    return True


def _commit_startup_build(conversation, module, character, *, live_scope, preserve_existing=False):
    """Resume approved per-file work; no scene is narrated before disk is ready."""
    module_name = module["name"]
    while not save_character_to_module(character, module_name, live_scope=live_scope,
                                       preserve_existing=preserve_existing):
        _startup_write_wait(live_scope, "character file")
    path = ModulePathManager(module_name).get_character_unified_path(character["name"])
    _set_startup_progress(conversation, live_scope=live_scope, phase="character_saved",
                          candidate=character, character_path=path)
    progress = _startup_progress(conversation)
    location = _resolve_startup_location(module_name, progress.get("location"))
    if location is None:
        location = get_ai_starting_location({"moduleName": module_name}, live_scope=live_scope)
        _set_startup_progress(conversation, live_scope=live_scope, location=location)
    while True:
        if update_party_tracker(module_name, character["name"], live_scope=live_scope,
                                starting_location=location) and _startup_build_ready(module_name, character):
            break
        _startup_write_wait(live_scope, "party tracker and starting location")
    _set_startup_progress(conversation, live_scope=live_scope, phase="ready")

# ===== CONVERSATION MANAGEMENT =====

def initialize_startup_conversation():
    """Retain old history and versioned progress across engine restarts."""
    conversation = safe_json_load(STARTUP_CONVERSATION_FILE)
    if isinstance(conversation, list):
        return conversation
    conversation = [{
        "role": "system",
        "content": "Guide the player through adventure selection and character creation. "
                   "Use standard ASCII characters. Do not claim saved state without committed facts.",
    }]
    _set_startup_progress(conversation, phase="module_selection")
    return conversation

def _ensure_local_provider_alternation(messages, provider):
    """Make a startup message array safe for strict-alternation local templates.

    Issue #179 (same class as #168/#170). The startup wizard steers the DM
    entirely with ``system``-role messages and calls the model with no user turn
    (module/character selection greetings, the JSON-retry interview steps), so on
    a fresh install with a strict local chat template the game hangs at start.
    Validated directly against the real LM Studio server: qwen3.5-9b enforces TWO
    constraints its Jinja template raises 500 on --

      1. "No user query found in messages"  -> the array must end on a user turn.
      2. "System message must be at the beginning" -> only ONE system message,
         at the start (a second/mid/trailing system message is rejected).

    This is applied REACTIVELY by startup transport -- only after a local-provider
    call fails -- so lenient models (e.g. Gemma 12B), which accept the raw shape
    and succeed on the first attempt, are never reshaped (byte-identical). Only a
    strict template that actually 500s triggers a normalized retry.

    For the local provider ONLY: keep the FIRST message's system as the single
    leading system block, and convert every OTHER system message to a user turn
    IN PLACE -- preserving its content and position. This is critical for the
    JSON-retry interview step, whose directive ("return corrected JSON: <error>")
    is a trailing system message that must stay the model's operative latest
    instruction: merging it to the front and appending a generic nudge made the
    model answer the nudge (prose) instead of emitting the corrected JSON.
    Finally, ensure the array ends on a user turn.

    An already-valid request (one leading system, turns ending on user) is
    reconstructed identically, so this cannot alter a currently-working call.
    OpenAI/Gemini/legacy are returned unchanged -- they accept the raw shape.
    STARTUP-ONLY (T092 interview/review and T093 location); the main game loop and
    every non-LM-Studio provider are untouched.
    """
    if provider != "lmstudio":
        return messages
    normalized = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")
        if role == "system" and not normalized:
            normalized.append({"role": "system", "content": content})
        elif role == "system":
            normalized.append({"role": "user", "content": content})
        else:
            normalized.append({"role": role, "content": content})
    if not normalized or normalized[-1].get("role") != "user":
        normalized.append(
            {"role": "user", "content": "Please respond based on the instructions above."}
        )
    return normalized

def get_ai_response(conversation, response_format=None, *, persist_response=True, live_scope=None,
                    startup_phase="startup_interview"):
    """Run T092 through shared cancellable transport; borrowed scope stays open."""
    from utils.capture.live_provider_call import (
        LiveProviderSuperseded, finish_live_turn_scope, open_live_turn_scope,
        _interruptible_wait, _delay_for_error,
    )
    from model_config import MODEL_PROVIDER

    owned = live_scope is None
    scope = open_live_turn_scope() if owned else live_scope
    provider = MODEL_PROVIDER
    main_cfg = {
        "openai": config.DM_MAIN_GPT52_NONE,
        "gemini": config.DM_MAIN_GEMINI_PRO_LOW,
        "lmstudio": config.DM_MAIN_LMSTUDIO,
        "legacy": config.DM_MAIN_LEGACY,
    }[provider]

    def repair_rejected_messages(messages, failure):
        if provider == "lmstudio":
            return _ensure_local_provider_alternation(messages, provider)
        return messages

    request_messages = copy.deepcopy(conversation)
    _emit_startup_phase(startup_phase)
    status_processing_ai()
    try:
        while True:
            if scope.is_superseded():
                raise LiveProviderSuperseded("startup request superseded")
            try:
                response = capture_and_fanout(
                    "T092", api_client.create_completion,
                    _request_provider=provider, _live_selected="required",
                    _detached_scope=scope,
                    _live_retry_message_repair=(
                        repair_rejected_messages if provider == "lmstudio" else None
                    ),
                    messages=copy.deepcopy(request_messages),
                    model=main_cfg["model"], temperature=0.7,
                    response_format=response_format,
                    **{k: v for k, v in main_cfg.items() if k != "model"},
                )
                content = response.choices[0].message.content
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Provider returned no usable startup response")
                content = content.strip()
                if scope.is_superseded():
                    raise LiveProviderSuperseded("startup response superseded")
                if persist_response:
                    conversation.append({"role": "assistant", "content": content})
                    save_startup_conversation(conversation, live_scope=scope)
                return content
            except LiveProviderSuperseded:
                raise
            except Exception as exc:
                warning(f"Startup provider correction remains pending: {exc}", category="startup")
                # Transient requests reissue inside the shared transport. This
                # handback retains completed-error context, without a count cap.
                envelope = getattr(exc, "envelope", {"error_class": type(exc).__name__})
                request_messages.append({"role": "system", "content": (
                    f"The previous startup request did not complete correctly: {exc}. "
                    "Retain the player choices and return the requested response."
                )})
                _interruptible_wait(_delay_for_error(envelope, 0), scope,
                                    "Character setup is still pending; your choices are retained.",
                                    display_status)
    finally:
        if owned:
            finish_live_turn_scope(scope)
        status_ready()


def save_startup_conversation(conversation, *, live_scope=None):
    """Persist accepted setup progress without abandoning it on contention."""
    with _startup_operation(live_scope) as scope:
        _emit_startup_phase("startup_checkpoint_commit")
        while not safe_write_json(STARTUP_CONVERSATION_FILE, conversation,
                                  commit_guard=lambda: _startup_commit_guard(scope)):
            _startup_write_wait(scope, "startup conversation")
    return True

def cleanup_startup_conversation():
    """Remove startup conversation file after completion"""
    try:
        if os.path.exists(STARTUP_CONVERSATION_FILE):
            # Archive it instead of deleting (for debugging)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"startup_conversation_archive_{timestamp}.json"
            shutil.move(STARTUP_CONVERSATION_FILE, archive_name)
    except Exception as exc:
        warning(f"Completed startup history could not be archived: {exc}", category="startup")

# ===== AI STARTING LOCATION DETECTION =====

def _validate_starting_location(candidate):
    """Parse all six fields; membership is checked against the installed module."""
    if isinstance(candidate, str):
        try:
            candidate = json.loads(candidate)
        except ValueError:
            return None
    if type(candidate) is not dict or set(candidate) != set(STARTING_LOCATION_FIELDS):
        return None

    validated = {}
    for field in STARTING_LOCATION_FIELDS:
        value = candidate[field]
        if type(value) is not str or not value.strip():
            return None
        validated[field] = value.strip()
    return validated


def get_ai_starting_location(module, request_provider=None, *, live_scope=None):
    """Have T093 choose an entry from the installed module; never invent IDs."""
    from model_config import MODEL_PROVIDER
    from utils.capture.live_provider_call import (
        LiveProviderSuperseded, _interruptible_wait, _delay_for_error,
    )

    provider = request_provider or MODEL_PROVIDER
    profiles = {
        "openai": config.MINI_UTIL_GPT54MINI_NONE,
        "gemini": config.MINI_UTIL_GEMINI_FLASH_LOW,
        "lmstudio": config.MINI_UTIL_LMSTUDIO,
    }
    mini_cfg = profiles.get(provider, config.MINI_UTIL_LEGACY)
    module_name = module["moduleName"]
    with _startup_operation(live_scope) as scope:
        _emit_startup_phase("startup_location")
        module_data = load_module_for_ai_analysis(module_name)
        messages = [{"role": "user", "content": (
            "Analyze this installed adventure's plot and areas to choose its intended "
            "starting location for the player's new adventure. Use actual areaId and "
            "locationId values from this module only. Do not guess an ID or substitute "
            "a generic starting area. Choose appropriate initial weather and political "
            "climate. Use standard ASCII characters. Return only a JSON object with "
            "exactly six nonempty string fields: areaId, areaName, locationId, "
            "locationName, weather, politicalClimate. This is a location proposal, "
            "not evidence that the party has arrived.\nMODULE DATA:\n"
            + json.dumps(module_data, ensure_ascii=True)
        )}]
        while True:
            try:
                response = capture_and_fanout(
                    "T093", api_client.create_completion,
                    _request_provider=provider, _live_selected="required",
                    _detached_scope=scope,
                    _live_retry_message_repair=(
                        (lambda rejected, failure: _ensure_local_provider_alternation(rejected, provider))
                        if provider == "lmstudio" else None
                    ),
                    messages=copy.deepcopy(messages),
                    model=mini_cfg["model"], temperature=0.7, response_format=None,
                    **{key: value for key, value in mini_cfg.items() if key != "model"},
                )
                if scope.is_superseded():
                    raise LiveProviderSuperseded("Startup location superseded")
                raw = response.choices[0].message.content or ""
                try:
                    candidate = _validate_starting_location(extract_json_object(sanitize_json_string(raw)))
                except (ValueError, TypeError):
                    candidate = None
                location = _resolve_startup_location(module_name, candidate)
                if location is not None:
                    return location
                messages.append({"role": "system", "content": (
                    "The rejected response is incomplete or its IDs do not resolve in "
                    "the selected module. Correct all six fields using these actual "
                    "module files. No location has been committed. Rejected response: "
                    + raw + "\nCURRENT MODULE DATA:\n"
                    + json.dumps(load_module_for_ai_analysis(module_name), ensure_ascii=True)
                )})
            except LiveProviderSuperseded:
                raise
            except Exception as exc:
                warning(f"Startup location remains pending: {exc}", category="startup")
                messages.append({"role": "system", "content": (
                    f"The last location request failed: {exc}. Retain the task and "
                    "return a complete grounded proposal."
                )})
                _interruptible_wait(
                    _delay_for_error(getattr(exc, "envelope", {}) or {}, 0), scope,
                    "Still determining the adventure's starting location.", display_status,
                )

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
