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

from utils.module_monster_authority import (
    discover_module_authored_monster_names,
    load_monster_compendium_lookup,
    materialize_authorized_monster_file,
)


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
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    return slug


def _load_monster_compendium() -> Dict[str, Any]:
    """Load the global monster compendium and create normalized lookup.

    Handles both dict-form (keyed by slug) and list-form compendium structures
    for compatibility with different bestiary formats.
    """
    return load_monster_compendium_lookup("data/bestiary/monster_compendium.json")


def _load_monsters_seed(module_path: Path) -> List[Any]:
    """Load monsters_seed.json for a module.

    Returns list of monster entries from seed file.
    Supports both string list ["name", ...] and dict list [{"name": ...}, ...].
    """
    seed_path = module_path / "monsters_seed.json"
    if not seed_path.exists():
        return []

    try:
        with open(seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("monsters", [])
    except Exception:
        return []


def _extract_seed_monster_names(seed_monsters: List[Any]) -> List[str]:
    """Extract display names from seed list entries."""
    names: List[str] = []
    for monster_entry in seed_monsters:
        if isinstance(monster_entry, str):
            monster_name = monster_entry
        elif isinstance(monster_entry, dict):
            monster_name = str(monster_entry.get("name") or "")
        else:
            monster_name = ""

        cleaned = monster_name.strip()
        if cleaned:
            names.append(cleaned)
    return names


def _build_hydration_candidates(module_slug: str, module_path: Path) -> Dict[str, Any]:
    """Build deterministic hydration candidates from seeds + authored fallback."""
    seed_entries = _load_monsters_seed(module_path)
    seed_names = _extract_seed_monster_names(seed_entries)
    authored_names = discover_module_authored_monster_names(module_slug)

    ordered_names: List[str] = []
    seen_slugs = set()
    for name in seed_names + authored_names:
        slug = _normalize_monster_name(name)
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        ordered_names.append(name)

    return {
        "seed_count": len(seed_names),
        "authored_count": len(authored_names),
        "seed_missing_fallback_used": len(seed_names) == 0 and len(authored_names) > 0,
        "candidates": ordered_names,
    }


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
        temp_file = monster_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
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
        "hydration_modes": {
            "existing": 0,
            "reuse": 0,
            "bestiary": 0,
            "generated": 0,
        },
        "blocker_classes": {},
        "blocked_count": 0,
        "monster_results": [],
        "candidate_sources": {
            "seed_count": 0,
            "authored_count": 0,
            "seed_missing_fallback_used": False,
        },
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
    current_dir = Path(__file__).resolve().parent
    monster_builder_path = str(
        (current_dir.parent / "core" / "generators" / "monster_builder.py").resolve()
    )

    candidate_bundle = _build_hydration_candidates(module_slug, module_path)
    result["candidate_sources"] = {
        "seed_count": int(candidate_bundle.get("seed_count", 0) or 0),
        "authored_count": int(candidate_bundle.get("authored_count", 0) or 0),
        "seed_missing_fallback_used": bool(
            candidate_bundle.get("seed_missing_fallback_used")
        ),
    }
    candidate_monsters = list(candidate_bundle.get("candidates") or [])
    if not candidate_monsters:
        return result

    for monster_name in candidate_monsters:
        resolution = materialize_authorized_monster_file(
            module_slug,
            monster_name,
            monster_builder_path,
            compendium_lookup=compendium,
            allow_generation=not dry_run,
        )

        canonical_slug = str(
            resolution.get("canonical_slug")
            or resolution.get("slug")
            or _normalize_monster_name(monster_name)
        )
        outcome: Dict[str, Any] = {
            "requested_name": monster_name,
            "requested_slug": _normalize_monster_name(monster_name),
            "canonical_slug": canonical_slug,
            "canonical_name": str(resolution.get("canonical_name") or monster_name),
            "ok": bool(resolution.get("ok")),
            "mode": str(resolution.get("source") or "failed"),
            "blocker_class": "",
            "error_message": str(resolution.get("error_message") or ""),
            "resolution_mode": str(resolution.get("resolution_mode") or ""),
            "bestiary_missing": bool(resolution.get("bestiary_missing", False)),
        }

        if outcome["bestiary_missing"]:
            result["missing_in_bestiary_count"] += 1
            result["missing_names"].append(monster_name)

        if resolution.get("ok"):
            mode = str(resolution.get("source") or "existing")
            if mode not in result["hydration_modes"]:
                result["hydration_modes"][mode] = 0
            result["hydration_modes"][mode] += 1

            if mode == "existing":
                result["skipped_existing_count"] += 1
            else:
                result["created_count"] += 1
        else:
            blocker_class = str(
                resolution.get("error_class") or "authorized_monster_hydration_failed"
            )
            outcome["blocker_class"] = blocker_class
            result["blocked_count"] += 1
            result["blocker_classes"][blocker_class] = (
                int(result["blocker_classes"].get(blocker_class, 0) or 0) + 1
            )

        result["monster_results"].append(outcome)

    # Strict mode check
    if strict and result["blocked_count"] > 0:
        result["status"] = "failed"
        result["error"] = (
            f"Strict mode: {result['blocked_count']} monster(s) blocked in hydration: "
            f"{', '.join(sorted(result['blocker_classes'].keys())[:5])}"
        )
    elif result["blocked_count"] > 0:
        result["status"] = "degraded"
        result["note"] = (
            f"{result['blocked_count']} monsters remain blocked after hydration"
        )
    elif result["missing_in_bestiary_count"] > 0:
        # Degraded but not failed
        result["note"] = (
            f"{result['missing_in_bestiary_count']} monsters could not be resolved"
        )

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
    print(f"  Blocked: {payload.get('blocked_count', 0)}")

    hydration_modes = payload.get("hydration_modes") or {}
    if isinstance(hydration_modes, dict) and hydration_modes:
        print("  Hydration modes:")
        for mode in sorted(hydration_modes.keys()):
            print(f"    - {mode}: {hydration_modes[mode]}")

    blocker_classes = payload.get("blocker_classes") or {}
    if isinstance(blocker_classes, dict) and blocker_classes:
        print("  Blocker classes:")
        for blocker, count in sorted(blocker_classes.items()):
            print(f"    - {blocker}: {count}")

    if payload.get("path_conflicts_detected", 0) > 0:
        print(f"  Path conflicts detected: {payload['path_conflicts_detected']}")
        print(f"  Path conflicts repaired: {payload['path_conflicts_repaired']}")

    if payload.get("missing_names"):
        print("\nMissing monsters (not in bestiary):")
        for name in payload["missing_names"]:
            print(f"  - {name}")

    if payload.get("conflict_paths"):
        print("\nPath conflicts (repaired):")
        for path in payload["conflict_paths"]:
            print(f"  - {path}")

    if payload.get("error"):
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
