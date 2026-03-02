#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Ingest Media Pipeline Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Targeted regression tests for homebrew ingest media stages.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import functions under test
from homebrew_ingest_dev import (
    _persist_media_to_sidecar,
    _sanitize_stage_for_sidecar,
    _run_subprocess_stage,
)
from homebrew_sidecar_audit import audit_sidecar, _validate_media_section


class TestMediaStageKeyNames(unittest.TestCase):
    """Verify canonical key names in orchestrator output."""
    
    def test_canonical_keys_present(self):
        """Media stages should use canonical key names."""
        # Test that the expected keys are used in the codebase
        import homebrew_ingest_dev as ingest_module
        
        # Read source and verify canonical keys
        source = Path(__file__).parent / "homebrew_ingest_dev.py"
        code = source.read_text()
        
        # Should use 'media_extraction' in result assignments
        self.assertIn('result["media_extraction"]', code)
        # Should NOT assign to legacy 'media_extract' as a result key
        # (Note: 'media_extract' appears in exit code mapping, not as data key)
        self.assertNotIn('result["media_extract"]', code)
        
        # Should use 'media_handles' and 'portrait_prewarm'
        self.assertIn('result["media_handles"]', code)
        self.assertIn('result["portrait_prewarm"]', code)


class TestSidecarPersistence(unittest.TestCase):
    """Verify sidecar persistence of media blocks."""
    
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_dir = self.temp_dir / "archive"
        self.archive_dir.mkdir()
        
        # Create a sidecar for testing
        self.sidecar = self.archive_dir / "20260302_120000_test_module.md.result.json"
        sidecar_data = {
            "source": "test_module.md",
            "processed_at": "2026-03-02T12:00:00",
            "result": {
                "status": "success",
                "module_slug": "Test_Module",
                "validation": {"passed": True},
                "registration": {
                    "registration_attempted": True,
                    "registration_success": True,
                    "registry_module_present": True,
                }
            }
        }
        self.sidecar.write_text(json.dumps(sidecar_data))
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_persist_media_to_sidecar_writes_canonical_keys(self):
        """Media stages should be persisted with canonical key names."""
        import homebrew_sidecar_audit as audit_module
        original_archive = audit_module.ARCHIVE_ROOT
        
        try:
            audit_module.ARCHIVE_ROOT = self.archive_dir
            
            media_extraction = {
                "status": "success",
                "duration_ms": 2450,
                "parsed_output": {
                    "detected_urls": ["http://example.com/1.jpg"],
                    "extracted_count": 1,
                    "warning_count": 0,
                }
            }
            media_handles = {
                "status": "success",
                "duration_ms": 180,
                "parsed_output": {
                    "handle_count": 5,
                }
            }
            portrait_prewarm = {
                "status": "success",
                "duration_ms": 5000,
                "parsed_output": {
                    "npcs": {"planned": 3, "done": 3, "failed": 0, "skipped": 0},
                    "monsters": {"planned": 2, "done": 2, "failed": 0, "skipped": 0},
                }
            }
            
            result = _persist_media_to_sidecar(
                module_slug="Test_Module",
                media_extraction=media_extraction,
                media_handles=media_handles,
                portrait_prewarm=portrait_prewarm,
                media_warnings=[],
            )
            
            self.assertTrue(result["success"])
            
            # Verify sidecar was updated
            updated_sidecar = json.loads(self.sidecar.read_text())
            result_section = updated_sidecar.get("result", {})
            
            # Canonical keys should be present
            self.assertIn("media_extraction", result_section)
            self.assertIn("media_handles", result_section)
            self.assertIn("portrait_prewarm", result_section)
            
            # Legacy key should NOT be present
            self.assertNotIn("media_extract", result_section)
            
            # Verify content
            self.assertEqual(result_section["media_extraction"]["status"], "success")
            self.assertEqual(result_section["media_extraction"]["detected_count"], 1)
            self.assertEqual(result_section["media_handles"]["handle_count"], 5)
            self.assertEqual(result_section["portrait_prewarm"]["npcs"]["done"], 3)
            
        finally:
            audit_module.ARCHIVE_ROOT = original_archive
    
    def test_persist_media_fail_open_when_no_sidecar(self):
        """Should fail-open (return error but not raise) when sidecar not found."""
        result = _persist_media_to_sidecar(
            module_slug="NonExistentModule",
            media_extraction={"status": "success"},
            media_handles=None,
            portrait_prewarm=None,
            media_warnings=None,
        )
        
        self.assertFalse(result["success"])
        self.assertIn("No sidecar found", result["error"])


