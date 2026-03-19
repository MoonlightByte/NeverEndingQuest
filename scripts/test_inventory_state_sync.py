# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - inventory/equipment/weapon state synchronization tests.

Focused deterministic tests for update_character_info inventory ops and
weapon-attack reconciliation.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


from updates.update_character_info import _apply_character_ops_deterministic, repair_character_data


class TestInventoryStateSync(unittest.TestCase):
    """Regression tests for inventory/weapon state coherence."""

    def _base_character(self):
        return {
            "name": "Chronos",
            "abilities": {"strength": 20, "dexterity": 19},
            "proficiencyBonus": 2,
            "equipment": [],
            "ammunition": [],
            "attacksAndSpellcasting": [],
        }

    def _apply_and_repair(self, character_data, ops):
        success, updated_data, error_msg, unsupported_ops = _apply_character_ops_deterministic(character_data, ops)
        self.assertTrue(success, msg=f"ops failed: {error_msg} unsupported={unsupported_ops}")
        repaired = repair_character_data(updated_data)
        return repaired

    def test_inventory_add_infers_weapon_type_for_dagger_like_name(self):
        character_data = self._base_character()
        updated = self._apply_and_repair(
            character_data,
            [{"op": "inventory_add", "item": "Wolf-engraved Dagger"}],
        )

        item = next((entry for entry in updated["equipment"] if entry.get("item_name") == "Wolf-engraved Dagger"), None)
        self.assertIsNotNone(item)
        self.assertEqual(item.get("item_type"), "weapon")

        attack_names = [entry.get("name") for entry in updated.get("attacksAndSpellcasting", [])]
        self.assertIn("Wolf-engraved Dagger", attack_names)

    def test_inventory_add_includes_required_equipment_description_before_repair(self):
        character_data = self._base_character()
        success, updated_data, error_msg, unsupported_ops = _apply_character_ops_deterministic(
            character_data,
            [{"op": "inventory_add", "item": "Reliquary of Saint Rydal"}],
        )

        self.assertTrue(success, msg=f"ops failed: {error_msg} unsupported={unsupported_ops}")
        item = next(
            (entry for entry in updated_data.get("equipment", []) if entry.get("item_name") == "Reliquary of Saint Rydal"),
            None,
        )
        self.assertIsNotNone(item)
        self.assertTrue(bool(item.get("description")))

    def test_inventory_add_includes_required_ammunition_description_before_repair(self):
        character_data = self._base_character()
        success, updated_data, error_msg, unsupported_ops = _apply_character_ops_deterministic(
            character_data,
            [{"op": "inventory_add", "item": "Arrows", "item_type": "ammunition", "quantity": 5}],
        )

        self.assertTrue(success, msg=f"ops failed: {error_msg} unsupported={unsupported_ops}")
        item = next((entry for entry in updated_data.get("ammunition", []) if entry.get("name") == "Arrows"), None)
        self.assertIsNotNone(item)
        self.assertTrue(bool(item.get("description")))

    def test_weapon_swap_removes_stale_attack_and_adds_new_attack(self):
        character_data = self._base_character()
        character_data["equipment"] = [
            {
                "item_name": "Dagger",
                "item_type": "weapon",
                "quantity": 1,
                "equipped": False,
                "damage": "1d4",
                "weapon_type": "melee",
            }
        ]
        character_data["attacksAndSpellcasting"] = [
            {
                "name": "Dagger",
                "attackBonus": 0,
                "damageDice": "1d4",
                "damageBonus": 0,
                "damageType": "bludgeoning",
                "type": "melee",
                "description": "Stale attack",
            }
        ]

        updated = self._apply_and_repair(
            character_data,
            [
                {"op": "inventory_remove", "item": "Dagger"},
                {"op": "inventory_add", "item": "Wolf-engraved Dagger"},
            ],
        )

        equipment_names = [entry.get("item_name") for entry in updated.get("equipment", [])]
        self.assertNotIn("Dagger", equipment_names)
        self.assertIn("Wolf-engraved Dagger", equipment_names)

        attack_names = [entry.get("name") for entry in updated.get("attacksAndSpellcasting", [])]
        self.assertNotIn("Dagger", attack_names)
        self.assertIn("Wolf-engraved Dagger", attack_names)

    def test_silver_bracer_inventory_add_does_not_create_weapon_attack(self):
        character_data = self._base_character()
        updated = self._apply_and_repair(
            character_data,
            [{"op": "inventory_add", "item": "Silver Bracer"}],
        )

        item = next((entry for entry in updated["equipment"] if entry.get("item_name") == "Silver Bracer"), None)
        self.assertIsNotNone(item)
        self.assertNotEqual(item.get("item_type"), "weapon")
        self.assertEqual(updated.get("attacksAndSpellcasting", []), [])

    def test_removing_non_weapon_item_preserves_existing_weapon_attack(self):
        character_data = self._base_character()
        character_data["equipment"] = [
            {
                "item_name": "Dagger",
                "item_type": "weapon",
                "quantity": 1,
                "equipped": False,
                "damage": "1d4",
                "weapon_type": "melee",
            },
            {
                "item_name": "Silver Bracer",
                "item_type": "miscellaneous",
                "quantity": 1,
                "equipped": True,
            },
        ]
        character_data["attacksAndSpellcasting"] = [
            {
                "name": "Dagger",
                "attackBonus": 0,
                "damageDice": "1d4",
                "damageBonus": 0,
                "damageType": "piercing",
                "type": "melee",
                "description": "Dagger attack",
            }
        ]

        updated = self._apply_and_repair(
            character_data,
            [{"op": "inventory_remove", "item": "Silver Bracer"}],
        )

        attack_names = [entry.get("name") for entry in updated.get("attacksAndSpellcasting", [])]
        self.assertIn("Dagger", attack_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
