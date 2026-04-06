# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit module post-build publication parity."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web.extensions.toolkit_module_finisher as finisher


class TestToolkitModuleFinisher(unittest.TestCase):
    """Verify finisher status mapping and report persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.original_cwd = Path.cwd()
        os.chdir(self.repo_root)

        self.module_slug = "Parity_Test_Module"
        self.module_dir = self.repo_root / "modules" / self.module_slug
        self.module_dir.mkdir(parents=True, exist_ok=True)
        (self.module_dir / "module_context.json").write_text("{}", encoding="utf-8")
        (self.module_dir / "module_plot.json").write_text("{}", encoding="utf-8")

        self.original_continuity = finisher._run_continuity_stage
        self.original_registry = finisher._run_registry_stage
        self.original_materialization = finisher._run_monster_materialization_stage

    def tearDown(self) -> None:
        finisher._run_continuity_stage = self.original_continuity
        finisher._run_registry_stage = self.original_registry
        finisher._run_monster_materialization_stage = self.original_materialization

        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_finisher_success_writes_report(self) -> None:
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success", "stage": "continuity"}
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success", "stage": "registry"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {"status": "success", "stage": "monster_materialization"}

        result = finisher.run_toolkit_module_postbuild_finishing(self.module_slug, strict=True)

        self.assertEqual(result.get("status"), "success")
        report_path = Path(result.get("report_path", ""))
        self.assertTrue(report_path.exists())

        report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report_payload.get("status"), "success")
        self.assertIn("publication_parity_note", report_payload)

    def test_finisher_degraded_maps_status(self) -> None:
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {"status": "degraded", "reason": "missing bestiary entries"}

        result = finisher.run_toolkit_module_postbuild_finishing(self.module_slug, strict=True)
        self.assertEqual(result.get("status"), "degraded")

    def test_finisher_failed_registry_maps_failed(self) -> None:
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "failed", "reason": "registry missing"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {"status": "success"}

        result = finisher.run_toolkit_module_postbuild_finishing(self.module_slug, strict=True)
        self.assertEqual(result.get("status"), "failed")
        self.assertEqual((result.get("stages") or {}).get("registry", {}).get("reason"), "registry missing")


class TestToolkitPublicationParitySourceContracts(unittest.TestCase):
    """Source-level contracts for web handler and toolkit UI integration."""

    def test_web_interface_invokes_finisher_and_reports_status(self) -> None:
        source = Path("web/web_interface.py").read_text(encoding="utf-8")

        self.assertIn("run_toolkit_module_postbuild_finishing", source)
        self.assertIn("stage_name': 'Post Build Finishing'", source)
        self.assertIn("generation_succeeded", source)
        self.assertIn("publication_parity_note", source)

    def test_toolkit_template_exposes_finishing_stage_and_parity_note(self) -> None:
        source = Path("web/templates/module_toolkit.html").read_text(encoding="utf-8")

        self.assertIn("Post-Build Finishing", source)
        self.assertIn("publication_parity_note", source)
        self.assertIn("Post-Build Status", source)


if __name__ == "__main__":
    unittest.main()
