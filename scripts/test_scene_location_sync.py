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
    evaluate_implicit_sublocation_descent_decision,
    evaluate_narrated_location_arrival_decision,
    prioritize_pre_encounter_location_actions,
    evaluate_scene_plot_location_reconciliation_decision,
    evaluate_scene_location_sync_decision,
    evaluate_startup_scene_location_recovery_decision,
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

    def test_room_prefix_stripped_alias_commits_priest_lodging(self):
        response_json = {
            "narration": "You push open the warped door and step into the priest's lodging.",
            "actions": [],
        }

        module_locations = [
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

        decision = evaluate_narrated_location_arrival_decision(
            response_json=response_json,
            current_location_id="NIG01",
            current_area_id="NIG001",
            known_location_names=["Room 1: Ma's Watering Hole", "Room 4: Priest's Lodging"],
            module_locations=module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "narrated_location_arrival_sync")
        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred_actions), 2)
        self.assertEqual(inferred_actions[1].get("action"), "updatePartyTracker")
        self.assertEqual(inferred_actions[1].get("parameters", {}).get("currentLocationId"), "NIG04")

    def test_ambiguous_alias_fails_open_without_commit(self):
        response_json = {
            "narration": "You arrive at the shrine and hold your breath.",
            "actions": [],
        }

        module_locations = [
            {
                "id": "A01",
                "name": "Room 1: Shrine",
                "area_id": "A001",
                "area_name": "Area A",
                "source_room_title": "Shrine",
            },
            {
                "id": "B02",
                "name": "Room 2: Shrine",
                "area_id": "B001",
                "area_name": "Area B",
                "source_room_title": "Shrine",
            },
        ]

        decision = evaluate_narrated_location_arrival_decision(
            response_json=response_json,
            current_location_id="A01",
            current_area_id="A001",
            known_location_names=["Room 1: Shrine", "Room 2: Shrine"],
            module_locations=module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "none")
        self.assertEqual(decision.get("inferred_actions"), [])


class TestImplicitSublocationDescentDecision(unittest.TestCase):
    """Behavior tests for narrow implicit sublocation descent sync."""

    def setUp(self):
        self.module_locations = [
            {
                "id": "NIG01",
                "name": "Ma's Watering Hole",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
                "connectivity": ["NIG02", "NIG04", "NIG08"],
            },
            {
                "id": "NIG02",
                "name": "Ruined Cathedral Main Hall",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
                "source_room_title": "Ruined Cathedral Main Hall",
                "connectivity": ["NIG08", "NIG01", "NIG03"],
                "transition_hints": [
                    {
                        "destinationId": "NIG03",
                        "match_any": [
                            "crevice behind the altar",
                            "altar crevice",
                            "base of a wide fissure",
                            "base of a shadowy fissure",
                            "catacombs below",
                            "beneath the ruined cathedral",
                        ],
                    }
                ],
            },
            {
                "id": "NIG03",
                "name": "Cathedral Storage",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
                "source_room_title": "Cathedral Storage",
                "connectivity": ["NIG02", "NIG04"],
            },
            {
                "id": "NIG08",
                "name": "Brother Lintar's Place",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
                "connectivity": ["NIG01", "NIG02"],
            },
        ]

    def test_cathedral_crevice_descent_commits_storage_without_named_destination(self):
        response_json = {
            "narration": (
                "Deep beneath the ruined cathedral, the party stands at the base of a wide fissure, "
                "the air echoing with distant chanting from the catacombs below."
            ),
            "actions": [],
        }

        decision = evaluate_implicit_sublocation_descent_decision(
            response_json=response_json,
            current_location_id="NIG02",
            user_utterance="We climbed down the crevice behind the altar and ready our weapons.",
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "implicit_sublocation_descent_sync")
        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred_actions), 1)
        self.assertEqual(inferred_actions[0].get("action"), "updatePartyTracker")
        self.assertEqual(inferred_actions[0].get("parameters", {}).get("currentLocationId"), "NIG03")

    def test_ambiguous_lower_depth_prose_fails_open(self):
        response_json = {
            "narration": "The cold air from below brushes past the party as shadows gather in the dark.",
            "actions": [],
        }

        decision = evaluate_implicit_sublocation_descent_decision(
            response_json=response_json,
            current_location_id="NIG02",
            user_utterance="We listen carefully before going any deeper.",
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "none")
        self.assertEqual(decision.get("inferred_actions"), [])

    def test_explicit_transition_prevents_duplicate_descent_commit(self):
        response_json = {
            "narration": "The party drops down behind the altar into the catacombs.",
            "actions": [
                {
                    "action": "transitionLocation",
                    "parameters": {"newLocation": "NIG03"},
                }
            ],
        }

        decision = evaluate_implicit_sublocation_descent_decision(
            response_json=response_json,
            current_location_id="NIG02",
            user_utterance="Down the crevice we go.",
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])

    def test_dm_drift_question_does_not_force_descent_commit(self):
        response_json = {
            "narration": (
                "Requires DM correction: the world state is still upstairs even though the earlier scene "
                "was described below."
            ),
            "actions": [],
        }

        decision = evaluate_implicit_sublocation_descent_decision(
            response_json=response_json,
            current_location_id="NIG02",
            user_utterance=(
                "DM, why did the location manager bump us back into the cathedral above?"
            ),
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "none")
        self.assertEqual(decision.get("inferred_actions"), [])


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


