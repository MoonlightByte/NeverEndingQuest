# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Rest Contract Parity Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Phase 1A regression tests for prompt/validator/runtime rest contract alignment.
"""

import os
import re
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRestRuntimeBaseline(unittest.TestCase):
    """Lock runtime baseline for dedicated rest action."""

    @classmethod
    def setUpClass(cls):
        action_handler_path = os.path.join(REPO_ROOT, "core", "ai", "action_handler.py")
        with open(action_handler_path, "r", encoding="utf-8") as f:
            cls.action_handler = f.read()

    def test_runtime_defines_rest_action_constant(self):
        self.assertIn('ACTION_REST = "rest"', self.action_handler)

    def test_runtime_has_rest_branch(self):
        self.assertIn('elif action_type == ACTION_REST:', self.action_handler)
        self.assertIn('rest_type = parameters.get("type", "short")', self.action_handler)


class TestRestPromptValidatorParity(unittest.TestCase):
    """Enforce rest parity across prompt and validator variants."""

    @classmethod
    def setUpClass(cls):
        files = {
            "system_compressed": os.path.join(REPO_ROOT, "prompts", "system_prompt_compressed.txt"),
            "system_full": os.path.join(REPO_ROOT, "prompts", "system_prompt.txt"),
            "validator_compressed": os.path.join(REPO_ROOT, "prompts", "validation", "validation_prompt_compressed.txt"),
            "validator_full": os.path.join(REPO_ROOT, "prompts", "validation", "validation_prompt.txt"),
        }
        cls.content = {}
        for key, path in files.items():
            with open(path, "r", encoding="utf-8") as f:
                cls.content[key] = f.read()

    def test_system_prompt_variants_include_rest_contract(self):
        self.assertIn("rest", self.content["system_compressed"])
        self.assertIn("rest", self.content["system_full"])

    def test_validator_variants_include_rest_action(self):
        self.assertIn("rest: dedicated rest action; runtime applies mechanical recovery", self.content["validator_compressed"])
        self.assertIn('"rest": Dedicated narrator-layer rest action.', self.content["validator_full"])

    def test_validator_compressed_rest_params_present(self):
        self.assertRegex(
            self.content["validator_compressed"],
            re.compile(r"@ACTION_PARAMS=\{[\s\S]*\brest:\s*\{\"type\":\"short\|long\"", re.IGNORECASE),
        )

    def test_stale_rest_requirement_removed_from_compressed_validator(self):
        self.assertNotIn("updateTime+updateCharacterInfo REQUIRED", self.content["validator_compressed"])

    def test_stale_rest_requirement_removed_from_full_validator(self):
        self.assertNotIn("REQUIRED: updateCharacterInfo for ANY character benefits received", self.content["validator_full"])
        self.assertNotIn("REQUIRED: updateCharacterInfo for ALL characters resting", self.content["validator_full"])

    def test_stale_rest_command_mapping_removed_from_full_system_prompt(self):
        self.assertNotIn('/rest short` -> Use `updateTime` (60 mins) and `updateCharacterInfo`', self.content["system_full"])
        self.assertNotIn('/rest long` -> Use `updateTime` (480 mins) and `updateCharacterInfo`', self.content["system_full"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
