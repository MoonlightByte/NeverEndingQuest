#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Targeted regression tests for GUI builder sidebar audit failure signals.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.generators.module_stitcher import ModuleStitcher


def _write_json(file_path: Path, payload: Dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


class ModuleSidebarAuditFailureSignalsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.modules_dir = self.tmp_path / "modules"
        self.modules_dir.mkdir(parents=True, exist_ok=True)

        self.stitcher = ModuleStitcher.__new__(ModuleStitcher)
        self.stitcher.modules_dir = str(self.modules_dir)
        self.stitcher.root_dir = str(self.tmp_path)
        self.stitcher.world_registry_file = str(self.modules_dir / "world_registry.json")
        self.stitcher.party_tracker_file = str(self.tmp_path / "party_tracker.json")
        self.stitcher.world_registry = {
            "modules": {
                "Murder_at_the_Drowning_Lass": {
                    "plotObjective": "Find the killer",
                    "levelRange": {"min": 3, "max": 5},
                    "themes": ["mystery"],
                    "addedDate": "2026-04-20",
                },
                "The_Ancients_Lab": {
                    "plotObjective": "Explore the lab",
                    "levelRange": {"min": 5, "max": 8},
                    "themes": ["horror"],
                    "addedDate": "2026-04-21",
                },
                "Semantic_Only_Module": {
                    "plotObjective": "Semantic issues only",
                    "levelRange": {"min": 2, "max": 3},
                    "themes": ["investigation"],
                    "addedDate": "2026-04-22",
                },
                "No_Report_Module": {
                    "plotObjective": "No report file",
                    "levelRange": {"min": 1, "max": 2},
                    "themes": ["fallback"],
                    "addedDate": "2026-04-23",
                },
            },
            "areas": {},
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build_report(
        self,
        status: str = "failed",
        ready_status: str = "fail",
        publishable_status: str = "fail",
        remediation_categories: Any = None,
        toolkit_media_policy: Any = None,
        blocking_errors: Any = None,
        nested_marker: str = "",
    ) -> Dict[str, Any]:
        canonical_report = {
            "remediation_categories": remediation_categories or [],
            "toolkit_media_policy": toolkit_media_policy or {},
            "blocking_errors": blocking_errors or [],
            "fix_list": [],
            "readiness": {
                "gates": {
                    "gameplay": {
                        "blocking_errors": [nested_marker] if nested_marker else []
                    }
                }
            },
        }

        return {
            "status": status,
            "ready_status": ready_status,
            "publishable_status": publishable_status,
            "remediation_categories": remediation_categories or [],
            "toolkit_media_policy": toolkit_media_policy or {},
            "blocking_errors": blocking_errors or [],
            "stages": {
                "publishability": {
                    "report": canonical_report,
                }
            },
        }

    def test_missing_report_fails_open_without_sidebar_fields(self) -> None:
        modules = self.stitcher.get_available_modules()
        no_report_entry = next(m for m in modules if m["moduleName"] == "No_Report_Module")
        self.assertNotIn("brief_failure", no_report_entry)
        self.assertNotIn("media_generator_needed", no_report_entry)

    def test_malformed_report_fails_open_without_crashing(self) -> None:
        malformed_path = self.modules_dir / "No_Report_Module" / "toolkit_build_report.json"
        malformed_path.parent.mkdir(parents=True, exist_ok=True)
        malformed_path.write_text("{not valid json", encoding="utf-8")

        modules = self.stitcher.get_available_modules()
        no_report_entry = next(m for m in modules if m["moduleName"] == "No_Report_Module")
        self.assertNotIn("brief_failure", no_report_entry)
        self.assertNotIn("media_generator_needed", no_report_entry)

    def test_media_handoff_detected_from_remediation_categories(self) -> None:
        report = self._build_report(
            remediation_categories=[
                "structured_monster_media_missing",
                "toolkit_manual_media_generation_required",
            ],
            toolkit_media_policy={"structural_media_debt_count": 5},
        )
        _write_json(
            self.modules_dir / "Murder_at_the_Drowning_Lass" / "toolkit_build_report.json",
            report,
        )

        modules = self.stitcher.get_available_modules()
        entry = next(m for m in modules if m["moduleName"] == "Murder_at_the_Drowning_Lass")
        self.assertEqual(entry.get("brief_failure"), "Build failed: missing monster media")
        self.assertTrue(entry.get("media_generator_needed"))

    def test_mixed_missing_monsters_and_media_maps_to_compact_message(self) -> None:
        report = self._build_report(
            remediation_categories=["structured_monster_media_missing"],
            toolkit_media_policy={"structural_media_debt_count": 0},
            blocking_errors=["Missing monster JSON: coreland_aberration"],
            nested_marker="Missing base media for: coreland_aberration",
        )
        _write_json(
            self.modules_dir / "The_Ancients_Lab" / "toolkit_build_report.json",
            report,
        )

        modules = self.stitcher.get_available_modules()
        entry = next(m for m in modules if m["moduleName"] == "The_Ancients_Lab")
        self.assertEqual(entry.get("brief_failure"), "Build failed: missing monsters/media")
        self.assertTrue(entry.get("media_generator_needed"))

    def test_non_media_failure_has_no_media_handoff(self) -> None:
        report = self._build_report(
            remediation_categories=["semantic_publishability_blocking"],
            toolkit_media_policy={"structural_media_debt_count": 0},
            blocking_errors=["Missing semantic_authority payload in module_context.json"],
        )
        _write_json(
            self.modules_dir / "Semantic_Only_Module" / "toolkit_build_report.json",
            report,
        )

        modules = self.stitcher.get_available_modules()
        entry = next(m for m in modules if m["moduleName"] == "Semantic_Only_Module")
        self.assertEqual(entry.get("brief_failure"), "Build failed: semantic publishability checks")
        self.assertFalse(entry.get("media_generator_needed"))

    def test_stale_nested_media_noise_ignored_when_canonical_has_destination_only(self) -> None:
        report = self._build_report(
            remediation_categories=[],
            toolkit_media_policy={"structural_media_debt_count": 0},
            blocking_errors=["travel_unresolved_destination_phrase: paradox sanctuary"],
            nested_marker="Missing base media for: stale_shadow",
        )
        _write_json(
            self.modules_dir / "The_Ancients_Lab" / "toolkit_build_report.json",
            report,
        )

        modules = self.stitcher.get_available_modules()
        entry = next(m for m in modules if m["moduleName"] == "The_Ancients_Lab")
        self.assertEqual(entry.get("brief_failure"), "Build failed: unresolved destinations")
        self.assertFalse(entry.get("media_generator_needed"))

    def test_renderer_contracts_present_in_both_templates(self) -> None:
        toolkit_template = Path("web/templates/module_toolkit.html").read_text(encoding="utf-8")
        builder_template = Path("web/templates/module_builder.html").read_text(encoding="utf-8")

        for source in (toolkit_template, builder_template):
            self.assertIn("module.brief_failure", source)
            self.assertIn("module.media_generator_needed", source)
            self.assertIn("module-sidebar-failure", source)
            self.assertIn("module-sidebar-handoff", source)
            self.assertIn("Needs Module Media Generator", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
