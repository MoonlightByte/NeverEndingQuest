#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Regression tests for NPC Arrival State Sync party member exemption fix.

This test verifies that party members (PCs) are exempt from NPC arrival state
validation, preventing the hard fail loop when the AI mentions party members
in narration.

Validation scenarios covered:
1. Party member mentions are valid without arrival actions
2. Mixed party member + off-location NPC validation only flags NPC
3. No false positive PC/NPC misclassification
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.npc_arrival_validator import (
    validate_npc_arrival_state_sync,
)


def test_party_members_are_exempt_from_arrival_validation():
    """
    Scenario: AI mentions party members in narration
    Expected: Valid (True) - party members are PCs, not NPCs requiring arrival
    """
    # Setup: party has zeug and Anselara as members
    party_tracker_data = {
        "partyMembers": ["zeug", "Anselara"],
        "partyNPCs": [
            {"name": "Oswin Peverell", "role": "Fighter"},
            {"name": "Amanita Gorse", "role": "Ranger"},
        ],
    }

    # Simulate name collision: module also has "zeug" and "anselara" as NPCs
    # This is the bug scenario - validator would demand arrival actions
    module_npc_names = {"zeug", "anselara", "oswin peverell", "aminita gorse"}

    # Current location has only Oswin present
    location_data = {
        "npcs": ["Oswin Peverell"],
    }

    # AI mentions both party members in narration
    response_json = {
        "narration": "Zeug and Anselara look around the crossroads, then turn to Oswin.",
        "actions": [],  # No arrival actions needed for party members
    }

    is_valid, reason = validate_npc_arrival_state_sync(
        response_json, party_tracker_data, location_data, module_npc_names
    )

    assert is_valid, f"Party member mentions should be valid, got: {reason}"
    assert reason == "", f"Valid response should have empty reason, got: {reason}"
    print("PASS: Party members are exempt from arrival validation")


def test_mixed_party_member_and_off_location_npc_only_flags_npc():
    """
    Scenario: AI mentions both party member AND off-location NPC
    Expected: Invalid only for NPC, reason mentions NPC but not party member
    """
    party_tracker_data = {
        "partyMembers": ["zeug", "Anselara"],
        "partyNPCs": [
            {"name": "Oswin Peverell", "role": "Fighter"},
        ],
    }

    # Module has both party member name (collision) and true NPC
    module_npc_names = {"zeug", "mysterious stranger"}

    # Location has Oswin, no mysterious stranger
    location_data = {
        "npcs": ["Oswin Peverell"],
    }

    # AI mentions party member zeug (present) and off-location NPC
    response_json = {
        "narration": "Zeug points at the mysterious stranger lurking in the shadows.",
        "actions": [],  # No arrival action for mysterious stranger
    }

    is_valid, reason = validate_npc_arrival_state_sync(
        response_json, party_tracker_data, location_data, module_npc_names
    )

    assert not is_valid, "Should be invalid due to off-location NPC"
    assert "mysterious stranger" in reason.lower(), f"Reason should mention NPC, got: {reason}"
    assert "zeug" not in reason.lower(), f"Reason should NOT mention party member zeug, got: {reason}"
    print("PASS: Mixed mention only flags off-location NPC, not party member")


def test_party_npc_in_party_list_is_treated_as_present():
    """
    Scenario: partyNPC mentioned while listed in partyNPCs.
    Expected: Valid - current validator treats partyNPCs as present companions.
    """
    party_tracker_data = {
        "partyMembers": ["zeug"],
        "partyNPCs": [
            {"name": "Oswin Peverell", "role": "Fighter"},
            {"name": "Amanita Gorse", "role": "Ranger"},  # Not present
        ],
    }

    module_npc_names = {"oswin peverell", "aminita gorse"}

    # Only Oswin is at current location
    location_data = {
        "npcs": ["Oswin Peverell"],
    }

    # AI mentions Amanita (partyNPC) while she remains in partyNPC list
    response_json = {
        "narration": "Amanita Gorse appears from the forest.",
        "actions": [],
    }

    is_valid, reason = validate_npc_arrival_state_sync(
        response_json, party_tracker_data, location_data, module_npc_names
    )

    assert is_valid, f"partyNPCs in party list should be treated as present, got: {reason}"
    print("PASS: partyNPC in party list is treated as present")


