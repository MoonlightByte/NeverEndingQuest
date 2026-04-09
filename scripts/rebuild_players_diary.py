# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Players diary markdown rebuild utility."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.players_diary import append_players_diary_from_journal, rebuild_players_diary_from_journal


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Manage players diary markdown artifact.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force full rebuild from all journal entries.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Default is dry-run preview.",
    )
    return parser.parse_args()


def main() -> int:
    """Run players diary append/rebuild and print result."""
    args = parse_args()
    if args.rebuild:
        result = rebuild_players_diary_from_journal(dry_run=not args.apply)
    else:
        result = append_players_diary_from_journal(dry_run=not args.apply)

    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    if result.get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
