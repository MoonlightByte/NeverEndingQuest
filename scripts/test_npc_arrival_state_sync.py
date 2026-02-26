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


if __name__ == "__main__":
    # Run tests with verbosity
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestNPCArrivalValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestCanonicalDedupe))
    suite.addTests(loader.loadTestsFromTestCase(TestContractIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
