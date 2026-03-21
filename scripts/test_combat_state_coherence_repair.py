# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Focused regression coverage for tt-combat-state-coherence-repair.

Usage:
    python3 scripts/test_combat_state_coherence_repair.py
"""

import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.managers import combat_manager
from core.managers.multi_pc_combat import (
    CombatStateManager,
    Combatant,
    CombatantType,
    MultiPCCombatManager,
    PCStatus,
)
from updates.update_character_info import _apply_character_ops_deterministic


class TestCombatStateCoherenceRepair(unittest.TestCase):
    def test_initialize_from_party_dedupes_canonical_identities(self):
        state_mgr = CombatStateManager()
        party_data = {
            "partyMembers": [
                "xorn",
                "Xorn",
                "athelon",
                "Athelon",
                "lidda_underbough",
                "Lidda Underbough",
            ],
            "active_character": "athelon",
        }

        def fake_safe_json_load(path):
            path = str(path)
            if path.endswith("characters/xorn.json"):
                return {"name": "Xorn", "hitPoints": 10, "maxHitPoints": 10, "armorClass": 16}
            if path.endswith("characters/athelon.json"):
                return {"name": "Athelon", "hitPoints": 11, "maxHitPoints": 11, "armorClass": 15}
            if path.endswith("characters/lidda_underbough.json"):
                return {"name": "Lidda Underbough", "hitPoints": 9, "maxHitPoints": 9, "armorClass": 15}
            return {}

        with patch("core.managers.multi_pc_combat.safe_json_load", side_effect=fake_safe_json_load):
            state_mgr.initialize_from_party(party_data)

        self.assertEqual(set(state_mgr.pc_states.keys()), {"Xorn", "Athelon", "Lidda Underbough"})
        self.assertEqual(state_mgr.current_pc_name, "Athelon")

    def test_update_pc_hp_preserves_existing_death_save_counts(self):
        state_mgr = CombatStateManager()
        state_mgr.pc_states["Lidda Underbough"] = SimpleNamespace(
            current_hp=0,
            max_hp=9,
            status=PCStatus.INCAPACITATED,
            death_save_successes=0,
            death_save_failures=1,
        )

        state_mgr.update_pc_hp("Lidda Underbough", 0)

        self.assertEqual(state_mgr.pc_states["Lidda Underbough"].death_save_failures, 1)
        self.assertEqual(state_mgr.pc_states["Lidda Underbough"].status, PCStatus.INCAPACITATED)

    def test_dead_enemy_excluded_from_enemy_phase_and_tracker_window(self):
        manager = MultiPCCombatManager()
        manager._state.pc_states = {
            "Redax": SimpleNamespace(status=PCStatus.READY, current_hp=11, max_hp=11),
        }
        manager._state.current_pc_name = "Redax"
        manager._turns.turn_queue = [
            Combatant("Cultist_7", CombatantType.ENEMY, 19, -5, 9, 12, "alive"),
            Combatant("Cultist_4", CombatantType.ENEMY, 18, 9, 9, 12, "alive"),
            Combatant("Redax", CombatantType.PC, 9, 11, 11, 18, "alive"),
        ]

        remaining = manager.get_remaining_enemies_for_round()
        tracker = manager.format_initiative_tracker({})

        self.assertEqual(remaining, ["Cultist_4"])
        self.assertNotIn(">>> PROCESS ALL OF THESE IN ONE RESPONSE (Initiative Order):\n- Cultist_7", tracker)
        self.assertIn("- [D] Cultist_7 (19) - Dead", tracker)

    def test_find_target_prefers_living_enemy_and_rejects_dead_only(self):
        turn_mgr = MultiPCCombatManager()._turns
        turn_mgr.turn_queue = [
            Combatant("Cultist", CombatantType.ENEMY, 20, 0, 9, 12, "dead"),
            Combatant("Cultist_4", CombatantType.ENEMY, 18, 9, 9, 12, "alive"),
            Combatant("Cultist_9", CombatantType.ENEMY, 10, -15, 9, 12, "dead"),
        ]

        target = turn_mgr.find_target("cultist", {})
        dead_only = turn_mgr.find_target("cultist_9", {})

        self.assertIsNotNone(target)
        self.assertEqual(target.name, "Cultist_4")
        self.assertIsNone(dead_only)

    def test_incapacitated_pc_cannot_use_fast_lane_attack_commands(self):
        manager = MultiPCCombatManager()
        manager._state.pc_states = {
            "Lidda Underbough": SimpleNamespace(
                character_name="Lidda Underbough",
                status=PCStatus.INCAPACITATED,
                current_hp=0,
                max_hp=9,
            )
        }
        manager._state.current_pc_name = "Lidda Underbough"

        feedback, log_msg = manager.handle_combat_command(
            "/att cultist 20",
            {"creatures": []},
            actor_name="lidda_underbough",
        )

        self.assertIn("cannot use /att while at 0 HP", feedback)
        self.assertIsNone(log_msg)

    def test_player_phase_prompt_uses_selected_active_pc_not_stale_queue_actor(self):
        manager = MultiPCCombatManager()
        manager._state.current_pc_name = "Redax"
        manager._state.pc_states = {
            "Redax": SimpleNamespace(status=PCStatus.READY, current_hp=11, max_hp=11),
            "Lidda Underbough": SimpleNamespace(status=PCStatus.INCAPACITATED, current_hp=0, max_hp=9),
        }
        manager._turns.turn_queue = [
            Combatant("Lidda Underbough", CombatantType.PC, 20, 0, 9, 15, "unconscious"),
            Combatant("Redax", CombatantType.PC, 9, 11, 11, 18, "alive"),
        ]
        manager._turns.current_turn_index = 0
        manager._turns.pc_phase_complete = False

        prompt = manager.get_required_response_prompt()

        self.assertIn("ACTIVE ACTOR: Redax", prompt)
        self.assertIn("Narrate ONLY the result of Redax's declared action.", prompt)
        self.assertNotIn("Lidda Underbough's declared action", prompt)

    def test_death_save_ops_apply_deterministically(self):
        character_data = {
            "name": "Lidda Underbough",
            "hitPoints": 0,
            "maxHitPoints": 9,
            "status": "unconscious",
            "condition": "unconscious",
            "condition_affected": ["unconscious"],
            "deathSaves": {"successes": 0, "failures": 0},
            "spellcasting": {"spellSlots": {"level1": {"current": 0, "max": 0}}},
            "equipment": [],
            "ammunition": [],
            "currency": {"gold": 0, "silver": 0, "copper": 0},
            "classFeatures": [],
        }

        success, updated_data, error_message, unsupported = _apply_character_ops_deterministic(
            character_data,
            [{"op": "death_save_failure", "delta": 1}],
        )

        self.assertTrue(success, error_message)
        self.assertEqual(unsupported, [])
        self.assertEqual(updated_data["deathSaves"], {"successes": 0, "failures": 1})
        self.assertEqual(updated_data["status"], "unconscious")

    def test_combat_manager_applies_ops_payloads_before_prose_fallback(self):
        queued = {}
        combat_manager._queue_final_character_update(
            queued,
            "Lidda Underbough",
            "Failed one death saving throw (1 failure, 0 successes).",
            [{"op": "death_save_failure", "delta": 1}],
        )
        combat_manager._queue_final_character_update(
            queued,
            "Lidda Underbough",
            "awarded 10 experience points",
            None,
        )

        update_calls = []
        sync_calls = []

        def fake_update_character_info(character_name, changes, ops=None):
            update_calls.append((character_name, changes, ops))
            return True

        def fake_safe_json_load(path):
            if str(path).endswith("characters/lidda_underbough.json"):
                return {
                    "name": "Lidda Underbough",
                    "hitPoints": 0,
                    "maxHitPoints": 9,
                    "status": "unconscious",
                    "deathSaves": {"successes": 0, "failures": 1},
                }
            return {}

        fake_manager = SimpleNamespace(
            pc_states={"Lidda Underbough": object()},
            sync_pc_persistent_state=lambda name, data: sync_calls.append((name, data.get("deathSaves"))),
        )

        with patch("core.managers.combat_manager.update_character_info", side_effect=fake_update_character_info), patch(
            "core.managers.combat_manager.safe_json_load", side_effect=fake_safe_json_load
        ):
            combat_manager._apply_final_character_updates(queued, fake_manager)

        self.assertEqual(len(update_calls), 2)
        self.assertIsNotNone(update_calls[0][2])
        self.assertIsNone(update_calls[1][2])
        self.assertEqual(sync_calls[0][1], {"successes": 0, "failures": 1})

    def test_schema_includes_nested_death_saves(self):
        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas", "char_schema.json")
        with open(schema_path, "r", encoding="utf-8") as handle:
            schema = json.load(handle)

        self.assertIn("deathSaves", schema["properties"])
        self.assertEqual(
            schema["properties"]["deathSaves"]["required"],
            ["successes", "failures"],
        )


if __name__ == "__main__":
    unittest.main()
