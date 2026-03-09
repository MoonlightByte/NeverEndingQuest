#!/usr/bin/env python3
"""
Regression tests for validator monster reference hygiene fixes.

Tests cover:
1. Backup file exclusion from reference scan
2. Normalized slug matching parity with module_generator
3. Deduped error reporting
4. Location name fallback behavior

Run: python3 scripts/test_validator_monster_reference_hygiene.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.validation.validate_module_files import ModuleValidator


class TestValidatorBackupFileExclusion(unittest.TestCase):
    """Test that backup files are excluded from monster reference scanning"""
    
    def setUp(self):
        """Create temp module directory with area and monster files"""
        self.temp_dir = tempfile.mkdtemp()
        self.areas_dir = Path(self.temp_dir) / "areas"
        self.monsters_dir = Path(self.temp_dir) / "monsters"
        self.areas_dir.mkdir()
        self.monsters_dir.mkdir()
        
    def tearDown(self):
        """Clean up temp directory"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_backup_area_files_excluded_from_scan(self):
        """Backup area files should not generate duplicate reference errors"""
        # Create a valid monster file
        monster_data = {"name": "Goblin", "type": "humanoid", "hit_points": 7}
        with open(self.monsters_dir / "goblin.json", "w") as f:
            json.dump(monster_data, f)
        
        # Create active area file with resolved reference
        area_data = {
            "areaId": "TEST001",
            "areaName": "Test Area",
            "locations": [{
                "locationId": "LOC001",
                "locationName": "Test Location",
                "monsters": [{"name": "Goblin"}]
            }]
        }
        with open(self.areas_dir / "TEST001.json", "w") as f:
            json.dump(area_data, f)
        
        # Create backup file with UNRESOLVED reference
        backup_area_data = {
            "areaId": "TEST001",
            "areaName": "Test Area Backup",
            "locations": [{
                "locationId": "LOC001",
                "locationName": "Test Location",
                "monsters": [{"name": "Missing Monster"}]
            }]
        }
        with open(self.areas_dir / "TEST001_BU.json", "w") as f:
            json.dump(backup_area_data, f)
        
        # Run validation
        schema_dir = Path(__file__).parent.parent
        validator = ModuleValidator(self.temp_dir, schema_dir)
        validator.validate_monster_references()
        
        # Should have no unresolved references (backup excluded)
        self.assertEqual(validator.results["reference_integrity"].get("failed", 0), 0)
        self.assertEqual(validator.results["reference_integrity"].get("passed", 0), 1)
    
    def test_all_backup_patterns_excluded(self):
        """All backup file patterns should be excluded"""
        # Create monster for resolved reference
        with open(self.monsters_dir / "resolved.json", "w") as f:
            json.dump({"name": "Resolved"}, f)
        
        # Create active area with resolved reference
        active_area = {
            "areaId": "AREA001",
            "areaName": "Active Area",
            "locations": [{
                "locationId": "LOC001",
                "monsters": [{"name": "Resolved"}]
            }]
        }
        with open(self.areas_dir / "AREA001.json", "w") as f:
            json.dump(active_area, f)
        
        # Create backup files with unresolved references
        backup_patterns = ["_BU.json", ".bak", ".backup", ".tmp", "_backup.json"]
        unresolved_area = {
            "areaId": "AREA001",
            "areaName": "Backup Area",
            "locations": [{
                "locationId": "LOC001",
                "monsters": [{"name": "Unresolved Monster"}]
            }]
        }
        
        for i, pattern in enumerate(backup_patterns):
            filename = f"AREA{i:03d}{pattern}" if not pattern.startswith('.') else f"AREA{i:03d}{pattern}"
            with open(self.areas_dir / filename, "w") as f:
                json.dump(unresolved_area, f)
        
        # Run validation
        schema_dir = Path(__file__).parent.parent
        validator = ModuleValidator(self.temp_dir, schema_dir)
        validator.validate_monster_references()
        
        # Should have no unresolved (all backups excluded)
        self.assertEqual(validator.results["reference_integrity"].get("failed", 0), 0)


