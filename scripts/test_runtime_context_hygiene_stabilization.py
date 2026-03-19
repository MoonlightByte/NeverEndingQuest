#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for runtime context hygiene stabilization."""

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.location_context_hygiene import (
    build_location_provenance_line,
    inject_location_provenance,
    is_derived_location_context_message,
    parse_location_provenance,
)


class TestLocationContextHygieneHelpers(unittest.TestCase):
    def test_summary_block_is_recognized_as_derived_location_context(self):
        msg = {
            "role": "assistant",
            "content": "[SUMMARY OF EVENTS AT THIS LOCATION]\n\nThe following is a summary of your party's activities at the current location (TW05) up to this point:\n\nBandits...",
        }
        self.assertTrue(is_derived_location_context_message(msg))

    def test_injected_provenance_round_trips(self):
        content = "=== LOCATION SUMMARY ===\n\nBandit Stronghold (TW05):\n---\nText"
        tagged = inject_location_provenance(content, "The_Thornwood_Watch", "TW001", "TW05", "location_summary")
        parsed = parse_location_provenance(tagged)
        self.assertEqual(parsed["module"], "The_Thornwood_Watch")
        self.assertEqual(parsed["area"], "TW001")
        self.assertEqual(parsed["location"], "TW05")
        self.assertEqual(parsed["kind"], "location_summary")


class TestCampaignManagerModuleScanQuarantine(unittest.TestCase):
    def test_campaign_manager_scans_for_new_modules_only_once_per_process(self):
        from core.managers.campaign_manager import CampaignManager

        original_flag = CampaignManager._module_scan_attempted
        CampaignManager._module_scan_attempted = False
        try:
            with patch("core.managers.campaign_manager.OpenAI"), \
                 patch.object(CampaignManager, "_scan_for_new_modules") as mock_scan:
                CampaignManager()
                CampaignManager()
            self.assertEqual(mock_scan.call_count, 1)
        finally:
            CampaignManager._module_scan_attempted = original_flag


class TestSourceContracts(unittest.TestCase):
    def _read(self, relative_path):
        file_path = os.path.join(PROJECT_ROOT, relative_path)
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_main_sanitizer_filters_derived_location_context(self):
        source = self._read("main.py")
        self.assertIn("is_derived_location_context_message", source)
        self.assertIn("derived_context_matches_scene", source)
        self.assertIn("even matching derived location summaries remain excluded", source)

    def test_reconciler_skips_derived_location_context_blocks(self):
        source = self._read("utils/reconcile_location_state.py")
        self.assertIn("is_derived_location_context_message", source)
        self.assertIn("Skipping derived location context block", source)

    def test_incremental_summary_emits_provenance(self):
        source = self._read("core/ai/incremental_compression.py")
        self.assertIn("inject_location_provenance", source)
        self.assertIn('"location_summary"', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
