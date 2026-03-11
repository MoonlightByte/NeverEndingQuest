# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Combat Retry Hygiene Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Source-contract tests for combat validation retry hygiene.
"""

import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMBAT_MANAGER_PATH = os.path.join(
    REPO_ROOT,
    "core",
    "managers",
    "combat_manager.py",
)


class TestCombatRetryHygieneSourceContract(unittest.TestCase):
    """Lock retry-hygiene contracts for Step 4.2 implementation."""

    @classmethod
    def setUpClass(cls):
        with open(COMBAT_MANAGER_PATH, "r", encoding="utf-8") as file_handle:
            cls.combat_manager_source = file_handle.read()

    def test_validation_feedback_not_persisted_as_user_turn(self):
        self.assertNotIn(
            "conversation_history.append({\"role\": \"user\", \"content\": validation_result})",
            self.combat_manager_source,
            msg=(
                "Step 4.2 contract: validation_result feedback should remain "
                "retry-local and must not be appended as a user turn."
            ),
        )

    def test_invalid_json_retry_note_not_persisted_as_user_turn(self):
        self.assertNotIn(
            "conversation_history.append({\"role\": \"user\", \"content\": \"Invalid JSON format. Please try again.\"})",
            self.combat_manager_source,
            msg=(
                "Step 4.2 contract: invalid JSON retry notes must not be "
                "persisted as user turns in combat history."
            ),
        )

    def test_retry_hygiene_keeps_correction_notes_local(self):
        self.assertIn("retry_feedback_note", self.combat_manager_source)
        self.assertIn("retry_request_history", self.combat_manager_source)
        self.assertIn("retry_validation_history", self.combat_manager_source)
        self.assertNotIn(
            "conversation_history.append({\"role\": \"user\", \"content\": feedback})",
            self.combat_manager_source,
            msg=(
                "Step 4.2 contract: validation feedback should be passed via retry-local "
                "history and not appended to canonical conversation history."
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
