#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Source-contract regression for adv_summary location name fallback."""

import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADV_SUMMARY_PATH = os.path.join(PROJECT_ROOT, "core", "ai", "adv_summary.py")


class TestAdvSummaryLocationNameFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(ADV_SUMMARY_PATH, "r", encoding="utf-8") as handle:
            cls.source = handle.read()

    def test_cli_argument_normalizes_legacy_room_prefix(self):
        self.assertIn('leaving_location_name_arg = _normalize_display_location_name(sys.argv[3])', self.source)

    def test_area_lookup_accepts_name_prefix_normalization_and_source_room_title(self):
        self.assertIn('_normalize_display_location_name(loc.get("name", "")) == leaving_location_name_arg', self.source)
        self.assertIn('loc.get("source_room_title") == leaving_location_name_arg', self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
