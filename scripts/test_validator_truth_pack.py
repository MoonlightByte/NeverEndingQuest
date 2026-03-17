# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Validator Truth Pack Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Contracts for touched-character mechanical truth pack generation.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _loader_factory(character_map):
    def _loader(name):
        return character_map.get(name.lower())
    return _loader


class TestValidatorTruthPackBehavior(unittest.TestCase):
    """Behavior tests for touched-character truth-pack helper."""

    def test_truth_pack_contains_mechanics_fields(self):
        from utils.validator_truth_pack import build_touched_character_truth_pack

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "HP 12->9 after trap damage"
                    }
                }
            ]
        }
        loader = _loader_factory({
            "acheron": {
                "name": "Acheron",
                "hitPoints": 9,
                "maxHitPoints": 21,
                "condition_affected": ["Poisoned"],
                "spellSlots": {"1": {"current": 2, "max": 4}},
                "deathSaveSuccesses": 0,
                "deathSaveFailures": 1,
                "classFeatures": [{"name": "Second Wind", "uses": 0, "maxUses": 1}],
                "currency": {"gold": 4, "silver": 1, "copper": 0},
                "ammunition": [{"name": "Arrow", "quantity": 6}],
                "equipment": [{"item_name": "Rope", "quantity": 1}],
            }
        })

        packs = build_touched_character_truth_pack(response_json, character_loader=loader)
        self.assertEqual(len(packs), 1)
        pack = packs[0]

        self.assertEqual(pack["character_name"], "Acheron")
        self.assertEqual(pack["hp"], 9)
        self.assertEqual(pack["max_hp"], 21)
        self.assertIn("Poisoned", pack["conditions"])
        self.assertIn("1", pack["spell_slots"])
        self.assertIn("successes", pack["death_saves"])
        self.assertIn("class_features", pack)

    def test_inventory_included_when_change_is_inventory_relevant(self):
        from utils.validator_truth_pack import build_touched_character_truth_pack

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Removed 1 arrow from inventory"
                    }
                }
            ]
        }
        loader = _loader_factory({
            "acheron": {
                "hitPoints": 9,
                "maxHitPoints": 21,
                "currency": {"gold": 1, "silver": 0, "copper": 0},
                "ammunition": [{"name": "Arrow", "quantity": 5}],
                "equipment": [{"item_name": "Torch", "quantity": 2}],
            }
        })

        packs = build_touched_character_truth_pack(response_json, character_loader=loader)
        self.assertIn("inventory", packs[0])
        self.assertIn("ammunition", packs[0]["inventory"])

    def test_nested_feature_usage_is_included_in_class_feature_summary(self):
        from utils.validator_truth_pack import build_touched_character_truth_pack

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Chronos",
                        "changes": "Rage usage 2->1",
                    }
                }
            ]
        }
        loader = _loader_factory({
            "chronos": {
                "name": "Chronos",
                "hitPoints": 14,
                "maxHitPoints": 14,
                "classFeatures": [
                    {"name": "Rage", "usage": {"current": 1, "max": 2, "refreshOn": "longRest"}}
                ],
            }
        })

        packs = build_touched_character_truth_pack(response_json, character_loader=loader)
        self.assertEqual(len(packs), 1)
        features = packs[0].get("class_features", [])
        self.assertEqual(len(features), 1)
        self.assertIn("usage", features[0])
        self.assertEqual(features[0]["usage"].get("current"), 1)
        self.assertEqual(features[0]["usage"].get("max"), 2)

    def test_inventory_omitted_for_clear_non_inventory_change(self):
        from utils.validator_truth_pack import build_touched_character_truth_pack

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "HP 12->9 after trap damage"
                    }
                }
            ]
        }
        loader = _loader_factory({
            "acheron": {
                "hitPoints": 9,
                "maxHitPoints": 21,
                "currency": {"gold": 1, "silver": 0, "copper": 0},
                "ammunition": [{"name": "Arrow", "quantity": 5}],
                "equipment": [{"item_name": "Torch", "quantity": 2}],
            }
        })

        packs = build_touched_character_truth_pack(response_json, character_loader=loader)
        self.assertNotIn("inventory", packs[0])


class TestValidatorTruthPackSourceContract(unittest.TestCase):
    """Source-contract tests for main validation wiring."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "main.py"), "r", encoding="utf-8") as f:
            cls.main_source = f.read()

    def test_main_uses_truth_pack_helper(self):
        self.assertIn("build_touched_character_truth_pack", self.main_source)
        self.assertIn("CHARACTER_MECHANICAL_TRUTH_PACK", self.main_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
