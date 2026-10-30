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
register_callsite("T092", "utils/startup_wizard.py", 1035)
register_callsite("T093", "utils/startup_wizard.py", 2032)
register_callsite("T124", "utils/startup_wizard.py", 826)
from jsonschema import validate, ValidationError
from core.generators.module_stitcher import ModuleStitcher
from utils.startup_prompt_builder import build_character_creation_system_prompt as _build_character_creation_system_prompt
from utils.startup_prompt_builder import build_startup_review_prompt
from utils.startup_prompt_builder import (
    ORIGINS_FILE, STARTUP_RULES_REFERENCE_PURPOSE, build_startup_rules_reference,
)
from utils.startup_contract import (
    parse_startup_response, parse_startup_review, parse_startup_checkpoint,
)
from core.nql import creation_build, creation_scope
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

class StartupCancelled(Exception):
    """Intentional input cancellation; retained setup is not a failure."""


def _foreign_save(module_name):
    """True when party_tracker.json is another installed module's save
    (D-1285-1): its module value is an installed folder id, never a name, and
    not the selected one. Any other value (empty, a display name, a module no
    longer installed) is not one: #1284 still empties the tracker at commit."""
    tracker = safe_json_load("party_tracker.json")
    module = tracker.get("module") if isinstance(tracker, dict) else None
    if not isinstance(module, str) or module == module_name:
        return False
    from utils.capture.live_provider_call import LiveProviderSuperseded
    try:
        installed = {entry["name"] for entry in scan_available_modules()}
    except LiveProviderSuperseded:
        raise
    except Exception as exc:
        # An unreadable catalog is not a foreign save; setup goes on (B1).
        warning(f"Foreign-save check skipped: {exc}", category="startup")
        return False
    return module in installed


def reset_foreign_save(module_name):
    """Run the whole Reset, backup first, before a new game starts over another
    module's save (#1285, D-1285-1). True when it ran. A reset that does not
    finish is reported and setup goes on (B1); the tracker is still emptied at
    commit (#1284)."""
    if not _foreign_save(module_name):
        return False
    from utils.reset_campaign import perform_reset_logic
    try:
        backup_dir = perform_reset_logic()
    except Exception as exc:
        from utils.player_notice import show_reset_failed

        show_reset_failed(exc)
        return False
    from web.shared_state import message_log_reset
    message_log_reset()
    _say("Dungeon Master: This save belonged to another adventure, so the campaign was reset "
          f"first, as Reset does. The old game is backed up in {backup_dir}.")
    return True


def _saved_defense_line(character):
    """The saved sheet's armor class and hit points for the post-save line (dplay-AC-difficult turn 18): the
    engine-projected values, which the interview preview cannot show before the gear is granted."""
    ac, hp = character.get("armorClass"), character.get("maxHitPoints")
    if type(ac) is not int or type(hp) is not int:
        return ""
    return f" Armor class {ac}, hit points {hp}."


def run_startup_sequence():
    """Resume the shared setup, publishing success only from verified files."""
    from utils.capture.live_provider_call import LiveProviderSuperseded

    # flush=True publishes this line as its own card before the next one (#1422 F1).
    _say("\nDungeon Master: Welcome! Choose your adventure, then build your character.", flush=True)
    initialize_game_files_from_bu()
    try:
        conversation = initialize_startup_conversation()
        module = select_module(conversation)
        if not module:
            return False
        if reset_foreign_save(module["name"]):
            # Reset removed the setup file; the choices made so far are in memory.
            save_startup_conversation(conversation)
        progress = _startup_progress(conversation) or {}
        if progress.get("candidate") and progress.get("phase") in {"approved", "character_saved", "ready"}:
            with _startup_operation() as scope:
                _commit_startup_build(conversation, module, progress["candidate"],
                                      live_scope=scope, preserve_existing=True)
            character = progress["candidate"]
        else:
            name = (create_new_character(conversation, module)
                    if _startup_interview_started(conversation)
                    else select_or_create_character(conversation, module))
            if not name:
                return False
            character = safe_json_load(ModulePathManager(module["name"]).get_character_unified_path(name))
        if not _startup_build_ready(module["name"], character):
            raise LiveProviderSuperseded("Startup state changed before handoff")
        # D-PKG-8: the engine purse; a character the interview created starts with it.
        from core.nql.acquisition import balance
        purse = "You start with" if _startup_interview_started(conversation) else "You have"
        cleanup_startup_conversation()
        _say(f"\nDungeon Master: Your character setup is saved and verified. Welcome, {character['name']}! "
              f"{purse} {balance(character)['gold']} gold.{_saved_defense_line(character)}")
        return True
    except LiveProviderSuperseded:
        raise
    except (StartupCancelled, KeyboardInterrupt, EOFError):
        # #341: a headless Reset ends input the same way as Quit, then removes
        # the unfinished interview; it must not be told its choices are kept.
        if _input_control_kind() != "reset":
            _say("Dungeon Master: Setup paused. Your choices are retained.")
        raise StartupCancelled() from None


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

def _present_startup_menu(conversation, prompt, *, phase="startup_interview"):
    """Keep catalog presentation separate from retained interview instructions."""
    request = [
        {"role": "system", "content": (
            "Present only the supplied startup menu in plain ASCII prose. "
            "Preserve every supplied option and its exact number. Do not choose "
            "for the player, create a character, or claim anything was saved. "
            "This is menu presentation, not a character interview; do not emit JSON."
        )},
        {"role": "user", "content": prompt},
    ]
    with _startup_operation() as scope:
        response = get_ai_response(request, persist_response=False,
                                   live_scope=scope, startup_phase=phase)
        conversation.extend([
            {"role": "system", "content": prompt},
            {"role": "assistant", "content": response},
        ])
        save_startup_conversation(conversation, live_scope=scope)
        _say(f"Dungeon Master: {response}")


def _menu_key(text):
    """One whole menu answer or option name, spacing and case folded (D-KW-6)."""
    return " ".join(str(text).split()).casefold()


def _input_control_kind():
    """The lifecycle control that ended input ("quit", "reset"), read from the
    headless stdin when it carries one (#341); None for a terminal or the web."""
    import sys

    kind = getattr(sys.stdin, "lifecycle_control_kind", None)
    try:
        return kind() if callable(kind) else None
    except Exception:
        return None


def _say(text, flush=False):
    """A player-facing wizard line (#257): the frontend's narration sink, else today's print.

    The card is what the stdout scraper used to build from the same line: the
    text without its "Dungeon Master:" prefix and surrounding blank lines. With
    no sink (the plain terminal) the print is byte-identical to before.
    """
    from web.shared_state import emit_player_output

    content = text.strip()
    if content.startswith("Dungeon Master:"):
        content = content[len("Dungeon Master:"):].strip()
    if content and emit_player_output(
        {"type": "narration", "channel": "main", "content": content}
    ) is True:
        return
    print(text, flush=flush)


def _print_startup_choices(labels):
    """Print the exact numbered choices under the presented menu."""
    _say("\n".join(f"{i}. {label}" for i, label in enumerate(labels, 1)))


# D-STARTUP-MENU-1 (#1260): the adventure menu lists the module builder as its
# last option. It is not stitched in yet: choosing it says so and shows the menu
# again; nothing here imports or starts the builder.
MODULE_BUILDER_OPTION = "Create a new adventure (module builder)"


def _module_builder_coming_soon(labels):
    """The builder option: a coming-soon line and the menu again (no builder path)."""
    _say("Dungeon Master: Creating a new adventure with the module builder is coming soon. "
          "For now, please choose one of the installed adventures.")
    _print_startup_choices(labels)


def _read_menu_sentence(menu, labels, details, line):
    """A menu answer code did not resolve, read by T127 (D-STARTUP-MENU-1): the
    numbered options as printed and the player's whole line; returns {"choice": n},
    {"question": text} or {"unavailable": outcome}."""
    from core.ai.menu_answer import read_menu_answer, request_payload
    options = [{"number": number, "name": label, "detail": detail}
               for number, (label, detail) in enumerate(zip(labels, details), 1)]
    return read_menu_answer(request_payload(menu, options, line))


def present_module_options(conversation, modules):
    """Show available modules to player using AI"""
    if not modules:
        _say("Error: No valid modules found!")
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
    
    module_list.append(
        f"{len(modules) + 1}. **{MODULE_BUILDER_OPTION}**\n"
        "   Build your own adventure. Coming soon."
    )
    modules_text = "\n\n".join(module_list)
    
    # AI prompt for module selection
    ai_prompt = f"""You are the Dungeon Master for NeverEndingQuest, a text-based adventure game based on the world's most popular 5th edition roleplaying game. Welcome the player and present the available modules.

Start with: "Welcome to NeverEndingQuest! This adventure game uses the SRD 5.2.1 rules (based on the world's most popular 5th edition roleplaying game) to bring you an immersive text-based fantasy experience."

Then mention these key features:
- AI-powered storytelling that adapts to your choices
- Turn-based tactical combat with dice rolling
- Character progression from level 1 to 20
- Inventory management and magical items
- Multiple adventure modules with interconnected stories
- Save/load system to continue your adventures

Available Modules:
{modules_text}

Present EVERY listed option with its exact menu number; the last one, creating a new adventure with the module builder, is coming soon. Recommend an adventure
only from its actual known level metadata; unknown is not level 1. Never choose
for the player. Even a sole installed module needs the player's confirmation.

Ask the player which module they'd like to play, and explain that they can type its number (1, 2, etc.) or its name, or simply say which adventure they want."""
    
    _present_startup_menu(conversation, ai_prompt, phase="startup_module_selection")
    _print_startup_choices([module['display_name'] for module in modules] + [MODULE_BUILDER_OPTION])
    
    return modules

def select_module(conversation):
    """Handle module selection with player input"""
    modules = scan_available_modules()
    
    if not modules:
        _say("Error: No modules available. Please add modules to the modules/ directory.")
        return None
    
    checkpoint = _startup_progress(conversation)
    if checkpoint and checkpoint.get('module'):
        for module in modules:
            if module['name'] == checkpoint['module']:
                return module
        _say("Dungeon Master: Your selected adventure is no longer installed. Please choose an available adventure; your character choices are retained.")

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
            builder_number = len(modules) + 1
            labels = [module['display_name'] for module in modules] + [MODULE_BUILDER_OPTION]
            try:
                choice_num = int(user_input)
                if choice_num == builder_number:
                    _module_builder_coming_soon(labels)
                    continue
                if 1 <= choice_num <= len(modules):
                    selected = modules[choice_num - 1]
                    _set_startup_progress(conversation, module=selected['name'],
                                          phase=selection_phase, location=None)
                    return selected
                else:
                    _say(f"Dungeon Master: Please choose a number between 1 and {builder_number}")
                    continue
            except ValueError:
                pass
            
            # The number, or the adventure's whole name (D-KW-6).
            answer = _menu_key(user_input)
            if answer == _menu_key(MODULE_BUILDER_OPTION):
                _module_builder_coming_soon(labels)
                continue
            matches = [module for module in modules
                       if answer in {_menu_key(module['display_name']),
                                     _menu_key(module['name'])}]
            if len(matches) == 1:
                selected = matches[0]
                _set_startup_progress(conversation, module=selected['name'],
                                      phase=selection_phase, location=None)
                return selected
            if len(matches) > 1:
                _say("Dungeon Master: That name matches more than one adventure. Please choose its displayed number.")
                continue
            
            # Any other line is read by T127 (D-STARTUP-MENU-1).
            details = [module['description'] for module in modules] + ['Build your own adventure. Coming soon.']
            read = _read_menu_sentence("adventure", labels, details, user_input)
            if read.get("choice") == builder_number:
                _module_builder_coming_soon(labels)
                continue
            if read.get("choice"):
                selected = modules[read["choice"] - 1]
                _set_startup_progress(conversation, module=selected['name'],
                                      phase=selection_phase, location=None)
                return selected
            if read.get("question"):
                _say(f"Dungeon Master: {read['question']}")
                continue
            
            _say("Dungeon Master: I didn't understand that. Please enter the number (1, 2, etc.) or the adventure's full name as listed.")
            
        except KeyboardInterrupt:
            raise

