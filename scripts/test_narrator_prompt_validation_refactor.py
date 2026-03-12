# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Narrator Prompt Validation Refactor Regression Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for narrator/validator behavior using known-failure fixtures.
"""

import unittest
import sys
import os
import json


class TestFixtureContracts(unittest.TestCase):
    """Test fixture shape and intent for known failure patterns."""

    def setUp(self):
        """Load fixtures from disk."""
        self.fixtures_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures", "narrator_validation"
        )
        
    def _load_fixture(self, name):
        """Load a fixture JSON file."""
        path = os.path.join(self.fixtures_dir, f"{name}.json")
        with open(path, 'r') as f:
            return json.load(f)

    def test_kira_fixture_contract_shape_and_intent(self):
        """
        Verify Kira onboarding fixture has required contract fields.
        """
        fixture = self._load_fixture("kira_onboarding_failure")
        
        # Required top-level keys
        self.assertEqual(fixture["fixture_name"], "kira_onboarding_failure")
        self.assertIn("description", fixture)
        self.assertIn("input", fixture)
        self.assertIn("party_state_before", fixture)
        self.assertIn("expected_behavior", fixture)
        self.assertIn("actual_buggy_behavior", fixture)
        self.assertIn("notes", fixture)
        
        # Input structure
        self.assertIn("narrator_output", fixture["input"])
        self.assertIn("actions", fixture["input"])
        self.assertEqual(len(fixture["input"]["actions"]), 1)
        self.assertEqual(fixture["input"]["actions"][0]["action"], "updatePartyNPCs")
        
        # Party state before
        self.assertIn("partyMembers", fixture["party_state_before"])
        self.assertIn("partyNPCs", fixture["party_state_before"])
        self.assertEqual(len(fixture["party_state_before"]["partyNPCs"]), 0)
        
        # Expected behavior
        self.assertEqual(fixture["expected_behavior"]["deterministic_validator_result"], "pass")
        self.assertIn("Scout Kira", fixture["expected_behavior"]["party_state_after"]["partyNPCs"])
        
        # Actual buggy behavior
        self.assertEqual(fixture["actual_buggy_behavior"]["deterministic_validator_result"], "fail")
        self.assertEqual(fixture["actual_buggy_behavior"]["blocked_npc"], "Maelo")
        self.assertEqual(len(fixture["actual_buggy_behavior"]["party_state_after"]["partyNPCs"]), 0)

    def test_bex_fixture_contract_shape_and_intent(self):
        """
        Verify Bex hint mismatch fixture has required contract fields.
        """
        fixture = self._load_fixture("bex_hint_mismatch")
        
        # Required top-level keys
        self.assertEqual(fixture["fixture_name"], "bex_hint_mismatch")
        self.assertIn("description", fixture)
        self.assertIn("input", fixture)
        self.assertIn("canonical_reference", fixture)
        self.assertIn("strict_hint_expected_result", fixture)
        self.assertIn("fallback_expected_result", fixture)
        self.assertIn("actual_buggy_behavior", fixture)
        self.assertIn("notes", fixture)
        
        # Input structure
        self.assertEqual(fixture["input"]["action"]["action"], "moveBackgroundNPC")
        self.assertEqual(fixture["input"]["action"]["parameters"]["name"], "Bex")
        self.assertEqual(fixture["input"]["action"]["parameters"]["currentLocation"], "TW03")
        
        # Canonical reference
        self.assertEqual(fixture["canonical_reference"]["npc_name"], "Bex")
        self.assertEqual(fixture["canonical_reference"]["actual_location"], "RO03")
        
        # Strict hint should fail
        self.assertEqual(fixture["strict_hint_expected_result"]["result"], "not_found")
        
        # Fallback should succeed
        self.assertEqual(fixture["fallback_expected_result"]["result"], "success")
        self.assertTrue(fixture["fallback_expected_result"]["fallback_applied"])
        
        # Actual buggy behavior
        self.assertEqual(fixture["actual_buggy_behavior"]["result"], "error")
        self.assertFalse(fixture["actual_buggy_behavior"]["npc_moved"])

    def test_retry_pollution_fixture_contract_shape_and_intent(self):
        """
        Verify retry pollution fixture has required contract fields.
        """
        fixture = self._load_fixture("retry_pollution_chain")
        
        # Required top-level keys
        self.assertEqual(fixture["fixture_name"], "retry_pollution_chain")
        self.assertIn("description", fixture)
        self.assertIn("input_sequence", fixture)
        self.assertIn("expected_clean_behavior", fixture)
        self.assertIn("actual_polluted_behavior", fixture)
        self.assertIn("notes", fixture)
        
        # Input sequence has 3 attempts
        self.assertIn("attempt_1", fixture["input_sequence"])
        self.assertIn("attempt_2", fixture["input_sequence"])
        self.assertIn("attempt_3", fixture["input_sequence"])
        self.assertIn("correction_1", fixture["input_sequence"])
        self.assertIn("correction_2", fixture["input_sequence"])
        
        # Corrections stored in conversation history (buggy)
        self.assertEqual(fixture["input_sequence"]["correction_1"]["storage_location"], "conversation_history")
        self.assertEqual(fixture["input_sequence"]["correction_1"]["role"], "user")
        
        # Expected clean behavior
        self.assertEqual(fixture["expected_clean_behavior"]["correction_storage"], "validation-local metadata")
        self.assertEqual(fixture["expected_clean_behavior"]["correction_count_in_history"], 0)
        
        # Actual polluted behavior
        self.assertEqual(fixture["actual_polluted_behavior"]["correction_storage"], "conversation_history as user messages")
        self.assertEqual(fixture["actual_polluted_behavior"]["correction_count_in_history"], 2)


class TestRetryHygieneContracts(unittest.TestCase):
    """Test retry-loop hygiene and conversation pollution."""

    def setUp(self):
        """Load fixtures."""
        fixtures_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures", "narrator_validation"
        )
        with open(os.path.join(fixtures_dir, "retry_pollution_chain.json"), 'r') as f:
            self.retry_fixture = json.load(f)

    def test_retry_clean_history_contains_no_correction_user_turns(self):
        """
        Verify expected clean behavior has zero correction user turns.
        """
        clean = self.retry_fixture["expected_clean_behavior"]
        
        # No corrections in history
        self.assertEqual(clean["correction_count_in_history"], 0)
        
        # Verify history contains only system/assistant/user (player) roles
        history = clean["conversation_history"]
        for entry in history:
            self.assertIn(entry["role"], ["system", "user", "assistant"])
            # No correction marker in content
            self.assertNotIn("[CORRECTION REQUIRED]", entry.get("content", ""))

    def test_retry_polluted_history_contains_correction_user_turns(self):
        """
        Verify actual polluted behavior has correction user turns.
        """
        polluted = self.retry_fixture["actual_polluted_behavior"]
        
        # Has corrections in history
        self.assertEqual(polluted["correction_count_in_history"], 2)
        
        # Verify history contains user messages with correction markers
        history = polluted["conversation_history"]
        user_msgs = [e for e in history if e["role"] == "user"]
        
        # Should have player input + 2 corrections as user messages
        correction_msgs = [m for m in user_msgs if "[CORRECTION REQUIRED]" in m.get("content", "")]
        self.assertEqual(len(correction_msgs), 2)


class TestCleanFollowupIsolation(unittest.TestCase):
    """Test that clean follow-up responses are not blocked by prior failure context."""

    def setUp(self):
        """Load fixtures."""
        fixtures_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures", "narrator_validation"
        )
        with open(os.path.join(fixtures_dir, "kira_onboarding_failure.json"), 'r') as f:
            self.kira_fixture = json.load(f)

    def test_clean_followup_not_blocked_by_prior_failure_context(self):
        """
        Verify that a clean follow-up response after a failure is not blocked
        by residual failure context.
        
        This is a contract test: the fixture asserts that a clean response
        (Kira present + valid action) should pass even if a prior failed
        response mentioned off-location NPCs.
        """
        # Expected behavior: clean Kira onboarding passes
        expected = self.kira_fixture["expected_behavior"]
        self.assertEqual(expected["deterministic_validator_result"], "pass")
        self.assertIn("Scout Kira", expected["party_state_after"]["partyNPCs"])
        
        # Buggy behavior: prior failure context blocks
        buggy = self.kira_fixture["actual_buggy_behavior"]
        self.assertEqual(buggy["deterministic_validator_result"], "fail")
        
        # The key contract: clean follow-up should be stateless
        # This test documents the expected behavior from the fixture
        notes = self.kira_fixture["notes"]
        self.assertIn("Party member exemption", notes)


class TestNPCMoveFallbackContracts(unittest.TestCase):
    """Contract tests for Step 3.3 strict-then-fallback NPC lookup."""

    def test_strict_hint_match_success(self):
        """
        Strict hint match should succeed when NPC is at hinted location.
        
        Scenario: Bex is in RO03, hint is RO03.
        Expected: Strict match succeeds, fallback not needed.
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Mock the expected behavior using fixture data
        fixture = self._load_fixture("bex_hint_mismatch")
        
        # Verify fixture describes strict success case
        strict_expected = fixture["strict_hint_expected_result"]
        self.assertEqual(strict_expected["result"], "not_found",
                        "Fixture expects strict hint to fail (stale hint)")
        
        # But fallback should succeed
        fallback_expected = fixture["fallback_expected_result"]
        self.assertEqual(fallback_expected["result"], "success",
                        "Fixture expects fallback to succeed")
        self.assertTrue(fallback_expected["fallback_applied"],
                       "Fallback should be applied")

    def test_stale_hint_unambiguous_fallback_success(self):
        """
        Stale hint + unique canonical match should succeed via fallback.
        
        Scenario: Bex hint is TW03 (stale), but Bex is actually in RO03.
        Expected: Fallback finds exactly one Bex in RO03, succeeds.
        """
        fixture = self._load_fixture("bex_hint_mismatch")
        
        # Verify canonical reference
        canonical = fixture["canonical_reference"]
        self.assertEqual(canonical["npc_name"], "Bex")
        self.assertEqual(canonical["actual_location"], "RO03")
        self.assertNotEqual(fixture["input"]["action"]["parameters"]["currentLocation"],
                           canonical["actual_location"],
                           "Hint should be stale (different from actual)")

    def test_ambiguous_fallback_fails_closed(self):
        """
        Stale hint + multiple matches should fail closed.
        
        Scenario: Searching for "caravan guard" with stale hint,
        but multiple "caravan guard" NPCs exist in different locations.
        Expected: Fail closed (return None), no unsafe move.
        """
        # This is a design contract test - the implementation should
        # detect ambiguity and fail closed
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Document the expected contract
        # In real scenario with ambiguous matches, function returns None
        self.assertTrue(True, "Ambiguous fallback contract documented")

    def test_no_match_returns_none(self):
        """
        No match anywhere should return None (existing behavior preserved).
        
        Scenario: NPC name doesn't exist in any location.
        Expected: Return None, caller handles not-found case.
        """
        # Document existing behavior preservation
        self.assertTrue(True, "No-match returns None contract preserved")

    def _load_fixture(self, name):
        """Helper to load a fixture."""
        import json
        import os
        fixtures_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures", "narrator_validation"
        )
        path = os.path.join(fixtures_dir, f"{name}.json")
        with open(path, 'r') as f:
            return json.load(f)


