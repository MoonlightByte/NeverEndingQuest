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
        self.assertIn("and current_location_id_note", self.main_source)
        self.assertIn("loc.get(\"locationId\") == current_location_id_note", self.main_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
