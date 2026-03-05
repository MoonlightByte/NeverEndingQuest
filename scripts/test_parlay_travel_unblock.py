# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Regression tests for peaceful hostile resolution travel unblock.
Ensures resolved hostile locations don't block travel.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Test coverage:
- Baseline: unresolved hostile location with monsters blocks travel
- Resolution marker: resolved location with monsters does NOT block
- Legacy: encounter-entry visited logic still works
- Fail-open: missing resolvedHostilesByLocation preserves baseline
"""

import unittest
import json
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.path_encounter_analyzer import analyze_path_for_encounters
from core.ai.transition_atlas_builder import build_transition_atlas
from utils.multi_pc_dm_note import build_standard_dm_note


class MockLocationGraph:
    """Mock location graph for testing."""

    def __init__(self, area_data=None, nodes=None, edges=None):
        self.area_data = area_data or {}
        self.nodes = nodes or {}
        self.edges = edges or {}


class TestParlayTravelUnblock(unittest.TestCase):
    """Test cases for peaceful resolution travel unblock."""

    def setUp(self):
        """Set up common test fixtures."""
        self.module_name = "test_module"
        self.location_id = "V04"
        self.area_id = "BOO001"
        self.location_name = "Petitioner's Rest"
        self.area_name = "Fields of Supplication"

    def _create_mock_graph(self, has_monsters=True):
        """Create a mock location graph."""
        nodes = {
            self.location_id: {
                "area_id": self.area_id,
                "location_name": self.location_name
            }
        }
        area_data = {
            self.area_id: {
                "areaName": self.area_name
            }
        }
        return MockLocationGraph(area_data=area_data, nodes=nodes)

    def _create_area_data(self, monsters=None, encounters=None):
        """Create area JSON data with monsters and encounters."""
        return {
            "locations": [{
                "locationId": self.location_id,
                "name": self.location_name,
                "monsters": monsters or [],
                "encounters": encounters or []
            }]
        }

    @patch("utils.path_encounter_analyzer.safe_read_json")
    @patch("utils.path_encounter_analyzer.os.path.exists")
    @patch("utils.path_encounter_analyzer.ModulePathManager")
    def test_unresolved_hostile_blocks_travel(self, mock_path_manager_cls, mock_exists, mock_read_json):
        """Test 1: Unresolved hostile location with monsters blocks travel (baseline)."""
        # Setup: location has monsters, no encounters, no resolution
        area_data = self._create_area_data(
            monsters=[{"name": "Bloodshadow"}],
            encounters=[]  # No gameplay encounters = not visited
        )
        mock_read_json.return_value = area_data
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph(has_monsters=True)
        path = [self.location_id]

        # No world_conditions = baseline behavior
        result = analyze_path_for_encounters(path, graph, self.module_name)

        # Assertions
        self.assertTrue(result["has_unexplored"])
        self.assertEqual(result["first_blocking_location"], self.location_id)
        self.assertTrue(result["requires_stop"])
        self.assertFalse(result["safe_to_auto_travel"])

        segment = result["path_segments"][0]
        self.assertTrue(segment["has_monsters"])
        self.assertFalse(segment["has_encounter_entries"])
        self.assertFalse(segment["is_resolved"])
        self.assertTrue(segment["blocks_travel"])
        self.assertEqual(segment["status"], "unexplored")

    @patch("utils.path_encounter_analyzer.safe_read_json")
    @patch("utils.path_encounter_analyzer.os.path.exists")
    @patch("utils.path_encounter_analyzer.ModulePathManager")
    def test_resolved_location_does_not_block(self, mock_path_manager_cls, mock_exists, mock_read_json):
        """Test 2: Resolved location with monsters does NOT block travel."""
        # Setup: location has monsters, but is marked resolved
        area_data = self._create_area_data(
            monsters=[{"name": "Bloodshadow"}],
            encounters=[]  # No gameplay encounters
        )
        mock_read_json.return_value = area_data
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph(has_monsters=True)
        path = [self.location_id]

        # Pass world_conditions with resolved marker
        world_conditions = {
            "resolvedHostilesByLocation": {
                self.location_id: True
            }
        }

        result = analyze_path_for_encounters(path, graph, self.module_name, world_conditions)

        # Assertions: Should NOT block despite monsters
        self.assertFalse(result["has_unexplored"])
        self.assertIsNone(result["first_blocking_location"])
        self.assertFalse(result["requires_stop"])
        self.assertTrue(result["safe_to_auto_travel"])

        segment = result["path_segments"][0]
        self.assertTrue(segment["has_monsters"])
        self.assertFalse(segment["has_encounter_entries"])
        self.assertTrue(segment["is_resolved"])
        self.assertFalse(segment["blocks_travel"])
        self.assertEqual(segment["status"], "visited")

    @patch("utils.path_encounter_analyzer.safe_read_json")
    @patch("utils.path_encounter_analyzer.os.path.exists")
    @patch("utils.path_encounter_analyzer.ModulePathManager")
    def test_encounter_entry_visited_still_works(self, mock_path_manager_cls, mock_exists, mock_read_json):
        """Test 3: Encounter-entry visited logic still works as before."""
        # Setup: location has monsters AND gameplay encounter entries
        area_data = self._create_area_data(
            monsters=[{"name": "Bloodshadow"}],
            encounters=[
                {"encounterId": "enc_001", "summary": "Combat resolved"}
            ]
        )
        mock_read_json.return_value = area_data
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph(has_monsters=True)
        path = [self.location_id]

        # No resolution marker, but has encounter entries
        result = analyze_path_for_encounters(path, graph, self.module_name)

        # Assertions: Should be visited via encounter entries
        self.assertFalse(result["has_unexplored"])
        self.assertIsNone(result["first_blocking_location"])
        self.assertFalse(result["requires_stop"])
        self.assertTrue(result["safe_to_auto_travel"])

        segment = result["path_segments"][0]
        self.assertTrue(segment["has_monsters"])
        self.assertTrue(segment["has_encounter_entries"])
        self.assertFalse(segment["is_resolved"])  # Not resolved via world_conditions
        self.assertFalse(segment["blocks_travel"])
        self.assertEqual(segment["status"], "visited")

    @patch("utils.path_encounter_analyzer.safe_read_json")
    @patch("utils.path_encounter_analyzer.os.path.exists")
    @patch("utils.path_encounter_analyzer.ModulePathManager")
    def test_missing_resolved_key_preserves_baseline(self, mock_path_manager_cls, mock_exists, mock_read_json):
        """Test 4: Missing resolvedHostilesByLocation key preserves baseline behavior."""
        # Setup: location has monsters, no encounters
        area_data = self._create_area_data(
            monsters=[{"name": "Bloodshadow"}],
            encounters=[]
        )
        mock_read_json.return_value = area_data
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph(has_monsters=True)
        path = [self.location_id]

        # Pass empty world_conditions (no resolvedHostilesByLocation)
        world_conditions = {}

        result = analyze_path_for_encounters(path, graph, self.module_name, world_conditions)

        # Assertions: Should block (same as no world_conditions)
        self.assertTrue(result["has_unexplored"])
        self.assertEqual(result["first_blocking_location"], self.location_id)
        self.assertTrue(result["requires_stop"])

        segment = result["path_segments"][0]
        self.assertFalse(segment["is_resolved"])
        self.assertTrue(segment["blocks_travel"])

    @patch("utils.path_encounter_analyzer.safe_read_json")
    @patch("utils.path_encounter_analyzer.os.path.exists")
    @patch("utils.path_encounter_analyzer.ModulePathManager")
    def test_none_world_conditions(self, mock_path_manager_cls, mock_exists, mock_read_json):
        """Test 5: None world_conditions is backward compatible."""
        # Setup: location has monsters
        area_data = self._create_area_data(
            monsters=[{"name": "Bloodshadow"}],
            encounters=[]
        )
        mock_read_json.return_value = area_data
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph(has_monsters=True)
        path = [self.location_id]

        # Pass None explicitly
        result = analyze_path_for_encounters(path, graph, self.module_name, None)

        # Assertions: Should block (baseline)
        self.assertTrue(result["requires_stop"])
        segment = result["path_segments"][0]
        self.assertFalse(segment["is_resolved"])


class TestTransitionAtlasParity(unittest.TestCase):
    """Test cases for atlas parity with analyzer resolution logic."""

    def setUp(self):
        """Set up common test fixtures."""
        self.module_name = "test_module"
        self.location_id = "V04"
        self.area_id = "BOO001"
        self.location_name = "Petitioner's Rest"
        self.area_name = "Fields of Supplication"

    def _create_mock_graph(self):
        """Create a mock location graph with edges for atlas compatibility."""
        nodes = {
            self.location_id: {
                "area_id": self.area_id,
                "location_name": self.location_name,
                "data": {"type": "outdoor"}
            }
        }
        area_data = {
            self.area_id: {
                "areaName": self.area_name
            }
        }
        return MockLocationGraph(area_data=area_data, nodes=nodes, edges={})

    @patch("core.ai.transition_atlas_builder.safe_read_json")
    @patch("core.ai.transition_atlas_builder.os.path.exists")
    @patch("core.ai.transition_atlas_builder.ModulePathManager")
    def test_atlas_shows_resolved_marker(self, mock_path_manager_cls, mock_exists, mock_read_json):
        """Test 6: Atlas shows [RESOLVED - SAFE] for location resolved via world marker."""
        # Setup: location has monsters but is resolved in world state
        area_data = {
            "locations": [{
                "locationId": self.location_id,
                "monsters": [{"name": "Bloodshadow"}],
                "encounters": []  # No gameplay encounters
            }]
        }
        mock_read_json.return_value = area_data
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph()
        world_conditions = {
            "resolvedHostilesByLocation": {self.location_id: True}
        }

        atlas = build_transition_atlas(graph, self.module_name, world_conditions)

        # Assertions: Should show RESOLVED - SAFE
        self.assertIn("[RESOLVED - SAFE]", atlas)
        self.assertIn(self.location_id, atlas)

    @patch("core.ai.transition_atlas_builder.safe_read_json")
    @patch("core.ai.transition_atlas_builder.os.path.exists")
    @patch("core.ai.transition_atlas_builder.ModulePathManager")
    def test_atlas_shows_unexplored_monsters_for_unresolved(self, mock_path_manager_cls, mock_exists, mock_read_json):
        """Test 7: Atlas shows [UNEXPLORED - HAS MONSTERS] for unresolved hostile location."""
        # Setup: location has monsters, not resolved, no encounters
        area_data = {
            "locations": [{
                "locationId": self.location_id,
                "monsters": [{"name": "Bloodshadow"}],
                "encounters": []
            }]
        }
        mock_read_json.return_value = area_data
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph()
        world_conditions = {}  # No resolution marker

        atlas = build_transition_atlas(graph, self.module_name, world_conditions)

        # Assertions: Should show UNEXPLORED - HAS MONSTERS
        self.assertIn("[UNEXPLORED - HAS MONSTERS]", atlas)
        self.assertIn("Bloodshadow", atlas)

    @patch("utils.path_encounter_analyzer.safe_read_json")
    @patch("utils.path_encounter_analyzer.os.path.exists")
    @patch("utils.path_encounter_analyzer.ModulePathManager")
    @patch("core.ai.transition_atlas_builder.safe_read_json")
    @patch("core.ai.transition_atlas_builder.os.path.exists")
    @patch("core.ai.transition_atlas_builder.ModulePathManager")
    def test_analyzer_and_atlas_agree_on_resolved(self,
                                                   mock_atlas_pm, mock_atlas_exists, mock_atlas_read,
                                                   mock_analyzer_pm, mock_analyzer_exists, mock_analyzer_read):
        """Test 8: Atlas and analyzer agree on blocking status for resolved marker case."""
        # Setup same data for both
        area_data = {
            "locations": [{
                "locationId": self.location_id,
                "monsters": [{"name": "Bloodshadow"}],
                "encounters": []  # No gameplay encounters
            }]
        }

        # Configure both mocks
        mock_analyzer_read.return_value = area_data
        mock_analyzer_exists.return_value = True
        mock_analyzer_pm_instance = MagicMock()
        mock_analyzer_pm_instance.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_analyzer_pm.return_value = mock_analyzer_pm_instance

        mock_atlas_read.return_value = area_data
        mock_atlas_exists.return_value = True
        mock_atlas_pm_instance = MagicMock()
        mock_atlas_pm_instance.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_atlas_pm.return_value = mock_atlas_pm_instance

        graph_nodes = {
            self.location_id: {
                "area_id": self.area_id,
                "location_name": self.location_name
            }
        }
        graph_area_data = {self.area_id: {"areaName": self.area_name}}
        graph = MockLocationGraph(area_data=graph_area_data, nodes=graph_nodes)

        world_conditions = {
            "resolvedHostilesByLocation": {self.location_id: True}
        }

        # Run both
        analyzer_result = analyze_path_for_encounters(
            [self.location_id], graph, self.module_name, world_conditions
        )

        # Atlas needs nodes with data key for loc_type
        graph.nodes[self.location_id]["data"] = {"type": "outdoor"}
        atlas = build_transition_atlas(graph, self.module_name, world_conditions)

        # Assertions: Both should agree this location does not block
        self.assertFalse(analyzer_result["requires_stop"])
        self.assertIn("[RESOLVED - SAFE]", atlas)
        # Check location line specifically (not legend) - location line should not have UNEXPLORED marker
        for line in atlas.split("\n"):
            if self.location_id in line and "Petitioner's Rest" in line:
                self.assertIn("[RESOLVED - SAFE]", line)
                self.assertNotIn("[UNEXPLORED", line)
                break

    @patch("core.ai.transition_atlas_builder.safe_read_json")
    @patch("core.ai.transition_atlas_builder.os.path.exists")
    @patch("core.ai.transition_atlas_builder.ModulePathManager")
    def test_atlas_backward_compatible_without_world_conditions(self, mock_path_manager_cls, mock_exists, mock_read_json):
        """Test 9: Atlas keeps prior behavior when world_conditions is missing/None."""
        # Setup: location has monsters, no encounters
        area_data = {
            "locations": [{
                "locationId": self.location_id,
                "monsters": [{"name": "Bloodshadow"}],
                "encounters": []
            }]
        }
        mock_read_json.return_value = area_data
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = "/mock/path/BOO001.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph()

        # Test with None
        atlas_none = build_transition_atlas(graph, self.module_name, None)
        self.assertIn("[UNEXPLORED - HAS MONSTERS]", atlas_none)

        # Test with empty dict
        atlas_empty = build_transition_atlas(graph, self.module_name, {})
        self.assertIn("[UNEXPLORED - HAS MONSTERS]", atlas_empty)

        # Test without param (backward compat)
        atlas_no_arg = build_transition_atlas(graph, self.module_name)
        self.assertIn("[UNEXPLORED - HAS MONSTERS]", atlas_no_arg)


class TestPromptContract(unittest.TestCase):
    """Test cases for prompt contract consistency with resolution mechanics."""

    def test_system_prompt_includes_resolution_terms(self):
        """Test 10: System prompt includes resolution key terms."""
        # Read system prompt file
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "system_prompt_compressed.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("System prompt file not found at expected path")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify key terms are present
        self.assertIn("resolvedHostilesByLocation", content,
                     "System prompt should mention resolvedHostilesByLocation for travel unblocking")
        self.assertIn("peacefulResolution", content,
                     "System prompt should include peacefulResolution guidance for parlay scenarios")

    def test_system_prompt_mentions_update_party_tracker(self):
        """Test 11: System prompt links resolution to updatePartyTracker action."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "system_prompt_compressed.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("System prompt file not found at expected path")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify action contract reference
        self.assertIn("updatePartyTracker", content,
                     "System prompt should reference updatePartyTracker for persisting resolution")


