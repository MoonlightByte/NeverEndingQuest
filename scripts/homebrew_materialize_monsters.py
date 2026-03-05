# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Homebrew Monster Materialization
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Materializes module-local monster stat files from bestiary-backed seed data.

TABLETOP MODE: Added to support deterministic combat readiness for ingested modules.
After strict ingest creates monsters_seed.json, this script resolves each monster
against data/bestiary/monster_compendium.json and writes module-local monsters/*.json
files required by fail-closed tabletop combat loader paths.

Usage:
    python scripts/homebrew_materialize_monsters.py --module <module_slug> [--strict] [--dry-run]

Returns structured summary with counts for created/skipped/missing and path conflict repairs.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


def _normalize_monster_name(name: str) -> str:
    """Normalize monster name to slug format matching runtime combat lookup.
    
    Lowercase, strip spaces, convert spaces to underscores,
    remove apostrophes and non-alphanumeric characters.
    """
    if not name:
        return ""
    # Lowercase and strip
    slug = name.lower().strip()
    # Remove apostrophes
    slug = slug.replace("'", "").replace('"', "")
    # Replace spaces and hyphens with underscores
    slug = slug.replace(" ", "_").replace("-", "_")
    # Remove any remaining non-alphanumeric except underscore
    slug = ''.join(c for c in slug if c.isalnum() or c == '_')
    return slug


def _load_monster_compendium() -> Dict[str, Any]:
    """Load the global monster compendium and create normalized lookup.
    
    Handles both dict-form (keyed by slug) and list-form compendium structures
    for compatibility with different bestiary formats.
    """
    compendium_path = Path("data/bestiary/monster_compendium.json")
    if not compendium_path.exists():
        return {}
        
    try:
        with open(compendium_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        monsters_data = data.get("monsters", {})
        lookup = {}
        
        # Handle dict-form compendium (slug -> monster_data)
        if isinstance(monsters_data, dict):
            for slug, monster in monsters_data.items():
                if isinstance(monster, dict) and monster.get("name"):
                    normalized = _normalize_monster_name(monster["name"])
                    lookup[normalized] = monster
        # Handle list-form compendium for compatibility
        elif isinstance(monsters_data, list):
            for monster in monsters_data:
                if isinstance(monster, dict):
                    name = monster.get("name", "")
                    if name:
                        normalized = _normalize_monster_name(name)
                        lookup[normalized] = monster
                
        return lookup
        
    except Exception:
        return {}


def _load_monsters_seed(module_path: Path) -> List[Any]:
    """Load monsters_seed.json for a module.
    
    Returns list of monster entries from seed file.
    Supports both string list ["name", ...] and dict list [{"name": ...}, ...].
    """
    seed_path = module_path / "monsters_seed.json"
    if not seed_path.exists():
        return []
    
    try:
        with open(seed_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("monsters", [])
    except Exception:
        return []


def _repair_path_conflict(
    monster_file: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Auto-repair when target path exists as a directory instead of file.
    
    TABLETOP MODE: Auto-repair moves conflicting directory to archive suffix,
    then allows writing the intended JSON file.
    
    Returns repair report dict with status and paths.
    """
    repair_result = {
        "repaired": False,
        "conflict_path": str(monster_file),
        "archive_path": None,
        "error": None,
    }
    
    if not monster_file.is_dir():
        # No conflict - nothing to repair
        return repair_result
    
    # Conflict detected: path is a directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{monster_file.stem}.json_conflict_{timestamp}"
    archive_path = monster_file.parent / archive_name
    
    try:
        if not dry_run:
            # Move the conflicting directory to archive location
            monster_file.rename(archive_path)
        
        repair_result["repaired"] = True
        repair_result["archive_path"] = str(archive_path)
        
    except Exception as e:
        repair_result["error"] = str(e)
    
    return repair_result


def _write_monster_file(
    module_path: Path,
    monster_slug: str,
    monster_data: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Write monster stat file to module monsters/ directory with auto-repair support.
    
    Creates monsters/ directory if needed.
    Auto-repairs path conflicts (directory at JSON path).
    
    Returns dict with success status and repair info.
    """
    result = {
        "written": False,
        "skipped": False,
        "repair": None,
        "error": None,
    }
    
    monsters_dir = module_path / "monsters"
    
    if not dry_run:
        monsters_dir.mkdir(parents=True, exist_ok=True)
    
    monster_file = monsters_dir / f"{monster_slug}.json"
    
    # Check for path conflict (directory at target path)
    if monster_file.is_dir():
        repair = _repair_path_conflict(monster_file, dry_run)
        result["repair"] = repair
        if not repair["repaired"] and not dry_run:
            result["error"] = f"Could not repair path conflict: {repair.get('error')}"
            return result
    elif monster_file.exists():
        # File already exists - skip
        result["skipped"] = True
        return result
    
    if dry_run:
        # In dry-run, report success if no conflict or repairable
        result["written"] = True
        return result
    
    try:
        # Write with atomic pattern
        temp_file = monster_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(monster_data, f, indent=2, ensure_ascii=False)
        temp_file.rename(monster_file)
        result["written"] = True
    except Exception as e:
        result["error"] = str(e)
    
    return result


def materialize_monsters(
    module_slug: str,
    strict: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Materialize module-local monster stat files from bestiary seeds.

    TABLETOP MODE: Added for combat readiness - creates module-specific monster
    stat files from bestiary so tabletop fail-closed combat can load encounters.
    """
    result = {
        "status": "success",
        "created_count": 0,
        "skipped_existing_count": 0,
        "missing_in_bestiary_count": 0,
        "missing_names": [],
        "path_conflicts_detected": 0,
        "path_conflicts_repaired": 0,
        "conflict_paths": [],
        "module_path": None,
        "error": None,
    }

    # Resolve module path
    module_path = Path("modules") / module_slug
    if not module_path.exists():
        result["status"] = "failed"
        result["error"] = f"Module not found: {module_path}"
        return result

    result["module_path"] = str(module_path)

    # Load dependencies
    compendium = _load_monster_compendium()
    
    seed_monsters = _load_monsters_seed(module_path)
    if not seed_monsters:
        # No monsters to materialize - this is OK
        return result
    
    # Process each seed monster
    for monster_entry in seed_monsters:
        # Support both string names and dict entries
        if isinstance(monster_entry, str):
            monster_name = monster_entry
        elif isinstance(monster_entry, dict):
            monster_name = monster_entry.get("name", "")
        else:
            continue
        
        if not monster_name:
            continue
        
        monster_slug = _normalize_monster_name(monster_name)
        if not monster_slug:
            continue
        
        # Look up in compendium
        bestiary_entry = compendium.get(monster_slug)
        
        if not bestiary_entry:
            # Not in bestiary - track as missing
            result["missing_in_bestiary_count"] += 1
            result["missing_names"].append(monster_name)
            continue
        
        # Materialize the monster file
        write_result = _write_monster_file(
            module_path,
            monster_slug,
            bestiary_entry,
            dry_run=dry_run,
        )
        
        if write_result.get("written"):
            result["created_count"] += 1
        elif write_result.get("skipped"):
            result["skipped_existing_count"] += 1
        
        # Track path conflicts
        repair = write_result.get("repair")
        if repair:
            result["path_conflicts_detected"] += 1
            if repair.get("repaired"):
                result["path_conflicts_repaired"] += 1
            result["conflict_paths"].append(repair["conflict_path"])
    
    # Strict mode check
    if strict and result["missing_in_bestiary_count"] > 0:
        result["status"] = "failed"
        result["error"] = (
            f"Strict mode: {result['missing_in_bestiary_count']} monster(s) not found in bestiary: "
            f"{', '.join(result['missing_names'][:5])}"
        )
    elif result["missing_in_bestiary_count"] > 0:
        # Degraded but not failed
        result["note"] = f"{result['missing_in_bestiary_count']} monsters could not be resolved"
    
    return result


def _create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="homebrew_materialize_monsters",
        description="Materialize module-local monster stat files from bestiary seeds",
    )
    parser.add_argument(
        "--module",
        type=str,
        required=True,
        help="Module slug (directory name under modules/)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Fail if any seed monster is not found in bestiary",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be done without writing files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output JSON result",
    )
    return parser


def _print_json_or_text(payload: Dict[str, Any], use_json: bool) -> None:
    """Print result as JSON or human-readable text."""
    if use_json:
        print(json.dumps(payload, indent=2))
        return
    
    # Text output
    print(f"Module: {payload.get('module_path', 'N/A')}")
    print(f"Status: {payload.get('status', 'unknown')}")
    print(f"  Created: {payload.get('created_count', 0)}")
    print(f"  Skipped (existing): {payload.get('skipped_existing_count', 0)}")
    print(f"  Missing in bestiary: {payload.get('missing_in_bestiary_count', 0)}")
    
    if payload.get('path_conflicts_detected', 0) > 0:
        print(f"  Path conflicts detected: {payload['path_conflicts_detected']}")
        print(f"  Path conflicts repaired: {payload['path_conflicts_repaired']}")
    
    if payload.get('missing_names'):
        print("\nMissing monsters (not in bestiary):")
        for name in payload['missing_names']:
            print(f"  - {name}")
    
    if payload.get('conflict_paths'):
        print("\nPath conflicts (repaired):")
        for path in payload['conflict_paths']:
            print(f"  - {path}")
    
    if payload.get('error'):
        print(f"\nError: {payload['error']}")


def main() -> None:
    """Main entry point."""
    parser = _create_parser()
    args = parser.parse_args()
    
    result = materialize_monsters(
        module_slug=args.module,
        strict=args.strict,
        dry_run=args.dry_run,
    )
    
    _print_json_or_text(result, args.json)
    
    # Exit non-zero on failure
    if result["status"] == "failed":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
