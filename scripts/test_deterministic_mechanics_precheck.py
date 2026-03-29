# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Deterministic Mechanics Precheck Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Targeted tests for explicit mechanics contradiction guardrails.
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


class TestDeterministicMechanicsPrecheck(unittest.TestCase):
    """Unit tests for deterministic mechanics precheck utility."""

    def test_hp_target_above_max_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Healing surge applied. HP 10->25"
                    }
                }
            ]
        }
        loader = _loader_factory({
            "acheron": {"maxHitPoints": 21}
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertFalse(valid)
        self.assertIn("HP", reason)

    def test_hp_target_below_zero_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Massive hit landed. HP 3->-1"
                    }
                }
            ]
        }
        loader = _loader_factory({
            "acheron": {"maxHitPoints": 21}
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertFalse(valid)
        self.assertIn("below 0", reason)

    def test_spell_slot_ratio_current_above_max_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Claris",
                        "changes": "Long rest completed. Level 1 slots to 5/4"
                    }
                }
            ]
        }
        loader = _loader_factory({"claris": {"maxHitPoints": 18}})

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertFalse(valid)
        self.assertIn("slot", reason.lower())

    def test_cantrip_slot_spend_contradiction_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Claris",
                        "changes": "Cast Fire Bolt cantrip and expended one 1st-level spell slot."
                    }
                }
            ]
        }
        loader = _loader_factory({
            "claris": {
                "maxHitPoints": 18,
                "spellcasting": {
                    "spellSlots": {
                        "level1": {"current": 2, "max": 4}
                    }
                }
            }
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertFalse(valid)
        self.assertIn("cantrip", reason.lower())

    def test_explicit_spell_slot_underflow_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Claris",
                        "changes": "Expended 2 1st-level spell slots to empower the ritual."
                    }
                }
            ]
        }
        loader = _loader_factory({
            "claris": {
                "maxHitPoints": 18,
                "spellcasting": {
                    "spellSlots": {
                        "level1": {"current": 1, "max": 4}
                    }
                }
            }
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertFalse(valid)
        self.assertIn("underflow", reason.lower())

    def test_inventory_over_removal_fails_when_item_matched(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Removed 3 arrows from inventory."
                    }
                }
            ]
        }
        loader = _loader_factory({
            "acheron": {
                "maxHitPoints": 21,
                "ammunition": [{"name": "Arrow", "quantity": 2}],
                "equipment": []
            }
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertFalse(valid)
        self.assertIn("Removed", reason)

    def test_explicit_ammo_fire_over_spend_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Fired 3 arrows at the charging cultist."
                    }
                }
            ]
        }
        loader = _loader_factory({
            "acheron": {
                "maxHitPoints": 21,
                "ammunition": [{"name": "Arrow", "quantity": 2}],
                "equipment": []
            }
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertFalse(valid)
        self.assertIn("spent", reason.lower())

    def test_unconscious_with_above_zero_hp_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Emergency aid applied. HP 0->5 but remains unconscious."
                    }
                }
            ]
        }
        loader = _loader_factory({"acheron": {"maxHitPoints": 21}})

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertFalse(valid)
        self.assertIn("unconscious", reason.lower())

    def test_short_rest_duration_below_minimum_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "narration": "The party completes a short rest for 30 minutes.",
            "actions": []
        }

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=_loader_factory({}))
        self.assertFalse(valid)
        self.assertIn("short rest duration", reason.lower())

    def test_long_rest_duration_below_minimum_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "rest",
                    "parameters": {
                        "type": "long",
                        "durationMinutes": 360
                    }
                }
            ]
        }

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=_loader_factory({}))
        self.assertFalse(valid)
        self.assertIn("long rest duration", reason.lower())

    def test_ambiguous_rest_duration_fail_open(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "narration": "The party catches its breath before moving on.",
            "actions": [
                {
                    "action": "rest",
                    "parameters": {
                        "type": "short"
                    }
                }
            ]
        }

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=_loader_factory({}))
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_cantrip_without_slot_spend_is_fail_open(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Claris",
                        "changes": "Cast Fire Bolt cantrip with no spell slot cost."
                    }
                }
            ]
        }
        loader = _loader_factory({
            "claris": {
                "maxHitPoints": 18,
                "spellcasting": {
                    "spellSlots": {
                        "level1": {"current": 1, "max": 4}
                    }
                }
            }
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_ambiguous_slot_spend_without_level_is_fail_open(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Claris",
                        "changes": "Expended a spell slot for a divine effect."
                    }
                }
            ]
        }
        loader = _loader_factory({
            "claris": {
                "maxHitPoints": 18,
                "spellcasting": {
                    "spellSlots": {
                        "level1": {"current": 0, "max": 4}
                    }
                }
            }
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_unconscious_flavor_without_explicit_hp_is_fail_open(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Acheron looks nearly unconscious from the shock."
                    }
                }
            ]
        }
        loader = _loader_factory({"acheron": {"maxHitPoints": 21}})

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_ambiguous_ammo_use_without_quantity_is_fail_open(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Acheron fires arrows into the darkness."
                    }
                }
            ]
        }
        loader = _loader_factory({
            "acheron": {
                "maxHitPoints": 21,
                "ammunition": [{"name": "Arrow", "quantity": 2}],
                "equipment": []
            }
        })

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_unparseable_changes_fail_open(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Feels inspired by the speech."
                    }
                }
            ]
        }
        loader = _loader_factory({"acheron": {"maxHitPoints": 21}})

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_coin_pouch_correction_without_action_coverage_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "narration": "Yes. You now have 16 copper coins in your currency pouch, and your inventory remains organized.",
            "actions": [],
        }

        valid, reason = validate_deterministic_mechanics_precheck(
            response_json,
            character_loader=_loader_factory({}),
            user_input="That copper coin should be currency, not miscellaneous inventory.",
        )
        self.assertFalse(valid)
        self.assertIn("bookkeeping correction", reason.lower())

    def test_coin_pouch_correction_with_action_coverage_passes(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "narration": "Yes. The copper is now tracked in your coin pouch.",
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "lidda_underbough",
                        "changes": "Moved 1 copper coin from misc inventory handling to currency. Added 1 copper to currency.",
                        "ops": [{"op": "currency_delta", "currency": "copper", "delta": 1}],
                    },
                }
            ],
        }

        valid, reason = validate_deterministic_mechanics_precheck(
            response_json,
            character_loader=_loader_factory({}),
            user_input="Please track that copper as currency instead of miscellaneous inventory.",
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_payment_without_action_coverage_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "narration": "You paid 2 silver for the room.",
            "actions": [],
        }

        valid, reason = validate_deterministic_mechanics_precheck(
            response_json,
            character_loader=_loader_factory({}),
            user_input="I pay for the room.",
        )
        self.assertFalse(valid)
        self.assertIn("updatecharacterinfo", reason.lower())

    def test_refund_without_action_coverage_fails(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "narration": "The innkeeper refunded 5 copper to you.",
            "actions": [],
        }

        valid, reason = validate_deterministic_mechanics_precheck(
            response_json,
            character_loader=_loader_factory({}),
            user_input="He gives the copper back.",
        )
        self.assertFalse(valid)
        self.assertIn("bookkeeping correction", reason.lower())

    def test_narrated_currency_gain_with_action_coverage_passes(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "narration": "You found 5 copper among the loose stones.",
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "lidda_underbough",
                        "changes": "Found 5 copper. Added 5 copper to currency.",
                        "ops": [{"op": "currency_delta", "currency": "cp", "amount": 5}],
                    },
                }
            ],
        }

        valid, reason = validate_deterministic_mechanics_precheck(
            response_json,
            character_loader=_loader_factory({}),
            user_input="I scoop up the loose copper.",
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_non_update_actions_are_ignored(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updatePlot",
                    "parameters": {
                        "plotPointId": "PP001",
                        "newStatus": "completed",
                        "plotImpact": "None"
                    }
                }
            ]
        }

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=_loader_factory({}))
        self.assertTrue(valid)
        self.assertEqual(reason, "")


class TestPipelineIntegrationContract(unittest.TestCase):
    """Source-contract check for main validation callsite."""

    def test_main_calls_deterministic_mechanics_precheck(self):
        main_path = os.path.join(REPO_ROOT, "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("validate_deterministic_mechanics_precheck", source)
        self.assertIn('user_input=user_input or ""', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
