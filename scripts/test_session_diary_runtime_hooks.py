# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Session diary runtime hook tests.

Focused Step-3 coverage:
- save remains successful when diary checkpoint generation fails,
- Start Game diary refresh helper fails open,
- web handler source wiring remains present.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSessionDiaryRuntimeHooks(unittest.TestCase):
    """Fail-open verification for diary runtime hooks."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_diary_hooks_")
        self.prev_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        os.makedirs("modules/Test_Module/saved_games", exist_ok=True)
        os.makedirs("modules/conversation_history", exist_ok=True)

        self._write_json(
            "party_tracker.json",
            {
                "module": "Test_Module",
                "partyMembers": ["Acheron"],
                "partyNPCs": [],
                "worldConditions": {
                    "year": 1492,
                    "month": "Ches",
                    "day": 21,
                    "time": "13:10:54",
                    "currentLocation": "NIG01",
                    "currentArea": "NIG001",
                },
            },
        )
        self._write_json(
            "current_location.json",
            {"name": "Ma's Watering Hole", "areaId": "NIG001"},
        )
        self._write_json("journal.json", {"journal_entries": []})

    def tearDown(self) -> None:
        import shutil

        os.chdir(self.prev_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_json(self, path: str, payload: object) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_save_manager_diary_failure_is_fail_open(self) -> None:
        import updates.save_game_manager as save_game_manager

        manager = save_game_manager.SaveGameManager()
        with mock.patch.object(
            save_game_manager,
            "confirm_diary_for_save",
            side_effect=RuntimeError("forced diary failure"),
        ):
            success, message = manager.create_save_game("Diary hook fail-open", "essential")

        self.assertTrue(success)
        self.assertIn("Diary checkpoint: degraded", message)

        saves = manager.list_save_games()
        self.assertEqual(len(saves), 1)

        metadata_path = os.path.join(saves[0]["save_path"], "save_metadata.json")
        with open(metadata_path, "r", encoding="utf-8") as handle:
            metadata = json.load(handle)

        self.assertEqual(metadata["session_diary"]["status"], "error")
        self.assertIn("forced diary failure", metadata["session_diary"]["message"])

    def test_start_hook_failure_returns_error_payload_without_raise(self) -> None:
        import web.extensions.session_diary_runtime as runtime

        with mock.patch.object(
            runtime,
            "refresh_draft_if_stale",
            side_effect=RuntimeError("forced start hook failure"),
        ):
            result = runtime.refresh_session_diary_start_hook("data/memory.db")

        self.assertEqual(result["status"], "error")
        self.assertIn("forced start hook failure", result["message"])

    def test_web_interface_contains_start_hook_wiring(self) -> None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        web_interface_path = os.path.join(repo_root, "web", "web_interface.py")

        with open(web_interface_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("refresh_session_diary_start_hook", source)
        self.assertIn("Journal draft updated.", source)


if __name__ == "__main__":
    unittest.main()
