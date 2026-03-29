# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Validation Skip Routing Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for conservative low-risk LLM validation skip routing.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestValidationSkipRoutingBehavior(unittest.TestCase):
    """Behavior tests for low-risk skip helper."""

    def test_narration_only_can_skip(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={"narration": "Nothing changes.", "actions": []},
            deterministic_passed=True,
        )
        self.assertTrue(decision)
        self.assertEqual(reason, "narration_only")

    def test_low_risk_actions_can_skip(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={
                "actions": [
                    {"action": "updateTime", "parameters": {"timeEstimate": 10}},
                    {"action": "saveGame", "parameters": {"description": "checkpoint"}},
                ]
            },
            deterministic_passed=True,
        )
        self.assertTrue(decision)
        self.assertEqual(reason, "low_risk_actions_only")

    def test_high_risk_action_cannot_skip(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={"actions": [{"action": "createEncounter", "parameters": {}}]},
            deterministic_passed=True,
        )
        self.assertFalse(decision)
        self.assertIn("high_risk_action", reason)

    def test_non_low_risk_action_cannot_skip(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={
                "actions": [
                    {
                        "action": "updateCharacterInfo",
                        "parameters": {"characterName": "Acheron", "changes": "Removed 1 arrow."},
                    }
                ]
            },
            deterministic_passed=True,
        )
        self.assertFalse(decision)
        self.assertIn("non_low_risk_action", reason)

    def test_deterministic_failure_cannot_skip(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={"actions": []},
            deterministic_passed=False,
        )
        self.assertFalse(decision)
        self.assertEqual(reason, "deterministic_failed")

    def test_possession_query_turn_cannot_skip_even_without_actions(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={"actions": []},
            deterministic_passed=True,
            user_input="Do I still have the reliquary?",
            possession_checked=True,
        )
        self.assertFalse(decision)
        self.assertEqual(reason, "possession_query_turn")

    def test_possession_query_requires_authority_check_before_skip(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={"actions": []},
            deterministic_passed=True,
            user_input="Check my pack for the reliquary.",
            possession_checked=False,
        )
        self.assertFalse(decision)
        self.assertEqual(reason, "requires_possession_authority_check")

    def test_bookkeeping_correction_turn_cannot_skip(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={
                "narration": "Yes. You now have 16 copper coins in your currency pouch, and your inventory remains organized.",
                "actions": [],
            },
            deterministic_passed=True,
            user_input="That copper coin should be currency, not miscellaneous inventory.",
        )
        self.assertFalse(decision)
        self.assertEqual(reason, "explicit_bookkeeping_correction_turn")

    def test_pure_bookkeeping_clarification_can_still_skip(self):
        from utils.validation_routing import should_skip_llm_validation

        decision, reason = should_skip_llm_validation(
            response_json={
                "narration": "Yes. Copper coins are generally tracked as currency rather than miscellaneous inventory.",
                "actions": [],
            },
            deterministic_passed=True,
            user_input="Should that copper be tracked as currency instead of inventory?",
        )
        self.assertTrue(decision)
        self.assertEqual(reason, "narration_only")


class TestValidationSkipRoutingSourceContract(unittest.TestCase):
    """Source-contract checks for pipeline integration."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "main.py"), "r", encoding="utf-8") as f:
            cls.main_source = f.read()

    def test_main_invokes_skip_helper(self):
        self.assertIn("should_skip_llm_validation", self.main_source)
        self.assertIn("skip_llm_validation", self.main_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
