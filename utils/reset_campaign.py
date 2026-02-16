#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
CAMPAIGN NUCLEAR RESET TOOL
===========================
This script creates a complete backup of the current campaign state,
then wipes everything clean to test the virgin campaign experience.

WARNING: This will delete ALL game data after backing it up!
Use this to test character creation, party tracker generation,
and the complete fresh campaign startup process.
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path

# ANSI colors for output
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

def print_header():
    """Print warning header"""
    print(f"\n{RED}{'='*60}")
    print("CAMPAIGN NUCLEAR RESET - COMPLETE WIPE TO VIRGIN STATE")
    print(f"{'='*60}{RESET}\n")
    print(f"{YELLOW}This will:")
    print("1. Backup EVERYTHING to a timestamped folder")
    print("2. Restore all modules from clean _BU.json backups")
    print("3. Delete ALL characters, conversations, and game state")
    print(f"4. Create a fresh campaign ready for first-time play{RESET}\n")

def create_backup():
    """Phase 1: Create complete backup of current state"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"modules/backups/campaign_backup_{timestamp}"
    
    print(f"\n{CYAN}PHASE 1: Creating complete backup...{RESET}")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup modules directory (excluding backups subdirectory to prevent recursion)
    if os.path.exists("modules"):
        print(f"Backing up modules directory...")
        def ignore_backups(dir, files):
            # Ignore the backups directory to prevent recursive backup loops
            return ['backups'] if os.path.basename(dir) == 'modules' else []

        shutil.copytree("modules", os.path.join(backup_dir, "modules"), ignore=ignore_backups)
    
    # Backup all root game files
    root_files = [
        "party_tracker.json", "campaign.json", "world_registry.json",
        "modules/conversation_history/conversation_history.json", "modules/conversation_history/chat_history.json", "modules/conversation_history/combat_conversation_history.json",
        "modules/conversation_history/conversation_history.json", "current_location.json", "journal.json",
        "summary_dump.json", "trimmed_summary_dump.json", "modules/conversation_history/second_model_history.json",
        "modules/conversation_history/third_model_history.json", "debug_encounter_update.json", "debug_initial_response.json",
        "debug_npc_update.json", "debug_player_update.json", "debug_second_model.json",
        "npc_update_debug_log.json", "npc_update_detailed_log.json", "prompt_validation.json",
        "training_data.json", "debug.txt", "claude.txt",
        "modules/effects_tracker.json", "modules/default/effects_tracker.json"
    ]
    
    for file in root_files:
        if os.path.exists(file):
            print(f"  Backing up {file}")
            shutil.copy2(file, backup_dir)
    
    # Backup log files
    log_files = ["modules/logs/transition_debug.log", "modules/logs/adv_summary_debug.log", "modules/logs/cumulative_summary_debug.log",
                 "modules/logs/combat_builder.log", "debug_log.txt", "modules/logs/game_debug.log", "modules/logs/game_errors.log", "error.txt"]
    
    for log in log_files:
        if os.path.exists(log):
            print(f"  Backing up {log}")
            shutil.copy2(log, backup_dir)
    
    # Backup combat logs directory
    if os.path.exists("combat_logs"):
        print(f"Backing up combat_logs directory...")
        shutil.copytree("combat_logs", os.path.join(backup_dir, "combat_logs"))
    
    # Backup debug log backups
    if os.path.exists("debug_log_backups"):
        print(f"Backing up debug_log_backups directory...")
        shutil.copytree("debug_log_backups", os.path.join(backup_dir, "debug_log_backups"))
    
    # TABLETOP MODE: Backup memory state artifact if present
    memory_db_path = "data/memory.db"
    memory_backed_up = False
    if os.path.exists(memory_db_path):
        print(f"  Backing up memory state artifact...")
        memory_backup_dir = os.path.join(backup_dir, "data")
        os.makedirs(memory_backup_dir, exist_ok=True)
        shutil.copy2(memory_db_path, os.path.join(memory_backup_dir, "memory.db"))
        print(f"  [OK] Memory state artifact backed up to {memory_backup_dir}/memory.db")
        memory_backed_up = True
    else:
        # TABLETOP MODE: Non-fatal reporting when memory artifact absent
        print(f"  [INFO] Memory state artifact not present; continuing backup")
    
    # TABLETOP MODE: Verify backup directory layout compatibility
    _verify_backup_layout_compatibility(backup_dir, memory_backed_up)
    
    print(f"{GREEN}[OK] Backup complete: {backup_dir}{RESET}")
    return backup_dir

def _verify_backup_layout_compatibility(backup_dir: str, memory_backed_up: bool) -> None:
    """Verify backup directory layout remains compatible with reset/restore expectations.
    
    TABLETOP MODE: Lightweight layout verification for backward compatibility.
    Checks that backup structure matches expectations without altering semantics.
    
    Args:
        backup_dir: Path to the backup directory to verify
        memory_backed_up: Whether memory artifact was backed up in this session
    """
    print(f"\n{CYAN}Verifying backup layout compatibility...{RESET}")
    
    # Check 1: modules/ directory exists when source modules/ exists
    source_modules_exists = os.path.exists("modules")
    backup_modules_path = os.path.join(backup_dir, "modules")
    if source_modules_exists:
        if os.path.exists(backup_modules_path):
            print(f"  [OK] modules/ directory present in backup")
        else:
            print(f"  [WARNING] modules/ directory missing in backup but source exists")
    
    # Check 2: Root backup files remain at backup root
    root_files_expected = ["party_tracker.json", "journal.json", "current_location.json"]
    root_files_found = 0
    for root_file in root_files_expected:
        if os.path.exists(os.path.join(backup_dir, root_file)):
            root_files_found += 1
    
    if root_files_found == len(root_files_expected):
        print(f"  [OK] All {len(root_files_expected)} expected root files present")
    elif root_files_found > 0:
        print(f"  [WARNING] Only {root_files_found}/{len(root_files_expected)} root files present")
    else:
        print(f"  [WARNING] No expected root files found at backup root")
    
    # Check 3: Memory artifact at correct path if backed up
    memory_backup_path = os.path.join(backup_dir, "data", "memory.db")
    if memory_backed_up:
        if os.path.exists(memory_backup_path):
            print(f"  [OK] Memory artifact at expected path: data/memory.db")
        else:
            print(f"  [WARNING] Memory artifact should be at {memory_backup_path} but is missing")
    else:
        # Check 4: No memory file if source absent
        if os.path.exists(memory_backup_path):
            print(f"  [INFO] Memory artifact present in backup (source may have changed)")
        else:
            print(f"  [OK] No memory artifact in backup (as expected)")
    
    print(f"{GREEN}[OK] Backup layout verification complete{RESET}")

def discover_modules():
    """Get list of all modules"""
    modules = []
    if os.path.exists("modules"):
        for item in os.listdir("modules"):
            path = os.path.join("modules", item)
            if os.path.isdir(path) and not item.startswith('.') and not item.endswith('_backup'):
                # Skip campaign_archives and campaign_summaries
                if item not in ["campaign_archives", "campaign_summaries"]:
                    modules.append(item)
    return modules

def reset_module(module_name):
    """Reset a single module from its backup files"""
    module_path = os.path.join("modules", module_name)
    print(f"\n{CYAN}Resetting module: {module_name}{RESET}")
    
    # Find all _BU.json files
    bu_files = []
    for root, dirs, files in os.walk(module_path):
        for file in files:
            if file.endswith("_BU.json"):
                bu_files.append(os.path.join(root, file))
    
    # Restore from backups
    for bu_file in bu_files:
        original_file = bu_file.replace("_BU.json", ".json")
        if os.path.exists(bu_file):
            shutil.copy2(bu_file, original_file)
            print(f"  ✓ Restored {os.path.relpath(original_file, module_path)}")
    
    # Clear characters directory completely
    chars_dir = os.path.join(module_path, "characters")
    if os.path.exists(chars_dir):
        print(f"  Clearing characters directory...")
        for file in os.listdir(chars_dir):
            file_path = os.path.join(chars_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        print(f"  ✓ Characters directory cleared")
    
    # Remove legacy area files from main folder (Keep_of_Doom migration cleanup)
    if module_name == "Keep_of_Doom":
        area_ids = ["G001", "HH001", "SK001", "TBM001", "TCD001"]
        print(f"  Cleaning up legacy area files from main folder...")
        for area_id in area_ids:
            legacy_file = os.path.join(module_path, f"{area_id}.json")
            if os.path.exists(legacy_file):
                os.remove(legacy_file)
                print(f"  ✓ Removed legacy {area_id}.json from main folder")
    
    # Clear any validation reports
    validation_report = os.path.join(module_path, "validation_report.json")
    if os.path.exists(validation_report):
        os.remove(validation_report)
    
    # Clear NPC codex if exists
    npc_codex = os.path.join(module_path, "npc_codex.json")
    if os.path.exists(npc_codex):
        os.remove(npc_codex)

def reset_global_state():
    """Phase 3: Create fresh game state"""
    print(f"\n{CYAN}PHASE 3: Creating fresh game state...{RESET}")
    
    # Reset party tracker to empty object (matches installer behavior)
    with open("party_tracker.json", 'w') as f:
        f.write("{}")
    print("  [OK] Reset party_tracker.json to {}")
    
    # Delete existing player storage - let game create fresh one
    if os.path.exists("player_storage.json"):
        os.remove("player_storage.json")
        print("  [OK] Removed player_storage.json (will be created fresh)")
    
    # Delete campaign.json - let game create fresh one
    campaign_file = os.path.join("modules", "campaign.json")
    if os.path.exists(campaign_file):
        os.remove(campaign_file)
        print("  [OK] Removed modules/campaign.json (will be created fresh)")
    
    # Delete world_registry.json - let module stitcher create fresh one
    world_registry_file = os.path.join("modules", "world_registry.json")
    if os.path.exists(world_registry_file):
        os.remove(world_registry_file)
        print("  ✓ Removed world_registry.json (will be created fresh)")
    
    # Delete effects_tracker.json files
    effects_tracker_files = ["modules/effects_tracker.json", "modules/default/effects_tracker.json"]
    for file in effects_tracker_files:
        if os.path.exists(file):
            os.remove(file)
    
    # Reset current location to Keep of Doom starting point
    starting_location = {
        "locationId": "A01",
        "name": "Hillfar General Store",
        "description": "A well-stocked general store with wooden shelves filled with adventuring supplies. Lanterns hang from the ceiling, casting warm light over the various goods. The shopkeeper, a friendly halfling named Pip, greets customers with enthusiasm.",
        "npcs": ["Pip Goodbarrel (Shopkeeper)"],
        "objects": ["Shop Counter", "Supply Shelves", "Equipment Racks"],
        "hiddenObjects": [],
        "exits": {
            "north": {"locationId": "A03", "description": "To Market Square"},
            "outside": {"locationId": "A03", "description": "To Market Square"}
        },
        "descriptionShort": "A cozy general store run by Pip the halfling"
    }
    
    with open("current_location.json", 'w', encoding='utf-8') as f:
        json.dump(starting_location, f, indent=2, ensure_ascii=False)
    print("  ✓ Reset current_location.json to starting point (HH001 A01)")
    
    # Create empty journal
    journal_data = {
        "module": "Keep_of_Doom",
        "entries": []
    }
    with open("journal.json", 'w', encoding='utf-8') as f:
        json.dump(journal_data, f, indent=2, ensure_ascii=False)
    print("  ✓ Created empty journal.json")
    
    # Delete world_registry.json - will be recreated
    if os.path.exists("world_registry.json"):
        os.remove("world_registry.json")
        print("  ✓ Removed world_registry.json (will be created fresh)")

def clear_all_files():
    """Phase 4: Delete all generated files"""
    print(f"\n{CYAN}PHASE 4: Clearing all generated files...{RESET}")
    
    # Conversation files and caches
    conversation_files = [
        "modules/conversation_history/conversation_history.json", "modules/conversation_history/chat_history.json",
        "modules/conversation_history/combat_conversation_history.json", "player_conversation_history.json",
        "modules/conversation_history/game_interface_cache.json", "modules/conversation_history/compression_cache.json",
        "modules/conversation_history/combat_user_message_cache.json"
    ]
    
    for file in conversation_files:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"  ✓ Deleted {file}")
            except PermissionError:
                print(f"  ⊘ Skipped {file} (file in use)")
            except Exception as e:
                print(f"  ⊘ Could not delete {file}: {e}")
    
    # Debug and log files
    debug_files = [
        "modules/logs/transition_debug.log", "modules/logs/adv_summary_debug.log", "modules/logs/cumulative_summary_debug.log",
        "modules/logs/combat_builder.log", "debug_log.txt", "modules/logs/game_debug.log", "modules/logs/game_errors.log", "error.txt",
        "summary_dump.json", "trimmed_summary_dump.json", "modules/conversation_history/second_model_history.json",
        "modules/conversation_history/third_model_history.json", "debug_encounter_update.json", "debug_initial_response.json",
        "debug_npc_update.json", "debug_player_update.json", "debug_second_model.json",
        "npc_update_debug_log.json", "npc_update_detailed_log.json", "prompt_validation.json",
        "modules/conversation_history/combat_validation_log.json", "debug_ai_response.json", "dialogue_summary.json",
        "debug_critical_field_loss.json", "debug_npc_update.json"
    ]
    
    for file in debug_files:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"  ✓ Deleted {file}")
            except PermissionError:
                print(f"  ⊘ Skipped {file} (file in use)")
            except Exception as e:
                print(f"  ⊘ Could not delete {file}: {e}")
    
    # Clear combat logs directory
    if os.path.exists("combat_logs"):
        shutil.rmtree("combat_logs")
        print("  ✓ Cleared combat_logs directory")

    # Clear companion memories
    if os.path.exists("data/companion_memories"):
        shutil.rmtree("data/companion_memories")
        os.makedirs("data/companion_memories")
        print("  ✓ Cleared companion memories")

    if os.path.exists("data/companion_memories_compressed"):
        shutil.rmtree("data/companion_memories_compressed")
        os.makedirs("data/companion_memories_compressed")
        print("  ✓ Cleared compressed companion memories")

    # Clear campaign archives and summaries
    if os.path.exists("modules/campaign_archives"):
        shutil.rmtree("modules/campaign_archives")
        os.makedirs("modules/campaign_archives")
        print("  ✓ Cleared campaign_archives")
    
    if os.path.exists("modules/campaign_summaries"):
        shutil.rmtree("modules/campaign_summaries")
        os.makedirs("modules/campaign_summaries")
        print("  ✓ Cleared campaign_summaries")

def perform_reset_logic():
    """The core logic of the reset, without prompts or top-level error handling."""
    # Phase 1: Backup everything
    backup_dir = create_backup()
    
    # Phase 2: Reset all modules
    print(f"\n{CYAN}PHASE 2: Resetting all modules from backups...{RESET}")
    modules = discover_modules()
    print(f"Found {len(modules)} modules: {', '.join(modules)}")
    
    for module in modules:
        reset_module(module)
    
    # Phase 3: Reset global state
    reset_global_state()
    
    # Phase 4: Clear all generated files
    clear_all_files()
    
    return backup_dir

def main():
    """Main reset function for command-line execution"""
    print_header()
    
    # Confirm with user
    response = input(f"\n{RED}Are you sure you want to completely reset the campaign? (yes/no): {RESET}")
    if response.lower() != 'yes':
        print(f"{YELLOW}Reset cancelled.{RESET}")
        return
    
    backup_dir = "backup failed" # Default value
    try:
        backup_dir = perform_reset_logic()
        
        # Success message
        print(f"\n{GREEN}{'='*60}")
        print("CAMPAIGN RESET COMPLETE!")
        print(f"{'='*60}{RESET}")
        print(f"\n{GREEN}✓ Current state backed up to: {backup_dir}")
        print(f"✓ All modules restored from clean backups")
        print(f"✓ All characters and game state cleared")
        print(f"✓ Ready for virgin campaign testing!{RESET}")
        print(f"\n{YELLOW}Next steps:")
        print("1. Run the game to test party tracker creation")
        print("2. Create a new character to test character generation")
        print(f"3. Begin your fresh campaign!{RESET}\n")
        
    except Exception as e:
        print(f"\n{RED}ERROR during reset: {str(e)}{RESET}")
        print(f"{YELLOW}Your backup is safe in: {backup_dir}{RESET}")
        raise

if __name__ == "__main__":
    main()