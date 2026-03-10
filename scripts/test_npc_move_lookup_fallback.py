# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - NPC Move Lookup Fallback Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Real runtime tests for strict-then-fallback NPC lookup with mocks.
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub openai module for environments without it
if 'openai' not in sys.modules:
    openai_stub = type(sys)('openai')
    openai_stub.OpenAI = lambda *args, **kwargs: None
    sys.modules['openai'] = openai_stub

# Stub jsonschema module for environments without it
if 'jsonschema' not in sys.modules:
    jsonschema_stub = type(sys)('jsonschema')
    def mock_validate(*args, **kwargs):
        pass
    jsonschema_stub.validate = mock_validate
    class MockValidationError(Exception):
        pass
    jsonschema_stub.ValidationError = MockValidationError
    sys.modules['jsonschema'] = jsonschema_stub


class MockPathManager:
    """Minimal path manager mock for testing."""
    def __init__(self, module_dir):
        self.module_dir = module_dir


class TestFindNPCInAreasStrictThenFallback(unittest.TestCase):
    """Test find_npc_in_areas with strict-then-fallback strategy using mocks."""

    def setUp(self):
        """Set up test fixtures."""
        self.module_dir = "/test/module"
        self.path_manager = MockPathManager(self.module_dir)
        
        # Sample area data structures
        self.area_ro001 = {
            "locations": [
                {
                    "locationId": "RO03",
                    "name": "Road Encampment",
                    "npcs": [
                        {"name": "Bex", "type": "npc", "description": "Caravan guard"}
                    ]
                }
            ]
        }
        
        self.area_tw001 = {
            "locations": [
                {
                    "locationId": "TW03", 
                    "name": "Thornwood Watchtower",
                    "npcs": [
                        {"name": "Guard Captain", "type": "npc"}
                    ]
                }
            ]
        }
        
        self.area_multi_guard = {
            "locations": [
                {
                    "locationId": "LOC01",
                    "name": "Location One", 
                    "npcs": [
                        {"name": "Caravan Guard", "type": "npc"}
                    ]
                },
                {
                    "locationId": "LOC02",
                    "name": "Location Two",
                    "npcs": [
                        {"name": "Caravan Guard", "type": "npc"}
                    ]
                }
            ]
        }

    @patch('glob.glob')
    @patch('utils.file_operations.safe_read_json')
    def test_strict_hint_match_success(self, mock_read_json, mock_glob):
        """
        Strict hint match succeeds when NPC is at hinted location.
        
        Scenario: Looking for Bex with hint RO03, Bex is in RO03.
        Expected: strict_match status, fallback not attempted.
        """
        # Import inside test to allow patching
        from core.ai.action_handler import find_npc_in_areas
        
        # Setup mocks
        mock_glob.return_value = [f"{self.module_dir}/areas/RO001.json"]
        mock_read_json.return_value = self.area_ro001
        
        # Execute
        status, data = find_npc_in_areas("Bex", self.path_manager, location_hint="RO03")
        
        # Verify
        self.assertEqual(status, 'strict_match')
        self.assertIsNotNone(data)
        area_file, location_id, npc = data
        self.assertEqual(location_id, "RO03")
        self.assertEqual(npc["name"], "Bex")

    @patch('glob.glob')
    @patch('utils.file_operations.safe_read_json')
    def test_stale_hint_unambiguous_fallback_success(self, mock_read_json, mock_glob):
        """
        Stale hint + unique canonical match succeeds via fallback.
        
        Scenario: Looking for Bex with stale hint TW03, but Bex is actually in RO03.
        Expected: fallback_match status with resolved location.
        """
        from core.ai.action_handler import find_npc_in_areas
        
        # Setup mocks - hint TW03 but Bex is in RO03
        mock_glob.return_value = [
            f"{self.module_dir}/areas/RO001.json",
            f"{self.module_dir}/areas/TW001.json"
        ]
        
        def side_effect(filepath):
            if "RO001" in filepath:
                return self.area_ro001
            elif "TW001" in filepath:
                return self.area_tw001
            return None
        
        mock_read_json.side_effect = side_effect
        
        # Execute - stale hint TW03, but Bex is in RO03
        status, data = find_npc_in_areas("Bex", self.path_manager, location_hint="TW03")
        
        # Verify
        self.assertEqual(status, 'fallback_match')
        self.assertIsNotNone(data)
        area_file, location_id, npc = data
        self.assertEqual(location_id, "RO03")  # Resolved to actual location
        self.assertEqual(npc["name"], "Bex")

    @patch('glob.glob')
    @patch('utils.file_operations.safe_read_json')
    def test_ambiguous_fallback_fails_closed(self, mock_read_json, mock_glob):
        """
        Stale hint + multiple matches fails closed with ambiguity status.
        
        Scenario: Searching for "Caravan Guard" with stale hint,
        but multiple "Caravan Guard" NPCs exist in different locations.
        Expected: ambiguous status with list of matches, no unsafe resolution.
        """
        from core.ai.action_handler import find_npc_in_areas
        
        # Setup mocks - multiple guards in different locations
        mock_glob.return_value = [f"{self.module_dir}/areas/MULTI.json"]
        mock_read_json.return_value = self.area_multi_guard
        
        # Execute - stale hint, multiple matches exist
        status, data = find_npc_in_areas("Caravan Guard", self.path_manager, location_hint="STALE01")
        
        # Verify
        self.assertEqual(status, 'ambiguous')
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 2)  # Two matches
        locations = [loc_id for _, loc_id, _ in data]
        self.assertIn("LOC01", locations)
        self.assertIn("LOC02", locations)

    @patch('glob.glob')
    @patch('utils.file_operations.safe_read_json')
    def test_no_match_returns_not_found(self, mock_read_json, mock_glob):
        """
        No match anywhere returns not_found status.
        
        Scenario: NPC name doesn't exist in any location.
        Expected: not_found status, data is None.
        """
        from core.ai.action_handler import find_npc_in_areas
        
        # Setup mocks - no matching NPC
        mock_glob.return_value = [f"{self.module_dir}/areas/EMPTY.json"]
        mock_read_json.return_value = {"locations": [{"locationId": "EMPTY", "npcs": []}]}
        
        # Execute
        status, data = find_npc_in_areas("NonExistentNPC", self.path_manager)
        
        # Verify
        self.assertEqual(status, 'not_found')
        self.assertIsNone(data)

    @patch('glob.glob')
    @patch('utils.file_operations.safe_read_json')
    def test_no_hint_searches_all_locations(self, mock_read_json, mock_glob):
        """
        No location hint searches all locations (canonical search only).
        
        Scenario: Looking for Bex without any hint.
        Expected: fallback_match (treated as canonical-only search).
        """
        from core.ai.action_handler import find_npc_in_areas
        
        # Setup mocks
        mock_glob.return_value = [f"{self.module_dir}/areas/RO001.json"]
        mock_read_json.return_value = self.area_ro001
        
        # Execute without hint
        status, data = find_npc_in_areas("Bex", self.path_manager, location_hint=None)
        
        # Verify - treated as canonical search since no hint provided
        self.assertEqual(status, 'fallback_match')
        self.assertIsNotNone(data)
        area_file, location_id, npc = data
        self.assertEqual(npc["name"], "Bex")


if __name__ == "__main__":
    # Run tests with verbosity
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFindNPCInAreasStrictThenFallback))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
