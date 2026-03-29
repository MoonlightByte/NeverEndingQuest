# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest combat narration consistency precheck tests.
"""

import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from utils.combat_narration_consistency_precheck import (
    validate_combat_narration_consistency_precheck,
    validate_update_encounter_enemy_boundary_precheck,
)


class TestCombatNarrationConsistencyPrecheck(unittest.TestCase):
    def setUp(self):
        self.encounter_data = {
            "encounterId": "NIG05-E2",
            "creatures": [
                {"name": "Redax", "type": "player", "armorClass": 18},
                {"name": "Athelon", "type": "player", "armorClass": 14},
                {"name": "Blarg", "type": "npc", "armorClass": 15},
                {"name": "Cultist", "type": "enemy", "armorClass": 12},
                {"name": "Skeleton", "type": "enemy", "armorClass": 13},
            ],
        }

    def test_rejects_explicit_miss_narrated_as_hit(self):
        response_json = {
            "plan": "Blarg attacks Skeleton (Attack roll: 4+5=9, misses Skeleton AC 13).",
            "narration": (
                "Blarg roars in reply, swinging his greataxe in a brutal arc at the skeleton. "
                "Bone splinters fly as the blade bites deep."
            ),
            "combat_round": 1,
            "actions": [
                {
                    "action": "updateEncounter",
                    "parameters": {
                        "encounterId": "NIG05-E2",
                        "changes": "Blarg attacks Skeleton with greataxe (Attack roll: 4+5=9, misses Skeleton AC 13).",
                    },
                }
            ],
        }

        valid, reason = validate_combat_narration_consistency_precheck(response_json, self.encounter_data)
        self.assertFalse(valid)
        self.assertIn("Blarg", reason)
        self.assertIn("miss", reason.lower())

    def test_rejects_explicit_hit_narrated_as_harmless_miss(self):
        response_json = {
            "plan": "Skeleton attacks Athelon (Attack roll: 19+4=23, hits Athelon AC 14).",
            "narration": (
                "The skeleton, jaw clacking, turns its hollow gaze on Athelon and looses an arrow. "
                "The shaft whistles through the cold air, shattering against the wall near Athelon's head."
            ),
            "combat_round": 1,
            "actions": [
                {
                    "action": "updateEncounter",
                    "parameters": {
                        "encounterId": "NIG05-E2",
                        "changes": "Skeleton attacks Athelon with shortbow (Attack roll: 19+4=23, hits Athelon AC 14; Damage roll: 4+2=6).",
                    },
                }
            ],
        }

        valid, reason = validate_combat_narration_consistency_precheck(response_json, self.encounter_data)
        self.assertFalse(valid)
        self.assertIn("Skeleton", reason)
        self.assertIn("confirmed hit", reason)

    def test_allows_ambiguous_atmosphere_on_miss(self):
        response_json = {
            "plan": "Blarg attacks Skeleton (Attack roll: 4+5=9, misses Skeleton AC 13).",
            "narration": "Blarg's axe whistles through the smoky chamber as candlelight flickers across the altar.",
            "combat_round": 1,
            "actions": [
                {
                    "action": "updateEncounter",
                    "parameters": {
                        "encounterId": "NIG05-E2",
                        "changes": "Blarg attacks Skeleton with greataxe (Attack roll: 4+5=9, misses Skeleton AC 13).",
                    },
                }
            ],
        }

        valid, reason = validate_combat_narration_consistency_precheck(response_json, self.encounter_data)
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_ignores_non_authoritative_attack_math(self):
        response_json = {
            "plan": "Blarg attacks Skeleton (Attack roll: 4+5=9, misses Skeleton AC 99).",
            "narration": "Blarg roars and bone splinters fly as the blade bites deep.",
            "combat_round": 1,
            "actions": [],
        }

        valid, reason = validate_combat_narration_consistency_precheck(response_json, self.encounter_data)
        self.assertTrue(valid)
        self.assertEqual(reason, "")


class TestCombatEncounterRoutingBoundaryPrecheck(unittest.TestCase):
    def setUp(self):
        self.encounter_data = {
            "encounterId": "NIG05-E2",
            "creatures": [
                {"name": "Redax", "type": "player", "armorClass": 18},
                {"name": "Athelon", "type": "player", "armorClass": 14},
                {"name": "Blarg", "type": "npc", "armorClass": 15},
                {"name": "Cultist", "type": "enemy", "armorClass": 12},
                {"name": "Skeleton", "type": "enemy", "armorClass": 13},
            ],
        }

    def test_rejects_player_target_inside_update_encounter_ops(self):
        response_json = {
            "narration": "The skeleton's arrow bites into Athelon.",
            "combat_round": 1,
            "actions": [
                {
                    "action": "updateEncounter",
                    "parameters": {
                        "encounterId": "NIG05-E2",
                        "changes": "Skeleton attacks Athelon (hit).",
                        "ops": [{"op": "hp_delta", "creature": "Athelon", "delta": -6}],
                    },
                }
            ],
        }

        valid, reason = validate_update_encounter_enemy_boundary_precheck(response_json, self.encounter_data)
        self.assertFalse(valid)
        self.assertIn("Athelon", reason)
        self.assertIn("updateCharacterInfo", reason)

    def test_rejects_player_hp_mutation_inside_update_encounter_changes(self):
        response_json = {
            "narration": "The skeleton's arrow bites into Athelon.",
            "combat_round": 1,
            "actions": [
                {
                    "action": "updateEncounter",
                    "parameters": {
                        "encounterId": "NIG05-E2",
                        "changes": "Skeleton deals 6 piercing damage to Athelon (HP 11->5).",
                    },
                }
            ],
        }

        valid, reason = validate_update_encounter_enemy_boundary_precheck(response_json, self.encounter_data)
        self.assertFalse(valid)
        self.assertIn("Athelon", reason)

    def test_allows_enemy_only_update_encounter_payload(self):
        response_json = {
            "narration": "Blarg's axe glances off the skeleton's rib cage.",
            "combat_round": 1,
            "actions": [
                {
                    "action": "updateEncounter",
                    "parameters": {
                        "encounterId": "NIG05-E2",
                        "changes": "Skeleton takes 5 slashing damage (HP 13->8).",
                        "ops": [{"op": "hp_delta", "creature": "Skeleton", "delta": -5}],
                    },
                }
            ],
        }

        valid, reason = validate_update_encounter_enemy_boundary_precheck(response_json, self.encounter_data)
        self.assertTrue(valid)
        self.assertEqual(reason, "")


class TestCombatNarrationConsistencyContracts(unittest.TestCase):
    def test_combat_manager_wires_prechecks(self):
        combat_manager_path = os.path.join(PROJECT_ROOT, "core", "managers", "combat_manager.py")
        with open(combat_manager_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("validate_combat_narration_consistency_precheck", source)
        self.assertIn("validate_update_encounter_enemy_boundary_precheck", source)
        self.assertIn("Narration-consistency precheck rejected response", source)
        self.assertIn("Enemy-routing precheck rejected response", source)

    def test_validation_prompts_lock_contradiction_rules(self):
        compressed_path = os.path.join(
            PROJECT_ROOT,
            "prompts",
            "combat",
            "combat_validation_prompt_multipc_compressed.txt",
        )
        with open(compressed_path, "r", encoding="utf-8") as handle:
            compressed = handle.read()

        self.assertIn("miss_as_hit_invalid", compressed)
        self.assertIn("hit_as_miss_invalid", compressed)
        self.assertIn("enemy_boundary_strict", compressed)


if __name__ == "__main__":
    unittest.main()
