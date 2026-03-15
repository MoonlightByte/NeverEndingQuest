#!/usr/bin/env python3
"""Source-contract tests for module-data-git-fix Step 1.3.

These tests lock bootstrap/runtime-state assumptions before Git tracking cleanup.
They are intentionally lightweight and avoid live runtime dependencies.
"""

import re
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class TestLauncherBootstrapContracts(unittest.TestCase):
    """Contracts for run_web launcher bootstrap behavior."""

    @classmethod
    def setUpClass(cls):
        cls.run_web_path = PROJECT_ROOT / "run_web.py"
        cls.run_web_source = cls.run_web_path.read_text(encoding="utf-8")

    def test_default_party_tracker_helper_exists(self):
        """Launcher keeps explicit helper for default tracker creation."""
        self.assertIn("def create_default_party_tracker():", self.run_web_source)

    def test_default_party_tracker_auto_create_is_disabled(self):
        """Launcher pre-seed remains disabled and does not silently auto-create."""
        self.assertIn(
            "# DISABLED FOR DEBUGGING - Create default party_tracker.json if it doesn't exist",
            self.run_web_source,
        )
        self.assertIn("# if not create_default_party_tracker():", self.run_web_source)

        enabled_call_pattern = re.compile(
            r"^\s*if\s+not\s+create_default_party_tracker\(\):", re.MULTILINE
        )
        self.assertIsNone(
            enabled_call_pattern.search(self.run_web_source),
            "Launcher must not re-enable automatic tracker pre-seed in this step",
        )


class TestStartGamePreflightRoutingContracts(unittest.TestCase):
    """Contracts for Start Game preflight ordering and fail gate semantics."""

    @classmethod
    def setUpClass(cls):
        cls.web_interface_path = PROJECT_ROOT / "web" / "web_interface.py"
        cls.web_interface_source = cls.web_interface_path.read_text(encoding="utf-8")

    def _get_start_game_handler_section(self) -> str:
        section = self.web_interface_source.split("@socketio.on('start_game')", 1)[1]
        section = section.split("@socketio.on(", 1)[0]
        return section

    def test_preflight_runs_before_game_thread_start(self):
        """Preflight invocation must happen before thread launch."""
        section = self._get_start_game_handler_section()

        preflight_call = "preflight_result = run_start_game_module_preflight()"
        thread_launch = "threading.Thread(target=run_game_loop, daemon=True)"

        self.assertIn(preflight_call, section)
        self.assertIn(thread_launch, section)
        self.assertLess(section.find(preflight_call), section.find(thread_launch))

    def test_fail_gate_blocks_before_thread_start(self):
        """Only fail status hard-blocks startup before game thread launch."""
        section = self._get_start_game_handler_section()

        fail_gate = "if preflight_result.get('status') == 'fail':"
        emit_error = "emit('error', {'message': error_msg})"
        thread_launch = "threading.Thread(target=run_game_loop, daemon=True)"

        self.assertIn(fail_gate, section)
        self.assertIn(emit_error, section)

        fail_pos = section.find(fail_gate)
        return_pos = section.find("return", fail_pos)
        thread_pos = section.find(thread_launch)

        self.assertGreater(return_pos, fail_pos)
        self.assertGreater(thread_pos, return_pos)

    def test_pass_and_repaired_pass_are_explicitly_handled(self):
        """Pass statuses are explicit and distinct from fail-only hard gate."""
        section = self._get_start_game_handler_section()
        self.assertIn("if preflight_result.get('status') == 'pass':", section)
        self.assertIn("elif preflight_result.get('status') == 'repaired_pass':", section)


class TestStartupWizardBootstrapContracts(unittest.TestCase):
    """Contracts for startup_required bootstrap detection logic."""

    @classmethod
    def setUpClass(cls):
        cls.startup_wizard_path = PROJECT_ROOT / "utils" / "startup_wizard.py"
        cls.startup_wizard_source = cls.startup_wizard_path.read_text(encoding="utf-8")

    def test_startup_required_checks_missing_tracker(self):
        """Missing tracker data must trigger setup-required path."""
        self.assertIn("def startup_required(party_file=\"party_tracker.json\"):", self.startup_wizard_source)
        self.assertIn("party_data = safe_json_load(party_file)", self.startup_wizard_source)
        self.assertIn("if not party_data:", self.startup_wizard_source)
        self.assertIn("return True", self.startup_wizard_source)

    def test_startup_required_checks_module_party_and_primary_character(self):
        """Startup gate checks module, party members, and first character file."""
        required_snippets = [
            'module = party_data.get("module", "").strip()',
            "if not module:",
            'party_members = party_data.get("partyMembers", [])',
            "if not party_members:",
            "char_path = path_manager.get_character_unified_path(player_name)",
            "if not os.path.exists(char_path):",
        ]
        for snippet in required_snippets:
            self.assertIn(snippet, self.startup_wizard_source)

    def test_startup_required_is_fail_open_to_setup(self):
        """Unexpected errors in startup_required should still force setup path."""
        self.assertIn("except Exception:", self.startup_wizard_source)
        self.assertIn("return True  # If anything fails, assume setup needed", self.startup_wizard_source)


class TestModulePathManagerFallbackContracts(unittest.TestCase):
    """Contracts for non-fatal module resolution fallback behavior."""

    @classmethod
    def setUpClass(cls):
        cls.module_path_manager_path = PROJECT_ROOT / "utils" / "module_path_manager.py"
        cls.module_path_manager_source = cls.module_path_manager_path.read_text(encoding="utf-8")

    def test_active_module_reads_party_tracker(self):
        """ModulePathManager resolves active module from party_tracker.json."""
        self.assertIn("def _get_active_module(self):", self.module_path_manager_source)
        self.assertIn('with open("party_tracker.json", \'r\', encoding=\'utf-8\') as file:', self.module_path_manager_source)

    def test_missing_tracker_fallback_is_non_fatal(self):
        """Missing tracker falls back to Keep_of_Doom instead of hard failure."""
        self.assertIn("except Exception as e:", self.module_path_manager_source)
        self.assertIn("return \"Keep_of_Doom\"  # Default fallback", self.module_path_manager_source)


class TestAssumptionSensitivePathContracts(unittest.TestCase):
    """Contracts that mark known assumption-sensitive helper paths for follow-up."""

    @classmethod
    def setUpClass(cls):
        cls.main_path = PROJECT_ROOT / "main.py"
        cls.main_source = cls.main_path.read_text(encoding="utf-8")

        cls.adv_summary_path = PROJECT_ROOT / "core" / "ai" / "adv_summary.py"
        cls.adv_summary_source = cls.adv_summary_path.read_text(encoding="utf-8")

    def test_main_get_npc_stat_reads_tracker_then_dereferences(self):
        """Document the direct dereference assumption in get_npc_stat path."""
        self.assertIn("def get_npc_stat(", self.main_source)
        self.assertIn('party_data = load_json_file("party_tracker.json")', self.main_source)
        self.assertIn('module_name = party_data.get("module", "").replace(" ", "_")', self.main_source)

    def test_adv_summary_get_game_time_reads_tracker_then_dereferences(self):
        """Document the direct dereference assumption in adv_summary get_game_time path."""
        self.assertIn("def get_game_time():", self.adv_summary_source)
        self.assertIn('party_tracker = load_json_file("party_tracker.json")', self.adv_summary_source)
        self.assertIn('world_conditions = party_tracker.get("worldConditions", {})', self.adv_summary_source)


if __name__ == "__main__":
    unittest.main()
