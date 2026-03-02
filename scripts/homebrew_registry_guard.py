# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Registry Guard
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Developer-only utility for duplicate checks, registry presence verification,
and safe module removal with backup.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# 1. Standard library imports
import argparse
import difflib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add project root for internal imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 3. Internal imports
from utils.file_operations import safe_write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "modules" / "world_registry.json"
MODULES_ROOT = REPO_ROOT / "modules"
BACKUP_ROOT = MODULES_ROOT / "backups"


def _load_registry() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Registry not found: {REGISTRY_PATH}")
    with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_text(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum() or ch.isspace()).strip()


def _extract_module_title(module_meta: Dict[str, Any], fallback_slug: str) -> str:
    title_candidates = [
        module_meta.get("moduleName", ""),
        module_meta.get("title", ""),
        module_meta.get("description", ""),
        fallback_slug,
    ]
    for candidate in title_candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return fallback_slug


def check_duplicate(slug: str, similarity_threshold: float = 0.85) -> Dict[str, Any]:
    """Check registry/folder conflicts for proposed module slug."""
    registry = _load_registry()
    modules = registry.get("modules", {})

    conflicts: List[Dict[str, Any]] = []

    if slug in modules:
        conflicts.append(
            {
                "type": "exact_slug",
                "existing_slug": slug,
                "existing_title": _extract_module_title(modules[slug], slug),
                "similarity": 1.0,
            }
        )

    requested_norm = _normalize_text(slug.replace("_", " "))
    for existing_slug, meta in modules.items():
        existing_title = _extract_module_title(meta, existing_slug)
        existing_norm = _normalize_text(existing_title.replace("_", " "))
        if not requested_norm or not existing_norm:
            continue

        similarity = difflib.SequenceMatcher(a=requested_norm, b=existing_norm).ratio()
        if similarity >= similarity_threshold and existing_slug != slug:
            conflicts.append(
                {
                    "type": "similar_title",
                    "existing_slug": existing_slug,
                    "existing_title": existing_title,
                    "similarity": round(similarity, 4),
                }
            )

    module_folder = MODULES_ROOT / slug
    if module_folder.exists() and module_folder.is_dir():
        conflicts.append(
            {
                "type": "folder_exists",
                "existing_slug": slug,
                "existing_title": slug,
                "similarity": 1.0,
            }
        )

    return {
        "safe_to_proceed": len(conflicts) == 0,
        "conflicts": conflicts,
    }


def verify_present(slug: str) -> Dict[str, Any]:
    """Verify slug is properly present in registry and filesystem."""
    registry = _load_registry()
    modules = registry.get("modules", {})
    areas = registry.get("areas", {})

    present = slug in modules
    module_folder = MODULES_ROOT / slug
    folder_exists = module_folder.exists() and module_folder.is_dir()

    area_ids = [area_id for area_id, area_meta in areas.items() if area_meta.get("module") == slug]

    encounters_dir = module_folder / "encounters"
    has_encounters = encounters_dir.exists() and any(encounters_dir.glob("*.json"))

    module_meta = modules.get(slug, {}) if present else {}

    return {
        "present": present,
        "module_key": slug,
        "folder_exists": folder_exists,
        "areas_count": len(area_ids),
        "area_ids": area_ids,
        "has_encounters": bool(has_encounters),
        "added_date": module_meta.get("addedDate"),
    }


def _backup_registry() -> Path:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_ROOT / f"world_registry.pre_remove.{timestamp}.json"
    backup_path.write_text(REGISTRY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def remove_module(slug: str, remove_folder: bool = False) -> Dict[str, Any]:
    """Safely remove module from registry and optionally delete folder."""
    registry = _load_registry()
    modules = registry.get("modules", {})
    areas = registry.get("areas", {})

    if slug not in modules:
        return {
            "removed": False,
            "backup_path": None,
            "registry_updated": False,
            "folder_removed": False,
            "error": f"Module not present in registry: {slug}",
        }

    backup_path = _backup_registry()

    del modules[slug]

    removed_area_ids = []
    for area_id, area_meta in list(areas.items()):
        if area_meta.get("module") == slug:
            del areas[area_id]
            removed_area_ids.append(area_id)

    registry["lastUpdated"] = datetime.now().isoformat()
    safe_write_json(str(REGISTRY_PATH), registry)

    folder_removed = False
    module_folder = MODULES_ROOT / slug
    if remove_folder and module_folder.exists() and module_folder.is_dir():
        import shutil

        shutil.rmtree(module_folder)
        folder_removed = True

    return {
        "removed": True,
        "backup_path": str(backup_path),
        "registry_updated": True,
        "folder_removed": folder_removed,
        "removed_area_ids": removed_area_ids,
    }


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_registry_guard",
        description="Developer-only registry guard for Homebrew ingestion",
    )
    parser.add_argument("--slug", type=str, required=True, help="Module slug")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--check-duplicate", action="store_true", help="Check slug/title/folder conflicts")
    mode_group.add_argument("--verify-present", action="store_true", help="Verify module registration presence")
    mode_group.add_argument("--remove", action="store_true", help="Remove module from registry")

    parser.add_argument("--remove-folder", action="store_true", default=False, help="With --remove, also delete module folder")
    parser.add_argument("--json", action="store_true", default=False, help="Output JSON")
    return parser


def _print_json_or_text(payload: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print("=" * 60)
        print("REGISTRY GUARD")
        print("=" * 60)
        for key, value in payload.items():
            print(f"{key}: {value}")


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    try:
        if args.check_duplicate:
            payload = check_duplicate(args.slug)
            _print_json_or_text(payload, args.json)
            sys.exit(0 if payload.get("safe_to_proceed") else 3)

        if args.verify_present:
            payload = verify_present(args.slug)
            _print_json_or_text(payload, args.json)
            sys.exit(0 if payload.get("present") else 4)

        payload = remove_module(args.slug, remove_folder=args.remove_folder)
        _print_json_or_text(payload, args.json)
        sys.exit(0 if payload.get("removed") else 5)

    except FileNotFoundError as exc:
        payload = {"error": str(exc)}
        _print_json_or_text(payload, args.json)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        payload = {"error": f"Registry parse failed: {exc}"}
        _print_json_or_text(payload, args.json)
        sys.exit(2)
    except Exception as exc:
        payload = {"error": str(exc)}
        _print_json_or_text(payload, args.json)
        sys.exit(5)


if __name__ == "__main__":
    main()
