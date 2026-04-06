# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Session diary remediation utility.

Rebuilds stored diary summaries from sanitized checkpoint source windows.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH
from core.memory.session_diary import remediate_diary_entries


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Rebuild existing diary rows using the improved concise recap pipeline.",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_MEMORY_DB_PATH,
        help=f"Path to memory DB (default: {DEFAULT_MEMORY_DB_PATH})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates. Default is dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of rows to scan (0 = all).",
    )
    parser.add_argument(
        "--confirmed-only",
        action="store_true",
        help="Remediate confirmed rows only.",
    )
    parser.add_argument(
        "--draft-only",
        action="store_true",
        help="Remediate draft rows only.",
    )
    return parser.parse_args()


def main() -> int:
    """Run remediation and print deterministic summary."""
    args = parse_args()

    include_draft = True
    include_confirmed = True
    if args.confirmed_only and not args.draft_only:
        include_draft = False
    if args.draft_only and not args.confirmed_only:
        include_confirmed = False

    result = remediate_diary_entries(
        db_path=args.db,
        include_draft=include_draft,
        include_confirmed=include_confirmed,
        dry_run=not args.apply,
        limit=max(0, int(args.limit or 0)),
    )

    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))

    if result.get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
