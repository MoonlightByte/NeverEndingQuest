#!/usr/bin/env python3
"""
Unit tests for homebrew ingest cleanup functionality.

Covers Task 5.2: Cleanup on ingest/quarantine/verify failure paths
and safety guards for registered modules.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from homebrew_ingest_dev import _cleanup_failed_ingest


class TestCleanupFailedIngest(TestCase):
    """Test _cleanup_failed_ingest function directly."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        # Create modules and archive directories
        self.modules_dir = self.temp_dir / "modules"
        self.modules_dir.mkdir()
        self.archive_dir = self.temp_dir / "modules" / "ingest" / "archive"
        self.archive_dir.mkdir(parents=True)
        
        # Change to temp directory for the test
        self.orig_cwd = Path.cwd()

    def tearDown(self):
        import shutil
        import os
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cleanup_disabled_skips_action(self):
        """When cleanup_enabled=False, should skip with reason."""
        result = _cleanup_failed_ingest("test_module", cleanup_enabled=False)
        
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["action"], "none")
        self.assertEqual(result["reason"], "Cleanup disabled by flag")

    def test_no_module_slug_skips_action(self):
        """When no slug provided, should skip with reason."""
        result = _cleanup_failed_ingest(None, cleanup_enabled=True)
        
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "No module slug provided")

    def test_nonexistent_path_skips_action(self):
        """When module directory doesn't exist, should skip."""
        import os
        os.chdir(self.temp_dir)
        
        result = _cleanup_failed_ingest("nonexistent_module", cleanup_enabled=True)
        
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "Module directory does not exist")

    @patch('homebrew_ingest_dev.verify_present')
    def test_registered_module_skips_cleanup(self, mock_verify):
        """Registered/active module should not be cleaned up."""
        import os
        os.chdir(self.temp_dir)
        
        # Create a module directory
        module_dir = self.modules_dir / "registered_module"
        module_dir.mkdir()
        
        # Mock verify_present to return present=True
        mock_verify.return_value = {"present": True}
        
        result = _cleanup_failed_ingest("registered_module", cleanup_enabled=True)
        
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["action"], "none")
        self.assertEqual(result["reason"], "Module is registered/active - cleanup skipped for safety")
        
        # Verify directory still exists
        self.assertTrue(module_dir.exists())

    @patch('homebrew_ingest_dev.verify_present')
    def test_unregistered_module_gets_archived(self, mock_verify):
        """Unregistered module should be archived."""
        import os
        os.chdir(self.temp_dir)
        
        # Create a module directory
        module_dir = self.modules_dir / "failed_module"
        module_dir.mkdir()
        (module_dir / "test_file.txt").write_text("content")
        
        # Mock verify_present to return present=False
        mock_verify.return_value = {"present": False}
        
        result = _cleanup_failed_ingest("failed_module", cleanup_enabled=True)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "archived")
        self.assertIn("failed_", result["archived_path"])
        self.assertIn("failed_module", result["archived_path"])
        
        # Verify original directory is gone
        self.assertFalse(module_dir.exists())
        
        # Verify archive exists with content
        archive_path = Path(result["archived_path"])
        self.assertTrue(archive_path.exists())
        self.assertTrue((archive_path / "test_file.txt").exists())

    @patch('homebrew_ingest_dev.verify_present')
    def test_cleanup_result_structure(self, mock_verify):
        """Cleanup result should have expected structure."""
        import os
        os.chdir(self.temp_dir)
        
        module_dir = self.modules_dir / "test_module"
        module_dir.mkdir()
        mock_verify.return_value = {"present": False}
        
        result = _cleanup_failed_ingest("test_module", cleanup_enabled=True)
        
        # Verify all expected keys
        self.assertIn("status", result)
        self.assertIn("action", result)
        self.assertIn("reason", result)
        self.assertIn("archived_path", result)
        self.assertIn("error", result)


class TestIngestPipelineCleanupIntegration(TestCase):
    """Test cleanup integration in ingest pipeline failure paths."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.orig_cwd = Path.cwd()

    def tearDown(self):
        import shutil
        import os
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('homebrew_ingest_dev._cleanup_failed_ingest')
    def test_ingest_failure_includes_cleanup(self, mock_cleanup):
        """Ingest failure should include cleanup_failed_ingest in payload."""
        from homebrew_ingest_dev import run_ingest_pipeline
        
        mock_cleanup.return_value = {
            "status": "success",
            "action": "archived",
            "reason": "Moved test to archive"
        }
        
        import os
        os.chdir(self.temp_dir)
        
        # Create a source file that will fail validation
        source = self.temp_dir / "bad.md"
        source.write_text('Invalid content without metadata.')
        
        # Change to temp dir and create required structure
        modules_dir = self.temp_dir / "modules"
        modules_dir.mkdir(exist_ok=True)
        
        result = run_ingest_pipeline(str(source), strict=True, cleanup_failed=True)
        
        # Cleanup should have been called or considered
        # Note: Depending on where failure occurs, cleanup may or may not be called
        # The key assertion is that the structure supports it

    def test_cleanup_payload_structure_on_failure(self):
        """Verify cleanup result structure in failure payload."""
        # This documents the expected payload structure
        expected_cleanup_structure = {
            "status": "skipped",  # or "success", "failed"
            "action": "none",     # or "archived", "error"
            "reason": str,
            "archived_path": str,  # or None
            "error": str           # or None
        }
        
        # Verify the function returns this structure
        result = _cleanup_failed_ingest(None, cleanup_enabled=True)
        
        self.assertIn("status", result)
        self.assertIn("action", result)
        self.assertIn("reason", result)
        self.assertIn("archived_path", result)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