class TestPersistenceContract(unittest.TestCase):
    """Test cases for persistence contract verification in source code."""

    def test_action_handler_handles_resolved_hostiles_directly(self):
        """Test 12: Merge utility explicitly handles resolvedHostilesByLocation."""
        merge_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "utils", "party_tracker_merge.py"
        )

        if not os.path.exists(merge_path):
            self.skipTest("Merge utility file not found at expected path")

        with open(merge_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify explicit handling exists
        self.assertIn('elif key == "resolvedHostilesByLocation":', content,
                     "Merge utility should have explicit branch for resolvedHostilesByLocation")

    def test_action_handler_handles_world_conditions_dict(self):
        """Test 13: Merge utility explicitly handles worldConditions dict merge."""
        merge_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "utils", "party_tracker_merge.py"
        )

        if not os.path.exists(merge_path):
            self.skipTest("Merge utility file not found at expected path")

        with open(merge_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify worldConditions dict handling
        self.assertIn('elif key == "worldConditions":', content,
                     "Merge utility should have explicit branch for worldConditions dict")

    def test_action_handler_merges_nested_location_markers(self):
        """Test 14: Merge utility merges resolvedHostilesByLocation non-destructively."""
        merge_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "utils", "party_tracker_merge.py"
        )

        if not os.path.exists(merge_path):
            self.skipTest("Merge utility file not found at expected path")

        with open(merge_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify merge behavior (using .update() pattern for preservation)
        self.assertIn('.update(value)', content,
                     "Merge utility should use .update() to merge location markers")


class TestPromptContractParity(unittest.TestCase):
    """Test cases for prompt contract parity across all prompt files."""

    def test_system_prompt_contains_resolution_marker_contract(self):
        """Test 15: System prompt includes resolvedHostilesByLocation in updatePartyTracker params."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "system_prompt_compressed.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("System prompt file not found at expected path")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify updatePartyTracker contract includes resolution marker
        self.assertIn('resolvedHostilesByLocation', content,
                     "System prompt should include resolvedHostilesByLocation in updatePartyTracker contract")
        self.assertIn('worldConditions', content,
                     "System prompt should include worldConditions in updatePartyTracker contract")

    def test_validation_prompt_compressed_contains_resolution_marker_contract(self):
        """Test 16: Compressed validation prompt includes resolvedHostilesByLocation in updatePartyTracker params."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt_compressed.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("Compressed validation prompt file not found at expected path")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify updatePartyTracker contract includes resolution marker
        self.assertIn('resolvedHostilesByLocation', content,
                     "Compressed validation prompt should include resolvedHostilesByLocation in updatePartyTracker contract")
        self.assertIn('worldConditions', content,
                     "Compressed validation prompt should include worldConditions in updatePartyTracker contract")

    def test_validation_prompt_uncompressed_contains_resolution_marker_contract(self):
        """Test 17: Uncompressed validation prompt includes resolvedHostilesByLocation in updatePartyTracker params."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("Uncompressed validation prompt file not found at expected path")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify updatePartyTracker contract includes resolution marker
        self.assertIn('resolvedHostilesByLocation', content,
                     "Uncompressed validation prompt should include resolvedHostilesByLocation in updatePartyTracker contract")
        self.assertIn('worldConditions', content,
                     "Uncompressed validation prompt should include worldConditions in updatePartyTracker contract")

    def test_all_prompts_parity_for_resolution_markers(self):
        """Test 18: All three prompt files have parity for resolution marker contract."""
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        prompt_files = [
            ("system_prompt_compressed.txt", os.path.join(base_path, "prompts", "system_prompt_compressed.txt")),
            ("validation_prompt_compressed.txt", os.path.join(base_path, "prompts", "validation", "validation_prompt_compressed.txt")),
            ("validation_prompt.txt", os.path.join(base_path, "prompts", "validation", "validation_prompt.txt"))
        ]
        
        for name, path in prompt_files:
            if not os.path.exists(path):
                self.skipTest(f"Prompt file {name} not found")
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Each file must have both contract terms
            self.assertIn('resolvedHostilesByLocation', content,
                         f"{name} must include resolvedHostilesByLocation")
            self.assertIn('worldConditions', content,
                         f"{name} must include worldConditions")


class TestDMNoteResolvedBehavior(unittest.TestCase):
    """Test cases for DM-note conditional threat guidance based on resolved state."""

    def test_dm_note_builder_includes_resolved_state_check(self):
        """Test 19: DM note builder contains resolved state conditional logic."""
        import inspect
        from utils.multi_pc_dm_note import build_multi_pc_dm_note, build_standard_dm_note
        
        # Check build_multi_pc_dm_note source
        source = inspect.getsource(build_multi_pc_dm_note)
        self.assertIn('resolvedHostilesByLocation', source,
                     "build_multi_pc_dm_note should check resolvedHostilesByLocation")
        self.assertIn('is_resolved_here', source,
                     "build_multi_pc_dm_note should have is_resolved_here variable")
        self.assertIn('Resolved Hostile State', source,
                     "build_multi_pc_dm_note should have resolved hostile state guidance")
        
        # Check build_standard_dm_note source
        source = inspect.getsource(build_standard_dm_note)
        self.assertIn('resolvedHostilesByLocation', source,
                     "build_standard_dm_note should check resolvedHostilesByLocation")
        self.assertIn('is_resolved_here', source,
                     "build_standard_dm_note should have is_resolved_here variable")

    def test_main_dm_note_builder_includes_resolved_state_check(self):
        """Test 20: Main DM note builder contains resolved state conditional logic."""
        # Read main.py DM note construction section
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py"
        )
        
        if not os.path.exists(main_path):
            self.skipTest("main.py not found")
        
        with open(main_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verify resolved state logic exists
        self.assertIn('resolvedHostilesByLocation', content,
                     "main.py DM note builder should check resolvedHostilesByLocation")
        self.assertIn('is_resolved_here', content,
                     "main.py DM note builder should have is_resolved_here variable")
        self.assertIn('threat_guidance', content,
                     "main.py DM note builder should have threat_guidance variable")

    def test_resolved_guidance_text_differs_from_unresolved(self):
        """Test 21: Resolved and unresolved guidance text are distinct."""
        from utils.multi_pc_dm_note import build_multi_pc_dm_note
        
        # Check that both guidance messages exist in source
        import inspect
        source = inspect.getsource(build_multi_pc_dm_note)
        
        self.assertIn('Resolved Hostile State', source,
                     "Should have resolved hostile state guidance")
        self.assertIn('Monsters should be active threats', source,
                     "Should have unresolved active threats guidance")
        
        # Verify they're in conditional branches
        self.assertIn('if is_resolved_here', source,
                     "Guidance should be conditional on is_resolved_here")


class TestAntiLoopValidationRules(unittest.TestCase):
    """Test cases for anti-loop validation guardrail in prompt files."""

    def test_validation_prompt_compressed_contains_anti_loop_rule(self):
        """Test 22: Compressed validation prompt includes anti-loop prevention rule."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt_compressed.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("Compressed validation prompt file not found")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify anti-loop rule exists
        self.assertIn('@PARLAY_LOOP_PREVENTION', content,
                     "Compressed validation prompt should have @PARLAY_LOOP_PREVENTION rule block")
        self.assertIn('Repeated blocker loop', content,
                     "Should have fail_reason text for repeated blocker loops")
        self.assertIn('actions:[]', content,
                     "Should reference empty actions array in loop detection")

    def test_validation_prompt_uncompressed_contains_anti_loop_rule(self):
        """Test 23: Uncompressed validation prompt includes anti-loop prevention rule."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("Uncompressed validation prompt file not found")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify anti-loop rule exists
        self.assertIn('PARLAY LOOP PREVENTION', content,
                     "Uncompressed validation prompt should have PARLAY LOOP PREVENTION section")
        self.assertIn('Repeated blocker loop', content,
                     "Should have fail_reason text for repeated blocker loops")
        self.assertIn('actions:[]', content,
                     "Should reference empty actions array in loop detection")
        self.assertIn('resolvedHostilesByLocation', content,
                     "Should mention state sync via resolvedHostilesByLocation")

    def test_all_validation_prompts_have_parlay_loop_prevention(self):
        """Test 24: Both validation prompts have parlay loop prevention coverage."""
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        validation_files = [
            ("validation_prompt_compressed.txt", os.path.join(base_path, "prompts", "validation", "validation_prompt_compressed.txt")),
            ("validation_prompt.txt", os.path.join(base_path, "prompts", "validation", "validation_prompt.txt"))
        ]
        
        for name, path in validation_files:
            if not os.path.exists(path):
                self.skipTest(f"Validation prompt file {name} not found")
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Each validation file must have loop prevention rule
            has_rule = '@PARLAY_LOOP_PREVENTION' in content or 'PARLAY LOOP PREVENTION' in content
            self.assertTrue(has_rule,
                           f"{name} must include parlay loop prevention rule")
            
            # Must specify required actions for valid responses
            self.assertIn('transitionLocation', content,
                         f"{name} must mention transitionLocation as valid resolution")
            self.assertIn('updatePartyTracker', content,
                         f"{name} must mention updatePartyTracker as valid resolution")


class TestPassageStateSync(unittest.TestCase):
    """Test cases for passage state sync validation rule in prompt files."""

    def test_validation_prompt_compressed_contains_passage_state_sync(self):
        """Test 25: Compressed validation prompt includes @PASSAGE_STATE_SYNC rule."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt_compressed.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("Compressed validation prompt file not found")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify passage state sync rule exists
        self.assertIn('@PASSAGE_STATE_SYNC', content,
                     "Compressed validation prompt should have @PASSAGE_STATE_SYNC rule block")
        self.assertIn('Missing passage state sync', content,
                     "Should have fail_reason for missing state sync")
        self.assertIn('resolvedHostilesByLocation', content,
                     "Should mention resolvedHostilesByLocation requirement")
        self.assertIn('updatePartyTracker', content,
                     "Should require updatePartyTracker action")

    def test_validation_prompt_uncompressed_contains_passage_state_sync(self):
        """Test 26: Uncompressed validation prompt includes PASSAGE STATE SYNCHRONIZATION section."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts", "validation", "validation_prompt.txt"
        )

        if not os.path.exists(prompt_path):
            self.skipTest("Uncompressed validation prompt file not found")

        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Verify passage state sync section exists
        self.assertIn('PASSAGE STATE SYNCHRONIZATION VALIDATION RULES', content,
                     "Uncompressed validation prompt should have PASSAGE STATE SYNCHRONIZATION section")
        self.assertIn('Missing passage state sync', content,
                     "Should have fail_reason for missing state sync")
        self.assertIn('resolvedHostilesByLocation', content,
                     "Should mention resolvedHostilesByLocation requirement")
        self.assertIn('updatePartyTracker', content,
                     "Should require updatePartyTracker action")

    def test_all_validation_prompts_have_passage_state_sync_coverage(self):
        """Test 27: Both validation prompts include passage state sync rule."""
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        validation_files = [
            ("validation_prompt_compressed.txt", os.path.join(base_path, "prompts", "validation", "validation_prompt_compressed.txt")),
            ("validation_prompt.txt", os.path.join(base_path, "prompts", "validation", "validation_prompt.txt"))
        ]
        
        for name, path in validation_files:
            if not os.path.exists(path):
                self.skipTest(f"Validation prompt file {name} not found")
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Each validation file must have passage state sync rule
            has_compressed_rule = '@PASSAGE_STATE_SYNC' in content
            has_uncompressed_rule = 'PASSAGE STATE SYNCHRONIZATION VALIDATION RULES' in content
            self.assertTrue(has_compressed_rule or has_uncompressed_rule,
                           f"{name} must include passage state sync rule")
            
            # Must mention updatePartyTracker and resolvedHostilesByLocation
            self.assertIn('updatePartyTracker', content,
                         f"{name} must mention updatePartyTracker for passage state sync")
            self.assertIn('resolvedHostilesByLocation', content,
                         f"{name} must mention resolvedHostilesByLocation for passage state sync")


class TestFunctionalEndToEndResolution(unittest.TestCase):
    """Functional integration tests for complete resolution flow."""

    def setUp(self):
        """Set up common test fixtures."""
        self.module_name = "test_module"
        self.location_id = "V04"
        self.area_id = "BOO001"
        self.location_name = "Petitioner's Rest"
        self.area_name = "Fields of Supplication"

    def _create_mock_graph_with_monsters(self):
        """Create a mock location graph with monsters at V04."""
        nodes = {
            self.location_id: {
                "area_id": self.area_id,
                "location_name": self.location_name,
                "data": {"type": "outdoor"}
            }
        }
        area_data = {
            self.area_id: {
                "areaName": self.area_name
            }
        }
        return MockLocationGraph(area_data=area_data, nodes=nodes, edges={})

    def _get_location_data_with_monsters(self):
        """Get location data dict with monsters."""
        return {
            "locations": [{
                "locationId": self.location_id,
                "locationName": self.location_name,
                "monsters": [{"name": "Bloodshadow"}],
                "encounters": []
            }]
        }

    @patch("utils.path_encounter_analyzer.safe_read_json")
    @patch("utils.path_encounter_analyzer.os.path.exists")
    @patch("utils.path_encounter_analyzer.ModulePathManager")
    def test_resolved_location_allows_travel_behavior(
        self, mock_path_manager_cls, mock_exists, mock_read_json
    ):
        """Test 28: Resolved location with monsters does NOT block travel."""
        # Setup: location has monsters but is resolved
        mock_read_json.return_value = self._get_location_data_with_monsters()
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = f"/mock/path/{self.area_id}.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph_with_monsters()
        world_conditions = {
            "resolvedHostilesByLocation": {self.location_id: True}
        }

        # Execute analyzer
        result = analyze_path_for_encounters(
            [self.location_id], graph, self.module_name, world_conditions
        )

        # Assertions: travel should NOT be blocked
        self.assertFalse(result["requires_stop"], 
                         "Resolved location should not require stop")
        self.assertIsNone(result["first_blocking_location"],
                          "Resolved location should not be blocking location")
        self.assertTrue(result["safe_to_auto_travel"],
                        "Resolved location should allow auto travel")
        
        # Verify segment details
        segment = result["path_segments"][0]
        self.assertFalse(segment["blocks_travel"],
                         "Resolved location segment should not block travel")
        self.assertTrue(segment["is_resolved"],
                        "Segment should show is_resolved = True")
        self.assertEqual(segment["status"], "visited",
                         "Resolved location should have visited status")

    @patch("core.ai.transition_atlas_builder.safe_read_json")
    @patch("core.ai.transition_atlas_builder.os.path.exists")
    @patch("core.ai.transition_atlas_builder.ModulePathManager")
    def test_atlas_shows_resolved_safe_marker_behavior(
        self, mock_path_manager_cls, mock_exists, mock_read_json
    ):
        """Test 29: Atlas shows [RESOLVED - SAFE] for resolved location."""
        # Setup
        mock_read_json.return_value = self._get_location_data_with_monsters()
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = f"/mock/path/{self.area_id}.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph_with_monsters()
        world_conditions = {
            "resolvedHostilesByLocation": {self.location_id: True}
        }

        # Execute atlas builder
        atlas = build_transition_atlas(graph, self.module_name, world_conditions)

        # Assertions: atlas should show resolved-safe marker
        self.assertIn("[RESOLVED - SAFE]", atlas,
                      "Atlas should show [RESOLVED - SAFE] marker")
        self.assertIn(self.location_id, atlas,
                      "Atlas should include location ID")
        
        # Verify location line specifically shows resolved marker (not unexplored)
        for line in atlas.split("\n"):
            if self.location_id in line and self.location_name in line:
                self.assertIn("[RESOLVED - SAFE]", line,
                              "Location line should show resolved-safe, not unexplored")
                self.assertNotIn("[UNEXPLORED", line,
                                 "Resolved location should not show unexplored marker")
                break

    @patch("utils.path_encounter_analyzer.safe_read_json")
    @patch("utils.path_encounter_analyzer.os.path.exists")
    @patch("utils.path_encounter_analyzer.ModulePathManager")
    def test_unresolved_location_with_monsters_blocks_travel_behavior(
        self, mock_path_manager_cls, mock_exists, mock_read_json
    ):
        """Test 30: Unresolved location with monsters DOES block travel (control case)."""
        # Setup: location has monsters, NOT resolved
        mock_read_json.return_value = self._get_location_data_with_monsters()
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = f"/mock/path/{self.area_id}.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph_with_monsters()
        world_conditions = {}  # No resolution marker

        # Execute analyzer
        result = analyze_path_for_encounters(
            [self.location_id], graph, self.module_name, world_conditions
        )

        # Assertions: travel SHOULD be blocked
        self.assertTrue(result["requires_stop"],
                        "Unresolved location with monsters should require stop")
        self.assertEqual(result["first_blocking_location"], self.location_id,
                         "Blocking location should be V04")
        self.assertFalse(result["safe_to_auto_travel"],
                         "Unresolved location should not allow auto travel")
        
        # Verify segment details
        segment = result["path_segments"][0]
        self.assertTrue(segment["blocks_travel"],
                        "Unresolved location segment should block travel")
        self.assertFalse(segment["is_resolved"],
                         "Segment should show is_resolved = False")
        self.assertEqual(segment["status"], "unexplored",
                         "Unresolved location should have unexplored status")

    @patch("core.ai.transition_atlas_builder.safe_read_json")
    @patch("core.ai.transition_atlas_builder.os.path.exists")
    @patch("core.ai.transition_atlas_builder.ModulePathManager")
    def test_atlas_shows_unexplored_monsters_for_unresolved_behavior(
        self, mock_path_manager_cls, mock_exists, mock_read_json
    ):
        """Test 31: Atlas shows [UNEXPLORED - HAS MONSTERS] for unresolved location (control case)."""
        # Setup
        mock_read_json.return_value = self._get_location_data_with_monsters()
        mock_exists.return_value = True
        mock_path_manager = MagicMock()
        mock_path_manager.get_area_path.return_value = f"/mock/path/{self.area_id}.json"
        mock_path_manager_cls.return_value = mock_path_manager

        graph = self._create_mock_graph_with_monsters()
        world_conditions = {}  # No resolution marker

        # Execute atlas builder
        atlas = build_transition_atlas(graph, self.module_name, world_conditions)

        # Assertions: atlas should show unexplored monsters marker
        self.assertIn("[UNEXPLORED - HAS MONSTERS]", atlas,
                      "Atlas should show [UNEXPLORED - HAS MONSTERS] marker")
        self.assertIn("Bloodshadow", atlas,
                      "Atlas should list monster name")


class TestDMNoteFunctionalOutput(unittest.TestCase):
    """Functional DM-note output assertions for resolved hostile state."""

    def setUp(self):
        """Set up common test fixtures."""
        self.location_id = "V04"
        self.location_name = "Petitioner's Rest"
        self.area_id = "BOO001"
        self.area_name = "Fields of Supplication"

    def _create_party_tracker_with_resolved_marker(self):
        """Create party tracker with resolved hostile marker for V04."""
        return {
            "partyMembers": ["Anselara", "zeug"],
            "worldConditions": {
                "resolvedHostilesByLocation": {self.location_id: True},
                "currentLocationId": self.location_id
            }
        }

    def _create_party_tracker_without_resolved_marker(self):
        """Create party tracker without resolved marker."""
        return {
            "partyMembers": ["Anselara", "zeug"],
            "worldConditions": {
                "currentLocationId": self.location_id
            }
        }

    def test_resolved_marker_changes_guidance(self):
        """Test 32: Resolved marker changes DM-note guidance to resolved state."""
        party_tracker_data = self._create_party_tracker_with_resolved_marker()
        world_conditions = party_tracker_data.get("worldConditions", {})
        
        dm_note = build_standard_dm_note(
            party_tracker_data=party_tracker_data,
            world_conditions=world_conditions,
            date_time_str="1492 Springmonth 2, 7:25 AM",
            current_season="Spring",
            current_module_name="The_Pumpkin_Kings_Curse",
            current_location_name=self.location_name,
            current_location_id=self.location_id,
            current_area_name=self.area_name,
            party_stats_str="HP 17/17",
            party_npcs_str="Oswin Peverell, Amanita Gorse",
            plot_points_str="PP005: Seeking the Ember Gourd",
            side_quests_str="None",
            monsters_str="Bloodshadow",
            traps_str="Fire Trap",
            connected_locations_str="V03 (Harvest Warden's Path)",
            module_creation_prompt="",
            should_inject_creation_prompt=False
        )
        
        # Assertions: resolved location should show resolved guidance
        self.assertIn("Resolved Hostile State:", dm_note,
                      "DM-note should include resolved hostile state guidance")
        self.assertIn("Hostile guardian at this location has been appeased", dm_note,
                      "DM-note should indicate guardian is appeased")
        
        # Should NOT contain active threats guidance
        self.assertNotIn("Monsters should be active threats per engagement rules", dm_note,
                          "Resolved location should NOT contain active threats guidance")

    def test_unresolved_location_keeps_active_threat_guidance(self):
        """Test 33: Unresolved location keeps active threat guidance (control case)."""
        party_tracker_data = self._create_party_tracker_without_resolved_marker()
        world_conditions = party_tracker_data.get("worldConditions", {})
        
        dm_note = build_standard_dm_note(
            party_tracker_data=party_tracker_data,
            world_conditions=world_conditions,
            date_time_str="1492 Springmonth 2, 7:25 AM",
            current_season="Spring",
            current_module_name="The_Pumpkin_Kings_Curse",
            current_location_name=self.location_name,
            current_location_id=self.location_id,
            current_area_name=self.area_name,
            party_stats_str="HP 17/17",
            party_npcs_str="Oswin Peverell, Amanita Gorse",
            plot_points_str="PP005: Seeking the Ember Gourd",
            side_quests_str="None",
            monsters_str="Bloodshadow",
            traps_str="Fire Trap",
            connected_locations_str="V03 (Harvest Warden's Path)",
            module_creation_prompt="",
            should_inject_creation_prompt=False
        )
        
        # Assertions: unresolved location should show active threats guidance
        self.assertIn("Monsters should be active threats per engagement rules", dm_note,
                      "Unresolved location should include active threats guidance")
        
        # Should NOT contain resolved guidance
        self.assertNotIn("Resolved Hostile State:", dm_note,
                          "Unresolved location should NOT contain resolved guidance")

    def test_invalid_marker_type_falls_back_to_unresolved(self):
        """Test 34: Invalid marker type falls back to unresolved behavior (fail-open)."""
        party_tracker_data = {
            "partyMembers": ["Anselara", "zeug"],
            "worldConditions": {
                "resolvedHostilesByLocation": "invalid_string",  # Non-dict type
                "currentLocationId": self.location_id
            }
        }
        world_conditions = party_tracker_data.get("worldConditions", {})
        
        dm_note = build_standard_dm_note(
            party_tracker_data=party_tracker_data,
            world_conditions=world_conditions,
            date_time_str="1492 Springmonth 2, 7:25 AM",
            current_season="Spring",
            current_module_name="The_Pumpkin_Kings_Curse",
            current_location_name=self.location_name,
            current_location_id=self.location_id,
            current_area_name=self.area_name,
            party_stats_str="HP 17/17",
            party_npcs_str="Oswin Peverell, Amanita Gorse",
            plot_points_str="PP005: Seeking the Ember Gourd",
            side_quests_str="None",
            monsters_str="Bloodshadow",
            traps_str="Fire Trap",
            connected_locations_str="V03 (Harvest Warden's Path)",
            module_creation_prompt="",
            should_inject_creation_prompt=False
        )
        
        # Assertions: invalid marker should fall back to unresolved behavior
        self.assertIn("Monsters should be active threats per engagement rules", dm_note,
                      "Invalid marker type should fall back to active threats guidance")
        
        # Should NOT contain resolved guidance
        self.assertNotIn("Resolved Hostile State:", dm_note,
                          "Invalid marker type should NOT show resolved guidance")


if __name__ == "__main__":
    unittest.main()
