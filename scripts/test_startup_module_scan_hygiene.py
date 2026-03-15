# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Startup wizard module-scan hygiene tests.

Validates that non-module runtime/system directories under modules/ are
excluded before ModuleStitcher analysis, preventing false startup warnings.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils import startup_wizard
    STARTUP_WIZARD_AVAILABLE = True
    STARTUP_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    startup_wizard = None
    STARTUP_WIZARD_AVAILABLE = False
    STARTUP_IMPORT_ERROR = exc


class TestStartupModuleScanHygiene(unittest.TestCase):
    """Focused tests for startup module scan candidate filtering."""

    def setUp(self):
        if not STARTUP_WIZARD_AVAILABLE:
            self.skipTest(f"startup_wizard unavailable: {STARTUP_IMPORT_ERROR}")

    def test_scan_skips_non_module_directories_before_analysis(self):
        """Only real module directories with areas/ should be analyzed."""
        directory_listing = [
            "backups",
            "conversation_history",
            "logs",
            "Real_Module",
            ".hidden_dir",
        ]

        def isdir_side_effect(path: str) -> bool:
            if path == "modules/Real_Module/areas":
                return True
            if path.startswith("modules/"):
                return True
            return False

        mock_stitcher = MagicMock()
        mock_stitcher.analyze_module.return_value = {
            "areas": {
                "A001": {
                    "recommendedLevel": 2,
                }
            }
        }

        with patch("utils.startup_wizard.os.path.exists", return_value=True), \
             patch("utils.startup_wizard.os.listdir", return_value=directory_listing), \
             patch("utils.startup_wizard.os.path.isdir", side_effect=isdir_side_effect), \
             patch.object(startup_wizard, "ModuleStitcher", return_value=mock_stitcher), \
             patch.object(startup_wizard, "status_loading"), \
             patch.object(startup_wizard, "status_ready"):
            modules = startup_wizard.scan_available_modules()

        self.assertEqual(mock_stitcher.analyze_module.call_args_list, [call("Real_Module")])
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["name"], "Real_Module")

    def test_scan_ignores_directories_without_areas(self):
        """Directories missing areas/ are ignored before analyze_module()."""
        directory_listing = ["CandidateWithoutAreas"]

        def isdir_side_effect(path: str) -> bool:
            if path == "modules/CandidateWithoutAreas/areas":
                return False
            if path == "modules/CandidateWithoutAreas":
                return True
            return False

        mock_stitcher = MagicMock()
        mock_stitcher.analyze_module.return_value = {
            "areas": {"A001": {"recommendedLevel": 1}}
        }

        with patch("utils.startup_wizard.os.path.exists", return_value=True), \
             patch("utils.startup_wizard.os.listdir", return_value=directory_listing), \
             patch("utils.startup_wizard.os.path.isdir", side_effect=isdir_side_effect), \
             patch.object(startup_wizard, "ModuleStitcher", return_value=mock_stitcher), \
             patch.object(startup_wizard, "status_loading"), \
             patch.object(startup_wizard, "status_ready"):
            modules = startup_wizard.scan_available_modules()

        mock_stitcher.analyze_module.assert_not_called()
        self.assertEqual(modules, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
