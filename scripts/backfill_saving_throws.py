# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Utility - Backfill missing saving throw proficiencies
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List


sys.path.append(str(Path(__file__).parent.parent))

from utils.file_operations import safe_read_json, safe_write_json
from utils.saving_throw_utils import get_class_fallback_saving_throws


TITLE_CASE_BY_KEY: Dict[str, str] = {
    "strength": "Strength",
    "dexterity": "Dexterity",
    "constitution": "Constitution",
    "intelligence": "Intelligence",
    "wisdom": "Wisdom",
    "charisma": "Charisma",
}

ABILITY_ORDER: List[str] = [
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
]


def _iter_character_files(include_module_characters: bool) -> Iterable[Path]:
    directories = [Path("characters")]
    if include_module_characters:
        modules_dir = Path("modules")
        if modules_dir.exists():
            for module_dir in modules_dir.iterdir():
                if module_dir.is_dir():
                    directories.append(module_dir / "characters")

    for directory in directories:
        if not directory.exists():
            continue
        for file_path in directory.glob("*.json"):
            file_name = file_path.name.lower()
            if ".backup" in file_name or file_name.endswith(".bak.json"):
                continue
            yield file_path


def _ordered_title_case_saves(fallback_keys: Iterable[str]) -> List[str]:
    fallback_set = set(fallback_keys)
    return [TITLE_CASE_BY_KEY[key] for key in ABILITY_ORDER if key in fallback_set]


def run_backfill(apply_changes: bool, include_module_characters: bool) -> int:
    scanned = 0
    updated = 0
    unchanged = 0
    skipped_unknown_class = 0
    failed = 0

    mode_text = "APPLY" if apply_changes else "DRY-RUN"
    print(f"Saving throw backfill mode: {mode_text}")

    for file_path in _iter_character_files(include_module_characters=include_module_characters):
        scanned += 1
        data = safe_read_json(str(file_path))
        if not isinstance(data, dict):
            failed += 1
            print(f"[ERROR] Could not read character JSON: {file_path}")
            continue

        existing_saves = data.get("savingThrows", [])
        if isinstance(existing_saves, list) and len(existing_saves) > 0:
            unchanged += 1
            print(f"[SKIP] Explicit savingThrows already present: {file_path}")
            continue

        fallback = get_class_fallback_saving_throws(data.get("class", ""))
        if not fallback:
            skipped_unknown_class += 1
            print(f"[SKIP] No fallback for class '{data.get('class', '')}': {file_path}")
            continue

        new_saves = _ordered_title_case_saves(fallback)
        print(f"[PLAN] {file_path} -> savingThrows={new_saves}")

        if apply_changes:
            data["savingThrows"] = new_saves
            if safe_write_json(str(file_path), data):
                updated += 1
                print(f"[DONE] Updated {file_path}")
            else:
                failed += 1
                print(f"[ERROR] Failed writing {file_path}")

    print("\nBackfill summary")
    print(f"- scanned: {scanned}")
    print(f"- updated: {updated}")
    print(f"- unchanged (explicit saves present): {unchanged}")
    print(f"- skipped (unknown class fallback): {skipped_unknown_class}")
    print(f"- failed: {failed}")

    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill missing savingThrows using deterministic class defaults."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to files. Omit for dry-run report mode.",
    )
    parser.add_argument(
        "--include-module-characters",
        action="store_true",
        help="Also scan modules/*/characters/*.json files.",
    )
    args = parser.parse_args()

    return run_backfill(
        apply_changes=args.apply,
        include_module_characters=args.include_module_characters,
    )


if __name__ == "__main__":
    raise SystemExit(main())
