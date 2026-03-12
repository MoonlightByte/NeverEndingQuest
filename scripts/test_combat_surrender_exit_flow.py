# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - surrender/capture combat exit flow tests.

Focused regression coverage for the reported live failure mode:
- last hostile yields/captured but combat does not end,
- enemy batch omits a remaining hostile due to queue pointer,
- defeated captives remain eligible turn actors.
"""

import json
import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from core.managers.multi_pc_combat import Combatant, CombatantType, TurnQueueManager


MISSING_JSONSCHEMA = False

try:
    from updates.update_encounter import update_encounter
except ModuleNotFoundError as import_error:
    if getattr(import_error, "name", "") == "jsonschema":
        MISSING_JSONSCHEMA = True
        update_encounter = None
    else:
        raise


def _all_enemies_resolved(encounter_data):
    """Mirror combat-manager enemy resolution contract for exit gating."""
    if not encounter_data or "creatures" not in encounter_data:
        return False

    has_enemies = False
    all_defeated = True

    for creature in encounter_data.get("creatures", []):
        if creature.get("type") != "enemy":
            continue

        has_enemies = True
        current_hp = creature.get("currentHitPoints", 0)
        status = str(creature.get("status", "alive")).lower()
        if current_hp > 0 and status not in ("dead", "defeated", "unconscious"):
            all_defeated = False
            break

    return has_enemies and all_defeated


class TestSurrenderExitQueueBehavior(unittest.TestCase):
    """Queue-level behavior for capture/surrender combat wrap-up."""

    def test_enemy_batch_ignores_turn_pointer_for_end_phase(self):
        manager = TurnQueueManager()
        manager.turn_queue = [
            Combatant("Vitreol", CombatantType.PC, 19, 18, 18, 14, "alive"),
            Combatant("Blairen", CombatantType.PC, 17, 20, 20, 16, "alive"),
            Combatant("Bandit_2", CombatantType.ENEMY, 14, 0, 11, 12, "defeated"),
            Combatant("Scout Kira", CombatantType.NPC, 13, 12, 12, 13, "alive"),
            Combatant("Bandit_1", CombatantType.ENEMY, 11, 5, 11, 12, "alive"),
        ]

        expected = ["Scout Kira", "Bandit_1"]

        manager.current_turn_index = 0
        self.assertEqual(manager.get_remaining_enemies_for_round(), expected)

        manager.current_turn_index = 3
        self.assertEqual(manager.get_remaining_enemies_for_round(), expected)

        manager.current_turn_index = 4
        self.assertEqual(manager.get_remaining_enemies_for_round(), expected)

    def test_advance_turn_skips_captured_defeated_actor(self):
        manager = TurnQueueManager()
        manager.current_turn_index = 0
        manager.turn_queue = [
            Combatant("Chronos", CombatantType.PC, 20, 30, 30, 18, "alive"),
            Combatant("Captured Bandit", CombatantType.ENEMY, 16, 4, 11, 12, "defeated"),
            Combatant("Bandit Leader", CombatantType.ENEMY, 12, 9, 16, 13, "alive"),
        ]

        actor, rolled_over = manager.advance_turn()

        self.assertEqual(actor.name, "Bandit Leader")
        self.assertFalse(rolled_over)


@unittest.skipIf(MISSING_JSONSCHEMA, "jsonschema dependency unavailable")
class TestSurrenderExitEncounterState(unittest.TestCase):
    """Encounter-state behavior for last-hostile surrender/capture exits."""

    def setUp(self):
        self.encounter_id = "UNITTEST_SURRENDER_EXIT"
        self.encounter_path = os.path.join(
            REPO_ROOT,
            "modules",
            "encounters",
            f"encounter_{self.encounter_id}.json",
        )
        self._write_fixture()

    def tearDown(self):
        if os.path.exists(self.encounter_path):
            os.remove(self.encounter_path)

    def _write_fixture(self):
        fixture = {
            "encounterId": self.encounter_id,
            "encounterSummary": "Surrender exit regression fixture",
            "creatures": [
                {
                    "name": "UT_Player_One",
                    "type": "player",
                    "initiative": 20,
                    "status": "alive",
                    "conditions": [],
                    "currentHitPoints": 30,
                    "maxHitPoints": 30,
                    "actions": {"actionType": "attack", "target": "enemy"},
                },
                {
                    "name": "UT_Companion_One",
                    "type": "npc",
                    "npcType": "ally",
                    "initiative": 13,
                    "status": "alive",
                    "conditions": [],
                    "currentHitPoints": 12,
                    "maxHitPoints": 12,
                    "actions": {"actionType": "attack", "target": "enemy"},
                },
                {
                    "name": "UT_Bandit",
                    "type": "enemy",
                    "monsterType": "bandit",
                    "initiative": 11,
                    "status": "alive",
                    "conditions": [],
                    "actions": {"actionType": "attack", "target": "pc"},
                    "currentHitPoints": 5,
                    "maxHitPoints": 11,
                },
            ],
        }
        with open(self.encounter_path, "w", encoding="utf-8") as file_handle:
            json.dump(fixture, file_handle, indent=2)

    def _read_encounter(self):
        with open(self.encounter_path, "r", encoding="utf-8") as file_handle:
            return json.load(file_handle)

    def test_last_hostile_set_to_defeated_satisfies_exit_gate(self):
        # Simulate LLM + runtime capture/surrender resolution for final hostile.
        if update_encounter is None:
            self.skipTest("jsonschema dependency unavailable")
        updated = update_encounter(
            self.encounter_id,
            "Bandit yields and is captured.",
            ops=[
                {"op": "set_status", "creature": "UT_Bandit", "status": "defeated"},
                {"op": "condition_add", "creature": "UT_Bandit", "condition": "Restrained"},
            ],
        )

        self.assertIsNotNone(updated)
        self.assertTrue(_all_enemies_resolved(updated))

        persisted = self._read_encounter()
        self.assertTrue(_all_enemies_resolved(persisted))
        enemy = next(c for c in persisted["creatures"] if c.get("type") == "enemy")
        self.assertEqual(enemy.get("status"), "defeated")
        self.assertIn("Restrained", enemy.get("conditions", []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
