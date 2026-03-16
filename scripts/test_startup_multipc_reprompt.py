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
import tempfile
import unittest
from pathlib import Path
from typing import Any
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
        assert startup_wizard is not None
        wizard: Any = startup_wizard
        selected_module = {
            "name": "test_module",
            "display_name": "Test Module",
        }

        create_new_character_mock = MagicMock(side_effect=create_side_effect)
        update_party_tracker_mock = MagicMock(return_value=True)
        cleanup_mock = MagicMock()

        with patch.object(wizard, "initialize_game_files_from_bu", return_value=0), \
             patch.object(wizard, "initialize_startup_conversation", return_value=[]), \
             patch.object(wizard, "select_module", return_value=selected_module), \
             patch.object(wizard, "select_or_create_character", return_value="alpha"), \
             patch.object(wizard, "create_new_character", create_new_character_mock), \
             patch.object(wizard, "update_party_tracker", update_party_tracker_mock), \
             patch.object(wizard, "cleanup_startup_conversation", cleanup_mock), \
             patch("builtins.input", side_effect=input_values), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = wizard.run_startup_sequence()
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
        self.assertEqual(update_mock.call_count, 3)
        self.assertEqual(
            [entry.kwargs.get("startup_incomplete") for entry in update_mock.call_args_list],
            [True, True, False],
        )
        self.assertTrue(all(entry.args[0] == "test_module" for entry in update_mock.call_args_list))

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
        self.assertEqual(update_mock.call_count, 3)
        self.assertEqual(
            [entry.kwargs.get("startup_incomplete") for entry in update_mock.call_args_list],
            [True, True, False],
        )
        self.assertTrue(all(entry.args[0] == "test_module" for entry in update_mock.call_args_list))

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
        self.assertEqual(update_mock.call_count, 2)
        self.assertEqual(
            [entry.kwargs.get("startup_incomplete") for entry in update_mock.call_args_list],
            [True, False],
        )
        self.assertTrue(all(entry.args[0] == "test_module" for entry in update_mock.call_args_list))
        self.assertIn("Retry creating another player? (y/n):", output)

    def test_interrupted_after_first_persistence_never_clears_incomplete(self):
        """Interruption after first PC persistence keeps startup-incomplete uncleared."""
        result, output, create_mock, update_mock = self._run_startup(
            input_values=RuntimeError("simulated interruption"),
            create_side_effect=[],
        )

        self.assertFalse(result)
        self.assertEqual(create_mock.call_count, 0)
        self.assertEqual(update_mock.call_count, 1)
        update_mock.assert_called_once_with("test_module", ["alpha"], startup_incomplete=True)
        self.assertNotIn("startup_incomplete=False", str(update_mock.call_args_list))
        self.assertIn("Error during setup", output)


