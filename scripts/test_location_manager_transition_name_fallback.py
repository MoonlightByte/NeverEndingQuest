#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Source-contract regression for location transition name fallback."""

import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCATION_MANAGER_PATH = os.path.join(PROJECT_ROOT, "core", "managers", "location_manager.py")


class TestLocationManagerTransitionNameFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(LOCATION_MANAGER_PATH, "r", encoding="utf-8") as handle:
            cls.source = handle.read()

    def test_transition_uses_party_tracker_location_id_fallback(self):
        self.assertIn('current_location_id_from_tracker = str(party_tracker.get("worldConditions", {}).get("currentLocationId", "") or "").strip()', self.source)
        self.assertIn('location_id == current_location_id_from_tracker', self.source)

    def test_transition_accepts_source_room_title_and_room_prefix_stripped_name(self):
        self.assertIn('current_location_room_prefix_stripped = re.sub(r"^Room\\s+\\d+\\s*:\\s*", "", current_location_normalized, flags=re.IGNORECASE).strip()', self.source)
        self.assertIn('source_room_title = str(loc.get("source_room_title", "") or "").strip()', self.source)
        self.assertIn('source_room_title == current_location_normalized', self.source)
        self.assertIn('location_name == current_location_room_prefix_stripped', self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
