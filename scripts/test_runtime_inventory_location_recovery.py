# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Runtime Inventory/Location Recovery Regressions
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Lock tests for deterministic party-item transfer recovery and startup scene
location recovery.
"""

import os
import sys
import unittest
from unittest.mock import patch


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _ops_by_character(actions):
    by_character = {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("action") != "updateCharacterInfo":
            continue
        params = action.get("parameters", {})
        if not isinstance(params, dict):
            continue
        character_name = str(params.get("characterName") or "").strip()
        ops = params.get("ops", [])
        op_names = [str(op.get("op") or "").strip() for op in ops if isinstance(op, dict)]
        by_character.setdefault(character_name, []).extend(op_names)
    return by_character


class TestPartyItemTransferRecovery(unittest.TestCase):
    def setUp(self):
        self.party_tracker = {
            "partyMembers": ["Redax", "Xorn"],
            "partyNPCs": [],
        }

    def test_reliquary_handoff_recovers_both_sides(self):
        from utils.scene_item_reconcile import evaluate_party_item_transfer_recovery_decision

        parsed_response = {
            "narration": "Redax hands the Reliquary of Saint Rydal to Xorn.",
            "actions": [],
        }
        conversation_history = [{"role": "user", "content": "I tell Redax to pass the reliquary to Xorn."}]

        with patch("utils.scene_item_reconcile.get_character_state") as mock_get_state:
            mock_get_state.side_effect = lambda name: {
                "equipment": [{"item_name": "Reliquary of Saint Rydal", "description": "Sacred relic.", "quantity": 1}],
                "ammunition": [],
            } if name == "Redax" else {"equipment": [], "ammunition": []}

            decision = evaluate_party_item_transfer_recovery_decision(
                parsed_response=parsed_response,
                user_utterance="",
                conversation_history=conversation_history,
                party_tracker_data=self.party_tracker,
            )

        inferred = decision.get("inferred_actions", [])
        self.assertGreaterEqual(len(inferred), 2)
        ops = _ops_by_character(inferred)
        self.assertIn("inventory_add", ops.get("Xorn", []))
        self.assertIn("inventory_remove", ops.get("Redax", []))

    def test_receiver_self_stow_backfills_missing_ownership(self):
        from utils.scene_item_reconcile import evaluate_party_item_transfer_recovery_decision

        parsed_response = {
            "narration": "Xorn places the reliquary into the explorer's pack.",
            "actions": [],
        }
        conversation_history = [
            {"role": "assistant", "content": "Redax hands the Reliquary of Saint Rydal to Xorn."},
            {"role": "user", "content": "Xorn secures it."},
        ]

        with patch("utils.scene_item_reconcile.get_character_state") as mock_get_state:
            mock_get_state.side_effect = lambda name: {
                "equipment": [{"item_name": "Reliquary of Saint Rydal", "description": "Sacred relic.", "quantity": 1}],
                "ammunition": [],
            } if name == "Redax" else {"equipment": [], "ammunition": []}

            decision = evaluate_party_item_transfer_recovery_decision(
                parsed_response=parsed_response,
                user_utterance="",
                conversation_history=conversation_history,
                party_tracker_data=self.party_tracker,
            )

        inferred = decision.get("inferred_actions", [])
        ops = _ops_by_character(inferred)
        self.assertIn("inventory_add", ops.get("Xorn", []))

    def test_ambiguous_transfer_language_is_noop(self):
        from utils.scene_item_reconcile import evaluate_party_item_transfer_recovery_decision

        parsed_response = {
            "narration": "Redax offers some supplies to the group.",
            "actions": [],
        }

        with patch("utils.scene_item_reconcile.get_character_state", return_value={"equipment": [], "ammunition": []}):
            decision = evaluate_party_item_transfer_recovery_decision(
                parsed_response=parsed_response,
                user_utterance="",
                conversation_history=[],
                party_tracker_data=self.party_tracker,
            )

        self.assertEqual(decision.get("inferred_actions"), [])

    def test_existing_explicit_transfer_actions_are_not_duplicated(self):
        from utils.scene_item_reconcile import evaluate_party_item_transfer_recovery_decision

        parsed_response = {
            "narration": "Redax hands the Reliquary of Saint Rydal to Xorn.",
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Redax",
                        "ops": [{"op": "inventory_remove", "item": "Reliquary of Saint Rydal", "quantity": 1}],
                    },
                },
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Xorn",
                        "ops": [{"op": "inventory_add", "item": "Reliquary of Saint Rydal", "quantity": 1}],
                    },
                },
            ],
        }

        with patch("utils.scene_item_reconcile.get_character_state") as mock_get_state:
            mock_get_state.side_effect = lambda _name: {"equipment": [], "ammunition": []}

            decision = evaluate_party_item_transfer_recovery_decision(
                parsed_response=parsed_response,
                user_utterance="",
                conversation_history=[],
                party_tracker_data=self.party_tracker,
            )

        self.assertEqual(decision.get("inferred_actions"), [])


class TestStartupSceneLocationRecovery(unittest.TestCase):
    def setUp(self):
        self.module_locations = [
            {
                "id": "NIG01",
                "name": "Room 1: Ma's Watering Hole",
                "area_id": "NIG001",
                "area_name": "Night_of_the_Restless_Dead Main Area",
                "source_room_title": "Ma's Watering Hole",
            },
            {
                "id": "NIG04",
                "name": "Room 4: Priest's Lodging",
                "area_id": "NIG001",
                "area_name": "Night_of_the_Restless_Dead Main Area",
                "source_room_title": "Priest's Lodging",
            },
        ]

    def test_startup_recovers_priests_lodging_from_recent_scene(self):
        from utils.travel_state_sync_guard import evaluate_startup_scene_location_recovery_decision

        conversation_history = [
            {"role": "assistant", "content": "You are now in the priest's lodging, and the room goes still."},
            {"role": "user", "content": "We bar the door and inspect the room."},
        ]

        decision = evaluate_startup_scene_location_recovery_decision(
            conversation_history=conversation_history,
            current_location_id="NIG01",
            current_area_id="NIG001",
            known_location_names=["Room 1: Ma's Watering Hole", "Room 4: Priest's Lodging"],
            module_locations=self.module_locations,
        )

        inferred = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred), 1)
        self.assertEqual(inferred[0].get("action"), "updatePartyTracker")
        self.assertEqual(inferred[0].get("parameters", {}).get("currentLocationId"), "NIG04")

    def test_ambiguous_recent_scene_evidence_does_not_rewrite_location(self):
        from utils.travel_state_sync_guard import evaluate_startup_scene_location_recovery_decision

        conversation_history = [
            {"role": "assistant", "content": "You are in the priest's lodging, but then you return to Ma's Watering Hole."},
            {"role": "assistant", "content": "Both rooms remain in view as you move between them."},
        ]

        decision = evaluate_startup_scene_location_recovery_decision(
            conversation_history=conversation_history,
            current_location_id="NIG01",
            current_area_id="NIG001",
            known_location_names=["Room 1: Ma's Watering Hole", "Room 4: Priest's Lodging"],
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])

    def test_startup_transition_replay_trusts_latest_transition_destination(self):
        from utils.travel_state_sync_guard import evaluate_startup_scene_location_recovery_decision

        conversation_history = [
            {"role": "assistant", "content": "The priest's lodging falls quiet behind you."},
            {"role": "user", "content": "Location transition: Priest's Lodging (NIG04) to Ma's Watering Hole (NIG01)"},
            {"role": "assistant", "content": "You gather at Ma's Watering Hole and bar the shutters."},
        ]

        decision = evaluate_startup_scene_location_recovery_decision(
            conversation_history=conversation_history,
            current_location_id="NIG04",
            current_area_id="NIG001",
            known_location_names=["Room 1: Ma's Watering Hole", "Room 4: Priest's Lodging"],
            module_locations=self.module_locations,
        )

        inferred = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred), 1)
        self.assertEqual(decision.get("reconciliation"), "startup_transition_replay")
        self.assertEqual(inferred[0].get("parameters", {}).get("currentLocationId"), "NIG01")


class TestRuntimeInventoryLocationRecoverySourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "main.py"), "r", encoding="utf-8") as file_handle:
            cls.main_source = file_handle.read()
        with open(
            os.path.join(REPO_ROOT, "prompts", "validation", "validation_prompt_compressed.txt"),
            "r",
            encoding="utf-8",
        ) as file_handle:
            cls.validation_prompt_compressed = file_handle.read()
        with open(
            os.path.join(REPO_ROOT, "prompts", "validation", "validation_prompt.txt"),
            "r",
            encoding="utf-8",
        ) as file_handle:
            cls.validation_prompt = file_handle.read()

    def test_main_runs_inventory_recovery_before_narration_only_skip(self):
        self.assertIn("evaluate_party_item_transfer_recovery_decision", self.main_source)
        recovery_index = self.main_source.index("evaluate_party_item_transfer_recovery_decision")
        skip_index = self.main_source.index("should_skip_llm_validation")
        self.assertLess(recovery_index, skip_index)

    def test_main_runs_startup_scene_location_recovery_before_history_refresh(self):
        self.assertIn("evaluate_startup_scene_location_recovery_decision", self.main_source)
        self.assertIn("STATE_SYNC: Startup scene location recovered", self.main_source)

    def test_validation_contract_rejects_one_sided_inventory_transfer(self):
        self.assertIn("invalid_one_sided", self.validation_prompt_compressed)
        self.assertIn("One-sided transfers are invalid", self.validation_prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
