#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for cumulative summary transition compression."""

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.ai.cumulative_summary import compress_conversation_history_on_transition


class TestCumulativeSummaryTransition(unittest.TestCase):
    def test_transition_compression_handles_location_id_parsing(self):
        conversation_history = [
            {"role": "system", "content": "Dungeon Master Note"},
            {"role": "user", "content": "We search the room."},
            {"role": "assistant", "content": "You find the hidden altar."},
            {
                "role": "user",
                "content": "Location transition: Priest's Lodging (NIG04) to Brother Lintar's Place (NIG08)",
            },
            {"role": "assistant", "content": "You arrive at the refuge."},
        ]

        with patch("core.ai.cumulative_summary.generate_location_summary", return_value="A concise summary."), \
             patch("core.ai.cumulative_summary.safe_json_load", return_value={
                 "module": "Night_of_the_Restless_Dead",
                 "worldConditions": {"currentAreaId": "NIG001"},
             }):
            compressed = compress_conversation_history_on_transition(
                conversation_history,
                "Priest's Lodging (NIG04)",
            )

        self.assertEqual(len(compressed), 4)
        summary_message = compressed[1]
        self.assertEqual(summary_message["role"], "assistant")
        self.assertIn("=== LOCATION SUMMARY ===", summary_message["content"])
        self.assertIn("location=NIG04", summary_message["content"])
        self.assertIn("A concise summary.", summary_message["content"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