# ===== CHARACTER MANAGEMENT =====

def scan_existing_characters(module_name):
    """List player identities, with canonical root files taking precedence."""
    from updates.update_character_info import is_character_backup_file
    characters = []
    path_manager = ModulePathManager(module_name)
    identities = set()
    for char_dir in ("characters", os.path.join(path_manager.module_dir, "characters")):
        if not os.path.isdir(char_dir):
            continue
        for filename in sorted(os.listdir(char_dir)):
            # A code-written backup copy is not a character (#1263): listed, the
            # oldest copy sorts before the sheet and the commit refuses it.
            if not filename.endswith('.json') or filename.endswith('_BU.json') \
                    or is_character_backup_file(filename):
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
        # #1368: no model call. This note is not a menu, so the menu prompt answered
        # "No startup menu was supplied."; the interview opener welcomes the player
        # into creation instead.
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

{len(characters) + 1}. Create a new character

Be helpful and explain that they can type the character's number or name, or "new" (or {len(characters) + 1}) to create a fresh character, or simply say which they want."""
    
    _present_startup_menu(conversation, ai_prompt)
    _print_startup_choices([char['name'] for char in characters] + ['Create a new character'])
    
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
            if _menu_key(user_input) == 'new':
                return create_new_character(conversation, module)
            
            # Try to parse as number
            try:
                choice_num = int(user_input)
                if choice_num == len(characters) + 1:
                    return create_new_character(conversation, module)
                if 1 <= choice_num <= len(characters):
                    selected_char = characters[choice_num - 1]
                    _say(f"Dungeon Master: Excellent! You've selected {selected_char['name']}!")
                    chosen = _use_existing_startup_character(conversation, module, selected_char)
                    if chosen:
                        return chosen
                    continue
                else:
                    _say(f"Dungeon Master: Please choose a number between 1 and {len(characters) + 1}; {len(characters) + 1} or 'new' creates a character")
                    continue
            except ValueError:
                pass
            
            # The number, or the character's whole name (D-KW-6).
            answer = _menu_key(user_input)
            named = [char for char in characters if _menu_key(char['name']) == answer]
            if len(named) > 1:
                _say("Dungeon Master: That name matches more than one character. Please choose its displayed number.")
                continue
            matched = named[0] if named else None
            if matched is not None:
                _say(f"Dungeon Master: Excellent! You've selected {matched['name']}!")
                chosen = _use_existing_startup_character(conversation, module, matched)
                if chosen:
                    return chosen
                continue
            
            # Any other line is read by T127 (D-STARTUP-MENU-1).
            labels = [char['name'] for char in characters] + ['Create a new character']
            details = [f"Level {char['level']} {char['race']} {char['class']}" for char in characters]
            details.append('Make a brand new character for this adventure')
            read = _read_menu_sentence("character", labels, details, user_input)
            if read.get("choice") == len(characters) + 1:
                return create_new_character(conversation, module)
            if read.get("choice"):
                selected_char = characters[read["choice"] - 1]
                _say(f"Dungeon Master: Excellent! You've selected {selected_char['name']}!")
                chosen = _use_existing_startup_character(conversation, module, selected_char)
                if chosen:
                    return chosen
                continue
            if read.get("question"):
                _say(f"Dungeon Master: {read['question']}")
                continue
            
            _say("Dungeon Master: I didn't understand that. Please enter the character's number or full name as listed, or 'new' to create a new character.")
            
        except KeyboardInterrupt:
            raise

# ===== CHARACTER CREATION =====

def create_new_character(conversation, module):
    """The shared interview owns validation and durable finalization."""
    character = ai_character_interview(conversation, module)
    return character["name"] if character else None


def _use_existing_startup_character(conversation, module, selected):
    from updates.save_game_manager import SaveGameManager
    from utils.encoding_utils import sanitize_dict
    from utils.transient_filesystem import read_bytes_preserving_errors

    try:
        # A file another program holds is waited for (B2); a missing, empty or
        # broken one is unavailable and the player chooses again (#338).
        # The bytes are read with the native Windows lock error kept: open()
        # reports a held file as plain access denied, which is not retried.
        raw = SaveGameManager._restore_io(
            read_bytes_preserving_errors, selected["path"],
            wait_label="Character selection",
        )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        character = sanitize_dict(json.loads(text))
    except (OSError, ValueError) as exc:
        warning(f"STARTUP: selected character unavailable: {selected['path']}: {exc}",
                category="startup")
        character = None
    if not isinstance(character, dict) or not character.get("name"):
        _say("Dungeon Master: That character file is unavailable. "
              "Please choose another character, or type 'new' to create one.")
        return None
    with _startup_operation() as scope:
        _set_startup_progress(conversation, live_scope=scope, phase="approved",
                              candidate=character, character_path=selected["path"])
        _commit_startup_build(conversation, module, character,
                              live_scope=scope, preserve_existing=True)
    return character["name"]

def build_character_creation_system_prompt(*, scoped=False):
    """Build and return the startup wizard character-creation system prompt."""
    return _build_character_creation_system_prompt(scoped=scoped)

def _paused_player_indexes(conversation):
    """Player inputs whose request to stop setup a published pause_setup already honored."""
    indexes = set()
    for message in conversation:
        if message.get("role") != "assistant":
            continue
        try:
            proposal = json.loads(message.get("content", ""))
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(proposal, dict) and proposal.get("decision") == "pause_setup":
            indexes.add((proposal.get("confirmation") or {}).get("player_message_index"))
    return indexes


def _latest_player_index(conversation):
    return next((i for i in range(len(conversation) - 1, -1, -1)
                 if conversation[i].get("role") == "user"), None)


def _startup_interview_started(conversation):
    """Recognize the existing code-authored task record, never approval prose."""
    for message in conversation:
        if message.get("role") != "system":
            continue
        try:
            record = json.loads(message.get("content", ""))
        except (ValueError, TypeError):
            continue
        if isinstance(record, dict) and record.get("task_purpose") == "startup_character_interview":
            return True
    return False


def _startup_rules_reference_present(conversation):
    """True when a code-authored creation reference is already in the interview."""
    for message in conversation:
        if message.get("role") != "system":
            continue
        try:
            record = json.loads(message.get("content", ""))
        except (ValueError, TypeError):
            continue
        if isinstance(record, dict) and record.get("task_purpose") == STARTUP_RULES_REFERENCE_PURPOSE:
            return True
    return False


def _append_startup_rules_reference(conversation):
    """Supply the creation reference once per interview; a resume keeps the one it has."""
    if _startup_rules_reference_present(conversation):
        return
    reference = build_startup_rules_reference()
    if reference is None:
        warning("Startup rules reference unavailable; the interview continues without it",
                category="startup")
        return
    conversation.append({"role": "system", "content": json.dumps(reference, ensure_ascii=False)})


def _system_records(conversation, purpose):
    """The code-authored system records with this task_purpose, in history order."""
    records = []
    for message in conversation:
        if message.get("role") != "system":
            continue
        try:
            record = json.loads(message.get("content", ""))
        except (ValueError, TypeError):
            continue
        if isinstance(record, dict) and record.get("task_purpose") == purpose:
            records.append(record)
    return records


def _startup_review_mode():
    """The review shape (D-CREATE-COST-5): "engine" (default) or "whole" (#1278's review over the engine-built
    sheet). "sectioned", set before the rename, reads as "engine"; any other value too (no authority)."""
    from model_config import STARTUP_REVIEW_MODE
    return "whole" if STARTUP_REVIEW_MODE == "whole" else "engine"


def _creation_scope_current(conversation):
    """The interview's current engine scope item (the latest appended), or None."""
    scopes = _system_records(conversation, creation_scope.SCOPE_PURPOSE)
    return scopes[-1] if scopes else None


SCOPE_STATE_PURPOSE = "startup_scope_state"


def _scope_states(conversation, purpose=SCOPE_STATE_PURPOSE):
    """This interview's scope state records (or other per-startup records of purpose), in order: by purpose
    and the current checkpoint's startup_id (r3.1 section 3.6); a record of another startup never applies to this one."""
    states = _system_records(conversation, purpose)
    startup_id = (_startup_progress(conversation) or {}).get("startup_id")
    if startup_id is not None:
        # A record written before the history's first checkpoint has no id; that checkpoint minted the id of
        # the same startup, so the record is the first startup's and no later one's.
        first = _first_startup_id(conversation)
        states = [s for s in states if s.get("startup_id") == startup_id
                  or (s.get("startup_id") is None and startup_id == first)]
    return states


def _first_startup_id(conversation):
    for message in conversation:
        if message.get("role") != "system":
            continue
        try:
            record = json.loads(message.get("content", ""))
        except (TypeError, ValueError):
            continue
        if isinstance(record, dict) and "startup_checkpoint_version" in record:
            return record.get("startup_id")
    return None


ABILITY_ROLL_PURPOSE = "startup_ability_roll"
OPEN_CHOICES_PURPOSE = "startup_open_choices"


def _ability_roll(conversation):
    """This interview's engine ability roll (D-CREATE-COST-5, amendment 1f), or None: one per interview,
    kept with the history and never rolled again on resume."""
    rolls = _scope_states(conversation, ABILITY_ROLL_PURPOSE)
    return rolls[-1] if rolls else None


ENGINE_BUILD_PURPOSE = "startup_engine_build"
SHEET_PREVIEW_PURPOSE = "startup_sheet_preview"


def _persist_system_record(conversation, record, live_scope):
    """Append a code-authored record to the saved history and save it now (the ability roll)."""
    conversation.append({"role": "system", "content": json.dumps(record, ensure_ascii=False)})
    save_startup_conversation(conversation, live_scope=live_scope)


