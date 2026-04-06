# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Session diary remediation tests."""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import init_memory_db
from core.memory.memory_ingest import ingest_journal_entry
from core.memory.session_diary import remediate_diary_entries


class TestSessionDiaryRemediation(unittest.TestCase):
    """Verify remediation rebuilds noisy diary entries safely."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_diary_remediate_")
        self.db_path = os.path.join(self.temp_dir, "memory.db")
        self.assertTrue(init_memory_db(self.db_path))

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_journal_source(self, content: str, source_ref: str) -> int:
        result = ingest_journal_entry(
            {
                "title": "Rangers' Command Post",
                "content": content,
                "source_type": "journal",
                "source_ref": source_ref,
                "entry_ts": "1492-03-21T12:00:00Z",
                "created_at": "1492-03-21T12:00:00Z",
            },
            db_path=self.db_path,
        )
        self.assertEqual(result.get("status"), "success")
        return int(result.get("entry_id", 0))

    def _insert_noisy_diary_row(self, source_end_event_id: int) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                cursor = conn.execute(
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
                        'save_remediate_1',
                        'save',
                        'save_remediate_1',
                        NULL,
                        1492,
                        'Ches',
                        3,
                        21,
                        '12:00:00',
                        14920321120000,
                        '{"plan":"json leak"}',
                        0,
                        ?,
                        '{}',
                        '',
                        '',
                        '',
                        '',
                        '',
                        'llm',
                        'test-model',
                        datetime('now'),
                        datetime('now')
                    )
                    """,
                    (source_end_event_id,),
                )
                return int(cursor.lastrowid)
        finally:
            conn.close()

    def test_remediation_dry_run_reports_pending_updates(self) -> None:
        event_id = self._insert_journal_source(
            "Journal Entry: The party reached the ruined gate. They secured the courtyard.",
            "journal:dry_run",
        )
        self._insert_noisy_diary_row(event_id)

        result = remediate_diary_entries(self.db_path, dry_run=True)
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("scanned"), 1)
        self.assertEqual(result.get("updated"), 0)
        self.assertEqual(result.get("would_update"), 1)

    def test_remediation_apply_rebuilds_summary_and_mode(self) -> None:
        event_id = self._insert_journal_source(
            "Journal Entry: The party reached the ruined gate. They secured the courtyard.",
            "journal:apply",
        )
        diary_id = self._insert_noisy_diary_row(event_id)

        result = remediate_diary_entries(self.db_path, dry_run=False)
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("updated"), 1)
        self.assertIn(diary_id, result.get("changed_ids", []))

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT summary, generation_mode, llm_model, checkpoint_location, checkpoint_module FROM session_diary_entries WHERE diary_id = ?",
                (diary_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertIn("At", row["summary"])
        self.assertEqual(row["generation_mode"], "fallback")
        self.assertIsNone(row["llm_model"])
        self.assertTrue(str(row["checkpoint_location"] or "").strip())
        self.assertTrue(str(row["checkpoint_module"] or "").strip())


if __name__ == "__main__":
    unittest.main()
