#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""NeverEndingQuest - Background Feature Placeholder Remediation Script

USAGE:
    python scripts/remediate_background_feature_placeholders.py --dry-run
    python scripts/remediate_background_feature_placeholders.py --apply

DESCRIPTION:
    Scans character JSON files for generic background feature placeholders
    and remediates them using deterministic background feature suggestions.
    
    By default (--dry-run), the script reports planned changes without
    modifying files. Use --apply to write changes.

MODES:
    --dry-run   Report planned changes without writing (default mode)
    --apply     Apply remediation changes to character files

SUPPORTED BACKGROUNDS:
    - acolyte -> Shelter of the Faithful
    - criminal -> Criminal Contact
    - folk hero -> Rustic Hospitality
    - noble -> Position of Privilege
    - sage -> Researcher
    - soldier -> Military Rank

PHILOSOPHY:
    - Only updates blank or generic placeholder values
    - Preserves authored non-generic content
    - Leaves unknown backgrounds unchanged
    - Idempotent (second run produces zero changes)
    - Mechanical fields never modified
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.character_creation_audit import (
    is_generic_background_feature_name,
    is_generic_background_feature_description,
    apply_background_feature_suggestion_if_generic,
)
from utils.file_operations import safe_read_json, safe_write_json
from utils.enhanced_logger import info, warning, error


def scan_character_files(characters_dir: str = "characters") -> List[str]:
    """Get list of character JSON files, excluding backups."""
    files = []
    if not os.path.exists(characters_dir):
        return files
    
    for filename in os.listdir(characters_dir):
        # Only .json files, exclude backups
        if not filename.endswith(".json"):
            continue
        if ".backup_update_" in filename:
            continue
        files.append(os.path.join(characters_dir, filename))
    
    return sorted(files)


