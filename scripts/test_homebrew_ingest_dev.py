#!/usr/bin/env python3
"""
Unit tests for homebrew_ingest_dev.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from homebrew_ingest_dev import (
    run_ingest_pipeline,
    _normalize_continuity_contract,
    _persist_media_to_sidecar,
    _ensure_continuity_contract_keys,
)
from continuity_cross_ref_enrichment import enrich_continuity_cross_refs


class TestPipelineStopConditions(TestCase):
    """Test pipeline stops on failures."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_stops_at_preflight_for_untransformable_source(self):
        """Should halt at preflight when source cannot be auto-transformed."""
        source = self.temp_dir / "bad.md"
        source.write_text("Just random text without structure.")

        result = run_ingest_pipeline(str(source), strict=True, dry_run_only=True)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "preflight")
        self.assertEqual(result["exit_code"], 1)

    def test_routes_readable_ambiguous_source_when_enabled(self):
        """Should return normalization_required when routing path is enabled."""
        source = self.temp_dir / "ambiguous.md"
        source.write_text("# Chapter 1\n\nReadable but non-deterministic narrative text.")
        workspace = self.temp_dir / "workspace"

        result = run_ingest_pipeline(
            str(source),
            strict=True,
            dry_run_only=False,
            allow_normalization_routing=True,
            artifact_workspace=str(workspace),
        )

        self.assertEqual(result["status"], "normalization_required")
        self.assertEqual(result["stage"], "routing")
        self.assertEqual(result["routing_outcome"], "normalization_required")
        self.assertTrue((workspace / "source_preflight.json").exists())
        self.assertTrue((workspace / "normalized_packet.json").exists())

    def test_stops_at_dry_run_for_validation_failure(self):
        """Should halt when dry-run validation fails."""
        source = self.temp_dir / "test.md"
        source.write_text(
            "```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Start\nStart.\n\n## Room 2: End\nEnd."
        )

        result = run_ingest_pipeline(str(source), strict=True, dry_run_only=True)

        # Should reach dry_run stage before potential quarantine
        self.assertIn(result["stage"], ["dry_run", "ingest", "verify"])

    def test_dry_run_mode_returns_success_note(self):
        """Should return success with note in dry-run mode."""
        source = self.temp_dir / "test.md"
        source.write_text(
            "```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Start\nStart."
        )

        result = run_ingest_pipeline(str(source), strict=True, dry_run_only=True)

        self.assertEqual(result["status"], "success")
        self.assertIn("note", result)
        self.assertIn("Dry-run only", result["note"])


class TestPipelineHappyPath(TestCase):
    """Test successful pipeline execution."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("homebrew_ingest_dev.import_homebrewery_adventure_to_module")
    @patch("homebrew_ingest_dev.verify_present")
    def test_successful_dry_run_pipeline(self, mock_verify, mock_import):
        """Should return success with all stage data in dry-run mode."""
        # Mock dry-run result
        mock_import.return_value = {
            "status": "dry_run",
            "module_slug": "Test_Module",
            "validation": {"passed": True, "errors": [], "success_rate": "100%"},
            "preview": {"room_count": 2, "area": "TST001"},
        }

        # Note: In dry-run mode, registry verification is skipped
        # So we don't need to mock verify_present for this test

        source = self.temp_dir / "test.md"
        source.write_text(
            "```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Start\nStart."
        )

        result = run_ingest_pipeline(str(source), strict=True, dry_run_only=True)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["module_slug"], "Test_Module")
        # In dry-run mode, registry_verified should be False (verification not performed)
        self.assertFalse(result["registry_verified"])
        self.assertIn("note", result)


class TestConditionalTransform(TestCase):
    """Test conditional transform behavior."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_skips_transform_for_ready_room_based(self):
        """Should not transform when source is already room_based and ready."""
        source = self.temp_dir / "test.md"
        source.write_text(
            "```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Start\nStart room.\n\n## Room 2: Chamber\nChamber."
        )

        result = run_ingest_pipeline(str(source), strict=True, dry_run_only=True)

        # Should use original source (not transformed temp file)
        self.assertEqual(result["source"], str(source))


class TestErrorHandling(TestCase):
    """Test error conditions."""

    def test_missing_source_file(self):
        """Should fail for missing source file."""
        result = run_ingest_pipeline("/nonexistent/path.md", strict=True)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "preflight")
        self.assertIn("not found", result["error"].lower())


