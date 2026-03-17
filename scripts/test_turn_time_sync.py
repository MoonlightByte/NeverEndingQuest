#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for turn-synced world-time and idle-input hardening."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.turn_time_sync import apply_turn_time_sync, TURN_SYNC_TIMESTAMP_FIELD


class TestTurnTimeSyncBehavior(unittest.TestCase):
    """Behavior tests for bounded turn-synced world time."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        self._write_party_tracker("06:25:00")

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def _write_party_tracker(self, time_value):
        payload = {
            "module": "The_Thornwood_Watch",
            "partyMembers": ["vitreol"],
            "active_character": "vitreol",
            "worldConditions": {
                "year": 1492,
                "month": "Springmonth",
                "day": 2,
                "time": time_value,
                "currentLocation": "Bandit Stronghold",
                "currentLocationId": "TW05",
                "currentArea": "Thornwood Wilds",
                "currentAreaId": "TW001",
            },
        }
        with open("party_tracker.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _read_party_tracker(self):
        with open("party_tracker.json", "r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_first_turn_seeds_timestamp_without_time_advance(self):
        now_value = datetime(2026, 3, 17, 9, 0, 0)
        result = apply_turn_time_sync(now_ts=now_value, max_minutes=15)

        self.assertEqual(result.get("status"), "seeded")
        self.assertEqual(result.get("applied_minutes"), 0)

        tracker = self._read_party_tracker()
        self.assertEqual(tracker["worldConditions"]["time"], "06:25:00")
        self.assertEqual(
            tracker["worldConditions"].get(TURN_SYNC_TIMESTAMP_FIELD),
            "2026-03-17T09:00:00",
        )

    def test_elapsed_minutes_advance_world_time(self):
        start_time = datetime(2026, 3, 17, 9, 0, 0)
        apply_turn_time_sync(now_ts=start_time, max_minutes=15)

        next_time = start_time + timedelta(minutes=6, seconds=30)
        result = apply_turn_time_sync(now_ts=next_time, max_minutes=15)

        self.assertEqual(result.get("status"), "applied")
        self.assertEqual(result.get("elapsed_minutes"), 6)
        self.assertEqual(result.get("applied_minutes"), 6)

        tracker = self._read_party_tracker()
        self.assertEqual(tracker["worldConditions"]["time"], "06:31:00")

    def test_sub_minute_gap_updates_marker_only(self):
        start_time = datetime(2026, 3, 17, 9, 0, 0)
        apply_turn_time_sync(now_ts=start_time, max_minutes=15)

        next_time = start_time + timedelta(seconds=59)
        result = apply_turn_time_sync(now_ts=next_time, max_minutes=15)

        self.assertEqual(result.get("status"), "updated_marker")
        self.assertEqual(result.get("applied_minutes"), 0)

        tracker = self._read_party_tracker()
        self.assertEqual(tracker["worldConditions"]["time"], "06:25:00")

    def test_large_gap_is_clamped(self):
        start_time = datetime(2026, 3, 17, 9, 0, 0)
        apply_turn_time_sync(now_ts=start_time, max_minutes=15)

        next_time = start_time + timedelta(minutes=120)
        result = apply_turn_time_sync(now_ts=next_time, max_minutes=15)

        self.assertEqual(result.get("elapsed_minutes"), 120)
        self.assertEqual(result.get("applied_minutes"), 15)

        tracker = self._read_party_tracker()
        self.assertEqual(tracker["worldConditions"]["time"], "06:40:00")

    def test_malformed_timestamp_resets_fail_open(self):
        tracker = self._read_party_tracker()
        tracker["worldConditions"][TURN_SYNC_TIMESTAMP_FIELD] = "not-a-timestamp"
        with open("party_tracker.json", "w", encoding="utf-8") as handle:
            json.dump(tracker, handle, indent=2)

        now_value = datetime(2026, 3, 17, 9, 5, 0)
        result = apply_turn_time_sync(now_ts=now_value, max_minutes=15)

        self.assertEqual(result.get("status"), "seeded")
        self.assertEqual(result.get("applied_minutes"), 0)
        self.assertTrue(result.get("reset"))


class TestTurnTimeSyncSourceContracts(unittest.TestCase):
    """Source-level contracts for main-loop and web-input wiring."""

    def test_main_calls_turn_time_sync_helper(self):
        main_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_py, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("apply_turn_time_sync()", content)
        self.assertIn("Applied turn-synced world time", content)

    def test_web_input_no_longer_returns_synthetic_blank_line(self):
        web_interface_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web",
            "web_interface.py",
        )
        with open(web_interface_py, "r", encoding="utf-8") as handle:
            content = handle.read()

        method_start = content.index("def readline(self):")
        method_end = content.index("@app.route('/')")
        readline_block = content[method_start:method_end]

        self.assertIn("user_input = self.queue.get()", readline_block)
        self.assertNotIn("return '\\n'", readline_block)
        self.assertNotIn("timeout=0.1", readline_block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
