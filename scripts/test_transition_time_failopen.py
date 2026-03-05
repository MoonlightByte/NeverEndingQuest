#!/usr/bin/env python3
"""
Regression tests for transition-time fail-open fallback.
Tests deterministic auto-time injection when transitionLocation lacks updateTime.
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTransitionTimeFailOpen(unittest.TestCase):
    """Test suite for transition-time auto-fallback logic."""

    def setUp(self):
        """Set up common test fixtures."""
        self.party_tracker_data = {
            "worldConditions": {
                "currentAreaId": "BOO001",
                "currentLocationId": "V04",
                "time": "06:55:00"
            }
        }

        # Mock location graph with area mappings
        self.location_graph = Mock()
        self.location_graph.nodes = {
            "V04": {"area_id": "BOO001"},
            "V05": {"area_id": "BOO001"},  # Same area
            "HFG001": {"area_id": "HFG001"},  # Cross area
            "CMS001": {"area_id": "CMS001"},  # Cross area
        }

    def _simulate_fallback_logic(self, actions, party_tracker_data, location_graph):
        """
        Simulate the fallback logic from main.py for testing.
        Returns: (modified_actions, injected_update_time, fallback_minutes, log_message)
        """
        has_transition = any(action.get("action") == "transitionLocation" for action in actions)
        has_update_time = any(action.get("action") == "updateTime" for action in actions)

        injected_update_time = None
        fallback_minutes = None
        log_message = None

        if has_transition and not has_update_time:
            # Find transition action
            transition_action = next((a for a in actions if a.get("action") == "transitionLocation"), None)
            if transition_action:
                target_location = transition_action.get("parameters", {}).get("newLocation", "")
                current_area_id = party_tracker_data.get("worldConditions", {}).get("currentAreaId", "")

                # Determine if cross-area
                is_cross_area = False
                try:
                    if location_graph and target_location in location_graph.nodes:
                        target_area_id = location_graph.nodes[target_location].get("area_id", "")
                        is_cross_area = (target_area_id != current_area_id)
                    else:
                        is_cross_area = True  # Default to cross-area on lookup failure
                except Exception:
                    is_cross_area = True

                # Deterministic fallback minutes
                fallback_minutes = 20 if is_cross_area else 10

                # Create synthetic action
                injected_update_time = {
                    "action": "updateTime",
                    "parameters": {
                        "timeEstimate": fallback_minutes
                    }
                }

                log_message = f"STATE_SYNC: Auto-applied updateTime={fallback_minutes} due to transitionLocation without updateTime (cross_area={is_cross_area})"

                # Simulate insertion at beginning of other_actions
                modified_actions = [injected_update_time] + actions
            else:
                modified_actions = actions
        else:
            modified_actions = actions

        return modified_actions, injected_update_time, fallback_minutes, log_message

    def test_injects_update_time_when_transition_missing_time_same_area(self):
        """Test: Same-area transition without updateTime gets 10-minute fallback."""
        actions = [
            {"action": "transitionLocation", "parameters": {"newLocation": "V05"}}
        ]

        modified, injected, minutes, log = self._simulate_fallback_logic(
            actions, self.party_tracker_data, self.location_graph
        )

        self.assertIsNotNone(injected, "Should inject synthetic updateTime")
        self.assertEqual(minutes, 10, "Same-area transition should get 10 minutes")
        self.assertEqual(injected["parameters"]["timeEstimate"], 10)
        self.assertIn("STATE_SYNC", log)
        self.assertIn("cross_area=False", log)

        # Verify synthetic action is first in modified list
        self.assertEqual(modified[0]["action"], "updateTime")
        self.assertEqual(modified[1]["action"], "transitionLocation")

    def test_injects_update_time_when_transition_missing_time_cross_area(self):
        """Test: Cross-area transition without updateTime gets 20-minute fallback."""
        actions = [
            {"action": "transitionLocation", "parameters": {"newLocation": "HFG001"}}
        ]

        modified, injected, minutes, log = self._simulate_fallback_logic(
            actions, self.party_tracker_data, self.location_graph
        )

        self.assertIsNotNone(injected, "Should inject synthetic updateTime")
        self.assertEqual(minutes, 20, "Cross-area transition should get 20 minutes")
        self.assertEqual(injected["parameters"]["timeEstimate"], 20)
        self.assertIn("STATE_SYNC", log)
        self.assertIn("cross_area=True", log)

    def test_does_not_inject_when_update_time_already_present(self):
        """Test: No injection when explicit updateTime is already in bundle."""
        actions = [
            {"action": "transitionLocation", "parameters": {"newLocation": "V05"}},
            {"action": "updateTime", "parameters": {"timeEstimate": 15}}
        ]

        modified, injected, minutes, log = self._simulate_fallback_logic(
            actions, self.party_tracker_data, self.location_graph
        )

        self.assertIsNone(injected, "Should NOT inject when updateTime already exists")
        self.assertIsNone(minutes)
        self.assertIsNone(log)
        self.assertEqual(len(modified), 2, "Actions should remain unchanged")

    def test_no_injection_for_non_transition_turn(self):
        """Test: No injection when no transitionLocation present."""
        actions = [
            {"action": "updateCharacterInfo", "parameters": {"characterName": "Test"}},
            {"action": "moveBackgroundNPC", "parameters": {"npcName": "NPC1", "location": "V05"}}
        ]

        modified, injected, minutes, log = self._simulate_fallback_logic(
            actions, self.party_tracker_data, self.location_graph
        )

        self.assertIsNone(injected, "Should NOT inject without transitionLocation")
        self.assertIsNone(minutes)
        self.assertIsNone(log)
        self.assertEqual(len(modified), 2, "Actions should remain unchanged")

    def test_graph_lookup_failure_defaults_cross_area_minutes(self):
        """Test: Unknown location defaults to cross-area (20 minutes) for safety."""
        actions = [
            {"action": "transitionLocation", "parameters": {"newLocation": "UNKNOWN_LOCATION"}}
        ]

        modified, injected, minutes, log = self._simulate_fallback_logic(
            actions, self.party_tracker_data, self.location_graph
        )

        self.assertIsNotNone(injected, "Should inject fallback for unknown location")
        self.assertEqual(minutes, 20, "Unknown location should default to 20 minutes (cross-area)")
        self.assertIn("cross_area=True", log)

    def test_multiple_transitions_same_response(self):
        """Test: Multiple transitions in same response still get single fallback."""
        actions = [
            {"action": "transitionLocation", "parameters": {"newLocation": "V05"}},
            {"action": "transitionLocation", "parameters": {"newLocation": "HFG001"}}
        ]

        modified, injected, minutes, log = self._simulate_fallback_logic(
            actions, self.party_tracker_data, self.location_graph
        )

        self.assertIsNotNone(injected, "Should inject fallback for multi-transition")
        # Only one updateTime should be injected
        update_time_count = sum(1 for a in modified if a["action"] == "updateTime")
        self.assertEqual(update_time_count, 1, "Should inject exactly one updateTime")

    def test_transition_with_existing_update_time_preserved(self):
        """Test: Original explicit updateTime is preserved, no duplicate."""
        actions = [
            {"action": "transitionLocation", "parameters": {"newLocation": "V05"}},
            {"action": "updateTime", "parameters": {"timeEstimate": 25}}
        ]

        modified, injected, minutes, log = self._simulate_fallback_logic(
            actions, self.party_tracker_data, self.location_graph
        )

        # Should keep original, not inject new
        update_times = [a for a in modified if a["action"] == "updateTime"]
        self.assertEqual(len(update_times), 1)
        self.assertEqual(update_times[0]["parameters"]["timeEstimate"], 25)

    def test_log_format_ascii_only(self):
        """Test: Log message uses ASCII characters only."""
        actions = [
            {"action": "transitionLocation", "parameters": {"newLocation": "V05"}}
        ]

        modified, injected, minutes, log = self._simulate_fallback_logic(
            actions, self.party_tracker_data, self.location_graph
        )

        # Check no non-ASCII characters in log
        self.assertTrue(all(ord(c) < 128 for c in log), "Log must be ASCII only")
        self.assertIn("STATE_SYNC:", log)
        self.assertIn("Auto-applied updateTime=", log)


if __name__ == "__main__":
    unittest.main(verbosity=2)