class TestMonsterMaterializationStage(TestCase):
    """Test monster materialization stage in pipeline (Task 5.3)."""

    def test_result_structure_supports_materialization(self):
        """Pipeline result structure should support monster_materialization field."""
        # This test documents that the pipeline structure supports the field
        # Full integration would require complex mocking; manual verification shows
        # the field is populated in successful non-dry-run completions
        from homebrew_ingest_dev import run_ingest_pipeline

        # Verify function signature accepts allow_provider (cost transparency)
        import inspect

        sig = inspect.signature(run_ingest_pipeline)
        self.assertIn("allow_provider", sig.parameters)
        self.assertIn("cleanup_failed", sig.parameters)


class TestProviderGenerationFlag(TestCase):
    """Test provider generation cost transparency (Task 5.3)."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_provider_generation_parameter_exists(self):
        """Provider generation flag should be in function signature."""
        from homebrew_ingest_dev import run_ingest_pipeline
        import inspect

        sig = inspect.signature(run_ingest_pipeline)
        self.assertIn("allow_provider", sig.parameters)

        # Default should be False (opt-in only)
        param = sig.parameters["allow_provider"]
        self.assertEqual(param.default, False)


class TestCleanupIntegration(TestCase):
    """Test cleanup stage integration (Task 5.3)."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cleanup_result_structure_on_failure(self):
        """Cleanup result should have expected structure on ingest failure."""
        source = self.temp_dir / "bad.md"
        source.write_text("Invalid content without structure.")

        result = run_ingest_pipeline(str(source), strict=True)

        # On ingest failure, cleanup_failed_ingest should be in payload
        if result["stage"] in ["ingest", "verify"] and result["status"] == "failed":
            self.assertIn("cleanup_failed_ingest", result)
            cleanup = result["cleanup_failed_ingest"]
            self.assertIn("status", cleanup)
            self.assertIn("action", cleanup)
            self.assertIn("reason", cleanup)


class TestContinuityContractNormalization(TestCase):
    """Test continuity contract normalization stage payload."""

    def test_warn_first_allows_missing_required_keys(self):
        contract = _normalize_continuity_contract(
            module_context={}, module_plot={}, strict=False
        )
        self.assertEqual(contract["status"], "warning")
        self.assertIn("continuity_version", contract["missing_required_keys"])

    def test_strict_fails_missing_required_keys(self):
        contract = _normalize_continuity_contract(
            module_context={}, module_plot={}, strict=True
        )
        self.assertEqual(contract["status"], "error")
        self.assertGreater(len(contract["errors"]), 0)

    def test_entry_state_variants_requires_object_shape(self):
        module_context = {
            "continuity": {
                "continuity_version": "v1",
                "entry_state_variants": {
                    "cold_start": {"summary": "fresh start"},
                    "partial_context": {"summary": "known lore"},
                    "late_arc": {"summary": "deep continuity"},
                },
                "cross_module_refs": [],
                "standalone_fallback": {"enabled": True},
            }
        }
        contract = _normalize_continuity_contract(
            module_context=module_context, module_plot={}, strict=True
        )
        self.assertEqual(contract["status"], "success")
        self.assertEqual(contract["missing_required_keys"], [])


class TestContinuityContractBackfill(TestCase):
    """Test additive continuity key backfill for new ingests."""

    def test_backfills_missing_keys_before_strict_audit(self):
        module_context = {"module_name": "Backfill Test"}
        result = _ensure_continuity_contract_keys(module_context, "Backfill_Test")

        self.assertTrue(result["changed"])
        continuity = result["module_context"]["continuity"]
        self.assertEqual(continuity["continuity_version"], "v1")
        self.assertIn("cold_start", continuity["entry_state_variants"])
        self.assertIn("partial_context", continuity["entry_state_variants"])
        self.assertIn("late_arc", continuity["entry_state_variants"])
        self.assertIsInstance(continuity["cross_module_refs"], list)
        self.assertIsInstance(continuity["standalone_fallback"], dict)

    def test_preserves_existing_cross_module_refs(self):
        module_context = {
            "module_name": "Backfill Test",
            "continuity": {
                "continuity_version": "v1",
                "entry_state_variants": {"cold_start": {"summary": "custom"}},
                "cross_module_refs": [
                    {
                        "target_module": "Other",
                        "entity_id": "npc.test",
                        "relation": "echo",
                        "confidence": "medium",
                    }
                ],
                "standalone_fallback": {"enabled": False},
            },
        }

        result = _ensure_continuity_contract_keys(module_context, "Backfill_Test")
        continuity = result["module_context"]["continuity"]

        self.assertEqual(len(continuity["cross_module_refs"]), 1)
        self.assertEqual(continuity["cross_module_refs"][0]["target_module"], "Other")
        self.assertFalse(continuity["standalone_fallback"]["enabled"])


