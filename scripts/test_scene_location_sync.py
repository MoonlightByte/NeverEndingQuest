#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Regression tests for scene-location sync when direct NPC interaction proves the
party has reached the NPC's location.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.travel_state_sync_guard import (
    evaluate_narrated_location_arrival_decision,
    evaluate_scene_location_sync_decision,
)


class TestNarratedLocationArrivalSyncDecision(unittest.TestCase):
    """Behavior tests for narrated arrival -> party location sync."""

    def setUp(self):
        self.module_locations = [
            {
                "id": "RO01",
                "name": "Rangers' Command Post",
                "area_id": "RO001",
                "area_name": "Rangers' Outpost",
            },
            {
                "id": "TW04",
                "name": "Hermit's Refuge",
                "area_id": "TW001",
                "area_name": "Thornwood Wilds",
            },
        ]

    def test_hermit_refuge_narrated_arrival_syncs_location(self):
        response_json = {
            "narration": (
                "At last, you push through the final screen of foliage and step into a secluded clearing. "
                "Before the Hermit's refuge, the forest falls silent."
            ),
            "actions": [],
        }

        decision = evaluate_narrated_location_arrival_decision(
            response_json=response_json,
            current_location_id="RO01",
            current_area_id="RO001",
            known_location_names=["Hermit's Refuge", "Rangers' Command Post"],
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "narrated_location_arrival_sync")
        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred_actions), 2)
        self.assertEqual(inferred_actions[0].get("action"), "updateTime")
        self.assertEqual(inferred_actions[0].get("parameters", {}).get("timeEstimate"), 20)
        self.assertEqual(inferred_actions[1].get("action"), "updatePartyTracker")
        params = inferred_actions[1].get("parameters", {})
        self.assertEqual(params.get("currentLocationId"), "TW04")
        self.assertEqual(params.get("currentLocation"), "Hermit's Refuge")

    def test_progress_only_narration_does_not_sync_location(self):
        response_json = {
            "narration": "Kira says the Hermit's refuge is just ahead and you should be there soon.",
            "actions": [],
        }

        decision = evaluate_narrated_location_arrival_decision(
            response_json=response_json,
            current_location_id="RO01",
            current_area_id="RO001",
            known_location_names=["Hermit's Refuge", "Rangers' Command Post"],
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])
        self.assertEqual(decision.get("reconciliation"), "none")

    def test_ambiguous_arrival_does_not_sync_location(self):
        response_json = {
            "narration": (
                "You arrive at the edge between the Rangers' Command Post and the Hermit's Refuge, "
                "uncertain where to settle."
            ),
            "actions": [],
        }

        decision = evaluate_narrated_location_arrival_decision(
            response_json=response_json,
            current_location_id="RO01",
            current_area_id="RO001",
            known_location_names=["Hermit's Refuge", "Rangers' Command Post"],
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])

    def test_explicit_transition_precedence_prevents_duplicate_sync(self):
        response_json = {
            "narration": "You step into Hermit's Refuge.",
            "actions": [
                {
                    "action": "transitionLocation",
                    "parameters": {"newLocation": "TW04"},
                }
            ],
        }

        decision = evaluate_narrated_location_arrival_decision(
            response_json=response_json,
            current_location_id="RO01",
            current_area_id="RO001",
            known_location_names=["Hermit's Refuge", "Rangers' Command Post"],
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])

    def test_explicit_update_time_is_authoritative_for_arrival_sync(self):
        response_json = {
            "narration": "You step into Hermit's Refuge.",
            "actions": [
                {
                    "action": "updateTime",
                    "parameters": {"timeEstimate": 12},
                }
            ],
        }

        decision = evaluate_narrated_location_arrival_decision(
            response_json=response_json,
            current_location_id="RO01",
            current_area_id="RO001",
            known_location_names=["Hermit's Refuge", "Rangers' Command Post"],
            module_locations=self.module_locations,
        )

        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred_actions), 1)
        self.assertEqual(inferred_actions[0].get("action"), "updatePartyTracker")


class TestSceneLocationSyncDecision(unittest.TestCase):
    """Behavior tests for direct NPC scene -> party location sync."""

    def setUp(self):
        self.module_locations = [
            {
                "id": "RO01",
                "name": "Rangers' Command Post",
                "area_id": "RO001",
                "area_name": "Rangers' Outpost",
            },
            {
                "id": "TW04",
                "name": "Hermit's Refuge",
                "area_id": "TW001",
                "area_name": "Thornwood Wilds",
            },
        ]

    def test_direct_address_to_maelo_syncs_party_location(self):
        response_json = {
            "narration": "Maelo opens his eyes and gestures the party closer to the fire.",
            "actions": [
                {
                    "action": "moveBackgroundNPC",
                    "parameters": {
                        "npcName": "Spirit-Touched Hermit Maelo",
                        "context": "The hermit receives the party in his clearing.",
                        "currentLocation": "TW04",
                    },
                }
            ],
        }

        decision = evaluate_scene_location_sync_decision(
            response_json=response_json,
            user_utterance="Hail Maelo, will you allow us entry to sit and speak with you?",
            current_location_id="RO01",
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "scene_location_sync")
        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred_actions), 1)
        self.assertEqual(inferred_actions[0].get("action"), "updatePartyTracker")
        params = inferred_actions[0].get("parameters", {})
        self.assertEqual(params.get("currentLocationId"), "TW04")
        self.assertEqual(params.get("currentLocation"), "Hermit's Refuge")
        self.assertEqual(params.get("currentAreaId"), "TW001")

    def test_no_sync_without_direct_npc_address(self):
        response_json = {
            "narration": "Maelo waits in his clearing beyond the stream.",
            "actions": [
                {
                    "action": "moveBackgroundNPC",
                    "parameters": {
                        "npcName": "Spirit-Touched Hermit Maelo",
                        "currentLocation": "TW04",
                    },
                }
            ],
        }

        decision = evaluate_scene_location_sync_decision(
            response_json=response_json,
            user_utterance="How far away is the refuge?",
            current_location_id="RO01",
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])
        self.assertEqual(decision.get("reconciliation"), "none")

    def test_no_sync_when_transition_already_present(self):
        response_json = {
            "narration": "The party reaches the refuge and calls out to Maelo.",
            "actions": [
                {
                    "action": "transitionLocation",
                    "parameters": {"newLocation": "TW04"},
                },
                {
                    "action": "moveBackgroundNPC",
                    "parameters": {
                        "npcName": "Spirit-Touched Hermit Maelo",
                        "currentLocation": "TW04",
                    },
                },
            ],
        }

        decision = evaluate_scene_location_sync_decision(
            response_json=response_json,
            user_utterance="Hail Maelo!",
            current_location_id="RO01",
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])


class TestSceneLocationSyncSourceContract(unittest.TestCase):
    """Source-contract checks for validator wiring."""

    def test_main_injects_scene_location_sync_actions(self):
        main_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_py, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("evaluate_narrated_location_arrival_decision", content)
        self.assertIn("evaluate_scene_location_sync_decision", content)
        self.assertIn("STATE_SYNC: Narrated location arrival injected", content)
        self.assertIn("STATE_SYNC: Scene location sync injected", content)


if __name__ == "__main__":
    unittest.main()
