#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Source-contract regression for current_location_id_note connectivity fallback."""

import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PATH = os.path.join(PROJECT_ROOT, "main.py")


class TestMainLocationConnectivityNoteFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MAIN_PATH, "r", encoding="utf-8") as handle:
            cls.main_source = handle.read()

    def test_connectivity_fallback_uses_note_scoped_location_id(self):
        self.assertIn("current_location_id_note = world_conditions[\"currentLocationId\"]", self.main_source)
        self.assertIn("loc.get(\"locationId\") == current_location_id_note", self.main_source)

    def test_connectivity_fallback_runs_even_when_location_data_missing(self):
        self.assertIn(
            'location_record_for_connectivity = location_data if isinstance(location_data, dict) else {}',
            self.main_source,
        )
        self.assertIn(
            'if isinstance(fallback_location, dict) and (not location_record_for_connectivity or not location_record_for_connectivity.get("connectivity")):',
            self.main_source,
        )

    def test_packet_adjacency_fallback_is_available_for_dm_note(self):
        self.assertIn('raw_packet_adjacency = packet_location.get("adjacent_location_ids", [])', self.main_source)
        self.assertIn('connected_locations_display_str = ", ".join(connected_names_current_area)', self.main_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
