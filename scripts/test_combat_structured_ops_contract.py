# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - combat structured ops Contract Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Step 1.1 contract tests for combat-structured-pc-allied-ops-pilot.
"""

import os
import re
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


SUPPORTED_COMBAT_OPS = {
    "hp_delta",
    "set_hp",
    "spell_slot_delta",
    "condition_add",
    "condition_remove",
    "inventory_remove",
    "inventory_add",
}


class TestCombatStructuredOpsOpenSpecContracts(unittest.TestCase):
    """Lock OpenSpec artifacts for the combat structured-ops pilot."""

    @classmethod
    def setUpClass(cls):
        change_root = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-structured-pc-allied-ops-pilot",
        )
        cls.paths = {
            "proposal": os.path.join(change_root, "proposal.md"),
            "design": os.path.join(change_root, "design.md"),
            "tasks": os.path.join(change_root, "tasks.md"),
            "spec": os.path.join(
                change_root,
                "specs",
                "tt-combat-structured-character-ops-routing",
                "spec.md",
            ),
        }
        cls.content = {}
        for key, path in cls.paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_supported_combat_ops_set_locked(self):
        self.assertEqual(
            SUPPORTED_COMBAT_OPS,
            {
                "hp_delta",
                "set_hp",
                "spell_slot_delta",
                "condition_add",
                "condition_remove",
                "inventory_remove",
                "inventory_add",
            },
        )

    def test_mixed_changes_and_ops_preference_documented(self):
        self.assertIn("changes + ops", self.content["proposal"])
        self.assertIn("changes + ops", self.content["design"])
        self.assertIn("both `changes` and supported `ops`", self.content["spec"])

    def test_enemy_side_update_encounter_deferral_documented(self):
        self.assertIn("enemy-side combat mutations", self.content["proposal"])
        self.assertIn("remain on `updateEncounter`", self.content["proposal"])
        self.assertIn("Enemy-side mutations SHALL remain on `updateEncounter`", self.content["design"])
        self.assertIn("Enemy-side combat mutations SHALL remain on `updateEncounter`", self.content["spec"])

    def test_prose_fallback_compatibility_documented(self):
        self.assertIn("prose fallback", self.content["proposal"])
        self.assertIn("prose-only", self.content["spec"])
        self.assertIn("Prose-only combat payload remains valid during migration", self.content["spec"])
        self.assertIn("Preserve prose-only fallback coverage", self.content["tasks"])

    def test_tasks_step_1_1_scope_present(self):
        self.assertIn("1.1 Add focused combat contract tests", self.content["tasks"])
        self.assertIn("explicit enemy-side `updateEncounter` deferral", self.content["tasks"])

    def test_design_documents_full_supported_combat_ops_set(self):
        design_text = self.content["design"]
        start_marker = "**Decision:** Combat examples and tests SHALL focus first on:"
        end_marker = "**Rationale:**"
        start_index = design_text.find(start_marker)
        self.assertNotEqual(start_index, -1, msg="Design is missing supported combat ops decision block")

        end_index = design_text.find(end_marker, start_index)
        self.assertNotEqual(end_index, -1, msg="Design supported combat ops decision block has no rationale boundary")

        decision_block = design_text[start_index:end_index]
        decision_ops = set(re.findall(r"`([a-z_]+)`", decision_block))
        self.assertEqual(
            decision_ops,
            SUPPORTED_COMBAT_OPS,
            msg="Design supported combat-facing ops list drifted from locked Step 1.2 contract",
        )

    def test_tasks_document_full_supported_combat_ops_set(self):
        tasks_text = self.content["tasks"]
        line_match = re.search(
            r"1\.2 Add contract coverage for supported combat-facing ops examples \(([^\n]+)\)\.",
            tasks_text,
        )
        if line_match is None:
            self.fail("Tasks missing Step 1.2 supported ops list")

        task_ops = set(re.findall(r"`([a-z_]+)`", line_match.group(1)))
        self.assertEqual(
            task_ops,
            SUPPORTED_COMBAT_OPS,
            msg="Tasks supported combat-facing ops list drifted from locked Step 1.2 contract",
        )

    def test_proposal_categories_cover_supported_combat_examples(self):
        proposal_text = self.content["proposal"]
        self.assertIn("combat examples for HP, spell slots, ammo/item spend, and conditions", proposal_text)


class TestCombatStructuredOpsRuntimeSourceContracts(unittest.TestCase):
    """Lock current runtime touchpoints before prompt/validator migration."""

    @classmethod
    def setUpClass(cls):
        cls.paths = {
            "action_handler": os.path.join(REPO_ROOT, "core", "ai", "action_handler.py"),
            "update_character_info": os.path.join(REPO_ROOT, "updates", "update_character_info.py"),
            "sim_prompt": os.path.join(
                REPO_ROOT,
                "prompts",
                "combat",
                "combat_sim_prompt_multipc_compressed.txt",
            ),
            "validation_prompt": os.path.join(
                REPO_ROOT,
                "prompts",
                "combat",
                "combat_validation_prompt_multipc_compressed.txt",
            ),
        }
        cls.content = {}
        for key, path in cls.paths.items():
            if path.endswith(".py"):
                with open(path, "r", encoding="utf-8") as file_handle:
                    cls.content[key] = file_handle.read()

    def test_combat_prompt_files_exist(self):
        self.assertTrue(os.path.exists(self.paths["sim_prompt"]))
        self.assertTrue(os.path.exists(self.paths["validation_prompt"]))

    def test_action_handler_references_ops_route_markers(self):
        source = self.content["action_handler"]
        self.assertIn("CHAR_OPS_ROUTE", source)
        self.assertIn("get_last_ops_routing_marker", source)
        self.assertIn("update_character_info(character_name, changes, ops=ops)", source)

    def test_update_character_info_has_deterministic_ops_engine(self):
        source = self.content["update_character_info"]
        self.assertIn("_apply_character_ops_deterministic", source)
        self.assertIn("SUPPORTED_CHARACTER_OPS", source)
        self.assertIn("classify_character_update_payload", source)

    def test_update_character_info_has_fallback_reason_markers(self):
        source = self.content["update_character_info"]
        self.assertIn("ops_absent", source)
        self.assertIn("ops_invalid_with_changes_fallback", source)
        self.assertIn("ops_unsupported_with_changes_fallback", source)


class TestCombatStructuredOpsCompatibilityContracts(unittest.TestCase):
    """Lock prose compatibility and mixed payload acceptance for combat migration."""

    @classmethod
    def setUpClass(cls):
        change_tasks = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-structured-pc-allied-ops-pilot",
            "tasks.md",
        )
        with open(change_tasks, "r", encoding="utf-8") as file_handle:
            cls.tasks_content = file_handle.read()

    def test_tasks_include_step_1_3_contract(self):
        self.assertIn(
            "1.3 Preserve prose-only fallback coverage and mixed-payload acceptance in combat-specific tests.",
            self.tasks_content,
        )

    def test_prose_only_payload_classification_remains_compatible(self):
        from utils.character_ops_routing import classify_character_update_payload

        result = classify_character_update_payload(
            "Takes 6 slashing damage (HP 28->22).",
            None,
        )
        self.assertEqual(result["mode"], "prose_fallback")
        self.assertEqual(result["reason"], "ops_absent")

    def test_mixed_payload_classification_remains_accepted(self):
        from utils.character_ops_routing import classify_character_update_payload

        result = classify_character_update_payload(
            "Expended level 3 spell slot.",
            [{"op": "spell_slot_delta", "level": "level3", "delta": -1}],
        )
        self.assertEqual(result["mode"], "mixed")
        self.assertEqual(result["reason"], "ops_present_with_changes")

    def test_invalid_ops_with_changes_still_falls_back(self):
        from utils.character_ops_routing import classify_character_update_payload

        result = classify_character_update_payload(
            "Expended 1 arrow.",
            "not-a-list",
        )
        self.assertEqual(result["mode"], "prose_fallback")
        self.assertEqual(result["reason"], "ops_invalid_with_changes_fallback")


if __name__ == "__main__":
    unittest.main(verbosity=2)