def test_already_present_party_npc_is_valid():
    """
    Scenario: partyNPC is present at location and mentioned
    Expected: Valid - already present NPCs don't need arrival actions
    """
    party_tracker_data = {
        "partyMembers": ["zeug"],
        "partyNPCs": [
            {"name": "Oswin Peverell", "role": "Fighter"},
        ],
    }

    module_npc_names = {"oswin peverell"}

    # Oswin is present at location
    location_data = {
        "npcs": ["Oswin Peverell"],
    }

    response_json = {
        "narration": "Oswin Peverell draws his sword.",
        "actions": [],
    }

    is_valid, reason = validate_npc_arrival_state_sync(
        response_json, party_tracker_data, location_data, module_npc_names
    )

    assert is_valid, f"Present partyNPC mention should be valid, got: {reason}"
    print("PASS: Already-present partyNPC is valid without arrival action")


def test_case_insensitive_party_member_exemption():
    """
    Scenario: Party member name has different case than in partyMembers list
    Expected: Still exempt (case-insensitive matching)
    """
    party_tracker_data = {
        "partyMembers": ["Anselara"],  # Capitalized
        "partyNPCs": [],
    }

    module_npc_names = {"anselara"}  # lowercase in module

    location_data = {"npcs": []}

    # AI uses lowercase
    response_json = {
        "narration": "anselara raises her bow.",
        "actions": [],
    }

    is_valid, reason = validate_npc_arrival_state_sync(
        response_json, party_tracker_data, location_data, module_npc_names
    )

    assert is_valid, f"Case-insensitive party member match should be exempt, got: {reason}"
    print("PASS: Case-insensitive party member exemption works")


def test_party_member_short_name_exempt_under_alias_matching():
    """
    Task 2.5: Party-member exemption remains valid under alias-aware matching.
    Scenario: Party member full name 'Oswin Peverell', narration uses short 'oswin'.
    """
    party_tracker_data = {
        "partyMembers": ["Oswin Peverell"],
        "partyNPCs": [],
    }

    module_npc_names = {"Oswin Peverell", "Amanita Gorse"}

    location_data = {"npcs": []}

    response_json = {
        "narration": "Oswin attacks the goblin.",
        "actions": [],
    }

    is_valid, reason = validate_npc_arrival_state_sync(
        response_json, party_tracker_data, location_data, module_npc_names
    )

    assert is_valid, f"Short party member mention should be exempt, got: {reason}"
    print("PASS: Party member short name exempt under alias matching")


def test_party_member_full_name_exempt_when_short_in_party():
    """
    Edge case: Party member stored as short name, narration uses full name.
    """
    party_tracker_data = {
        "partyMembers": ["Amanita"],
        "partyNPCs": [],
    }

    module_npc_names = {"Amanita Gorse"}

    location_data = {"npcs": []}

    response_json = {
        "narration": "Amanita Gorse fires an arrow.",
        "actions": [],
    }

    is_valid, reason = validate_npc_arrival_state_sync(
        response_json, party_tracker_data, location_data, module_npc_names
    )

    assert is_valid, f"Full name mention should match short party member, got: {reason}"
    print("PASS: Full name matches short party member name")


def run_all_tests():
    """Run all regression tests."""
    tests = [
        test_party_members_are_exempt_from_arrival_validation,
        test_mixed_party_member_and_off_location_npc_only_flags_npc,
        test_party_npc_in_party_list_is_treated_as_present,
        test_already_present_party_npc_is_valid,
        test_case_insensitive_party_member_exemption,
        test_party_member_short_name_exempt_under_alias_matching,
        test_party_member_full_name_exempt_when_short_in_party,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test_func.__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
