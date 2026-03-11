# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - combat save/concentration Contract Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Step 1.1 contract tests for combat-save-concentration-contract.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


REQUEST_ROLL_ACTION = "requestRoll"
REQUEST_ROLL_TYPES = {
    "saving_throw",
    "ability_check",
    "skill_check",
}
CONCENTRATION_FORMULA = "max(10, floor(damage / 2))"


class TestCombatSaveConcentrationOpenSpecContracts(unittest.TestCase):
    """Lock OpenSpec artifacts for combat requestRoll and concentration contracts."""

    @classmethod
    def setUpClass(cls):
        change_root = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-save-concentration-contract",
        )
        cls.paths = {
            "proposal": os.path.join(change_root, "proposal.md"),
            "design": os.path.join(change_root, "design.md"),
            "tasks": os.path.join(change_root, "tasks.md"),
            "request_roll_spec": os.path.join(
                change_root,
                "specs",
                "tt-combat-request-roll-routing",
                "spec.md",
            ),
            "concentration_spec": os.path.join(
                change_root,
                "specs",
                "tt-combat-concentration-request-dc",
                "spec.md",
            ),
        }
        cls.content = {}
        for key, path in cls.paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_request_roll_preference_documented(self):
        self.assertIn("prefer `requestRoll`", self.content["proposal"])
        self.assertIn("prefer `requestRoll`", self.content["design"])
        self.assertIn("prefer `requestRoll`", self.content["request_roll_spec"])

    def test_stop_after_request_semantics_documented(self):
        self.assertIn("stop-after-request semantics", self.content["proposal"])
        self.assertIn("stop after issuing the request", self.content["design"])
        self.assertIn("same response SHALL stop after issuing the request", self.content["request_roll_spec"])
        self.assertIn("SHALL stop after the request", self.content["concentration_spec"])

    def test_no_contingent_outcomes_documented(self):
        self.assertIn("does not narrate contingent", self.content["proposal"])
        self.assertIn("SHALL NOT narrate contingent success/failure", self.content["design"])
        self.assertIn("SHALL NOT narrate contingent success or failure", self.content["request_roll_spec"])
        self.assertIn("SHALL NOT narrate contingent save success or failure", self.content["concentration_spec"])

    def test_prose_compatibility_documented(self):
        self.assertIn("prose-only compatibility", self.content["proposal"])
        self.assertIn("Prose-only save/check requests SHALL remain compatibility-valid", self.content["design"])
        self.assertIn("preserve prose-only", self.content["request_roll_spec"])
        self.assertIn("prose fallback", self.content["concentration_spec"])
        self.assertIn("explicit prose-compatibility fallback", self.content["tasks"])

    def test_concentration_formula_documented(self):
        self.assertIn(CONCENTRATION_FORMULA, self.content["proposal"])
        self.assertIn(CONCENTRATION_FORMULA, self.content["design"])
        self.assertIn(CONCENTRATION_FORMULA, self.content["concentration_spec"])


class TestCombatSaveConcentrationRuntimeSourceContracts(unittest.TestCase):
    """Lock current runtime scaffolding presence for combat save/check contracts."""

    @classmethod
    def setUpClass(cls):
        cls.paths = {
            "action_handler": os.path.join(REPO_ROOT, "core", "ai", "action_handler.py"),
            "combat_manager": os.path.join(REPO_ROOT, "core", "managers", "combat_manager.py"),
        }
        cls.content = {}
        for key, path in cls.paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_action_handler_has_request_roll_branch(self):
        source = self.content["action_handler"]
        self.assertIn('ACTION_REQUEST_ROLL = "requestRoll"', source)
        self.assertIn("elif action_type == ACTION_REQUEST_ROLL", source)
        self.assertIn("validate_request_roll_parameters(parameters)", source)

    def test_action_handler_references_concentration_dc_helper(self):
        source = self.content["action_handler"]
        self.assertIn("calculate_concentration_dc", source)
        self.assertIn('"concentration" in reason_text.lower()', source)
        self.assertIn("expected_dc = calculate_concentration_dc(damage_value)", source)

    def test_action_handler_request_roll_path_is_scaffold_only(self):
        source = self.content["action_handler"]
        self.assertIn("Runtime behavior remains narration-driven in this phase", source)
        self.assertIn("validate payload shape", source)

    def test_combat_manager_has_request_roll_helpers(self):
        source = self.content["combat_manager"]
        self.assertIn("def build_request_roll_action(", source)
        self.assertIn('"action": "requestRoll"', source)
        self.assertIn("def get_concentration_request_dc(damage_taken: int) -> int", source)
        self.assertIn("return calculate_concentration_dc(damage_taken)", source)


