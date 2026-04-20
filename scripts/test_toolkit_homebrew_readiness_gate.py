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
                lambda module_slug, module_dir, failure_categories, validation_report=None: (
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
                lambda module_slug, module_dir, failure_categories, validation_report=None: {
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
            self.assertEqual(result.get("convergence_outcome"), "fixed_point_detected")
            self.assertTrue(result.get("fixed_point_detected"))
            self.assertIn(
                "monster_reference_closure_gap",
                result.get("residual_blocker_classes") or [],
            )
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
                lambda module_slug, module_dir, failure_categories, validation_report=None: {
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

    def test_failed_deterministic_with_changes_revalidates_before_exit(self) -> None:
        validator_sequence = [
            _make_validation_report(
                {
                    "reference_integrity": {
                        "failed": 1,
                        "errors": ["missing monster"],
                    }
                },
                1,
            ),
            _make_validation_report({}, 0),
        ]
        validator_calls = []

        original_validator = readiness_gate._run_validator
        original_det = readiness_gate._run_deterministic_repairs
        original_audit = readiness_gate._run_structural_readiness_audit
        original_defect = readiness_gate._detect_build_system_defect

        try:
            def _next_validation(module_slug):
                validator_calls.append(module_slug)
                return validator_sequence.pop(0)

            readiness_gate._run_validator = _next_validation
            readiness_gate._detect_build_system_defect = (
                lambda build_result, module_dir, validation_report: None
            )
            readiness_gate._run_deterministic_repairs = (
                lambda module_slug, module_dir, failure_categories, validation_report=None: {
                    "status": "failed",
                    "changed": True,
                    "repairs": {
                        "monster_reference_closure": {
                            "status": "changed",
                            "reason": "validator_reference_closure",
                        }
                    },
                }
            )
            readiness_gate._run_structural_readiness_audit = lambda module_slug: {
                "status": "pass",
                "report": {"overall_status": "pass"},
            }

            result = readiness_gate.run_toolkit_homebrew_readiness_gate(
                workspace=self.workspace,
                job_id="job-1",
            )

            self.assertEqual(len(validator_calls), 2)
            self.assertEqual((result.get("validation") or {}).get("status"), "pass")
            self.assertEqual(result.get("status"), "ready_for_finishing")
        finally:
            readiness_gate._run_validator = original_validator
            readiness_gate._run_deterministic_repairs = original_det
            readiness_gate._run_structural_readiness_audit = original_audit
            readiness_gate._detect_build_system_defect = original_defect

    def test_monster_schema_completion_backfills_required_fields(self) -> None:
        module_slug = "Toolkit_Readiness_Module"
        module_dir = self.workspace / "modules" / module_slug
        monsters_dir = module_dir / "monsters"
        monsters_dir.mkdir(parents=True, exist_ok=True)

        monster_path = monsters_dir / "salt_wraith.json"
        monster_path.write_text(
            json.dumps(
                {
                    "name": "Salt Wraith",
                    "type": "undead",
                    "hitPoints": 19,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        compendium = {
            "salt_wraith": {
                "name": "Salt Wraith",
                "size": "Medium",
                "alignment": "chaotic evil",
                "armorClass": 13,
            }
        }

        with patch(
            "utils.module_monster_authority.load_monster_compendium_lookup",
            return_value=compendium,
        ):
            result = readiness_gate._deterministic_repair_monster_schema(
                module_slug,
                module_dir,
            )

        self.assertEqual(result.get("status"), "changed")
        repaired = json.loads(monster_path.read_text(encoding="utf-8"))
        self.assertEqual(repaired.get("size"), "Medium")
        self.assertEqual(repaired.get("alignment"), "chaotic evil")
        self.assertEqual(repaired.get("armorClass"), 13)

    def test_monster_schema_completion_recovers_plural_compendium_slug(self) -> None:
        module_slug = "Toolkit_Readiness_Module"
        module_dir = self.workspace / "modules" / module_slug
        monsters_dir = module_dir / "monsters"
        monsters_dir.mkdir(parents=True, exist_ok=True)

        monster_path = monsters_dir / "salt_wraith.json"
        monster_path.write_text(
            json.dumps(
                {
                    "name": "Salt Wraith",
                    "type": "undead",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        compendium = {
            "salt_wraiths": {
                "name": "Salt Wraiths",
                "size": "Medium",
                "alignment": "chaotic evil",
                "armorClass": 14,
            }
        }

        with patch(
            "utils.module_monster_authority.load_monster_compendium_lookup",
            return_value=compendium,
        ):
            result = readiness_gate._deterministic_repair_monster_schema(
                module_slug,
                module_dir,
            )

        self.assertEqual(result.get("status"), "changed")
        repaired = json.loads(monster_path.read_text(encoding="utf-8"))
        self.assertEqual(repaired.get("size"), "Medium")
        self.assertEqual(repaired.get("alignment"), "chaotic evil")
        self.assertEqual(repaired.get("armorClass"), 14)

    def test_validator_driven_reference_closure_uses_expected_paths(self) -> None:
        validation_report = _make_validation_report(
            {
                "reference_integrity": {
                    "failed": 1,
                    "errors": [
                        "Echoes of the Party in The Mindweft Expanse/Twilight Cachehouse -> expected monsters/echoes_of_the_party.json"
                    ],
                }
            },
            1,
        )

        with patch(
            "utils.module_monster_authority.materialize_authorized_monster_file",
            return_value={"ok": True, "source": "existing"},
        ):
            result = readiness_gate._deterministic_close_monster_references(
                "Toolkit_Readiness_Module",
                validation_report,
            )

        self.assertEqual(result.get("status"), "skipped")
        self.assertEqual(result.get("reason"), "validator_reference_closure")
        self.assertEqual(result.get("target_slugs"), ["echoes_of_the_party"])

    def test_plot_prerequisite_repair_supports_list_shape(self) -> None:
        module_dir = self.workspace / "modules" / "Toolkit_Readiness_Module"
        module_dir.mkdir(parents=True, exist_ok=True)
        plot_path = module_dir / "module_plot.json"
        plot_path.write_text(
            json.dumps(
                {
                    "plotPoints": [
                        {"id": "PP017", "title": "Sanctuary"},
                        {"id": "PP018", "title": "Finale"},
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        result = readiness_gate._deterministic_fix_plot_prerequisites(module_dir)
        self.assertEqual(result.get("status"), "changed")

        plot_data = json.loads(plot_path.read_text(encoding="utf-8"))
        points = plot_data.get("plotPoints") or []
        pp018 = next((p for p in points if p.get("id") == "PP018"), {})
        self.assertEqual(pp018.get("prerequisites"), ["PP017"])

    def test_plot_prerequisite_repair_targets_validator_edge_before_terminal(self) -> None:
        module_dir = self.workspace / "modules" / "Toolkit_Readiness_Module"
        module_dir.mkdir(parents=True, exist_ok=True)
        plot_path = module_dir / "module_plot.json"
        plot_path.write_text(
            json.dumps(
                {
                    "plotPoints": [
                        {"id": "PP017", "title": "Lead", "nextPoints": ["PP018"]},
                        {"id": "PP018", "title": "Conclusion", "nextPoints": ["PP019"]},
                        {
                            "id": "PP019",
                            "title": "Terminal",
                            "nextPoints": [],
                            "prerequisites": ["PP018"],
                        },
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        validation_report = _make_validation_report(
            {
                "plot_progression": {
                    "failed": 1,
                    "errors": [
                        "modules/X/module_plot.json: conclusion/finale plot PP018 missing explicit prerequisite gate (upstream: PP017)"
                    ],
                }
            },
            1,
        )

        result = readiness_gate._deterministic_fix_plot_prerequisites_from_validation(
            module_dir,
            validation_report,
        )
        self.assertEqual(result.get("status"), "changed")
        self.assertEqual(result.get("target"), "PP018")
        self.assertEqual(result.get("upstream"), "PP017")

        plot_data = json.loads(plot_path.read_text(encoding="utf-8"))
        points = plot_data.get("plotPoints") or []
        pp018 = next((p for p in points if p.get("id") == "PP018"), {})
        pp019 = next((p for p in points if p.get("id") == "PP019"), {})
        self.assertEqual(pp018.get("prerequisites"), ["PP017"])
        self.assertEqual(pp019.get("prerequisites"), ["PP018"])

    def test_spatial_contradictions_unchanged_escalates_structural_debt(self) -> None:
        validation_report = _make_validation_report(
            {
                "spatial_contract": {
                    "failed": 1,
                    "errors": [
                        "GLQ001.json: connected rooms G03->G04 are not cardinally adjacent"
                    ],
                }
            },
            1,
        )

        original_spatial = readiness_gate._deterministic_fix_spatial_contract
        original_validator = readiness_gate._run_validator
        try:
            readiness_gate._deterministic_fix_spatial_contract = lambda module_dir: {
                "status": "skipped",
                "reason": "spatial_remediation",
                "remediation": {"changed": 0},
            }
            readiness_gate._run_validator = lambda module_slug: dict(validation_report)

            result = readiness_gate._run_deterministic_repairs(
                module_slug="Toolkit_Readiness_Module",
                module_dir=self.workspace / "modules" / "Toolkit_Readiness_Module",
                failure_categories={"spatial_contract": 1},
                validation_report=validation_report,
            )

            spatial = (result.get("repairs") or {}).get("spatial_contract") or {}
            self.assertEqual(spatial.get("status"), "failed")
            self.assertEqual(spatial.get("reason"), "spatial_contradictions_unchanged")
            self.assertEqual(spatial.get("debt_classification"), "author_structural_debt")
        finally:
            readiness_gate._deterministic_fix_spatial_contract = original_spatial
            readiness_gate._run_validator = original_validator

    def test_spatial_map_parity_sync_updates_external_map_coordinates(self) -> None:
        module_dir = self.workspace / "modules" / "Toolkit_Readiness_Module"
        areas_dir = module_dir / "areas"
        areas_dir.mkdir(parents=True, exist_ok=True)

        area_payload = {
            "areaId": "GLQ001",
            "locations": [
                {
                    "locationId": "G03",
                    "coordinates": "X12Y10",
                    "connectivity": ["G04"],
                },
                {
                    "locationId": "G04",
                    "coordinates": "X13Y10",
                    "connectivity": ["G03"],
                },
            ],
        }
        map_payload = {
            "rooms": [
                {
                    "id": "G03",
                    "coordinates": "X10Y11",
                    "connections": ["G04"],
                    "directions": {"north": "G04"},
                },
                {
                    "id": "G04",
                    "coordinates": "X12Y10",
                    "connections": ["G03"],
                    "directions": {"west": "G03"},
                },
            ],
            "startRoom": "G03",
        }

        (areas_dir / "GLQ001.json").write_text(
            json.dumps(area_payload, indent=2), encoding="utf-8"
        )
        (module_dir / "map_GLQ001.json").write_text(
            json.dumps(map_payload, indent=2), encoding="utf-8"
        )

        validation_report = _make_validation_report(
            {
                "spatial_contract": {
                    "failed": 1,
                    "errors": [
                        "GLQ001.json <-> map_GLQ001.json: connected rooms G03->G04 are not cardinally adjacent (X10Y11 -> X12Y10)"
                    ],
                }
            },
            1,
        )

        result = readiness_gate._deterministic_sync_external_map_parity(
            module_dir,
            validation_report,
        )
        self.assertEqual(result.get("status"), "changed")
        self.assertIn("map_GLQ001.json", result.get("changed_maps") or [])

        repaired_map = json.loads((module_dir / "map_GLQ001.json").read_text(encoding="utf-8"))
        rooms = {room["id"]: room for room in repaired_map.get("rooms", [])}
        self.assertEqual(rooms["G03"].get("coordinates"), "X12Y10")
        self.assertEqual(rooms["G04"].get("coordinates"), "X13Y10")
        self.assertEqual(rooms["G03"].get("directions"), {"east": "G04"})
        self.assertEqual(rooms["G04"].get("directions"), {"west": "G03"})

    def test_plot_prerequisite_repair_backfills_finale_dependency(self) -> None:
        module_dir = self.workspace / "modules" / "Toolkit_Readiness_Module"
        module_dir.mkdir(parents=True, exist_ok=True)
        plot_path = module_dir / "module_plot.json"
        plot_path.write_text(
            json.dumps(
                {
                    "plotPoints": {
                        "PP017": {
                            "title": "Find the sanctuary",
                            "prerequisites": ["PP016"],
                        },
                        "PP018": {
                            "title": "Final confrontation",
                            "description": "Resolve the mindscape.",
                        },
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        result = readiness_gate._deterministic_fix_plot_prerequisites(module_dir)
        self.assertEqual(result.get("status"), "changed")

        plot_data = json.loads(plot_path.read_text(encoding="utf-8"))
        pp018 = (plot_data.get("plotPoints") or {}).get("PP018") or {}
        self.assertEqual(pp018.get("prerequisites"), ["PP017"])


if __name__ == "__main__":
    unittest.main()
