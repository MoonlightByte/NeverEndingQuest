# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Journal diary UI MVP source-contract tests.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestJournalDiaryUiMVP(unittest.TestCase):
    """Source-contract coverage for Diary tab UI integration."""

    @classmethod
    def setUpClass(cls) -> None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(repo_root, "web", "templates", "game_interface.html")
        with open(template_path, "r", encoding="utf-8") as handle:
            cls.source = handle.read()

    def test_journal_tabs_exist(self) -> None:
        self.assertIn('id="journal-tab-quests"', self.source)
        self.assertIn('id="journal-tab-diary"', self.source)

    def test_diary_download_button_contract_exists(self) -> None:
        self.assertIn('Download the story so far...', self.source)
        self.assertIn("downloadStorySoFar", self.source)
        self.assertIn("/api/journal/story-so-far/pdf", self.source)

    def test_diary_fetch_contract_exists(self) -> None:
        self.assertIn("async function requestDiaryData()", self.source)
        self.assertIn("/api/journal/diary", self.source)
        self.assertIn("renderDiaryToPages", self.source)

    def test_diary_meta_uses_checkpoint_location_stamp(self) -> None:
        self.assertIn("const checkpoint = entry.checkpoint || {};", self.source)
        self.assertIn("Unknown Location", self.source)
        self.assertIn("locationStamp", self.source)

    def test_confirmed_diary_entries_no_longer_use_fixed_title(self) -> None:
        self.assertIn("const titleHtml = isDraft", self.source)
        self.assertNotIn("Confirmed Chronicle", self.source)

    def test_existing_quest_flow_remains_present(self) -> None:
        self.assertIn("socket.emit('request_plot_data')", self.source)
        self.assertIn("function renderQuestsFromResponse(response)", self.source)
        self.assertIn("Current Objectives", self.source)
        self.assertIn("A Chronicle of Deeds", self.source)


if __name__ == "__main__":
    unittest.main()
