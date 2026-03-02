#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Cleanup stale SESSION RESUME RECAP markers from runtime history files.

This script shares logic with runtime startup cleanup to guarantee parity.
"""

import argparse
import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.session_cleanup import cleanup_history_files, get_default_history_filepaths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove stale SESSION RESUME RECAP ONLY messages from history files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report removals without writing files (default mode)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply removals to files",
    )
    return parser


def _print_summary(results: List[dict], apply_changes: bool) -> None:
    mode_label = "APPLY" if apply_changes else "DRY-RUN"
    print(f"[{mode_label}] Stale recap cleanup summary")

    total_removed = 0
    for result in results:
        path = result.get("path", "<unknown>")
        status = result.get("status", "error")
        removed_count = int(result.get("removed_count", 0))
        total_before = int(result.get("total_before", 0))
        total_after = int(result.get("total_after", 0))
        error_message = result.get("error")

        total_removed += removed_count

        if status == "ok":
            print(
                f"[OK] {path}: {total_before} -> {total_after} "
                f"(removed {removed_count})"
            )
        elif status == "missing":
            print(f"[INFO] {path}: file not found (skipped)")
        else:
            print(f"[ERROR] {path}: cleanup failed ({error_message})")

    print(f"[RESULT] Total stale recap messages removed: {total_removed}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.apply and args.dry_run:
        parser.error("Use either --apply or --dry-run, not both")

    apply_changes = args.apply
    target_files = get_default_history_filepaths()
    results = cleanup_history_files(filepaths=target_files, apply_changes=apply_changes)

    _print_summary(results, apply_changes=apply_changes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
