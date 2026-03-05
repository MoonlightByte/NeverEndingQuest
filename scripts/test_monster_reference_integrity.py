# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Regression Tests - Monster Reference Integrity Validator
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Regression coverage for Task 4.1: Monster reference integrity validation.
"""

import unittest
import json
import tempfile
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.validation.validate_module_files import ModuleValidator


class TestMonsterReferenceIntegrity(unittest.TestCase):
    """Test monster reference integrity validation (Task 4.1)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.module_path = Path(self.temp_dir)
        
        # Create areas directory
        self.areas_dir = self.module_path / "areas"
        self.areas_dir.mkdir()
        
        # Create monsters directory
        self.monsters_dir = self.module_path / "monsters"
        self.monsters_dir.mkdir()
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def _create_area_with_monster(self, area_name, location_name, monster_name, quantity=1):
        """Create an area file with a monster reference"""
        area_data = {
            "areaId": area_name.lower().replace(" ", "_"),
            "areaName": area_name,
            "locations": [{
                "locationId": f"{area_name}_loc_01",
                "locationName": location_name,
                "monsters": [{"name": monster_name, "quantity": quantity}]
            }]
        }
        area_file = self.areas_dir / f"{area_name.lower().replace(' ', '_')}.json"
        with open(area_file, 'w', encoding='utf-8') as f:
            json.dump(area_data, f)
            
    def _create_monster_file(self, monster_name):
        """Create a monster stat file"""
        monster_data = {
            "name": monster_name,
            "hitPoints": 20,
            "armorClass": 10,
            "challengeRating": 1
        }
        # Normalize name to slug
        slug = monster_name.lower().replace(" ", "_").replace("'", "")
        monster_file = self.monsters_dir / f"{slug}.json"
        with open(monster_file, 'w', encoding='utf-8') as f:
            json.dump(monster_data, f)
            
    def test_unresolved_monster_reference_fails_validation(self):
        """Test that unresolved monster references fail validation"""
        # Arrange: Create area with monster reference but no stat file
        self._create_area_with_monster("Test Area", "Test Location", "Missing Monster")
        
        # Act: Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should fail with unresolved reference
        ref_int = validator.results.get("reference_integrity", {})
        self.assertEqual(ref_int.get("failed", 0), 1, "Expected 1 failed reference")
        self.assertEqual(ref_int.get("passed", 0), 0, "Expected 0 passed references")
        self.assertTrue(len(ref_int.get("errors", [])) > 0, "Expected error messages")
        
        # Verify error contains expected details
        errors = ref_int.get("errors", [])
        found_detail = False
        for error in errors:
            if "Missing Monster" in error and "monsters/missing_monster.json" in error:
                found_detail = True
                break
        self.assertTrue(found_detail, "Error should include monster name and expected file path")
        
    def test_resolved_monster_reference_passes_validation(self):
        """Test that resolved monster references pass validation"""
        # Arrange: Create area with monster reference AND stat file
        self._create_area_with_monster("Test Area", "Test Location", "Valid Monster")
        self._create_monster_file("Valid Monster")
        
        # Act: Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should pass
        ref_int = validator.results.get("reference_integrity", {})
        self.assertEqual(ref_int.get("failed", 0), 0, "Expected 0 failed references")
        self.assertEqual(ref_int.get("passed", 0), 1, "Expected 1 passed reference (no errors found)")
        
    def test_normalization_lowercase(self):
        """Test that lowercase normalization works correctly"""
        # Arrange: Mixed case monster name
        self._create_area_with_monster("Test Area", "Test Location", "Goblin Warrior")
        # Create file with normalized name (lowercase, spaces->underscores)
        self._create_monster_file("goblin_warrior")
        
        # Act: Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should pass (normalized names match)
        ref_int = validator.results.get("reference_integrity", {})
        self.assertEqual(ref_int.get("failed", 0), 0, "Lowercase normalization should work")
        
    def test_normalization_apostrophes(self):
        """Test that apostrophe normalization works correctly"""
        # Arrange: Monster name with apostrophe
        self._create_area_with_monster("Test Area", "Test Location", "Dragon's Servant")
        # Create file without apostrophe
        self._create_monster_file("Dragons Servant")
        
        # Act: Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should pass (apostrophes removed)
        ref_int = validator.results.get("reference_integrity", {})
        self.assertEqual(ref_int.get("failed", 0), 0, "Apostrophe normalization should work")
        
    def test_normalization_spaces(self):
        """Test that space normalization works correctly"""
        # Arrange: Monster name with spaces
        self._create_area_with_monster("Test Area", "Test Location", "Dark Knight")
        # Create file with underscores
        self._create_monster_file("Dark_Knight")
        
        # Act: Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should pass (spaces->underscores)
        ref_int = validator.results.get("reference_integrity", {})
        self.assertEqual(ref_int.get("failed", 0), 0, "Space normalization should work")
        
    def test_multiple_monster_references(self):
        """Test validation with multiple monster references"""
        # Arrange: Two areas with different monsters
        self._create_area_with_monster("Area One", "Location One", "Monster A")
        self._create_area_with_monster("Area Two", "Location Two", "Monster B")
        # Only create one monster file
        self._create_monster_file("Monster A")
        
        # Act: Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should fail for Monster B only
        ref_int = validator.results.get("reference_integrity", {})
        self.assertEqual(ref_int.get("failed", 0), 1, "Expected 1 failed reference (Monster B)")
        
        # Verify error is for Monster B
        errors = ref_int.get("errors", [])
        found_monster_b = any("Monster B" in e for e in errors)
        self.assertTrue(found_monster_b, "Error should reference Monster B")
        
    def test_empty_monsters_directory(self):
        """Test validation when monsters directory is empty"""
        # Arrange: Area with monster reference, no monster files
        self._create_area_with_monster("Test Area", "Test Location", "Some Monster")
        
        # Act: Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should fail
        ref_int = validator.results.get("reference_integrity", {})
        self.assertTrue(ref_int.get("failed", 0) > 0, "Empty monsters directory should fail")
        

class TestMonsterReferenceIntegrityReport(unittest.TestCase):
    """Test reporting of monster reference integrity (Task 4.1)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.module_path = Path(self.temp_dir)
        
        # Create areas directory
        self.areas_dir = self.module_path / "areas"
        self.areas_dir.mkdir()
        
        # Create monsters directory
        self.monsters_dir = self.module_path / "monsters"
        self.monsters_dir.mkdir()
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_report_includes_reference_integrity_section(self):
        """Test that print_report includes reference_integrity section"""
        # Arrange
        area_data = {
            "areaId": "test_area",
            "areaName": "Test Area",
            "locations": [{
                "locationId": "test_loc_01",
                "locationName": "Test Location",
                "monsters": [{"name": "Test Monster", "quantity": 1}]
            }]
        }
        area_file = self.areas_dir / "test_area.json"
        with open(area_file, 'w', encoding='utf-8') as f:
            json.dump(area_data, f)
            
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Act: Check results structure
        self.assertIn("reference_integrity", validator.results, 
                     "Results should include reference_integrity category")
        

if __name__ == '__main__':
    unittest.main(verbosity=2)