def _sheet_preview(conversation, intent):
    """Once no choice id is open, the engine builds the sheet for the published intent and the player sees
    the summary rendered from it (D2); the author gets it as a typed startup_sheet_preview item. Returns the
    summary text when it changed since the last preview, else None."""
    from core.nql import creation_build
    if creation_scope.open_choice_ids(intent):
        return None
    roll = _ability_roll(conversation)
    try:
        sheet, built = creation_build.build_level_one_sheet(
            intent, None, rolled=roll["rolled"] if roll else None, preview=True)
    except creation_build.BuildRefusal:
        return None   # the ability scores are not set yet: nothing to preview
    built["hit_points"] = expected_starting_hit_points(sheet, intent)[0]
    summary = creation_build.render_sheet_summary(sheet, built)
    previews = _scope_states(conversation, SHEET_PREVIEW_PURPOSE)
    if previews and previews[-1].get("summary") == summary:
        return None
    conversation.append({"role": "system", "content": json.dumps({
        "task_purpose": SHEET_PREVIEW_PURPOSE,
        "startup_id": (_startup_progress(conversation) or {}).get("startup_id"),
        "summary": summary, "untyped": built["untyped"],
        "instruction": ("The game showed the player this summary of the engine-built sheet after your "
                        "narration. It is the build the player approves; never restate it differently."),
    }, ensure_ascii=False)})
    return summary


def _append_scope(conversations, scope, intent):
    """Append a scope item and its state record to each list (the first is read for the current state)."""
    # The state record is its own typed item, never a checkpoint field: code before COST-4 skips it (r3.1,
    # CR-9). It keeps its COST-4 shape; sticky stays empty and an old one is ignored (COST-5 section 5).
    record = {"task_purpose": SCOPE_STATE_PURPOSE,
              "startup_id": (_startup_progress(conversations[0]) or {}).get("startup_id"),
              "scope_id": scope["scope_id"], "intent": intent, "sticky": {}}
    for conversation in conversations:
        conversation.append({"role": "system", "content": json.dumps(scope, ensure_ascii=False)})
        conversation.append({"role": "system", "content": json.dumps(record, ensure_ascii=False)})


class StartupScopeRefusal(ValueError):
    """A scoped response's picks the engine refuses (typed; no reviewer call)."""

    def __init__(self, problems, open_ids=None):
        self.problems = problems
        self.open_ids = open_ids or []
        super().__init__("choices outside the current scope" if problems
                         else "finalize with open choice ids")

    def record(self):
        return {"task_purpose": "startup_choice_refusal", "problems": self.problems,
                "open_choice_ids": self.open_ids,
                "instruction": ("Correct these picks from the current scope; a finalize needs every "
                                "issued choice id filled with its count. Refuse only an option the scope "
                                "does not offer, and ask only about open choice ids.")}


def _scoped_intent(conversations, proposal, rescoped, persist=None):
    """Apply the engine scope to a parsed scoped response (D-CREATE-COST-4 section 1, section 3).

    Picks the previous scope issued and the new intent's scope does not (a switch) are dropped
    into one typed startup_choices_dropped item. A changed scope is appended; returns True when
    T092 must be asked again for the same answer (at most once per response chain; a rejection starts a
    new chain). Picks outside the scope, and a finalize with open choice ids, raise StartupScopeRefusal.
    conversations are the turn's request base and its pending items: the saved history gets the items only
    when the turn publishes (r3.1, T4). The ability roll is the exception: persist saves it the moment it
    is made, so no handback or restart rolls again (amendment 1f, N7)."""
    intent = proposal["intent"]
    # Every id an earlier scope of this interview issued: a pick under one the new scope does not issue
    # is a switch's leftover (dropped), not a refusal.
    previous = set()
    for state in _scope_states(conversations[0]):
        previous.update(creation_scope.issued_points(state.get("intent")))
    issued = creation_scope.issued_points(intent)
    dropped = {cid: picks for cid, picks in (intent.get("choices") or {}).items()
               if cid in previous and cid not in issued}
    if dropped:
        intent["choices"] = {cid: picks for cid, picks in intent["choices"].items() if cid not in dropped}
        for conversation in conversations:
            conversation.append({"role": "system", "content": json.dumps({
                "task_purpose": "startup_choices_dropped", "dropped": dropped,
                "instruction": "These picks belong to an earlier choice; the current scope does not issue them.",
            }, ensure_ascii=False)})
    # #1368: the background package is recorded only in starting_equipment; the same pick mirrored under
    # background.<key>.starting-equipment (the class package's shape) is redundant and is dropped.
    mirror = "background.%s.starting-equipment" % intent.get("background_key")
    held = (proposal.get("starting_equipment") or {}).get("background_package")
    if held is not None and (intent.get("choices") or {}).get(mirror) == [held]:
        intent["choices"] = {cid: picks for cid, picks in intent["choices"].items() if cid != mirror}
    # A refused intent never becomes the scope: picks are checked before any scope is appended.
    problems = creation_scope.choice_problems(intent)
    if problems:
        raise StartupScopeRefusal(problems, [])
    ask_again = False
    if ((intent.get("ability_scores") or {}).get("method") == "random"
            and _ability_roll(conversations[0]) is None):
        # The engine rolls once, the first time the player's method is random; the author assigns the
        # rolled numbers and never invents its own (amendment 1f).
        from core.nql.creation_build import roll_ability_scores
        record = dict({"task_purpose": ABILITY_ROLL_PURPOSE,
                       "startup_id": (_startup_progress(conversations[0]) or {}).get("startup_id")},
                      **roll_ability_scores(),
                      instruction=("The engine rolled these six ability scores (four d6, highest three). Show them "
                                   "and assign them as the player wishes; they are never rolled again or replaced."))
        conversations[0].append({"role": "system", "content": json.dumps(record, ensure_ascii=False)})
        if persist is not None:
            persist(record)
        ask_again = True
    scope = creation_scope.creation_scope(intent)
    current = _creation_scope_current(conversations[0])
    if scope is not None and (current is None or current.get("scope_id") != scope["scope_id"]):
        _append_scope(conversations, scope, intent)
        ask_again = True
    if ask_again and not rescoped:
        return True
    open_ids = creation_scope.open_choice_ids(intent)
    # #1325: the narration's typed claims against the response's own intent; a correct turn costs no call.
    problems = creation_scope.turn_problems(intent, proposal["choice_turn"])
    if problems:
        raise StartupScopeRefusal(problems, open_ids)
    if proposal["decision"] == "finalize_character":
        if open_ids:
            raise StartupScopeRefusal([], open_ids)
        return False
    reported = _scope_states(conversations[0], OPEN_CHOICES_PURPOSE)
    if not reported or reported[-1].get("open_choice_ids") != open_ids:
        # Amendment 2: the engine reports what is still open, as typed ids (their options are in the scope).
        # The author asks the player for each, or picks itself only when the player delegates; never filled
        # silently, and never read from the player's words by code.
        record = {"task_purpose": OPEN_CHOICES_PURPOSE,
                  "startup_id": (_startup_progress(conversations[0]) or {}).get("startup_id"),
                  "open_choice_ids": open_ids,
                  "open_choices": creation_scope.open_choices(intent),
                  "instruction": ("Each open choice id is answered in intent from its options listed here: ask the player, "
                                  "or choose yourself only when the player asks you to choose. Finalize only when "
                                  "none are open.")}
        for conversation in conversations:
            conversation.append({"role": "system", "content": json.dumps(record, ensure_ascii=False)})
    return False


def _append_system_once(conversation, content):
    """Append a code-authored system message unless the identical one is already there (#1277).

    A resumed interview keeps the copy it has; a changed prompt or record is still appended.
    """
    if any(m.get("role") == "system" and m.get("content") == content for m in conversation):
        return
    conversation.append({"role": "system", "content": content})


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
    conversation.append({"role": "system", "content": json.dumps(record, ensure_ascii=False)})
    save_startup_conversation(conversation, live_scope=live_scope)
    return record


def _review_startup_response(conversation, proposal, committed_facts, *,
                             authored_proposal, normalization_provenance, live_scope,
                             attempts=None):
    """Return the parsed review; None once `attempts` reviews (when given) had invalid structure.

    Stable content first, one input item per interview message, so a provider's
    prompt cache can reuse the interview from the previous review; the turn's
    proposal is the last item (D-CREATE-COST-1). Each item is the message's own
    JSON, as the interview list carried it.
    """
    review_messages = [{"role": "system", "content": build_startup_review_prompt()}]
    review_messages += [{"role": "user", "content": json.dumps(message, ensure_ascii=False)}
                        for message in conversation]
    review_messages += [
        {"role": "user", "content": json.dumps({
            "task_purpose": "startup_semantic_review",
            "interview": {"messages": len(conversation),
                          "supplied_as": "the preceding items, one per interview message, in order"},
            "proposal": proposal,
            "authored_proposal": authored_proposal,
            "normalization_provenance": normalization_provenance,
            "latest_user_index": _latest_player_index(conversation),
            "committed_facts": committed_facts,
        }, ensure_ascii=False)},
    ]
    invalid = 0
    while True:
        raw = get_ai_response(review_messages, {"type": "json_object"},
                              persist_response=False, live_scope=live_scope,
                              startup_phase="startup_review", task_id="T124")
        try:
            return parse_startup_review(raw, decision=proposal.get("decision"))
        except ValueError as exc:
            invalid += 1
            if attempts is not None and invalid >= attempts:
                return None
            review_messages.append({"role": "system", "content": (
                f"The rejected review has invalid structure: {exc}. "
                "Return the complete corrected review object."
            )})


def _origin_key(name):
    """Typed name key: the whole name, trimmed and casefolded; no part is cut off (#855)."""
    return str(name or "").strip().casefold()


def _check_background_origin_feat(character, background_key):
    """A new character must list its background's Origin feat (SRD 5.2.1).

    The background record is the one the typed origin.background_key selects. The feat is matched by
    typed name equality. A missing reference file is not checked.
    """
    origins = safe_json_load(ORIGINS_FILE)
    if not isinstance(origins, dict):
        return
    entry = next((b for b in origins.get("backgrounds", []) if b.get("key") == background_key), None)
    if entry is None:
        return
    feat = entry["feat"]
    feats = character.get("feats") or []
    if any(isinstance(f, dict) and _origin_key(f.get("name")) == _origin_key(feat) for f in feats):
        return
    raise ValueError(
        f"The {entry['name']} background grants the Origin feat {feat} (SRD 5.2.1, startup_rules_reference); "
        f"the sheet's feats do not list it. Record it as the reference's sheet_representation says, keeping "
        f"the player's approved choices."
    )


def _schema_allows_null(prop):
    """True when a JSON-schema property admits null (or does not constrain the type)."""
    if not isinstance(prop, dict):
        return True
    branches = prop.get("anyOf", []) + prop.get("oneOf", [])
    if branches:
        return any(_schema_allows_null(branch) for branch in branches)
    if "enum" in prop:
        return None in prop["enum"]
    kind = prop.get("type")
    if kind is None:
        return True
    return kind == "null" or (isinstance(kind, list) and "null" in kind)