class TestScenePlotLocationReconciliationDecision(unittest.TestCase):
    def setUp(self):
        self.module_locations = [
            {
                "id": "NIG04",
                "name": "Room 4: Priest's Lodging",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
            },
            {
                "id": "NIG05",
                "name": "Room 5: Cellar Hallway",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
            },
            {
                "id": "NIG06",
                "name": "Room 6: Dead End Ritual Chamber",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
            },
        ]
        self.plot_data = {
            "plotPoints": [
                {"id": "PP004", "location": "NIG04"},
                {"id": "PP005", "location": "NIG05"},
                {"id": "PP006", "location": "NIG06"},
            ]
        }

    def test_plot_update_repairs_stale_location(self):
        response_json = {
            "narration": "The party presses through the cellar threshold.",
            "actions": [
                {
                    "action": "updatePlot",
                    "parameters": {
                        "plotPointId": "PP005",
                        "newStatus": "in progress",
                    },
                }
            ],
        }

        decision = evaluate_scene_plot_location_reconciliation_decision(
            response_json=response_json,
            current_location_id="NIG04",
            plot_data=self.plot_data,
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "scene_plot_location_sync")
        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred_actions), 1)
        self.assertEqual(inferred_actions[0].get("action"), "updatePartyTracker")
        self.assertEqual(inferred_actions[0].get("parameters", {}).get("currentLocationId"), "NIG05")

    def test_encounter_update_repairs_stale_location(self):
        response_json = {
            "narration": "The last cultist falls in the ritual chamber.",
            "actions": [
                {
                    "action": "updateEncounter",
                    "parameters": {
                        "encounterId": "NIG06-E1",
                    },
                }
            ],
        }

        decision = evaluate_scene_plot_location_reconciliation_decision(
            response_json=response_json,
            current_location_id="NIG04",
            plot_data=self.plot_data,
            module_locations=self.module_locations,
        )

        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred_actions), 1)
        self.assertEqual(inferred_actions[0].get("parameters", {}).get("currentLocationId"), "NIG06")

    def test_explicit_location_action_blocks_reconciliation(self):
        response_json = {
            "narration": "The party pushes deeper into the cellar hallway.",
            "actions": [
                {
                    "action": "transitionLocation",
                    "parameters": {"newLocation": "NIG05"},
                },
                {
                    "action": "updatePlot",
                    "parameters": {"plotPointId": "PP005", "newStatus": "in progress"},
                },
            ],
        }

        decision = evaluate_scene_plot_location_reconciliation_decision(
            response_json=response_json,
            current_location_id="NIG04",
            plot_data=self.plot_data,
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])

    def test_ambiguous_candidates_fail_open(self):
        response_json = {
            "narration": "The scene spans the hallway and chamber.",
            "actions": [
                {
                    "action": "updatePlot",
                    "parameters": {"plotPointId": "PP005", "newStatus": "in progress"},
                },
                {
                    "action": "updateEncounter",
                    "parameters": {"encounterId": "NIG06-E1"},
                },
            ],
        }

        decision = evaluate_scene_plot_location_reconciliation_decision(
            response_json=response_json,
            current_location_id="NIG04",
            plot_data=self.plot_data,
            module_locations=self.module_locations,
        )

        self.assertEqual(decision.get("inferred_actions"), [])


