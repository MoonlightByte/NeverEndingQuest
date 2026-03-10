# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Runtime Prompt Authority Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Source-contract tests for compressed prompt runtime authority.
"""

import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRuntimePromptAuthority(unittest.TestCase):
    """Ensure live runtime paths use compressed prompt sources."""

    @classmethod
    def setUpClass(cls):
        main_path = os.path.join(REPO_ROOT, "main.py")
        conversation_utils_path = os.path.join(REPO_ROOT, "core", "ai", "conversation_utils.py")

        with open(main_path, "r", encoding="utf-8") as f:
            cls.main_source = f.read()

        with open(conversation_utils_path, "r", encoding="utf-8") as f:
            cls.conversation_utils_source = f.read()

    def test_main_initialization_uses_compressed_system_prompt(self):
        self.assertIn('with open("prompts/system_prompt_compressed.txt", "r", encoding="utf-8") as file:', self.main_source)
        self.assertNotIn('with open("prompts/system_prompt.txt", "r", encoding="utf-8") as file:', self.main_source)

    def test_validation_prompt_loader_uses_compressed_variant(self):
        self.assertIn('prompt_file = "prompts/validation/validation_prompt_compressed.txt"', self.main_source)
        self.assertNotIn('prompt_file = "prompts/validation/validation_prompt.txt"', self.main_source)

    def test_conversation_utils_uses_compressed_prompt_identity(self):
        self.assertIn('"prompts", "system_prompt_compressed.txt"', self.conversation_utils_source)
        self.assertNotIn('"prompts", "system_prompt.txt"', self.conversation_utils_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