def _drop_schema_disallowed_nulls(character):
    """Drop optional top-level keys set to null where the frozen schema does not admit null.

    Keyed on the schema only (property type and required list), never on field names. A required key with
    null is kept, so validation still refuses it. Returns the drops for normalization provenance.
    """
    schema = safe_json_load("schemas/char_schema.json") or {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    dropped = []
    for key in list(character):
        if character[key] is not None or key in required or key not in properties:
            continue
        if _schema_allows_null(properties[key]):
            continue
        del character[key]
        dropped.append({"field": key, "supplied": None, "schema_type": properties[key].get("type"),
                        "reason": "optional property whose schema does not admit null; dropped by the game"})
    return character, dropped


def _control_character_correction(value, path="character"):
    """The correction for a sheet string holding a control character (Unicode
    category Cc other than newline, carriage return and tab), as a model writes
    when it spells a letter as a broken \\u escape (#874); None when there is none.
    Nothing is stripped: the author rewrites the value as the player gave it."""
    import unicodedata
    if isinstance(value, str):
        for ch in value:
            if ch not in "\n\r\t" and unicodedata.category(ch) == "Cc":
                return (f"{path} contains the control character U+{ord(ch):04X}; write every letter "
                        "as itself, not as a \\u escape, exactly as the player gave it.")
        return None
    if isinstance(value, dict):
        items = ((f"{path}.{key}", item) for key, item in value.items())
    elif isinstance(value, list):
        items = ((f"{path}[{index}]", item) for index, item in enumerate(value))
    else:
        return None
    for item_path, item in items:
        detail = _control_character_correction(item, item_path)
        if detail:
            return detail
    return None


def _write_origin_identity(character, origin):
    """Write the display class and background from the typed origin keys (D-KW-12): the class name from
    progression.json, the background name from its origins record. An authored value that differs is
    overwritten and noted (#532). Without readable origins data the background is left as written; the
    grant then reports the data unavailable."""
    from core.leveling import tables
    from core.nql.startup_rows import package_records
    classes = tables.tables()["classes"]
    if origin["class_key"] not in classes:
        raise ValueError(f"origin.class_key {origin['class_key']!r} is not a class key; one of "
                         f"{', '.join(sorted(classes))}")
    names = {"class": classes[origin["class_key"]]["name"]}
    records = package_records()
    if records is not None:
        if origin["background_key"] not in records.backgrounds:
            raise ValueError(f"origin.background_key {origin['background_key']!r} is not a background key; "
                             f"one of {', '.join(sorted(records.backgrounds))}")
        names["background"] = records.backgrounds[origin["background_key"]]["name"]
    notes = []
    for field, name in names.items():
        if character.get(field) != name:
            notes.append(f"{field} {character.get(field)!r} -> {name!r} (written from origin.{field}_key)")
            character[field] = name
    return notes


def _zero_authored_gear(character):
    """Set the authored purse and gear aside: the grant writes them from the packages. Returns the
    authored values for provenance. Authored melee and ranged attack rows go too (the engine writes the
    weapon rows); spell rows stay."""
    attacks = character.get("attacksAndSpellcasting")
    weapon = lambda row: isinstance(row, dict) and row.get("type") in ("melee", "ranged")
    authored = copy.deepcopy({
        "currency": character.get("currency"), "equipment": character.get("equipment"),
        "ammunition": character.get("ammunition"), "equipment_effects": character.get("equipment_effects"),
        "attacksAndSpellcasting": [row for row in attacks if weapon(row)] if isinstance(attacks, list) else attacks,
    })
    character["currency"] = {"gold": 0, "silver": 0, "copper": 0}
    character["equipment"] = []
    character["ammunition"] = []
    character["equipment_effects"] = []
    if isinstance(attacks, list):
        character["attacksAndSpellcasting"] = [row for row in attacks if not weapon(row)]
    return authored


# D-PKG-5 (#193 Part 5): at character creation a second consecutive engine
# timeout (the fixed apply.DEFAULT_TIMEOUT_SECONDS deadline) of one engine call
# saves the character without gear; "file in use" keeps waiting.
STARTUP_ENGINE_TIMEOUT_LIMIT = 2
STARTUP_ENGINE_WAIT_TEXT = ("Still adding your starting gear; your choices are kept. Stop the game "
                            "(close its window or launcher); setup resumes where it left off.")


def _startup_engine_fault(fault, scope, call, timeouts):
    """The creation-time rule for one engine fault of ``call``: None after the busy-engine wait, when the
    caller reissues that call; otherwise the end-state (d) record for provenance["starting_packages"].
    ``timeouts`` holds the consecutive timeouts per call ("grant", "attack_rows") of one proposal.

    Classified by the fault's type: an EngineUnavailable whose cause is an OSError the shared transient
    classifier accepts waits; a timeout waits once (D-PKG-5); every other EngineUnavailable, a refusal
    and unreadable package data are (d). The wait is not a rejection.
    """
    import subprocess
    from core.nql import apply
    from utils.transient_filesystem import is_transient_filesystem_error
    record = {"status": "engine_unavailable", "policy": "D-PKG-1", "phase": call, "exit": None}
    if isinstance(fault, apply.EngineUnavailable):
        warning(f"Startup rules engine fault at {call}: {fault}", category="startup")
        cause = fault.__cause__
        if isinstance(cause, subprocess.TimeoutExpired):
            timeouts[call] = timeouts.get(call, 0) + 1
            if timeouts[call] >= STARTUP_ENGINE_TIMEOUT_LIMIT:
                return dict(record, cause="timeout")
        elif isinstance(cause, OSError) and is_transient_filesystem_error(cause):
            timeouts[call] = 0
        else:
            return dict(record, cause="unavailable")
    elif fault == ("data_unavailable", "grant"):
        warning("Startup package data unavailable; the character is saved without starting gear", category="startup")
        return dict(record, status="data_unavailable", cause="data_unavailable")
    else:
        warning(f"Startup rules engine refused {call} at phase {fault[1]}", category="startup")
        return dict(record, cause="refused")
    from utils.capture.live_provider_call import _interruptible_wait, drain_live_saves
    if scope is not None:
        # A completed boundary can service Save without ending the build.
        drain_live_saves(scope)
    _interruptible_wait(1.0, scope, STARTUP_ENGINE_WAIT_TEXT + ("" if web_mode else " Or press Ctrl+C to pause."),
                        display_status)
    return None


def _engine_built_character(proposal, rolled):
    """The engine-built level-1 sheet for a finalize's typed intent and creative fields (D-CREATE-COST-5),
    and its provenance; an engine refusal is a typed rejection of the turn (amendment 1e)."""
    from core.nql import creation_build
    try:
        sheet, built = creation_build.build_level_one_sheet(proposal["intent"], proposal["creative"],
                                                           rolled=rolled)
    except creation_build.BuildRefusal as exc:
        raise ValueError("The engine cannot build this character from intent: %s"
                         % json.dumps(exc.problems, ensure_ascii=False)) from None
    origin = {"class_key": proposal["intent"]["class_key"], "background_key": proposal["intent"]["background_key"]}
    return sheet, origin, built


def _prepare_startup_proposal(authored_proposal, *, live_scope=None, rolled=None):
    """Normalize a private copy; keep authorship distinct from engine output.

    A new character's class and background are written from its typed origin, its authored purse and
    gear are set aside, and its starting gold and gear come from one engine grant of the typed package
    picks (D-KW-16). A busy engine is waited for under ``live_scope`` and the call reissued; an engine
    that cannot run saves the character without gear (end state (d), D-PKG-1).
    """
    from core.nql import item_catalog, startup_rows
    proposal = copy.deepcopy(authored_proposal)
    provenance = {}
    if proposal["decision"] != "finalize_character":
        return proposal, provenance
    if "creative" in proposal:
        # Amendment 2: every package and slot the scope needs is in starting_equipment before the build.
        scope = creation_scope.creation_scope(proposal["intent"]) or {}
        open_gear = [entry["id"] for entry in creation_scope.unanswered_required(
            scope, proposal["intent"], proposal["starting_equipment"]) if entry["id"].startswith("starting_equipment.")]
        if open_gear:
            raise ValueError("Finalization requires every package and slot pick in starting_equipment: missing "
                             + ", ".join(open_gear))
        proposal["character"], proposal["origin"], provenance["engine_build"] = _engine_built_character(
            proposal, rolled)
    from utils.encoding_utils import sanitize_dict
    # The loader's own form (#1288): the name is checked as it will read back.
    character = sanitize_dict(sanitize_character_data(proposal["character"]))
    from updates.update_character_info import name_refusal
    detail = name_refusal(character.get("name"))
    if detail:
        raise ValueError(f"The character name cannot be used: {detail}. Choose another name.")
    detail = _control_character_correction(character)
    if detail:
        raise ValueError(detail)
    identity_notes = _write_origin_identity(character, proposal["origin"])
    authored_gear = _zero_authored_gear(character)
    character, dropped = _drop_schema_disallowed_nulls(character)
    if dropped:
        provenance["schema_null_drops"] = dropped
    character, _ = repair_required_ammunition_field(character)
    character, _ = repair_startup_character_sheet(character)
    character = auto_fix_character_data(character)
    valid, detail = validate_character_with_recovery(character, mechanics=False)
    if not valid:
        raise ValueError(detail)
    zeroed = copy.deepcopy(character)
    timeouts = {}
    unavailable = None
    while True:
        faults = []
        granted, grant = startup_rows.grant_starting_packages(character, proposal["origin"],
                                                              proposal["starting_equipment"], faults)
        if not faults:
            character = granted
            break
        unavailable = _startup_engine_fault(faults[0], live_scope, "grant", timeouts)
        if unavailable is not None:
            break
    # The step-7 rule applies only after an applied grant; a (d) at the grant keeps main's fallbacks.
    faults = [] if unavailable is None else None
    # #1280 / B1: the interview passes its typed intent (an empty one when the path has none), never race.
    intent = proposal.get("intent") if isinstance(proposal.get("intent"), dict) else {}
    character, mechanics = startup_mechanics(character, provenance=provenance, faults=faults, intent=intent)
    while faults:
        # The step-7 rule: a busy engine reissues only the rows step, on the projected sheet.
        outcome = _startup_engine_fault(faults.pop(), live_scope, "attack_rows", timeouts)
        if outcome is None:
            rows = provenance["engine_rows"]
            _startup_attack_rows(character, character.get("name", "Unknown"), rows["typed_equipment"],
                                 rows["untyped_equipment"], provenance, faults)
        elif unavailable is None:
            unavailable = outcome
    if (unavailable is None and provenance["engine_rows"]["item_rows"] is not True
            and any((item_catalog.entry(row.get("catalog_id")) or {}).get("kind") == "weapon"
                    for row in character.get("equipment") or [])):
        # The older-engine resend (startup_rows.attack_rows): granted weapons with no engine rows.
        unavailable = _startup_engine_fault(("refused", "attack_rows"), live_scope, "attack_rows", timeouts)
    if unavailable is not None and granted is not None:
        # (d) after a successful grant: the character is rebuilt from the zeroed sheet, once, with no
        # engine fault rule, so no sheet commits granted gear without engine rows.
        display_status("Finishing your character without starting gear.")
        character, mechanics = startup_mechanics(copy.deepcopy(zeroed), provenance=provenance, intent=intent)
    provenance["starting_packages"] = dict(unavailable or dict(grant, status="applied"), authored=authored_gear)
    provenance["mechanics_notes"] = identity_notes + mechanics
    # Equipment checks read the sheet as the engine left it; armorClass is the
    # engine's projection above (#531), not derived again here.
    from utils.startup_mechanics import validate_startup_mechanics
    valid, detail = validate_startup_mechanics(character)
    if not valid:
        raise ValueError(detail)
    detail = _fighting_style_correction(character)
    if detail:
        raise ValueError(detail)
    detail = _order_choice_correction(character)
    if detail:
        raise ValueError(detail)
    # Engine text too (#1288): what is saved reads back equal (read-back, ready check, resume).
    character = sanitize_dict(character)
    try:
        validate(character, safe_json_load("schemas/char_schema.json"))
    except ValidationError as exc:
        raise ValueError(exc.message) from exc
    _check_background_origin_feat(character, proposal["origin"]["background_key"])
    proposal["character"] = character
    return proposal, provenance


def _starting_gear_facts(proposal, provenance):
    """The reviewer's committed facts for a finalize: the typed picks and what the engine made of them."""
    from core.leveling import tables
    packages = provenance["starting_packages"]
    character = proposal["character"]
    projection = provenance.get("engine_projection") or {}
    result = {"status": packages["status"],
              # Unchecked when the projection did not apply: the authored armorClass stands (D-PKG-7).
              "armor_class": character.get("armorClass") if projection.get("applied") else "unchecked"}
    if packages["status"] == "applied":
        background, cls = packages["background"], packages["class"]
        class_name = tables.tables()["classes"][cls["key"]]["name"]
        result["engine_result"] = (f"gold {packages['currency']['gold']} = {background['name']} "
                                   f"{background['package']} {background['gp']} + {class_name} {cls['package']} {cls['gp']}")
        result["rows"] = ([f"{r.get('item_name')} x{r.get('quantity')}" for r in character.get("equipment") or []]
                          + [f"{r.get('name')} x{r.get('quantity')} (ammunition)" for r in character.get("ammunition") or []])
        result["equipped"] = [r.get("item_name") for r in character.get("equipment") or [] if r.get("equipped") is True]
    else:
        result["policy"] = packages["policy"]
    return {"origin": proposal["origin"], "starting_equipment": proposal["starting_equipment"],
            "starting_packages": result}


def _starting_gear_notice(character, provenance):
    """The plain notice for a character saved without starting gear (end state (d)), or None."""
    from core.nql import apply
    packages = provenance.get("starting_packages") or {}
    name, binary = character.get("name"), apply.binary_path()
    moves = (f"To play with them, make sure {binary} runs on this computer, reset the campaign, and "
             f"create the character again; otherwise you can play on without them.")
    if packages.get("status") == "data_unavailable":
        return (f"The game's rules data could not be read, so {name} starts with no gold, no starting gear "
                f"and no weapons. Reinstalling the game restores it; reset the campaign and create the "
                f"character again, or play on without them.")
    if packages.get("status") != "engine_unavailable":
        return None
    if packages.get("cause") == "refused":
        return (f"The rules engine refused the starting gear, so {name} starts with no gold, no starting gear "
                f"and no weapons. You can play on without them, or reset the campaign and create the "
                f"character again.")
    if packages.get("cause") == "timeout":
        return (f"The rules engine did not answer in time, so {name} starts with no gold, no starting gear "
                f"and no weapons. {moves}")
    return (f"The rules engine could not run, so {name} starts with no gold, no starting gear and no "
            f"weapons. {moves}")


# Rejected proposals (invalid structure or review rejection) one player turn may
# cost before the turn is handed back to the player; a review that cannot return
# a valid verdict within the remaining budget also hands the turn back. Not
# persisted: a restart replays the turn with a fresh count.
STARTUP_TURN_REJECTION_LIMIT = 4
# T093 starting-location proposals that complete but don't resolve (D-1270-1,
# a B2-iv class matching the limit above); provider errors don't count. After
# this many in a row the party starts at the plot's starting area (D-1270-2).
STARTUP_LOCATION_REJECTION_LIMIT = 4
STARTUP_HANDBACK_NOTICE = (
    "I could not finish that build yet. Your choices so far "
    "are kept and no character has been saved. Tell me what to adjust, or say "
    "continue and I will try again."
)


def ai_character_interview(conversation, module):
    """One agent-authored, independently reviewed startup turn at a time."""
    from utils.capture.live_provider_call import (
        LiveProviderSuperseded, open_live_turn_scope, finish_live_turn_scope,
    )

    # D-CREATE-COST-5 (Q1 option 1, amendment 1c): one creation path. The engine builds the sheet from the
    # typed intent; an interview begun before this continues here and re-asks the typed intent it lacks
    # (never derived from old prose). STARTUP_REVIEW_MODE selects only the review.
    scoped = True
    _append_system_once(conversation, build_character_creation_system_prompt(scoped=scoped))
    _append_system_once(conversation, json.dumps({
        "task_purpose": "startup_character_interview",
        "selected_adventure": module,
        "instruction": "Continue the actual interview or begin with an identity question. "
                       "Old history is context, not proof of approval or saved state. "
                       "Follow the current startup response contract.",
    }, ensure_ascii=False))
    if _creation_scope_current(conversation) is None:
        menu = creation_scope.creation_scope({})
        if menu is not None:
            _append_scope([conversation], menu, None)
        else:
            warning("Startup creation scope unavailable; the interview continues without it", category="startup")
    _say("\nDungeon Master: Let's build your character together.", flush=True)  # #1422 F1
    while True:
        scope = open_live_turn_scope()
        try:
            save_startup_conversation(conversation, live_scope=scope)
            correction_context = copy.deepcopy(conversation)
            rejected = 0
            rescoped = False  # one re-scope per T092 response chain (r3 section 3.2)
            turn_items = []  # scope, state and drop items made this turn; saved only when it publishes (T4)
            while True:
                if rejected >= STARTUP_TURN_REJECTION_LIMIT:
                    # Fail forward: hand the turn back unpublished; nothing is approved or saved.
                    if scope.is_superseded():
                        raise LiveProviderSuperseded("startup review superseded")
                    conversation.append({"role": "system", "content": json.dumps({
                        "task_purpose": "startup_turn_handback",
                        "rejected_outputs": rejected,
                        "notice_shown_to_player": STARTUP_HANDBACK_NOTICE,
                        "instruction": ("No proposal for the player's previous message was published or "
                                        "approved. Answer the player's next message with the retained choices."),
                    }, ensure_ascii=False)})
                    save_startup_conversation(conversation, live_scope=scope)
                    _say(f"\nDungeon Master: {STARTUP_HANDBACK_NOTICE}")
                    break
                current_index = _latest_player_index(conversation)
                facts = {
                    "selected_module": module["name"],
                    "phase": (_startup_progress(conversation) or {}).get("phase", "interview"),
                    "character_saved": False, "adventure_ready": False,
                }
                request = correction_context + [{"role": "system", "content": json.dumps({
                    "latest_user_index": current_index, "committed_facts": facts,
                    "instruction": "Return the complete startup response object, not a bare sheet.",
                }, ensure_ascii=False)}]
                raw = get_ai_response(request, {"type": "json_object"},
                                      persist_response=False, live_scope=scope)
                try:
                    authored_proposal = copy.deepcopy(
                        parse_startup_response(raw, latest_user_index=current_index, scoped=scoped))
                    if scoped:
                        if _scoped_intent([correction_context, turn_items], authored_proposal, rescoped,
                                          persist=lambda record: _persist_system_record(conversation, record, scope)):
                            rescoped = True
                            continue
                    if (authored_proposal["decision"] == "pause_setup"
                            and current_index in _paused_player_indexes(conversation)):
                        raise ValueError("That request to stop was already honored; the player is "
                                         "back, so continue the interview")
                    roll = _ability_roll(correction_context)
                    proposal, provenance = _prepare_startup_proposal(
                        authored_proposal, live_scope=scope, rolled=roll["rolled"] if roll else None)
                    if proposal["decision"] == "finalize_character":
                        facts.update(_starting_gear_facts(proposal, provenance))
                        mechanics = provenance["mechanics_notes"]
                        if mechanics:
                            facts["startup_mechanics"] = {
                                "status": "already applied by the game to the candidate sheet under review",
                                "meaning": ("These normalization notes describe the candidate, not author requirements "
                                            "or player approval. Check narration against the candidate and still reject "
                                            "unsupported mechanics or lost choices."),
                                "changes": mechanics,
                            }
                    # The mode selects only the review, read on every turn (Q1 option 1). D-ALLCLASS-4: the engine
                    # path has no model review; the engine is the only gate (creation_build refusals,
                    # unanswered_required, the typed schema), and its refusals reach the author as ValueError.
                    if _startup_review_mode() == "engine":
                        review = {"accepted": True}
                    else:
                        # #1278's review over the engine-built sheet, against the reference a scoped history lacks.
                        review_request = copy.deepcopy(request)
                        _append_startup_rules_reference(review_request)
                        review = _review_startup_response(
                            review_request, proposal, facts, authored_proposal=authored_proposal,
                            normalization_provenance=provenance, live_scope=scope,
                            attempts=STARTUP_TURN_REJECTION_LIMIT - rejected)
                except StartupScopeRefusal as exc:
                    rejected += 1
                    rescoped = False
                    correction_context.append({"role": "system", "content": json.dumps(
                        dict(exc.record(), rejected_response=raw), ensure_ascii=False)})
                    continue
                except ValueError as exc:
                    rejected += 1
                    rescoped = False
                    correction_context.append({"role": "system", "content": (
                        f"Rejected startup proposal (not approved): {exc}. "
                        f"Correct this response using the retained player choices: {raw}"
                    )})
                    continue
                if review is None:
                    # No valid review within the turn's remaining budget.
                    rejected = STARTUP_TURN_REJECTION_LIMIT
                    continue
                if not review["accepted"]:
                    rejected += 1
                    rescoped = False
                    correction_context.append({"role": "system", "content": json.dumps({
                        "rejected_proposal": authored_proposal,
                        "canonical_candidate": proposal,
                        "normalization_provenance": provenance,
                        "review_feedback": review["feedback"],
                        "needs_player_clarification": review["needs_player_clarification"],
                        "instruction": ("Propose a continue_interview question; do not finalize."
                                        if review["needs_player_clarification"]
                                        else "Correct the proposal without inventing a new player choice."),
                    }, ensure_ascii=False)})
                    continue
                if scope.is_superseded():
                    raise LiveProviderSuperseded("startup review superseded")
                conversation.extend(turn_items)
                conversation.append({"role": "assistant", "content": json.dumps(proposal, ensure_ascii=False)})
                summary = None
                if proposal["decision"] == "finalize_character" and "engine_build" in provenance:
                    # Written before the approved checkpoint and the archive move, so it survives handoff.
                    conversation.append({"role": "system", "content": json.dumps(dict(
                        {"task_purpose": ENGINE_BUILD_PURPOSE,
                         "startup_id": (_startup_progress(conversation) or {}).get("startup_id")},
                        **provenance["engine_build"]), ensure_ascii=False)})
                elif proposal["decision"] == "continue_interview" and scoped:
                    summary = _sheet_preview(conversation, proposal["intent"])
                if proposal["decision"] == "finalize_character":
                    notice = _starting_gear_notice(proposal["character"], provenance)
                    if notice:
                        # Shown once, before the approved checkpoint: a restart after it loses nothing.
                        _say(f"\nDungeon Master: {notice}", flush=True)  # #1422 F1
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
                    # #1422 F5: the reply to the player's approval, shown only once
                    # the build is saved (a name conflict above continues instead).
                    if isinstance(proposal.get("narration"), str) and proposal["narration"].strip():
                        _say(f"\nDungeon Master: {proposal['narration']}", flush=True)
                    return proposal["character"]
                _set_startup_progress(conversation, live_scope=scope, phase="interview")
                _say(f"\nDungeon Master: {proposal['narration']}")
                if summary:
                    _say(f"\n{summary}")
                if proposal["decision"] == "pause_setup":
                    # The reviewed typed decision, never the player's words (#855).
                    raise StartupCancelled()
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
            raise StartupCancelled() from None
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
            "\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C"  # other emoji
            "\u2B50\u2B55\u3030\u303D\u3297\u3299\U0001F004\U0001F0CF\U0001F170-\U0001F251"  # enclosed
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


def _level_one_hit_die(class_name):
    """The class's level-1 hit point base (its hit die maximum) from the SRD
    progression tables, data/srd/progression.json; None for an unknown class."""
    from core.leveling import tables
    entry = (tables.tables().get("classes") or {}).get(str(class_name).strip().casefold())
    value = entry.get("hp_at_first_level_base") if isinstance(entry, dict) else None
    return value if type(value) is int and value > 0 else None


from core.leveling import fighting_style as _fighting_style
_fighting_style_texts = _fighting_style.style_texts
_fighting_styles_allowed = _fighting_style.styles_allowed


def _canonicalize_fighting_style(character, provenance=None):
    return _fighting_style.canonicalize(character, provenance,
                                        source="utils.startup_wizard._canonicalize_fighting_style")


def _fighting_style_correction(character):
    """The correction for an interview sheet that records fewer Fighting Styles
    than its class has gained by its level, counted by the exact classFeatures
    name level-up writes ("Fighting Style: <name>"), the only one the engine
    grants; None when the count is met or the SRD style list is unavailable.
    The author keeps the player's choice or asks for it (#855)."""
    styles = _fighting_style_texts()
    allowed = _fighting_styles_allowed(character.get("class"), character.get("level"))
    if allowed < 1 or not styles:
        return None
    exact = {f"Fighting Style: {name}" for name, _ in styles.values()}
    recorded = sum(1 for entry in character.get("classFeatures") or []
                   if isinstance(entry, dict) and entry.get("name") in exact)
    if recorded >= allowed:
        return None
    names = ", ".join(sorted(name for name, _ in styles.values()))
    return (f"{character.get('class')} level {character.get('level')} has {allowed} Fighting "
            f"Style and the sheet records {recorded}. Keep the player's choice and record it "
            f"as one classFeatures entry named exactly \"Fighting Style: <name>\", with <name> "
            f"one of: {names}. If the player has not chosen one, ask them.")


def _apply_order_grants(character, provenance=None):
    """Write the proficiencies a recorded class order grants (#888; the rule is
    core.leveling.choices.apply_order_grants, shared with the startup repair of
    saved sheets) and record them in the provenance. Matched by the exact
    classFeatures name only; an order recorded another way is sent back by
    _order_choice_correction, not guessed."""
    from core.leveling import choices
    notes = []
    applied = []
    for entry in choices.apply_order_grants(character):
        notes.append(f"{entry['feature']} grants {entry['printed']} (SRD 5.2.1 p.{entry['page']}); "
                     + (f"added {', '.join(entry['added'])}" if entry["added"] else "already present"))
        applied.append({"feature": entry["feature"], "added": entry["added"]})
    if applied and provenance is not None:
        provenance["order_grants"] = {
            "source": "utils.startup_wizard._apply_order_grants", "applied": applied,
            "policy": ("A class order's typed grants (choices.json option_grants) are written in the engine's "
                       "short labels for the exact classFeatures name; present labels are kept."),
        }
    return notes


def _order_choice_correction(character):
    """The correction for an interview sheet whose class has a typed order choice
    (Divine Order, Primal Order) at its level but does not record exactly one by
    its exact classFeatures name; None otherwise (#888, refused and corrected as
    #870's Fighting Style). The choice point comes from choices.json by class and
    level, never from text in the sheet."""
    from core.leveling import choices
    for point in choices.order_choice_points(character):
        chosen = choices.order_options_recorded(character, point)
        count = choices.order_choice_count(point)
        if len(chosen) == count:
            continue
        options = ", ".join(point["option_source"])
        return (f"{character.get('class')} level {character.get('level')} has {point['name']} and the sheet "
                f"records {len(chosen)} by its exact name (the class chooses {count}). Keep the player's choice "
                f"and record it as one classFeatures entry named exactly \"{point['name']}: <option>\", with "
                f"<option> one of: {options}. If the player has not chosen one, ask them.")
    return None


def _usage_text(usage):
    """A use pool's usage for a mechanics note, e.g. "2/2 shortRest (a Short Rest regains 1)"."""
    if not isinstance(usage, dict):
        return repr(usage)
    text = f"{usage.get('current')}/{usage.get('max')} {usage.get('refreshOn')}"
    if usage.get("shortRestRegain") is not None:
        text += f" (a Short Rest regains {usage['shortRestRegain']})"
    return text


def _level_one_pools_and_slots(character, provenance=None):
    """A new level-1 character's feature use pools and spell slots from the SRD
    progression tables, data/srd/progression.json use_pools and spell or pact
    slots (#704). Each pool the class has at level 1 is set full on the
    classFeatures entry that names it (the name before any parenthesis, as
    level-up matches pools); a pool whose feature the sheet does
    not list is noted for the reviewer, not invented. Spell slots are set
    exactly to the class's level-1 slots. A sheet that is not level 1 or not an
    SRD class is unchanged."""
    from core.leveling import tables
    notes = []
    if not isinstance(character, dict) or character.get("level") != 1:
        return notes
    cls = tables.class_key(character)
    if cls is None:
        return notes
    pools = tables.use_pools_at(cls, 1, character.get("abilities"))
    slots = tables.slot_maxima(cls, 1)
    record = {
        "source": "utils.startup_wizard._level_one_pools_and_slots",
        "tables": "data/srd/progression.json use_pools, spell_slots_by_level, pact_slots_by_level",
        "pools": {}, "slots": {level: n for level, n in slots.items() if n}, "missing_features": [],
        "policy": ("Level-1 pools set full on the classFeatures entry that names them; spell slots set "
                   "exactly to the class table; a missing pool feature is noted, not invented."),
    }
    if provenance is not None:
        provenance["use_pools"] = record
    features = character.get("classFeatures") if isinstance(character.get("classFeatures"), list) else []
    for name, pool in pools.items():
        entry = tables.pool_feature(features, name)
        if entry is None:
            record["missing_features"].append(name)
            notes.append(f"{name}: no classFeatures entry of that name; its level-1 use pool "
                         f"({_usage_text(pool.usage())}) is not set")
            continue
        usage = pool.usage()
        record["pools"][entry["name"]] = usage
        if entry.get("usage") != usage:
            notes.append(f"{entry['name']} usage {_usage_text(entry.get('usage'))} -> {_usage_text(usage)} "
                         "(SRD level 1)")
            entry["usage"] = usage
    casting = character.get("spellcasting")
    if not isinstance(casting, dict):
        if record["slots"]:
            notes.append(f"{character.get('class')} level 1 has spell slots {record['slots']}, but the sheet "
                         "has no spellcasting object; slots not set")
        return notes
    current = casting.get("spellSlots") if isinstance(casting.get("spellSlots"), dict) else {}
    # A slot level the sheet does not list counts as none; only a listed level
    # that differs, or a level the table grants, is written.
    target = {level: {"current": n, "max": n} for level, n in slots.items()
              if n or (level in current and current[level] != {"current": 0, "max": 0})}
    changed = [f"{level} {(current.get(level) or {}).get('current', 0)}/{(current.get(level) or {}).get('max', 0)}"
               f" -> {slot['max']}/{slot['max']}" for level, slot in target.items() if current.get(level) != slot]
    if changed:
        casting["spellSlots"] = dict(current, **target)
        notes.append(f"spellSlots {', '.join(changed)} (SRD level 1)")
    return notes



def _normalize_shield_defense(item):
    """A shield's defense is ac_base + ac_bonus (core.nql.genesis). The SRD shield
    is base 2 with no bonus; only a magical shield carries one (#531)."""
    base = item.get("ac_base")
    bonus = item.get("ac_bonus")
    base = base if type(base) is int else 0
    bonus = bonus if type(bonus) is int else 0
    if base < 2:
        # The draft wrote the shield's total as its bonus (base 0 / bonus 2):
        # fold the stated total into base 2 plus whatever remains.
        item["ac_base"] = 2
        item["ac_bonus"] = max(0, base + bonus - 2)
    elif bonus > 0 and item.get("magical") is not True:
        item["ac_bonus"] = 0


def _species_hit_point_bonuses(character, intent=None):
    """The level-1 hit point bonuses a species trait grants, from the SRD
    progression tables' hp_bonuses (data/srd/progression.json): each entry of
    kind "species trait" whose species_key is the character's typed species
    (choices.species_key_for: the creation intent's, or EXC-COST5-1 on a
    supplied sheet), at per_character_level (expected_starting_hit_points runs
    only for a level-1 sheet, so the bonus is that value; never multiplied by
    the authored level, which the schema lets be 1.0). Without a typed species
    no bonus applies; racialTraits names are display only and never read
    here (B1, nql-c0 S2). [(name, bonus)]."""
    from core.leveling import tables, choices as leveling_choices
    key, _ = leveling_choices.species_key_for(character, intent)
    if key is None:
        return []
    out = []
    for entry in tables.tables().get("hp_bonuses") or []:
        if not isinstance(entry, dict):
            continue
        granted = entry.get("granted_by") if isinstance(entry.get("granted_by"), dict) else {}
        per_level = entry.get("per_character_level")
        name = str(entry.get("name", "")).strip()
        if granted.get("kind") != "species trait" or type(per_level) is not int or not name:
            continue
        if granted.get("species_key") == key:
            out.append((name, per_level))
    return out


def expected_starting_hit_points(character, intent=None):
    """SRD 5.2.1 level-1 hit point maximum from the sheet's typed facts, with
    the terms that make it up: the class's hit die maximum from the progression
    tables, the Constitution modifier and Dwarven Toughness (minimum 1). SRD 5.2.1
    has no Tough feat, so a feats entry adds nothing. (None, []) when the sheet
    is not level 1 or its class or Constitution is unknown."""
    if not isinstance(character, dict) or character.get("level") != 1:
        return None, []
    class_name = str(character.get("class", "")).strip()
    die = _level_one_hit_die(class_name)
    abilities = character.get("abilities") if isinstance(character.get("abilities"), dict) else {}
    con = abilities.get("constitution")
    if die is None or type(con) is not int:
        return None, []
    con_mod = (con - 10) // 2
    terms = [f"{class_name} d{die} maximum {die}", f"Constitution {con} ({con_mod:+d})"]
    expected = die + con_mod
    for name, bonus in _species_hit_point_bonuses(character, intent):
        expected += bonus
        terms.append(f"{name} (+{bonus})")
    return max(1, expected), terms


def _apply_species_resistances(character, intent, provenance):
    """#1280: the species' damage resistances from the typed table, added to the sheet (never removing an
    entry). With the creation intent, its picked options count (Draconic Ancestry, Fiendish Legacy); without
    one (a supplied sheet), the canonical species named by race grants its unconditional ones. A live
    interview always passes its intent, so race is never read there."""
    from core.leveling import choices as leveling_choices
    notes = []
    applied = leveling_choices.apply_species_resistances(character, intent)
    for entry in applied:
        if entry["added"]:
            notes.append(f"damageResistances + {', '.join(entry['added'])} (Resistance from {entry['source']})")
    if provenance is not None and applied:
        provenance["species_resistances"] = {"source": "core.leveling.choices.apply_species_resistances",
                                             "grants": copy.deepcopy([e for e in applied if not e.get("untyped")])}
        gaps = [e["untyped"] for e in applied if e.get("untyped")]
        if gaps:
            provenance["species_resistances"]["untyped"] = gaps
    return notes


def startup_mechanics(character, *, provenance=None, faults=None, intent=None):
    """Derive a new character's engine-owned and SRD-derived numbers.

    The level-1 hit point maximum is set exactly to the SRD derivation from
    typed facts: hit die maximum, Constitution, Dwarven Toughness (#532, #570).
    An authored value that differs is overwritten and noted, and current hit
    points start at that maximum. It is set before the engine projection, so
    the projection's status carries the committed maximum (#696). A chosen
    Fighting Style is then recorded as level-up writes it, one classFeatures
    entry "Fighting Style: <name>", so the projection sees it (#569), and its
    level-1 use pools and spell slots come from the class tables (#704). Armor class
    comes from the engine's defense explanation, the same projection every
    later write applies (#531).
    Returns the sheet and the notes of what changed (also logged), which the
    startup reviewer receives as committed facts. When provenance is supplied,
    retain successful projection output even if these scalar notes are empty.
    """
    notes = []
    if not isinstance(character, dict):
        return character, notes
    name = character.get("name", "Unknown")
    expected, terms = expected_starting_hit_points(character, intent)
    if provenance is not None and expected is not None:
        provenance["hit_points"] = {
            "source": "utils.startup_wizard.expected_starting_hit_points",
            "expected_maximum": expected, "terms": terms,
            "policy": "Set exactly to the SRD level-1 derivation; a differing authored value is overwritten and noted.",
        }
    if expected is not None:
        breakdown = " + ".join(terms)
        current_max = character.get("maxHitPoints")
        current = character.get("hitPoints")
        if current_max != expected:
            notes.append(f"maxHitPoints {current_max} -> {expected} (SRD level 1: {breakdown})")
        if current != expected:
            notes.append(f"hitPoints {current} -> {expected} (a new level-1 hero starts at its maximum)")
        character["maxHitPoints"] = expected
        character["hitPoints"] = expected
    notes.extend(_canonicalize_fighting_style(character, provenance))
    notes.extend(_apply_order_grants(character, provenance))
    notes.extend(_apply_species_resistances(character, intent, provenance))
    notes.extend(_level_one_pools_and_slots(character, provenance))
    from core.nql.resources import add_feat_usage as _add_feat_usage
    for _feat in _add_feat_usage(character):
        # #891: a feat with its own use (Magic Initiate) starts full.
        notes.append(f"{_feat} usage set full (SRD 5.2.1 feat use)")
    from core.nql import armor_class, startup_rows, stats
    # NUM-H3c: exact-name catalog rows (HQ4), then the hand rule's carried rows
    # unequipped, before the projection reads the equipment.
    typed, untyped = startup_rows.type_catalog_rows(character, filled=notes)
    notes.extend(startup_rows.release_carried(character, armor_class.PROJECTION_LOCATION))
    projection = armor_class.project(character)
    if provenance is not None:
        provenance["engine_projection"] = {
            "source": "core.nql.armor_class.project",
            "applied": projection.applied and not projection.gaps,
            "reason": _reason_first_line(projection.reason),
            "gaps": copy.deepcopy(projection.gaps),
        }
    if projection.applied and projection.gaps:
        # Equipment the engine could not model (an equipped armor without
        # ac_base, an unknown category): the written armorClass stands until
        # the first later write types the entries and projects (T051).
        warning(f"[Startup Mechanics] {name}: armorClass left as written: {projection.gaps}",
                category="character_validation")
    elif projection.applied:
        if provenance is not None:
            # Successful projection writes these even when AC/HP do not change.
            # Preserve the actual engine status, not an author-provided claim.
            provenance["engine_projection"].update({
                "armorClass": projection.armor_class,
                "equipment_effects": {
                    "selector": {"target": armor_class.AC_TARGET},
                    "entries": copy.deepcopy([
                        e for e in projection.sheet.get("equipment_effects") or []
                        if isinstance(e, dict) and e.get("target") == armor_class.AC_TARGET
                    ]),
                },
                "status": copy.deepcopy(projection.status),
                # The engine's own derived fields on the projected sheet (#682): the
                # engine writes them, so they are never an author change.
                "engine_owned_fields": [f for f in stats.DERIVED_FIELDS if f in projection.sheet],
            })
        if projection.changed:
            parts = [f"{e.get('source')} {e.get('value'):+d}" if e.get("type") == "bonus" else f"{e.get('source')} {e.get('value')}"
                     for e in projection.sheet.get("equipment_effects") or []
                     if isinstance(e, dict) and e.get("target") == armor_class.AC_TARGET and type(e.get("value")) is int]
            notes.append(f"armorClass {projection.previous_armor_class} -> {projection.armor_class} "
                         f"(engine defense: {', '.join(parts) or 'unarmored'})")
        character = projection.sheet
    else:
        warning(f"[Startup Mechanics] {name}: armorClass left as written: {projection.reason}",
                category="character_validation")
    _startup_attack_rows(character, name, typed, untyped, provenance, faults)
    for note in notes:
        info(f"[Startup Mechanics] {name}: {note}", category="character_validation")
    return character, notes


def _reason_first_line(reason):
    """D-PKG-9: an engine error's first line, a structural split, never a character cut, for the
    provenance fields the author and reviewer read; the warning log keeps the whole text."""
    return (reason.splitlines() or [""])[0] if isinstance(reason, str) else reason


def _startup_attack_rows(character, name, typed, untyped, provenance, faults):
    """The startup rows step, one copy for startup_mechanics and the creation-time reissue: the engine's
    attack rows merged onto the sheet in place, and their report written to provenance["engine_rows"]
    (a reissue rewrites it). An engine fault is appended to ``faults`` when a list is given."""
    from core.nql import armor_class, startup_rows
    # NUM-H3c: attack rows from the engine's grants; the author's rows stay
    # when the engine is unavailable.
    not_usable_now = []
    rows, with_items, reason = startup_rows.attack_rows(character, armor_class.PROJECTION_LOCATION,
                                                        not_usable_now=not_usable_now, faults=faults,
                                                        on_timeout="raise")
    report = {"source": "core.nql.startup_rows", "typed_equipment": typed, "untyped_equipment": untyped,
              "item_rows": with_items}
    if rows is None:
        report["reason"] = _reason_first_line(reason)
        warning(f"[Startup Mechanics] {name}: attack rows left as written: {reason}", category="character_validation")
    else:
        report.update(startup_rows.merge_attack_rows(character, rows, with_items))
        report["not_usable_now"] = not_usable_now
    if provenance is not None:
        provenance["engine_rows"] = report


def validate_character_with_recovery(character_data, mechanics=True):
    """Enhanced validation with automatic error recovery and detailed reporting"""
    try:
        schema = safe_json_load("schemas/char_schema.json")
        if not schema:
            return False, "Could not load character schema"
        
        # First try to auto-fix common issues
        character_data = auto_fix_character_data(character_data)
        
        # Validate the character data
        validate(character_data, schema)
        if not mechanics:
            return True, None
        from utils.startup_mechanics import validate_startup_mechanics
        return validate_startup_mechanics(character_data)
        
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
            if isinstance(item, dict) and ("ac_base" in item or item.get("armor_category") == "shield"):
                # Shield should have ac_base of 2, armor should be 10+
                if item.get("armor_category") == "shield":
                    _normalize_shield_defense(item)
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
    from utils.transient_filesystem import ReadOnlySaveStop
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
        except (LiveProviderSuperseded, FileExistsError, ReadOnlySaveStop):
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


def _startup_location_choices(module_data):
    """The installed module's places as typed ids (#1270): the list a T093
    correction chooses from, and the fall-forward start (D-1270-2): the first
    location of the plot's first area, else of the first area by id."""
    choices = []
    areas = module_data.get("areas") or {}
    for area_id in sorted(areas):
        area = areas[area_id]
        if not isinstance(area, dict) or not area.get("areaName"):
            continue
        locations = area.get("locations", [])
        if isinstance(locations, dict):
            locations = list(locations.values())
        for location in locations:
            if isinstance(location, dict) and location.get("locationId") and location.get("name"):
                choices.append({"areaId": area_id, "areaName": area["areaName"],
                                "locationId": location["locationId"], "locationName": location["name"]})
    points = (module_data.get("plot") or {}).get("plotPoints") or []
    plot_area = points[0].get("location") if points and isinstance(points[0], dict) else None
    start = next((choice for choice in choices if choice["areaId"] == plot_area),
                 choices[0] if choices else None)
    return choices, start


def update_party_tracker(module_name, character_name, *, live_scope=None, starting_location=None):
    """Commit the selected identity and a real location through the shared writer."""
    with _startup_operation(live_scope) as scope:
        _emit_startup_phase("startup_party_commit")
        party_data = safe_json_load("party_tracker.json") or {}
        same_module = party_data.get("module") == module_name
        if not same_module:
            # Another module's save (its player file missing, or a reused headless
            # folder): start from what Reset leaves, never its calendar, events,
            # combat, companions or quests (#1283, D-1283-1). Compared by module id.
            party_data = {}
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
            # A missing weather or politicalClimate reads as unknown, never
            # as a schema failure on a same-module resume (#576).
            "weather": "", "politicalClimate": "",
        }
        for key, value in defaults.items():
            world.setdefault(key, value)
        world.update({
            "currentLocation": location["locationName"], "currentLocationId": location["locationId"],
            "currentArea": location["areaName"], "currentAreaId": location["areaId"],
        })
        for key in ("weather", "politicalClimate"):
            # A built location's own value wins; otherwise the tracker keeps its own.
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
                   "Do not claim saved state without committed facts.",
    }]
    _set_startup_progress(conversation, phase="module_selection")
    return conversation