def analyze_character(filepath: str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Analyze a character file for remediation needs.
    
    Returns:
        Tuple of (status, original_data, updates):
        - status: "changed", "skipped", or "error"
        - original_data: the character data dict (or {} if error)
        - updates: dict with keys indicating what would change
    
    FAIL-OPEN: All exceptions are caught, categorized, and returned as error status.
    """
    updates = {
        "name_changed": False,
        "description_changed": False,
        "old_name": "",
        "new_name": "",
        "old_description": "",
        "new_description": "",
        "error_message": "",
        "error_category": None,  # "read", "analysis", or None
    }
    
    try:
        # READ PHASE: Load character data
        try:
            data = safe_read_json(filepath)
        except Exception as read_err:
            # READ ERROR: File read/parsing failed
            updates["error_message"] = f"Read error: {read_err}"
            updates["error_category"] = "read"
            return ("error", {}, updates)
        
        if not data:
            # Empty file or missing data
            updates["error_message"] = "Character file is empty or unreadable"
            updates["error_category"] = "read"
            return ("error", {}, updates)
        
        if not isinstance(data, dict):
            # Invalid JSON structure
            updates["error_message"] = f"Invalid character data type: {type(data).__name__}"
            updates["error_category"] = "read"
            return ("error", {}, updates)
        
        # ANALYSIS PHASE: Determine if remediation needed
        try:
            background = data.get("background", "")
            bg_feature = data.get("backgroundFeature", {})
            current_name = bg_feature.get("name", "")
            current_description = bg_feature.get("description", "")
            
            # Check if remediation needed
            name_is_generic = is_generic_background_feature_name(current_name)
            desc_is_generic = is_generic_background_feature_description(current_description)
            
            if not name_is_generic and not desc_is_generic:
                return ("skipped", data, updates)
            
            # Get deterministic suggestion
            suggestion = apply_background_feature_suggestion_if_generic(
                background, current_name, current_description
            )
            
            updates["old_name"] = str(current_name)
            updates["new_name"] = suggestion["name"]
            updates["old_description"] = str(current_description)
            updates["new_description"] = suggestion["description"]
            
            # Track what would change
            if name_is_generic and suggestion["name"] != str(current_name).strip():
                updates["name_changed"] = True
            
            if desc_is_generic and suggestion["description"] != str(current_description).strip():
                updates["description_changed"] = True
            
            # If no actual changes (e.g., unknown background), skip
            if not updates["name_changed"] and not updates["description_changed"]:
                return ("skipped", data, updates)
            
            return ("changed", data, updates)
            
        except Exception as analysis_err:
            # ANALYSIS ERROR: Logic/processing failure
            updates["error_message"] = f"Analysis error: {analysis_err}"
            updates["error_category"] = "analysis"
            return ("error", {}, updates)
        
    except Exception as outer_err:
        # Unexpected outer exception - also treated as analysis error
        updates["error_message"] = f"Unexpected exception: {outer_err}"
        updates["error_category"] = "analysis"
        return ("error", {}, updates)


def remediate_file(filepath: str, dry_run: bool = True) -> Tuple[str, Dict[str, Any], Optional[str]]:
    """Analyze and optionally remediate a single character file.
    
    Returns:
        Tuple of (status, details, error_type) where:
        - status: "changed", "skipped", or "error"
        - details: update information for reporting
        - error_type: None, "read", "analysis", or "write" (for error categorization)
    
    FAIL-OPEN GUARANTEE: All exceptions are caught, errors are logged,
    and processing continues. No single file failure aborts the run.
    """
    error_type = None
    
    try:
        status, data, updates = analyze_character(filepath)
        
        if status == "error":
            error_type = updates.get("error_category", "analysis")
            error(f"[ERROR] {filepath}: {updates['error_message']}")
            return (status, updates, error_type)
        
        if status == "skipped":
            info(f"[SKIP] {filepath}: No generic placeholders detected")
            return (status, updates, None)
        
        if status == "changed":
            filename = os.path.basename(filepath)
            changes = []
            if updates["name_changed"]:
                changes.append(f"name: '{updates['old_name']}' -> '{updates['new_name']}'")
            if updates["description_changed"]:
                changes.append(f"desc: updated")
            
            info(f"[CHANGE] {filename}: {', '.join(changes)}")
            
            if not dry_run:
                # Apply the changes
                if "backgroundFeature" not in data:
                    data["backgroundFeature"] = {}
                
                if updates["name_changed"]:
                    data["backgroundFeature"]["name"] = updates["new_name"]
                
                if updates["description_changed"]:
                    data["backgroundFeature"]["description"] = updates["new_description"]
                
                # ATOMIC WRITE: Use safe_write_json for guaranteed atomic operation
                success = safe_write_json(filepath, data)
                if not success:
                    error_type = "write"
                    error(f"[ERROR] {filepath}: Failed to write changes (atomic write failed)")
                    return ("error", updates, error_type)
                
                info(f"[PASS] {filename}: Changes applied atomically")
            else:
                info(f"[DRY-RUN] {filename}: Would apply changes (use --apply to execute)")
        
        return (status, updates, None)
        
    except Exception as e:
        # FAIL-OPEN: Catch all unexpected exceptions, log error, continue
        error_type = "analysis"
        error_msg = f"Unexpected exception processing {filepath}: {e}"
        error(f"[ERROR] {error_msg}")
        return ("error", {"error_message": error_msg}, error_type)


def main():
    parser = argparse.ArgumentParser(
        description="Remediate generic background feature placeholders in character files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
    # Show what would change (no writes)
    python scripts/remediate_background_feature_placeholders.py --dry-run
    
    # Apply remediation changes
    python scripts/remediate_background_feature_placeholders.py --apply
        """,
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report planned changes without writing (default)",
    )
    
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply remediation changes to character files",
    )
    
    args = parser.parse_args()
    
    # If --apply is set, disable dry-run
    dry_run = not args.apply
    
    if dry_run:
        print("=" * 70)
        print("BACKGROUND FEATURE REMEDIATION - DRY RUN MODE")
        print("No files will be modified. Use --apply to execute changes.")
        print("=" * 70)
    else:
        print("=" * 70)
        print("BACKGROUND FEATURE REMEDIATION - APPLY MODE")
        print("Changes will be written to character files!")
        print("=" * 70)
    
    print()
    
    # Scan character files
    character_files = scan_character_files()
    total_files = len(character_files)
    
    print(f"Scanning {total_files} character files...")
    print()
    
    # Track statistics with error subtypes for observability
    stats = {
        "scanned": total_files,
        "changed": 0,
        "skipped": 0,
        "errors": 0,
        "read_errors": 0,      # File read/parsing failures
        "analysis_errors": 0,  # Processing/logic failures
        "write_errors": 0,     # Atomic write failures (apply mode only)
    }
    
    # Process each file with fail-open guarantee
    for filepath in character_files:
        status, details, error_type = remediate_file(filepath, dry_run=dry_run)
        stats[status] += 1
        
        # Track error subtypes for detailed reporting
        if status == "error" and error_type:
            if error_type == "read":
                stats["read_errors"] += 1
            elif error_type == "write":
                stats["write_errors"] += 1
            elif error_type == "analysis":
                stats["analysis_errors"] += 1
    
    # Print summary
    print()
    print("=" * 70)
    print("REMEDIATION SUMMARY")
    print("=" * 70)
    print(f"Files scanned:         {stats['scanned']}")
    print(f"Files changed:         {stats['changed']}")
    print(f"Files skipped:         {stats['skipped']}")
    print(f"Files with errors:     {stats['errors']}")
    
    # Show error subtypes if any errors occurred
    if stats['errors'] > 0:
        print()
        print("Error breakdown:")
        if stats['read_errors'] > 0:
            print(f"  - Read/parsing errors:     {stats['read_errors']}")
        if stats['analysis_errors'] > 0:
            print(f"  - Analysis/processing:     {stats['analysis_errors']}")
        if stats['write_errors'] > 0:
            print(f"  - Atomic write failures:   {stats['write_errors']}")
    
    print()
    
    if dry_run:
        print("Dry run complete. No files were modified.")
        if stats["changed"] > 0:
            print(f"Run with --apply to execute {stats['changed']} remediation(s).")
    else:
        print("Remediation complete. Changes have been applied.")
    
    # Return non-zero exit code if errors occurred
    if stats["errors"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
