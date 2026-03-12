# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest level-up XP invariant regression tests.
"""

import json
import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


from core.managers.level_up_manager import LevelUpSession
from updates.update_character_info import repair_character_data
from utils.level_up import get_level_up_guidance
from utils.xp_progression_utils import get_next_level_threshold, normalize_xp_progression


class TestXPProgressionUtils(unittest.TestCase):
    def test_next_level_thresholds_follow_cumulative_table(self):
        self.assertEqual(get_next_level_threshold(2), 900)
        self.assertEqual(get_next_level_threshold(3), 2700)
        self.assertEqual(get_next_level_threshold(20), 0)

    def test_normalize_xp_progression_preserves_level_and_repairs_threshold(self):
        kira_like = {
            "name": "Scout Kira",
            "level": 2,
            "experience_points": 1827,
            "exp_required_for_next_level": 0,
        }

        updated, diagnostics = normalize_xp_progression(kira_like, preserve_level=True)
        self.assertEqual(updated["level"], 2)
        self.assertEqual(updated["experience_points"], 1827)
        self.assertEqual(updated["exp_required_for_next_level"], 900)
        self.assertTrue(diagnostics["ready_to_level"])
        self.assertTrue(diagnostics["threshold_mismatch"])


class TestLevelUpSessionXPGuards(unittest.TestCase):
    def test_level_up_session_preserves_cumulative_xp_and_recomputes_threshold(self):
        session = LevelUpSession("Scout Kira", 2, 3)
        session.character_data = {
            "name": "Scout Kira",
            "level": 2,
            "experience_points": 1827,
            "exp_required_for_next_level": 900,
        }

        raw_changes = json.dumps(
            {
                "level": 3,
                "experience_points": 0,
                "exp_required_for_next_level": 900,
                "maxHitPoints": 18,
            }
        )
        normalized = json.loads(session._normalize_final_level_up_changes(raw_changes))

        self.assertEqual(normalized["level"], 3)
        self.assertEqual(normalized["exp_required_for_next_level"], 2700)
        self.assertNotIn("experience_points", normalized)
        self.assertEqual(normalized["maxHitPoints"], 18)


class TestRepairAndPromptContracts(unittest.TestCase):
    def test_repair_character_data_normalizes_threshold_without_auto_leveling(self):
        repaired = repair_character_data(
            {
                "name": "Scout Kira",
                "level": 2,
                "experience_points": 1827,
                "exp_required_for_next_level": 2700,
                "equipment": [],
                "attacksAndSpellcasting": [],
            }
        )

        self.assertEqual(repaired["level"], 2)
        self.assertEqual(repaired["experience_points"], 1827)
        self.assertEqual(repaired["exp_required_for_next_level"], 900)

    def test_legacy_guidance_no_longer_resets_xp_to_zero(self):
        guidance = get_level_up_guidance("Scout Kira", 2, 3)
        self.assertNotIn("Set experience_points to 0", guidance)
        self.assertIn("Preserve the current cumulative experience_points value", guidance)

    def test_leveling_prompts_reference_cumulative_xp_semantics(self):
        info_path = os.path.join(REPO_ROOT, "prompts", "leveling", "leveling_info.txt")
        validation_path = os.path.join(REPO_ROOT, "prompts", "leveling", "leveling_validation_prompt.txt")

        with open(info_path, "r", encoding="utf-8") as f:
            info_content = f.read()
        with open(validation_path, "r", encoding="utf-8") as f:
            validation_content = f.read()

        self.assertIn("Do NOT reset cumulative experience_points", info_content)
        self.assertIn("Reject any response that resets experience_points to 0", validation_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
