# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - updateCharacterInfo ops Contract Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Phase 1 contract tests for additive updateCharacterInfo ops support.
"""

import os
import re
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

INITIAL_OPS = {
    "set_hp",
    "hp_delta",
    "spell_slot_delta",
    "inventory_add",
    "inventory_remove",
    "currency_delta",
    "condition_add",
    "condition_remove",
}


class TestOpsContractPromptParity(unittest.TestCase):
    """Lock prompt/validator ops contract expectations."""

    @classmethod
    def setUpClass(cls):
        paths = {
            "system_compressed": os.path.join(REPO_ROOT, "prompts", "system_prompt_compressed.txt"),
            "validation_compressed": os.path.join(REPO_ROOT, "prompts", "validation", "validation_prompt_compressed.txt"),
        }
        cls.content = {}
        for key, path in paths.items():
            with open(path, "r", encoding="utf-8") as f:
                cls.content[key] = f.read()

    def test_initial_supported_ops_set_locked(self):
        self.assertEqual(
            INITIAL_OPS,
            {
                "set_hp",
                "hp_delta",
                "spell_slot_delta",
                "inventory_add",
                "inventory_remove",
                "currency_delta",
                "condition_add",
                "condition_remove",
            },
        )

    def test_system_prompt_documents_additive_ops(self):
        pattern = re.compile(
            r'updateCharacterInfo\s*:\s*\{[^\n]*"characterName"[^\n]*"changes"[^\n]*"ops"',
            re.IGNORECASE,
        )
        self.assertRegex(
            self.content["system_compressed"],
            pattern,
            msg="system_prompt_compressed must document additive updateCharacterInfo ops contract",
        )

    def test_validation_prompt_documents_additive_ops(self):
        pattern = re.compile(
            r'updateCharacterInfo\s*:\s*\{[^\n]*characterName[^\n]*changes[^\n]*ops',
            re.IGNORECASE,
        )
        self.assertRegex(
            self.content["validation_compressed"],
            pattern,
            msg="validation_prompt_compressed must accept additive updateCharacterInfo ops contract",
        )

    def test_prompts_reference_all_initial_ops(self):
        for op_name in sorted(INITIAL_OPS):
            self.assertIn(op_name, self.content["system_compressed"], msg=f"system prompt missing op {op_name}")
            self.assertIn(op_name, self.content["validation_compressed"], msg=f"validation prompt missing op {op_name}")

    def test_legacy_changes_only_path_remains_documented(self):
        self.assertIn("changes", self.content["system_compressed"])
        self.assertIn("changes", self.content["validation_compressed"])


class TestOpsRuntimeSourceContracts(unittest.TestCase):
    """Lock runtime reference expectations for upcoming ops implementation."""

    @classmethod
    def setUpClass(cls):
        paths = {
            "action_handler": os.path.join(REPO_ROOT, "core", "ai", "action_handler.py"),
            "update_character_info": os.path.join(REPO_ROOT, "updates", "update_character_info.py"),
        }
        cls.content = {}
        for key, path in paths.items():
            with open(path, "r", encoding="utf-8") as f:
                cls.content[key] = f.read()

    def test_runtime_references_ops_field(self):
        self.assertIn('"ops"', self.content["action_handler"], msg="action_handler must reference ops field")
        self.assertIn('"ops"', self.content["update_character_info"], msg="update_character_info must reference ops field")

    def test_runtime_still_supports_legacy_changes_field(self):
        self.assertIn('"changes"', self.content["action_handler"])
        self.assertIn('"changes"', self.content["update_character_info"])

    def test_deterministic_fallback_reason_codes_present(self):
        update_source = self.content["update_character_info"]
        self.assertIn("ops_absent", update_source)
        self.assertIn("ops_invalid_with_changes_fallback", update_source)
        self.assertIn("ops_unsupported_with_changes_fallback", update_source)

    def test_action_handler_logs_ops_route_marker(self):
        self.assertIn("CHAR_OPS_ROUTE", self.content["action_handler"])


class TestOpsRoutingBehaviorContracts(unittest.TestCase):
    """Runtime routing behavior tests for structured/prose/mixed payloads."""

    def test_prose_only_classification(self):
        from utils.character_ops_routing import classify_character_update_payload

        result = classify_character_update_payload("Removed 1 arrow from inventory", None)
        self.assertEqual(result["mode"], "prose_fallback")
        self.assertEqual(result["reason"], "ops_absent")

    def test_structured_only_classification(self):
        from utils.character_ops_routing import classify_character_update_payload

        result = classify_character_update_payload("", [{"op": "set_hp", "value": 12}])
        self.assertEqual(result["mode"], "structured_only")
        self.assertEqual(result["reason"], "ops_present_no_changes")

    def test_mixed_classification(self):
        from utils.character_ops_routing import classify_character_update_payload

        result = classify_character_update_payload(
            "Applied potion healing",
            [{"op": "hp_delta", "delta": 4}],
        )
        self.assertEqual(result["mode"], "mixed")
        self.assertEqual(result["reason"], "ops_present_with_changes")

    def test_invalid_ops_with_changes_fallback_classification(self):
        from utils.character_ops_routing import classify_character_update_payload

        result = classify_character_update_payload("Spent 10 gold", "not-a-list")
        self.assertEqual(result["mode"], "prose_fallback")
        self.assertEqual(result["reason"], "ops_invalid_with_changes_fallback")


if __name__ == "__main__":
    unittest.main(verbosity=2)
