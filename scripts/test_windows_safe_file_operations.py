#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Windows-safe file operation regressions.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.encoding_utils import safe_json_dump
from utils.file_operations import AtomicFileWriter


class TestWindowsSafeFileOperations(unittest.TestCase):
    def test_write_json_retries_atomic_replace_after_permission_error(self):
        writer = AtomicFileWriter(max_retries=3, retry_delay=0)

        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "party_tracker.json")
            original_replace = os.replace
            state = {"attempts": 0}

            def flaky_replace(src, dst):
                if state["attempts"] == 0:
                    state["attempts"] += 1
                    raise PermissionError("file is being used by another process")
                return original_replace(src, dst)

            with patch("utils.file_operations.os.replace", side_effect=flaky_replace):
                result = writer.write_json(
                    target_path,
                    {"worldConditions": {"currentLocationId": "NIG04"}},
                    create_backup=False,
                    acquire_lock=False,
                )

            self.assertTrue(result)
            self.assertEqual(state["attempts"], 1)
            with open(target_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.assertEqual(payload["worldConditions"]["currentLocationId"], "NIG04")

    def test_safe_json_dump_routes_through_atomic_writer(self):
        with patch("utils.file_operations.safe_write_json", return_value=True) as mock_safe_write:
            result = safe_json_dump({"text": "A -- B"}, "party_tracker.json", indent=4)

        self.assertTrue(result)
        mock_safe_write.assert_called_once()
        args, kwargs = mock_safe_write.call_args
        self.assertEqual(args[0], "party_tracker.json")
        self.assertEqual(args[1], {"text": "A -- B"})
        self.assertEqual(kwargs["json_kwargs"]["indent"], 4)
        self.assertEqual(kwargs["json_kwargs"]["ensure_ascii"], False)

    def test_file_operations_uses_replace_not_delete_then_rename(self):
        file_path = os.path.join(os.path.dirname(__file__), "..", "utils", "file_operations.py")
        file_path = os.path.abspath(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("os.replace(temp_path, filepath)", source)
        self.assertNotIn("os.unlink(filepath)", source)
        self.assertNotIn("os.rename(temp_path, filepath)", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
