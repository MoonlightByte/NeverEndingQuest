#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Regression tests for authoritative state packet foundation.
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.authoritative_state_packet import build_authoritative_state_packet


class TestAuthoritativeStatePacketShape(unittest.TestCase):
    """Behavior tests for packet v1 shape and read-only behavior."""

    def setUp(self):
        self.party_tracker = {
            "module": "The_Thornwood_Watch",
            "partyMembers": ["vitreol", "Chronos"],
            "active_character": "vitreol",
            "partyNPCs": [
                {"name": "Scout Kira", "role": "Rogue", "level": "?"},
            ],
            "worldConditions": {
                "currentAreaId": "TW001",
                "currentArea": "Thornwood",
                "currentLocationId": "RO01",
                "currentLocation": "Rangers' Command Post",
            },
        }
        self.area_data = {
            "areaId": "TW001",
            "locations": [
                {
                    "locationId": "RO01",
                    "name": "Rangers' Command Post",
                    "description": "A muddy camp beneath old pines.",
                    "dmInstructions": "Keep watchful NPC tone.",
                    "connectivity": ["TW02", "TW03"],
                },
                {
                    "locationId": "TW02",
                    "name": "Forest Trail",
                },
            ],
        }

    def test_packet_includes_expected_v1_sections(self):
        packet = build_authoritative_state_packet(
            self.party_tracker,
            area_data=self.area_data,
            location_data=self.area_data["locations"][0],
        )

        self.assertEqual(packet.get("version"), "v1")
        self.assertIn("module", packet)
        self.assertIn("world", packet)
        self.assertIn("party", packet)
        self.assertIn("location", packet)
        self.assertIn("topology", packet)

    def test_packet_prefers_area_location_name_when_available(self):
        packet = build_authoritative_state_packet(
            self.party_tracker,
            area_data=self.area_data,
            location_data=self.area_data["locations"][0],
        )

        self.assertEqual(packet["world"]["current_location_id"], "RO01")
        self.assertEqual(packet["world"]["current_location_name"], "Rangers' Command Post")
        self.assertEqual(packet["module"]["name"], "The_Thornwood_Watch")

    def test_packet_captures_party_and_npc_lists(self):
        packet = build_authoritative_state_packet(
            self.party_tracker,
            area_data=self.area_data,
            location_data=self.area_data["locations"][0],
        )

        self.assertEqual(packet["party"]["party_members"], ["vitreol", "Chronos"])
        self.assertEqual(packet["party"]["active_character"], "vitreol")
        self.assertEqual(packet["party"]["party_npc_names"], ["Scout Kira"])
        self.assertIn("TW02", packet["topology"]["known_location_ids"])
        self.assertIn("Forest Trail", packet["topology"]["known_location_names"])

    def test_packet_builder_is_read_only_for_input_payload(self):
        before = copy.deepcopy(self.party_tracker)
        _ = build_authoritative_state_packet(
            self.party_tracker,
            area_data=self.area_data,
            location_data=self.area_data["locations"][0],
        )
        self.assertEqual(self.party_tracker, before)


class TestAuthoritativePacketSourceContracts(unittest.TestCase):
    """Source-contract tests for packet parity integration points."""

    def test_main_uses_authoritative_packet_in_validation_handoff(self):
        main_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_py, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("build_authoritative_state_packet(", content)
        self.assertIn("state_packet=authoritative_state_packet", content)
        self.assertIn("AUTHORITATIVE_STATE_PACKET:", content)

    def test_dm_note_builder_consumes_authoritative_packet(self):
        dm_note_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "utils",
            "multi_pc_dm_note.py",
        )
        with open(dm_note_py, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("build_authoritative_state_packet(party_tracker_data)", content)
        self.assertIn("effective_location_id", content)
        self.assertIn("packet_party", content)


if __name__ == "__main__":
    unittest.main()
