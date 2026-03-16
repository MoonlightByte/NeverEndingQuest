#!/usr/bin/env python3
"""
Test for Prompt 2 (Tasks 2.1-2.4): Travel fail-soft and explicit-arrival semantics.

Verifies that:
1. Travel-intent + off-location NPC mention + NO explicit-arrival semantics + NO action => VALID (fail-soft)
2. Travel-intent + explicit-arrival semantics + NO action => INVALID (fail-closed)
3. Travel-intent + explicit-arrival semantics + matching action => VALID
4. Non-travel incidental off-location mention remains VALID when no explicit arrival semantics are present
5. All existing exemptions preserved (party member, alias resolution, negated mentions)
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.npc_arrival_validator import (
    validate_npc_arrival_state_sync,
    _has_explicit_arrival_semantics,
    _EXPLICIT_ARRIVAL_VERBS
)


class TestExplicitArrivalSemanticsDetection(unittest.TestCase):
    """Test explicit arrival verb detection."""

    def test_arrive_verb_detected(self):
        """Test 'arrives' verb detected."""
        narration = "Scout Elen arrives from the north."
        mentions = {"scout elen"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_enter_verb_detected(self):
        """Test 'enters' verb detected."""
        narration = "The mysterious stranger enters the tavern."
        mentions = {"mysterious stranger"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_join_verb_detected(self):
        """Test 'joins' verb detected."""
        narration = "Kira joins the party at the campfire."
        mentions = {"kira"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_emerge_verb_detected(self):
        """Test 'emerges' verb detected."""
        narration = "A figure emerges from the shadows."
        mentions = {"figure"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_appear_verb_detected(self):
        """Test 'appears' verb detected."""
        narration = "Oswin Peverell suddenly appears before you."
        mentions = {"oswin peverell"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_approach_verb_detected(self):
        """Test 'approaches' verb detected."""
        narration = "The guard approaches from the gatehouse."
        mentions = {"guard"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_come_verb_detected(self):
        """Test 'comes' verb detected."""
        narration = "Help comes from an unexpected quarter."
        mentions = {"help"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_step_verb_detected(self):
        """Test 'steps' verb detected."""
        narration = "The innkeeper steps out to greet you."
        mentions = {"innkeeper"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_arrive_from_phrase_detected(self):
        """Test 'arrives from' phrase detected."""
        narration = "A messenger arrives from the capital."
        mentions = {"messenger"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_step_out_phrase_detected(self):
        """Test 'steps out' phrase detected."""
        narration = "The wizard steps out of his tower."
        mentions = {"wizard"}
        self.assertTrue(_has_explicit_arrival_semantics(narration, mentions))

    def test_no_explicit_arrival_mentions_nearby(self):
        """Test no arrival when NPC mentioned without arrival verbs."""
        narration = "You recall that Elen is stationed at the outpost."
        mentions = {"elen"}
        self.assertFalse(_has_explicit_arrival_semantics(narration, mentions))

    def test_no_explicit_arrival_generic_reference(self):
        """Test no arrival when NPC referenced but not arriving."""
        narration = "The captain mentioned Kira in his report."
        mentions = {"kira"}
        self.assertFalse(_has_explicit_arrival_semantics(narration, mentions))

    def test_no_explicit_arrival_thinking_about(self):
        """Test no arrival when NPC thought about."""
        narration = "You wonder what Oswin would do in this situation."
        mentions = {"oswin"}
        self.assertFalse(_has_explicit_arrival_semantics(narration, mentions))


class TestTravelFailSoftBehavior(unittest.TestCase):
    """Test travel fail-soft behavior (Task 2.3)."""

    def setUp(self):
        """Set up test fixtures."""
        self.party_tracker = {
            "partyMembers": ["Zeug"],
            "partyNPCs": [],
            "worldConditions": {
                "currentLocationId": "LOC001",
                "currentLocation": "Test Location",
                "currentAreaId": "AREA01"
            }
        }
        self.location_data = {"npcs": []}
        self.module_npcs = {"Scout Elen", "Oswin Peverell", "Kira"}

    def test_travel_fail_soft_no_explicit_arrival_no_action(self):
        """
        Test 1: Travel-intent + off-location NPC mention + NO explicit-arrival + NO action => VALID.
        
        This is the core fail-soft case - during travel, referencing distant NPCs
        without explicit arrival verbs should not block.
        """
        response_json = {
            "narration": "As you travel north, you pass near the outpost where Elen is stationed.",
            "actions": []
        }
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=True,  # Travel turn
            user_utterance="go north"
        )
        
        self.assertTrue(is_valid,
            f"Travel fail-soft should allow incidental NPC references without explicit arrival, got: {reason}")
        self.assertEqual(reason, "",
            "Fail-soft should return empty reason string")

    def test_travel_fail_closed_explicit_arrival_no_action(self):
        """
        Test 2: Travel-intent + explicit-arrival semantics + NO action => INVALID (fail-closed).
        
        Even during travel, explicit arrival verbs require matching action.
        """
        response_json = {
            "narration": "As you travel north, Scout Elen arrives from the outpost to join you.",
            "actions": []  # No moveBackgroundNPC or updatePartyNPCs
        }
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=True,
            user_utterance="go north"
        )
        
        self.assertFalse(is_valid,
            "Travel fail-soft should NOT apply when explicit arrival verbs present")
        self.assertIn("scout elen", reason.lower(),
            "Reason should mention the NPC")

    def test_travel_explicit_arrival_with_action_is_valid(self):
        """
        Test 3: Travel-intent + explicit-arrival semantics + matching action => VALID.
        """
        response_json = {
            "narration": "As you travel north, Scout Elen arrives from the outpost.",
            "actions": [
                {"action": "moveBackgroundNPC", "parameters": {"npcName": "Scout Elen"}}
            ]
        }
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=True,
            user_utterance="go north"
        )
        
        self.assertTrue(is_valid,
            f"Explicit arrival with matching action should be valid, got: {reason}")

    def test_non_travel_incidental_mention_no_action_is_valid(self):
        """
        Test 4: Non-travel turn + off-location NPC mention + NO action => VALID.
        
        Contract parity: incidental mention without explicit-arrival semantics
        remains valid in both travel and non-travel turns.
        """
        response_json = {
            "narration": "You notice that Elen is watching from the outpost.",
            "actions": []
        }
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=False,  # NOT a travel turn
            user_utterance="look around"
        )
        
        self.assertTrue(is_valid,
            f"Non-travel incidental mention without explicit-arrival should pass, got: {reason}")
        self.assertEqual(reason, "")

    def test_travel_with_party_npc_exempt(self):
        """
        Test 5: Travel turn + party NPC mention => VALID (party exemption preserved).
        
        Party members should be exempt even during travel fail-soft.
        """
        party_tracker_with_npc = {
            "partyMembers": ["Zeug"],
            "partyNPCs": [{"name": "Kira"}],
            "worldConditions": {
                "currentLocationId": "LOC001",
                "currentLocation": "Test Location",
                "currentAreaId": "AREA01"
            }
        }
        
        response_json = {
            "narration": "As you travel, Kira scouts ahead for danger.",
            "actions": []
        }
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            party_tracker_with_npc,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=True,
            user_utterance="go north"
        )
        
        self.assertTrue(is_valid,
            f"Party NPC should be exempt from arrival checks, got: {reason}")

    def test_travel_with_present_npc_exempt(self):
        """
        Test 6: Travel turn + present NPC mention => VALID (presence exemption preserved).
        """
        location_with_npc = {"npcs": [{"name": "Elen"}]}
        
        response_json = {
            "narration": "As you travel, Elen walks beside you.",
            "actions": []
        }
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=location_with_npc,
            module_npc_names=self.module_npcs,
            is_travel_intent=True,
            user_utterance="go north"
        )
        
        self.assertTrue(is_valid,
            f"Present NPC should be exempt from arrival checks, got: {reason}")

    def test_travel_fail_soft_mentioning_distant_npcs(self):
        """
        Test 7: Travel turn mentioning multiple distant NPCs without actions => VALID.
        
        Complex travel narration should be allowed to reference off-location NPCs.
        """
        response_json = {
            "narration": (
                "As you journey through the valley, you pass the crossroads where Elen patrols, "
                "the abandoned watchtower where Oswin once stood guard, and the grove where "
                "villagers say Kira trains recruits. The road ahead is clear."
            ),
            "actions": []
        }
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=True,
            user_utterance="travel to the valley"
        )
        
        self.assertTrue(is_valid,
            f"Complex travel narration with distant NPC refs should pass, got: {reason}")

    def test_explicit_arrival_in_middle_of_travel_narration(self):
        """
        Test 8: Travel narration with explicit arrival embedded still requires action.
        
        Fail-soft should NOT apply when explicit arrival verbs are present.
        """
        response_json = {
            "narration": (
                "You travel north through the valley. Along the way, Scout Elen "
                "emerges from the treeline and joins your march. The path continues "
                "toward the mountains."
            ),
            "actions": []  # Missing action for Elen
        }
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=True,
            user_utterance="go north"
        )
        
        self.assertFalse(is_valid,
            "Explicit arrival verb 'emerges' should trigger fail-closed")
        self.assertIn("scout elen", reason.lower())


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility for no-travel-intent calls."""

    def test_no_travel_intent_defaults_to_incidental_mention_valid(self):
        """
        Test 9: Default behavior (no is_travel_intent parameter) remains
        explicit-arrival-only for incidental off-location mentions.
        """
        party_tracker = {
            "partyMembers": ["Zeug"],
            "partyNPCs": [],
            "worldConditions": {
                "currentLocationId": "LOC001",
                "currentLocation": "Test Location",
                "currentAreaId": "AREA01"
            }
        }
        location_data = {"npcs": []}
        module_npcs = {"Scout Elen"}
        
        response_json = {
            "narration": "You see Elen in the distance.",
            "actions": []
        }
        
        # Call without is_travel_intent (backward compatibility)
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            party_tracker,
            location_data=location_data,
            module_npc_names=module_npcs
        )
        
        self.assertTrue(is_valid,
            f"Default behavior should allow incidental mention without explicit-arrival, got: {reason}")
        self.assertEqual(reason, "")


if __name__ == '__main__':
    unittest.main()