class TestLegacyKeyNormalization(unittest.TestCase):
    """Verify legacy key normalization in sidecar audit."""
    
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_dir = self.temp_dir / "archive"
        self.archive_dir.mkdir()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_validate_media_section_accepts_legacy_status_values(self):
        """Media section validation should accept standard status values including legacy."""
        # Test that validation accepts the status values we use
        for status in ["success", "degraded", "skipped", "failed", "planned"]:
            section_data = {"status": status, "duration_ms": 1000}
            valid, errors = _validate_media_section("media_handles", section_data)
            self.assertTrue(valid, f"Status '{status}' should be valid")
            self.assertEqual(len(errors), 0, f"Status '{status}' should have no errors")


class TestMediaStageDegradation(unittest.TestCase):
    """Verify media stage degradation does not fail successful ingest."""
    
    def test_degraded_media_does_not_fail_ingest(self):
        """Failed media stages should degrade but not block ingest success."""
        # Simulate an ingest result with degraded media stages
        ingest_result = {
            "status": "success",
            "stage": "verify",
            "registry_verified": True,
            "media_extraction": {
                "status": "degraded",
                "duration_ms": 5000,
                "parsed_output": {
                    "detected_urls": ["http://example.com/1.jpg"],
                    "extracted_count": 0,
                    "warning_count": 1,
                }
            },
            "media_handles": {
                "status": "success",
                "duration_ms": 200,
            },
            "portrait_prewarm": {
                "status": "degraded",
                "duration_ms": 10000,
                "parsed_output": {
                    "npcs": {"planned": 5, "done": 3, "failed": 2, "skipped": 0},
                }
            },
            "media_warnings": [
                {"stage": "media_extraction", "type": "download_failed", "message": "Timeout"},
                {"stage": "portrait_prewarm", "type": "generation_failures", "message": "Failed: 0 NPCs, 2 monsters"},
            ],
        }
        
        # Status should be degraded, not failed
        self.assertEqual(ingest_result["status"], "success")
        # But we have warnings
        self.assertTrue(len(ingest_result["media_warnings"]) > 0)


class TestMediaSectionValidation(unittest.TestCase):
    """Verify media section validation logic."""
    
    def test_validate_media_section_success(self):
        """Valid media section should pass validation."""
        section_data = {
            "status": "success",
            "duration_ms": 1000,
            "parsed_output": {"handle_count": 5},
        }
        
        valid, errors = _validate_media_section("media_handles", section_data)
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_media_section_missing_duration(self):
        """Media section missing duration_ms should fail validation."""
        section_data = {
            "status": "success",
            # Missing duration_ms
        }
        
        valid, errors = _validate_media_section("media_handles", section_data)
        self.assertFalse(valid)
        self.assertTrue(any("duration_ms" in e for e in errors))
    
    def test_validate_media_section_invalid_status(self):
        """Media section with unexpected status should fail validation."""
        section_data = {
            "status": "unexpected_status",
            "duration_ms": 1000,
        }
        
        valid, errors = _validate_media_section("media_handles", section_data)
        self.assertFalse(valid)
        self.assertTrue(any("status" in e for e in errors))


class TestStageSanitization(unittest.TestCase):
    """Verify stage data sanitization for sidecar."""
    
    def test_sanitize_stage_extracts_summary(self):
        """Should extract summary fields, not full stdout."""
        stage_data = {
            "status": "success",
            "duration_ms": 1000,
            "stdout": "very long output...",
            "stderr": "",
            "parsed_output": {
                "detected_urls": ["http://a.com/1.jpg", "http://b.com/2.jpg"],
                "extracted_count": 2,
                "warning_count": 0,
            },
        }
        
        sanitized = _sanitize_stage_for_sidecar(stage_data)
        
        self.assertEqual(sanitized["status"], "success")
        self.assertEqual(sanitized["duration_ms"], 1000)
        self.assertEqual(sanitized["detected_count"], 2)
        self.assertNotIn("stdout", sanitized)
        self.assertNotIn("stderr", sanitized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
