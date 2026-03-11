# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - combat phase integrity precheck Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import os
import sys
import unittest
from typing import Any, Dict, Optional


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _build_encounter(hostiles_alive: bool = True, include_creatures: bool = True) -> Dict[str, Any]:
    if not include_creatures:
        return {}
    status = "alive" if hostiles_alive else "defeated"
    hp = 12 if hostiles_alive else 0
    return {
        "id": "L05-E1",
        "creatures": [
            {
                "name": "Goblin Scout",
                "type": "enemy",
                "status": status,
                "currentHitPoints": hp,
            }
        ],
    }


def _base_phase_state(**overrides: Any) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "current_phase": "PC_PHASE",
        "forbidden_actors": ["Goblin Scout"],
        "pending_enemies": [],
        "pc_phase_complete": True,
        "current_round": 2,
    }
    state.update(overrides)
    return state


def _build_response(
    plan: str = "",
    narration: str = "",
    actions: Optional[list] = None,
    combat_round: int = 2,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "plan": plan,
        "narration": narration,
        "actions": actions or [],
        "combat_round": combat_round,
    }
    return payload


class TestCombatPhaseIntegrityPrecheck(unittest.TestCase):
    """Deterministic phase-integrity checks and fail-open behavior."""

    def test_forbidden_actor_action_fails(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(plan="Goblin Scout attacks Acheron with a spear.")
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=True),
            _base_phase_state(current_phase="PC_PHASE", forbidden_actors=["Goblin Scout"]),
        )
        self.assertFalse(valid)
        self.assertIn("forbidden actor", reason.lower())

    def test_forbidden_actor_guard_fail_open_when_list_missing(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(plan="Goblin Scout attacks Acheron with a spear.")
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=True),
            {"current_phase": "PC_PHASE"},
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_mid_enemy_batch_stop_fails(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(
            narration="The goblin nocks another arrow. Acheron, what do you do?"
        )
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=True),
            _base_phase_state(current_phase="ENEMY_PHASE", pending_enemies=["Goblin Scout"]),
        )
        self.assertFalse(valid)
        self.assertIn("enemy_phase", reason.lower())

    def test_mid_enemy_batch_guard_passes_when_no_turn_prompt(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(narration="Goblin Scout fires another arrow at Acheron.")
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=True),
            _base_phase_state(current_phase="ENEMY_PHASE", pending_enemies=["Goblin Scout"]),
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_exit_while_hostiles_remain_fails(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(
            actions=[
                {
                    "action": "exit",
                    "parameters": {"encounterId": "L05-E1", "reason": "All enemies defeated"},
                }
            ]
        )
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=True),
            _base_phase_state(),
        )
        self.assertFalse(valid)
        self.assertIn("living hostiles remain", reason.lower())

    def test_exit_guard_passes_when_hostiles_defeated(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(
            actions=[
                {
                    "action": "exit",
                    "parameters": {"encounterId": "L05-E1", "reason": "All enemies defeated"},
                }
            ]
        )
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=False),
            _base_phase_state(),
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_exit_guard_fail_open_when_encounter_not_authoritative(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(
            actions=[
                {
                    "action": "exit",
                    "parameters": {"encounterId": "L05-E1", "reason": "All enemies defeated"},
                }
            ]
        )
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(include_creatures=False),
            _base_phase_state(),
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_round_increment_before_pc_phase_complete_fails(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(combat_round=3)
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=True),
            _base_phase_state(current_round=2, pc_phase_complete=False),
        )
        self.assertFalse(valid)
        self.assertIn("combat_round advanced", reason.lower())

    def test_round_increment_guard_passes_when_pc_phase_complete(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(combat_round=3)
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=True),
            _base_phase_state(current_round=2, pc_phase_complete=True),
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_round_increment_guard_fail_open_when_state_missing(self):
        from utils.combat_phase_integrity_precheck import validate_combat_phase_integrity_precheck

        response_json = _build_response(combat_round=3)
        valid, reason = validate_combat_phase_integrity_precheck(
            response_json,
            _build_encounter(hostiles_alive=True),
            {"current_phase": "ENEMY_PHASE"},
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
