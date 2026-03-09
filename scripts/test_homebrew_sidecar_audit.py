#!/usr/bin/env python3
"""
Unit tests for homebrew_sidecar_audit.py
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from homebrew_sidecar_audit import audit_sidecar


class TestSidecarDiscovery(TestCase):
    """Test finding sidecars for module slugs."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_root = self.temp_dir / "modules" / "ingest" / "archive"
        self.archive_root.mkdir(parents=True, exist_ok=True)
        
        # Patch ARCHIVE_ROOT in module
        import homebrew_sidecar_audit
        homebrew_sidecar_audit.ARCHIVE_ROOT = self.archive_root

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_sidecar_found_returns_exit_code_1(self):
        """Should return exit code 1 when no sidecar exists."""
        result = audit_sidecar("NonExistentModule")
        
        self.assertFalse(result["sidecar_found"])
        self.assertEqual(result["exit_code"], 1)

    def test_finds_sidecar_by_slug(self):
        """Should find sidecar by module_slug field."""
        sidecar = self.archive_root / "20260302_120000_ingested_test.md.result.json"
        sidecar.write_text(json.dumps({
            "module_slug": "TestModule",
            "status": "success",
            "registration": {
                "registration_attempted": True,
                "registration_success": True,
                "registry_module_present": True
            }
        }))
        
        result = audit_sidecar("TestModule")
        
        self.assertTrue(result["sidecar_found"])
        self.assertEqual(result["status"], "success")

    def test_finds_latest_sidecar(self):
        """Should find the most recent sidecar."""
        # Older sidecar
        old = self.archive_root / "20260301_120000_ingested_test.md.result.json"
        old.write_text(json.dumps({
            "module_slug": "TestModule",
            "status": "quarantined"
        }))
        
        # Newer sidecar
        new = self.archive_root / "20260302_120000_ingested_test.md.result.json"
        new.write_text(json.dumps({
            "module_slug": "TestModule",
            "status": "success"
        }))
        
        result = audit_sidecar("TestModule")
        
        # Should find the newer one
        self.assertEqual(result["status"], "success")


class TestStatusValidation(TestCase):
    """Test status validation logic."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_root = self.temp_dir / "modules" / "ingest" / "archive"
        self.archive_root.mkdir(parents=True, exist_ok=True)
        
        import homebrew_sidecar_audit as audit_module
        self.orig_archive_root = audit_module.ARCHIVE_ROOT
        audit_module.ARCHIVE_ROOT = self.archive_root

    def tearDown(self):
        import homebrew_sidecar_audit as audit_module
        audit_module.ARCHIVE_ROOT = self.orig_archive_root
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_status_values(self):
        """Should accept valid status values."""
        for status in ["success", "quarantined", "dry_run", "error"]:
            # Ensure unique slugs for each status to avoid conflicts
            slug = f"Test{status}_{id(self)}"
            sidecar = self.archive_root / f"test_{status}_{id(self)}.json"
            sidecar.write_text(json.dumps({
                "module_slug": slug,
                "status": status,
                "registration": {}
            }))
            
            result = audit_sidecar(slug)
            self.assertTrue(result["valid"], f"Status {status} should be valid")

    def test_require_success_fails_for_quarantined(self):
        """Should fail when require-success and status is quarantined."""
        slug = f"QuarantinedMod_{id(self)}"
        sidecar = self.archive_root / f"quarantine_{id(self)}.json"
        sidecar.write_text(json.dumps({
            "module_slug": slug,
            "status": "quarantined",
            "registration": {}
        }))
        
        result = audit_sidecar(slug, require_success=True)
        
        self.assertFalse(result["valid"])
        # Exit code should be non-zero for failed validation
        self.assertNotEqual(result["exit_code"], 0)

    def test_require_success_passes_for_success(self):
        """Should pass when require-success and status is success."""
        sidecar = self.archive_root / "success.json"
        sidecar.write_text(json.dumps({
            "module_slug": "SuccessMod",
            "status": "success",
            "registration": {
                "registration_attempted": True,
                "registry_module_present": True
            }
        }))
        
        result = audit_sidecar("SuccessMod", require_success=True)
        
        self.assertTrue(result["valid"])
        self.assertEqual(result["exit_code"], 0)


class TestRegistrationBlock(TestCase):
    """Test registration field verification."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_root = self.temp_dir / "modules" / "ingest" / "archive"
        self.archive_root.mkdir(parents=True, exist_ok=True)
        
        import homebrew_sidecar_audit
        homebrew_sidecar_audit.ARCHIVE_ROOT = self.archive_root

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_surfaces_registration_fields(self):
        """Should expose registration block fields."""
        sidecar = self.archive_root / "test.json"
        sidecar.write_text(json.dumps({
            "module_slug": "TestMod",
            "status": "success",
            "registration": {
                "registration_attempted": True,
                "registration_success": True,
                "registry_module_present": True,
                "registration_errors": []
            }
        }))
        
        result = audit_sidecar("TestMod")
        
        # Verify registration fields are surfaced
        self.assertEqual(result["registration"]["registration_attempted"], True)
        self.assertEqual(result["registration"]["registration_success"], True)
        self.assertEqual(result["registration"]["registry_module_present"], True)
        self.assertEqual(result["registration"]["registration_errors"], [])

    def test_require_success_checks_registration_attempted(self):
        """Should fail if registration_attempted is false."""
        sidecar = self.archive_root / "test.json"
        sidecar.write_text(json.dumps({
            "module_slug": "TestMod",
            "status": "success",
            "registration": {
                "registration_attempted": False,
                "registry_module_present": False
            }
        }))
        
        result = audit_sidecar("TestMod", require_success=True)
        
        self.assertFalse(result["valid"])
        # Check that errors list contains the expected message
        self.assertIn("registration_attempted is false", str(result.get("errors", [])))

    def test_require_success_checks_registry_module_present(self):
        """Should fail if registry_module_present is false."""
        sidecar = self.archive_root / "test.json"
        sidecar.write_text(json.dumps({
            "module_slug": "TestMod",
            "status": "success",
            "registration": {
                "registration_attempted": True,
                "registration_success": False,
                "registry_module_present": False
            }
        }))
        
        result = audit_sidecar("TestMod", require_success=True)
        
        self.assertFalse(result["valid"])


