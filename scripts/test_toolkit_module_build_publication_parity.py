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
from unittest.mock import patch

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
        self.original_publishability = finisher._run_publishability_stage

    def tearDown(self) -> None:
        finisher._run_continuity_stage = self.original_continuity
        finisher._run_registry_stage = self.original_registry
        finisher._run_monster_materialization_stage = self.original_materialization
        finisher._run_publishability_stage = self.original_publishability

        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_finisher_success_writes_report(self) -> None:
        finisher._run_continuity_stage = lambda *args, **kwargs: {
            "status": "success",
            "stage": "continuity",
        }
        finisher._run_registry_stage = lambda *args, **kwargs: {
            "status": "success",
            "stage": "registry",
        }
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "success",
            "stage": "monster_materialization",
        }
        finisher._run_publishability_stage = lambda *args, **kwargs: {
            "status": "success",
            "ready_status": "pass",
            "publishable_status": "pass",
        }

        result = finisher.run_toolkit_module_postbuild_finishing(
            self.module_slug, strict=True
        )

        self.assertEqual(result.get("status"), "success")
        report_path = Path(result.get("report_path", ""))
        self.assertTrue(report_path.exists())

        report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report_payload.get("status"), "success")
        self.assertIn("publication_parity_note", report_payload)
        self.assertEqual(report_payload.get("ready_status"), "pass")
        self.assertEqual(report_payload.get("publishable_status"), "pass")

    def test_finisher_degraded_maps_status(self) -> None:
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "degraded",
            "reason": "missing bestiary entries",
        }
        finisher._run_publishability_stage = lambda *args, **kwargs: {
            "status": "success",
            "ready_status": "pass",
            "publishable_status": "pass",
        }

        result = finisher.run_toolkit_module_postbuild_finishing(
            self.module_slug, strict=True
        )
        self.assertEqual(result.get("status"), "degraded")

    def test_finisher_failed_registry_maps_failed(self) -> None:
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_registry_stage = lambda *args, **kwargs: {
            "status": "failed",
            "reason": "registry missing",
        }
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "success"
        }
        finisher._run_publishability_stage = lambda *args, **kwargs: {
            "status": "degraded",
            "ready_status": "pass",
            "publishable_status": "fail",
        }

        result = finisher.run_toolkit_module_postbuild_finishing(
            self.module_slug, strict=True
        )
        self.assertEqual(result.get("status"), "failed")
        self.assertEqual(
            (result.get("stages") or {}).get("registry", {}).get("reason"),
            "registry missing",
        )

    def test_finisher_publishable_failure_without_media_handoff_fails(self) -> None:
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "success"
        }
        finisher._run_publishability_stage = lambda *args, **kwargs: {
            "status": "degraded",
            "ready_status": "pass",
            "publishable_status": "fail",
            "report": {
                "ready_status": "pass",
                "publishable_status": "fail",
                "readiness": {
                    "overall_status": "pass",
                },
                "remediation_categories": ["semantic_probe_failure"],
                "blocking_errors": ["semantic_probe_failure: travel continuity mismatch"],
                "toolkit_media_policy": {
                    "structural_media_debt_count": 0,
                    "structural_media_debt_slugs": [],
                },
            },
        }

        result = finisher.run_toolkit_module_postbuild_finishing(
            self.module_slug, strict=True
        )
        self.assertEqual(result.get("status"), "failed")
        self.assertEqual(result.get("ready_status"), "pass")
        self.assertEqual(result.get("publishable_status"), "fail")

    def test_monster_materialization_stage_fails_on_blocked_count(self) -> None:
        with patch(
            "scripts.homebrew_materialize_monsters.materialize_monsters",
            return_value={
                "status": "degraded",
                "blocked_count": 1,
                "blocker_classes": {"authorized_monster_provider_unavailable": 1},
            },
        ):
            stage = finisher._run_monster_materialization_stage(self.module_slug)
            self.assertEqual(stage.get("status"), "failed")
            self.assertIn(
                "authorized_monster_provider_unavailable",
                str(stage.get("reason") or ""),
            )
            parsed_output = stage.get("parsed_output") or {}
            self.assertEqual(int(parsed_output.get("blocked_count", 0)), 1)

    def test_same_run_provenance_report_exists_before_publishability_stage(self) -> None:
        """Verify toolkit_build_report.json is written BEFORE publishability runs."""
        write_order = []
        original_safe_write = finisher.safe_write_json

        def _tracking_safe_write(path: str, data, **kwargs):
            write_order.append(("write", Path(path).name))
            return original_safe_write(path, data, **kwargs)

        finisher._run_continuity_stage = lambda *args, **kwargs: {
            "status": "success",
        }
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "success",
        }

        def _tracking_publishability(*args, **kwargs):
            report_path = self.module_dir / "toolkit_build_report.json"
            exists_before = report_path.exists()
            write_order.append(("publishability_called", exists_before))
            return {
                "status": "success",
                "ready_status": "pass",
                "publishable_status": "pass",
            }

        finisher._run_publishability_stage = _tracking_publishability

        with patch.object(finisher, "safe_write_json", _tracking_safe_write):
            result = finisher.run_toolkit_module_postbuild_finishing(
                self.module_slug, strict=True
            )

        pre_write_events = [
            e for e in write_order if e[0] == "write"
        ]
        pub_called_after_pre_write = any(
            e[1] == "toolkit_build_report.json" for e in pre_write_events
        )
        pub_event = next(
            e for e in write_order if e[0] == "publishability_called"
        )
        self.assertTrue(
            pub_event[1],
            "toolkit_build_report.json must exist before publishability stage runs",
        )
        self.assertTrue(
            pub_called_after_pre_write,
            "toolkit_build_report.json must be written before publishability stage",
        )

    def test_finisher_media_only_debt_yields_success_with_handoff(self) -> None:
        """Media-only debt: build succeeds with handoff semantics, not failure."""
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "success",
        }
        finisher._run_publishability_stage = lambda *args, **kwargs: {
            "status": "degraded",
            "ready_status": "pass",
            "publishable_status": "fail",
            "report": {
                "ready_status": "pass",
                "publishable_status": "fail",
                "readiness": {
                    "overall_status": "pass",
                },
                "remediation_categories": ["structured_monster_media_missing"],
                "blocking_errors": ["missing base media files for monsters"],
                "toolkit_media_policy": {
                    "structural_media_debt_count": 2,
                    "structural_media_debt_slugs": ["goblin", "orc"],
                },
            },
        }

        result = finisher.run_toolkit_module_postbuild_finishing(
            self.module_slug, strict=True
        )

        self.assertEqual(result.get("status"), "success")
        publishability_stage = result.get("stages", {}).get("publishability", {})
        self.assertEqual(publishability_stage.get("status"), "degraded")
        media_handoff = publishability_stage.get("media_handoff", {})
        self.assertEqual(media_handoff.get("build_outcome"), "success_with_media_handoff")
        self.assertEqual(media_handoff.get("next_step"), "Module Builder -> Module Media Generator")
        self.assertEqual(media_handoff.get("media_debt_count"), 2)
        self.assertIn("goblin", media_handoff.get("media_debt_slugs", []))
        self.assertIn("Module Builder", str(media_handoff.get("message", "")))

    def test_finisher_real_structural_failure_still_fails(self) -> None:
        """Real structural failure (not media-only): build still fails."""
        finisher._run_continuity_stage = lambda *args, **kwargs: {
            "status": "failed",
            "reason": "continuity contract missing required keys",
        }
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "success",
        }
        finisher._run_publishability_stage = lambda *args, **kwargs: {
            "status": "failed",
            "ready_status": "fail",
            "publishable_status": "fail",
            "report": {
                "ready_status": "fail",
                "publishable_status": "fail",
                "readiness": {
                    "overall_status": "fail",
                },
                "remediation_categories": ["structured_monster_media_missing"],
                "blocking_errors": ["readiness_gate_failed: module is not structurally ready"],
                "toolkit_media_policy": {
                    "structural_media_debt_count": 0,
                    "structural_media_debt_slugs": [],
                },
            },
        }

        result = finisher.run_toolkit_module_postbuild_finishing(
            self.module_slug, strict=True
        )

        self.assertEqual(result.get("status"), "failed")
        self.assertIsNone(result.get("media_handoff"))
        continuity_stage = result.get("stages", {}).get("continuity", {})
        self.assertEqual(continuity_stage.get("status"), "failed")

    def test_finisher_non_media_blocking_errors_still_fails(self) -> None:
        """Non-media blocking errors present: build still fails even if media debt exists."""
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "success",
        }
        finisher._run_publishability_stage = lambda *args, **kwargs: {
            "status": "degraded",
            "ready_status": "pass",
            "publishable_status": "fail",
            "report": {
                "ready_status": "pass",
                "publishable_status": "fail",
                "readiness": {
                    "overall_status": "pass",
                },
                "remediation_categories": ["structured_monster_media_missing"],
                "blocking_errors": [
                    "missing base media files for monsters",
                    "unresolved destination: NIG99 (does not exist in module)",
                ],
                "toolkit_media_policy": {
                    "structural_media_debt_count": 1,
                    "structural_media_debt_slugs": ["goblin"],
                },
            },
        }

        result = finisher.run_toolkit_module_postbuild_finishing(
            self.module_slug, strict=True
        )

        self.assertEqual(result.get("status"), "failed")
        self.assertIsNone(
            result.get("stages", {}).get("publishability", {}).get("media_handoff")
        )

    def test_finisher_mixed_category_blocks_media_handoff_even_if_blockers_are_sparse(self) -> None:
        """Mixed remediation category must block success-with-media-handoff semantics."""
        finisher._run_continuity_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_registry_stage = lambda *args, **kwargs: {"status": "success"}
        finisher._run_monster_materialization_stage = lambda *args, **kwargs: {
            "status": "success",
        }
        finisher._run_publishability_stage = lambda *args, **kwargs: {
            "status": "degraded",
            "ready_status": "pass",
            "publishable_status": "fail",
            "report": {
                "ready_status": "pass",
                "publishable_status": "fail",
                "readiness": {
                    "overall_status": "pass",
                },
                "remediation_categories": [
                    "structured_monster_media_missing",
                    "semantic_publishability_blocking",
                    "mixed_media_semantic_blocking",
                ],
                "blocking_errors": [],
                "toolkit_media_policy": {
                    "structural_media_debt_count": 1,
                    "structural_media_debt_slugs": ["goblin"],
                },
            },
        }

        result = finisher.run_toolkit_module_postbuild_finishing(
            self.module_slug, strict=True
        )

        self.assertEqual(result.get("status"), "failed")
        self.assertIsNone(
            result.get("stages", {}).get("publishability", {}).get("media_handoff")
        )


