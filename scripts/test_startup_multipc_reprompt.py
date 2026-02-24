# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Startup multi-PC reprompt regression tests.

Validates Step 4.1 contracts for `pc-creation-startup-fixes`:
- explicit yes/no enforcement in startup add-more loop
- blank/invalid input reprompt behavior
- no silent loop exit without explicit no
"""

import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils import startup_wizard
    STARTUP_WIZARD_AVAILABLE = True
    STARTUP_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    startup_wizard = None
    STARTUP_WIZARD_AVAILABLE = False
    STARTUP_IMPORT_ERROR = exc


class TestStartupMultiPcReprompt(unittest.TestCase):
    """Focused startup tests for explicit yes/no + reprompt behavior."""

    def setUp(self):
        if not STARTUP_WIZARD_AVAILABLE:
            self.skipTest(f"startup_wizard unavailable: {STARTUP_IMPORT_ERROR}")

    def _run_startup(self, input_values, create_side_effect):
        """Run startup sequence with mocked dependencies and scripted input."""
        selected_module = {
            "name": "test_module",
            "display_name": "Test Module",
        }

        create_new_character_mock = MagicMock(side_effect=create_side_effect)
        update_party_tracker_mock = MagicMock()
        cleanup_mock = MagicMock()

        with patch.object(startup_wizard, "initialize_game_files_from_bu", return_value=0), \
             patch.object(startup_wizard, "initialize_startup_conversation", return_value=[]), \
             patch.object(startup_wizard, "select_module", return_value=selected_module), \
             patch.object(startup_wizard, "select_or_create_character", return_value="alpha"), \
             patch.object(startup_wizard, "create_new_character", create_new_character_mock), \
             patch.object(startup_wizard, "update_party_tracker", update_party_tracker_mock), \
             patch.object(startup_wizard, "cleanup_startup_conversation", cleanup_mock), \
             patch("builtins.input", side_effect=input_values), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = startup_wizard.run_startup_sequence()
            output = mock_stdout.getvalue()

        return result, output, create_new_character_mock, update_party_tracker_mock

    def test_primary_prompt_reprompts_for_blank_and_invalid(self):
        """Blank/invalid add-more inputs reprompt until explicit yes/no."""
        result, output, create_mock, update_mock = self._run_startup(
            input_values=["", "maybe", "y", "n"],
            create_side_effect=["beta"],
        )

        self.assertTrue(result)
        self.assertEqual(create_mock.call_count, 1)
        update_mock.assert_called_once_with("test_module", ["alpha", "beta"])

        self.assertGreaterEqual(output.count("Add another player character? (y/n):"), 4)
        self.assertGreaterEqual(output.count("Please enter 'y' for yes or 'n' for no."), 2)

    def test_secondary_retry_blank_does_not_silently_exit(self):
        """Blank retry input must not end loop; explicit no is still required."""
        result, output, create_mock, update_mock = self._run_startup(
            input_values=["y", "", "y", "n"],
            create_side_effect=[None, "beta"],
        )

        self.assertTrue(result)
        self.assertEqual(create_mock.call_count, 2)
        update_mock.assert_called_once_with("test_module", ["alpha", "beta"])

        self.assertIn("Additional player creation failed.", output)
        self.assertIn("Retry creating another player? (y/n):", output)
        self.assertIn("Please enter 'y' for yes or 'n' for no.", output)

    def test_secondary_retry_explicit_no_exits_loop(self):
        """Retry decision exits only on explicit n/no after failure."""
        result, output, create_mock, update_mock = self._run_startup(
            input_values=["y", "n"],
            create_side_effect=[None],
        )

        self.assertTrue(result)
        self.assertEqual(create_mock.call_count, 1)
        update_mock.assert_called_once_with("test_module", ["alpha"])
        self.assertIn("Retry creating another player? (y/n):", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
