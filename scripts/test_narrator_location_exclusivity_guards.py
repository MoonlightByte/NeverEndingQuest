#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for narrator location exclusivity and exit grounding guards."""

import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.narrator_location_exclusivity_guard import (  # noqa: E402
    evaluate_authored_exit_grounding_decision,
    evaluate_location_exclusivity_decision,
)


class TestLocationExclusivityDecision(unittest.TestCase):
    """Behavior tests for metadata-first and fallback exclusivity guard."""

    def test_metadata_blocks_present_scene_anchor_without_transition(self):
        response_json = {
            "narration": "The Nexus Warden stands before you at the ritual altar.",
            "actions": [],
        }
        module_locations = [
            {"id": "A01", "name": "Outer Hall"},
            {
                "id": "B02",
                "name": "Nexus Chamber",
                "sceneAuthority": {
                    "presentSceneAnchors": [
                        {
                            "anchorId": "nexus_warden",
                            "aliases": ["Nexus Warden", "ritual altar"],
                            "foreshadowAllowed": True,
                        }
                    ]
                },
            },
        ]

        decision = evaluate_location_exclusivity_decision(
            response_json=response_json,
            module_name="Any_Module",
            current_location_id="A01",
            module_locations=module_locations,
        )

        self.assertFalse(decision.get("valid"))
        self.assertIn("Location exclusivity violation", decision.get("reason", ""))

    def test_metadata_allows_foreshadow_without_present_scene_instantiation(self):
        response_json = {
            "narration": "You sense the Nexus Warden deeper ahead, a distant ritual pulse in the stone.",
            "actions": [],
        }
        module_locations = [
            {"id": "A01", "name": "Outer Hall"},
            {
                "id": "B02",
                "name": "Nexus Chamber",
                "sceneAuthority": {
                    "presentSceneAnchors": [
                        {
                            "anchorId": "nexus_warden",
                            "aliases": ["Nexus Warden"],
                            "foreshadowAllowed": True,
                        }
                    ]
                },
            },
        ]

        decision = evaluate_location_exclusivity_decision(
            response_json=response_json,
            module_name="Any_Module",
            current_location_id="A01",
            module_locations=module_locations,
        )

        self.assertTrue(decision.get("valid"))

    def test_metadata_allows_present_scene_when_transition_committed(self):
        response_json = {
            "narration": "The Nexus Warden stands before you at the ritual altar.",
            "actions": [
                {
                    "action": "transitionLocation",
                    "parameters": {"newLocation": "B02"},
                }
            ],
        }
        module_locations = [
            {"id": "A01", "name": "Outer Hall"},
            {
                "id": "B02",
                "name": "Nexus Chamber",
                "sceneAuthority": {
                    "presentSceneAnchors": [
                        {
                            "anchorId": "nexus_warden",
                            "aliases": ["Nexus Warden", "ritual altar"],
                            "foreshadowAllowed": True,
                        }
                    ]
                },
            },
        ]

        decision = evaluate_location_exclusivity_decision(
            response_json=response_json,
            module_name="Any_Module",
            current_location_id="A01",
            module_locations=module_locations,
        )

        self.assertTrue(decision.get("valid"))

    def test_nc01_allows_foreshadowing(self):
        response_json = {
            "narration": "You sense Malarok deeper ahead, and a distant ritual pulse echoes through the cave.",
            "actions": [],
        }

        decision = evaluate_location_exclusivity_decision(
            response_json=response_json,
            module_name="The_Thornwood_Watch",
            current_location_id="NC01",
        )

        self.assertTrue(decision.get("valid"))

    def test_nc01_blocks_nc05_present_scene_anchor_without_transition(self):
        response_json = {
            "narration": "Malarok stands before you at the Voidstone altar, right here in this chamber.",
            "actions": [],
        }

        decision = evaluate_location_exclusivity_decision(
            response_json=response_json,
            module_name="The_Thornwood_Watch",
            current_location_id="NC01",
        )

        self.assertFalse(decision.get("valid"))
        self.assertIn("Location exclusivity violation", decision.get("reason", ""))

    def test_nc01_allows_present_scene_anchor_when_transition_committed(self):
        response_json = {
            "narration": "Malarok stands before you at the Voidstone altar.",
            "actions": [
                {
                    "action": "transitionLocation",
                    "parameters": {"newLocation": "NC05"},
                }
            ],
        }

        decision = evaluate_location_exclusivity_decision(
            response_json=response_json,
            module_name="The_Thornwood_Watch",
            current_location_id="NC01",
        )

        self.assertTrue(decision.get("valid"))


