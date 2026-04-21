#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Audit and rebuild strict-cache runtime media folders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.toolkit.pack_manager import PackManager


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit/rebuild web/static/media strict cache",
    )
    parser.add_argument(
        "--active-packs",
        default="",
        help="Comma-separated pack names override",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        default=False,
        help="Execute destructive rebuild (default: dry-run audit)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        default=False,
        help="Skip pre-rebuild backup snapshot",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit JSON output",
    )
    args = parser.parse_args()

    active_packs = None
    if args.active_packs.strip():
        active_packs = [
            item.strip()
            for item in args.active_packs.split(",")
            if item.strip()
        ]

    manager = PackManager()
    result = manager.rebuild_static_runtime_cache(
        active_packs=active_packs,
        create_backup=not args.no_backup,
        dry_run=not args.rebuild,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        action = result.get("action", "unknown")
        print(f"strict-cache action: {action}")
        if not result.get("success"):
            print(f"[ERROR] {result.get('error', 'unknown error')}")
            return 1

        audit = result.get("audit", {})
        for media_type in ("npcs", "monsters"):
            target = audit.get("targets", {}).get(media_type, {})
            counts = target.get("counts", {})
            print(
                f"- {media_type}: live={counts.get('live', 0)} "
                f"active_union={counts.get('active_union', 0)} "
                f"orphans={counts.get('orphaned', 0)} "
                f"collisions={counts.get('collisions', 0)}"
            )

        if action == "rebuild":
            backup = result.get("backup") or {}
            if backup.get("success"):
                print(f"backup: {backup.get('backup_name')}")
            targets = result.get("targets", {})
            for media_type in ("npcs", "monsters"):
                target = targets.get(media_type, {})
                print(
                    f"  rebuilt {media_type}: copied={target.get('copied', 0)} "
                    f"orphaned_removed={target.get('orphaned_removed', 0)}"
                )

    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
