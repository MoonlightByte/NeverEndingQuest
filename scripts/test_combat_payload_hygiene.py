# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Combat Payload Hygiene Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Source-contract tests for duplicated-state reduction and phase/actor packet
preservation in the multi-PC combat payload.
"""

import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _CombatSourceMixin:
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

    def _extract_multipc_context_template(self):
        start_marker = 'multi_pc_context = f"""'
        start_index = self.combat_manager_source.find(start_marker)
        self.assertNotEqual(
            start_index,
            -1,
            msg="Could not locate multi_pc_context template in combat_manager.py",
        )

        content_start = start_index + len(start_marker)
        content_end = self.combat_manager_source.find('"""', content_start)
        self.assertNotEqual(
            content_end,
            -1,
            msg="Could not locate end of multi_pc_context template in combat_manager.py",
        )

        return self.combat_manager_source[content_start:content_end]


class TestCombatDuplicateStateContracts(_CombatSourceMixin, unittest.TestCase):
    """Document duplicated-state contracts that Step 2.2 must resolve."""

    def test_multipc_context_emits_current_phase_only_once(self):
        multipc_context_template = self._extract_multipc_context_template()
        current_phase_emissions = multipc_context_template.count("CURRENT_PHASE:")

        self.assertLessEqual(
            current_phase_emissions,
            1,
            msg=(
                "DUPLICATED STATE DETECTED: multi_pc_context emits CURRENT_PHASE "
                f"{current_phase_emissions} times. Step 2.2 should reduce this to one "
                "authoritative emission."
            ),
        )


class TestCombatPhaseActorPacketPreservation(_CombatSourceMixin, unittest.TestCase):
    """Lock required phase/actor packet touchpoints during payload slimming."""

    def test_required_initiative_authority_fields_remain_present(self):
        self.assertIn('"initiativeMode"', self.combat_manager_source)
        self.assertIn('"initiativeRolls"', self.combat_manager_source)
        self.assertIn('"initiativeWinner"', self.combat_manager_source)
        self.assertIn('"roundStartsWith"', self.combat_manager_source)

    def test_required_phase_actor_touchpoints_remain_present(self):
        self.assertIn("PENDING_ENEMIES:", self.combat_manager_source)
        self.assertIn(
            "multi_pc_manager.get_remaining_enemies_for_round()",
            self.combat_manager_source,
        )
        self.assertIn(
            "multi_pc_manager.format_party_turn_summary()",
            self.combat_manager_source,
        )
        self.assertIn(
            "multi_pc_manager.format_pc_context_for_prompt(active_pc)",
            self.combat_manager_source,
        )

    def test_initiative_tracker_hook_remains_present(self):
        self.assertIn(
            "live_tracker = multi_pc_manager.format_initiative_tracker(encounter_data)",
            self.combat_manager_source,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