class TestStartupIncompleteResumeContracts(unittest.TestCase):
    """Focused runtime contracts for startup_incomplete resume behavior."""

    def setUp(self):
        if not STARTUP_WIZARD_AVAILABLE:
            self.skipTest(f"startup_wizard unavailable: {STARTUP_IMPORT_ERROR}")

    def test_startup_required_true_when_incomplete_even_if_state_otherwise_valid(self):
        """startup_required must force wizard resume when startup_incomplete is true."""
        assert startup_wizard is not None
        fake_party = {
            "module": "test_module",
            "partyMembers": ["alpha"],
            "startup_incomplete": True,
        }

        mock_path_manager = MagicMock()
        mock_path_manager.get_character_unified_path.return_value = "characters/alpha.json"

        with patch.object(startup_wizard, "safe_json_load", return_value=fake_party), \
             patch.object(startup_wizard, "ModulePathManager", return_value=mock_path_manager), \
             patch.object(startup_wizard.os.path, "exists", return_value=True):
            self.assertTrue(startup_wizard.startup_required("party_tracker.json"))

    def test_startup_required_false_when_incomplete_is_false_and_state_valid(self):
        """Completed startup metadata should preserve normal startup-required behavior."""
        assert startup_wizard is not None
        fake_party = {
            "module": "test_module",
            "partyMembers": ["alpha"],
            "startup_incomplete": False,
        }

        mock_path_manager = MagicMock()
        mock_path_manager.get_character_unified_path.return_value = "characters/alpha.json"

        with patch.object(startup_wizard, "safe_json_load", return_value=fake_party), \
             patch.object(startup_wizard, "ModulePathManager", return_value=mock_path_manager), \
             patch.object(startup_wizard.os.path, "exists", return_value=True):
            self.assertFalse(startup_wizard.startup_required("party_tracker.json"))

    def test_update_party_tracker_preserves_existing_members_on_resume_progress(self):
        """update_party_tracker appends new members and preserves existing startup members."""
        assert startup_wizard is not None
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                existing_party = {
                    "module": "test_module",
                    "partyMembers": ["alpha"],
                    "active_character": "alpha",
                    "partyNPCs": [],
                    "worldConditions": {
                        "year": 1492,
                        "month": "Springmonth",
                        "day": 1,
                        "time": "09:00:00",
                        "weather": "Clear skies",
                        "season": "Spring",
                        "dayNightCycle": "Day",
                        "moonPhase": "New Moon",
                        "currentLocation": "",
                        "currentLocationId": "",
                        "currentArea": "",
                        "currentAreaId": "",
                        "majorEventsUnderway": [],
                        "politicalClimate": "",
                        "activeEncounter": "",
                        "activeCombatEncounter": "",
                    },
                }
                Path("party_tracker.json").write_text(
                    startup_wizard.json.dumps(existing_party),
                    encoding="utf-8",
                )

                first_update = startup_wizard.update_party_tracker(
                    "test_module",
                    ["alpha", "beta"],
                    startup_incomplete=True,
                )
                self.assertTrue(first_update)

                first_data = startup_wizard.safe_json_load("party_tracker.json")
                self.assertEqual(first_data.get("partyMembers"), ["alpha", "beta"])
                self.assertEqual(first_data.get("active_character"), "alpha")
                self.assertTrue(first_data.get("startup_incomplete"))

                second_update = startup_wizard.update_party_tracker(
                    "test_module",
                    ["alpha", "beta"],
                    startup_incomplete=False,
                )
                self.assertTrue(second_update)

                second_data = startup_wizard.safe_json_load("party_tracker.json")
                self.assertEqual(second_data.get("partyMembers"), ["alpha", "beta"])
                self.assertEqual(second_data.get("active_character"), "alpha")
                self.assertFalse(second_data.get("startup_incomplete"))
            finally:
                os.chdir(original_cwd)

    def test_update_party_tracker_preserves_existing_active_character_when_valid(self):
        """Existing valid active_character should survive resume-progress updates."""
        assert startup_wizard is not None
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                existing_party = {
                    "module": "test_module",
                    "partyMembers": ["alpha", "beta"],
                    "active_character": "beta",
                    "partyNPCs": [],
                    "worldConditions": {
                        "year": 1492,
                        "month": "Springmonth",
                        "day": 1,
                        "time": "09:00:00",
                        "weather": "Clear skies",
                        "season": "Spring",
                        "dayNightCycle": "Day",
                        "moonPhase": "New Moon",
                        "currentLocation": "",
                        "currentLocationId": "",
                        "currentArea": "",
                        "currentAreaId": "",
                        "majorEventsUnderway": [],
                        "politicalClimate": "",
                        "activeEncounter": "",
                        "activeCombatEncounter": "",
                    },
                }
                Path("party_tracker.json").write_text(
                    startup_wizard.json.dumps(existing_party),
                    encoding="utf-8",
                )

                update_result = startup_wizard.update_party_tracker(
                    "test_module",
                    ["alpha", "beta", "gamma"],
                    startup_incomplete=True,
                )
                self.assertTrue(update_result)

                updated_data = startup_wizard.safe_json_load("party_tracker.json")
                self.assertEqual(updated_data.get("partyMembers"), ["alpha", "beta", "gamma"])
                self.assertEqual(updated_data.get("active_character"), "beta")
            finally:
                os.chdir(original_cwd)


class TestStartupInterviewOutputContracts(unittest.TestCase):
    """Focused tests for startup interview output suppression and input normalization."""

    def setUp(self):
        if not STARTUP_WIZARD_AVAILABLE:
            self.skipTest(f"startup_wizard unavailable: {STARTUP_IMPORT_ERROR}")

    def test_normalize_startup_prompt_input_strips_tabletop_prefix(self):
        assert startup_wizard is not None
        self.assertEqual(startup_wizard._normalize_startup_prompt_input("[xorn]: y"), "y")
        self.assertEqual(startup_wizard._normalize_startup_prompt_input("[xorn]: yes"), "yes")
        self.assertEqual(startup_wizard._normalize_startup_prompt_input("  n  "), "n")

    def test_ai_interview_does_not_print_raw_final_json_on_success(self):
        assert startup_wizard is not None
        final_response = '{"name": "Xorn", "class": "Cleric"}'

        with patch.object(startup_wizard, "safe_json_load", return_value={"type": "object"}), \
             patch.object(startup_wizard, "build_dm_creation_prompt_bundle", return_value={
                 "system_prompt": "system",
                 "kickoff_user_prompt": "kickoff",
             }), \
             patch.object(startup_wizard, "get_ai_response", return_value=final_response), \
             patch.object(startup_wizard, "finalize_character_creation_candidate", return_value={
                 "status": "success",
                 "character_data": {"name": "Xorn"},
             }), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = startup_wizard.ai_character_interview([], {"name": "test_module"})
            output = mock_stdout.getvalue()

        self.assertEqual(result, {"name": "Xorn"})
        self.assertIn("Character data received! Finalizing your hero...", output)
        self.assertNotIn(final_response, output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
