#!/usr/bin/env python3
"""
Regression tests for audit_module_gameplay.py

Validates:
- Structural extraction coverage
- Heuristic extraction behavior (strict mode only)
- Strict-mode severity escalation
- Output contract stability
- Exit code behavior
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.audit_module_gameplay import (
    MonsterRef,
    audit_module,
    check_monster_json,
    check_monster_media,
    extract_from_structure,
    extract_monster_refs,
    extract_monster_refs_from_text,
    normalize_slug,
)


class TestStructuralExtraction(unittest.TestCase):
    """Tests for structural monster reference extraction."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.module_name = "test_module"
        self.module_path = os.path.join(self.temp_dir, "modules", self.module_name)
        os.makedirs(os.path.join(self.module_path, "areas"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "monsters"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "media", "monsters"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_locations_monsters_refs_detected(self):
        """Verify locations[].monsters refs are detected."""
        area_data = {
            "locations": [
                {
                    "locationId": "forest_clearing",
                    "name": "Forest Clearing",
                    "monsters": [
                        {"name": "Goblin Scout", "type": "humanoid"},
                        "Wolf",
                        {"monsterType": "Bandit Captain"}
                    ]
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        refs = extract_monster_refs(self.module_path, strict_instructions=False)
        
        # Should find 3 structural refs
        structural_refs = [r for r in refs if r.confidence == "structural"]
        self.assertEqual(len(structural_refs), 3)
        
        slugs = [r.slug for r in structural_refs]
        self.assertIn("goblin_scout", slugs)
        self.assertIn("wolf", slugs)
        self.assertIn("bandit_captain", slugs)
        
        # Verify source attribution
        for ref in structural_refs:
            self.assertEqual(ref.source_file, "test_area.json")
            self.assertTrue(ref.source_path.startswith("locations[0].monsters"))
            self.assertEqual(ref.confidence, "structural")

    def test_randomEncounters_monsters_refs_detected(self):
        """Verify randomEncounters[].monsters refs are detected."""
        area_data = {
            "randomEncounters": [
                {
                    "id": "enc_001",
                    "monsters": [
                        {"name": "Skeleton Warrior"},
                        {"name": "Skeleton Archer"}
                    ]
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        refs = extract_monster_refs(self.module_path, strict_instructions=False)
        
        structural_refs = [r for r in refs if r.confidence == "structural"]
        # Should find refs from both direct scan and nested structure scan
        slugs = [r.slug for r in structural_refs]
        self.assertIn("skeleton_warrior", slugs)
        self.assertIn("skeleton_archer", slugs)
        # Verify at least 2 unique slugs are found
        self.assertGreaterEqual(len(set(slugs)), 2)

    def test_nested_createEncounter_payload_refs_detected(self):
        """Verify nested createEncounter-like payload refs are detected."""
        area_data = {
            "randomEncounters": [
                {
                    "id": "ambush",
                    "action": "createEncounter",
                    "parameters": {
                        "monsters": [
                            {"name": "Orc Brute"},
                            {"name": "Orc Shaman"}
                        ]
                    }
                }
            ],
            "locations": [
                {
                    "locationId": "dungeon_hall",
                    "randomEncounters": [
                        {
                            "id": "trap_room",
                            "dmAction": "createEncounter",
                            "monsters": [
                                {"name": "Mimic"},
                                {"name": "Animated Armor"}
                            ]
                        }
                    ]
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        refs = extract_monster_refs(self.module_path, strict_instructions=False)
        
        structural_refs = [r for r in refs if r.confidence == "structural"]
        
        # Verify all expected slugs are found (may find duplicates from nested scanning)
        slugs = [r.slug for r in structural_refs]
        self.assertIn("orc_brute", slugs)
        self.assertIn("orc_shaman", slugs)
        self.assertIn("mimic", slugs)
        self.assertIn("animated_armor", slugs)
        
        # Verify source paths contain expected markers
        paths = [r.source_path for r in structural_refs]
        self.assertTrue(any("parameters.monsters" in p for p in paths))
        self.assertTrue(any("dmAction" in p for p in paths))

    def test_extract_from_structure_recursive_nesting(self):
        """Verify extract_from_structure handles deep nesting."""
        nested_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "monsters": [
                            {"name": "Deep Monster"}
                        ]
                    }
                }
            }
        }
        
        refs = extract_from_structure(nested_data, "root")
        
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0][0], "deep_monster")
        self.assertTrue("level1.level2.level3.monsters[0]" in refs[0][1])
        self.assertEqual(refs[0][2], "structural")

    def test_scene_entity_branches_are_ignored_in_structural_scan(self):
        """Verify sceneEntity metadata does not produce structural monster refs."""
        nested_data = {
            "locations": [
                {
                    "locationId": "illusion_hall",
                    "sceneEntity": {
                        "scene_only": True,
                        "monsters": [
                            {"name": "Illusory Beast"},
                        ],
                        "nested": {
                            "creatures": [
                                {"name": "Ghostly Projection"},
                            ]
                        },
                    },
                    "monsters": [
                        {"name": "Real Guardian"},
                    ],
                }
            ]
        }

        refs = extract_from_structure(nested_data, "root")
        slugs = [ref[0] for ref in refs]

        self.assertIn("real_guardian", slugs)
        self.assertNotIn("illusory_beast", slugs)
        self.assertNotIn("ghostly_projection", slugs)


class TestHeuristicExtraction(unittest.TestCase):
    """Tests for heuristic monster reference extraction."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.module_name = "test_module"
        self.module_path = os.path.join(self.temp_dir, "modules", self.module_name)
        os.makedirs(os.path.join(self.module_path, "areas"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "monsters"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_heuristic_refs_only_in_strict_mode(self):
        """Verify heuristic refs from instruction fields are included only when strict mode is enabled."""
        area_data = {
            "plotHooks": [
                "The party encounters a Mythic Beast in the dungeon."
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        # Normal mode: no heuristic refs from plotHooks
        refs_normal = extract_monster_refs(self.module_path, strict_instructions=False)
        heuristic_refs_normal = [r for r in refs_normal if r.confidence == "heuristic"]
        self.assertEqual(len(heuristic_refs_normal), 0)
        
        # Strict mode: heuristic refs from plotHooks should be present
        refs_strict = extract_monster_refs(self.module_path, strict_instructions=True)
        heuristic_refs_strict = [r for r in refs_strict if r.confidence == "heuristic"]
        self.assertGreater(len(heuristic_refs_strict), 0)

    def test_heuristic_source_attribution(self):
        """Verify heuristic refs have proper source attribution fields."""
        area_data = {
            "plotHooks": [
                "The party encounters a Dire Wolf Alpha in the woods."
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        refs = extract_monster_refs(self.module_path, strict_instructions=True)
        heuristic_refs = [r for r in refs if r.confidence == "heuristic"]
        
        self.assertGreater(len(heuristic_refs), 0)
        
        for ref in heuristic_refs:
            # All required attribution fields must be present
            self.assertIsNotNone(ref.slug)
            self.assertIsNotNone(ref.source_file)
            self.assertIsNotNone(ref.source_path)
            self.assertEqual(ref.confidence, "heuristic")
            self.assertIsNotNone(ref.original_text)
            self.assertTrue(len(ref.original_text) > 0)

    def test_extract_monster_refs_from_text_patterns(self):
        """Verify text pattern extraction finds monster references."""
        text = "The party encounters a Dire Wolf and fights a Goblin King. 'Dire Wolf Alpha' appears."
        
        refs = extract_monster_refs_from_text(text, "test.path")
        
        self.assertGreater(len(refs), 0)
        
        slugs = [r[0] for r in refs]
        self.assertIn("dire_wolf", slugs)
        self.assertIn("goblin_king", slugs)
        self.assertIn("dire_wolf_alpha", slugs)
        
        # All should be heuristic
        for ref in refs:
            self.assertEqual(ref[2], "heuristic")
            self.assertTrue(len(ref[3]) > 0)  # original_text

    def test_generic_phrases_not_extracted(self):
        """Verify generic prose phrases are not extracted as heuristic refs."""
        area_data = {
            "randomEncounters": [
                {
                    "id": "avoidance1",
                    "description": "This encounter can be avoided with stealth."
                },
                {
                    "id": "avoidance2",
                    "description": "But can be avoided with stealth."
                },
                {
                    "id": "avoidance3",
                    "description": "The encounter can be avoided."
                },
                {
                    "id": "avoidance4",
                    "description": "Attack the town and destroy the village."
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        refs = extract_monster_refs(self.module_path, strict_instructions=True)
        heuristic_refs = [r for r in refs if r.confidence == "heuristic"]
        
        # None of these generic phrases should produce heuristic refs
        self.assertEqual(len(heuristic_refs), 0, 
                        f"Expected 0 heuristic refs, got {len(heuristic_refs)}: {[r.original_text for r in heuristic_refs]}")


class TestStrictModeSeverity(unittest.TestCase):
    """Tests for strict-mode severity escalation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.module_name = "test_module"
        self.module_path = os.path.join(self.temp_dir, "modules", self.module_name)
        os.makedirs(os.path.join(self.module_path, "areas"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "monsters"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "media", "monsters"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_area_with_heuristic_refs(self):
        """Helper to create an area with heuristic refs pointing to non-existent monsters."""
        area_data = {
            "plotHooks": [
                "The party encounters a Mythic Beast in the dungeon."
            ],
            "dcChecks": [
                {"description": "The party encounters a Legendary Dragon."}
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)

    def test_unresolved_heuristic_refs_warning_in_normal_mode(self):
        """Verify unresolved heuristic refs from randomEncounters are warnings in normal mode."""
        # Create area with heuristic refs in randomEncounters (scanned in both modes)
        area_data = {
            "randomEncounters": [
                {
                    "id": "enc_001",
                    "description": "The party encounters a Legendary Dragon."
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        # Must change to temp dir for audit_module to find the module
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            result = audit_module(self.module_name, strict_instructions=False)
            
            # Heuristic refs from randomEncounters should be in warnings, not blocking_errors
            heuristic_warnings = [w for w in result['warnings'] if 'heuristic' in w.lower()]
            self.assertGreater(len(heuristic_warnings), 0)
            
            heuristic_blockers = [e for e in result['blocking_errors'] if 'heuristic' in e.lower()]
            self.assertEqual(len(heuristic_blockers), 0)
        finally:
            os.chdir(original_dir)

    def test_unresolved_heuristic_refs_blocking_in_strict_mode(self):
        """Verify same unresolved heuristic refs are blocking_errors in strict mode."""
        self._create_test_area_with_heuristic_refs()
        
        # Must change to temp dir for audit_module to find the module
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            result = audit_module(self.module_name, strict_instructions=True)
            
            # Should be in blocking_errors, not warnings
            heuristic_blockers = [e for e in result['blocking_errors'] if 'heuristic' in e.lower()]
            self.assertGreater(len(heuristic_blockers), 0)
        finally:
            os.chdir(original_dir)

    def test_structural_refs_always_blocking_when_broken(self):
        """Verify structural refs are always blocking errors regardless of mode."""
        # Create area with structural refs to non-existent monster
        area_data = {
            "locations": [
                {
                    "locationId": "test_loc",
                    "monsters": [{"name": "NonExistent Monster"}]
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        # Must change to temp dir for audit_module to find the module
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            # Both modes should report as blocking error (may have multiple blockers: JSON + media)
            result_normal = audit_module(self.module_name, strict_instructions=False)
            blockers_normal = [e for e in result_normal['blocking_errors'] if 'nonexistent' in e.lower()]
            self.assertGreaterEqual(len(blockers_normal), 1, f"Expected at least 1 blocker in normal mode, got {blockers_normal}")
            
            result_strict = audit_module(self.module_name, strict_instructions=True)
            blockers_strict = [e for e in result_strict['blocking_errors'] if 'nonexistent' in e.lower()]
            self.assertGreaterEqual(len(blockers_strict), 1, f"Expected at least 1 blocker in strict mode, got {blockers_strict}")
        finally:
            os.chdir(original_dir)


class TestOutputContract(unittest.TestCase):
    """Tests for output contract stability."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.module_name = "test_module"
        self.module_path = os.path.join(self.temp_dir, "modules", self.module_name)
        os.makedirs(os.path.join(self.module_path, "areas"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "monsters"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "media", "monsters"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_result_contains_required_top_level_sections(self):
        """Verify result object always contains required top-level sections."""
        # Create valid module structure
        area_data = {
            "locations": [{"locationId": "test", "monsters": []}]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        result = audit_module(self.module_name, strict_instructions=False)
        
        # Required sections
        self.assertIn('blocking_errors', result)
        self.assertIn('warnings', result)
        self.assertIn('coverage_stats', result)
        self.assertIn('fix_list', result)
        self.assertIn('references', result)
        
        # Type checks
        self.assertIsInstance(result['blocking_errors'], list)
        self.assertIsInstance(result['warnings'], list)
        self.assertIsInstance(result['coverage_stats'], dict)
        self.assertIsInstance(result['fix_list'], list)
        self.assertIsInstance(result['references'], list)

    def test_references_array_contains_source_attribution(self):
        """Verify references array contains objects with source attribution."""
        # Create valid monster and media files so refs are kept
        monster_data = {
            "name": "Test Monster",
            "size": "Medium",
            "type": "beast",
            "alignment": "unaligned",
            "armorClass": 12,
            "hitPoints": 20,
            "speed": "30 ft.",
            "abilities": {"str": 10, "dex": 12, "con": 10, "int": 2, "wis": 10, "cha": 5},
            "challengeRating": "1/2"
        }
        monster_file = os.path.join(self.module_path, "monsters", "test_monster.json")
        with open(monster_file, 'w') as f:
            json.dump(monster_data, f)
        
        media_file = os.path.join(self.module_path, "media", "monsters", "test_monster.png")
        with open(media_file, 'w') as f:
            f.write("")
        
        area_data = {
            "locations": [
                {
                    "locationId": "test_loc",
                    "monsters": [{"name": "Test Monster"}]
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        # Must change to temp dir for audit_module to find the module
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            result = audit_module(self.module_name, strict_instructions=False)
        finally:
            os.chdir(original_dir)
        
        self.assertGreater(len(result['references']), 0)
        
        for ref in result['references']:
            self.assertIn('slug', ref)
            self.assertIn('file', ref)
            self.assertIn('path', ref)
            self.assertIn('confidence', ref)
            self.assertIn('original', ref)
            
            self.assertIsInstance(ref['slug'], str)
            self.assertIsInstance(ref['file'], str)
            self.assertIsInstance(ref['path'], str)
            self.assertIn(ref['confidence'], ['structural', 'heuristic'])

    def test_coverage_stats_has_expected_fields(self):
        """Verify coverage_stats contains expected fields."""
        # Create valid monster so stats get populated
        monster_data = {
            "name": "Test Goblin",
            "size": "Small",
            "type": "humanoid",
            "alignment": "neutral evil",
            "armorClass": 15,
            "hitPoints": 7,
            "speed": "30 ft.",
            "abilities": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
            "challengeRating": "1/4"
        }
        monster_file = os.path.join(self.module_path, "monsters", "test_goblin.json")
        with open(monster_file, 'w') as f:
            json.dump(monster_data, f)
        
        # Create media file
        media_file = os.path.join(self.module_path, "media", "monsters", "test_goblin.png")
        with open(media_file, 'w') as f:
            f.write("")
        
        area_data = {
            "locations": [{"locationId": "test", "monsters": [{"name": "Test Goblin"}]}]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        # Must change to temp dir for audit_module to find the module
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            result = audit_module(self.module_name, strict_instructions=False)
        finally:
            os.chdir(original_dir)
        
        stats = result['coverage_stats']
        
        expected_fields = [
            'module', 'referenced_monsters', 'structural_refs', 'heuristic_refs',
            'json_valid', 'json_invalid', 'json_missing', 'json_coverage_pct',
            'media_base_coverage', 'media_thumb_coverage', 'media_video_coverage',
            'media_base_coverage_pct'
        ]
        
        for field in expected_fields:
            self.assertIn(field, stats, f"Missing field: {field}")

    def test_empty_module_returns_valid_contract(self):
        """Verify empty module returns valid output contract."""
        # Create empty area file so module exists but has no monsters
        area_file = os.path.join(self.module_path, "areas", "empty_area.json")
        with open(area_file, 'w') as f:
            json.dump({"locations": []}, f)
        
        result = audit_module(self.module_name, strict_instructions=False)
        
        self.assertIn('blocking_errors', result)
        self.assertIn('warnings', result)
        self.assertIn('coverage_stats', result)
        self.assertIn('fix_list', result)
        self.assertIn('references', result)

    def test_nonexistent_module_returns_valid_contract(self):
        """Verify non-existent module returns valid output contract with error."""
        result = audit_module("nonexistent_module_xyz", strict_instructions=False)
        
        self.assertIn('blocking_errors', result)
        self.assertEqual(len(result['blocking_errors']), 1)
        self.assertIn("Module not found", result['blocking_errors'][0])
        self.assertIn('coverage_stats', result)
        self.assertIn('warnings', result)
        self.assertIn('fix_list', result)


class TestExitCodeBehavior(unittest.TestCase):
    """Tests for CLI exit code behavior."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.module_name = "test_module"
        self.module_path = os.path.join(self.temp_dir, "modules", self.module_name)
        os.makedirs(os.path.join(self.module_path, "areas"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "monsters"), exist_ok=True)
        os.makedirs(os.path.join(self.module_path, "media", "monsters"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_audit_script(self, module_name, strict=False):
        """Helper to run the audit script and return exit code."""
        script_path = Path(__file__).parent / "audit_module_gameplay.py"
        cmd = [sys.executable, str(script_path), "--module", module_name]
        if strict:
            cmd.append("--strict-instructions")
        
        result = subprocess.run(
            cmd,
            cwd=self.temp_dir,
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout, result.stderr

    def test_no_blockers_exit_code_0(self):
        """Verify no blockers results in exit code 0."""
        # Create valid monster with proper structure
        monster_data = {
            "name": "Test Goblin",
            "size": "Small",
            "type": "humanoid",
            "alignment": "neutral evil",
            "armorClass": 15,
            "hitPoints": 7,
            "speed": "30 ft.",
            "abilities": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
            "challengeRating": "1/4"
        }
        
        monster_file = os.path.join(self.module_path, "monsters", "test_goblin.json")
        with open(monster_file, 'w') as f:
            json.dump(monster_data, f)
        
        # Create dummy media file
        media_file = os.path.join(self.module_path, "media", "monsters", "test_goblin.png")
        with open(media_file, 'w') as f:
            f.write("")
        
        # Create area referencing the monster
        area_data = {
            "locations": [
                {
                    "locationId": "test",
                    "monsters": [{"name": "Test Goblin"}]
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        # Change to temp directory for script execution
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            exit_code, stdout, stderr = self._run_audit_script(self.module_name)
        finally:
            os.chdir(original_dir)
        
        self.assertEqual(exit_code, 0, f"Expected exit code 0, got {exit_code}. stdout: {stdout}")

    def test_blockers_present_exit_code_1(self):
        """Verify blockers present results in exit code 1."""
        # Create area referencing non-existent monster (will be blocker)
        area_data = {
            "locations": [
                {
                    "locationId": "test",
                    "monsters": [{"name": "NonExistent Monster"}]
                }
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            exit_code, stdout, stderr = self._run_audit_script(self.module_name)
        finally:
            os.chdir(original_dir)
        
        self.assertEqual(exit_code, 1, f"Expected exit code 1, got {exit_code}. stdout: {stdout}")

    def test_strict_mode_heuristic_blockers_exit_code_1(self):
        """Verify strict mode with unresolved heuristic refs results in exit code 1."""
        # Create area with heuristic refs in strict-mode-only fields
        area_data = {
            "plotHooks": [
                "The party encounters a Mythic Beast in the forest."
            ]
        }
        
        area_file = os.path.join(self.module_path, "areas", "test_area.json")
        with open(area_file, 'w') as f:
            json.dump(area_data, f)
        
        original_dir = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            exit_code, stdout, stderr = self._run_audit_script(self.module_name, strict=True)
        finally:
            os.chdir(original_dir)
        
        self.assertEqual(exit_code, 1, f"Expected exit code 1 in strict mode, got {exit_code}. stdout: {stdout}")


class TestIntegrationSmoke(unittest.TestCase):
    """Integration smoke tests using real modules if available."""

    def test_normalize_slug_function(self):
        """Verify normalize_slug produces expected output."""
        test_cases = [
            ("Goblin Scout", "goblin_scout"),
            ("Dire Wolf", "dire_wolf"),
            ("Orc's Bane", "orc_s_bane"),
            ("  Spaced  Name  ", "spaced_name"),
            ("Multi   Space", "multi_space"),
        ]
        
        for input_name, expected_slug in test_cases:
            with self.subTest(input_name=input_name):
                result = normalize_slug(input_name)
                self.assertEqual(result, expected_slug)


if __name__ == "__main__":
    unittest.main(verbosity=2)