class TestStartupSceneLocationRecoveryDecision(unittest.TestCase):
    """Behavior tests for restart-oriented location recovery after corrected commit."""

    def test_transition_history_recovers_cathedral_storage_on_startup(self):
        conversation_history = [
            {
                "role": "user",
                "content": "Location transition: Ruined Cathedral Main Hall (NIG02) to Cathedral Storage (NIG03)",
            },
            {
                "role": "assistant",
                "content": "The party descends into the catacombs and regroups in Cathedral Storage.",
            },
        ]
        module_locations = [
            {
                "id": "NIG02",
                "name": "Ruined Cathedral Main Hall",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
            },
            {
                "id": "NIG03",
                "name": "Cathedral Storage",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
            },
        ]

        decision = evaluate_startup_scene_location_recovery_decision(
            conversation_history=conversation_history,
            current_location_id="NIG02",
            current_area_id="NIG001",
            known_location_names=["Ruined Cathedral Main Hall", "Cathedral Storage"],
            module_locations=module_locations,
        )

        self.assertEqual(decision.get("reconciliation"), "startup_transition_replay")
        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(len(inferred_actions), 1)
        self.assertEqual(inferred_actions[0].get("parameters", {}).get("currentLocationId"), "NIG03")


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
        self.assertIn("evaluate_implicit_sublocation_descent_decision", content)
        self.assertIn("prioritize_pre_encounter_location_actions", content)
        self.assertIn("evaluate_scene_plot_location_reconciliation_decision", content)
        self.assertIn("evaluate_scene_location_sync_decision", content)
        self.assertIn("STATE_SYNC: Implicit sublocation descent injected", content)
        self.assertIn("STATE_SYNC: Narrated location arrival injected", content)
        self.assertIn("STATE_SYNC: Scene/plot location sync injected", content)
        self.assertIn("STATE_SYNC: Scene location sync injected", content)


class TestPreEncounterLocationPrioritization(unittest.TestCase):
    """Behavior tests for ordering location anchors before encounter creation."""

    def setUp(self):
        self.module_locations = [
            {
                "id": "NIG02",
                "name": "Ruined Cathedral Main Hall",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
                "connectivity": ["NIG08", "NIG01", "NIG03"],
                "transition_hints": [
                    {
                        "destinationId": "NIG03",
                        "match_any": ["crevice behind the altar", "catacombs below"],
                    }
                ],
            },
            {
                "id": "NIG03",
                "name": "Cathedral Storage",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
                "connectivity": ["NIG02", "NIG04"],
            },
            {
                "id": "NIG08",
                "name": "Brother Lintar's Place",
                "area_id": "NIG001",
                "area_name": "Night of the Restless Dead",
                "connectivity": ["NIG01", "NIG02"],
            },
        ]

    def test_inferred_location_commit_moves_ahead_of_create_encounter(self):
        actions = [
            {
                "action": "createEncounter",
                "parameters": {"encounterSummary": "Cultists surge from the dark."},
            },
            {
                "action": "updatePartyTracker",
                "parameters": {
                    "currentLocationId": "NIG03",
                    "currentLocation": "Cathedral Storage",
                },
            },
        ]

        prioritized = prioritize_pre_encounter_location_actions(actions)

        self.assertEqual(prioritized[0].get("action"), "updatePartyTracker")
        self.assertEqual(prioritized[1].get("action"), "createEncounter")

    def test_unrelated_actions_keep_order_when_no_location_anchor_exists(self):
        actions = [
            {"action": "updateTime", "parameters": {"timeEstimate": 5}},
            {"action": "createEncounter", "parameters": {"encounterSummary": "Battle"}},
        ]

        prioritized = prioritize_pre_encounter_location_actions(actions)
        self.assertEqual(prioritized, actions)

    def test_descent_inference_and_prioritization_anchor_same_turn_encounter(self):
        response_json = {
            "narration": (
                "Deep beneath the ruined cathedral, the party gathers at the altar crevice and prepares for the fight below."
            ),
            "actions": [
                {
                    "action": "createEncounter",
                    "parameters": {"encounterSummary": "Three cultists and an undead spider descend on the party."},
                }
            ],
        }

        implicit_decision = evaluate_implicit_sublocation_descent_decision(
            response_json=response_json,
            current_location_id="NIG02",
            user_utterance="We climb down the crevice behind the altar and get ready to fight.",
            module_locations=self.module_locations,
        )

        combined_actions = implicit_decision.get("inferred_actions", []) + response_json["actions"]
        prioritized = prioritize_pre_encounter_location_actions(combined_actions)

        self.assertEqual(prioritized[0].get("action"), "updatePartyTracker")
        self.assertEqual(prioritized[0].get("parameters", {}).get("currentLocationId"), "NIG03")
        self.assertEqual(prioritized[1].get("action"), "createEncounter")


if __name__ == "__main__":
    unittest.main()
