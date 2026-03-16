#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Transcript-driven contract tests for G3 NPC scene-presence reconcile-first.

These tests are intentionally added before runtime implementation. At least one
test is expected to fail until G3 behavior is implemented.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.npc_arrival_validator import (
    evaluate_npc_arrival_state_sync_decision,
    resolve_npc_identity,
    validate_npc_arrival_state_sync,
)


class TestNpcScenePresenceReconcileFirstContracts(unittest.TestCase):
    """Pre-implementation G3 contract locks."""

    def setUp(self):
        self.party_tracker = {
            "partyMembers": ["Vitreol", "Blairen", "Chronos"],
            "partyNPCs": [{"name": "Scout Kira"}],
            "worldConditions": {
                "currentLocationId": "TW004",
                "currentLocation": "Hermit's Refuge Approach",
                "currentAreaId": "TW001",
            },
        }
        self.location_data = {"npcs": []}
        self.module_npcs = {
            "Spirit-Touched Hermit Maelo",
            "Scout Kira",
            "Scout Elen",
            "Scout Mara",
        }

    def test_transcript_maelo_scene_presence_should_reconcile_not_hard_fail(self):
        """Transcript lock from main_conversation_messages_to_api.json Maelo correction loop."""
        response_json = {
            "narration": (
                "A bent figure emerges from the refuge doorway. "
                "Spirit-Touched Hermit Maelo fixes Vitreol with a knowing stare and motions the party closer."
            ),
            "actions": [],
        }

        decision = evaluate_npc_arrival_state_sync_decision(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=False,
            user_utterance="call out to the hermit",
        )

        is_valid = bool(decision.get("valid", False))
        reason = str(decision.get("reason", "") or "")
        self.assertTrue(
            is_valid,
            "G3 target: clear Maelo scene presence should reconcile-first instead of hard-failing. "
            f"Current reason: {reason}",
        )
        inferred_actions = decision.get("inferred_actions", [])
        self.assertEqual(decision.get("reconciliation"), "scene_presence_autocommit")
        self.assertEqual(len(inferred_actions), 1)
        self.assertEqual(inferred_actions[0].get("action"), "moveBackgroundNPC")
        self.assertEqual(inferred_actions[0].get("parameters", {}).get("npcName"), "Spirit-Touched Hermit Maelo")

    def test_foreshadowing_reference_remains_action_free(self):
        response_json = {
            "narration": (
                "The reeds whisper with stories that Spirit-Touched Hermit Maelo still watches this marsh, "
                "though the refuge itself remains hidden beyond the fog."
            ),
            "actions": [],
        }

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=False,
            user_utterance="listen at the edge of the refuge",
        )

        self.assertTrue(is_valid, reason)
        self.assertEqual(reason, "")

    def test_explicit_party_join_still_requires_update_party_npcs(self):
        response_json = {
            "narration": "Spirit-Touched Hermit Maelo nods once and agrees to join the party on the road ahead.",
            "actions": [],
        }

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=False,
            user_utterance="ask Maelo to travel with us",
        )

        self.assertFalse(
            is_valid,
            "G3 should not turn explicit party-join narration into implicit party membership",
        )
        self.assertIn("maelo", reason.lower())

    def test_ambiguous_identity_remains_safe(self):
        result = resolve_npc_identity("Scout", {"Scout Kira", "Scout Mara"})
        self.assertEqual(result.status, "ambiguous")


class TestNpcScenePresenceSourceContracts(unittest.TestCase):
    """Source-contract checks for the new OpenSpec change scaffolding."""

    def test_change_directory_exists(self):
        change_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "openspec",
            "changes",
            "npc-scene-presence-reconcile-first",
        )
        self.assertTrue(os.path.isdir(change_dir))

    def test_change_spec_mentions_scene_presence(self):
        spec_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "openspec",
            "changes",
            "npc-scene-presence-reconcile-first",
            "specs",
            "tt-npc-scene-presence-reconcile-first",
            "spec.md",
        )
        with open(spec_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("scene-compatible NPC presence", content)
        self.assertIn("Spirit-Touched Hermit Maelo", content)

    def test_main_wires_npc_reconcile_first_inferred_actions(self):
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("evaluate_npc_arrival_state_sync_decision", content)
        self.assertIn("NPC reconcile-first injected", content)


if __name__ == "__main__":
    unittest.main()
