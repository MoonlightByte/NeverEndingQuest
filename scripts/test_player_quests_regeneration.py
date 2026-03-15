#!/usr/bin/env python3
"""Regression tests for derived player_quests regeneration contract (Step 3.3)."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.quest_player_formatter import ensure_player_quests_file
from web.extensions.tabletop_socket_handlers import handle_plot_data_request_impl


class TestEnsurePlayerQuestsFile(unittest.TestCase):
    """Behavior tests for derived player_quests file creation contract."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="player_quests_regen_")
        self.previous_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        os.chdir(self.previous_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def test_missing_player_quests_is_regenerated_from_plot(self):
        module_dir = Path("modules") / "TestModule"
        plot_path = module_dir / "module_plot.json"
        self._write_json(
            plot_path,
            {
                "plotPoints": [
                    {
                        "id": "PP001",
                        "title": "Find the tower",
                        "description": "Travel to the old tower.",
                        "status": "not started",
                        "sideQuests": [],
                    }
                ]
            },
        )

        result = ensure_player_quests_file("TestModule")

        self.assertEqual(result["status"], "regenerated")
        player_quests_path = Path(result["path"])
        self.assertTrue(player_quests_path.exists())

        data = json.loads(player_quests_path.read_text(encoding="utf-8"))
        self.assertEqual(data.get("module"), "TestModule")
        self.assertIn("PP001", data.get("quests", {}))

    def test_existing_player_quests_is_preserved(self):
        module_dir = Path("modules") / "TestModule"
        existing_path = module_dir / "player_quests_TestModule.json"
        self._write_json(existing_path, {"module": "TestModule", "quests": {}})

        result = ensure_player_quests_file("TestModule")

        self.assertEqual(result["status"], "exists")
        self.assertEqual(Path(result["path"]), existing_path)

    def test_missing_plot_yields_failed_status(self):
        result = ensure_player_quests_file("TestModule")
        self.assertEqual(result["status"], "failed")


class TestPlotDataRequestRegenerationFallback(unittest.TestCase):
    """Socket handler tests for regeneration and fail-open fallback behavior."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="plot_data_req_")
        self.previous_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        self.module_name = "TestModule"
        self.module_dir = Path("modules") / self.module_name
        self.module_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(
            Path("party_tracker.json"),
            {
                "module": self.module_name,
                "partyMembers": ["Hero"],
                "active_character": "Hero",
                "worldConditions": {},
            },
        )

        self.plot_payload = {
            "plotPoints": [
                {
                    "id": "PP001",
                    "title": "Original Title",
                    "description": "Original plot description.",
                    "status": "in progress",
                    "sideQuests": [],
                }
            ]
        }
        self._write_json(self.module_dir / "module_plot.json", self.plot_payload)

        self.emits = []
        self.debug_messages = []

    def tearDown(self):
        os.chdir(self.previous_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _emit(self, event, payload):
        self.emits.append((event, payload))

    def _debug(self, message, category=None):
        self.debug_messages.append((message, category))

    def _latest_plot_payload(self):
        for event, payload in reversed(self.emits):
            if event == "plot_data_response":
                return payload
        return None

    def test_missing_player_quests_regenerates_and_serves_player_payload(self):
        handle_plot_data_request_impl(self._emit, self._debug)

        output = self._latest_plot_payload()
        self.assertIsNotNone(output)
        self.assertIsNone(output.get("error"))

        plot_points = output.get("data", {}).get("plotPoints", [])
        self.assertEqual(len(plot_points), 1)
        self.assertEqual(plot_points[0].get("description"), "Original plot description.")

        player_quests_path = self.module_dir / f"player_quests_{self.module_name}.json"
        self.assertTrue(player_quests_path.exists())

    def test_existing_player_quests_is_used_without_regeneration(self):
        self._write_json(
            self.module_dir / f"player_quests_{self.module_name}.json",
            {
                "module": self.module_name,
                "quests": {
                    "PP001": {
                        "id": "PP001",
                        "title": "Friendly Title",
                        "playerDescription": "Friendly quest text.",
                        "originalDescription": "Original plot description.",
                        "status": "in progress",
                        "type": "main",
                        "sideQuests": {},
                    }
                },
            },
        )

        handle_plot_data_request_impl(self._emit, self._debug)
        output = self._latest_plot_payload()
        plot_points = output.get("data", {}).get("plotPoints", [])
        self.assertEqual(plot_points[0].get("description"), "Friendly quest text.")

    def test_failed_regeneration_falls_back_to_original_plot_data(self):
        with patch(
            "utils.quest_player_formatter.ensure_player_quests_file",
            return_value={
                "status": "failed",
                "path": str(self.module_dir / f"player_quests_{self.module_name}.json"),
            },
        ):
            handle_plot_data_request_impl(self._emit, self._debug)

        output = self._latest_plot_payload()
        self.assertIsNotNone(output)
        self.assertIsNone(output.get("error"))

        plot_points = output.get("data", {}).get("plotPoints", [])
        self.assertEqual(plot_points[0].get("description"), "Original plot description.")

    def test_invalid_player_quests_json_falls_back_to_original_plot_data(self):
        player_quests_path = self.module_dir / f"player_quests_{self.module_name}.json"
        player_quests_path.write_text("{not-valid-json", encoding="utf-8")

        handle_plot_data_request_impl(self._emit, self._debug)

        output = self._latest_plot_payload()
        self.assertIsNotNone(output)
        self.assertIsNone(output.get("error"))

        plot_points = output.get("data", {}).get("plotPoints", [])
        self.assertEqual(plot_points[0].get("description"), "Original plot description.")


if __name__ == "__main__":
    unittest.main()
