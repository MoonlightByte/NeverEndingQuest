# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for journal cadence hardening (transition + long rest)."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.ai.cumulative_summary import (
    build_transition_checkpoint_metadata,
    maybe_create_long_rest_journal_checkpoint,
    update_journal_with_summary,
)


class TestJournalCadenceHardening(unittest.TestCase):
    """Focused coverage for transition and long-rest cadence hooks."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_journal_cadence_")
        self.prev_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        self.party_tracker = {
            "module": "Night_of_the_Restless_Dead",
            "partyMembers": ["Acheron"],
            "active_character": "Acheron",
            "worldConditions": {
                "year": 1492,
                "month": "Ches",
                "day": 21,
                "time": "06:00:00",
                "currentLocation": "Ma's Watering Hole",
                "currentLocationId": "NIG01",
                "currentAreaId": "NIG001",
            },
        }

        os.makedirs("modules/logs", exist_ok=True)
        os.makedirs("characters", exist_ok=True)
        self._write_json("party_tracker.json", self.party_tracker)
        self._write_json("characters/acheron.json", {"name": "Acheron", "level": 1})
        self._write_json("journal.json", {"entries": []})

    def tearDown(self) -> None:
        os.chdir(self.prev_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _read_json(self, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, path: str, payload: dict) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def test_transition_checkpoint_metadata_is_idempotent(self) -> None:
        metadata = build_transition_checkpoint_metadata(
            "Location transition: Priest's Lodging (NIG04) to Brother Lintar's Place (NIG08)",
            self.party_tracker,
            source_location="Priest's Lodging",
            source_location_id="NIG04",
        )

        first_write = update_journal_with_summary(
            "Transition checkpoint summary",
            self.party_tracker,
            "Priest's Lodging",
            checkpoint_metadata=metadata,
        )
        second_write = update_journal_with_summary(
            "Transition checkpoint summary",
            self.party_tracker,
            "Priest's Lodging",
            checkpoint_metadata=metadata,
        )

        self.assertTrue(first_write)
        self.assertFalse(second_write)

        journal_data = self._read_json("journal.json")
        self.assertEqual(len(journal_data.get("entries", [])), 1)
        self.assertEqual(
            journal_data["entries"][0].get("checkpoint", {}).get("kind"),
            "transition",
        )

    def test_transition_path_remains_active_in_main_loop(self) -> None:
        main_path = os.path.join(PROJECT_ROOT, "main.py")
        with open(main_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("check_and_process_location_transitions(", source)
        self.assertIn("update_journal_with_summary(", source)
        self.assertIn("build_transition_checkpoint_metadata(", source)

    def test_long_rest_checkpoint_is_created_when_meaningful_delta_exists(self) -> None:
        conversation_history = [
            {
                "role": "user",
                "content": "Location transition: Ma's Watering Hole (NIG01) to Priest's Lodging (NIG04)",
            },
            {"role": "user", "content": "I investigate the ruined altar for clues."},
            {
                "role": "assistant",
                "content": "You find an old sigil etched beneath dried blood.",
            },
            {"role": "user", "content": "We take a long rest."},
        ]

        with mock.patch(
            "core.ai.cumulative_summary.generate_enhanced_summary_from_messages",
            return_value="Long-rest checkpoint summary",
        ):
            result = maybe_create_long_rest_journal_checkpoint(
                conversation_history,
                self.party_tracker,
            )

        self.assertEqual(result.get("status"), "written")

        journal_data = self._read_json("journal.json")
        entries = journal_data.get("entries", [])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get("summary"), "Long-rest checkpoint summary")
        self.assertEqual(entries[0].get("checkpoint", {}).get("kind"), "long_rest")

    def test_duplicate_long_rest_checkpoint_is_suppressed(self) -> None:
        conversation_history = [
            {
                "role": "user",
                "content": "Location transition: Ma's Watering Hole (NIG01) to Priest's Lodging (NIG04)",
            },
            {"role": "user", "content": "We search the cellar and catalog relics."},
            {
                "role": "assistant",
                "content": "You recover a rusted reliquary and map fragments.",
            },
        ]

        with mock.patch(
            "core.ai.cumulative_summary.generate_enhanced_summary_from_messages",
            return_value="Long-rest checkpoint summary",
        ):
            first = maybe_create_long_rest_journal_checkpoint(
                conversation_history,
                self.party_tracker,
            )
            duplicate = maybe_create_long_rest_journal_checkpoint(
                conversation_history,
                self.party_tracker,
            )

        self.assertEqual(first.get("status"), "written")
        self.assertEqual(duplicate.get("status"), "duplicate")

        journal_data = self._read_json("journal.json")
        self.assertEqual(len(journal_data.get("entries", [])), 1)

    def test_long_rest_no_delta_is_no_op(self) -> None:
        conversation_history = [
            {
                "role": "user",
                "content": "Location transition: Ma's Watering Hole (NIG01) to Priest's Lodging (NIG04)",
            },
            {"role": "assistant", "content": "You arrive at the ruined lodgings."},
            {"role": "user", "content": "We take a long rest."},
        ]

        with mock.patch(
            "core.ai.cumulative_summary.generate_enhanced_summary_from_messages"
        ) as summary_mock:
            result = maybe_create_long_rest_journal_checkpoint(
                conversation_history,
                self.party_tracker,
            )

        self.assertEqual(result.get("status"), "no_delta")
        summary_mock.assert_not_called()
        journal_data = self._read_json("journal.json")
        self.assertEqual(len(journal_data.get("entries", [])), 0)

    def test_rest_action_remains_successful_when_journal_checkpoint_degrades(
        self,
    ) -> None:
        import core.ai.action_handler as action_handler

        action = {
            "action": "rest",
            "parameters": {"type": "long", "characters": ["Acheron"]},
        }
        conversation_history = []

        with (
            mock.patch.object(
                action_handler,
                "_process_character_rest",
                return_value={
                    "character": "Acheron",
                    "rest_type": "long",
                    "hp_restored": 12,
                    "spell_slots_restored": 2,
                    "features_reset": ["Second Wind"],
                    "exhaustion_reduced": False,
                },
            ),
            mock.patch(
                "core.ai.cumulative_summary.maybe_create_long_rest_journal_checkpoint",
                side_effect=RuntimeError("forced journal failure"),
            ),
        ):
            result = action_handler.process_action(
                action,
                self.party_tracker,
                {},
                conversation_history,
            )

        self.assertEqual(result.get("status"), "continue")
        self.assertTrue(result.get("needs_update"))
        self.assertEqual(len(conversation_history), 1)
        self.assertEqual(conversation_history[0].get("role"), "system")
        self.assertIn("Long rest completed", conversation_history[0].get("content", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
