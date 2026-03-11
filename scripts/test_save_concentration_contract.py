# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - save/concentration Contract Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Phase 1 contract tests for requestRoll and concentration DC rules.
"""

import os
import sys
import unittest
from typing import Any


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


REQUEST_ROLL_ACTION = "requestRoll"
REQUEST_ROLL_REQUIRED_FIELDS = {
    "characterName",
    "rollType",
    "dc",
    "reason",
}
REQUEST_ROLL_CONDITIONAL_FIELDS = {
    "ability",
    "skill",
}
REQUEST_ROLL_OPTIONAL_FIELDS = {
    "advantage",
}
REQUEST_ROLL_ALLOWED_TYPES = {
    "saving_throw",
    "ability_check",
    "skill_check",
}


def _resolve_archived_or_live_change_root(change_slug: str) -> str:
    """Resolve an OpenSpec change root from live or archived paths."""
    live_root = os.path.join(REPO_ROOT, "openspec", "changes", change_slug)
    if os.path.isdir(live_root):
        return live_root

    archive_root = os.path.join(REPO_ROOT, "openspec", "changes", "archive")
    if os.path.isdir(archive_root):
        for entry in sorted(os.listdir(archive_root), reverse=True):
            if entry.endswith(change_slug):
                candidate = os.path.join(archive_root, entry)
                if os.path.isdir(candidate):
                    return candidate

    raise FileNotFoundError(f"OpenSpec change not found (live or archive): {change_slug}")


def _resolve_main_or_delta_spec(spec_slug: str, change_root: str) -> str:
    """Prefer main spec sync path; fall back to change-local delta spec."""
    main_spec = os.path.join(REPO_ROOT, "openspec", "specs", spec_slug, "spec.md")
    if os.path.exists(main_spec):
        return main_spec

    delta_spec = os.path.join(change_root, "specs", spec_slug, "spec.md")
    if os.path.exists(delta_spec):
        return delta_spec

    raise FileNotFoundError(f"Spec not found in main or delta paths: {spec_slug}")


def expected_concentration_dc(damage: int) -> int:
    """Deterministic concentration DC formula lock for 5e contract tests."""
    return max(10, damage // 2)


class TestSaveConcentrationContractScaffold(unittest.TestCase):
    """Lock core requestRoll contract constants before runtime implementation."""

    def test_request_roll_action_name_locked(self):
        self.assertEqual(REQUEST_ROLL_ACTION, "requestRoll")

    def test_required_payload_fields_locked(self):
        self.assertEqual(
            REQUEST_ROLL_REQUIRED_FIELDS,
            {"characterName", "rollType", "dc", "reason"},
        )

    def test_conditional_and_optional_fields_locked(self):
        self.assertEqual(REQUEST_ROLL_CONDITIONAL_FIELDS, {"ability", "skill"})
        self.assertEqual(REQUEST_ROLL_OPTIONAL_FIELDS, {"advantage"})

    def test_allowed_roll_types_locked(self):
        self.assertEqual(
            REQUEST_ROLL_ALLOWED_TYPES,
            {"saving_throw", "ability_check", "skill_check"},
        )


class TestSaveConcentrationOpenSpecContracts(unittest.TestCase):
    """Lock OpenSpec artifacts for requestRoll and concentration contracts."""

    @classmethod
    def setUpClass(cls):
        change_root = _resolve_archived_or_live_change_root(
            "prompt-validator-save-concentration-contract"
        )
        cls.paths = {
            "proposal": os.path.join(change_root, "proposal.md"),
            "design": os.path.join(change_root, "design.md"),
            "request_roll_spec": _resolve_main_or_delta_spec(
                "tt-request-roll-contract",
                change_root,
            ),
            "concentration_spec": _resolve_main_or_delta_spec(
                "tt-concentration-dc-contract",
                change_root,
            ),
        }
        cls.content = {}
        for key, path in cls.paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_change_artifacts_reference_request_roll(self):
        self.assertIn(REQUEST_ROLL_ACTION, self.content["proposal"])
        self.assertIn(REQUEST_ROLL_ACTION, self.content["design"])
        self.assertIn(REQUEST_ROLL_ACTION, self.content["request_roll_spec"])

    def test_request_roll_spec_locks_payload_fields(self):
        spec_content = self.content["request_roll_spec"]
        for field_name in sorted(REQUEST_ROLL_REQUIRED_FIELDS):
            self.assertIn(field_name, spec_content)
        for field_name in sorted(REQUEST_ROLL_CONDITIONAL_FIELDS):
            self.assertIn(field_name, spec_content)
        for field_name in sorted(REQUEST_ROLL_OPTIONAL_FIELDS):
            self.assertIn(field_name, spec_content)

    def test_request_roll_spec_locks_allowed_types(self):
        spec_content = self.content["request_roll_spec"]
        for roll_type in sorted(REQUEST_ROLL_ALLOWED_TYPES):
            self.assertIn(roll_type, spec_content)

    def test_concentration_spec_locks_formula(self):
        concentration_content = self.content["concentration_spec"]
        self.assertIn("max(10, floor(damage / 2))", concentration_content)

    def test_design_mentions_prose_compatibility(self):
        self.assertIn("prose-only", self.content["design"])
        self.assertIn("compatibility", self.content["design"])


class TestCompressedPromptRequestRollContract(unittest.TestCase):
    """Lock compressed prompt and validator requestRoll contract wording."""

    @classmethod
    def setUpClass(cls):
        paths = {
            "system_compressed": os.path.join(REPO_ROOT, "prompts", "system_prompt_compressed.txt"),
            "validation_compressed": os.path.join(
                REPO_ROOT,
                "prompts",
                "validation",
                "validation_prompt_compressed.txt",
            ),
        }
        cls.content = {}
        for key, path in paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_request_roll_present_in_compressed_prompts(self):
        self.assertIn("requestRoll", self.content["system_compressed"])
        self.assertIn("requestRoll", self.content["validation_compressed"])

    def test_pause_semantics_present(self):
        self.assertIn("Do NOT narrate contingent success/failure", self.content["system_compressed"])
        self.assertIn("response MUST stop", self.content["validation_compressed"])

    def test_concentration_formula_present(self):
        formula = "max(10, floor(damage / 2))"
        self.assertIn(formula, self.content["system_compressed"])
        self.assertIn(formula, self.content["validation_compressed"])

    def test_roll_type_contract_present(self):
        for roll_type in sorted(REQUEST_ROLL_ALLOWED_TYPES):
            self.assertIn(roll_type, self.content["system_compressed"])
            self.assertIn(roll_type, self.content["validation_compressed"])


class TestConcentrationDcRule(unittest.TestCase):
    """Lock deterministic concentration DC behavior."""

    def test_dc_floor_half_damage_under_twenty(self):
        self.assertEqual(expected_concentration_dc(1), 10)
        self.assertEqual(expected_concentration_dc(19), 10)

    def test_dc_floor_half_damage_twenty_and_above(self):
        self.assertEqual(expected_concentration_dc(20), 10)
        self.assertEqual(expected_concentration_dc(21), 10)
        self.assertEqual(expected_concentration_dc(22), 11)
        self.assertEqual(expected_concentration_dc(23), 11)


class TestRuntimeRequestRollContracts(unittest.TestCase):
    """Runtime-facing helper contract tests for structured requestRoll payloads."""

    def test_valid_request_roll_payload_saving_throw(self):
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

    def test_valid_request_roll_payload_skill_check(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "characterName": "Acheron",
                "rollType": "skill_check",
                "dc": 15,
                "reason": "Search for hidden sigils in the altar room.",
                "skill": "investigation",
            }
        )
        self.assertTrue(is_valid)
        self.assertEqual(error_message, "")

    def test_action_handler_has_request_roll_branch(self):
        action_handler_path = os.path.join(REPO_ROOT, "core", "ai", "action_handler.py")
        with open(action_handler_path, "r", encoding="utf-8") as file_handle:
            source_text = file_handle.read()
        self.assertIn('ACTION_REQUEST_ROLL = "requestRoll"', source_text)
        self.assertIn("validate_request_roll_parameters(parameters)", source_text)


class TestRequestRollNegativeContracts(unittest.TestCase):
    """Fail-closed validation tests for malformed requestRoll payloads."""

    def test_missing_character_name_rejected(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "rollType": "saving_throw",
                "dc": 12,
                "reason": "Avoid poison gas.",
                "ability": "constitution",
            }
        )
        self.assertFalse(is_valid)
        self.assertIn("characterName", error_message)

    def test_missing_dc_rejected(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "characterName": "Acheron",
                "rollType": "saving_throw",
                "reason": "Avoid poison gas.",
                "ability": "constitution",
            }
        )
        self.assertFalse(is_valid)
        self.assertIn("dc", error_message)

    def test_bad_roll_type_rejected(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "characterName": "Acheron",
                "rollType": "initiative",
                "dc": 10,
                "reason": "Test invalid roll type.",
                "ability": "dexterity",
            }
        )
        self.assertFalse(is_valid)
        self.assertIn("rollType", error_message)

    def test_missing_ability_for_saving_throw_rejected(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "characterName": "Acheron",
                "rollType": "saving_throw",
                "dc": 12,
                "reason": "Avoid poison gas.",
            }
        )
        self.assertFalse(is_valid)
        self.assertIn("ability", error_message)

    def test_missing_skill_for_skill_check_rejected(self):
        from utils.save_roll_contract import validate_request_roll_parameters

        is_valid, error_message = validate_request_roll_parameters(
            {
                "characterName": "Acheron",
                "rollType": "skill_check",
                "dc": 14,
                "reason": "Inspect hidden marks.",
            }
        )
        self.assertFalse(is_valid)
        self.assertIn("skill", error_message)

    def test_malformed_concentration_input_rejected(self):
        from utils.save_roll_contract import calculate_concentration_dc

        bad_damage_input: Any = "12"
        with self.assertRaises(TypeError):
            calculate_concentration_dc(bad_damage_input)
        with self.assertRaises(ValueError):
            calculate_concentration_dc(-3)


class TestPauseSemanticsCompatibility(unittest.TestCase):
    """Verify save/check pause semantics remain intact in SP and TT contracts."""

    def test_single_player_pause_semantics_present(self):
        system_prompt_path = os.path.join(REPO_ROOT, "prompts", "system_prompt_compressed.txt")
        with open(system_prompt_path, "r", encoding="utf-8") as file_handle:
            content = file_handle.read()
        self.assertIn("Do NOT narrate contingent success/failure", content)
        self.assertIn("After requestRoll", content)

    def test_multiplayer_combat_pause_semantics_present(self):
        multipc_combat_prompt_path = os.path.join(
            REPO_ROOT,
            "prompts",
            "combat",
            "combat_sim_prompt_multipc_compressed.txt",
        )
        with open(multipc_combat_prompt_path, "r", encoding="utf-8") as file_handle:
            content = file_handle.read().lower()
        self.assertIn("saving throw", content)
        self.assertIn("stop", content)


class TestExpectedRuntimeTouchpoints(unittest.TestCase):
    """Lock expected future source touchpoints for requestRoll implementation."""

    def test_expected_runtime_files_exist(self):
        expected_files = [
            os.path.join(REPO_ROOT, "main.py"),
            os.path.join(REPO_ROOT, "core", "managers", "combat_manager.py"),
            os.path.join(REPO_ROOT, "core", "ai", "action_handler.py"),
            os.path.join(REPO_ROOT, "prompts", "system_prompt_compressed.txt"),
            os.path.join(REPO_ROOT, "prompts", "validation", "validation_prompt_compressed.txt"),
        ]
        for file_path in expected_files:
            self.assertTrue(os.path.exists(file_path), msg=f"Missing expected touchpoint file: {file_path}")

    def test_runtime_touchpoints_already_contain_save_or_check_context(self):
        touchpoint_keywords = {
            "main.py": ["saving throw", "skill check", "skill checks"],
            "combat_manager.py": ["saving throw", "saving throws"],
            "action_handler.py": ["action", "updateCharacterInfo"],
            "system_prompt_compressed.txt": ["saving throw", "skill check", "skill checks", "save/check", "death save", "con save"],
            "validation_prompt_compressed.txt": ["saving throw", "validity", "save/check"],
        }
        for relative_name, keywords in touchpoint_keywords.items():
            if relative_name == "main.py":
                file_path = os.path.join(REPO_ROOT, relative_name)
            elif relative_name == "combat_manager.py":
                file_path = os.path.join(REPO_ROOT, "core", "managers", relative_name)
            elif relative_name == "action_handler.py":
                file_path = os.path.join(REPO_ROOT, "core", "ai", relative_name)
            elif relative_name == "system_prompt_compressed.txt":
                file_path = os.path.join(REPO_ROOT, "prompts", relative_name)
            else:
                file_path = os.path.join(REPO_ROOT, "prompts", "validation", relative_name)

            with open(file_path, "r", encoding="utf-8") as file_handle:
                source_text = file_handle.read().lower()
            self.assertTrue(
                any(keyword in source_text for keyword in keywords),
                msg=f"Expected at least one save/check keyword in {relative_name}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
