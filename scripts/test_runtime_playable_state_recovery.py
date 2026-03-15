#!/usr/bin/env python3
"""Step 3.4 runtime playable-state recovery verification tests."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.runtime_hydration import (
    hydrate_missing_live_area_files_from_bu,
    hydrate_missing_module_plot_files_from_bu,
)
from utils.reset_campaign import reset_module, reset_global_state
from web.extensions.tabletop_socket_handlers import handle_plot_data_request_impl

try:
    from utils import startup_wizard
    STARTUP_WIZARD_AVAILABLE = True
except Exception:
    startup_wizard = None
    STARTUP_WIZARD_AVAILABLE = False


class TestRuntimePlayableStateRecovery(unittest.TestCase):
    """Verifies startup/reset recovery leaves runtime in playable state."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="runtime_playable_state_")
        self.previous_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        os.chdir(self.previous_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _latest_plot_payload(self, emits):
        for event, payload in reversed(emits):
            if event == "plot_data_response":
                return payload
        return None

    def test_startup_style_recovery_restores_missing_live_files_and_serves_plot(self):
        """Missing area/plot files recover from BU and plot request remains functional."""
        module_name = "TestModule"
        module_dir = Path("modules") / module_name

        self._write_json(
            module_dir / "areas" / "A001_BU.json",
            {
                "areaId": "A001",
                "areaName": "Area One",
                "locations": [],
            },
        )
        self._write_json(
            module_dir / "module_plot_BU.json",
            {
                "plotTitle": "Test Plot",
                "plotPoints": [
                    {
                        "id": "PP001",
                        "title": "Recover the relic",
                        "description": "Find the relic in the crypt.",
                        "status": "not started",
                        "sideQuests": [],
                    }
                ],
            },
        )

        area_result = hydrate_missing_live_area_files_from_bu("modules")
        plot_result = hydrate_missing_module_plot_files_from_bu("modules")

        self.assertEqual(area_result["restored"], 1)
        self.assertEqual(plot_result["restored"], 1)
        self.assertTrue((module_dir / "areas" / "A001.json").exists())
        self.assertTrue((module_dir / "module_plot.json").exists())

        self._write_json(
            Path("party_tracker.json"),
            {
                "module": module_name,
                "partyMembers": ["Hero"],
                "active_character": "Hero",
                "worldConditions": {},
            },
        )

        emits = []

        def emit_fn(event, payload):
            emits.append((event, payload))

        def debug_fn(message, category=None):
            _ = (message, category)

        handle_plot_data_request_impl(emit_fn, debug_fn)

        payload = self._latest_plot_payload(emits)
        self.assertIsNotNone(payload)
        self.assertIsNone(payload.get("error"))
        self.assertGreater(len(payload.get("data", {}).get("plotPoints", [])), 0)

        player_quests_path = module_dir / f"player_quests_{module_name}.json"
        self.assertTrue(player_quests_path.exists())

    def test_reset_module_restores_area_and_plot_from_backups(self):
        """Reset module restores both area and module_plot from BU sources."""
        module_name = "TestModule"
        module_dir = Path("modules") / module_name

        self._write_json(module_dir / "areas" / "A001_BU.json", {"areaId": "A001", "name": "From Backup"})
        self._write_json(module_dir / "areas" / "A001.json", {"areaId": "A001", "name": "Mutated Live"})

        self._write_json(module_dir / "module_plot_BU.json", {"plotTitle": "Backup Plot", "plotPoints": []})
        self._write_json(module_dir / "module_plot.json", {"plotTitle": "Mutated Plot", "plotPoints": []})

        with redirect_stdout(io.StringIO()):
            reset_module(module_name)

        self.assertEqual(
            (module_dir / "areas" / "A001.json").read_text(encoding="utf-8"),
            (module_dir / "areas" / "A001_BU.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            (module_dir / "module_plot.json").read_text(encoding="utf-8"),
            (module_dir / "module_plot_BU.json").read_text(encoding="utf-8"),
        )

    def test_reset_global_state_keeps_startup_bootstrap_path_available(self):
        """Reset global state keeps first-run startup path available."""
        Path("modules").mkdir(parents=True, exist_ok=True)

        with redirect_stdout(io.StringIO()):
            reset_global_state()

        self.assertTrue(Path("party_tracker.json").exists())
        self.assertEqual(json.loads(Path("party_tracker.json").read_text(encoding="utf-8")), {})
        self.assertTrue(Path("current_location.json").exists())
        self.assertTrue(Path("journal.json").exists())

        if STARTUP_WIZARD_AVAILABLE:
            self.assertTrue(startup_wizard.startup_required("party_tracker.json"))


if __name__ == "__main__":
    unittest.main()
