# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Regression Tests - Ingest Strict Path with Monster Reference Integrity
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Regression coverage for Task 4.2: Ingest strict path quarantine on unresolved monster references.
"""

import unittest
import json
import tempfile
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIngestStrictPath(unittest.TestCase):
    """Test strict ingest quarantine on unresolved monster references (Task 4.2)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.module_path = Path(self.temp_dir)
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_unresolved_references_cause_quarantine(self):
        """Test that strict ingest quarantines modules with unresolved monster references"""
        # Import here to avoid early import issues
        try:
            from core.importers.homebrewery_importer import import_homebrewery_adventure_to_module
            from core.validation.validate_module_files import ModuleValidator
        except ImportError as e:
            self.fail(f"Failed to import required modules: {e}")
            
        # Create a module structure with unresolved monster reference
        areas_dir = self.module_path / "areas"
        areas_dir.mkdir(parents=True)
        
        area_data = {
            "areaId": "test_area",
            "areaName": "Test Area",
            "locations": [{
                "locationId": "test_loc_01",
                "locationName": "Test Location",
                "monsters": [{"name": "Nonexistent Monster", "quantity": 1}]
            }]
        }
        
        area_file = areas_dir / "test_area.json"
        with open(area_file, 'w', encoding='utf-8') as f:
            json.dump(area_data, f)
            
        # Run validation (simulating what strict ingest does)
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should have reference_integrity failures
        ref_int = validator.results.get("reference_integrity", {})
        self.assertTrue(
            ref_int.get("failed", 0) > 0,
            "Expected reference_integrity failures for unresolved monster"
        )
        
        # Assert: Should not pass validation
        self.assertFalse(
            ref_int.get("passed", 0) > 0 and ref_int.get("failed", 0) == 0,
            "Validation should not pass with unresolved references"
        )
        
    def test_resolved_references_pass_validation(self):
        """Test that modules with resolved references pass validation"""
        try:
            from core.validation.validate_module_files import ModuleValidator
        except ImportError as e:
            self.fail(f"Failed to import required modules: {e}")
            
        # Create a complete module structure
        areas_dir = self.module_path / "areas"
        areas_dir.mkdir(parents=True)
        
        monsters_dir = self.module_path / "monsters"
        monsters_dir.mkdir()
        
        # Create area with monster reference
        area_data = {
            "areaId": "test_area",
            "areaName": "Test Area",
            "locations": [{
                "locationId": "test_loc_01",
                "locationName": "Test Location",
                "monsters": [{"name": "Valid Monster", "quantity": 1}]
            }]
        }
        
        area_file = areas_dir / "test_area.json"
        with open(area_file, 'w', encoding='utf-8') as f:
            json.dump(area_data, f)
            
        # Create corresponding monster file
        monster_data = {
            "name": "Valid Monster",
            "hitPoints": 20,
            "armorClass": 10,
            "challengeRating": 1
        }
        
        monster_file = monsters_dir / "valid_monster.json"
        with open(monster_file, 'w', encoding='utf-8') as f:
            json.dump(monster_data, f)
            
        # Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Should pass (no failed references)
        ref_int = validator.results.get("reference_integrity", {})
        self.assertEqual(
            ref_int.get("failed", 0),
            0,
            "Expected no reference_integrity failures for valid module"
        )
        

class TestIngestValidationErrors(unittest.TestCase):
    """Test that validation errors are surfaced in ingest results (Task 4.2)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.module_path = Path(self.temp_dir)
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_validation_errors_include_expected_path(self):
        """Test that validation errors include expected monster file path"""
        try:
            from core.validation.validate_module_files import ModuleValidator
        except ImportError as e:
            self.fail(f"Failed to import required modules: {e}")
            
        # Create module with unresolved reference
        areas_dir = self.module_path / "areas"
        areas_dir.mkdir(parents=True)
        
        area_data = {
            "areaId": "test_area",
            "areaName": "Test Area",
            "locations": [{
                "locationId": "test_loc_01",
                "locationName": "Test Location",
                "monsters": [{"name": "Test Monster", "quantity": 1}]
            }]
        }
        
        area_file = areas_dir / "test_area.json"
        with open(area_file, 'w', encoding='utf-8') as f:
            json.dump(area_data, f)
            
        # Run validation
        validator = ModuleValidator(self.module_path, ".")
        validator.run_all_validations()
        
        # Assert: Errors should include expected file path
        ref_int = validator.results.get("reference_integrity", {})
        errors = ref_int.get("errors", [])
        
        self.assertTrue(len(errors) > 0, "Expected error messages")
        
        # Check that at least one error contains expected path
        found_path = False
        for error in errors:
            if "monsters/test_monster.json" in error:
                found_path = True
                break
                
        self.assertTrue(found_path, "Errors should include expected monster file path")
        

if __name__ == '__main__':
    unittest.main(verbosity=2)