class TestToolkitPublicationParitySourceContracts(unittest.TestCase):
    """Source-level contracts for web handler and toolkit UI integration."""

    def test_web_interface_invokes_finisher_and_reports_status(self) -> None:
        source = Path("web/web_interface.py").read_text(encoding="utf-8")
        routes_source = Path("web/routes/toolkit_homebrew_routes.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("run_toolkit_module_postbuild_finishing", source)
        self.assertIn("stage_name': 'Post Build Finishing'", source)
        self.assertIn("generation_succeeded", source)
        self.assertIn("publication_parity_note", source)
        self.assertIn("_build_hydration_summary", routes_source)
        self.assertIn('"hydration_summary"', routes_source)

    def test_toolkit_template_exposes_finishing_stage_and_parity_note(self) -> None:
        source = Path("web/templates/module_toolkit.html").read_text(encoding="utf-8")

        self.assertIn("Post-Build Finishing", source)
        self.assertIn("publication_parity_note", source)
        self.assertIn("Post-Build Status", source)
        self.assertIn("Hydration Summary:", source)
        self.assertIn("buildHomebrewHydrationAwareDetails", source)

    def test_toolkit_template_exposes_semantic_remediation_lane(self) -> None:
        source = Path("web/templates/module_toolkit.html").read_text(encoding="utf-8")

        self.assertIn("formatSemanticRemediationSection", source)
        self.assertIn("Semantic Remediation:", source)
        self.assertIn("blocking_findings", source)
        self.assertIn("Blocking Errors (fallback):", source)

    def test_toolkit_template_exposes_mixed_media_semantic_sections(self) -> None:
        source = Path("web/templates/module_toolkit.html").read_text(encoding="utf-8")

        self.assertIn("formatMediaRemediationSection", source)
        self.assertIn("Media Remediation:", source)
        self.assertIn("structural_media_debt_count", source)
        self.assertIn("buildToolkitFinishingFailureDetails", source)

    def test_toolkit_template_preserves_summary_plus_raw_payload_output(self) -> None:
        source = Path("web/templates/module_toolkit.html").read_text(encoding="utf-8")

        self.assertIn("const semanticRemediationText = formatSemanticRemediationSection", source)
        self.assertIn("const mediaRemediationText = formatMediaRemediationSection", source)
        self.assertIn("sections.push(semanticRemediationText)", source)
        self.assertIn("sections.push(mediaRemediationText)", source)
        self.assertIn("sections.push(`Raw Payload:", source)


if __name__ == "__main__":
    unittest.main()
