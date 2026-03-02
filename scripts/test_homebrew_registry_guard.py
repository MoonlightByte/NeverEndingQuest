#!/usr/bin/env python3
"""
Unit tests for homebrew_registry_guard.py
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

# Import after path setup
import homebrew_registry_guard as guard


class TestCheckDuplicate(TestCase):
    """Test duplicate detection functionality."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.registry_path = self.temp_dir / "world_registry.json"
        self.modules_root = self.temp_dir / "modules"
        self.modules_root.mkdir(parents=True, exist_ok=True)
        
        # Patch paths in guard module
        guard.REPO_ROOT = self.temp_dir
        guard.REGISTRY_PATH = self.registry_path
        guard.MODULES_ROOT = self.modules_root
        guard.BACKUP_ROOT = self.temp_dir / "backups"
        
        # Create minimal registry
        self.registry_path.write_text(json.dumps({
            "modules": {
                "Birble_Adventuring_Academy": {
                    "moduleName": "Birble Adventuring Academy",
                    "title": "Birble Adventuring Academy"
                }
            },
            "areas": {},
            "lastUpdated": "2026-01-01T00:00:00"
        }))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_exact_slug_conflict(self):
        """Should detect exact slug match as conflict."""
        result = guard.check_duplicate("Birble_Adventuring_Academy")
        
        self.assertFalse(result["safe_to_proceed"])
        conflicts = result["conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "exact_slug")

    def test_no_conflict_for_unique_slug(self):
        """Should allow unique slugs."""
        result = guard.check_duplicate("Totally_New_Module")
        
        self.assertTrue(result["safe_to_proceed"])
        self.assertEqual(len(result["conflicts"]), 0)

    def test_folder_conflict(self):
        """Should detect existing module folder."""
        (self.modules_root / "ExistingFolder").mkdir()
        
        result = guard.check_duplicate("ExistingFolder")
        
        self.assertFalse(result["safe_to_proceed"])
        folder_conflicts = [c for c in result["conflicts"] if c["type"] == "folder_exists"]
        self.assertEqual(len(folder_conflicts), 1)


class TestVerifyPresent(TestCase):
    """Test registry presence verification."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.registry_path = self.temp_dir / "world_registry.json"
        self.modules_root = self.temp_dir / "modules"
        
        guard.REPO_ROOT = self.temp_dir
        guard.REGISTRY_PATH = self.registry_path
        guard.MODULES_ROOT = self.modules_root
        
        # Create registry with areas
        self.registry_path.write_text(json.dumps({
            "modules": {
                "Test_Module": {
                    "moduleName": "Test Module",
                    "addedDate": "2026-03-02T12:00:00"
                }
            },
            "areas": {
                "TST001": {"module": "Test_Module"},
                "TST002": {"module": "Test_Module"}
            }
        }))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_present_when_module_in_registry(self):
        """Should return present=true for existing module."""
        result = guard.verify_present("Test_Module")
        
        self.assertTrue(result["present"])
        self.assertEqual(result["areas_count"], 2)

    def test_not_present_for_missing_module(self):
        """Should return present=false for missing module."""
        result = guard.verify_present("NonExistent_Module")
        
        self.assertFalse(result["present"])

    def test_counts_areas_correctly(self):
        """Should count areas associated with module."""
        result = guard.verify_present("Test_Module")
        
        self.assertEqual(result["areas_count"], 2)
        self.assertEqual(len(result["area_ids"]), 2)


class TestRemoveModule(TestCase):
    """Test safe module removal."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.registry_path = self.temp_dir / "world_registry.json"
        self.modules_root = self.temp_dir / "modules"
        
        guard.REPO_ROOT = self.temp_dir
        guard.REGISTRY_PATH = self.registry_path
        guard.MODULES_ROOT = self.modules_root
        guard.BACKUP_ROOT = self.temp_dir / "backups"
        
        # Create registry
        self.registry_path.write_text(json.dumps({
            "modules": {
                "RemoveMe": {"moduleName": "Remove Me"},
                "KeepMe": {"moduleName": "Keep Me"}
            },
            "areas": {
                "REM001": {"module": "RemoveMe"},
                "REM002": {"module": "RemoveMe"},
                "KEP001": {"module": "KeepMe"}
            },
            "lastUpdated": "2026-01-01T00:00:00"
        }))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_removes_module_from_registry(self):
        """Should remove module key from registry."""
        result = guard.remove_module("RemoveMe")
        
        self.assertTrue(result["removed"])
        
        # Verify registry updated
        updated = json.loads(self.registry_path.read_text())
        self.assertNotIn("RemoveMe", updated["modules"])
        self.assertIn("KeepMe", updated["modules"])

    def test_removes_associated_areas(self):
        """Should remove areas linked to module."""
        result = guard.remove_module("RemoveMe")
        
        self.assertTrue(result["removed"])
        
        updated = json.loads(self.registry_path.read_text())
        self.assertNotIn("REM001", updated["areas"])
        self.assertNotIn("REM002", updated["areas"])
        self.assertIn("KEP001", updated["areas"])

    def test_creates_backup(self):
        """Should create registry backup before removal."""
        result = guard.remove_module("RemoveMe")
        
        self.assertTrue(result["removed"])
        self.assertIsNotNone(result["backup_path"])
        self.assertTrue(Path(result["backup_path"]).exists())

    def test_fails_for_nonexistent_module(self):
        """Should fail when module not in registry."""
        result = guard.remove_module("NeverExisted")
        
        self.assertFalse(result["removed"])
        self.assertIn("not present", result.get("error", "").lower())

    def test_updates_timestamp(self):
        """Should update registry lastUpdated timestamp."""
        result = guard.remove_module("RemoveMe")
        
        self.assertTrue(result["removed"])
        
        updated = json.loads(self.registry_path.read_text())
        self.assertNotEqual(updated["lastUpdated"], "2026-01-01T00:00:00")


class TestRegistryNotFound(TestCase):
    """Test handling of missing registry."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        guard.REPO_ROOT = self.temp_dir
        guard.REGISTRY_PATH = self.temp_dir / "nonexistent" / "world_registry.json"
        guard.MODULES_ROOT = self.temp_dir / "modules"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_raises_error_for_missing_registry(self):
        """Should raise FileNotFoundError when registry missing."""
        with self.assertRaises(FileNotFoundError):
            guard.check_duplicate("AnyModule")


if __name__ == "__main__":
    unittest.main(verbosity=2)