class TestValidatorSlugNormalization(unittest.TestCase):
    """Test that validator normalizes monster names consistently with builder"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.areas_dir = Path(self.temp_dir) / "areas"
        self.monsters_dir = Path(self.temp_dir) / "monsters"
        self.areas_dir.mkdir()
        self.monsters_dir.mkdir()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_normalization_matches_builder_contract(self):
        """Validator normalization should match module_generator contract"""
        # Test cases: (input_name, expected_slug)
        test_cases = [
            ("Wolf", "wolf"),
            ("Shadow Corrupted Wolf", "shadow_corrupted_wolf"),
            ("Malarok the Corruptor", "malarok_the_corruptor"),
            ("Whispering Ashling", "whispering_ashling"),
            ("Elite Bandit Bodyguard", "elite_bandit_bodyguard"),
            ("Bob's Monster", "bobs_monster"),  # Apostrophe removed
            ("Hyphenated-Monster", "hyphenated_monster"),  # Hyphen to underscore
        ]
        
        for original_name, expected_slug in test_cases:
            with self.subTest(original_name=original_name):
                normalized = ModuleValidator._normalize_monster_name(original_name)
                self.assertEqual(normalized, expected_slug)
    
    def test_slug_matching_is_case_insensitive(self):
        """Slug matching should be case insensitive"""
        # Create monster file with lowercase slug
        with open(self.monsters_dir / "test_monster.json", "w") as f:
            json.dump({"name": "Test Monster"}, f)
        
        # Create area with mixed-case reference
        area_data = {
            "areaId": "TEST",
            "areaName": "Test Area",
            "locations": [{
                "locationId": "LOC001",
                "monsters": [{"name": "TEST MONSTER"}]  # Uppercase
            }]
        }
        with open(self.areas_dir / "TEST.json", "w") as f:
            json.dump(area_data, f)
        
        # Run validation
        schema_dir = Path(__file__).parent.parent
        validator = ModuleValidator(self.temp_dir, schema_dir)
        validator.validate_monster_references()
        
        # Should resolve (case insensitive match)
        self.assertEqual(validator.results["reference_integrity"].get("failed", 0), 0)


class TestValidatorDeduplication(unittest.TestCase):
    """Test that duplicate monster references are deduplicated in error reports"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.areas_dir = Path(self.temp_dir) / "areas"
        self.monsters_dir = Path(self.temp_dir) / "monsters"
        self.areas_dir.mkdir()
        self.monsters_dir.mkdir()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_duplicate_references_deduplicated(self):
        """Same monster in multiple locations should produce one error"""
        # Create area with same missing monster in multiple locations
        area_data = {
            "areaId": "AREA001",
            "areaName": "Test Area",
            "locations": [
                {
                    "locationId": "LOC001",
                    "locationName": "Location One",
                    "monsters": [{"name": "Missing Monster"}]
                },
                {
                    "locationId": "LOC002", 
                    "locationName": "Location Two",
                    "monsters": [{"name": "Missing Monster"}]
                }
            ]
        }
        with open(self.areas_dir / "AREA001.json", "w") as f:
            json.dump(area_data, f)
        
        # Run validation
        schema_dir = Path(__file__).parent.parent
        validator = ModuleValidator(self.temp_dir, schema_dir)
        validator.validate_monster_references()
        
        # Should have exactly 1 error (deduplicated)
        self.assertEqual(validator.results["reference_integrity"].get("failed", 0), 1)
        self.assertEqual(len(validator.results["reference_integrity"].get("errors", [])), 1)
    
    def test_different_monsters_not_deduplicated(self):
        """Different missing monsters should produce separate errors"""
        area_data = {
            "areaId": "AREA001",
            "areaName": "Test Area",
            "locations": [{
                "locationId": "LOC001",
                "monsters": [
                    {"name": "Missing Monster A"},
                    {"name": "Missing Monster B"}
                ]
            }]
        }
        with open(self.areas_dir / "AREA001.json", "w") as f:
            json.dump(area_data, f)
        
        # Run validation
        schema_dir = Path(__file__).parent.parent
        validator = ModuleValidator(self.temp_dir, schema_dir)
        validator.validate_monster_references()
        
        # Should have 2 errors (different monsters)
        self.assertEqual(validator.results["reference_integrity"].get("failed", 0), 2)


class TestValidatorLocationNameFallback(unittest.TestCase):
    """Test that location name uses fallback chain"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.areas_dir = Path(self.temp_dir) / "areas"
        self.monsters_dir = Path(self.temp_dir) / "monsters"
        self.areas_dir.mkdir()
        self.monsters_dir.mkdir()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_location_name_fallback_chain(self):
        """Location name should use: locationName -> name -> locationId"""
        # Create area with location missing locationName
        area_data = {
            "areaId": "AREA001",
            "areaName": "Test Area",
            "locations": [
                {
                    "locationId": "LOC001",
                    "name": "Fallback Name",
                    "monsters": [{"name": "Missing Monster"}]
                },
                {
                    "locationId": "LOC002",
                    # No locationName or name
                    "monsters": [{"name": "Another Missing"}]
                }
            ]
        }
        with open(self.areas_dir / "AREA001.json", "w") as f:
            json.dump(area_data, f)
        
        # Run validation
        schema_dir = Path(__file__).parent.parent
        validator = ModuleValidator(self.temp_dir, schema_dir)
        validator.validate_monster_references()
        
        errors = validator.results["reference_integrity"].get("errors", [])
        
        # Check that errors contain correct location names
        self.assertEqual(len(errors), 2)
        
        # Find error for each monster
        loc001_error = next(e for e in errors if "LOC001" in e or "Fallback Name" in e)
        loc002_error = next(e for e in errors if "LOC002" in e)
        
        # LOC001 should use 'name' field
        self.assertIn("Fallback Name", loc001_error)
        
        # LOC002 should use locationId
        self.assertIn("LOC002", loc002_error)


class TestValidatorIntegration(unittest.TestCase):
    """Integration tests with real module structure"""
    
    def test_thornwood_validation_after_fixes(self):
        """Thornwood Watch should validate cleanly after monster generation"""
        thornwood_path = Path(__file__).parent.parent / "modules" / "The_Thornwood_Watch"
        
        if not thornwood_path.exists():
            self.skipTest("Thornwood Watch module not found")
        
        schema_dir = Path(__file__).parent.parent
        validator = ModuleValidator(thornwood_path, schema_dir)
        validator.validate_monster_references()
        
        # Should have no unresolved references after builder fix
        self.assertEqual(
            validator.results["reference_integrity"].get("failed", 0), 0,
            f"Unresolved references: {validator.results['reference_integrity'].get('errors', [])}"
        )


if __name__ == "__main__":
    # Run with verbosity
    unittest.main(verbosity=2)
