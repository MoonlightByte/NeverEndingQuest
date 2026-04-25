#!/usr/bin/env python3
"""Tests for layered module publishability audit."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parent / "audit_module_publishability.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_module_publishability", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
publishability = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publishability)


class TestAuditModulePublishability(unittest.TestCase):
    def test_publishable_pass_requires_all_layers(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={"overall_status": "pass", "fix_list": [], "gates": {}},
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertEqual(report["ready_status"], "pass")
        self.assertEqual(report["publishable_status"], "pass")
        self.assertEqual(report["exit_code"], 0)

    def test_ready_can_pass_while_publishable_fails(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={"overall_status": "pass", "fix_list": [], "gates": {}},
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={
                    "status": "fail",
                    "blocking_errors": ["semantic issue"],
                    "warnings": [],
                },
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertEqual(report["ready_status"], "pass")
        self.assertEqual(report["publishable_status"], "fail")
        self.assertIn("semantic issue", report["blocking_errors"])
        self.assertIn("semantic_publishability_blocking", report["remediation_categories"])
        self.assertNotIn("mixed_media_semantic_blocking", report["remediation_categories"])
        self.assertEqual(report["exit_code"], 1)

    def test_readiness_failure_forces_publishable_failure(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={
                    "overall_status": "fail",
                    "fix_list": ["fix ready"],
                    "gates": {},
                },
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertEqual(report["ready_status"], "fail")
        self.assertEqual(report["publishable_status"], "fail")
        self.assertIn("readiness_gate_failed", " ".join(report["blocking_errors"]))
        self.assertIn("fix ready", report["fix_list"])

    def test_toolkit_source_is_forwarded_to_readiness(self):
        captured = {}

        def _fake_readiness(module_slug, source="watcher", **_kwargs):
            captured["source"] = source
            return {"overall_status": "pass", "fix_list": [], "gates": {}}

        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                side_effect=_fake_readiness,
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability(
                "example_module",
                source="toolkit",
            )

        self.assertEqual(captured.get("source"), "toolkit")
        self.assertEqual(report.get("source"), "toolkit")

    def test_degraded_semantic_audit_without_blocking_errors_does_not_fail_publishability(
        self,
    ):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={"overall_status": "pass", "fix_list": [], "gates": {}},
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={
                    "status": "degraded",
                    "blocking_errors": [],
                    "warnings": ["npc_scene_authority has no visible locations"],
                },
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertEqual(report["ready_status"], "pass")
        self.assertEqual(report["publishable_status"], "pass")
        self.assertEqual(report["exit_code"], 0)
        self.assertNotIn(
            "semantic_publication_audit_nonpass",
            " ".join(report.get("blocking_errors", [])),
        )

    def test_degraded_semantic_probes_without_blocking_errors_does_not_fail_publishability(
        self,
    ):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={"overall_status": "pass", "fix_list": [], "gates": {}},
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={
                    "status": "degraded",
                    "blocking_errors": [],
                    "warnings": ["handoff_probe_fixture_missing"],
                },
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertEqual(report["ready_status"], "pass")
        self.assertEqual(report["publishable_status"], "pass")
        self.assertEqual(report["exit_code"], 0)
        self.assertNotIn(
            "semantic_probe_harness_nonpass",
            " ".join(report.get("blocking_errors", [])),
        )

    def test_remediation_categories_classifies_warning_only_degraded(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={"overall_status": "pass", "fix_list": [], "gates": {}},
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={
                    "status": "degraded",
                    "blocking_errors": [],
                    "warnings": ["npc_scene_authority has no visible locations"],
                },
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={
                    "status": "degraded",
                    "blocking_errors": [],
                    "warnings": ["handoff_probe_fixture_missing"],
                },
            ),
        ):
            report = publishability.audit_module_publishability("example_module")

        self.assertIn("remediation_categories", report)
        cats = report["remediation_categories"]
        self.assertIn("semantic_warning_only", cats)
        self.assertIn("semantic_tooling_debt", cats)

    def test_toolkit_media_policy_passthrough_drives_media_remediation_categories(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={
                    "overall_status": "fail",
                    "fix_list": [],
                    "gates": {"sidecar": {"reason": "pass"}},
                    "toolkit_media_policy": {
                        "structural_media_debt_count": 2,
                        "structural_media_debt_slugs": ["ogre", "goblin"],
                    },
                },
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability(
                "example_module", source="toolkit"
            )

        self.assertIn("structured_monster_media_missing", report["remediation_categories"])
        self.assertIn(
            "toolkit_manual_media_generation_required", report["remediation_categories"]
        )
        self.assertEqual(
            report.get("toolkit_media_policy", {}).get("structural_media_debt_count"),
            2,
        )

    def test_mixed_media_and_semantic_blockers_are_classified(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={
                    "overall_status": "fail",
                    "fix_list": [],
                    "gates": {"sidecar": {"reason": "pass"}},
                    "toolkit_media_policy": {
                        "structural_media_debt_count": 1,
                        "structural_media_debt_slugs": ["ogre"],
                    },
                },
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={
                    "status": "fail",
                    "blocking_errors": ["travel_unresolved_destination_phrase: crucible hall"],
                    "warnings": [],
                },
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability(
                "example_module", source="toolkit"
            )

        self.assertEqual(report["publishable_status"], "fail")
        self.assertIn("structured_monster_media_missing", report["remediation_categories"])
        self.assertIn("semantic_publishability_blocking", report["remediation_categories"])
        self.assertIn("mixed_media_semantic_blocking", report["remediation_categories"])

    def test_shared_static_fallback_does_not_override_module_local_media_debt(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={
                    "overall_status": "fail",
                    "fix_list": ["Add media: modules/example_module/media/monsters/ogre.jpg"],
                    "gates": {"gameplay": {"reason": "missing_base_media_files"}},
                    "toolkit_media_policy": {
                        "structural_media_debt_count": 1,
                        "structural_media_debt_slugs": ["ogre"],
                        "fallback_hits": ["web/static/media/monsters/ogre.jpg"],
                    },
                },
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability(
                "example_module", source="toolkit"
            )

        self.assertEqual(report["ready_status"], "fail")
        self.assertEqual(report["publishable_status"], "fail")
        self.assertIn("readiness_gate_failed", " ".join(report["blocking_errors"]))
        self.assertIn("structured_monster_media_missing", report["remediation_categories"])

    def test_scene_entity_modeling_candidate_for_media_plus_semantic_warnings(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={
                    "overall_status": "fail",
                    "fix_list": [],
                    "gates": {"sidecar": {"reason": "pass"}},
                    "toolkit_media_policy": {
                        "structural_media_debt_count": 1,
                        "structural_media_debt_slugs": ["illusory_beast"],
                    },
                },
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={
                    "status": "degraded",
                    "blocking_errors": [],
                    "warnings": ["npc_scene_authority has no visible locations"],
                },
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={
                    "status": "degraded",
                    "blocking_errors": [],
                    "warnings": ["handoff_probe_fixture_missing"],
                },
            ),
        ):
            report = publishability.audit_module_publishability(
                "example_module", source="toolkit"
            )

        self.assertIn("structured_monster_media_missing", report["remediation_categories"])
        self.assertIn("semantic_warning_only", report["remediation_categories"])
        self.assertIn("scene_entity_modeling_candidate", report["remediation_categories"])
        self.assertNotIn("mixed_media_semantic_blocking", report["remediation_categories"])

    def test_normalized_shortform_semantic_context_does_not_create_semantic_blocker(self):
        with (
            patch.object(
                publishability,
                "audit_module_readiness",
                return_value={
                    "overall_status": "fail",
                    "fix_list": [],
                    "gates": {"sidecar": {"reason": "pass"}},
                    "toolkit_media_policy": {
                        "structural_media_debt_count": 1,
                        "structural_media_debt_slugs": ["oathbound_shade"],
                    },
                },
            ),
            patch.object(
                publishability,
                "audit_module_semantic_authority",
                return_value={
                    "status": "degraded",
                    "blocking_errors": [],
                    "warnings": [
                        "normalized short-form destination: oath chamber -> silent oath chamber"
                    ],
                    "normalized_shortform_destination_phrases": [
                        {
                            "phrase": "oath chamber",
                            "anchor_phrase": "silent oath chamber",
                            "location_id": "H03",
                        }
                    ],
                },
            ),
            patch.object(
                publishability,
                "run_module_semantic_probes",
                return_value={"status": "pass", "blocking_errors": [], "warnings": []},
            ),
        ):
            report = publishability.audit_module_publishability(
                "Murder_at_the_Drowning_Lass", source="toolkit"
            )

        self.assertEqual(report["publishable_status"], "fail")
        self.assertIn("structured_monster_media_missing", report["remediation_categories"])
        self.assertIn("semantic_warning_only", report["remediation_categories"])
        self.assertNotIn("semantic_publishability_blocking", report["remediation_categories"])
        self.assertNotIn("mixed_media_semantic_blocking", report["remediation_categories"])


if __name__ == "__main__":
    unittest.main()
