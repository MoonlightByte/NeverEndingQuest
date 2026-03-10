# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Validation Payload Hygiene Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for validation payload contradictions, duplicates, and budget constraints.
"""

import unittest
import sys
import os
import re


class TestContradictoryGuidance(unittest.TestCase):
    """Test that contradictory guidance blocks are not emitted together."""

    def test_no_contradictory_arrival_sync_guidance_in_build_npc_context(self):
        """
        Verify that build_npc_context does not emit text contradicting arrival-sync rules.
        
        The text "Do NOT flag missing physical presence as error" contradicts
        @NPC_ARRIVAL_VALIDATION which requires actions for explicit arrivals.
        """
        # Read build_npc_context.py
        build_npc_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "ai", "build_npc_context.py"
        )
        
        with open(build_npc_path, 'r') as f:
            content = f.read()
        
        # Look for the contradictory text
        # This test documents the CURRENT buggy state
        # After Step 4.2 fixes this, this test should be updated to assert NOT present
        has_contradictory_text = "Do NOT flag missing physical presence as error" in content
        
        if has_contradictory_text:
            # Document the bug - this will fail until Step 4.2 fixes it
            self.fail(
                "CONTRADICTION DETECTED: build_npc_context.py contains "
                "'Do NOT flag missing physical presence as error' which contradicts "
                "@NPC_ARRIVAL_VALIDATION rules. This must be fixed in Step 4.2."
            )

    def test_arrival_sync_rules_present_in_validation_prompt(self):
        """
        Verify that validation prompt contains arrival-sync enforcement rules.
        """
        validation_prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt_compressed.txt"
        )
        
        with open(validation_prompt_path, 'r') as f:
            content = f.read()
        
        # Should have NPC_ARRIVAL_VALIDATION section
        self.assertIn("@NPC_ARRIVAL_VALIDATION", content,
                     "Validation prompt missing @NPC_ARRIVAL_VALIDATION section")
        
        # Should have explicit arrival verb list
        self.assertIn("explicit_arrival_verbs:", content,
                     "Validation prompt missing explicit_arrival_verbs guidance")
        
        # Should require matching state action
        self.assertIn("MUST have matching state action", content,
                     "Validation prompt missing state action requirement")


class TestDuplicateGuidance(unittest.TestCase):
    """Test that validation guidance is not duplicated unnecessarily."""

    def test_no_duplicate_critical_rules_in_validation_prompt(self):
        """
        Verify that high-priority arrival/state-sync rules are not duplicated.
        
        Duplicate critical rules can confuse the validator and bloat payload.
        """
        validation_prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt_compressed.txt"
        )
        
        with open(validation_prompt_path, 'r') as f:
            content = f.read()
        
        # Check for duplicated high-priority rule blocks
        # Count occurrences of key rule markers
        arrival_validation_count = content.count("@NPC_ARRIVAL_VALIDATION")
        self.assertEqual(arrival_validation_count, 1,
                        f"@NPC_ARRIVAL_VALIDATION appears {arrival_validation_count} times (should be 1)")
        
        # Check that explicit_arrival_verbs list appears only once
        explicit_verbs_count = content.count("explicit_arrival_verbs:")
        self.assertEqual(explicit_verbs_count, 1,
                        f"explicit_arrival_verbs appears {explicit_verbs_count} times (should be 1)")

    def test_validation_prompt_unique_section_headers(self):
        """
        Verify that major section headers in validation prompt are unique.
        """
        validation_prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt_compressed.txt"
        )
        
        with open(validation_prompt_path, 'r') as f:
            content = f.read()
        
        # Find all @SECTION headers
        section_pattern = r'^@[A-Z_]+=\{|^@[A-Z_]+\{'
        sections = re.findall(section_pattern, content, re.MULTILINE)
        
        # Count occurrences of each section type
        section_counts = {}
        for section in sections:
            section_counts[section] = section_counts.get(section, 0) + 1
        
        # Each section type should appear only once
        duplicates = {s: c for s, c in section_counts.items() if c > 1}
        self.assertEqual(len(duplicates), 0,
                        f"Duplicate section headers found: {duplicates}")


class TestPayloadBudget(unittest.TestCase):
    """Test that validation payload stays within reasonable bounds."""

    def test_validation_prompt_size_under_proxy_budget(self):
        """
        Verify validation prompt is under token budget proxy.
        
        Uses char_count/4.0 as a rough token estimator.
        Target: < 5000 tokens (20000 chars).
        """
        validation_prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt_compressed.txt"
        )
        
        with open(validation_prompt_path, 'r') as f:
            content = f.read()
        
        char_count = len(content)
        token_proxy = char_count / 4.0
        
        # Budget: 5000 tokens = ~20000 chars
        BUDGET_CHARS = 20000
        
        self.assertLess(char_count, BUDGET_CHARS,
                       f"Validation prompt ({char_count} chars, ~{token_proxy:.0f} tokens) "
                       f"exceeds budget proxy ({BUDGET_CHARS} chars, ~5000 tokens)")

    def test_npc_context_builder_output_bounded(self):
        """
        Verify NPC context builder produces bounded output.
        
        The builder limits other_modules to 30 NPCs and module NPCs to 50.
        """
        build_npc_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "ai", "build_npc_context.py"
        )
        
        with open(build_npc_path, 'r') as f:
            content = f.read()
        
        # Check for explicit bounds in the code
        self.assertIn("[:50]", content,
                     "NPC context builder missing [:50] bound for module_npcs")
        self.assertIn("[:30]", content,
                     "NPC context builder missing [:30] bound for other_npcs")


class TestDeterministicResultContract(unittest.TestCase):
    """Test that deterministic result metadata contract is present in validation flow."""

    def test_deterministic_result_metadata_in_main_validation_flow(self):
        """
        Verify main.py validation flow supports deterministic result metadata.
        
        Step 3.1 COMPLETE: Deterministic metadata handoff is now implemented.
        This test verifies the contract is in place.
        """
        # TODO: After Step 3.1 implementation:
        # 1. Read main.py validation flow
        # 2. Check for deterministic result metadata being passed to LLM validator context
        # 3. Verify fields: deterministic_passed, reason, required_action
        
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py"
        )
        
        with open(main_path, 'r') as f:
            content = f.read()
        
        # Look for deterministic result metadata in validation context assembly
        # This pattern should exist after Step 3.1
        has_deterministic_metadata = (
            "deterministic_passed" in content or
            "deterministic_result" in content
        )
        
        # This assertion documents the expected contract
        # It will fail until Step 3.1 implements it
        self.assertTrue(
            has_deterministic_metadata,
            "Step 3.1 not yet implemented: main.py validation flow missing "
            "deterministic result metadata contract (deterministic_passed, "
            "deterministic_result, etc.). This is expected to fail until "
            "runtime refactor is complete."
        )

    def test_npc_arrival_validator_exports_structured_result(self):
        """
        Verify npc_arrival_validator returns structured result suitable for metadata.
        
        Current validator returns (is_valid, reason) tuple.
        After Step 3.1, should return structured dict with passed/reason/required_action.
        """
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.npc_arrival_validator import validate_npc_arrival_state_sync
        
        # Create minimal test case
        response_json = {"narration": "Test", "actions": []}
        party_tracker = {"partyMembers": [], "partyNPCs": []}
        location_data = {"npcs": []}
        module_npcs = set()
        
        result = validate_npc_arrival_state_sync(
            response_json, party_tracker, location_data, module_npcs
        )
        
        # Current contract: returns tuple (is_valid, reason)
        self.assertIsInstance(result, tuple, 
                             "Validator should return tuple (is_valid, reason)")
        self.assertEqual(len(result), 2,
                        "Validator tuple should have 2 elements")
        
        is_valid, reason = result
        self.assertIsInstance(is_valid, bool,
                             "First element should be boolean")
        self.assertIsInstance(reason, str,
                             "Second element should be string")


class TestCleanGuidanceContract(unittest.TestCase):
    """Test that validation guidance is clean and non-contradictory overall."""

    def test_no_arrival_sync_waiver_in_dynamic_context(self):
        """
        Document the specific contradiction to be fixed in Step 4.2.
        
        build_npc_context emits text that waives arrival-sync requirements,
        contradicting the explicit @NPC_ARRIVAL_VALIDATION rules.
        """
        build_npc_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "ai", "build_npc_context.py"
        )
        
        with open(build_npc_path, 'r') as f:
            content = f.read()
        
        # This specific text must be removed in Step 4.2
        waiver_text = "Do NOT flag missing physical presence as error"
        
        # Document current state - will fail until Step 4.2
        if waiver_text in content:
            self.fail(
                f"CRITICAL: build_npc_context.py contains waiver text that "
                f"contradicts @NPC_ARRIVAL_VALIDATION: '{waiver_text}'\n\n"
                f"This must be removed in Step 4.2 (Dynamic NPC context cleanup). "
                f"The text allows any NPC to be mentioned without actions, "
                f"while validation prompt requires actions for explicit arrivals."
            )


if __name__ == "__main__":
    # Run tests with verbosity
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestContradictoryGuidance))
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateGuidance))
    suite.addTests(loader.loadTestsFromTestCase(TestPayloadBudget))
    suite.addTests(loader.loadTestsFromTestCase(TestDeterministicResultContract))
    suite.addTests(loader.loadTestsFromTestCase(TestCleanGuidanceContract))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
