#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.
#
# Portions of this file contain Forgotten Realms calendar month names which are:
# Copyright (c) Wizards of the Coast LLC. All Rights Reserved.
# Used under the Open Gaming License or similar terms.

"""
Calendar Migration Utility
Silently converts old Forgotten Realms calendar months to SRD-compliant months
"""

from utils.file_operations import safe_read_json, safe_write_json
from utils.enhanced_logger import debug, info, set_script_name
import os

# Set script name for logging
set_script_name("calendar_migration")

# Month conversion mapping from Forgotten Realms to SRD
MONTH_CONVERSION = {
    # Forgotten Realms -> SRD Calendar
    "Hammer": "Firstmonth",      # January equivalent
    "Alturiak": "Coldmonth",     # February equivalent
    "Ches": "Thawmonth",         # March equivalent
    "Tarsakh": "Springmonth",    # April equivalent
    "Mirtul": "Bloommonth",      # May equivalent
    "Kythorn": "Sunmonth",       # June equivalent
    "Flamerule": "Heatmonth",    # July equivalent
    "Eleasis": "Harvestmonth",   # August equivalent
    "Eleint": "Autumnmonth",     # September equivalent
    "Marpenoth": "Fademonth",    # October equivalent
    "Uktar": "Frostmonth",       # November equivalent
    "Nightal": "Yearend"         # December equivalent
}

def migrate_calendar():
    """
    Check and migrate calendar months in party_tracker.json
    Returns True if migration was performed, False otherwise
    """
    try:
        # Check if party_tracker.json exists
        if not os.path.exists("party_tracker.json"):
            debug("No party_tracker.json found, skipping calendar migration", category="calendar_migration")
            return False
        
        # Load party tracker data
        party_data = safe_read_json("party_tracker.json")
        if not party_data or "worldConditions" not in party_data:
            debug("No worldConditions found in party_tracker.json", category="calendar_migration")
            return False
        
        # Get current month
        current_month = party_data["worldConditions"].get("month", "")
        
        # Check if migration is needed
        if current_month in MONTH_CONVERSION:
            old_month = current_month
            new_month = MONTH_CONVERSION[current_month]
            
            # Update to new month
            party_data["worldConditions"]["month"] = new_month
            
            # Save updated data
            if safe_write_json("party_tracker.json", party_data):
                info(f"Calendar migrated: {old_month} -> {new_month}", category="calendar_migration")
                return True
            else:
                debug(f"Failed to save calendar migration", category="calendar_migration")
                return False
        else:
            # Check if it's already a valid SRD month
            valid_months = [
                "Firstmonth", "Coldmonth", "Thawmonth", "Springmonth",
                "Bloommonth", "Sunmonth", "Heatmonth", "Harvestmonth",
                "Autumnmonth", "Fademonth", "Frostmonth", "Yearend"
            ]
            
            if current_month not in valid_months and current_month:
                # Unknown month, default to Springmonth
                debug(f"Unknown month '{current_month}', defaulting to Springmonth", category="calendar_migration")
                party_data["worldConditions"]["month"] = "Springmonth"
                safe_write_json("party_tracker.json", party_data)
                return True
            
            debug("Calendar already using SRD months", category="calendar_migration")
            return False
            
    except Exception as e:
        debug(f"Error during calendar migration: {e}", category="calendar_migration")
        return False

def migrate_character_effects():
    """
    Migrate calendar months in character files and effects_tracker.json
    """
    migrated_count = 0
    
    # Check effects_tracker.json
    if os.path.exists("modules/effects_tracker.json"):
        try:
            effects_data = safe_read_json("modules/effects_tracker.json")
            if effects_data:
                modified = False
                # Check all character entries
                for char_name, char_effects in effects_data.get("characters", {}).items():
                    for effect in char_effects.get("effects", []):
                        if "appliedAt" in effect:
                            month = effect["appliedAt"].get("month", "")
                            if month in MONTH_CONVERSION:
                                effect["appliedAt"]["month"] = MONTH_CONVERSION[month]
                                modified = True
                
                if modified:
                    safe_write_json("modules/effects_tracker.json", effects_data)
                    migrated_count += 1
                    debug("Migrated calendar months in effects_tracker.json", category="calendar_migration")
                    
        except Exception as e:
            debug(f"Error migrating effects_tracker.json: {e}", category="calendar_migration")
    
    # Check character files in all modules
    modules_dir = "modules"
    if os.path.exists(modules_dir):
        for module_name in os.listdir(modules_dir):
            module_path = os.path.join(modules_dir, module_name)
            if os.path.isdir(module_path):
                chars_dir = os.path.join(module_path, "characters")
                if os.path.exists(chars_dir):
                    for char_file in os.listdir(chars_dir):
                        if char_file.endswith(".json"):
                            char_path = os.path.join(chars_dir, char_file)
                            try:
                                char_data = safe_read_json(char_path)
                                if char_data:
                                    modified = False
                                    
                                    # Check temporary effects
                                    for effect in char_data.get("temporaryEffects", []):
                                        if "appliedAt" in effect:
                                            month = effect["appliedAt"].get("month", "")
                                            if month in MONTH_CONVERSION:
                                                effect["appliedAt"]["month"] = MONTH_CONVERSION[month]
                                                modified = True
                                    
                                    if modified:
                                        safe_write_json(char_path, char_data)
                                        migrated_count += 1
                                        debug(f"Migrated calendar months in {char_file}", category="calendar_migration")
                                        
                            except Exception as e:
                                debug(f"Error migrating {char_file}: {e}", category="calendar_migration")
    
    return migrated_count

def run_calendar_migration():
    """
    Main migration function to be called at startup
    """
    debug("Starting calendar migration check", category="calendar_migration")
    
    # Migrate party tracker
    party_migrated = migrate_calendar()
    
    # Migrate character effects
    effects_migrated = migrate_character_effects()
    
    if party_migrated or effects_migrated > 0:
        info(f"Calendar migration complete. Migrated party tracker: {party_migrated}, character files: {effects_migrated}", category="calendar_migration")
    else:
        debug("No calendar migration needed", category="calendar_migration")

# For testing
if __name__ == "__main__":
    run_calendar_migration()