def _startup_configuration_handback(exc, provider, revision, scope):
    from utils.startup_provider_recovery import (
        configuration_required_message, notify_configuration_saved,
        wait_for_configuration,
    )
    from utils.capture.live_provider_call import LiveProviderSuperseded, _safe_emit

    message = configuration_required_message(exc)
    if message is None:
        return False
    _emit_startup_phase("startup_configuration_required")
    # Web Settings stays usable while the normal command row remains busy.
    # Console mode uses its existing input owner for an explicit retry/cancel.
    def emit(text):
        status_manager.update_status(text, True)
    _safe_emit(emit, message)
    if not web_mode:
        while True:
            if scope.is_superseded():
                raise LiveProviderSuperseded("startup configuration wait superseded")
            answer = input("\nAfter updating provider configuration, type retry, or cancel: ").strip().lower()
            if answer == "cancel":
                raise StartupCancelled()
            if answer == "retry":
                notify_configuration_saved(provider)
                break
    wait_for_configuration(provider, revision, scope, message, emit)
    return True


def _startup_provider_pause(player_message, scope):
    """The bounded startup attempts all failed (#1267): one plain line, then wait
    for the player's next input, which retries. The words typed are not read or
    kept; the setup choices already saved stay as they are. Load, Reset or Exit
    (web) and Ctrl+C or end of input (console) stop setup as before."""
    from utils.capture.live_provider_call import LiveProviderSuperseded

    from utils.player_notice import show_player_notice

    status_ready()
    # An operational notice, not the DM's voice (#1511).
    show_player_notice((player_message or (
        "The AI provider did not answer, so character setup is waiting.")) +
        " Your setup choices are kept. Send any message to try again.", padded=True)
    try:
        while not input("\nYour response: ").strip():
            pass
    except (EOFError, KeyboardInterrupt):
        raise StartupCancelled() from None
    if scope.is_superseded():
        raise LiveProviderSuperseded("startup provider wait superseded")


