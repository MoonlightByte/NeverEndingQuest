#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression checks for Night of the Restless Dead module semantics."""

import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

MODULE_ROOT = os.path.join(PROJECT_ROOT, "modules", "Night_of_the_Restless_Dead")


def _load_json(*parts):
    path = os.path.join(MODULE_ROOT, *parts)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


class TestRestlessDeadModuleSemantics(unittest.TestCase):
    def test_location_names_drop_room_prefixes(self):
        area_data = _load_json("areas", "NIG001.json")
        location_names = [location.get("name", "") for location in area_data.get("locations", [])]

        for name in location_names:
            self.assertFalse(name.startswith("Room "), f"Unexpected room prefix in location name: {name}")

    def test_lintar_location_exists_between_inn_and_cathedral(self):
        area_data = _load_json("areas", "NIG001.json")
        location_by_id = {location.get("locationId"): location for location in area_data.get("locations", [])}

        lintar_location = location_by_id.get("NIG08")
        self.assertIsNotNone(lintar_location)
        self.assertEqual(lintar_location.get("name"), "Brother Lintar's Place")
        self.assertEqual(lintar_location.get("connectivity"), ["NIG01", "NIG02"])

        ma_connectivity = location_by_id.get("NIG01", {}).get("connectivity", [])
        hall_connectivity = location_by_id.get("NIG02", {}).get("connectivity", [])
        self.assertIn("NIG08", ma_connectivity)
        self.assertIn("NIG08", hall_connectivity)

    def test_lintar_and_core_npcs_are_bound_to_module_context(self):
        context = _load_json("module_context.json")
        npcs = context.get("npcs", {})
        self.assertIn("brother_lintar", npcs)
        self.assertIn("father_aldric", npcs)
        self.assertIn("ma_thornfield", npcs)
        self.assertEqual(npcs["brother_lintar"]["name"], "Brother Lintar")

    def test_user_facing_module_strings_drop_underscores(self):
        context = _load_json("module_context.json")
        plot = _load_json("module_plot.json")
        area = _load_json("areas", "NIG001.json")
        module_name = context.get("module_name", "")
        plot_title = plot.get("plotTitle", "")
        area_name = area.get("areaName", "")

        self.assertNotIn("Night_of_the_Restless_Dead", module_name)
        self.assertNotIn("Night_of_the_Restless_Dead", plot_title)
        self.assertNotIn("Night_of_the_Restless_Dead", area_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
