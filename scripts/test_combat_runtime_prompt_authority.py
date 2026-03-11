# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Combat Runtime Prompt Authority Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Source-contract tests for compressed combat prompt runtime authority.
"""

import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCombatRuntimePromptAuthority(unittest.TestCase):
    """Ensure multi-PC combat runtime paths use compressed prompt sources."""

    @classmethod
    def setUpClass(cls):
        combat_manager_path = os.path.join(
            REPO_ROOT,
            "core",
            "managers",
            "combat_manager.py",
        )

        with open(combat_manager_path, "r", encoding="utf-8") as file_handle:
            cls.combat_manager_source = file_handle.read()

    def test_multipc_simulation_uses_compressed_prompt_path(self):
        self.assertTrue(
            "prompt_file = 'combat/combat_sim_prompt_multipc_compressed.txt'"
            in self.combat_manager_source,
            msg="Multi-PC sim runtime should assign compressed prompt path directly.",
        )

    def test_multipc_simulation_does_not_assign_uncompressed_prompt_path(self):
        self.assertFalse(
            "prompt_file = 'combat/combat_sim_prompt_multipc.txt'"
            in self.combat_manager_source,
            msg="Multi-PC sim runtime should not assign uncompressed prompt path as live authority.",
        )

    def test_multipc_validation_uses_compressed_prompt_path(self):
        self.assertTrue(
            "validation_prompt = read_prompt_from_file('combat/combat_validation_prompt_multipc_compressed.txt')"
            in self.combat_manager_source,
            msg="Multi-PC validation runtime should load compressed validator prompt.",
        )

    def test_multipc_validation_does_not_load_uncompressed_prompt_path(self):
        self.assertFalse(
            "validation_prompt = read_prompt_from_file('combat/combat_validation_prompt_multipc.txt')"
            in self.combat_manager_source,
            msg="Multi-PC validation runtime should not load uncompressed validator prompt as live authority.",
        )

    def test_single_player_simulation_default_path_remains_original(self):
        self.assertTrue(
            "prompt_file = 'combat/combat_sim_prompt.txt'" in self.combat_manager_source,
            msg="Single-player sim path should retain original default prompt file path.",
        )

    def test_single_player_validation_retains_toggle_based_paths(self):
        self.assertTrue(
            "validation_prompt = read_prompt_from_file('combat/combat_validation_prompt_compressed.txt')"
            in self.combat_manager_source,
            msg="Single-player validation should retain compressed-path toggle branch.",
        )
        self.assertTrue(
            "validation_prompt = read_prompt_from_file('combat/combat_validation_prompt.txt')"
            in self.combat_manager_source,
            msg="Single-player validation should retain uncompressed-path toggle branch.",
        )
        self.assertTrue(
            "if USE_COMPRESSED_COMBAT:" in self.combat_manager_source,
            msg="Single-player validation should retain USE_COMPRESSED_COMBAT toggle gate.",
        )

    def test_tabletop_phase_sync_touchpoints_remain_present(self):
        self.assertTrue(
            "apply_opening_batch_marker(encounter_data, \"dmGroup\")"
            in self.combat_manager_source,
            msg="Round-start DM-group marker application should remain present.",
        )
        self.assertTrue(
            "round_starts_with = encounter_data.get(\"roundStartsWith\", \"pcGroup\")"
            in self.combat_manager_source,
            msg="Round-start phase sync read from encounter state should remain present.",
        )
        self.assertTrue(
            "multi_pc_manager.get_remaining_enemies_for_round()"
            in self.combat_manager_source,
            msg="Pending-enemy phase sync touchpoint should remain present.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
