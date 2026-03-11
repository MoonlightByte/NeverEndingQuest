# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Combat Truth Pack Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for touched-combatant extraction, inventory relevance gating, and
combat-manager truth-pack hook wiring.
"""

import ast
import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMBAT_MANAGER_PATH = os.path.join(
    REPO_ROOT,
    "core",
    "managers",
    "combat_manager.py",
)


def _load_helper_functions():
    with open(COMBAT_MANAGER_PATH, "r", encoding="utf-8") as file_handle:
        source = file_handle.read()

    parsed = ast.parse(source)
    target_names = {
        "_is_combat_inventory_or_ammo_change",
        "_extract_touched_character_updates_from_response_json",
    }
    selected_nodes = [
        node
        for node in parsed.body
        if isinstance(node, ast.FunctionDef) and node.name in target_names
    ]

    helper_module = ast.Module(body=selected_nodes, type_ignores=[])
    namespace = {}
    exec(compile(helper_module, filename=COMBAT_MANAGER_PATH, mode="exec"), namespace)
    return namespace


class TestCombatTruthPackBehavior(unittest.TestCase):
    """Behavior tests for combat touched-character extraction helpers."""

    @classmethod
    def setUpClass(cls):
        helper_namespace = _load_helper_functions()
        cls.extract_touched = staticmethod(
            helper_namespace["_extract_touched_character_updates_from_response_json"]
        )
        cls.inventory_relevance = staticmethod(
            helper_namespace["_is_combat_inventory_or_ammo_change"]
        )

    def test_extracts_touched_character_names_from_update_character_info_actions(self):
        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "HP 21->16 after claw hit",
                    },
                },
                {
                    "action": "updateEncounter",
                    "parameters": {"changes": "Enemy attacks summary"},
                },
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Scout Kira",
                        "changes": "Expended 1 arrow from ammunition",
                    },
                },
            ]
        }

        touched = self.extract_touched(response_json)

        self.assertIn("Acheron", touched)
        self.assertIn("Scout Kira", touched)
        self.assertEqual(len(touched["Acheron"]["changes"]), 1)
        self.assertEqual(len(touched["Scout Kira"]["changes"]), 1)

    def test_omits_truth_pack_inputs_when_no_update_character_info_actions_exist(self):
        response_json = {
            "actions": [
                {
                    "action": "updateEncounter",
                    "parameters": {"changes": "Enemy takes 8 damage"},
                },
                {"action": "exit", "parameters": {}},
            ]
        }

        touched = self.extract_touched(response_json)
        self.assertEqual(touched, {})

    def test_inventory_ammo_relevance_gating_contract(self):
        self.assertTrue(self.inventory_relevance("Expended 1 arrow from ammunition"))
        self.assertTrue(self.inventory_relevance("Removed rope from inventory"))
        self.assertFalse(self.inventory_relevance("HP 14->9 after bite damage"))
        self.assertFalse(self.inventory_relevance("Condition changed to poisoned"))


class TestCombatTruthPackSourceContract(unittest.TestCase):
    """Source-contract tests for combat validation truth-pack hook wiring."""

    @classmethod
    def setUpClass(cls):
        with open(COMBAT_MANAGER_PATH, "r", encoding="utf-8") as file_handle:
            cls.combat_manager_source = file_handle.read()

    def test_combat_manager_contains_truth_pack_context_hook(self):
        self.assertIn("=== TOUCHED COMBATANT TRUTH PACK ===", self.combat_manager_source)
        self.assertIn("_build_compact_combat_truth_pack(", self.combat_manager_source)

    def test_truth_pack_assembly_failure_is_fail_open(self):
        self.assertIn(
            "Skipping truth pack due to error",
            self.combat_manager_source,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
