# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Session diary MVP focused tests.

Covers Step 2 requirements:
- single active draft behavior,
- confirmed save_id idempotency,
- deterministic fallback summary generation.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import init_memory_db
from core.memory.memory_ingest import ingest_journal_entry
from core.memory.session_diary import (
    build_fallback_summary,
    confirm_diary_for_exit,
    confirm_diary_for_save,
    refresh_draft_if_stale,
)


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TestSessionDiaryMVP(unittest.TestCase):
    """Focused Step-2 tests for diary checkpoint behavior."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_diary_test_")
        self.prev_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        os.makedirs("modules/conversation_history", exist_ok=True)
        with open("journal.json", "w", encoding="utf-8") as handle:
            handle.write('{"journal_entries": []}')
        with open("modules/conversation_history/conversation_history.json", "w", encoding="utf-8") as handle:
            handle.write('{"conversation_history": []}')
        with open("modules/conversation_history/combat_conversation_history.json", "w", encoding="utf-8") as handle:
            handle.write('{"combat_history": []}')
        self.db_path = os.path.join(self.temp_dir, "memory_test.db")
        self.assertTrue(init_memory_db(self.db_path))

    def tearDown(self) -> None:
        import shutil

        os.chdir(self.prev_cwd)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _ingest_entry(self, content: str, source_ref: str) -> None:
        result = ingest_journal_entry(
            {
                "entry_ts": _utc_now_iso(),
                "title": "Diary Source",
                "content": content,
                "source_type": "journal",
                "source_ref": source_ref,
                "created_at": _utc_now_iso(),
            },
            db_path=self.db_path,
        )
        self.assertEqual(result.get("status"), "success")

    def _count_rows(self, where_clause: str, params: tuple = ()) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute(
                f"SELECT COUNT(*) FROM session_diary_entries WHERE {where_clause}",
                params,
            ).fetchone()[0]
        finally:
            conn.close()

    def test_refresh_draft_maintains_single_active_row(self) -> None:
        self._ingest_entry("Acheron entered the ruined chapel.", "journal:1")
        self._ingest_entry("Lidda uncovered a hidden reliquary.", "journal:2")

        world_conditions = {
            "year": 1492,
            "month": "Ches",
            "day": 21,
            "time": "13:10:54",
        }

        first = refresh_draft_if_stale(self.db_path, world_conditions)
        self.assertEqual(first.get("status"), "success")
        self.assertEqual(first.get("action"), "updated")
        self.assertEqual(first.get("generation_mode"), "fallback")

        second = refresh_draft_if_stale(self.db_path, world_conditions)
        self.assertEqual(second.get("status"), "success")
        self.assertEqual(second.get("action"), "unchanged")

        self.assertEqual(self._count_rows("status = 'draft'"), 1)

        self._ingest_entry("The party escaped through moonlit alleys.", "journal:3")
        third = refresh_draft_if_stale(self.db_path, world_conditions)
        self.assertEqual(third.get("status"), "success")
        self.assertEqual(third.get("action"), "updated")
        self.assertEqual(self._count_rows("status = 'draft'"), 1)

    def test_refresh_draft_includes_checkpoint_worldline_stamps(self) -> None:
        self._ingest_entry("The party entered the ossuary crypt.", "journal:meta_1")

        world_conditions = {
            "year": 1492,
            "month": "Ches",
            "day": 25,
            "time": "14:20:00",
            "module": "Night_of_the_Restless_Dead",
            "currentLocation": "Cathedral Undercroft",
            "currentLocationId": "NIG03",
            "currentArea": "Nightgrave Cathedral",
            "currentAreaId": "NIG001",
        }

        result = refresh_draft_if_stale(self.db_path, world_conditions)
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("source_mode"), "journal")
        draft = result.get("draft", {})
        checkpoint = draft.get("checkpoint", {})
        self.assertEqual(checkpoint.get("module"), "Night_of_the_Restless_Dead")
        self.assertEqual(checkpoint.get("location"), "Cathedral Undercroft")
        self.assertEqual(checkpoint.get("location_id"), "NIG03")
        self.assertEqual(checkpoint.get("area"), "Nightgrave Cathedral")
        self.assertEqual(checkpoint.get("area_id"), "NIG001")

    def test_confirm_checkpoint_is_idempotent_by_save_id(self) -> None:
        self._ingest_entry("Scout Kira warned of movement at the gate.", "journal:4")

        world_conditions = {
            "year": 1492,
            "month": "Ches",
            "day": 22,
            "time": "08:01:00",
        }

        created = confirm_diary_for_save(self.db_path, "save_abc_001", world_conditions)
        self.assertEqual(created.get("status"), "success")
        self.assertEqual(created.get("action"), "created")
        self.assertEqual(created.get("generation_mode"), "fallback")

        reused = confirm_diary_for_save(self.db_path, "save_abc_001", world_conditions)
        self.assertEqual(reused.get("status"), "success")
        self.assertEqual(reused.get("action"), "reused")

        self.assertEqual(self._count_rows("status = 'confirmed' AND save_id = ?", ("save_abc_001",)), 1)

    def test_confirm_clears_draft_and_updates_checkpoint(self) -> None:
        self._ingest_entry("The group rested at Ma's Watering Hole.", "journal:5")
        refresh_result = refresh_draft_if_stale(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 23, "time": "20:00:00"},
        )
        self.assertEqual(refresh_result.get("status"), "success")
        self.assertEqual(self._count_rows("status = 'draft'"), 1)

        confirm_result = confirm_diary_for_save(
            self.db_path,
            "save_abc_002",
            {"year": 1492, "month": "Ches", "day": 23, "time": "20:15:00"},
        )
        self.assertEqual(confirm_result.get("status"), "success")
        self.assertEqual(confirm_result.get("action"), "created")
        self.assertEqual(self._count_rows("status = 'draft'"), 0)

    def test_exit_confirm_creates_one_confirmed_entry_without_save(self) -> None:
        self._ingest_entry("The party forced open the ossuary door.", "journal:6")
        refresh_result = refresh_draft_if_stale(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 24, "time": "09:00:00"},
        )
        self.assertEqual(refresh_result.get("status"), "success")
        self.assertEqual(self._count_rows("status = 'draft'"), 1)

        exit_result = confirm_diary_for_exit(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 24, "time": "09:30:00"},
        )
        self.assertEqual(exit_result.get("status"), "success")
        self.assertEqual(exit_result.get("action"), "created")
        self.assertEqual(exit_result.get("entry", {}).get("checkpoint_type"), "exit")
        self.assertEqual(exit_result.get("generation_mode"), "fallback")
        self.assertEqual(self._count_rows("status = 'confirmed' AND checkpoint_type = 'exit'"), 1)
        self.assertEqual(self._count_rows("status = 'draft'"), 0)

    def test_exit_confirm_is_idempotent_for_same_progress_window(self) -> None:
        self._ingest_entry("The chanting below the nave grew louder.", "journal:7")

        first = confirm_diary_for_exit(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 24, "time": "10:15:00"},
        )
        self.assertEqual(first.get("status"), "success")
        self.assertEqual(first.get("action"), "created")

        second = confirm_diary_for_exit(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 24, "time": "10:15:30"},
        )
        self.assertEqual(second.get("status"), "success")
        self.assertEqual(second.get("action"), "reused")
        self.assertEqual(self._count_rows("status = 'confirmed' AND checkpoint_type = 'exit'"), 1)

    def test_exit_confirm_unchanged_when_no_new_events_exist(self) -> None:
        unchanged = confirm_diary_for_exit(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 24, "time": "11:00:00"},
        )
        self.assertEqual(unchanged.get("status"), "success")
        self.assertEqual(unchanged.get("action"), "unchanged")
        self.assertEqual(self._count_rows("status = 'confirmed' AND checkpoint_type = 'exit'"), 0)

    def test_refresh_draft_backfills_runtime_sources_before_checkpoint(self) -> None:
        with open("journal.json", "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "journal_entries": [
                        {
                            "title": "Cathedral Descent",
                            "content": "The party descended beneath the ruined cathedral and hacked free of clinging webs.",
                            "timestamp": _utc_now_iso(),
                        }
                    ]
                },
                handle,
            )

        result = refresh_draft_if_stale(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 24, "time": "12:00:00"},
        )
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("action"), "updated")
        self.assertIn("ruined cathedral", result.get("draft", {}).get("summary", "").lower())

    def test_refresh_draft_filters_structured_journal_payloads(self) -> None:
        self._ingest_entry('{"plan":"json leak", "actions":[{"action":"updateEncounter"}]}', "journal:structured")
        self._ingest_entry("The party crossed the broken nave and found claw marks near the altar.", "journal:clean")

        result = refresh_draft_if_stale(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 24, "time": "12:30:00"},
        )
        self.assertEqual(result.get("status"), "success")
        summary = result.get("draft", {}).get("summary", "")
        self.assertIn("broken nave", summary.lower())
        self.assertNotIn("updateencounter", summary.lower())
        self.assertNotIn("\"plan\"", summary)

    def test_refresh_draft_strips_journal_headers(self) -> None:
        self._ingest_entry(
            "Journal Entry - Cathedral Watch\nDate: Early Autumn\nThe party fortified the bell tower and lit warning braziers.",
            "journal:header_strip",
        )

        result = refresh_draft_if_stale(
            self.db_path,
            {"year": 1492, "month": "Ches", "day": 24, "time": "12:40:00"},
        )
        self.assertEqual(result.get("status"), "success")
        summary = result.get("draft", {}).get("summary", "")
        self.assertNotIn("journal entry", summary.lower())
        self.assertNotIn("date:", summary.lower())
        self.assertIn("bell tower", summary.lower())

    def test_build_fallback_summary_is_deterministic(self) -> None:
        events = [
            {"summary": "Acheron forced open the sealed door."},
            {"content": "The party crossed the flooded gallery."},
        ]
        summary = build_fallback_summary(events)
        self.assertEqual(
            summary,
            "At Unknown Location, Acheron forced open the sealed door. Later, The party crossed the flooded gallery.",
        )


if __name__ == "__main__":
    unittest.main()
