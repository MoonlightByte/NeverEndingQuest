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
            # Runtime transaction/forensic roots are local recovery authority,
            # not campaign save data. Copying them would make a later restore
            # replay stale or contradictory lifecycle state.
            if os.path.basename(dir) == "conversation_history":
                return (
                    ["pending_location_transition.json"]
                    if "pending_location_transition.json" in files
                    else []
                )
            if os.path.basename(dir) != "modules":
                return []
            return [
                'backups',
                '.module_transactions',
                '.publication_transactions',
                '.module_orphan_quarantine',
            ]

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
        "modules/effects_tracker.json", "modules/effects_state.json", "modules/default/effects_tracker.json"
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
    
    print(f"{GREEN}✓ Backup complete: {backup_dir}{RESET}")
    return backup_dir

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
    """Reset global files without interleaving a party module publication."""
    from core.managers.campaign_manager import (
        _campaign_transaction_lock,
        _party_module_transition_lock,
    )
    from utils.module_refresh_lock import module_refresh_lock

    # Global lock order: party transition -> module (when needed) -> campaign.
    with _party_module_transition_lock():
        with module_refresh_lock() as refresh_acquired:
            if not refresh_acquired:
                raise TimeoutError("Module refresh is active; retry reset")
            lifecycle = _recover_module_lifecycle_for_reset_locked()
            with _campaign_transaction_lock("modules/campaign.json"):
                return _reset_global_state_locked(lifecycle=lifecycle)


def _recover_module_lifecycle_for_reset_locked():
    """Recover before reset work; leave receipts live until reset commits."""
    from utils.commit_state import recover_incomplete_refresh_commit
    from utils.module_lifecycle import ModuleLifecycleStore, RecoveryStatus

    recover_incomplete_refresh_commit()
    lifecycle = ModuleLifecycleStore("modules")
    lifecycle_recovery = lifecycle.recover()
    if lifecycle_recovery.status is RecoveryStatus.INDETERMINATE:
        raise RuntimeError("Module lifecycle recovery is required before reset")
    return lifecycle


def _reset_global_state_locked(*, lifecycle=None, reset_prepared=False):
    """Phase 3: Create fresh game state"""
    print(f"\n{CYAN}PHASE 3: Creating fresh game state...{RESET}")

    campaign_file = os.path.join("modules", "campaign.json")
    from core.managers.campaign_manager import (
        _assert_no_active_campaign_completion,
        _bump_campaign_lifecycle_epoch,
    )

    if not reset_prepared:
        # Refusal-capable checks must preserve the old timeline and its pending
        # delivery authority.  Invalidate only after reset is certain to begin.
        _assert_no_active_campaign_completion(campaign_file)
        if lifecycle is None:
            raise RuntimeError("Module lifecycle reset preflight is unavailable")
        lifecycle.invalidate_pending_publication_receipts_for_reset()
        _bump_campaign_lifecycle_epoch(campaign_file)
    
    # Reset party tracker to empty object (matches installer behavior)
    with open("party_tracker.json", 'w') as f:
        f.write("{}")
    print("  [OK] Reset party_tracker.json to {}")
    
    # Delete existing player storage - let game create fresh one
    if os.path.exists("player_storage.json"):
        os.remove("player_storage.json")
        print("  [OK] Removed player_storage.json (will be created fresh)")
    
    # Delete campaign state and its transactional metadata under the same
    # lifecycle boundary used by completion/save/restore.
    if os.path.exists(campaign_file):
        os.remove(campaign_file)
        print("  [OK] Removed modules/campaign.json (will be created fresh)")
    completion_metadata = os.path.join(
        os.path.dirname(campaign_file),
        f".{os.path.basename(campaign_file)}.completion",
    )
    if os.path.isdir(completion_metadata):
        shutil.rmtree(completion_metadata)
        print("  [OK] Removed campaign completion recovery metadata")
    
    # Delete world_registry.json - let module stitcher create fresh one
    world_registry_file = os.path.join("modules", "world_registry.json")
    if os.path.exists(world_registry_file):
        os.remove(world_registry_file)
        print("  ✓ Removed world_registry.json (will be created fresh)")
    
    # Delete effects_tracker.json files
    effects_tracker_files = [
        "modules/effects_tracker.json",
        "modules/effects_state.json",
        "modules/default/effects_tracker.json",
    ]
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

    pending_transition = os.path.join(
        "modules",
        "conversation_history",
        "pending_location_transition.json",
    )
    if os.path.exists(pending_transition):
        os.remove(pending_transition)
        print("  ✓ Removed stale location-transition recovery marker")

def clear_all_files():
    """Phase 4: Delete all generated files"""
    print(f"\n{CYAN}PHASE 4: Clearing all generated files...{RESET}")
    
    # Conversation files and caches
    conversation_files = [
        "modules/conversation_history/conversation_history.json", "modules/conversation_history/chat_history.json",
        "modules/conversation_history/combat_conversation_history.json", "player_conversation_history.json",
        "modules/conversation_history/game_interface_cache.json", "modules/conversation_history/compression_cache.json",
        "modules/conversation_history/combat_user_message_cache.json",
        "modules/conversation_history/pending_location_transition.json",
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
    """Run the full reset under the shared campaign lifecycle boundary."""
    from core.managers.campaign_manager import (
        _assert_no_active_campaign_completion,
        _campaign_transaction_lock,
        _party_module_transition_lock,
    )
    from utils.module_refresh_lock import module_refresh_lock

    with _party_module_transition_lock():
        with module_refresh_lock() as refresh_acquired:
            if not refresh_acquired:
                raise TimeoutError("Module refresh is active; retry reset")
            lifecycle = _recover_module_lifecycle_for_reset_locked()
            with _campaign_transaction_lock("modules/campaign.json"):
                _assert_no_active_campaign_completion("modules/campaign.json")
                return _perform_reset_logic_locked(lifecycle)


def _perform_reset_logic_locked(lifecycle):
    """The core logic of the reset, without prompts or top-level error handling."""
    # Phase 1: Backup everything
    backup_dir = create_backup()

    # Backup/refusal paths leave the old timeline intact.  Once the backup is
    # durable, retire old delivery authority and invalidate stale workers once,
    # immediately before the first live campaign/module mutation.
    from core.managers.campaign_manager import _bump_campaign_lifecycle_epoch

    lifecycle.invalidate_pending_publication_receipts_for_reset()
    _bump_campaign_lifecycle_epoch("modules/campaign.json")
    
    # Phase 2: Reset all modules
    print(f"\n{CYAN}PHASE 2: Resetting all modules from backups...{RESET}")
    modules = discover_modules()
    print(f"Found {len(modules)} modules: {', '.join(modules)}")
    
    for module in modules:
        reset_module(module)
    
    # Phase 3: Reset global state
    _reset_global_state_locked(reset_prepared=True)
    
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
