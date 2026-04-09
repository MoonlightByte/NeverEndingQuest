# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Players diary append markdown tests."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.memory.players_diary as players_diary


class TestPlayersDiaryAppendMarkdown(unittest.TestCase):
    """Contract tests for append/rebuild markdown diary workflow."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neq_players_diary_")
        self.prev_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        os.makedirs("data", exist_ok=True)

        self.journal_path = os.path.join(self.temp_dir, "journal.json")
        self.diary_path = os.path.join(self.temp_dir, "data", "players_diary.md")
        self.bookmark_path = os.path.join(self.temp_dir, "data", "players_diary_bookmark.json")

        self.original_generate = players_diary._generate_markdown_from_prompt

        self.write_journal([
            {
                "date": "1492 Springmonth 1",
                "time": "18:00:00",
                "location": "Rangers' Command Post",
                "summary": "The party repaired bells and heard grim talk of Malarok.",
            },
            {
                "date": "1492 Springmonth 1",
                "time": "18:30:00",
                "location": "North Tower Overlook",
                "summary": "They fought bandits and rescued Kael from the ruins.",
            },
        ])

    def tearDown(self) -> None:
        import shutil

        players_diary._generate_markdown_from_prompt = self.original_generate
        os.chdir(self.prev_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def write_journal(self, entries):
        with open(self.journal_path, "w", encoding="utf-8") as handle:
            json.dump({"module": "Test_Module", "entries": entries}, handle, ensure_ascii=True)

    def read_bookmark(self):
        if not os.path.exists(self.bookmark_path):
            return {}
        with open(self.bookmark_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def read_diary(self):
        if not os.path.exists(self.diary_path):
            return ""
        with open(self.diary_path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_rebuild_from_scratch_writes_diary_and_bookmark(self) -> None:
        def fake_generate(prompt_text, context_tag):
            self.assertIn("Full journal chronology", prompt_text)
            self.assertEqual(context_tag, "players_diary_rebuild")
            return {
                "status": "success",
                "message": "ok",
                "markdown": "# The Chronicle\n\n## Springmonth 1\n\nAll was mud and steel.",
                "model": "fake-model",
            }

        players_diary._generate_markdown_from_prompt = fake_generate

        result = players_diary.rebuild_players_diary_from_journal(
            journal_path=self.journal_path,
            diary_path=self.diary_path,
            bookmark_path=self.bookmark_path,
            dry_run=False,
        )
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("action"), "rebuild")

        diary_text = self.read_diary()
        self.assertIn("# The Chronicle", diary_text)

        bookmark = self.read_bookmark()
        self.assertEqual(int(bookmark.get("last_processed_index", -1)), 1)

    def test_append_noop_when_no_new_entries(self) -> None:
        with open(self.diary_path, "w", encoding="utf-8") as handle:
            handle.write("# Existing Diary\n")
        with open(self.bookmark_path, "w", encoding="utf-8") as handle:
            json.dump({"last_processed_index": 1}, handle)

        result = players_diary.append_players_diary_from_journal(
            journal_path=self.journal_path,
            diary_path=self.diary_path,
            bookmark_path=self.bookmark_path,
            dry_run=False,
        )
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("action"), "noop")
        self.assertIn("# Existing Diary", self.read_diary())

    def test_append_updates_markdown_and_bookmark(self) -> None:
        with open(self.diary_path, "w", encoding="utf-8") as handle:
            handle.write("# Existing Diary\n\n## Springmonth 1\n\nOld entry.\n")
        with open(self.bookmark_path, "w", encoding="utf-8") as handle:
            json.dump({"last_processed_index": 0}, handle)

        def fake_generate(prompt_text, context_tag):
            self.assertIn("Existing diary tail", prompt_text)
            self.assertEqual(context_tag, "players_diary_append")
            return {
                "status": "success",
                "message": "ok",
                "markdown": "## Springmonth 2\n\nNew trouble at the tower.",
                "model": "fake-model",
            }

        players_diary._generate_markdown_from_prompt = fake_generate

        result = players_diary.append_players_diary_from_journal(
            journal_path=self.journal_path,
            diary_path=self.diary_path,
            bookmark_path=self.bookmark_path,
            dry_run=False,
        )
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("action"), "append")
        self.assertEqual(result.get("appended_entries"), 1)

        diary_text = self.read_diary()
        self.assertIn("Old entry.", diary_text)
        self.assertIn("New trouble at the tower.", diary_text)

        bookmark = self.read_bookmark()
        self.assertEqual(int(bookmark.get("last_processed_index", -1)), 1)

    def test_append_failure_does_not_advance_bookmark_or_modify_file(self) -> None:
        with open(self.diary_path, "w", encoding="utf-8") as handle:
            handle.write("# Existing Diary\n\nStable content.\n")
        with open(self.bookmark_path, "w", encoding="utf-8") as handle:
            json.dump({"last_processed_index": 0}, handle)

        def fake_generate(prompt_text, context_tag):
            return {
                "status": "error",
                "message": "forced failure",
                "markdown": "",
                "model": None,
            }

        players_diary._generate_markdown_from_prompt = fake_generate

        before_diary = self.read_diary()
        before_bookmark = self.read_bookmark().get("last_processed_index")

        result = players_diary.append_players_diary_from_journal(
            journal_path=self.journal_path,
            diary_path=self.diary_path,
            bookmark_path=self.bookmark_path,
            dry_run=False,
        )
        self.assertEqual(result.get("status"), "error")

        self.assertEqual(self.read_diary(), before_diary)
        after_bookmark = self.read_bookmark().get("last_processed_index")
        self.assertEqual(after_bookmark, before_bookmark)


if __name__ == "__main__":
    unittest.main()
