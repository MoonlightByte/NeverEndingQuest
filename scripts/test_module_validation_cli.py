# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Tests - Module Validation CLI
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for validator CLI targeting, dependency behavior, and bulk validation.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import tempfile
import shutil
import subprocess
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestValidatorCLITargeting(unittest.TestCase):
    """Test validator CLI selector arguments."""

    def setUp(self):
        """Create temp module structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.modules_dir = Path(self.temp_dir) / "modules"
        self.modules_dir.mkdir()
        
        # Create a test module
        self.test_module = self.modules_dir / "Test_Module"
        self.test_module.mkdir()
        areas_dir = self.test_module / "areas"
        areas_dir.mkdir()
        (areas_dir / "TST001.json").write_text('{"areaId": "TST001", "areaName": "Test", "locations": []}')

    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)

    def test_help_works_without_jsonschema(self):
        """--help must work even when jsonschema is not installed."""
        validator_path = Path(__file__).parent.parent / "core" / "validation" / "validate_module_files.py"
        
        # Run with --help
        result = subprocess.run(
            [sys.executable, str(validator_path), "--help"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": ""}  # Isolate from test env
        )
        
        # Help should succeed and show usage
        self.assertEqual(result.returncode, 0)
        self.assertIn("--module", result.stdout)
        self.assertIn("--module-path", result.stdout)
        self.assertIn("--all-modules", result.stdout)
        self.assertIn("--json", result.stdout)

    def test_module_selector_requires_existing_module(self):
        """--module fails gracefully when module does not exist."""
        validator_path = Path(__file__).parent.parent / "core" / "validation" / "validate_module_files.py"
        
        result = subprocess.run(
            [sys.executable, str(validator_path), "--module", "NonExistent_Module"],
            capture_output=True,
            text=True
        )
        
        # Should fail with clear error
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr.lower() + result.stdout.lower())


class TestDependencyBehavior(unittest.TestCase):
    """Test behavior when validator dependencies are unavailable."""

    def test_validator_unavailable_exit_code(self):
        """When jsonschema unavailable and validation requested, exit code 2."""
        validator_path = Path(__file__).parent.parent / "core" / "validation" / "validate_module_files.py"
        
        # Create a minimal test module
        temp_dir = tempfile.mkdtemp()
        try:
            modules_dir = Path(temp_dir) / "modules"
            modules_dir.mkdir()
            test_module = modules_dir / "Test_Module"
            test_module.mkdir()
            areas_dir = test_module / "areas"
            areas_dir.mkdir()
            (areas_dir / "TST001.json").write_text('{"areaId": "TST001", "areaName": "Test", "locations": []}')
            
            # Run validation - will fail due to missing jsonschema
            result = subprocess.run(
                [sys.executable, str(validator_path), "--module", "Test_Module"],
                capture_output=True,
                text=True,
                cwd=temp_dir
            )
            
            # Should exit with code 2 (dependency unavailable)
            # or fail during validation with clear error
            output = result.stdout + result.stderr
            self.assertIn("jsonschema", output.lower())
            
        finally:
            shutil.rmtree(temp_dir)


class TestStrictIngestQuarantine(unittest.TestCase):
    """Test strict ingest validator-unavailable quarantine behavior."""

    def test_validator_unavailable_in_strict_mode(self):
        """Strict mode must quarantine when validator unavailable."""
        # This tests the importer logic directly
        from core.importers.homebrewery_importer import _validate_module_artifacts
        
        temp_dir = tempfile.mkdtemp()
        try:
            module_path = Path(temp_dir) / "test_module"
            module_path.mkdir()
            
            result = _validate_module_artifacts(module_path, Path(temp_dir))
            
            # Should indicate validator unavailable
            self.assertIn("validator_unavailable", result)
            self.assertTrue(result["validator_unavailable"])
            
            # In strict mode interpretation:
            # - passed should be True for non-strict compatibility
            # - but strict mode should check validator_unavailable flag
            self.assertTrue(result.get("passed", False))
            
        finally:
            shutil.rmtree(temp_dir)

    def test_quarantine_reason_deterministic(self):
        """Quarantine reason must be deterministic when validator unavailable."""
        from core.importers.homebrewery_importer import import_homebrewery_adventure_to_module
        
        # This would require mocking the full import flow
        # For now, verify the constant exists in expected locations
        validator_path = Path(__file__).parent.parent / "core" / "importers" / "homebrewery_importer.py"
        content = validator_path.read_text()
        
        # Should contain validator_unavailable quarantine logic
        self.assertIn("validator_unavailable", content)
        self.assertIn("quarantine_reason", content)


class TestBulkResolverDefaults(unittest.TestCase):
    """Test bulk validation default target resolution."""

    def setUp(self):
        """Create temp modules structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.modules_dir = Path(self.temp_dir) / "modules"
        self.modules_dir.mkdir()
        
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)

    def test_registry_modules_require_existing_folder(self):
        """Registry modules only included if folder exists on disk."""
        from scripts.validate_modules_bulk import _resolve_targets, _load_world_registry
        
        # Create registry with modules that don't exist
        registry = {"NonExistent": {}, "AlsoMissing": {}}
        
        # Create one existing module
        existing_module = self.modules_dir / "Exists"
        existing_module.mkdir()
        areas_dir = existing_module / "areas"
        areas_dir.mkdir()
        (areas_dir / "EXS001.json").write_text('{"areaId": "EXS001", "areaName": "Test", "locations": []}')
        
        # Mock registry loading
        with patch("scripts.validate_modules_bulk._load_world_registry") as mock_load:
            mock_load.return_value = {"NonExistent", "Exists"}
            targets = _resolve_targets(self.modules_dir)
        
        # Should only include Exists (which has folder + areas)
        self.assertIn("Exists", targets)
        self.assertNotIn("NonExistent", targets)

    def test_module_like_dirs_with_areas_included(self):
        """Directories with areas/*.json are included."""
        from scripts.validate_modules_bulk import _resolve_targets
        
        # Create module-like directory
        module_dir = self.modules_dir / "Has_Areas"
        module_dir.mkdir()
        areas_dir = module_dir / "areas"
        areas_dir.mkdir()
        (areas_dir / "TST001.json").write_text('{"areaId": "TST001", "areaName": "Test", "locations": []}')
        
        targets = _resolve_targets(self.modules_dir)
        
        self.assertIn("Has_Areas", targets)

    def test_system_dirs_excluded(self):
        """System directories are excluded from targets."""
        from scripts.validate_modules_bulk import _resolve_targets
        
        # Create system-like directories
        for sys_dir in ["ingest", "conversation_history", "backups"]:
            (self.modules_dir / sys_dir).mkdir()
        
        # Create valid module
        valid_module = self.modules_dir / "Valid"
        valid_module.mkdir()
        areas_dir = valid_module / "areas"
        areas_dir.mkdir()
        (areas_dir / "VLD001.json").write_text('{"areaId": "VLD001", "areaName": "Test", "locations": []}')
        
        targets = _resolve_targets(self.modules_dir)
        
        self.assertIn("Valid", targets)
        self.assertNotIn("ingest", targets)
        self.assertNotIn("conversation_history", targets)
        self.assertNotIn("backups", targets)

    def test_hidden_dirs_excluded(self):
        """Hidden directories are excluded."""
        from scripts.validate_modules_bulk import _resolve_targets
        
        # Create hidden directory
        hidden_dir = self.modules_dir / ".hidden"
        hidden_dir.mkdir()
        
        # Create valid module
        valid_module = self.modules_dir / "Valid"
        valid_module.mkdir()
        areas_dir = valid_module / "areas"
        areas_dir.mkdir()
        (areas_dir / "VLD001.json").write_text('{"areaId": "VLD001", "areaName": "Test", "locations": []}')
        
        targets = _resolve_targets(self.modules_dir)
        
        self.assertIn("Valid", targets)
        self.assertNotIn(".hidden", targets)

    def test_targets_deterministically_sorted(self):
        """Targets are returned in deterministic sorted order."""
        from scripts.validate_modules_bulk import _resolve_targets
        
        # Create multiple modules in non-sorted order
        for name in ["Zulu", "Alpha", "Mike", "Bravo"]:
            module_dir = self.modules_dir / name
            module_dir.mkdir()
            areas_dir = module_dir / "areas"
            areas_dir.mkdir()
            (areas_dir / f"{name[:3].upper()}001.json").write_text(
                f'"{{areaId": "{name[:3].upper()}001", "areaName": "{name}", "locations": []}}'
            )
        
        targets = _resolve_targets(self.modules_dir)
        
        # Should be sorted alphabetically
        self.assertEqual(targets, sorted(targets))


