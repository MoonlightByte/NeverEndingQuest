# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Tests - Module Runtime Progression Validation
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Regression and contract tests for runtime room reachability, map/area parity,
plot progression validation, and canonical CLI execution path parity.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.validation.validate_module_files import ModuleValidator


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR_PATH = REPO_ROOT / "core" / "validation" / "validate_module_files.py"


def _jsonschema_available() -> bool:
    """Return True when jsonschema dependency is available."""
    try:
        import jsonschema  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_jsonschema_available(), "jsonschema required for validator runtime tests")
class TestModuleRuntimeProgressionValidation(unittest.TestCase):
    """Contract tests for module-runtime-progression-validation."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.module_dir = self.temp_dir / "Runtime_Validation_Test_Module"
        self.module_dir.mkdir(parents=True, exist_ok=True)
        (self.module_dir / "areas").mkdir(exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _write_json(self, relative_path: str, payload: dict) -> Path:
        """Write a JSON fixture file under the temp module."""
        target = self.module_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return target

    def _build_area_payload(self, area_id: str, locations: list) -> dict:
        return {
            "areaId": area_id,
            "areaName": f"{area_id} Area",
            "areaDescription": "Test area",
            "locations": locations,
        }

    def _build_map_payload(self, area_id: str, rooms: list) -> dict:
        return {
            "mapName": f"Map {area_id}",
            "mapId": f"map_{area_id}",
            "totalRooms": len(rooms),
            "rooms": rooms,
            "layout": [[room["id"]] for room in rooms],
        }

    def _build_plot_payload(self, plot_points: list, branch_metadata: dict = None) -> dict:
        payload = {
            "plotTitle": "Test Plot",
            "mainObjective": "Test objective",
            "plotPoints": plot_points,
        }
        if branch_metadata is not None:
            payload["branch_metadata"] = branch_metadata
        return payload

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        """Run validator CLI against temp fixtures."""
        command = [sys.executable, str(VALIDATOR_PATH)]
        command.extend(args)
        return subprocess.run(command, capture_output=True, text=True)

    def test_cli_human_and_json_modes_run_same_validation_suite(self):
        """Human and --json modes must execute identical validation domains."""
        self._write_json(
            "areas/TST001.json",
            self._build_area_payload(
                "TST001",
                [
                    {
                        "locationId": "A01",
                        "name": "Start",
                        "description": "Start room",
                        "connectivity": ["A02"],
                    },
                    {
                        "locationId": "A02",
                        "name": "Middle",
                        "description": "Middle room",
                        "connectivity": ["A01"],
                    },
                    {
                        "locationId": "A03",
                        "name": "Isolated",
                        "description": "Isolated room",
                        "connectivity": [],
                    },
                ],
            ),
        )
        self._write_json(
            "map_TST001.json",
            self._build_map_payload(
                "TST001",
                [
                    {"id": "A01", "name": "Start", "connections": ["A02"], "coordinates": "X0Y0"},
                    {"id": "A02", "name": "Middle", "connections": [], "coordinates": "X1Y0"},
                    {"id": "A03", "name": "Isolated", "connections": [], "coordinates": "X2Y0"},
                ],
            ),
        )
        self._write_json(
            "module_plot.json",
            self._build_plot_payload(
                [
                    {
                        "id": "PP001",
                        "title": "Start Beat",
                        "description": "Start",
                        "location": "A01",
                        "nextPoints": ["PP002"],
                        "status": "not started",
                        "plotImpact": "None",
                    },
                    {
                        "id": "PP002",
                        "title": "Unreachable Beat",
                        "description": "Broken progression",
                        "location": "A03",
                        "nextPoints": ["PP003"],
                        "status": "not started",
                        "plotImpact": "None",
                    },
                    {
                        "id": "PP003",
                        "title": "Conclusion",
                        "description": "Final beat without gate",
                        "location": "A02",
                        "nextPoints": [],
                        "status": "not started",
                        "plotImpact": "Finale room progression",
                    },
                ],
                branch_metadata={
                    "investigation_routes": [
                        {
                            "id": "broken_route",
                            "path": ["A01", "A03"],
                        }
                    ]
                },
            ),
        )

        human = self._run_cli("--module-path", str(self.module_dir))
        self.assertEqual(human.returncode, 1)

        report_path = self.module_dir / "validation_report.json"
        self.assertTrue(report_path.exists(), "human mode should write validation_report.json")
        human_payload = json.loads(report_path.read_text(encoding="utf-8"))
        human_results = human_payload["results"]

        machine = self._run_cli("--module-path", str(self.module_dir), "--json")
        self.assertEqual(machine.returncode, 1)
        machine_payload = json.loads(machine.stdout)
        module_results = machine_payload["modules"][self.module_dir.name]["files"]

        required_domains = [
            "runtime_room_reachability",
            "map_area_parity",
            "plot_progression",
            "connectivity",
        ]
        for domain in required_domains:
            self.assertIn(domain, human_results)
            self.assertIn(domain, module_results)
            self.assertEqual(
                human_results[domain]["failed"],
                module_results[domain]["failed"],
                f"domain mismatch for {domain}",
            )

    def test_single_area_missing_connectivity_fails_runtime_reachability(self):
        """Single-area modules must fail when runtime connectivity does not traverse rooms."""
        self._write_json(
            "areas/TST001.json",
            self._build_area_payload(
                "TST001",
                [
                    {
                        "locationId": "R01",
                        "name": "Entry",
                        "description": "Entry room",
                        "connectivity": [],
                    },
                    {
                        "locationId": "R02",
                        "name": "Sealed",
                        "description": "Disconnected room",
                        "connectivity": [],
                    },
                ],
            ),
        )

        validator = ModuleValidator(self.module_dir, REPO_ROOT)
        validator.execute_full_validation(verbose=False)

        runtime_result = validator.results["runtime_room_reachability"]
        self.assertGreater(runtime_result["failed"], 0)
        joined_errors = "\n".join(runtime_result["errors"])
        self.assertIn("areas/TST001.json", joined_errors)
        self.assertIn("R02", joined_errors)

    def test_map_area_parity_drift_is_rejected_with_room_ids(self):
        """Area/map room-graph parity drift should fail with deterministic diagnostics."""
        self._write_json(
            "areas/TST001.json",
            self._build_area_payload(
                "TST001",
                [
                    {
                        "locationId": "R01",
                        "name": "Entry",
                        "description": "Entry room",
                        "connectivity": ["R02"],
                    },
                    {
                        "locationId": "R02",
                        "name": "Hall",
                        "description": "Hall room",
                        "connectivity": ["R01"],
                    },
                ],
            ),
        )
        self._write_json(
            "map_TST001.json",
            self._build_map_payload(
                "TST001",
                [
                    {"id": "R01", "name": "Entry", "connections": ["R02"], "coordinates": "X0Y0"},
                    {"id": "R02", "name": "Hall", "connections": [], "coordinates": "X1Y0"},
                ],
            ),
        )

        validator = ModuleValidator(self.module_dir, REPO_ROOT)
        validator.execute_full_validation(verbose=False)

        parity_result = validator.results["map_area_parity"]
        self.assertGreater(parity_result["failed"], 0)
        joined_errors = "\n".join(parity_result["errors"])
        self.assertIn("areas/TST001.json", joined_errors)
        self.assertIn("map_TST001.json", joined_errors)
        self.assertIn("R02", joined_errors)

    def test_plot_progression_rejects_unreachable_branch_breaks_and_ungated_conclusion(self):
        """Plot progression validator should catch unreachable beats, broken paths, and ungated conclusions."""
        self._write_json(
            "areas/TST001.json",
            self._build_area_payload(
                "TST001",
                [
                    {
                        "locationId": "A01",
                        "name": "Start",
                        "description": "Start room",
                        "connectivity": ["A02"],
                    },
                    {
                        "locationId": "A02",
                        "name": "Hub",
                        "description": "Hub room",
                        "connectivity": ["A01"],
                    },
                    {
                        "locationId": "A03",
                        "name": "Locked",
                        "description": "Disconnected room",
                        "connectivity": [],
                    },
                ],
            ),
        )
        self._write_json(
            "map_TST001.json",
            self._build_map_payload(
                "TST001",
                [
                    {"id": "A01", "name": "Start", "connections": ["A02"], "coordinates": "X0Y0"},
                    {"id": "A02", "name": "Hub", "connections": ["A01"], "coordinates": "X1Y0"},
                    {"id": "A03", "name": "Locked", "connections": [], "coordinates": "X2Y0"},
                ],
            ),
        )
        self._write_json(
            "module_plot.json",
            self._build_plot_payload(
                [
                    {
                        "id": "PP001",
                        "title": "Opening",
                        "description": "Start beat",
                        "location": "A01",
                        "nextPoints": ["PP002"],
                        "status": "not started",
                        "plotImpact": "None",
                    },
                    {
                        "id": "PP002",
                        "title": "Detour",
                        "description": "Should not be reachable",
                        "location": "A03",
                        "nextPoints": ["PP003"],
                        "status": "not started",
                        "plotImpact": "None",
                    },
                    {
                        "id": "PP003",
                        "title": "Finale Chamber",
                        "description": "Ungated ending beat",
                        "location": "A02",
                        "nextPoints": [],
                        "status": "not started",
                        "plotImpact": "Finale beat",
                    },
                ],
                branch_metadata={
                    "routes": [
                        {
                            "id": "branch_a",
                            "path": ["A01", "A03"],
                            "bypass": ["A02", "A03"],
                        }
                    ]
                },
            ),
        )

        validator = ModuleValidator(self.module_dir, REPO_ROOT)
        validator.execute_full_validation(verbose=False)

        progression_result = validator.results["plot_progression"]
        self.assertGreater(progression_result["failed"], 0)
        joined_errors = "\n".join(progression_result["errors"])
        self.assertIn("plot PP002 location A03 unreachable from start A01", joined_errors)
        self.assertIn("broken step A01 -> A03", joined_errors)
        self.assertIn("missing explicit prerequisite gate", joined_errors)


if __name__ == "__main__":
    unittest.main()