class TestAuthoredExitGroundingDecision(unittest.TestCase):
    """Behavior tests for authored-adjacent route-block grounding guard."""

    def setUp(self):
        self.current_location_data = {
            "locationId": "NC01",
            "connectivity": ["NC02", "NC03"],
        }

    def test_blocks_unsupported_route_claim_when_authored_adjacency_exists(self):
        response_json = {
            "narration": "The path to NC02 is blocked and impassable.",
            "actions": [],
        }

        decision = evaluate_authored_exit_grounding_decision(
            response_json=response_json,
            current_location_id="NC01",
            current_location_data=self.current_location_data,
        )

        self.assertFalse(decision.get("valid"))
        self.assertIn("Authored-exit grounding violation", decision.get("reason", ""))

    def test_allows_block_claim_with_authored_blocker_metadata(self):
        response_json = {
            "narration": "The path to NC02 is blocked by a cave-in.",
            "actions": [],
        }
        location_data = {
            "locationId": "NC01",
            "connectivity": ["NC02", "NC03"],
            "transition_hints": [
                {
                    "type": "blocked_exit",
                    "description": "North tunnel blocked by cave-in debris.",
                }
            ],
        }

        decision = evaluate_authored_exit_grounding_decision(
            response_json=response_json,
            current_location_id="NC01",
            current_location_data=location_data,
        )

        self.assertTrue(decision.get("valid"))

    def test_allows_block_claim_with_deterministic_action_support(self):
        response_json = {
            "narration": "The route ahead is blocked by hostile defenders.",
            "actions": [
                {
                    "action": "createEncounter",
                    "parameters": {
                        "encounterSummary": "Hostiles block the passage.",
                        "player": "Acheron",
                        "npcs": [],
                        "monsters": ["Bandit"],
                    },
                }
            ],
        }

        decision = evaluate_authored_exit_grounding_decision(
            response_json=response_json,
            current_location_id="NC01",
            current_location_data=self.current_location_data,
        )

        self.assertTrue(decision.get("valid"))

    def test_scene_authority_metadata_does_not_regress_exit_grounding(self):
        response_json = {
            "narration": "The path to NC02 is blocked and impassable.",
            "actions": [],
        }
        location_data = {
            "locationId": "NC01",
            "connectivity": ["NC02", "NC03"],
            "sceneAuthority": {
                "presentSceneAnchors": [
                    {
                        "anchorId": "dummy_anchor",
                        "aliases": ["Dummy Anchor"],
                    }
                ]
            },
        }

        decision = evaluate_authored_exit_grounding_decision(
            response_json=response_json,
            current_location_id="NC01",
            current_location_data=location_data,
        )

        self.assertFalse(decision.get("valid"))
        self.assertIn("Authored-exit grounding violation", decision.get("reason", ""))


class TestMainIntegrationSourceGuards(unittest.TestCase):
    """Source guards to keep main validation integration wired."""

    def test_main_calls_location_exclusivity_and_exit_grounding_guards(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_path = os.path.join(repo_root, "main.py")
        with open(main_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("evaluate_location_exclusivity_decision", source)
        self.assertIn("evaluate_authored_exit_grounding_decision", source)
        self.assertIn("module_locations=known_locations", source)
        self.assertIn("Narrator location exclusivity guard failed", source)
        self.assertIn("Narrator authored-exit grounding guard failed", source)


if __name__ == "__main__":
    unittest.main()
