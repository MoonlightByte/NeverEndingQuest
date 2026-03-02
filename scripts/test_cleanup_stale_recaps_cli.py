#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for cleanup_stale_recaps CLI mode contracts."""

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "cleanup_stale_recaps.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("cleanup_stale_recaps", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestCleanupStaleRecapsCLI(unittest.TestCase):
    def test_default_mode_is_dry_run(self) -> None:
        script = _load_script_module()

        with patch.object(sys, "argv", ["cleanup_stale_recaps.py"]), \
                patch.object(script, "get_default_history_filepaths", return_value=["a.json", "b.json"]), \
                patch.object(script, "cleanup_history_files", return_value=[] ) as cleanup_mock:
            rc = script.main()

        self.assertEqual(rc, 0)
        cleanup_mock.assert_called_once_with(filepaths=["a.json", "b.json"], apply_changes=False)

    def test_apply_mode_sets_apply_changes_true(self) -> None:
        script = _load_script_module()

        with patch.object(sys, "argv", ["cleanup_stale_recaps.py", "--apply"]), \
                patch.object(script, "get_default_history_filepaths", return_value=["a.json"]), \
                patch.object(script, "cleanup_history_files", return_value=[] ) as cleanup_mock:
            rc = script.main()

        self.assertEqual(rc, 0)
        cleanup_mock.assert_called_once_with(filepaths=["a.json"], apply_changes=True)

    def test_apply_and_dry_run_are_mutually_exclusive(self) -> None:
        script = _load_script_module()

        with patch.object(sys, "argv", ["cleanup_stale_recaps.py", "--apply", "--dry-run"]):
            with self.assertRaises(SystemExit) as ctx:
                script.main()

        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
