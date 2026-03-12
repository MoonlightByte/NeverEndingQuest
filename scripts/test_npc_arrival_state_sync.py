# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - NPC Arrival State Sync Regression Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for deterministic NPC mention/action pairing validation and canonical dedupe logic.
"""

import unittest
import sys
import os
import re
import json


class TestNPCArrivalValidation(unittest.TestCase):
    """Test cases for NPC arrival state sync validation (tasks 4.2-4.4)."""

    def _extract_npc_name_from_action(self, action: dict) -> str:
        """Extract NPC name from action parameters."""
        if action.get("action") == "moveBackgroundNPC":
            return action.get("parameters", {}).get("npcName", "").lower()
        elif action.get("action") == "updatePartyNPCs":
            npc_data = action.get("parameters", {}).get("npc", {})
            return npc_data.get("name", "").lower()
        return ""

    def _find_mentioned_npcs(self, narration: str) -> list:
        """Find NPC names mentioned in narration (simple capitalized word detection)."""
        # Look for capitalized names (basic pattern)
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
        matches = re.findall(pattern, narration)
        return [name.lower() for name in matches]

    def _validate_npc_arrival(self, narration: str, actions: list, known_npcs: set, present_npcs: set) -> dict:
        """
        Simulate validation logic for NPC arrival state sync.
        Returns {"valid": bool, "reason": str}
        """
        mentioned = self._find_mentioned_npcs(narration)
        action_npcs = {self._extract_npc_name_from_action(a) for a in actions if a.get("action") in ["moveBackgroundNPC", "updatePartyNPCs"]}

        # Check for off-location NPC mentions without matching action
        for npc in mentioned:
            if npc in known_npcs and npc not in present_npcs:
                # This is an off-location known NPC mention
                if npc not in action_npcs:
                    return {
                        "valid": False,
                        "reason": f"Narration claims '{npc}' arrived/joined from off-location but missing required state action (moveBackgroundNPC or updatePartyNPCs add). Add matching action or remove arrival claim."
                    }

        return {"valid": True, "reason": "NPC arrival state sync validated."}

    def test_4_2_valid_non_present_npc_with_matching_action(self):
        """
        Valid case: non-present NPC mention + matching action passes.
        Task 4.2
        """
        narration = "Scout Elen emerges from the forest trail, having tracked you down."
        actions = [
            {
                "action": "moveBackgroundNPC",
                "parameters": {
                    "npcName": "Scout Elen",
                    "context": "Arrived from forest trail",
                    "currentLocation": "B01"
                }
            }
        ]
        known_npcs = {"scout elen", "ranger thane", "kira"}
        present_npcs = {"ranger thane"}  # Scout Elen is NOT present initially

        result = self._validate_npc_arrival(narration, actions, known_npcs, present_npcs)
        self.assertTrue(result["valid"], f"Expected valid but got: {result['reason']}")
        self.assertIn("sync validated", result["reason"])

    def test_4_3_invalid_non_present_npc_without_action(self):
        """
        Invalid case: non-present NPC mention without matching action fails.
        Task 4.3
        """
        narration = "Scout Elen emerges from the forest and greets you."
        actions = []  # No action!
        known_npcs = {"scout elen", "ranger thane", "kira"}
        present_npcs = {"ranger thane"}  # Scout Elen is NOT present

        result = self._validate_npc_arrival(narration, actions, known_npcs, present_npcs)
        self.assertFalse(result["valid"], "Expected invalid due to missing action")
        self.assertIn("scout elen", result["reason"].lower())
        self.assertIn("missing required state action", result["reason"].lower())

    def test_4_4_noop_already_present_npc(self):
        """
        No-op case: already-present NPC mention requires no additional action.
        Task 4.4
        """
        narration = "Ranger Thane nods to Elen, who is standing guard nearby."
        actions = []  # No action needed for already-present NPC
        known_npcs = {"scout elen", "ranger thane", "kira"}
        present_npcs = {"scout elen", "ranger thane"}  # Both are already present

        result = self._validate_npc_arrival(narration, actions, known_npcs, present_npcs)
        self.assertTrue(result["valid"], "Already-present NPC should not require action")
        self.assertIn("sync validated", result["reason"])

    def test_valid_party_join_with_action(self):
        """
        Valid case: NPC joins party with updatePartyNPCs action.
        """
        narration = "Kira shouldering her pack, 'I'll come with you.'"
        actions = [
            {
                "action": "updatePartyNPCs",
                "parameters": {
                    "operation": "add",
                    "npc": {"name": "Kira", "level": "3", "class": "Rogue"}
                }
            }
        ]
        known_npcs = {"scout elen", "kira"}
        present_npcs = {"scout elen"}  # Kira is NOT present initially

        result = self._validate_npc_arrival(narration, actions, known_npcs, present_npcs)
        self.assertTrue(result["valid"], f"Expected valid party join: {result['reason']}")

    def test_invalid_party_join_without_action(self):
        """
        Invalid case: NPC says they'll join but no updatePartyNPCs action.
        """
        narration = "'I can spare Scout Kira,' says the commander. 'She'll travel with you.' Kira steps forward."
        actions = []  # Missing updatePartyNPCs!
        known_npcs = {"scout kira"}
        present_npcs = set()  # Kira is NOT present initially

        result = self._validate_npc_arrival(narration, actions, known_npcs, present_npcs)
        self.assertFalse(result["valid"], "Should fail without updatePartyNPCs action")
        self.assertIn("scout kira", result["reason"].lower())


class TestCanonicalDedupe(unittest.TestCase):
    """Test cases for canonical equality dedupe (task 4.5)."""

    def _canonical_name_for_dedupe(self, name: str) -> str:
        """Normalize name to canonical form for equality comparison."""
        return name.lower().strip().replace("'", "").replace(" ", "_")

    def _should_show_npc(self, npc_name: str, party_members: list) -> bool:
        """
        Deterministic dedupe check using canonical equality.
        Returns True if NPC should be shown (not a duplicate).
        """
        canonical_party = {self._canonical_name_for_dedupe(m['name']) for m in party_members}
        return self._canonical_name_for_dedupe(npc_name) not in canonical_party

    def test_4_5_ansel_vs_anselara_distinct(self):
        """
        Dedupe case: 'Ansel' and 'Anselara' remain distinct under equality matching.
        Task 4.5
        """
        party = [{"name": "Anselara"}, {"name": "Kira"}]

        # Ansel (shorter name) should NOT be suppressed by Anselara (different canonical form)
        should_show = self._should_show_npc("Ansel", party)
        self.assertTrue(should_show, "'Ansel' should be distinct from 'Anselara' - BUG: substring matching would suppress this")

        # Anselara (exact match) should be suppressed
        should_show_anselara = self._should_show_npc("Anselara", party)
        self.assertFalse(should_show_anselara, "True duplicate 'Anselara' should be suppressed")

    def test_old_substring_behavior_would_fail(self):
        """
        Demonstrate that old substring logic incorrectly suppresses distinct names.
        """
        party = [{"name": "Anselara"}]

        # Old substring logic: "ansel" in "anselara" -> True (suppresses, WRONG)
        old_logic = "ansel" in "anselara"
        self.assertTrue(old_logic, "Old substring logic incorrectly finds match")

        # New canonical logic: "ansel" != "anselara" -> True (allows, CORRECT)
        should_show = self._should_show_npc("Ansel", party)
        self.assertTrue(should_show, "New canonical logic correctly keeps distinct")

    def test_case_insensitive_matching(self):
        """
        Canonical matching should be case-insensitive.
        """
        party = [{"name": "Mac'Davier"}]

        # Should match regardless of case and punctuation
        should_show = self._should_show_npc("macdavier", party)
        self.assertFalse(should_show, "Case-insensitive match should suppress")

        # Different name should not match
        should_show_other = self._should_show_npc("mac_davier_different", party)
        self.assertTrue(should_show_other, "Different name should not match")

    def test_space_and_apostrophe_normalization(self):
        """
        Spaces and apostrophes should be normalized to underscores.
        """
        party = [{"name": "Ranger Thane"}]

        # "Ranger Thane" -> "ranger_thane"
        self.assertFalse(self._should_show_npc("Ranger Thane", party), "Exact match with space")
        self.assertFalse(self._should_show_npc("ranger_thane", party), "Pre-normalized form")
        self.assertTrue(self._should_show_npc("Rangerthane", party), "Different name without space")

        # Apostrophe handling
        party2 = [{"name": "Mac'Davier"}]
        self.assertFalse(self._should_show_npc("Mac'Davier", party2), "With apostrophe")
        self.assertFalse(self._should_show_npc("macdavier", party2), "Without apostrophe (canonical)")


class TestAliasResolution(unittest.TestCase):
    """Test cases for NPC arrival alias resolution (Prompt 3 tasks 2.1-2.4)."""

    def test_short_mention_with_full_arrival_action_is_valid(self):
        """
        Task 2.1: Short narration mention + full arrival action => valid.
        Scenario: Narration says 'oswin', action uses 'Oswin Peverell'.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "Oswin approaches from the north.",
            "actions": [{"action": "moveBackgroundNPC", "parameters": {"npcName": "Oswin Peverell"}}]
        }
        party_tracker_data = {"partyMembers": ["Zeug"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"Oswin Peverell", "Amanita Gorse", "Edda Ravenscroft"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertTrue(is_valid, f"Short mention + full action should be valid, got: {reason}")

    def test_short_mention_with_full_present_state_is_valid(self):
        """
        Task 2.2: Short narration mention + full present-state identity => valid/no arrival required.
        Scenario: 'amanita' mentioned, 'Amanita Gorse' already present in partyNPCs.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "Amanita readies her bow.",
            "actions": []
        }
        party_tracker_data = {
            "partyMembers": ["Zeug"],
            "partyNPCs": [{"name": "Amanita Gorse"}]
        }
        location_data = {"npcs": []}
        module_npc_names = {"Oswin Peverell", "Amanita Gorse", "Edda Ravenscroft"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertTrue(is_valid, f"Short mention with full present state should be valid, got: {reason}")

    def test_ambiguous_short_alias_fails_open(self):
        """
        Task 2.3: Ambiguous short alias with multiple full-name candidates => fail-open.
        Scenario: 'Will' mentioned, module has 'Will Blackwood' and 'Will Turner'.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "Will enters the tavern.",
            "actions": []
        }
        party_tracker_data = {"partyMembers": ["Zeug"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"Will Blackwood", "Will Turner", "Amanita Gorse"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertTrue(is_valid, f"Ambiguous alias should fail-open (valid), got: {reason}")

    def test_unambiguous_off_location_without_action_fails_closed(self):
        """
        Task 2.4: Unambiguous off-location mention without matching arrival action => invalid.
        Scenario: 'edda' mentioned, 'Edda Ravenscroft' is unambiguous, not present, no action.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "Edda Ravenscroft appears at the door.",
            "actions": []
        }
        party_tracker_data = {"partyMembers": ["Zeug"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"Oswin Peverell", "Amanita Gorse", "Edda Ravenscroft"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertFalse(is_valid, "Unambiguous off-location without action should fail-closed")
        self.assertIn("edda ravenscroft", reason.lower())

    def test_unambiguous_short_without_action_enforced(self):
        """
        Negative control: Short mention with uniquely resolvable alias and no action is enforced.
        Ensures validator does not silently bypass enforcement for unambiguous cases.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "Oswin enters the room.",
            "actions": []
        }
        party_tracker_data = {"partyMembers": ["Zeug"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"Oswin Peverell"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertFalse(is_valid, "Unambiguous short mention without action should be enforced")
        self.assertIn("oswin", reason.lower())

    def test_descriptor_alias_prisoner_to_captured_matches_unique_identity(self):
        """
        Descriptor alias normalization should allow prisoner/captured identity match.
        Scenario: narration/action use "Bandit Prisoner" while canonical NPC is "Captured Bandit".
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "The bandit prisoner enters under guard.",
            "actions": [
                {
                    "action": "moveBackgroundNPC",
                    "parameters": {"npcName": "Bandit Prisoner", "currentLocation": "RO01"}
                }
            ]
        }
        party_tracker_data = {"partyMembers": ["Zeug"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"Captured Bandit", "Ranger Marcus"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertTrue(is_valid, f"Expected alias-aware match to pass, got: {reason}")


class TestNegatedNpcMentions(unittest.TestCase):
    """Regression tests for negated NPC mention handling."""

    def test_negated_absence_mention_is_not_treated_as_arrival(self):
        """Negated mention should not require arrival action."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "There are no Harvest Witnesses here, only battered shrines and wind.",
            "actions": []
        }
        party_tracker_data = {"partyMembers": ["Zeug"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"The Harvest Witnesses", "Oswin Peverell"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertTrue(is_valid, f"Negated absence mention should pass, got: {reason}")

    def test_positive_mention_without_action_still_fails(self):
        """Positive arrival mention without action must still fail-closed."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "The Harvest Witnesses appear at the road behind you.",
            "actions": []
        }
        party_tracker_data = {"partyMembers": ["Zeug"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"The Harvest Witnesses", "Oswin Peverell"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertFalse(is_valid, "Positive mention without action should fail")
        self.assertIn("harvest witnesses", reason.lower())

    def test_mixed_negated_and_positive_mentions_requires_action(self):
        """If any non-negated mention exists, arrival action is required."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": (
                "There are no Harvest Witnesses at the altar, "
                "but the Harvest Witnesses appear at the road behind you."
            ),
            "actions": []
        }
        party_tracker_data = {"partyMembers": ["Zeug"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"The Harvest Witnesses", "Oswin Peverell"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertFalse(is_valid, "Mixed mentions should fail due to positive mention")
        self.assertIn("harvest witnesses", reason.lower())

    def test_exact_retry_phrase_with_negated_harvest_witnesses_passes(self):
        """Regression for repeated retry-loop phrase in Pumpkin King travel narration."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": (
                "No spectral witnesses, no gathering of the Harvest Witnesses "
                "or other spirits are present here--just the echoes of the party's own triumph."
            ),
            "actions": []
        }
        party_tracker_data = {"partyMembers": ["Zeug", "Anselara"], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npc_names = {"The Harvest Witnesses", "Ghost of the Last Judge", "Oswin Peverell"}

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        self.assertTrue(is_valid, f"Negated Harvest Witnesses phrase should pass, got: {reason}")


class TestTravelIntentFailSoft(unittest.TestCase):
    """Task 5.1: Travel-intent fail-soft and explicit-arrival fail-closed tests."""

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

    def test_travel_intent_incidental_mention_valid(self):
        """
        Task 5.1a: Travel-intent + off-location mention + NO explicit-arrival + NO action => VALID.
        Incidental NPC mentions during travel should not require state action.
        """
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "As you travel north, you pass near the outpost where Elen is stationed.",
            "actions": []
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
            f"Travel fail-soft should allow incidental NPC references without explicit arrival, got: {reason}")
        self.assertEqual(reason, "")

    def test_travel_intent_explicit_arrival_fail_closed(self):
        """
        Task 5.1b: Travel-intent + explicit-arrival + NO action => INVALID (fail-closed).
        Even during travel, explicit arrival verbs require matching action.
        """
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "As you travel north, Scout Elen arrives from the outpost to join you.",
            "actions": []  # Missing moveBackgroundNPC
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
        self.assertIn("scout elen", reason.lower())

    def test_travel_intent_explicit_arrival_with_action_valid(self):
        """
        Task 5.1c: Travel-intent + explicit-arrival + matching action => VALID.
        """
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

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

    def test_non_travel_incidental_off_location_mention_valid(self):
        """
        Task 5.1d: Non-travel + off-location mention + NO explicit-arrival + NO action => VALID.
        Incidental mention should not require state action outside travel either.
        """
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

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
            f"Incidental off-location mention without explicit arrival should pass, got: {reason}")
        self.assertEqual(reason, "")

    def test_non_travel_explicit_arrival_still_fails_closed(self):
        """
        Non-travel + explicit arrival verb + no action => INVALID (fail-closed).
        """
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "Scout Elen arrives from the trail and steps into camp.",
            "actions": []
        }

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=False,
            user_utterance="look around"
        )

        self.assertFalse(is_valid, "Explicit arrival without action must fail closed")
        self.assertIn("scout elen", reason.lower())

    def test_failure_reason_includes_remove_arrival_claim_option(self):
        """
        Failure text should provide legal alternative path to avoid impossible retry loops.
        """
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

        response_json = {
            "narration": "Scout Elen arrives from the trail and greets you.",
            "actions": []
        }

        is_valid, reason = validate_npc_arrival_state_sync(
            response_json,
            self.party_tracker,
            location_data=self.location_data,
            module_npc_names=self.module_npcs,
            is_travel_intent=False,
            user_utterance="look around"
        )

        self.assertFalse(is_valid)
        self.assertIn("remove explicit arrival", reason.lower())

    def test_complex_travel_narration_multiple_npcs(self):
        """
        Task 5.1 extended: Complex travel narration referencing multiple distant NPCs => VALID.
        """
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync

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


class TestContractIntegration(unittest.TestCase):
    """Integration tests combining validation and dedupe logic."""

    def test_complete_flow_arrival_with_dedupe(self):
        """
        Full flow: Off-location NPC arrives, passes validation, dedupe allows distinct similar names.
        """
        # Scenario: Party has Anselara, location has both Ansel and Anselara
        party_members = [{"name": "Anselara"}]
        location_npcs = ["Ansel", "Anselara", "Kira"]  # Ansel should show (distinct from Anselara)

        # Simulate dedupe
        def canonical(name):
            return name.lower().strip().replace("'", "").replace(" ", "_")

        canonical_party = {canonical(m['name']) for m in party_members}
        visible_npcs = [npc for npc in location_npcs if canonical(npc) not in canonical_party]

        # Ansel should be visible (distinct from Anselara)
        self.assertIn("Ansel", visible_npcs, "Ansel should be visible despite Anselara in party")
        # Anselara should NOT be visible (true duplicate)
        self.assertNotIn("Anselara", visible_npcs, "Anselara should be suppressed (in party)")
        # Kira should be visible
        self.assertIn("Kira", visible_npcs)


class TestNarratorPromptRefactorContracts(unittest.TestCase):
    """Contract tests for narrator prompt validation refactor (Step 2.1)."""
    
    def test_kira_onboarding_contract_short_and_full_name_alignment(self):
        """
        Short mention + canonical action name path should be accepted.
        
        Scenario: Narration uses short name 'Kira', action uses full name 'Scout Kira'.
        This should pass validation (alias resolution).
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync
        
        response_json = {
            "narration": "Kira steps forward with a warm smile.",
            "actions": [
                {
                    "action": "updatePartyNPCs",
                    "parameters": {"add": ["Scout Kira"]}
                }
            ]
        }
        party_tracker_data = {"partyMembers": ["Acheron", "Ansel"], "partyNPCs": []}
        location_data = {"npcs": ["Scout Kira"]}
        module_npc_names = {"Scout Kira", "Maelo"}
        
        is_valid, reason = validate_npc_arrival_state_sync(
            response_json, party_tracker_data, location_data, module_npc_names
        )
        
        self.assertTrue(is_valid, f"Short mention + full action name should be valid, got: {reason}")
    
    def test_validator_stateless_between_failed_and_clean_attempts(self):
        """
        Failed prior validation check should not force subsequent clean response failure.
        
        Scenario: First attempt mentions off-location NPC and fails.
        Second attempt is clean (no off-location mentions, valid actions).
        Second attempt should pass independently.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync
        
        party_tracker_data = {"partyMembers": ["Acheron"], "partyNPCs": []}
        location_data = {"npcs": ["Scout Kira"]}
        module_npc_names = {"Scout Kira", "Maelo"}
        
        # First attempt: mentions off-location Maelo without action (FAILS)
        failed_response = {
            "narration": "Scout Kira approaches. Meanwhile, Maelo waits at camp.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"add": ["Scout Kira"]}}
            ]
        }
        
        is_valid_fail, _ = validate_npc_arrival_state_sync(
            failed_response, party_tracker_data, location_data, module_npc_names
        )
        self.assertFalse(is_valid_fail, "First attempt should fail with off-location mention")
        
        # Second attempt: clean, only mentions present NPC with valid action (PASSES)
        clean_response = {
            "narration": "Scout Kira steps forward to join you.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"add": ["Scout Kira"]}}
            ]
        }
        
        is_valid_pass, reason_pass = validate_npc_arrival_state_sync(
            clean_response, party_tracker_data, location_data, module_npc_names
        )
        
        # Key assertion: clean attempt passes independently of prior failure
        self.assertTrue(is_valid_pass, f"Clean follow-up should pass, got: {reason_pass}")


class TestNPCNameNormalization(unittest.TestCase):
    """Regression tests for NPC name canonicalization in action payloads."""

    def test_short_name_canonicalized_to_full_name(self):
        """
        Short action name ('Kira') should be canonicalized to 'Scout Kira'.
        
        This is the core fix for the Kira onboarding loop.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response
        
        # Response with short name in action
        response = json.dumps({
            "narration": "Kira joins your party.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"operation": "add", "npc": {"name": "Kira", "level": "4", "class": "Scout"}}}
            ]
        })
        
        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [{"name": "Scout Kira", "role": "Scout"}]
        }
        
        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        
        self.assertIsNotNone(normalized, f"Should normalize successfully, got error: {message}")
        
        parsed = json.loads(normalized)
        npc_name = parsed["actions"][0]["parameters"]["npc"]["name"]
        self.assertEqual(npc_name, "Scout Kira", "Short name should be canonicalized")

    def test_ambiguous_short_name_fails_closed(self):
        """
        Ambiguous short name matching multiple NPCs should fail closed.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response
        
        # Response with ambiguous short name
        response = json.dumps({
            "narration": "A scout joins you.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"operation": "add", "npc": {"name": "Scout", "level": "4"}}}
            ]
        })
        
        # Two NPCs with "Scout" in their name
        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [
                {"name": "Scout Kira", "role": "Scout"},
                {"name": "Scout Mara", "role": "Scout"}
            ]
        }
        
        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        
        self.assertIsNone(normalized, "Ambiguous name should fail closed")
        self.assertIn("not in party tracker", message)

    def test_canonical_name_unchanged(self):
        """
        Canonical names should remain unchanged (no-op normalization).
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response
        
        # Response with canonical name
        response = json.dumps({
            "narration": "Scout Kira joins your party.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"operation": "add", "npc": {"name": "Scout Kira", "level": "4", "class": "Scout"}}}
            ]
        })
        
        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [{"name": "Scout Kira", "role": "Scout"}]
        }
        
        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        
        self.assertIsNotNone(normalized, "Canonical name should pass")
        
        parsed = json.loads(normalized)
        npc_name = parsed["actions"][0]["parameters"]["npc"]["name"]
        self.assertEqual(npc_name, "Scout Kira", "Canonical name should be unchanged")

    def test_moveBackgroundNPC_short_name_canonicalized(self):
        """
        Short name in moveBackgroundNPC action should also be canonicalized.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response
        
        # Response with short name in moveBackgroundNPC
        response = json.dumps({
            "narration": "Kira moves to the tower.",
            "actions": [
                {"action": "moveBackgroundNPC", "parameters": {"npcName": "Kira", "context": "Moving to tower", "currentLocation": "T01"}}
            ]
        })
        
        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [{"name": "Scout Kira", "role": "Scout"}]
        }
        
        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        
        self.assertIsNotNone(normalized, f"Should normalize successfully, got error: {message}")
        
        parsed = json.loads(normalized)
        npc_name = parsed["actions"][0]["parameters"]["npcName"]
        self.assertEqual(npc_name, "Scout Kira", "Short name in moveBackgroundNPC should be canonicalized")

    def test_moveBackgroundNPC_module_npc_not_rejected_by_party_only_set(self):
        """
        moveBackgroundNPC should resolve module-known NPC identity even when NPC is not in party tracker.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response

        response = json.dumps({
            "narration": "Merchant Kael arrives from the south road.",
            "actions": [
                {
                    "action": "moveBackgroundNPC",
                    "parameters": {
                        "npcName": "merchant kael",
                        "context": "Arrives from road",
                        "currentLocation": "RO01"
                    }
                }
            ]
        })

        party_tracker_data = {
            "module": "The_Thornwood_Watch",
            "partyMembers": ["Acheron"],
            "partyNPCs": [{"name": "Scout Kira", "role": "Scout"}]
        }

        normalized, message = normalize_character_names_in_response(response, party_tracker_data)

        self.assertIsNotNone(normalized, f"Module-known moveBackgroundNPC should be accepted, got: {message}")
        parsed = json.loads(normalized)
        npc_name = parsed["actions"][0]["parameters"]["npcName"]
        self.assertEqual(npc_name.lower(), "merchant kael")

    def test_string_npc_form_converted_to_dict(self):
        """
        Non-canonical string form for npc parameter should be converted to dict.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response
        
        # Response with npc as string (non-canonical)
        response = json.dumps({
            "narration": "Kira joins your party.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"operation": "add", "npc": "Kira"}}
            ]
        })
        
        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [{"name": "Scout Kira", "role": "Scout"}]
        }
        
        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        
        self.assertIsNotNone(normalized, f"Should normalize successfully, got error: {message}")
        
        parsed = json.loads(normalized)
        npc_param = parsed["actions"][0]["parameters"]["npc"]
        self.assertIsInstance(npc_param, dict, "String npc should be converted to dict")
        self.assertEqual(npc_param["name"], "Scout Kira", "Canonical name should be used")

    def test_add_string_short_name_canonicalized(self):
        """
        String in parameters.add should be canonicalized to full name.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response

        response = json.dumps({
            "narration": "Kira joins your party.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"add": "Kira"}}
            ]
        })

        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [{"name": "Scout Kira", "role": "Scout"}]
        }

        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        self.assertIsNotNone(normalized, f"Should normalize successfully, got error: {message}")

        parsed = json.loads(normalized)
        add_param = parsed["actions"][0]["parameters"]["add"]
        self.assertEqual(add_param, "Scout Kira", "Short name in add should be canonicalized")

    def test_add_list_short_names_canonicalized(self):
        """
        List of strings in parameters.add should be canonicalized.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response

        response = json.dumps({
            "narration": "Kira and Maelo join your party.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"add": ["Kira", "Maelo"]}}
            ]
        })

        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [
                {"name": "Scout Kira", "role": "Scout"},
                {"name": "Maelo the Wise", "role": "Companion"}
            ]
        }

        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        self.assertIsNotNone(normalized, f"Should normalize successfully, got error: {message}")

        parsed = json.loads(normalized)
        add_list = parsed["actions"][0]["parameters"]["add"]
        self.assertEqual(add_list, ["Scout Kira", "Maelo the Wise"], "List items should be canonicalized")

    def test_add_list_ambiguous_fails_closed(self):
        """
        Ambiguous short name in add list should fail closed.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response

        response = json.dumps({
            "narration": "Scout joins your party.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"add": ["Scout"]}}
            ]
        })

        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [
                {"name": "Scout Kira", "role": "Scout"},
                {"name": "Scout Mara", "role": "Scout"}
            ]
        }

        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        self.assertIsNone(normalized, "Ambiguous add list name should fail closed")
        self.assertIn("not in party tracker", message)

    def test_add_list_canonical_names_noop(self):
        """
        Canonical names in parameters.add should remain unchanged.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response

        response = json.dumps({
            "narration": "Scout Kira and Maelo the Wise join your party.",
            "actions": [
                {"action": "updatePartyNPCs", "parameters": {"add": ["Scout Kira", "Maelo the Wise"]}}
            ]
        })

        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [
                {"name": "Scout Kira", "role": "Scout"},
                {"name": "Maelo the Wise", "role": "Companion"}
            ]
        }

        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        self.assertIsNotNone(normalized, f"Canonical add list should pass, got error: {message}")

        parsed = json.loads(normalized)
        add_list = parsed["actions"][0]["parameters"]["add"]
        self.assertEqual(add_list, ["Scout Kira", "Maelo the Wise"], "Canonical add list should be unchanged")

    def test_add_list_dict_names_canonicalized(self):
        """
        List of dict entries in parameters.add should canonicalize each name key.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import normalize_character_names_in_response

        response = json.dumps({
            "narration": "Kira and Maelo join your party.",
            "actions": [
                {
                    "action": "updatePartyNPCs",
                    "parameters": {
                        "add": [
                            {"name": "Kira", "role": "Scout"},
                            {"name": "Maelo", "role": "Companion"}
                        ]
                    }
                }
            ]
        })

        party_tracker_data = {
            "partyMembers": ["Acheron"],
            "partyNPCs": [
                {"name": "Scout Kira", "role": "Scout"},
                {"name": "Maelo the Wise", "role": "Companion"}
            ]
        }

        normalized, message = normalize_character_names_in_response(response, party_tracker_data)
        self.assertIsNotNone(normalized, f"Dict add list should normalize, got error: {message}")

        parsed = json.loads(normalized)
        add_list = parsed["actions"][0]["parameters"]["add"]
        self.assertEqual(add_list[0]["name"], "Scout Kira")
        self.assertEqual(add_list[1]["name"], "Maelo the Wise")

    def test_prompt_example_uses_canonical_name(self):
        """
        Source-contract test: compressed system prompt must use canonical Scout Kira.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompt_path = os.path.join(repo_root, "prompts", "system_prompt_compressed.txt")

        with open(prompt_path, "r", encoding="utf-8") as handle:
            prompt_content = handle.read()

        # Guard against reintroducing contradictory short-name example.
        self.assertNotIn('"name":"Kira"', prompt_content)
        self.assertIn('"name":"Scout Kira"', prompt_content)


if __name__ == "__main__":
    # Run tests with verbosity
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestNPCArrivalValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestCanonicalDedupe))
    suite.addTests(loader.loadTestsFromTestCase(TestAliasResolution))
    suite.addTests(loader.loadTestsFromTestCase(TestNegatedNpcMentions))
    suite.addTests(loader.loadTestsFromTestCase(TestTravelIntentFailSoft))
    suite.addTests(loader.loadTestsFromTestCase(TestContractIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestNarratorPromptRefactorContracts))
    suite.addTests(loader.loadTestsFromTestCase(TestNPCNameNormalization))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
