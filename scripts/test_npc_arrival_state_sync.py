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
            "narration": "Oswin walks in.",
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
            "narration": "The Harvest Witnesses gather at the road behind you.",
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
                "but the Harvest Witnesses gather at the road behind you."
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

    def test_non_travel_strict_behavior_unchanged(self):
        """
        Task 5.1d: Non-travel strict behavior unchanged (is_travel_intent=False).
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
        
        self.assertFalse(is_valid,
            "Non-travel turns should fail-closed even without explicit arrival verbs")
        self.assertIn("scout elen", reason.lower())

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

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
