# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for deterministic character life-state hygiene."""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


from utils.character_state_hygiene import normalize_life_state_fields


class TestCharacterStateHygiene(unittest.TestCase):
    def test_positive_hp_clears_stale_unconscious_state(self):
        character_data = {
            "name": "Lidda Underbough",
            "hitPoints": 9,
            "maxHitPoints": 9,
            "status": "unconscious",
            "condition": "unconscious",
            "condition_affected": ["unconscious", "poisoned"],
            "deathSaves": {"successes": 2, "failures": 1},
        }

        normalized = normalize_life_state_fields(character_data)

        self.assertEqual(normalized["status"], "alive")
        self.assertEqual(normalized["condition"], "poisoned")
        self.assertEqual(normalized["condition_affected"], ["poisoned"])
        self.assertEqual(normalized["deathSaves"], {"successes": 0, "failures": 0})

    def test_zero_hp_enforces_unconscious_state_until_dead(self):
        character_data = {
            "name": "Lidda Underbough",
            "hitPoints": 0,
            "maxHitPoints": 9,
            "status": "alive",
            "condition": "none",
            "condition_affected": [],
            "deathSaves": {"successes": 0, "failures": 1},
        }

        normalized = normalize_life_state_fields(character_data)

        self.assertEqual(normalized["status"], "unconscious")
        self.assertEqual(normalized["condition"], "unconscious")
        self.assertIn("unconscious", normalized["condition_affected"])

    def test_three_failures_enforce_dead_state(self):
        character_data = {
            "name": "Lidda Underbough",
            "hitPoints": 0,
            "maxHitPoints": 9,
            "status": "unconscious",
            "condition": "unconscious",
            "condition_affected": ["unconscious"],
            "deathSaves": {"successes": 1, "failures": 3},
        }

        normalized = normalize_life_state_fields(character_data)

        self.assertEqual(normalized["status"], "dead")
        self.assertEqual(normalized["condition"], "none")
        self.assertEqual(normalized["condition_affected"], [])


class TestCharacterStateHygieneSourceContracts(unittest.TestCase):
    def test_pc_manager_normalizes_loaded_character_state(self):
        with open(os.path.join(REPO_ROOT, "utils", "pc_manager.py"), "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("normalize_life_state_fields", content)

    def test_combat_manager_normalizes_prompt_character_state(self):
        with open(os.path.join(REPO_ROOT, "core", "managers", "combat_manager.py"), "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("char_data = normalize_life_state_fields(dict(char_data))", content)
        self.assertIn("player_data = normalize_life_state_fields(player_data)", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
