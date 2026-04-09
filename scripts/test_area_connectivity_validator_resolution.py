#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for area connectivity resolution in module validator."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.validation.validate_module_files import ModuleValidator


class TestAreaConnectivityResolution(unittest.TestCase):
    """Cross-area links should resolve via areaConnectivityId and location names."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.module_dir = self.temp_dir / "Test_Module"
        (self.module_dir / "areas").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_area(self, area_id: str, area_name: str, location_payload: list) -> None:
        payload = {
            "areaId": area_id,
            "areaName": area_name,
            "locations": location_payload,
        }
        with open(
            self.module_dir / "areas" / f"{area_id}.json", "w", encoding="utf-8"
        ) as handle:
            json.dump(payload, handle)

    def test_resolves_area_connectivity_id_as_location_id(self):
        self._write_area(
            "A001",
            "Town A",
            [
                {
                    "locationId": "A01",
                    "name": "Town Gate",
                    "areaConnectivityId": ["B01"],
                    "areaConnectivity": [],
                }
            ],
        )
        self._write_area(
            "B001",
            "Ruins B",
            [
                {
                    "locationId": "B01",
                    "name": "Ruins Entry",
                    "areaConnectivityId": [],
                    "areaConnectivity": [],
                }
            ],
        )

        validator = ModuleValidator(str(self.module_dir), str(self.temp_dir))
        ok, errors = validator.validate_area_connectivity()
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_resolves_area_connectivity_name_as_location_name(self):
        self._write_area(
            "A001",
            "Town A",
            [
                {
                    "locationId": "A01",
                    "name": "Town Gate",
                    "areaConnectivityId": [],
                    "areaConnectivity": ["Ruins Entry"],
                }
            ],
        )
        self._write_area(
            "B001",
            "Ruins B",
            [
                {
                    "locationId": "B01",
                    "name": "Ruins Entry",
                    "areaConnectivityId": [],
                    "areaConnectivity": [],
                }
            ],
        )

        validator = ModuleValidator(str(self.module_dir), str(self.temp_dir))
        ok, errors = validator.validate_area_connectivity()
        self.assertTrue(ok)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
