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

from homebrew_ingest_dev import run_ingest_pipeline


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
        source.write_text('Just random text without structure.')
        
        result = run_ingest_pipeline(str(source), strict=True, dry_run_only=True)
        
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "preflight")
        self.assertEqual(result["exit_code"], 1)

    def test_stops_at_dry_run_for_validation_failure(self):
        """Should halt when dry-run validation fails."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Start\nStart.\n\n## Room 2: End\nEnd.')
        
        result = run_ingest_pipeline(str(source), strict=True, dry_run_only=True)
        
        # Should reach dry_run stage before potential quarantine
        self.assertIn(result["stage"], ["dry_run", "ingest", "verify"])

    def test_dry_run_mode_returns_success_note(self):
        """Should return success with note in dry-run mode."""
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Start\nStart.')
        
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

    @patch('homebrew_ingest_dev.import_homebrewery_adventure_to_module')
    @patch('homebrew_ingest_dev.verify_present')
    def test_successful_dry_run_pipeline(self, mock_verify, mock_import):
        """Should return success with all stage data in dry-run mode."""
        # Mock dry-run result
        mock_import.return_value = {
            "status": "dry_run",
            "module_slug": "Test_Module",
            "validation": {"passed": True, "errors": [], "success_rate": "100%"},
            "preview": {"room_count": 2, "area": "TST001"}
        }
        
        # Note: In dry-run mode, registry verification is skipped
        # So we don't need to mock verify_present for this test
        
        source = self.temp_dir / "test.md"
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Start\nStart.')
        
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
        source.write_text('```metadata\ntitle: Test\nauthor: A\ndescription: D\n```\n\n## Room 1: Start\nStart room.\n\n## Room 2: Chamber\nChamber.')
        
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