class TestCombatSaveConcentrationCompatibilityContracts(unittest.TestCase):
    """Lock compatibility-oriented behavior for request payloads and formula."""

    def test_request_roll_types_locked(self):
        self.assertEqual(
            REQUEST_ROLL_TYPES,
            {
                "saving_throw",
                "ability_check",
                "skill_check",
            },
        )

    def test_request_roll_payload_validator_accepts_saving_throw(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "characterName": "Acheron",
                "rollType": "saving_throw",
                "dc": 13,
                "reason": "Maintain concentration after taking damage.",
                "ability": "constitution",
                "advantage": "normal",
            }
        )
        self.assertTrue(is_valid)
        self.assertEqual(error_message, "")

    def test_request_roll_payload_validator_accepts_skill_check(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "characterName": "Merisiel",
                "rollType": "skill_check",
                "dc": 15,
                "reason": "Spot weak cover in the battlefield.",
                "skill": "perception",
            }
        )
        self.assertTrue(is_valid)
        self.assertEqual(error_message, "")

    def test_concentration_formula_helper_contract(self):
        from utils.save_roll_contract import calculate_concentration_dc

        self.assertEqual(calculate_concentration_dc(1), 10)
        self.assertEqual(calculate_concentration_dc(19), 10)
        self.assertEqual(calculate_concentration_dc(23), 11)


class TestCombatConcentrationSpecificContracts(unittest.TestCase):
    """Lock concentration-specific contract expectations for Step 1.2."""

    @classmethod
    def setUpClass(cls):
        change_root = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-save-concentration-contract",
        )
        cls.concentration_spec_path = os.path.join(
            change_root,
            "specs",
            "tt-combat-concentration-request-dc",
            "spec.md",
        )
        cls.request_roll_spec_path = os.path.join(
            change_root,
            "specs",
            "tt-combat-request-roll-routing",
            "spec.md",
        )
        cls.design_path = os.path.join(change_root, "design.md")

        with open(cls.concentration_spec_path, "r", encoding="utf-8") as file_handle:
            cls.concentration_spec = file_handle.read()
        with open(cls.request_roll_spec_path, "r", encoding="utf-8") as file_handle:
            cls.request_roll_spec = file_handle.read()
        with open(cls.design_path, "r", encoding="utf-8") as file_handle:
            cls.design = file_handle.read()

    def test_concentration_open_spec_low_and_high_damage_scenarios_locked(self):
        self.assertIn("less than 20 damage", self.concentration_spec)
        self.assertIn("SHALL use DC 10", self.concentration_spec)
        self.assertIn("deals 23 damage", self.concentration_spec)
        self.assertIn("SHALL use DC 11", self.concentration_spec)

    def test_concentration_open_spec_pause_only_and_no_contingent_outcome_locked(self):
        self.assertIn("SHALL stop after the request", self.concentration_spec)
        self.assertIn("SHALL NOT narrate contingent save success or failure", self.concentration_spec)
        self.assertIn("SHALL NOT narrate contingent success or failure", self.request_roll_spec)

    def test_concentration_open_spec_prose_fallback_locked(self):
        self.assertIn("Prose concentration request remains compatibility-valid", self.concentration_spec)
        self.assertIn("Prose-only save/check requests SHALL remain compatibility-valid", self.design)

    def test_concentration_formula_helper_boundary_values(self):
        from utils.save_roll_contract import calculate_concentration_dc

        self.assertEqual(calculate_concentration_dc(20), 10)
        self.assertEqual(calculate_concentration_dc(21), 10)
        self.assertEqual(calculate_concentration_dc(22), 11)

    def test_request_roll_validator_accepts_concentration_saving_throw_payload(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "characterName": "Acheron",
                "rollType": "saving_throw",
                "dc": 11,
                "reason": "Concentration save after taking 23 damage.",
                "ability": "constitution",
            }
        )
        self.assertTrue(is_valid)
        self.assertEqual(error_message, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
