#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for stale recap cleanup utilities."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.session_cleanup import (
    cleanup_history_file,
    is_stale_resume_recap_message,
    remove_stale_resume_recaps,
)


class TestSessionCleanup(unittest.TestCase):
    def test_is_stale_resume_recap_message_detects_marker(self) -> None:
        stale_message = {
            "role": "user",
            "content": "Dungeon Master Note: SESSION RESUME RECAP ONLY. Narration only.",
        }
        normal_message = {"role": "assistant", "content": "The wind shifts."}

        self.assertTrue(is_stale_resume_recap_message(stale_message))
        self.assertFalse(is_stale_resume_recap_message(normal_message))

    def test_remove_stale_resume_recaps_is_idempotent(self) -> None:
        messages = [
            {"role": "assistant", "content": "Opening line"},
            {"role": "user", "content": "SESSION RESUME RECAP ONLY"},
            {"role": "assistant", "content": "Continue"},
        ]

        cleaned_once, removed_once = remove_stale_resume_recaps(messages)
        cleaned_twice, removed_twice = remove_stale_resume_recaps(cleaned_once)

        self.assertEqual(removed_once, 1)
        self.assertEqual(removed_twice, 0)
        self.assertEqual(cleaned_once, cleaned_twice)

    def test_cleanup_history_file_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "conversation_history.json"
            history_path.write_text(
                json.dumps([
                    {"role": "assistant", "content": "a"},
                    {"role": "user", "content": "SESSION RESUME RECAP ONLY"},
                ]),
                encoding="utf-8",
            )

            result = cleanup_history_file(str(history_path), apply_changes=False)
            persisted = json.loads(history_path.read_text(encoding="utf-8"))

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(len(persisted), 2)

    def test_cleanup_history_file_apply_writes_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "chat_history.json"
            history_path.write_text(
                json.dumps([
                    {"role": "assistant", "content": "a"},
                    {"role": "user", "content": "SESSION RESUME RECAP ONLY"},
                ]),
                encoding="utf-8",
            )

            result = cleanup_history_file(str(history_path), apply_changes=True)
            persisted = json.loads(history_path.read_text(encoding="utf-8"))

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(len(persisted), 1)

    def test_cleanup_history_file_missing_is_fail_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = Path(tmp_dir) / "missing.json"
            result = cleanup_history_file(str(missing_path), apply_changes=True)
            self.assertEqual(result["status"], "missing")
            self.assertEqual(result["removed_count"], 0)


if __name__ == "__main__":
    unittest.main()
