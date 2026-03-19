# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Authoritative Transition/Inventory Reset Regressions
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Targeted tests for:
- Same-module authoritative transition validation
- Dormant transition post-processor fail-closed contracts
- Atomic tracked transfer rollback behavior
- Possession-query authority from committed state
- Active-character inventory grounding
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestSameModuleTransitionAuthority(unittest.TestCase):
    def test_nig04_to_nig05_validates_from_fresh_module_topology(self):
        from utils.authoritative_transition_validator import validate_same_module_transition_authority

        result = validate_same_module_transition_authority(
            module_name="Night_of_the_Restless_Dead",
            current_location_id="NIG04",
            destination_location_id="NIG05",
            current_area_id="NIG001",
        )

        self.assertTrue(result.get("applies"))
        self.assertTrue(result.get("valid"))
        self.assertIn("NIG05", result.get("path", []))

    def test_action_handler_routes_same_module_validation_through_authoritative_helper(self):
        action_handler_path = os.path.join(REPO_ROOT, "core", "ai", "action_handler.py")
        with open(action_handler_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("validate_same_module_transition_authority", source)
        self.assertIn("authoritative_result.get(\"applies\")", source)


class TestTransitionFailureHistoryHygieneContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "main.py"), "r", encoding="utf-8") as f:
            cls.main_source = f.read()

    def test_transition_postprocessor_is_dormant_by_default(self):
        self.assertIn("ENABLE_SEAMLESS_TRANSITION_POSTPROCESSOR = False", self.main_source)
        self.assertIn("if is_transition and ENABLE_SEAMLESS_TRANSITION_POSTPROCESSOR:", self.main_source)

    def test_transition_branch_checks_action_error_before_arrival_helpers(self):
        self.assertIn('if result.get("status") == "error":', self.main_source)
        self.assertIn("generate_arrival_narration", self.main_source)
        self.assertIn("generate_seamless_transition_narration", self.main_source)
        branch_start = self.main_source.index("if is_transition and ENABLE_SEAMLESS_TRANSITION_POSTPROCESSOR:")
        error_index = self.main_source.index('if result.get("status") == "error":', branch_start)
        arrival_index = self.main_source.index("generate_arrival_narration", branch_start)
        self.assertLess(error_index, arrival_index)


class TestTrackedTransferAtomicity(unittest.TestCase):
    def test_atomic_transfer_rolls_back_on_second_leg_failure(self):
        from utils.tracked_transfer_runtime import execute_atomic_transfer_pair

        state_store = {
            "Redax": {"equipment": [{"item_name": "Reliquary of Saint Rydal", "quantity": 1}]},
            "Xorn": {"equipment": []},
        }

        pair = {
            "item_name": "Reliquary of Saint Rydal",
            "quantity": 1,
            "giver_name": "Redax",
            "receiver_name": "Xorn",
            "add_action": {
                "action": "updateCharacterInfo",
                "parameters": {
                    "characterName": "Xorn",
                    "ops": [{"op": "inventory_add", "item": "Reliquary of Saint Rydal", "quantity": 1}],
                },
            },
            "remove_action": {
                "action": "updateCharacterInfo",
                "parameters": {
                    "characterName": "Redax",
                    "ops": [{"op": "inventory_remove", "item": "Reliquary of Saint Rydal", "quantity": 1}],
                },
            },
        }

        def _load_state(character_name):
            payload = state_store.get(character_name)
            return None if payload is None else {"equipment": [dict(item) for item in payload.get("equipment", [])]}

        def _save_state(character_name, payload):
            state_store[character_name] = {"equipment": [dict(item) for item in payload.get("equipment", [])]}
            return True

        def _apply(action):
            params = action.get("parameters", {})
            character_name = params.get("characterName")
            op = params.get("ops", [])[0]
            op_name = op.get("op")
            item_name = op.get("item")

            if op_name == "inventory_add":
                state_store[character_name]["equipment"].append({"item_name": item_name, "quantity": 1})
                return {"status": "continue", "needs_update": True}

            if op_name == "inventory_remove":
                return {"status": "error", "error_message": "Simulated remove failure"}

            return {"status": "continue", "needs_update": False}

        result = execute_atomic_transfer_pair(
            pair=pair,
            apply_update_fn=_apply,
            load_state_fn=_load_state,
            save_state_fn=_save_state,
        )

        self.assertFalse(result.get("ok"))
        redax_items = [item.get("item_name") for item in state_store["Redax"]["equipment"]]
        xorn_items = [item.get("item_name") for item in state_store["Xorn"]["equipment"]]
        self.assertIn("Reliquary of Saint Rydal", redax_items)
        self.assertNotIn("Reliquary of Saint Rydal", xorn_items)


class TestPossessionAuthority(unittest.TestCase):
    def test_possession_query_resolves_from_committed_state(self):
        from unittest.mock import patch

        from utils.inventory_possession_authority import evaluate_tracked_item_possession_query

        party_tracker = {
            "active_character": "Xorn",
            "partyMembers": ["Redax", "Xorn"],
            "partyNPCs": [],
        }

        with patch("utils.inventory_possession_authority.get_character_state") as mock_get_state:
            mock_get_state.side_effect = lambda name: {
                "equipment": [{"item_name": "Reliquary of Saint Rydal", "quantity": 1}],
                "ammunition": [],
            } if name == "Xorn" else {"equipment": [], "ammunition": []}

            decision = evaluate_tracked_item_possession_query(
                user_utterance="Do I still have the reliquary of saint rydal?",
                party_tracker_data=party_tracker,
            )

        self.assertTrue(decision.get("is_query"))
        self.assertTrue(decision.get("handled"))
        self.assertIn("Xorn currently has Reliquary of Saint Rydal", decision.get("response_text", ""))


class TestActiveCharacterInventoryGrounding(unittest.TestCase):
    def test_get_all_party_inventory_prefers_active_character(self):
        from core.ai.inventory_context_integration import get_all_party_inventory

        party_tracker = {
            "active_character": "Xorn",
            "partyMembers": ["Redax", "Xorn"],
            "party_npcs": [],
        }
        characters_data = {
            "Redax": {
                "equipment": [{"item_name": "Redax Token", "item_type": "miscellaneous", "description": "r"}],
                "attacksAndSpellcasting": [],
            },
            "Xorn": {
                "equipment": [{"item_name": "Xorn Token", "item_type": "miscellaneous", "description": "x"}],
                "attacksAndSpellcasting": [],
            },
        }

        inventory = get_all_party_inventory(party_tracker, characters_data)
        item_names = [item.get("name") for item in inventory]
        self.assertIn("Xorn Token", item_names)
        self.assertNotIn("Redax Token", item_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
