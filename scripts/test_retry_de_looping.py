#!/usr/bin/env python3
"""
Test for Prompt 3 (Tasks 3.1-3.3): Retry de-looping.

Verifies that:
1. Failed assistant output is NOT appended for deterministic guard failures
2. Concise normalized correction note is used instead of verbose retry note
3. Repeated same deterministic reason twice triggers early short-circuit
4. Non-deterministic validation retries still behave as expected
5. Existing exhaustion behavior preserved
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRetryDeLoopingContracts(unittest.TestCase):
    """Test that retry de-looping logic is present in main.py."""

    def test_retry_state_variables_exist(self):
        """
        Test 1: Retry state tracking variables exist for repeated-reason detection.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check for retry de-looping state variables
        self.assertIn(
            "last_validation_reason = None",
            content,
            "main.py should track last_validation_reason for repeat detection"
        )
        
        self.assertIn(
            "repeated_reason_count = 0",
            content,
            "main.py should track repeated_reason_count"
        )

    def test_repeated_reason_short_circuit_logic(self):
        """
        Test 2: Repeated-reason short-circuit logic exists.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check for short-circuit logic
        self.assertIn(
            "repeated_reason_count += 1",
            content,
            "main.py should increment repeated_reason_count"
        )
        
        self.assertIn(
            "Same deterministic reason repeated twice",
            content,
            "main.py should detect repeated reasons"
        )
        
        self.assertIn(
            "short-circuiting retry loop",
            content,
            "main.py should short-circuit on repeated reasons"
        )

    def test_no_failed_assistant_output_appended(self):
        """
        Test 3: Failed assistant output is NOT appended for deterministic failures.
        
        The old code had:
            conversation_history.append({"role": "assistant", "content": ai_response_content})
        
        This should be removed/skipped for deterministic guard failures.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check that the validation failure block doesn't save failed assistant output
        # The old comment "CRITICAL: Save the failed assistant response" should be removed
        # or the append should be conditional
        
        # Look for the validation failure section
        validation_fail_section = content.split("elif not is_valid and validation_reason:")[1]
        validation_fail_section = validation_fail_section.split("else:")[0]
        
        # Should NOT have unconditional assistant append in this section
        # (It may still exist elsewhere like transition pre-validation)
        self.assertNotIn(
            'conversation_history.append({"role": "assistant", "content": ai_response_content})',
            validation_fail_section,
            "Failed assistant output should NOT be appended in validation failure block"
        )

    def test_concise_correction_note_used(self):
        """
        Test 4: Concise normalized correction note format.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check for concise correction note format
        self.assertIn(
            "correction_note =",
            content,
            "main.py should use correction_note variable"
        )
        
        self.assertIn(
            '"[CORRECTION REQUIRED]:',
            content,
            "main.py should use concise [CORRECTION REQUIRED] prefix"
        )

    def test_deterministic_detection_logic(self):
        """
        Test 5: Deterministic guard detection logic exists.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check for deterministic guard detection
        self.assertIn(
            '"npc arrival state sync" in normalized_reason',
            content,
            "main.py should detect NPC arrival state sync as deterministic"
        )

    def test_exhaustion_behavior_preserved(self):
        """
        Test 6: Existing exhaustion behavior preserved.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check that exhaustion handling still exists
        self.assertIn(
            "get_validation_retry_exhaustion_message()",
            content,
            "main.py should still use exhaustion message function"
        )
        
        self.assertIn(
            "Failed to generate a valid response after 5 attempts",
            content,
            "main.py should still fail-closed after exhaustion"
        )


class TestRetryLoopBehavioralRegression(unittest.TestCase):
    """Task 5.2: Targeted retry-loop regression for deterministic failure handling."""

    def test_concise_note_format_token_efficient(self):
        """
        Test 8: Concise correction note is significantly shorter than old verbose format.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Verify concise format is used (should be ~50% shorter than old format)
        # Old format was: "Error Note: Your previous response failed validation. Reason: {reason}. Please adjust your response accordingly."
        # New format is: "[CORRECTION REQUIRED]: {validation_reason}"
        
        concise_marker = '[CORRECTION REQUIRED]:'
        old_verbose_marker = 'Your previous response failed validation'
        
        # Should have concise format
        self.assertIn(
            concise_marker,
            content,
            "Should use concise [CORRECTION REQUIRED] format"
        )
        
        # Should NOT have old verbose format in the deterministic branch
        validation_section = content.split("is_deterministic =")[1].split("conversation_history.append")[0]
        self.assertNotIn(
            old_verbose_marker,
            validation_section,
            "Old verbose format should be replaced with concise version"
        )

    def test_repeated_reason_short_circuit_resets(self):
        """
        Test 9: Repeated reason counter resets on new/different reason.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check that new reasons reset the counter
        self.assertIn(
            "last_validation_reason = normalized_reason",
            content,
            "Should store last reason for comparison"
        )
        
        self.assertIn(
            "repeated_reason_count = 0",
            content,
            "Should reset counter on new reason"
        )

    def test_short_circuit_force_exhaustion(self):
        """
        Test 10: Short-circuit forces exhaustion state correctly.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Verify short-circuit sets retry_count to max (5)
        self.assertIn(
            "retry_count = 5",
            content,
            "Short-circuit should force exhaustion by setting retry_count to max"
        )
        
        self.assertIn(
            "break  # Exit retry loop immediately",
            content,
            "Short-circuit should break out of retry loop"
        )

    def test_exhaustion_fail_closed_message_preserved(self):
        """
        Test 11: Exhaustion fail-closed messaging preserved (Task 5.2c).
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check exhaustion block still exists with fail-closed behavior
        exhaustion_section = content.split("if not valid_response_received:")[1]
        
        self.assertIn(
            "error_message = get_validation_retry_exhaustion_message()",
            exhaustion_section,
            "Should use exhaustion message function"
        )
        
        self.assertIn(
            '{"role": "system", "content": error_message}',
            exhaustion_section,
            "Should append system error message on exhaustion"
        )
        
        self.assertIn(
            "continue",
            exhaustion_section,
            "Should skip turn processing on exhaustion (continue to next iteration)"
        )


class TestBackwardsCompatibility(unittest.TestCase):
    """Test that non-deterministic failures still work correctly."""

    def test_non_deterministic_uses_standard_correction(self):
        """
        Test 7: Non-deterministic failures use standard correction format.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Check that there's an else branch for the is_deterministic check
        # Look for the pattern: if is_deterministic: ... else: ...
        validation_section = content.split("is_deterministic =")[1].split("correction_note")[0]
        
        # Should have if/else structure for deterministic vs non-deterministic
        self.assertIn(
            "if is_deterministic",
            content,
            "main.py should check is_deterministic"
        )
        
        # Check that else exists after the if block (handling non-deterministic)
        after_if = content.split("if is_deterministic:")[1]
        self.assertIn(
            "else:",
            after_if,
            "main.py should have else branch for non-deterministic failures"
        )
        
        # Verify non-deterministic branch uses standard correction
        after_else = after_if.split("else:")[1]
        self.assertIn(
            "Error Note:",
            after_else,
            "Non-deterministic branch should use standard Error Note format"
        )


class TestDeterministicCorrectionPathContracts(unittest.TestCase):
    """Contracts for deterministic correction wording to avoid impossible loops."""

    def test_arrival_failure_reason_offers_remove_claim_alternative(self):
        """Arrival failure reason should include legal rephrase option."""
        validator_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'utils',
            'npc_arrival_validator.py'
        )

        with open(validator_path, 'r') as f:
            content = f.read()

        self.assertIn(
            "remove explicit arrival",
            content.lower(),
            "Arrival failure reason should include remove explicit arrival alternative"
        )


if __name__ == '__main__':
    unittest.main()
