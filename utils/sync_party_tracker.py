#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Party Tracker Sync Script

This script ensures that party_tracker.json quest statuses are synchronized 
with the authoritative module_plot.json file. Run this periodically or 
whenever there are discrepancies between plot progression and quest status.

Usage:
    python sync_party_tracker.py [module_name]
    
If no module_name is provided, it will use the current module from party_tracker.json
"""

import sys
import os
from core.managers.campaign_manager import CampaignManager
from .encoding_utils import safe_json_load

def main():
    """Main sync script"""
    
    # Get module name from command line or party tracker
    if len(sys.argv) > 1:
        module_name = sys.argv[1]
        print(f"Syncing specified module: {module_name}")
    else:
        # Get current module from party tracker
        try:
            party_data = safe_json_load("party_tracker.json")
            module_name = party_data.get("module")
            if not module_name:
                print("Error: No module specified and no current module in party_tracker.json")
                sys.exit(1)
            print(f"Syncing current module: {module_name}")
        except Exception as e:
            print(f"Error reading party_tracker.json: {e}")
            sys.exit(1)
    
    # Create campaign manager and run sync
    print("=" * 60)
    print("PARTY TRACKER SYNC UTILITY")
    print("=" * 60)
    
    manager = CampaignManager()
    
    # Show current status
    print("\nBEFORE SYNC:")
    print("-" * 30)
    try:
        party_data = safe_json_load("party_tracker.json")
        for quest in party_data.get('activeQuests', []):
            print(f"  {quest['id']} ({quest['title']}): {quest['status']}")
    except Exception as e:
        print(f"Error reading party tracker: {e}")
        sys.exit(1)
    
    # Run sync
    print("\nSYNC PROCESS:")
    print("-" * 30)
    try:
        updated = manager.sync_party_tracker_with_plot(module_name)
        if updated:
            print("[PASS] Party tracker updated successfully")
        else:
            print("[PASS] Party tracker already in sync")
    except Exception as e:
        print(f"[FAIL] Sync failed: {e}")
        sys.exit(1)
    
    # Show final status
    print("\nAFTER SYNC:")
    print("-" * 30)
    try:
        party_data = safe_json_load("party_tracker.json")
        for quest in party_data.get('activeQuests', []):
            print(f"  {quest['id']} ({quest['title']}): {quest['status']}")
    except Exception as e:
        print(f"Error reading updated party tracker: {e}")
        sys.exit(1)
    
    # Check module completion status
    print("\nMODULE STATUS:")
    print("-" * 30)
    try:
        is_complete = manager.check_module_completion(module_name)
        if is_complete:
            print(f"[PASS] Module '{module_name}' is COMPLETE")
            print("  Ready for module transition and summary generation")
        else:
            print(f"o Module '{module_name}' is in progress")
            print("  Continue playing to complete the adventure")
    except Exception as e:
        print(f"Error checking completion: {e}")
    
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()