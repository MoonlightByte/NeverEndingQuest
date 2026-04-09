#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Tests for analyze_module_spatial_parity.py."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.analyze_module_spatial_parity import analyze_module


class TestAnalyzeModuleSpatialParity(unittest.TestCase):
    """Pre-apply parity analyzer should surface safe vs risky predictions."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.modules_dir = self.temp_dir / "modules"
        self.modules_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_module(self, module_slug: str, area_data: dict, map_data: dict) -> None:
        module_dir = self.modules_dir / module_slug
        areas_dir = module_dir / "areas"
        areas_dir.mkdir(parents=True, exist_ok=True)
        (areas_dir / "AAA001.json").write_text(json.dumps(area_data), encoding="utf-8")
        (module_dir / "map_AAA001.json").write_text(
            json.dumps(map_data), encoding="utf-8"
        )

    def test_reports_safe_apply_when_only_spatial_fields_missing(self):
        area_data = {
            "areaId": "AAA001",
            "areaName": "Area",
            "locations": [
                {
                    "locationId": "AAA01",
                    "name": "Room One",
                    "description": "Desc",
                    "connectivity": ["AAA02"],
                },
                {
                    "locationId": "AAA02",
                    "name": "Room Two",
                    "description": "Desc",
                    "connectivity": ["AAA01"],
                },
            ],
        }
        map_data = {
            "mapName": "Area",
            "mapId": "map_AAA001",
            "totalRooms": 2,
            "rooms": [
                {
                    "id": "AAA01",
                    "name": "Room One",
                    "connections": ["AAA02"],
                    "coordinates": "X0Y0",
                    "tags": ["hub"],
                },
                {
                    "id": "AAA02",
                    "name": "Room Two",
                    "connections": ["AAA01"],
                    "coordinates": "X1Y0",
                    "tags": ["dead_end"],
                },
            ],
            "layout": [["AAA01"], ["AAA02"]],
        }
        self._write_module("Safe_Module", area_data, map_data)

        with patch("scripts.analyze_module_spatial_parity.REPO_ROOT", self.temp_dir):
            report = analyze_module("Safe_Module")

        self.assertTrue(report["summary"]["overall_safe_to_apply"])
        self.assertEqual(report["summary"]["unsafe_areas"], 0)
        area_report = report["areas"][0]
        self.assertEqual(
            area_report["predicted_remediation"]["changes"]["location_connectivity"], 0
        )
        self.assertEqual(
            area_report["predicted_remediation"]["changes"]["map_layout_changed"], False
        )
        self.assertEqual(
            area_report["predicted_remediation"]["changes"][
                "map_room_metadata_keys_lost"
            ],
            0,
        )

    def test_reports_risk_when_remediation_would_change_connectivity(self):
        area_data = {
            "areaId": "AAA001",
            "areaName": "Area",
            "locations": [
                {
                    "locationId": "AAA01",
                    "name": "Room One",
                    "description": "Desc",
                },
                {
                    "locationId": "AAA02",
                    "name": "Room Two",
                    "description": "Desc",
                },
            ],
        }
        map_data = {
            "mapName": "Area",
            "mapId": "map_AAA001",
            "totalRooms": 2,
            "rooms": [
                {
                    "id": "AAA01",
                    "name": "Room One",
                    "connections": ["AAA02"],
                    "coordinates": "X0Y0",
                },
                {
                    "id": "AAA02",
                    "name": "Room Two",
                    "connections": ["AAA01"],
                    "coordinates": "X1Y0",
                },
            ],
            "layout": [["AAA01"], ["AAA02"]],
        }
        self._write_module("Risk_Module", area_data, map_data)

        with patch("scripts.analyze_module_spatial_parity.REPO_ROOT", self.temp_dir):
            report = analyze_module("Risk_Module")

        self.assertFalse(report["summary"]["overall_safe_to_apply"])
        self.assertIn("connectivity_changes", report["summary"]["risk_flags"])
        self.assertEqual(
            report["areas"][0]["predicted_remediation"]["changes"][
                "location_connectivity"
            ],
            2,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
