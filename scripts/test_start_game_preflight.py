#!/usr/bin/env python3
"""Regression tests for start_game_preflight.py helper outcomes.

Tests three terminal scenarios:
1. Direct pass - no remediation needed
2. Remediation pass - initial fail, remediation succeeds, revalidation passes
3. Remediation fail - initial fail, remediation attempted, still unresolved
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestStartGamePreflightOutcomes(unittest.TestCase):
    """Test preflight helper terminal state outcomes."""

    def setUp(self):
        """Set up common test fixtures."""
        self.module_name = "TestModule"
        self.normalized_module = "TestModule"

    def _build_party_tracker(self, module: str = "TestModule") -> dict:
        """Build a mock party tracker with specified module."""
        return {"module": module}

    @patch("web.extensions.start_game_preflight.Path")
    @patch("web.extensions.start_game_preflight.safe_read_json")
    @patch("web.extensions.start_game_preflight._run_module_validation")
    def test_direct_pass_no_remediation_needed(self, mock_validate, mock_read_json, mock_path):
        """Test direct pass when validation succeeds immediately.

        Scenario:
        - Party tracker exists with valid module
        - Initial validation returns zero unresolved references
        - Result: status="pass", no remediation attempted
        """
        # Arrange
        mock_read_json.return_value = self._build_party_tracker(self.module_name)
        mock_validate.return_value = (0, [])  # failed_count, errors
        mock_path.return_value.exists.return_value = True

        # Act
        from web.extensions.start_game_preflight import run_start_game_module_preflight

        result = run_start_game_module_preflight()

        # Assert
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["module"], self.normalized_module)
        self.assertEqual(result["reference_failed"], 0)
        self.assertEqual(result["reference_errors"], [])
        self.assertIn("message", result)
        self.assertIn("passed", result["message"].lower())

        # Verify validation called once (no remediation attempted)
        mock_validate.assert_called_once()

    @patch("web.extensions.start_game_preflight.Path")
    @patch("web.extensions.start_game_preflight.safe_read_json")
    @patch("web.extensions.start_game_preflight._attempt_remediation")
    @patch("web.extensions.start_game_preflight._run_module_validation")
    def test_remediation_pass_initial_fail_then_success(
        self, mock_validate, mock_remediate, mock_read_json, mock_path
    ):
        """Test repaired_pass when remediation fixes unresolved references.

        Scenario:
        - Party tracker exists with valid module
        - Initial validation returns 3 unresolved references
        - Remediation attempt succeeds
        - Re-validation returns zero unresolved references
        - Result: status="repaired_pass"
        """
        # Arrange
        mock_read_json.return_value = self._build_party_tracker(self.module_name)
        # First call: 3 unresolved, second call: 0 unresolved
        mock_validate.side_effect = [(3, ["error1", "error2", "error3"]), (0, [])]
        mock_remediate.return_value = True  # Remediation completed successfully
        mock_path.return_value.exists.return_value = True

        # Act
        from web.extensions.start_game_preflight import run_start_game_module_preflight

        result = run_start_game_module_preflight()

        # Assert
        self.assertEqual(result["status"], "repaired_pass")
        self.assertEqual(result["module"], self.normalized_module)
        self.assertEqual(result["reference_failed"], 0)
        self.assertEqual(result["reference_errors"], [])
        self.assertIn("message", result)
        self.assertIn("repaired", result["message"].lower())

        # Verify validation called twice (initial + post-remediation)
        self.assertEqual(mock_validate.call_count, 2)
        # Verify remediation attempted exactly once
        mock_remediate.assert_called_once()

    @patch("web.extensions.start_game_preflight.Path")
    @patch("web.extensions.start_game_preflight.safe_read_json")
    @patch("web.extensions.start_game_preflight._attempt_remediation")
    @patch("web.extensions.start_game_preflight._run_module_validation")
    def test_remediation_fail_unresolved_remain(
        self, mock_validate, mock_remediate, mock_read_json, mock_path
    ):
        """Test fail when remediation cannot resolve all references.

        Scenario:
        - Party tracker exists with valid module
        - Initial validation returns 5 unresolved references
        - Remediation attempt succeeds (but doesn't fix everything)
        - Re-validation still returns 2 unresolved references
        - Result: status="fail" with actionable message
        """
        # Arrange
        mock_read_json.return_value = self._build_party_tracker(self.module_name)
        initial_errors = ["ref1", "ref2", "ref3", "ref4", "ref5"]
        remaining_errors = ["ref4", "ref5"]
        # First call: 5 unresolved, second call: 2 still unresolved
        mock_validate.side_effect = [(5, initial_errors), (2, remaining_errors)]
        mock_remediate.return_value = True  # Remediation completed but didn't fix all
        mock_path.return_value.exists.return_value = True

        # Act
        from web.extensions.start_game_preflight import run_start_game_module_preflight

        result = run_start_game_module_preflight()

        # Assert
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["module"], self.normalized_module)
        self.assertEqual(result["reference_failed"], 2)
        self.assertEqual(result["reference_errors"], remaining_errors)
        self.assertIn("message", result)

        # Verify actionable message contains fix instructions
        message = result["message"]
        self.assertIn("[SYSTEM]", message)
        self.assertIn("failed", message.lower())
        self.assertIn("generate_missing_monsters.py", message)

        # Verify validation called twice (initial + post-remediation)
        self.assertEqual(mock_validate.call_count, 2)
        # Verify remediation attempted exactly once
        mock_remediate.assert_called_once()

    @patch("web.extensions.start_game_preflight.Path")
    @patch("web.extensions.start_game_preflight.safe_read_json")
    @patch("web.extensions.start_game_preflight._attempt_remediation")
    @patch("web.extensions.start_game_preflight._run_module_validation")
    def test_remediation_fail_attempt_failed(
        self, mock_validate, mock_remediate, mock_read_json, mock_path
    ):
        """Test fail when remediation attempt itself fails.

        Scenario:
        - Party tracker exists with valid module
        - Initial validation returns unresolved references
        - Remediation attempt fails (returns False)
        - No re-validation attempted
        - Result: status="fail" with actionable message
        """
        # Arrange
        mock_read_json.return_value = self._build_party_tracker(self.module_name)
        initial_errors = ["ref1", "ref2"]
        mock_validate.return_value = (2, initial_errors)
        mock_remediate.return_value = False  # Remediation failed to complete
        mock_path.return_value.exists.return_value = True

        # Act
        from web.extensions.start_game_preflight import run_start_game_module_preflight

        result = run_start_game_module_preflight()

        # Assert
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["module"], self.normalized_module)
        self.assertEqual(result["reference_failed"], 2)
        self.assertEqual(result["reference_errors"], initial_errors)
        self.assertIn("message", result)

        # Verify actionable message
        message = result["message"]
        self.assertIn("[SYSTEM]", message)
        self.assertIn("failed", message.lower())

        # Verify validation called only once (no re-validation since remediation failed)
        mock_validate.assert_called_once()
        # Verify remediation attempted exactly once
        mock_remediate.assert_called_once()


class TestStartGamePreflightPayloadContract(unittest.TestCase):
    """Test that payload contains all required keys in all scenarios."""

    @patch("web.extensions.start_game_preflight.Path")
    @patch("web.extensions.start_game_preflight.safe_read_json")
    @patch("web.extensions.start_game_preflight._run_module_validation")
    def test_payload_keys_present_in_pass(self, mock_validate, mock_read_json, mock_path):
        """Verify all payload keys present in pass scenario."""
        mock_read_json.return_value = {"module": "TestMod"}
        mock_validate.return_value = (0, [])
        mock_path.return_value.exists.return_value = True

        from web.extensions.start_game_preflight import run_start_game_module_preflight

        result = run_start_game_module_preflight()

        required_keys = {"status", "module", "reference_failed", "reference_errors", "message"}
        self.assertTrue(required_keys.issubset(result.keys()))

    @patch("web.extensions.start_game_preflight._attempt_remediation")
    @patch("web.extensions.start_game_preflight.Path")
    @patch("web.extensions.start_game_preflight.safe_read_json")
    @patch("web.extensions.start_game_preflight._run_module_validation")
    def test_payload_keys_present_in_fail(
        self, mock_validate, mock_read_json, mock_path, mock_remediate
    ):
        """Verify all payload keys present in fail scenario (deterministic, no side effects)."""
        mock_read_json.return_value = {"module": "TestMod"}
        # Return unresolved on both calls to trigger fail path
        mock_validate.side_effect = [(3, ["e1", "e2", "e3"]), (3, ["e1", "e2", "e3"])]
        mock_path.return_value.exists.return_value = True
        mock_remediate.return_value = True  # Remediation completes but doesn't fix

        from web.extensions.start_game_preflight import run_start_game_module_preflight

        result = run_start_game_module_preflight()

        required_keys = {"status", "module", "reference_failed", "reference_errors", "message"}
        self.assertTrue(required_keys.issubset(result.keys()))

    @patch("web.extensions.start_game_preflight._attempt_remediation")
    @patch("web.extensions.start_game_preflight.Path")
    @patch("web.extensions.start_game_preflight.safe_read_json")
    @patch("web.extensions.start_game_preflight._run_module_validation")
    def test_remediation_attempted_at_most_once_per_preflight_call(
        self, mock_validate, mock_read_json, mock_path, mock_remediate
    ):
        """Test that remediation runs at most once per preflight invocation.

        Scenario:
        - Initial validation fails with 4 unresolved references
        - Remediation attempted once and returns True
        - Re-validation still has 2 unresolved (partial fix)
        - Result: status="fail", but remediation called exactly once
        """
        # Arrange
        mock_read_json.return_value = {"module": "TestMod"}
        initial_errors = ["a", "b", "c", "d"]
        remaining_errors = ["c", "d"]
        mock_validate.side_effect = [(4, initial_errors), (2, remaining_errors)]
        mock_path.return_value.exists.return_value = True
        mock_remediate.return_value = True

        # Act
        from web.extensions.start_game_preflight import run_start_game_module_preflight

        result = run_start_game_module_preflight()

        # Assert
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["reference_failed"], 2)

        # Critical: remediation attempted exactly once
        mock_remediate.assert_called_once()
        # Validation called exactly twice (initial + one revalidation)
        self.assertEqual(mock_validate.call_count, 2)


class TestStartGameFailGateContract(unittest.TestCase):
    """Source-contract tests for startup fail-gate wiring in web_interface.py."""

    def setUp(self):
        """Load web_interface.py source for contract analysis."""
        self.interface_path = Path(__file__).resolve().parents[1] / "web" / "web_interface.py"
        self.source = self.interface_path.read_text(encoding="utf-8")

    def test_fail_gate_status_check_exists(self):
        """Verify fail-gate checks for status == 'fail'."""
        fail_check = "preflight_result.get('status') == 'fail'"
        self.assertIn(fail_check, self.source,
                      f"Fail-gate must check for status == 'fail'. Missing: {fail_check}")

    def test_fail_gate_emits_error_and_returns(self):
        """Verify fail-gate emits error and returns before startup."""
        handle_start_section = self.source.split("@socketio.on('start_game')")[1].split("@socketio.on(")[0]
        
        # Verify emit error present
        self.assertIn("emit('error',", handle_start_section,
                      "Fail-gate must emit 'error' event")
        
        # Verify return present
        self.assertIn("return", handle_start_section,
                      "Fail-gate must have immediate return after emit")

    def test_fail_gate_before_startup_progression(self):
        """Verify fail-gate return happens before uninstall_debug_interceptor."""
        handle_start_section = self.source.split("@socketio.on('start_game')")[1].split("@socketio.on(")[0]
        
        fail_gate_marker = "preflight_result.get('status') == 'fail'"
        fail_gate_pos = handle_start_section.find(fail_gate_marker)
        self.assertGreater(fail_gate_pos, 0, "Fail-gate must exist in handle_start_game")
        
        # Find the return after fail gate
        return_after_fail = handle_start_section.find("return", fail_gate_pos)
        self.assertGreater(return_after_fail, fail_gate_pos,
                           "Return must exist after fail-gate check")
        
        # Verify uninstall_debug_interceptor comes after return
        uninstall_pos = handle_start_section.find("uninstall_debug_interceptor()")
        self.assertGreater(uninstall_pos, return_after_fail,
                           "uninstall_debug_interceptor() must come after fail-gate return")

    def test_fallback_message_contract_present(self):
        """Verify fallback [SYSTEM] message contract exists."""
        expected_fallback = "[SYSTEM] Module preflight failed. Combat startup blocked."
        self.assertIn(expected_fallback, self.source,
                      f"Fallback message contract must be present: {expected_fallback}")


if __name__ == "__main__":
    unittest.main()