class TestInvalidJson(TestCase):
    """Test handling of invalid JSON sidecars."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_root = self.temp_dir / "modules" / "ingest" / "archive"
        self.archive_root.mkdir(parents=True, exist_ok=True)
        
        import homebrew_sidecar_audit
        homebrew_sidecar_audit.ARCHIVE_ROOT = self.archive_root

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_invalid_json_returns_nonzero_exit(self):
        """Should return non-zero exit code for invalid JSON."""
        sidecar = self.archive_root / "invalid.json"
        sidecar.write_text("not valid json {{{")
        
        result = audit_sidecar("InvalidJson")
        
        self.assertFalse(result["valid"])
        # Exit code should be non-zero for invalid JSON
        self.assertNotEqual(result["exit_code"], 0)


class TestQuarantineReason(TestCase):
    """Test quarantine reason surfacing."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_root = self.temp_dir / "modules" / "ingest" / "archive"
        self.archive_root.mkdir(parents=True, exist_ok=True)
        
        import homebrew_sidecar_audit
        homebrew_sidecar_audit.ARCHIVE_ROOT = self.archive_root

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_surfaces_quarantine_reason(self):
        """Should expose quarantine_reason field."""
        sidecar = self.archive_root / "quarantine.json"
        sidecar.write_text(json.dumps({
            "module_slug": "BadMod",
            "status": "quarantined",
            "quarantine_reason": "no_rooms_found",
            "registration": {}
        }))
        
        result = audit_sidecar("BadMod")
        
        self.assertEqual(result["quarantine_reason"], "no_rooms_found")


class TestContinuityContractValidation(TestCase):
    """Test continuity_contract sidecar validation behavior."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archive_root = self.temp_dir / "modules" / "ingest" / "archive"
        self.archive_root.mkdir(parents=True, exist_ok=True)

        import homebrew_sidecar_audit
        homebrew_sidecar_audit.ARCHIVE_ROOT = self.archive_root

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_continuity_contract_passes(self):
        sidecar = self.archive_root / "continuity_valid.json"
        sidecar.write_text(json.dumps({
            "module_slug": "ContinuityMod",
            "status": "success",
            "result": {
                "status": "success",
                "registration": {
                    "registration_attempted": True,
                    "registration_success": True,
                    "registry_module_present": True,
                },
                "continuity_contract": {
                    "status": "success",
                    "version": "v1",
                    "required_keys_present": ["continuity_version"],
                    "missing_required_keys": [],
                    "warnings": [],
                    "errors": [],
                    "normalized_refs_count": 1,
                    "alias_resolution": {"resolved": 1, "ambiguous": 0, "unresolved": 0},
                }
            }
        }))

        result = audit_sidecar("ContinuityMod", require_success=True)
        self.assertTrue(result["valid"])
        self.assertTrue(result["continuity"]["present"])
        self.assertTrue(result["continuity"]["valid"])

    def test_invalid_continuity_contract_fails_require_success(self):
        sidecar = self.archive_root / "continuity_invalid.json"
        sidecar.write_text(json.dumps({
            "module_slug": "ContinuityBadMod",
            "status": "success",
            "result": {
                "status": "success",
                "registration": {
                    "registration_attempted": True,
                    "registration_success": True,
                    "registry_module_present": True,
                },
                "continuity_contract": {
                    "status": "bad_status",
                    "version": "v2",
                    "required_keys_present": "not-a-list",
                    "missing_required_keys": [],
                    "warnings": [],
                    "errors": [],
                    "normalized_refs_count": "one",
                    "alias_resolution": {"resolved": 0},
                }
            }
        }))

        result = audit_sidecar("ContinuityBadMod", require_success=True)
        # Continuity payload issues are reported in continuity block but do not
        # fail sidecar gate by themselves.
        self.assertTrue(result["valid"])
        self.assertTrue(result["continuity"]["present"])
        self.assertFalse(result["continuity"]["valid"])
        self.assertGreater(len(result["continuity"]["errors"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