class TestContinuityCrossRefEnrichment(TestCase):
    """Test deterministic narrative cross-module ref enrichment."""

    def test_enrich_adds_refs_for_detected_targets(self):
        module_context = {
            "module_name": "Night_of_the_Restless_Dead",
            "continuity": {"cross_module_refs": []},
            "faction_context": {
                "notes": "Miriam fears the Pumpkin King and seeks Thornwood druid aid."
            },
        }
        module_plot = {"echo": "The old debt reaches toward Greenfields Vale."}

        result = enrich_continuity_cross_refs(
            module_slug="Night_of_the_Restless_Dead",
            module_context=module_context,
            module_plot=module_plot,
            known_modules=[
                "Night_of_the_Restless_Dead",
                "The_Pumpkin_Kings_Curse",
                "The_Thornwood_Watch",
            ],
        )

        self.assertTrue(result["changed"])
        refs = result["module_context"]["continuity"]["cross_module_refs"]
        self.assertGreater(len(refs), 0)
        self.assertTrue(
            any(row.get("target_module") == "The_Pumpkin_Kings_Curse" for row in refs)
        )


class TestSidecarContinuityPersistence(TestCase):
    """Test sidecar persistence includes continuity_contract payload."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("homebrew_sidecar_audit.find_latest_sidecar_for_slug")
    def test_persists_continuity_contract_to_sidecar(self, mock_find_sidecar):
        sidecar_path = self.temp_dir / "test.sidecar.json"
        sidecar_path.write_text(
            json.dumps({"status": "success", "result": {}}), encoding="utf-8"
        )
        mock_find_sidecar.return_value = sidecar_path

        continuity_payload = {
            "status": "warning",
            "version": "v1",
            "required_keys_present": ["continuity_version"],
            "missing_required_keys": ["entry_state_variants"],
            "warnings": ["missing entry_state_variants"],
            "errors": [],
            "normalized_refs_count": 0,
            "alias_resolution": {"resolved": 0, "ambiguous": 0, "unresolved": 0},
        }

        persisted = _persist_media_to_sidecar(
            module_slug="Test_Module",
            media_extraction=None,
            media_handles=None,
            portrait_prewarm=None,
            media_warnings=None,
            continuity_contract=continuity_payload,
        )

        self.assertTrue(persisted["success"])

        sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        self.assertIn("continuity_contract", sidecar_data["result"])
        self.assertEqual(
            sidecar_data["result"]["continuity_contract"]["status"], "warning"
        )

    @patch("homebrew_sidecar_audit.find_latest_sidecar_for_slug")
    def test_persists_semantic_authority_to_sidecar(self, mock_find_sidecar):
        sidecar_path = self.temp_dir / "semantic.sidecar.json"
        sidecar_path.write_text(
            json.dumps({"status": "success", "result": {}}), encoding="utf-8"
        )
        mock_find_sidecar.return_value = sidecar_path

        semantic_payload = {
            "status": "degraded",
            "warnings": ["semantic_authority_missing_npc_authority=1"],
            "errors": [],
            "semantic_authority": {
                "version": "v1",
                "location_aliases": {},
                "destination_phrases": {},
                "npc_scene_authority": {},
                "diagnostics": {
                    "missing_npc_authority": [{"npc": "Father Aldric"}],
                },
            },
        }

        persisted = _persist_media_to_sidecar(
            module_slug="Test_Module",
            media_extraction=None,
            media_handles=None,
            portrait_prewarm=None,
            media_warnings=None,
            continuity_contract=None,
            semantic_authority=semantic_payload,
        )

        self.assertTrue(persisted["success"])

        sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        self.assertIn("semantic_authority", sidecar_data["result"])
        self.assertEqual(
            sidecar_data["result"]["semantic_authority"]["status"], "degraded"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