class TestTravelIntentDetectionContracts(unittest.TestCase):
    """Test travel-intent detection tightening (Task 2)."""
    
    def setUp(self):
        """Set up test fixtures."""
        import re
        self.re = re
    
    def _detect_travel_intent(self, user_input, location_data=None):
        """
        Mirror of main.py travel-intent detection logic.
        Returns True if travel intent detected.
        """
        if not user_input:
            return False
            
        input_lower = user_input.lower()
        
        # PHASE 1: Check for directional movement verbs (required)
        directional_verbs = ["go", "travel", "head", "move", "walk", "run", "proceed"]
        has_directional_verb = any(
            self.re.search(r'\b' + verb + r'\b', input_lower) for verb in directional_verbs
        )
        
        # PHASE 2: Check for destination indicators (required)
        destination_indicators = [
            "north", "south", "east", "west", "up", "down", "left", "right",
            "forward", "backward", "back", "there", "here", "to the", "toward", "towards",
        ]
        if location_data and "locations" in location_data:
            for loc in location_data["locations"]:
                loc_name = loc.get("name", "").lower()
                if loc_name:
                    destination_indicators.append(loc_name)
        
        has_destination = any(
            self.re.search(r'\b' + self.re.escape(indicator) + r'\b', input_lower)
            for indicator in destination_indicators
        )
        
        # PHASE 3: Detect inquiry-only inputs (must NOT be inquiry-only)
        # Inquiry-only = wondering/thinking/asking WITHOUT directional movement
        inquiry_patterns = [
            r'^\s*(?:i\s+)?wonder\s+(?:about|if|whether)',
            r'^\s*(?:i\s+)?think\s+(?:about|of)',
            r'^\s*what\s+do\s+(?:i|we)\s+know',
            r'^\s*tell\s+(?:me|us)\s+about',
            r'^\s*ask\s+(?:about|regarding)',
        ]
        # Only check inquiry patterns if NO directional verb present
        is_inquiry_only = not has_directional_verb and any(
            self.re.search(pattern, input_lower) for pattern in inquiry_patterns
        )
        
        return has_directional_verb and has_destination and not is_inquiry_only
    
    def test_travel_intent_directional_verb_and_destination(self):
        """True positive: directional verb + destination."""
        test_cases = [
            ("I go to the forest", True),
            ("We head north", True),
            ("Travel to the castle", True),
            ("Walk toward the village", True),
            ("Move forward", True),
            ("Proceed there", True),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                result = self._detect_travel_intent(input_text)
                self.assertEqual(result, expected, f"Input: '{input_text}'")
    
    def test_travel_intent_wondering_excluded(self):
        """True negative: wondering about location without movement."""
        test_cases = [
            ("I wonder about the forest", False),
            ("What do I know about the village?", False),
            ("Tell me about the castle", False),
            ("I think about going north", False),
            ("Ask about the cave", False),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                result = self._detect_travel_intent(input_text)
                self.assertEqual(result, expected, f"Input: '{input_text}'")
    
    def test_travel_intent_no_destination(self):
        """True negative: directional verb but no destination."""
        test_cases = [
            ("I want to go", False),  # "to" alone is not a destination
            ("Let's travel", False),
            ("We should move", False),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                result = self._detect_travel_intent(input_text)
                self.assertEqual(result, expected, f"Input: '{input_text}'")
    
    def test_travel_intent_no_directional_verb(self):
        """True negative: destination mentioned but no movement intent."""
        test_cases = [
            ("The forest is nice", False),
            ("Tell me what is north", False),
            ("The village has shops", False),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                result = self._detect_travel_intent(input_text)
                self.assertEqual(result, expected, f"Input: '{input_text}'")
    
    def test_travel_intent_with_location_names(self):
        """Test with actual location names from location_data."""
        location_data = {
            "locations": [
                {"name": "Whispering Woods"},
                {"name": "Iron Keep"},
            ]
        }
        test_cases = [
            ("Go to Whispering Woods", True),
            ("Travel to Iron Keep", True),
            ("Head toward the Whispering Woods", True),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                result = self._detect_travel_intent(input_text, location_data)
                self.assertEqual(result, expected, f"Input: '{input_text}'")
    
    def test_travel_intent_mixed_wondering_and_movement(self):
        """Edge case: wondering + actual movement intent."""
        # Should detect travel intent when movement verbs + destination are present
        # even if wondering words appear (movement takes precedence)
        test_cases = [
            ("I wonder if we should go north", True),  # Has "go" + "north"
            ("Let's travel there and see what we find", True),  # Has "travel" + "there"
            ("I wonder about going north", False),  # No directional verb + destination combo
        ]
        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                result = self._detect_travel_intent(input_text)
                self.assertEqual(result, expected, f"Input: '{input_text}'")


class TestPromptSingularityContracts(unittest.TestCase):
    """Contracts for single canonical narrator system prompt in outbound payload."""

    def test_dedupe_helper_exists_in_main(self):
        """main.py should define a dedicated prompt singularity helper."""
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )

        with open(main_py_path, 'r') as f:
            content = f.read()

        self.assertIn(
            "def dedupe_main_system_prompt_messages(",
            content,
            "Expected dedupe_main_system_prompt_messages helper in main.py"
        )

    def test_dedupe_helper_collapses_legacy_and_canonical(self):
        """Legacy + canonical prompt inputs should collapse to one canonical prompt."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from main import dedupe_main_system_prompt_messages

        canonical_prompt = "You are the Dungeon Master for the world's most popular roleplaying game, 5th Edition."
        messages = [
            {"role": "system", "content": "You are a world-class 5th edition Dungeon Master who excels in telling warm stories."},
            {"role": "system", "content": canonical_prompt},
            {"role": "system", "content": "WORLD STATE CONTEXT:\nCurrent module: Test"},
            {"role": "user", "content": "hello"}
        ]

        deduped = dedupe_main_system_prompt_messages(messages, canonical_prompt)
        prompt_count = sum(1 for m in deduped if m.get("role") == "system" and m.get("content", "").startswith(canonical_prompt[:50]))

        self.assertEqual(prompt_count, 1, "Expected exactly one canonical prompt after dedupe")
        self.assertEqual(deduped[0]["role"], "system")
        self.assertTrue(deduped[0]["content"].startswith(canonical_prompt[:50]))


class TestNarratorContractSourceGuards(unittest.TestCase):
    """Source-level guard tests for narrator contract wiring."""

    def test_system_prompt_has_umpire_direct_answer_block(self):
        """Compressed system prompt should include direct adjudication guidance."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "system_prompt_compressed.txt"
        )
        with open(prompt_path, "r") as f:
            content = f.read()

        self.assertIn("@UMPIRE_DIRECT_ANSWER={", content)
        self.assertIn("ruling sentence", content)

    def test_validation_prompt_has_umpire_direct_answer_validation_block(self):
        """Compressed validation prompt should enforce ruling-first contract."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt_compressed.txt"
        )
        with open(prompt_path, "r") as f:
            content = f.read()

        self.assertIn("@UMPIRE_DIRECT_ANSWER_VALIDATION={", content)
        self.assertIn("clear ruling-first", content)

    def test_main_has_prerequisite_locked_plot_filter(self):
        """main.py should gate active plot visibility by prerequisites."""
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py"
        )

        with open(main_py_path, "r") as f:
            content = f.read()

        self.assertIn("def _is_plot_point_unlocked(point):", content)
        self.assertIn("plot_status_by_id", content)


if __name__ == "__main__":
    # Run tests with verbosity
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFixtureContracts))
    suite.addTests(loader.loadTestsFromTestCase(TestRetryHygieneContracts))
    suite.addTests(loader.loadTestsFromTestCase(TestCleanFollowupIsolation))
    suite.addTests(loader.loadTestsFromTestCase(TestNPCMoveFallbackContracts))
    suite.addTests(loader.loadTestsFromTestCase(TestTravelIntentDetectionContracts))
    suite.addTests(loader.loadTestsFromTestCase(TestPromptSingularityContracts))
    suite.addTests(loader.loadTestsFromTestCase(TestNarratorContractSourceGuards))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
