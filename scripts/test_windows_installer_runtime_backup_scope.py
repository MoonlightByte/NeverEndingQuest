# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Installer Backup Scope Tests - Runtime-only area backup contract
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import unittest
from pathlib import Path


INSTALLER_PATH = Path(__file__).resolve().parents[1] / "install_neverendingquest_windows.bat"


class TestWindowsInstallerRuntimeBackupScope(unittest.TestCase):
    """Verifies runtime-only backup/restore does not copy canonical BU area files."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.installer_content = INSTALLER_PATH.read_text(encoding="utf-8")

    def test_create_backup_skips_area_bu_files(self) -> None:
        self.assertIn('set "AREA_NAME=%%~nA"', self.installer_content)
        self.assertIn('if /I not "!AREA_NAME:~-3!"=="_BU" (', self.installer_content)
        self.assertIn(
            'if exist "%%~fA" call :CopyFileIfExists "%%~fA" "!BACKUP_SOURCE!\\modules\\!MOD_NAME!\\areas\\%%~nxA"',
            self.installer_content,
        )

    def test_restore_runtime_state_skips_area_bu_files(self) -> None:
        self.assertIn('set "AREA_NAME=%%~nA"', self.installer_content)
        self.assertIn('if /I not "!AREA_NAME:~-3!"=="_BU" (', self.installer_content)
        self.assertIn(
            'if exist "%%~fA" copy /Y "%%~fA" "%INSTALL_DIR%\\modules\\!MOD_NAME!\\areas\\%%~nxA" >nul',
            self.installer_content,
        )


if __name__ == "__main__":
    unittest.main()
