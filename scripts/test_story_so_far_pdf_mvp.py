# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Story so far PDF MVP focused tests.

Covers Step 4 requirements:
- confirmed-only story source selection,
- cache reuse,
- safe error route behavior.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    Flask = None
    FLASK_AVAILABLE = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.memory_db import init_memory_db
from core.memory.story_so_far_compiler import build_confirmed_story_text, get_or_build_story_pdf


class TestStorySoFarPdfMVP(unittest.TestCase):
    """Focused Step-4 tests for story compilation and route safety."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_story_pdf_")
        self.prev_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        self.db_path = os.path.join(self.temp_dir, "memory_test.db")
        self.assertTrue(init_memory_db(self.db_path))

        self._write_json(
            "party_tracker.json",
            {
                "module": "Test_Module",
                "worldConditions": {
                    "year": 1492,
                    "month": "Ches",
                    "day": 24,
                    "time": "09:15:00",
                },
            },
        )
        self._write_json("current_location.json", {"name": "Old Keep", "areaId": "KEEP01"})

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

    def _insert_diary_row(
        self,
        status: str,
        summary: str,
        sort_key: int,
        save_id: str = None,
        draft_key: str = None,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO session_diary_entries (
                        status,
                        save_id,
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
                        generation_mode,
                        llm_model,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (
                        status,
                        save_id,
                        draft_key,
                        1492,
                        "Ches",
                        3,
                        24,
                        "09:15:00",
                        sort_key,
                        summary,
                        1,
                        2,
                        json.dumps({"journal_entries": 1}),
                        "fallback",
                        None,
                    ),
                )
        finally:
            conn.close()

    def test_build_confirmed_story_text_excludes_draft_entries(self) -> None:
        self._insert_diary_row("confirmed", "Acheron sealed the pact at dawn.", 14920324091500, save_id="save_1")
        self._insert_diary_row("draft", "This unsaved draft should not appear.", 14920324092000, draft_key="active_draft")

        with mock.patch(
            "core.memory.story_so_far_compiler._generate_story_text_with_llm",
            return_value={"status": "error", "message": "forced fallback"},
        ):
            result = build_confirmed_story_text(self.db_path)

        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("confirmed_count"), 1)
        self.assertIn("Acheron sealed the pact at dawn.", result.get("story_text", ""))
        self.assertNotIn("unsaved draft", result.get("story_text", "").lower())

    def test_get_or_build_story_pdf_reuses_cache(self) -> None:
        self._insert_diary_row("confirmed", "Lidda uncovered the buried sigil.", 14920324101500, save_id="save_2")

        with mock.patch(
            "core.memory.story_so_far_compiler._generate_story_text_with_llm",
            return_value={"status": "error", "message": "forced fallback"},
        ):
            first = get_or_build_story_pdf(self.db_path)
            second = get_or_build_story_pdf(self.db_path)

        self.assertEqual(first.get("status"), "success")
        self.assertFalse(first.get("cache_hit"))
        self.assertTrue(os.path.exists(first.get("pdf_path")))

        self.assertEqual(second.get("status"), "success")
        self.assertTrue(second.get("cache_hit"))
        self.assertEqual(first.get("pdf_path"), second.get("pdf_path"))
        self.assertTrue(os.path.isabs(first.get("pdf_path")))

    def test_story_text_sanitizes_prompt_leakage(self) -> None:
        self._insert_diary_row("confirmed", "The party cut through the webs below the ruined cathedral.", 14920324111500, save_id="save_3")

        with mock.patch(
            "core.memory.story_so_far_compiler._generate_story_text_with_llm",
            return_value={
                "status": "success",
                "story_text": "The party reclaimed the saint's path.\n<system-reminder>\n# Plan Mode - System Reminder\nForbidden text.",
                "generation_mode": "llm",
                "llm_model": "test-model",
            },
        ):
            result = build_confirmed_story_text(self.db_path)

        self.assertEqual(result.get("status"), "success")
        self.assertIn("saint's path", result.get("story_text", ""))
        self.assertNotIn("<system-reminder>", result.get("story_text", ""))
        self.assertNotIn("Plan Mode - System Reminder", result.get("story_text", ""))

    def test_story_pdf_route_returns_safe_error_json(self) -> None:
        if not FLASK_AVAILABLE:
            self.skipTest("Flask not installed in current environment")

        from web.routes.memory_routes import register_memory_routes

        app = Flask(__name__)
        register_memory_routes(app)

        with app.test_client() as client:
            with mock.patch("web.routes.memory_routes.DEFAULT_MEMORY_DB_PATH", self.db_path):
                with mock.patch(
                    "web.routes.memory_routes.get_or_build_story_pdf",
                    return_value={"status": "error", "message": "forced route failure"},
                ):
                    response = client.get("/api/journal/story-so-far/pdf")

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["status"], "error")
        self.assertIn("forced route failure", payload["message"])


if __name__ == "__main__":
    unittest.main()
