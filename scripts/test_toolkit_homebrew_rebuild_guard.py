# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew rebuild guard helpers."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.extensions.toolkit_homebrew_rebuild_guard import (
    detect_module_collision,
    prepare_backup_clean_rebuild,
)


class TestToolkitHomebrewRebuildGuard(unittest.TestCase):
    """Verify backup+clean rebuild guard behavior is fail-closed."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = Path.cwd()
        os.chdir(self.temp_dir.name)
        Path("modules").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def _create_module(self, module_name: str) -> Path:
        module_dir = Path("modules") / module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "module_context.json").write_text('{"name":"test"}', encoding="utf-8")
        return module_dir

    def test_detect_module_collision_reports_absent_directory(self) -> None:
        result = detect_module_collision("Missing_Module")
        self.assertEqual(result.get("status"), "success")
        self.assertFalse(result.get("module_dir_exists"))

    def test_detect_module_collision_reports_existing_directory(self) -> None:
        self._create_module("Existing_Module")
        result = detect_module_collision("Existing_Module")
        self.assertEqual(result.get("status"), "success")
        self.assertTrue(result.get("module_dir_exists"))

    def test_prepare_backup_clean_rebuild_rejects_unsupported_policy(self) -> None:
        result = prepare_backup_clean_rebuild("Any_Module", overwrite_policy="delete_only")
        self.assertEqual(result.get("status"), "rebuild_prepare_failed")
        self.assertEqual(result.get("reason"), "unsupported_overwrite_policy")

    def test_prepare_backup_clean_rebuild_noop_when_module_missing(self) -> None:
        result = prepare_backup_clean_rebuild("Missing_Module", overwrite_policy="backup_clean")
        self.assertEqual(result.get("status"), "success")
        self.assertFalse(result.get("rebuild_mode"))
        self.assertEqual(result.get("reason"), "module_directory_not_present")

    def test_prepare_backup_clean_rebuild_success_creates_backup_and_cleans_target(self) -> None:
        module_dir = self._create_module("Rebuild_Target")
        result = prepare_backup_clean_rebuild("Rebuild_Target", overwrite_policy="backup_clean")
        self.assertEqual(result.get("status"), "success")
        self.assertTrue(result.get("rebuild_mode"))

        backup_dir = Path(str(result.get("backup_dir") or ""))
        self.assertTrue(backup_dir.exists())
        self.assertFalse(module_dir.exists())
        self.assertTrue((backup_dir / "module_context.json").exists())

    def test_prepare_backup_clean_rebuild_backup_failure_is_fail_closed(self) -> None:
        self._create_module("Backup_Fail")
        with patch("web.extensions.toolkit_homebrew_rebuild_guard.shutil.copytree", side_effect=RuntimeError("copy failed")):
            result = prepare_backup_clean_rebuild("Backup_Fail", overwrite_policy="backup_clean")

        self.assertEqual(result.get("status"), "rebuild_backup_failed")
        self.assertEqual(result.get("reason"), "backup_creation_failed")
        self.assertTrue((Path("modules") / "Backup_Fail").exists())

    def test_prepare_backup_clean_rebuild_cleanup_failure_is_fail_closed(self) -> None:
        self._create_module("Cleanup_Fail")
        with patch("web.extensions.toolkit_homebrew_rebuild_guard.shutil.rmtree", side_effect=RuntimeError("cleanup failed")):
            result = prepare_backup_clean_rebuild("Cleanup_Fail", overwrite_policy="backup_clean")

        self.assertEqual(result.get("status"), "rebuild_prepare_failed")
        self.assertEqual(result.get("reason"), "cleanup_failed_after_backup")
        self.assertTrue((Path("modules") / "Cleanup_Fail").exists())


if __name__ == "__main__":
    unittest.main()
