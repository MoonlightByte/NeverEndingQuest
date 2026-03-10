# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Save/Module Contract Parity Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Phase 1B regression tests for prompt/validator/runtime contract alignment.
"""

import os
import re
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRuntimeContractBaseline(unittest.TestCase):
    """Lock the runtime contract for covered save/module actions."""

    @classmethod
    def setUpClass(cls):
        action_handler_path = os.path.join(REPO_ROOT, "core", "ai", "action_handler.py")
        module_builder_path = os.path.join(REPO_ROOT, "core", "generators", "module_builder.py")

        with open(action_handler_path, "r", encoding="utf-8") as f:
            cls.action_handler = f.read()

        with open(module_builder_path, "r", encoding="utf-8") as f:
            cls.module_builder = f.read()

    def test_save_game_runtime_contract(self):
        """saveGame runtime contract uses description + saveMode."""
        self.assertIn('parameters.get("description", "")', self.action_handler)
        self.assertIn('parameters.get("saveMode", "essential")', self.action_handler)

    def test_restore_game_runtime_contract(self):
        """restoreGame runtime contract uses saveFolder."""
        self.assertIn('elif action_type == ACTION_RESTORE_GAME:', self.action_handler)
        self.assertIn('save_folder = parameters.get("saveFolder")', self.action_handler)

    def test_delete_save_runtime_contract(self):
        """deleteSave runtime contract uses saveFolder."""
        self.assertIn('elif action_type == ACTION_DELETE_SAVE:', self.action_handler)
        self.assertIn('save_folder = parameters.get("saveFolder")', self.action_handler)

    def test_list_saves_runtime_contract(self):
        """listSaves requires no explicit parameter extraction."""
        start = self.action_handler.find('elif action_type == ACTION_LIST_SAVES:')
        end = self.action_handler.find('elif action_type == ACTION_DELETE_SAVE:')
        self.assertNotEqual(start, -1, "Missing ACTION_LIST_SAVES branch")
        self.assertNotEqual(end, -1, "Missing ACTION_DELETE_SAVE branch")
        block = self.action_handler[start:end]
        self.assertNotIn('parameters.get("', block, "listSaves should not require parameters")

    def test_create_new_module_runtime_narrative_handoff(self):
        """createNewModule runtime accepts narrative-driven payload."""
        self.assertIn('elif action_type == ACTION_CREATE_NEW_MODULE:', self.action_handler)
        self.assertIn('if len(parameters) == 1 and isinstance(list(parameters.values())[0], str):', self.action_handler)
        self.assertIn('parameters = {"narrative": narrative}', self.action_handler)

    def test_module_builder_accepts_narrative_or_concept(self):
        """Module builder accepts narrative-first payload with concept fallback."""
        self.assertIn('narrative = params.get("narrative") or params.get("concept")', self.module_builder)


class TestPromptValidatorContractParity(unittest.TestCase):
    """Enforce covered contract parity across prompt and validator variants."""

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

    def test_system_prompt_variants_include_save_actions(self):
        """Both system prompt variants must document covered save actions."""
        required_actions = ["saveGame", "restoreGame", "listSaves", "deleteSave"]
        for key in ("system_compressed", "system_full"):
            for action_name in required_actions:
                self.assertIn(
                    action_name,
                    self.content[key],
                    msg=f"{key} missing action contract for {action_name}"
                )

    def test_validator_variants_use_save_folder_for_restore_delete(self):
        """Validator must use saveFolder for restore/delete contracts."""
        pattern_restore = re.compile(r"restoreGame\s*:\s*\{[^}]*saveFolder", re.IGNORECASE)
        pattern_delete = re.compile(r"deleteSave\s*:\s*\{[^}]*saveFolder", re.IGNORECASE)

        for key in ("validator_compressed", "validator_full"):
            self.assertRegex(self.content[key], pattern_restore, msg=f"{key} missing restoreGame saveFolder contract")
            self.assertRegex(self.content[key], pattern_delete, msg=f"{key} missing deleteSave saveFolder contract")

    def test_validator_variants_do_not_require_save_name_for_restore_delete(self):
        """Validator must not retain stale saveName contract for restore/delete."""
        stale_restore = re.compile(r"restoreGame\s*:\s*\{[^}]*saveName", re.IGNORECASE)
        stale_delete = re.compile(r"deleteSave\s*:\s*\{[^}]*saveName", re.IGNORECASE)

        for key in ("validator_compressed", "validator_full"):
            self.assertIsNone(stale_restore.search(self.content[key]), msg=f"{key} still has stale restoreGame saveName contract")
            self.assertIsNone(stale_delete.search(self.content[key]), msg=f"{key} still has stale deleteSave saveName contract")

    def test_validator_variants_create_module_accepts_narrative(self):
        """Validator must accept narrative-driven createNewModule contract."""
        narrative_pattern = re.compile(r"createNewModule\s*:\s*\{[^}]*narrative", re.IGNORECASE)
        for key in ("validator_compressed", "validator_full"):
            self.assertRegex(self.content[key], narrative_pattern, msg=f"{key} missing createNewModule narrative contract")

    def test_validator_variants_create_module_not_rigid_two_field_shape(self):
        """Validator must not require rigid moduleName+startingLocation-only shape."""
        rigid_pattern = re.compile(
            r"createNewModule\s*:\s*\{\s*\"?moduleName\"?\s*:\s*[^,}]+,\s*\"?startingLocation\"?\s*:",
            re.IGNORECASE,
        )
        for key in ("validator_compressed", "validator_full"):
            self.assertIsNone(
                rigid_pattern.search(self.content[key]),
                msg=f"{key} still documents rigid createNewModule moduleName+startingLocation shape",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