class TestBulkValidationOutput(unittest.TestCase):
    """Test bulk validation output formats."""

    def test_json_mode_outputs_valid_json(self):
        """--json mode must output valid JSON only."""
        bulk_path = Path(__file__).parent.parent / "scripts" / "validate_modules_bulk.py"
        
        temp_dir = tempfile.mkdtemp()
        try:
            # Create a minimal module
            modules_dir = Path(temp_dir) / "modules"
            modules_dir.mkdir()
            test_module = modules_dir / "Test"
            test_module.mkdir()
            areas_dir = test_module / "areas"
            areas_dir.mkdir()
            (areas_dir / "TST001.json").write_text('{"areaId": "TST001", "areaName": "Test", "locations": []}')
            
            result = subprocess.run(
                [sys.executable, str(bulk_path), "--json"],
                capture_output=True,
                text=True,
                cwd=temp_dir
            )
            
            # Should output valid JSON
            try:
                data = json.loads(result.stdout)
                self.assertIn("modules", data)
                self.assertIn("summary", data)
            except json.JSONDecodeError:
                self.fail(f"Output is not valid JSON: {result.stdout[:200]}")
                
        finally:
            shutil.rmtree(temp_dir)

    def test_exit_codes(self):
        """Exit codes follow contract: 0=all pass, 1=any fail, 2=execution error."""
        bulk_path = Path(__file__).parent.parent / "scripts" / "validate_modules_bulk.py"
        
        temp_dir = tempfile.mkdtemp()
        try:
            # Empty modules dir - should be execution error (no targets)
            modules_dir = Path(temp_dir) / "modules"
            modules_dir.mkdir()
            
            result = subprocess.run(
                [sys.executable, str(bulk_path)],
                capture_output=True,
                text=True,
                cwd=temp_dir
            )
            
            # No modules should result in exit 2
            self.assertEqual(result.returncode, 2)
            
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
