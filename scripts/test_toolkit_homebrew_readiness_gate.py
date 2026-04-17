# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for toolkit Homebrew structural readiness gate."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.toolkit_homebrew_upload_contract import (
    ensure_workspace_placeholders,
    get_workspace_files,
)
from utils.spatial_contract import parse_coordinate
from web.extensions import toolkit_homebrew_readiness_gate as readiness_gate
from scripts.remediate_module_coordinates import remediate_area_map_pair


def _make_validation_report(failures: dict, total_failed: int) -> dict:
    """Build synthetic validator report fixture."""
    return {
        "status": "fail" if total_failed > 0 else "pass",
        "module": "Toolkit_Readiness_Module",
        "report": {
            "modules": {
                "Toolkit_Readiness_Module": {
                    "module": "Toolkit_Readiness_Module",
                    "total_failed": total_failed,
                    "files": failures,
                }
            },
            "summary": {
                "any_failed": total_failed > 0,
                "modules_total": 1,
            },
        },
        "total_failed": total_failed,
    }


class TestToolkitHomebrewReadinessGate(unittest.TestCase):
    """Validate readiness gating ordering and bounded failure states."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        ensure_workspace_placeholders(self.workspace)
        self.files = get_workspace_files(self.workspace)
        self.files["build_result"].write_text(
            json.dumps(
                {
                    "status": "success",
                    "stage": "build",
                    "job_id": "job-1",
                    "module_name": "Toolkit_Readiness_Module",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_extract_failure_categories_reads_module_scoped_validator_shape(
        self,
    ) -> None:
        validation_report = _make_validation_report(
            {
                "reference_integrity": {"failed": 3, "errors": ["monster a"]},
                "spatial_contract": {"failed": 2, "errors": ["spatial a"]},
            },
            5,
        )

        categories = readiness_gate._extract_failure_categories(validation_report)
        signature = readiness_gate._build_validation_signature(validation_report)

        self.assertEqual(categories.get("reference_integrity"), 3)
        self.assertEqual(categories.get("spatial_contract"), 2)
        self.assertIn("reference_integrity", signature)
        self.assertIn("spatial_contract", signature)

    def test_structural_readiness_audit_disables_gameplay_gate(self) -> None:
        original_audit = readiness_gate.audit_module_readiness

        try:

            def _fake_audit(**kwargs):
                self.assertFalse(kwargs.get("include_gameplay_gate", True))
                return {
                    "gates": {
                        "gameplay": {"status": "skipped", "reason": "gate_disabled"},
                        "schema": {"status": "pass", "reason": "pass"},
                    },
                    "overall_status": "pass",
                }

            readiness_gate.audit_module_readiness = _fake_audit
            result = readiness_gate._run_structural_readiness_audit(
                "Toolkit_Readiness_Module"
            )
            self.assertEqual(result.get("status"), "pass")
            self.assertEqual(
                (result.get("gameplay_gate") or {}).get("status"), "skipped"
            )
        finally:
            readiness_gate.audit_module_readiness = original_audit

    def test_force_relayout_repositions_non_cardinal_connections(self) -> None:
        area_data = {
            "areaId": "AC001",
            "areaName": "Test Area",
            "locations": [
                {
                    "locationId": "F01",
                    "name": "Room 1",
                    "connectivity": ["F03"],
                    "coordinates": "X10Y10",
                },
                {
                    "locationId": "F02",
                    "name": "Room 2",
                    "connectivity": [],
                    "coordinates": "X11Y10",
                },
                {
                    "locationId": "F03",
                    "name": "Room 3",
                    "connectivity": ["F01"],
                    "coordinates": "X12Y10",
                },
            ],
        }
        map_data = {
            "rooms": [
                {
                    "id": "F01",
                    "name": "Room 1",
                    "connections": ["F03"],
                    "coordinates": "X10Y10",
                },
                {
                    "id": "F02",
                    "name": "Room 2",
                    "connections": [],
                    "coordinates": "X11Y10",
                },
                {
                    "id": "F03",
                    "name": "Room 3",
                    "connections": ["F01"],
                    "coordinates": "X12Y10",
                },
            ]
        }

        patched_area, patched_map, changes = remediate_area_map_pair(
            area_data,
            map_data,
            force_relayout=True,
        )

        self.assertGreater(changes, 0)
        relaid_coordinate = patched_area["locations"][2]["coordinates"]
        self.assertNotEqual(relaid_coordinate, "X12Y10")
        f01_x, f01_y = parse_coordinate(patched_area["locations"][0]["coordinates"])
        f03_x, f03_y = parse_coordinate(relaid_coordinate)
        self.assertEqual(abs(f01_x - f03_x) + abs(f01_y - f03_y), 1)
        self.assertEqual(patched_map["rooms"][2]["coordinates"], relaid_coordinate)

    def test_deterministic_repairs_run_before_semantic_repairs(self) -> None:
        call_order = []
        validator_sequence = [
            _make_validation_report(
                {
                    "reference_integrity": {
                        "failed": 2,
                        "errors": ["monster a", "monster b"],
                    }
                },
                2,
            ),
            _make_validation_report(
                {"spatial_contract": {"failed": 1, "errors": ["spatial parity"]}},
                1,
            ),
            _make_validation_report(
                {"module_context": {"failed": 1, "errors": ["npc placement"]}},
                1,
            ),
            _make_validation_report({}, 0),
        ]

        original_validator = readiness_gate._run_validator
        original_det = readiness_gate._run_deterministic_repairs
        original_sem = readiness_gate._run_semantic_repairs
        original_audit = readiness_gate._run_structural_readiness_audit
        original_defect = readiness_gate._detect_build_system_defect

        try:
            readiness_gate._run_validator = lambda module_slug: validator_sequence.pop(
                0
            )
            readiness_gate._detect_build_system_defect = (
                lambda build_result, module_dir, validation_report: None
            )
            readiness_gate._run_deterministic_repairs = (
                lambda module_slug, module_dir, failure_categories: (
                    call_order.append("det") or {"status": "success", "changed": True}
                )
            )
            readiness_gate._run_semantic_repairs = lambda module_dir: (
                call_order.append("sem") or {"status": "success", "changed": True}
            )
            readiness_gate._run_structural_readiness_audit = lambda module_slug: {
                "status": "pass",
                "report": {"overall_status": "pass"},
            }

            result = readiness_gate.run_toolkit_homebrew_readiness_gate(
                workspace=self.workspace,
                job_id="job-1",
            )

            self.assertEqual(result.get("status"), "ready_for_finishing")
            self.assertEqual(call_order, ["det", "det", "sem"])
        finally:
            readiness_gate._run_validator = original_validator
            readiness_gate._run_deterministic_repairs = original_det
            readiness_gate._run_semantic_repairs = original_sem
            readiness_gate._run_structural_readiness_audit = original_audit
            readiness_gate._detect_build_system_defect = original_defect

    def test_build_system_failed_bypasses_repair_loops(self) -> None:
        original_validator = readiness_gate._run_validator
        original_det = readiness_gate._run_deterministic_repairs
        original_sem = readiness_gate._run_semantic_repairs
        original_defect = readiness_gate._detect_build_system_defect

        try:
            readiness_gate._run_validator = lambda module_slug: _make_validation_report(
                {}, 0
            )
            readiness_gate._detect_build_system_defect = (
                lambda build_result, module_dir, validation_report: {
                    "status": "build_system_failed",
                    "reason": "builder_runtime_exception",
                }
            )

            def _fail_if_called(*_args, **_kwargs):
                raise AssertionError(
                    "repair loops should not run on build-system defect"
                )

            readiness_gate._run_deterministic_repairs = _fail_if_called
            readiness_gate._run_semantic_repairs = _fail_if_called

            result = readiness_gate.run_toolkit_homebrew_readiness_gate(
                workspace=self.workspace,
                job_id="job-1",
            )

            self.assertEqual(result.get("status"), "build_system_failed")
            self.assertEqual(
                (result.get("defect") or {}).get("reason"), "builder_runtime_exception"
            )
        finally:
            readiness_gate._run_validator = original_validator
            readiness_gate._run_deterministic_repairs = original_det
            readiness_gate._run_semantic_repairs = original_sem
            readiness_gate._detect_build_system_defect = original_defect

    def test_repair_budget_exhaustion_persists_inspectable_reports(self) -> None:
        failure_report = _make_validation_report(
            {
                "reference_integrity": {
                    "failed": 2,
                    "errors": ["monster a", "monster b"],
                }
            },
            2,
        )

        original_validator = readiness_gate._run_validator
        original_det = readiness_gate._run_deterministic_repairs
        original_sem = readiness_gate._run_semantic_repairs
        original_audit = readiness_gate._run_structural_readiness_audit
        original_defect = readiness_gate._detect_build_system_defect

        try:
            readiness_gate._run_validator = lambda module_slug: dict(failure_report)
            readiness_gate._detect_build_system_defect = (
                lambda build_result, module_dir, validation_report: None
            )
            readiness_gate._run_deterministic_repairs = (
                lambda module_slug, module_dir, failure_categories: {
                    "status": "success",
                    "changed": False,
                }
            )
            readiness_gate._run_semantic_repairs = lambda module_dir: {
                "status": "success",
                "changed": False,
            }
            readiness_gate._run_structural_readiness_audit = lambda module_slug: {
                "status": "fail",
                "report": {"overall_status": "fail"},
            }

            result = readiness_gate.run_toolkit_homebrew_readiness_gate(
                workspace=self.workspace,
                job_id="job-1",
            )

            self.assertEqual(result.get("status"), "repair_budget_exhausted")
            self.assertTrue(self.files["repair_report"].exists())
            self.assertTrue(self.files["readiness_validation_report"].exists())
            self.assertTrue(self.files["readiness_audit_report"].exists())
        finally:
            readiness_gate._run_validator = original_validator
            readiness_gate._run_deterministic_repairs = original_det
            readiness_gate._run_semantic_repairs = original_sem
            readiness_gate._run_structural_readiness_audit = original_audit
            readiness_gate._detect_build_system_defect = original_defect

    def test_hydration_blocked_maps_to_shared_failed_semantics(self) -> None:
        hydration_payload = {
            "status": "degraded",
            "blocked_count": 2,
            "blocker_classes": {
                "unauthorized_monster_reference": 1,
                "authorized_monster_provider_unavailable": 1,
            },
            "hydration_modes": {"existing": 1},
            "monster_results": [
                {
                    "requested_name": "Ghost Knight",
                    "canonical_name": "Ghost Knight",
                    "canonical_slug": "ghost_knight",
                    "mode": "failed",
                    "blocker_class": "unauthorized_monster_reference",
                }
            ],
        }

        with patch(
            "scripts.homebrew_materialize_monsters.materialize_monsters",
            return_value=hydration_payload,
        ):
            mapped = readiness_gate._deterministic_materialize_monsters(
                "Toolkit_Readiness_Module"
            )

        self.assertEqual(mapped.get("status"), "failed")
        self.assertEqual(mapped.get("reason"), "monster_hydration_blocked")
        hydration_result = mapped.get("hydration_result") or {}
        self.assertEqual(int(hydration_result.get("blocked_count", 0)), 2)
        self.assertEqual(
            (hydration_result.get("blocker_classes") or {}).get(
                "unauthorized_monster_reference"
            ),
            1,
        )

    def test_missing_monster_smoke_returns_precise_structured_blocker(self) -> None:
        failure_report = _make_validation_report(
            {"reference_integrity": {"failed": 1, "errors": ["missing monster"]}},
            1,
        )

        original_validator = readiness_gate._run_validator
        original_det = readiness_gate._run_deterministic_repairs
        original_sem = readiness_gate._run_semantic_repairs
        original_audit = readiness_gate._run_structural_readiness_audit
        original_defect = readiness_gate._detect_build_system_defect

        try:
            readiness_gate._run_validator = lambda module_slug: dict(failure_report)
            readiness_gate._detect_build_system_defect = (
                lambda build_result, module_dir, validation_report: None
            )
            readiness_gate._run_deterministic_repairs = (
                lambda module_slug, module_dir, failure_categories: {
                    "status": "failed",
                    "reason": "monster_hydration_blocked",
                    "repairs": {
                        "monster_materialization": {
                            "status": "failed",
                            "reason": "monster_hydration_blocked",
                            "hydration_result": {
                                "blocked_count": 1,
                                "blocker_classes": {
                                    "authorized_monster_provider_unavailable": 1
                                },
                                "hydration_modes": {},
                            },
                        }
                    },
                }
            )

            def _fail_if_called(*_args, **_kwargs):
                raise AssertionError(
                    "semantic repairs should not run after deterministic blocker"
                )

            readiness_gate._run_semantic_repairs = _fail_if_called
            readiness_gate._run_structural_readiness_audit = lambda module_slug: {
                "status": "fail",
                "report": {"overall_status": "fail"},
            }

            result = readiness_gate.run_toolkit_homebrew_readiness_gate(
                workspace=self.workspace,
                job_id="job-1",
            )

            self.assertEqual(result.get("status"), "repair_budget_exhausted")
            self.assertEqual(int(result.get("semantic_passes", 0)), 0)
            attempts = result.get("repair_attempts") or []
            self.assertTrue(attempts)
            first_attempt = attempts[0]
            self.assertEqual(first_attempt.get("status"), "failed")
            self.assertEqual(first_attempt.get("reason"), "monster_hydration_blocked")

            monster_repair = (first_attempt.get("repairs") or {}).get(
                "monster_materialization", {}
            )
            self.assertEqual(monster_repair.get("reason"), "monster_hydration_blocked")
            hydration_result = monster_repair.get("hydration_result") or {}
            self.assertEqual(int(hydration_result.get("blocked_count", 0)), 1)
            self.assertEqual(
                (hydration_result.get("blocker_classes") or {}).get(
                    "authorized_monster_provider_unavailable"
                ),
                1,
            )
        finally:
            readiness_gate._run_validator = original_validator
            readiness_gate._run_deterministic_repairs = original_det
            readiness_gate._run_semantic_repairs = original_sem
            readiness_gate._run_structural_readiness_audit = original_audit
            readiness_gate._detect_build_system_defect = original_defect


if __name__ == "__main__":
    unittest.main()