def _startup_provider_failure(exc, failures, scope, pending, wait=None):
    """One completed startup provider error (#1267); returns the count to carry.

    Transient requests reissue inside the shared transport, so this sees a
    completed error. It keeps the play turn's bound (utils/provider_errors);
    the caller resends its request with one correction note, replaced on each
    failure, never added to. A refused request (HTTP 400) keeps that automatic
    correction inside the bound; an account refusal (quota, key, model access)
    asks the player at once. At the bound the player is told once and their
    next input retries (0 is returned). ``wait`` ({taskId, provider,
    startedAt}) lets the web show the retry wait (#1271)."""
    from utils.capture.live_provider_call import _interruptible_wait
    from utils.provider_errors import (
        PROVIDER_MAX_FAILURES, classify_provider_error, provider_failure_policy,
        provider_retry_delay,
    )

    failures += 1
    classification = classify_provider_error(exc)
    decision = provider_failure_policy(classification, failures, True)
    warning(f"Startup provider attempt {failures}/{PROVIDER_MAX_FAILURES} failed: {exc}",
            category="startup")
    if failures >= PROVIDER_MAX_FAILURES or (
            decision["stop"] and classification["category"] != "bad_request"):
        _startup_provider_pause(decision["player_message"], scope)
        return 0
    # Every retry waits provider_retry_delay, not decision["delay"]: the play turn
    # waits 0 for an unclassified error, and #1267 is a repeating one.
    delay = provider_retry_delay(failures - 1)
    if wait is not None:
        _publish_startup_wait(wait, failures + 1, PROVIDER_MAX_FAILURES, delay)
    _interruptible_wait(delay, scope, pending, display_status)
    return failures


