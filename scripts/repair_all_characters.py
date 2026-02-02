#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""
Utility script to run the repair and weapon synchronization logic on all character sheets.
This ensures all characters benefit from the latest robust repair rules.
"""

import os
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from updates.update_character_info import repair_character_data
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_path_manager import ModulePathManager

def repair_all():
    print("Starting repair of all character sheets...")
    
    # 1. Global characters
    char_dir = Path("characters")
    if char_dir.exists():
        for char_file in char_dir.glob("*.json"):
            # Skip backups
            if ".backup" in char_file.name or ".bak" in char_file.name:
                continue
            
            repair_file(char_file)

    # 2. Module characters
    modules_dir = Path("modules")
    if modules_dir.exists():
        for module_dir in modules_dir.iterdir():
            if module_dir.is_dir():
                char_subdir = module_dir / "characters"
                if char_subdir.exists():
                    for char_file in char_subdir.glob("*.json"):
                        if ".backup" in char_file.name or ".bak" in char_file.name:
                            continue
                        repair_file(char_file)

def repair_file(file_path):
    print(f"  Repairing {file_path}...")
    try:
        data = safe_read_json(str(file_path))
        if not data:
            print(f"    [SKIP] Could not read or empty: {file_path}")
            return
            
        repaired_data = repair_character_data(data)
        
        # Check if anything changed by comparing JSON strings (simple but effective for this)
        if json.dumps(data, sort_keys=True) != json.dumps(repaired_data, sort_keys=True):
            success = safe_write_json(str(file_path), repaired_data)
            if success:
                print(f"    [DONE] Repaired and saved.")
            else:
                print(f"    [ERROR] Failed to save {file_path}")
        else:
            print(f"    [OK] No repairs needed.")
            
    except Exception as e:
        print(f"    [ERROR] Unexpected error repairing {file_path}: {e}")

if __name__ == "__main__":
    repair_all()
    print("\nRepair process complete.")
