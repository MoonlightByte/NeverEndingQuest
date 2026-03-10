# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Compressed Narrator Prompt Structure Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Checks hard-rules-first ordering and resolution ladder presence.
"""

import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_PATH = os.path.join(REPO_ROOT, "prompts", "system_prompt_compressed.txt")


class TestNarratorPromptStructure(unittest.TestCase):
    """Prompt ordering contracts for compressed narrator prompt."""

    @classmethod
    def setUpClass(cls):
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            cls.prompt_text = f.read()

    def _index(self, marker):
        idx = self.prompt_text.find(marker)
        self.assertNotEqual(idx, -1, msg=f"Missing marker: {marker}")
        return idx

    def test_resolution_ladder_present(self):
        self.assertIn("@RESOLUTION_LADDER", self.prompt_text)

    def test_hard_rules_precede_resolution_and_combat(self):
        idx_fmt = self._index("@FMT")
        idx_actions = self._index("@ACTIONS")
        idx_resolution = self._index("@RESOLUTION_LADDER")
        idx_combat = self._index("@COMBAT")

        self.assertLess(idx_fmt, idx_actions)
        self.assertLess(idx_actions, idx_resolution)
        self.assertLess(idx_resolution, idx_combat)

    def test_narrator_interface_after_core_mechanics(self):
        idx_narrator = self._index("@NARRATOR_INTERFACE")
        idx_combat = self._index("@COMBAT")
        self.assertGreater(idx_narrator, idx_combat)


if __name__ == "__main__":
    unittest.main(verbosity=2)