def _publish_startup_wait(wait, attempt, max_attempts, delay):
    """The web's typed record of a bounded startup retry wait (#1271). Wait-only:
    console and headless text are unchanged. ``attempt`` is the next one."""
    import time

    try:
        from core.managers.status_manager import status_manager
        from utils.capture.live_provider_call import wait_purpose
        from utils.provider_errors import provider_display_name

        status_manager.publish_wait({
            "purpose": wait_purpose(wait.get("taskId"), wait.get("purpose")),
            "taskId": wait.get("taskId"),
            "provider": wait.get("provider"),
            "providerName": provider_display_name(wait.get("provider")),
            "attempt": attempt,
            "maxAttempts": max_attempts,
            "startedAt": wait.get("startedAt"),
            "phase": None,
            "lastActivityAt": None,
            "retryUntil": time.monotonic() + delay,
        })
    except Exception:
        pass  # presentational only


def get_ai_response(conversation, response_format=None, *, persist_response=True, live_scope=None,
                    startup_phase="startup_interview", task_id="T092"):
    """Run T092 (author) or T124 (whole review) through shared cancellable transport.

    The borrowed scope stays open.
    """
    from utils.capture.live_provider_call import (
        LiveProviderSuperseded, finish_live_turn_scope, open_live_turn_scope,
    )
    from utils.transient_filesystem import ReadOnlySaveStop
    from model_config import get_provider
    from utils.startup_provider_recovery import configuration_revision

    owned = live_scope is None
    scope = open_live_turn_scope() if owned else live_scope
    profiles = {
        "openai": config.DM_MAIN_GPT52_NONE,
        "gemini": config.DM_MAIN_GEMINI_PRO_LOW,
        "lmstudio": config.DM_MAIN_LMSTUDIO,
        "legacy": config.DM_MAIN_LEGACY,
    }

    request_messages = copy.deepcopy(conversation)
    failures = 0
    import time
    started = time.monotonic()  # the player's wait, for #1271
    error_note = []  # the one correction note after a failed attempt (#1267)
    _emit_startup_phase(startup_phase)
    status_processing_ai()
    try:
        while True:
            if scope.is_superseded():
                raise LiveProviderSuperseded("startup request superseded")
            try:
                provider = get_provider()
                main_cfg = profiles[provider]
                revision = configuration_revision(provider)
                response = capture_and_fanout(
                    task_id, api_client.create_completion,
                    _request_provider=provider, _live_selected="required",
                    _detached_scope=scope,
                    # #1422 F2: the adventure menu is not character setup.
                    _wait_purpose=("adventure_choice" if startup_phase == "startup_module_selection" else None),
                    messages=copy.deepcopy(request_messages + error_note),
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
            except (LiveProviderSuperseded, ReadOnlySaveStop):
                raise
            except (StartupCancelled, KeyboardInterrupt, EOFError):
                raise
            except Exception as exc:
                if _startup_configuration_handback(exc, provider, revision, scope):
                    _emit_startup_phase(startup_phase)
                    status_processing_ai()
                    continue
                error_note = [{"role": "system", "content": (
                    f"The previous startup request did not complete correctly: {exc}. "
                    "Retain the player choices and return the requested response."
                )}]
                failures = _startup_provider_failure(
                    exc, failures, scope, "Character setup is still pending; your choices are retained.",
                    {"taskId": task_id, "provider": provider, "startedAt": started})
                if not failures:
                    _emit_startup_phase(startup_phase)
                    status_processing_ai()
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


def _declared_starting_location(module_name):
    """The entry the module declares (module_declaration.json, chosen as the
    entry when it was built), resolved against its files, with the weather
    and political climate the module was built with. None when it declares
    no entry, the entry does not resolve, or the module has no built weather
    and political climate (T093 then supplies them, as before)."""
    from utils import roster_conversion

    path_manager = ModulePathManager(module_name)
    start = roster_conversion.declared_start(path_manager.module_dir)
    location = _resolve_startup_location(module_name, start)
    if location is None:
        return None
    built = safe_json_load(os.path.join(path_manager.module_dir, "party_tracker_BU.json")) or {}
    built = built.get("worldConditions") if isinstance(built, dict) else None
    built = built if isinstance(built, dict) else {}
    # Empty conditions mean not built: T093 supplies them (#1478).
    if not all(isinstance(built.get(key), str) and built.get(key).strip()
               for key in ("weather", "politicalClimate")):
        return None
    return dict(location, weather=built["weather"], politicalClimate=built["politicalClimate"])


def get_ai_starting_location(module, request_provider=None, *, live_scope=None):
    """The module's declared entry if it has one; otherwise have T093 choose an
    entry from the installed module; never invent IDs."""
    declared = _declared_starting_location(module["moduleName"])
    if declared is not None:
        info(f"Starting at {module['moduleName']}'s declared entry "
             f"{declared['areaId']}/{declared['locationId']}", category="startup")
        return declared
    from model_config import get_provider
    from utils.startup_provider_recovery import configuration_revision
    from utils.capture.live_provider_call import LiveProviderSuperseded
    from utils.transient_filesystem import ReadOnlySaveStop

    provider = request_provider or get_provider()
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
        choices, fall_forward = _startup_location_choices(module_data or {})
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
        failures = 0
        import time
        started = time.monotonic()  # the player's wait, for #1271
        error_note = []  # the one correction note after a failed attempt (#1267)
        # The latest rejected proposal and the typed choices (#1270): replaced
        # each round, kept across a provider error, never accumulated.
        correction_note = []
        invalid = 0
        rejected = []
        while True:
            try:
                revision = configuration_revision(provider)
                response = capture_and_fanout(
                    "T093", api_client.create_completion,
                    _request_provider=provider, _live_selected="required",
                    _detached_scope=scope,
                    messages=copy.deepcopy(messages + correction_note + error_note),
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
                error_note = []
                invalid += 1
                rejected.append([candidate.get("areaId"), candidate.get("locationId")]
                                if isinstance(candidate, dict) else "unparseable")
                if invalid >= STARTUP_LOCATION_REJECTION_LIMIT:
                    location = _resolve_startup_location(
                        module_name, fall_forward and dict(fall_forward, weather="", politicalClimate=""))
                    if location is not None:
                        warning(f"T093 proposals rejected {invalid} times ({rejected}); starting at "
                                f"{location['areaId']}/{location['locationId']}", category="startup")
                        from utils.player_notice import show_player_notice

                        # An operational notice, not the DM's voice (#1511).
                        show_player_notice("The AI could not settle on a starting location, so your "
                                           f"adventure begins where the story starts: {location['locationName']} "
                                           f"in {location['areaName']}.", padded=True)
                        return location
                    # No place in this module resolves: wait for the player, then 4 fresh rounds.
                    _startup_provider_pause(
                        "The AI could not find a starting location in this adventure, so setup is waiting.", scope)
                    invalid, rejected, correction_note = 0, [], []
                    _emit_startup_phase("startup_location")
                    status_processing_ai()
                    continue
                correction_note = [{"role": "system", "content": (
                    "The rejected response is incomplete or its IDs do not resolve in "
                    "the selected module. No location has been committed. Return all six "
                    "fields for one of these actual locations. Rejected response: "
                    + raw + "\nLOCATIONS:\n" + json.dumps(choices, ensure_ascii=True)
                )}]
            except (LiveProviderSuperseded, ReadOnlySaveStop):
                raise
            except (StartupCancelled, KeyboardInterrupt, EOFError):
                raise
            except Exception as exc:
                if _startup_configuration_handback(exc, provider, revision, scope):
                    provider = get_provider()
                    mini_cfg = profiles.get(provider, config.MINI_UTIL_LEGACY)
                    _emit_startup_phase("startup_location")
                    status_processing_ai()
                    continue
                error_note = [{"role": "system", "content": (
                    f"The last location request failed: {exc}. Retain the task and "
                    "return a complete grounded proposal."
                )}]
                failures = _startup_provider_failure(
                    exc, failures, scope, "Still determining the adventure's starting location.",
                    {"taskId": "T093", "provider": provider, "startedAt": started})
                if not failures:
                    _emit_startup_phase("startup_location")
                    status_processing_ai()

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
        try:
            success = run_startup_sequence()
        except StartupCancelled:
            pass  # Shared runner already acknowledged the intentional pause.
        else:
            if success:
                _say("Dungeon Master: Startup wizard completed successfully!")
            else:
                print("Error: Startup wizard failed or was cancelled.")
    else:
        _say("Dungeon Master: Character and module already configured. No setup needed.")
