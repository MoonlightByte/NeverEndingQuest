#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Regression tests for travel-intent state sync guard.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.travel_state_sync_guard import evaluate_travel_state_sync_guard


class TestTravelStateSyncGuardBehavior(unittest.TestCase):
    """Behavior tests for deterministic travel-state guard logic."""

    def test_rejects_clear_travel_arrival_without_transition(self):
        response = {
            "narration": "You travel through the tunnel and reach the web-choked chamber ahead.",
            "actions": [],
        }
        is_valid, reason = evaluate_travel_state_sync_guard(
            response_json=response,
            is_travel_intent=True,
            current_location_name="Ma's Watering Hole",
            known_location_names=["Room 3: Cathedral Storage", "Ma's Watering Hole"],
        )
        self.assertFalse(is_valid)
        self.assertIn("travel state sync guard", reason)

    def test_allows_travel_with_transition_action(self):
        response = {
            "narration": "You travel to Cathedral Storage and take cover behind crates.",
            "actions": [{"action": "transitionLocation", "parameters": {"newLocation": "NIG03"}}],
        }
        is_valid, reason = evaluate_travel_state_sync_guard(
            response_json=response,
            is_travel_intent=True,
            current_location_name="Ma's Watering Hole",
            known_location_names=["Cathedral Storage", "Ma's Watering Hole"],
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "")

    def test_allows_current_location_blocker_without_transition(self):
        response = {
            "narration": "The tunnel loops and is blocked. You remain at Ma's Watering Hole.",
            "actions": [],
        }
        is_valid, reason = evaluate_travel_state_sync_guard(
            response_json=response,
            is_travel_intent=True,
            current_location_name="Ma's Watering Hole",
            known_location_names=["Cathedral Storage", "Ma's Watering Hole"],
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "")

    def test_allows_clarifier_without_transition(self):
        response = {
            "narration": "Which route do you choose from here before we continue?",
            "actions": [],
        }
        is_valid, reason = evaluate_travel_state_sync_guard(
            response_json=response,
            is_travel_intent=True,
            current_location_name="Ma's Watering Hole",
            known_location_names=["Cathedral Storage", "Ma's Watering Hole"],
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "")

    def test_rejects_contradictory_mixed_location_narration(self):
        response = {
            "narration": (
                "You reach Cathedral Storage through the tunnel. "
                "A moment later, you step up into Ma's Watering Hole."
            ),
            "actions": [],
        }
        is_valid, reason = evaluate_travel_state_sync_guard(
            response_json=response,
            is_travel_intent=True,
            current_location_name="Ma's Watering Hole",
            known_location_names=["Cathedral Storage", "Ma's Watering Hole"],
        )
        self.assertFalse(is_valid)
        self.assertIn("contradictory", reason)

    def test_ambiguous_prose_fails_open(self):
        response = {
            "narration": "Cold air moves through the stone and the lantern trembles.",
            "actions": [],
        }
        is_valid, reason = evaluate_travel_state_sync_guard(
            response_json=response,
            is_travel_intent=True,
            current_location_name="Ma's Watering Hole",
            known_location_names=["Cathedral Storage", "Ma's Watering Hole"],
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "")

    def test_non_travel_turn_is_unchanged(self):
        response = {
            "narration": "You sit by the hearth and review your notes.",
            "actions": [],
        }
        is_valid, reason = evaluate_travel_state_sync_guard(
            response_json=response,
            is_travel_intent=False,
            current_location_name="Ma's Watering Hole",
            known_location_names=["Cathedral Storage", "Ma's Watering Hole"],
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "")


class TestTravelStateSyncGuardSourceContracts(unittest.TestCase):
    """Source-contract checks for main.py integration."""

    def test_main_calls_travel_state_sync_guard(self):
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_py_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn(
            "evaluate_travel_state_sync_guard",
            content,
            "main.py should invoke travel-state sync guard",
        )

    def test_main_marks_travel_state_sync_as_deterministic(self):
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_py_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn(
            '"travel state sync guard" in normalized_reason',
            content,
            "main.py should classify travel-state guard failures as deterministic",
        )


if __name__ == "__main__":
    unittest.main()
