#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for plot-status normalization."""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from updates.plot_update import _normalize_plot_update_sections, normalize_plot_status


class TestPlotStatusNormalization(unittest.TestCase):
    def test_resolved_normalizes_to_completed(self):
        self.assertEqual(normalize_plot_status("resolved"), "completed")

    def test_spacing_and_case_variants_normalize(self):
        self.assertEqual(normalize_plot_status("Completed"), "completed")
        self.assertEqual(normalize_plot_status("in_progress"), "in progress")
        self.assertEqual(normalize_plot_status("not-started"), "not started")

    def test_unknown_status_passthrough_remains_visible(self):
        self.assertEqual(normalize_plot_status("mystery-state"), "mystery-state")

    def test_nested_sidequest_statuses_normalize(self):
        payload = {
            "PP004": {
                "status": "resolved",
                "sideQuests": [
                    {"id": "SQ1", "status": "Completed"},
                    {"id": "SQ2", "status": "in_progress"},
                ],
            }
        }

        normalized = _normalize_plot_update_sections(payload)
        self.assertEqual(normalized["PP004"]["status"], "completed")
        self.assertEqual(normalized["PP004"]["sideQuests"][0]["status"], "completed")
        self.assertEqual(normalized["PP004"]["sideQuests"][1]["status"], "in progress")


class TestPlotStatusNormalizationSourceContract(unittest.TestCase):
    def test_action_handler_uses_plot_status_normalization(self):
        action_handler_path = os.path.join(PROJECT_ROOT, "core", "ai", "action_handler.py")
        with open(action_handler_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("normalize_plot_status(new_status)", content)
        self.assertIn("PLOT_STATUS_NORMALIZED", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
