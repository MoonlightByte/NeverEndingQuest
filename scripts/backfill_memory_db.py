#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Memory DB tooling for backfill and portability workflows.

Usage:
    # Backfill
    python3 scripts/backfill_memory_db.py
    python3 scripts/backfill_memory_db.py --sources journal,combat --dry-run

    # Export package
    python3 scripts/backfill_memory_db.py --export-package exports/campaign_001

    # Import package (safe default: fails if target DB exists)
    python3 scripts/backfill_memory_db.py --import-package exports/campaign_001 --db-path data/memory.db
    python3 scripts/backfill_memory_db.py --import-package exports/campaign_001 --db-path data/memory.db --dry-run
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH
from core.memory.memory_ingest import backfill_memory_db_from_histories
from core.memory.memory_portability import export_memory_db_package, import_memory_db_package, validate_memory_package


ALLOWED_SOURCES = ("journal", "conversation", "combat")


def parse_sources_arg(raw_sources: str) -> list[str]:
    """Parse and validate CSV source selector."""
    parsed = [item.strip().lower() for item in str(raw_sources or "").split(",") if item.strip()]
    if not parsed:
        return list(ALLOWED_SOURCES)

    invalid = [item for item in parsed if item not in ALLOWED_SOURCES]
    if invalid:
        raise ValueError(
            "Invalid --sources values: "
            + ", ".join(sorted(invalid))
            + ". Allowed values: "
            + ", ".join(ALLOWED_SOURCES)
        )
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory DB backfill and portability tooling")
    parser.add_argument("--db-path", default=DEFAULT_MEMORY_DB_PATH, help="Path to memory SQLite DB")
    parser.add_argument("--journal-path", default="journal.json", help="Path to journal JSON")
    parser.add_argument(
        "--conversation-path",
        default="modules/conversation_history/conversation_history.json",
        help="Path to narrative conversation history JSON",
    )
    parser.add_argument(
        "--combat-path",
        default="modules/conversation_history/combat_conversation_history.json",
        help="Path to combat conversation history JSON",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include role=system messages from conversation histories",
    )
    parser.add_argument(
        "--sources",
        default=",".join(ALLOWED_SOURCES),
        help="CSV source selector for backfill: journal,conversation,combat",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Backfill: use temporary DB copy. Import: validate only without writing.",
    )
    parser.add_argument(
        "--export-package",
        default="",
        help="Export memory DB to package directory (DB copy + manifest)",
    )
    parser.add_argument(
        "--import-package",
        default="",
        help="Import memory DB package directory into --db-path",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing output/target in export/import workflows",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of entries per transaction batch for backfill (default: 50)",
    )
    args = parser.parse_args()

    if args.export_package and args.import_package:
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": "Choose only one mode: --export-package or --import-package",
                },
                indent=2,
            )
        )
        return 1

    # Export mode
    if args.export_package:
        result = export_memory_db_package(
            source_db_path=args.db_path,
            output_dir=args.export_package,
            overwrite=bool(args.overwrite),
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "success" else 1

    # Import mode
    if args.import_package:
        if args.dry_run:
            result = import_memory_db_package(
                package_dir=args.import_package,
                target_db_path=args.db_path,
                overwrite=bool(args.overwrite),
                dry_run=True,
            )
        else:
            # Validate first for clear diagnostics before write.
            validation = validate_memory_package(args.import_package)
            if validation.get("status") != "success":
                print(json.dumps(validation, indent=2))
                return 1
            result = import_memory_db_package(
                package_dir=args.import_package,
                target_db_path=args.db_path,
                overwrite=bool(args.overwrite),
                dry_run=False,
            )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "success" else 1

    try:
        selected_sources = parse_sources_arg(args.sources)
    except ValueError as parse_error:
        print(json.dumps({"status": "error", "message": str(parse_error)}, indent=2))
        return 1

    if args.batch_size <= 0:
        print(json.dumps({"status": "error", "message": f"--batch-size must be positive, got {args.batch_size}"}, indent=2))
        return 1

    db_path_to_use = args.db_path
    temp_dir = None
    if args.dry_run:
        temp_dir = tempfile.mkdtemp(prefix="neq_memory_backfill_dry_run_")
        db_path_to_use = os.path.join(temp_dir, "memory_dry_run.db")
        if os.path.exists(args.db_path):
            shutil.copy2(args.db_path, db_path_to_use)

    try:
        result = backfill_memory_db_from_histories(
            db_path=db_path_to_use,
            journal_path=args.journal_path,
            conversation_path=args.conversation_path,
            combat_history_path=args.combat_path,
            include_system_messages=bool(args.include_system),
            sources=selected_sources,
            batch_size=args.batch_size,
        )
        if args.dry_run:
            result["dry_run"] = True
            result["target_db_path"] = args.db_path
            result["temp_db_path"] = db_path_to_use
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "success" else 1
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
