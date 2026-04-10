# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Session diary rebuild utility.

Rebuilds confirmed diary entries in-place from journal chronology.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH
from core.memory.session_diary import (
    AI_CLIENTS_AVAILABLE,
    ENABLE_SESSION_DIARY_LLM,
    rebuild_diary_from_journal,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Rebuild session diary from journal chronology.",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_MEMORY_DB_PATH,
        help=f"Path to memory DB (default: {DEFAULT_MEMORY_DB_PATH})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates in place. Default is dry-run preview.",
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Allow deterministic fallback output when AI dependencies or providers are unavailable.",
    )
    return parser.parse_args()


def main() -> int:
    """Run diary rebuild and print deterministic JSON output."""
    args = parse_args()

    if (
        args.apply
        and ENABLE_SESSION_DIARY_LLM
        and not AI_CLIENTS_AVAILABLE
        and not args.allow_fallback
    ):
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": (
                        "Session diary rebuild requires .venv/bin/python with AI client dependencies. "
                        "Re-run with the project venv or pass --allow-fallback to accept deterministic degraded output."
                    ),
                    "db_path": args.db,
                    "dry_run": False,
                },
                indent=2,
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 1

    result = rebuild_diary_from_journal(
        db_path=args.db,
        dry_run=not args.apply,
        replace_existing=True,
    )
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    if result.get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
