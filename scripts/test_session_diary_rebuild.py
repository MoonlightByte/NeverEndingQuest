# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Session diary rebuild tests."""

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
from core.memory.session_diary import _sanitize_rebuild_summary, rebuild_diary_from_journal


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TestSessionDiaryRebuild(unittest.TestCase):
    """Validate in-place diary rebuild from journal chronology."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_diary_rebuild_")
        self.prev_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        self.db_path = os.path.join(self.temp_dir, "memory.db")
        self.assertTrue(init_memory_db(self.db_path))

        journal_payload = {
            "module": "Keep_of_Doom",
            "entries": [
                {
                    "date": "1492 Springmonth 1",
                    "time": "18:00:00",
                    "location": "Rangers' Command Post",
                    "summary": "The party reached the command post and planned the march north.",
                },
                {
                    "date": "1492 Springmonth 1",
                    "time": "18:10:00",
                    "location": "Rangers' Command Post (RO01)",
                    "summary": "Journal Entry: Rangers' Command Post. Date: Springmonth 1. The party reached the command post, repaired the silver bell network, gathered supplies, and prepared to move at dawn.",
                },
                {
                    "date": "1492 Springmonth 2",
                    "time": "06:15:00",
                    "location": "Hermit's Refuge (TW04)",
                    "summary": "The party met Maelo at the refuge and learned more about the corruption ahead.",
                },
                {
                    "date": "1492 Springmonth 2",
                    "time": "08:26:00",
                    "location": "Bandit Stronghold",
                    "summary": "They negotiated with Captain Gorvek and secured passage toward the cave.",
                },
            ],
        }
        with open("journal.json", "w", encoding="utf-8") as handle:
            json.dump(journal_payload, handle, ensure_ascii=True)

        for idx, entry in enumerate(journal_payload["entries"]):
            result = ingest_journal_entry(
                {
                    "entry_ts": _utc_now_iso(),
                    "title": entry["location"],
                    "content": entry["summary"],
                    "source_type": "journal",
                    "source_ref": f"journal.json:{idx}",
                    "created_at": _utc_now_iso(),
                },
                db_path=self.db_path,
            )
            self.assertEqual(result.get("status"), "success")

        with open("party_tracker.json", "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "module": "Night_of_the_Restless_Dead",
                },
                handle,
                ensure_ascii=True,
            )
        with open("current_location.json", "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "name": "Corrupted Entry Cave",
                    "locationId": "TW06",
                },
                handle,
                ensure_ascii=True,
            )

        # Seed one legacy row so module inference can prefer existing consistent module.
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO session_diary_entries (
                        status,
                        save_id,
                        checkpoint_type,
                        checkpoint_id,
                        draft_key,
                        world_year,
                        world_month,
                        world_month_index,
                        world_day,
                        world_time,
                        world_sort_key,
                        summary,
                        source_start_event_id,
                        source_end_event_id,
                        source_counts_json,
                        checkpoint_module,
                        checkpoint_location,
                        checkpoint_location_id,
                        checkpoint_area,
                        checkpoint_area_id,
                        generation_mode,
                        llm_model,
                        created_at,
                        updated_at
                    ) VALUES (
                        'confirmed',
                        NULL,
                        'exit',
                        'exit:legacy',
                        NULL,
                        1492,
                        'Springmonth',
                        1,
                        1,
                        '12:00:00',
                        14920101120000,
                        'Legacy row',
                        1,
                        1,
                        '{}',
                        'The_Thornwood_Watch',
                        'Unknown Location',
                        '',
                        'Unknown Area',
                        '',
                        'fallback',
                        NULL,
                        datetime('now'),
                        datetime('now')
                    )
                    """
                )
        finally:
            conn.close()

    def tearDown(self) -> None:
        import shutil

        os.chdir(self.prev_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rebuild_preview_reports_grouped_chapters(self) -> None:
        preview = rebuild_diary_from_journal(self.db_path, dry_run=True)
        self.assertEqual(preview.get("status"), "success")
        self.assertEqual(preview.get("action"), "preview")
        self.assertEqual(preview.get("scanned"), 4)
        self.assertEqual(preview.get("grouped"), 3)
        self.assertEqual(preview.get("rebuilt_row_count"), 3)
        self.assertEqual(preview.get("duplicate_collapsed"), 1)

        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM session_diary_entries").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1)

    def test_rebuild_apply_replaces_rows_and_preserves_historical_locations(self) -> None:
        applied = rebuild_diary_from_journal(self.db_path, dry_run=False)
        self.assertEqual(applied.get("status"), "success")
        self.assertEqual(applied.get("action"), "applied")
        self.assertEqual(applied.get("replaced"), 3)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT checkpoint_type, checkpoint_id, checkpoint_module, checkpoint_location, checkpoint_location_id, summary, generation_mode, source_counts_json
                FROM session_diary_entries
                ORDER BY world_sort_key ASC, diary_id ASC
                """
            ).fetchall()
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(str(row["checkpoint_type"]) == "rebuild" for row in rows))
            self.assertTrue(all(str(row["checkpoint_id"]).startswith("journal_chapter:") for row in rows))
            self.assertTrue(all(str(row["checkpoint_module"]) == "The_Thornwood_Watch" for row in rows))
            self.assertTrue(all(str(row["generation_mode"]) == "fallback" for row in rows))

            first = rows[0]
            self.assertEqual(first["checkpoint_location"], "Rangers' Command Post")
            self.assertIn("repaired the silver bell network", str(first["summary"]).lower())
            self.assertNotIn("Corrupted Entry Cave", str(first["summary"]))

            for row in rows:
                summary_text = str(row["summary"] or "")
                self.assertNotIn("Rangers' Command Post, Thornwood Borderlands", summary_text)
                self.assertFalse(summary_text.lower().startswith("- date:"))
                source_counts = json.loads(str(row["source_counts_json"] or "{}"))
                self.assertIn("chapter_source_start_index", source_counts)
                self.assertIn("chapter_source_end_index", source_counts)
                self.assertIn("chapter_source_entry_count", source_counts)

            location_ids = {str(row["checkpoint_location_id"] or "") for row in rows}
            self.assertIn("TW04", location_ids)

            state = conn.execute(
                "SELECT last_confirmed_event_id, last_draft_event_id, last_draft_key FROM session_diary_state WHERE state_id = 1"
            ).fetchone()
            self.assertEqual(int(state["last_confirmed_event_id"]), 4)
            self.assertEqual(int(state["last_draft_event_id"]), 4)
            self.assertIsNone(state["last_draft_key"])
        finally:
            conn.close()

    def test_heading_like_intro_is_removed_from_summary(self) -> None:
        raw = (
            "Arrival at Rangers' Command Post and Journey to the Hermit's Glade "
            "This morning, the party crossed the rain-soaked gate and resumed their watch."
        )
        cleaned = _sanitize_rebuild_summary(raw)
        self.assertTrue(cleaned.startswith("This morning"))
        self.assertNotIn("Arrival at Rangers' Command Post and Journey to the Hermit's Glade", cleaned)

    def test_rebuild_preserves_journal_source_order_over_world_time(self) -> None:
        reordered_payload = {
            "module": "Keep_of_Doom",
            "entries": [
                {
                    "date": "1492 Springmonth 5",
                    "time": "23:00:00",
                    "location": "Late Camp",
                    "summary": "The party camped after dusk and tended to wounds.",
                },
                {
                    "date": "1492 Springmonth 5",
                    "time": "01:00:00",
                    "location": "Early Gate",
                    "summary": "At first light, the party crossed the old gate.",
                },
            ],
        }
        with open("journal.json", "w", encoding="utf-8") as handle:
            json.dump(reordered_payload, handle, ensure_ascii=True)

        applied = rebuild_diary_from_journal(self.db_path, dry_run=False)
        self.assertEqual(applied.get("status"), "success")
        self.assertEqual(applied.get("replaced"), 2)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT checkpoint_location, world_time FROM session_diary_entries ORDER BY world_sort_key ASC, diary_id ASC"
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(str(rows[0]["checkpoint_location"]), "Late Camp")
            self.assertEqual(str(rows[0]["world_time"]), "23:00:00")
            self.assertEqual(str(rows[1]["checkpoint_location"]), "Early Gate")
            self.assertEqual(str(rows[1]["world_time"]), "01:00:00")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
