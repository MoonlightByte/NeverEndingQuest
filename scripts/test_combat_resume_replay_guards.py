# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Regression coverage for resumed combat replay guards.
"""

import os
import sys
import types
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if "jsonschema" not in sys.modules:
    jsonschema_stub = types.ModuleType("jsonschema")

    class _ValidationError(Exception):
        pass

    jsonschema_stub.validate = lambda *args, **kwargs: None
    jsonschema_stub.ValidationError = _ValidationError
    sys.modules["jsonschema"] = jsonschema_stub

if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")

    class _OpenAI:  # pragma: no cover - test import shim only
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    openai_stub.OpenAI = _OpenAI
    sys.modules["openai"] = openai_stub

from updates.update_encounter import (  # noqa: E402
    _extract_expected_enemy_transitions,
    _is_prepared_encounter_ops_replay,
)
from utils.combat_summary_history import (  # noqa: E402
    HISTORICAL_COMBAT_PREFIX,
    HISTORICAL_COMBAT_REWARD_GUARD,
    build_historical_combat_summary_message,
)


class TestCombatSummaryHistoryContracts(unittest.TestCase):
    def test_helper_wraps_summary_as_historical_record(self):
        message = build_historical_combat_summary_message("Combat Summary: skeleton falls.")
        self.assertIn(HISTORICAL_COMBAT_PREFIX, message)
        self.assertIn(HISTORICAL_COMBAT_REWARD_GUARD, message)
        self.assertIn("Combat Summary: skeleton falls.", message)

    def test_main_resume_path_uses_historical_summary_helper(self):
        main_path = os.path.join(PROJECT_ROOT, "main.py")
        with open(main_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("from utils.combat_summary_history import build_historical_combat_summary_message", source)
        self.assertIn("combat_summary_message = build_historical_combat_summary_message(dialogue_summary)", source)
        self.assertNotIn("[COMBAT CONCLUDED] The encounter has ended. The following is a summary of events", source)

    def test_action_handler_uses_same_historical_summary_helper(self):
        action_handler_path = os.path.join(PROJECT_ROOT, "core/ai/action_handler.py")
        with open(action_handler_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("from utils.combat_summary_history import build_historical_combat_summary_message", source)
        self.assertIn('"content": build_historical_combat_summary_message(combat_summary["content"])', source)


class TestEncounterReplayGuard(unittest.TestCase):
    def _build_encounter(self, hp_value, status="alive"):
        return {
            "creatures": [
                {
                    "name": "Skeleton_2",
                    "type": "enemy",
                    "currentHitPoints": hp_value,
                    "status": status,
                }
            ]
        }

    def test_extract_expected_enemy_transitions_reads_hp_mirror(self):
        transitions = _extract_expected_enemy_transitions(
            "Skeleton_2 takes 9 damage from Xorn's battleaxe (HP 13->4) and is now bloodied."
        )
        self.assertEqual(transitions["skeleton 2"]["final_hp"], 4)
        self.assertEqual(transitions["skeleton 2"]["final_status"], None)

    def test_replay_guard_detects_already_applied_positive_hp_update(self):
        encounter_info = self._build_encounter(4, "alive")
        prepared_ops = [
            {"op": "hp_delta", "creature": encounter_info["creatures"][0], "delta": -9, "index": 0}
        ]
        changes = "Skeleton_2 takes 9 damage from Xorn's battleaxe (HP 13->4) and is now bloodied."

        self.assertTrue(_is_prepared_encounter_ops_replay(encounter_info, prepared_ops, changes))

    def test_replay_guard_allows_fresh_positive_hp_update(self):
        encounter_info = self._build_encounter(13, "alive")
        prepared_ops = [
            {"op": "hp_delta", "creature": encounter_info["creatures"][0], "delta": -9, "index": 0}
        ]
        changes = "Skeleton_2 takes 9 damage from Xorn's battleaxe (HP 13->4) and is now bloodied."

        self.assertFalse(_is_prepared_encounter_ops_replay(encounter_info, prepared_ops, changes))

    def test_replay_guard_detects_already_applied_kill_update(self):
        encounter_info = self._build_encounter(0, "dead")
        prepared_ops = [
            {"op": "set_hp", "creature": encounter_info["creatures"][0], "hp": 0, "index": 0},
            {"op": "set_status", "creature": encounter_info["creatures"][0], "status": "dead", "index": 1},
        ]
        changes = "Skeleton_2 takes 10 damage from Xorn (HP 4->-6) and is now dead."

        self.assertTrue(_is_prepared_encounter_ops_replay(encounter_info, prepared_ops, changes))


if __name__ == "__main__":
    unittest.main()
