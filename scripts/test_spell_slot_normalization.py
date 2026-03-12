# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest spell-slot normalization regression tests.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


from utils.character_creation_audit import AUDIT_RESULT_SUCCESS, audit_character_creation
from utils.spell_slot_utils import normalize_character_spell_slots


def _empty_slot_block():
    return {f"level{i}": {"current": 0, "max": 0} for i in range(1, 10)}


def _base_spellcasting():
    return {
        "ability": "wisdom",
        "spellSaveDC": 13,
        "spellAttackBonus": 5,
        "spells": {
            "cantrips": [],
            "level1": [],
            "level2": [],
            "level3": [],
            "level4": [],
            "level5": [],
            "level6": [],
            "level7": [],
            "level8": [],
            "level9": [],
        },
        "spellSlots": _empty_slot_block(),
        "preparedSpells": [],
    }


class TestSpellSlotNormalization(unittest.TestCase):
    def test_ranger_level1_with_leveled_spells_gets_bootstrap_slots(self):
        character_data = {
            "name": "Vitreol",
            "class": "Ranger",
            "level": 1,
            "spellcasting": _base_spellcasting(),
        }
        character_data["spellcasting"]["spells"]["level1"] = ["Hunter's Mark", "Speak with Animals"]

        updated, changed = normalize_character_spell_slots(character_data)
        self.assertTrue(changed)
        self.assertEqual(updated["spellcasting"]["spellSlots"]["level1"]["max"], 2)
        self.assertEqual(updated["spellcasting"]["spellSlots"]["level1"]["current"], 2)

    def test_wizard_level3_zeroed_slots_get_expected_progression(self):
        character_data = {
            "name": "Acheron",
            "class": "Wizard",
            "level": 3,
            "spellcasting": _base_spellcasting(),
        }

        updated, changed = normalize_character_spell_slots(character_data)
        self.assertTrue(changed)
        self.assertEqual(updated["spellcasting"]["spellSlots"]["level1"]["max"], 4)
        self.assertEqual(updated["spellcasting"]["spellSlots"]["level2"]["max"], 2)
        self.assertEqual(updated["spellcasting"]["spellSlots"]["level1"]["current"], 4)
        self.assertEqual(updated["spellcasting"]["spellSlots"]["level2"]["current"], 2)

    def test_existing_slot_usage_is_preserved_when_max_is_valid(self):
        character_data = {
            "name": "Anselara",
            "class": "Wizard",
            "level": 3,
            "spellcasting": _base_spellcasting(),
        }
        character_data["spellcasting"]["spellSlots"]["level1"] = {"current": 1, "max": 4}
        character_data["spellcasting"]["spellSlots"]["level2"] = {"current": 0, "max": 2}

        updated, changed = normalize_character_spell_slots(character_data)
        self.assertFalse(changed)
        self.assertEqual(updated["spellcasting"]["spellSlots"]["level1"], {"current": 1, "max": 4})
        self.assertEqual(updated["spellcasting"]["spellSlots"]["level2"], {"current": 0, "max": 2})

    def test_audit_pipeline_applies_slot_normalization(self):
        payload = {
            "name": "Audit Ranger",
            "race": "Elf",
            "class": "Ranger",
            "background": "Outlander",
            "personality_traits": "Quiet",
            "ideals": "Balance",
            "bonds": "The wild",
            "flaws": "Suspicious",
            "backstory": "Raised in deep woods.",
            "backgroundFeature": {
                "name": "Wanderer",
                "description": "You can find food and fresh water in the wild.",
                "source": "SRD 5.2.1",
            },
            "level": 1,
            "spellcasting": _base_spellcasting(),
        }
        payload["spellcasting"]["spells"]["level1"] = ["Hunter's Mark"]

        result = audit_character_creation(payload, source="test_spell_slot_norm", enable_enrichment=False)
        self.assertEqual(result.result_type, AUDIT_RESULT_SUCCESS)
        self.assertEqual(result.normalized_data["spellcasting"]["spellSlots"]["level1"]["max"], 2)
        self.assertEqual(result.normalized_data["spellcasting"]["spellSlots"]["level1"]["current"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
