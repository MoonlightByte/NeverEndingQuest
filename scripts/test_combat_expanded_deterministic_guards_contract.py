# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - combat expanded deterministic guards Contract Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Steps 1.1-1.4 contract tests for combat-expanded-deterministic-guards.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


MECHANICS_CONTRADICTION_CLASSES = {
    "unconscious vs HP contradictions",
    "ammo underflow for explicit ranged-ammo spend/use",
    "spell-slot underflow for explicit combat casting/spend language",
}

PHASE_INTEGRITY_CONTRADICTION_CLASSES = {
    "illegal action by forbidden phase actor",
    "illegal stop mid enemy batch",
    "illegal exit while hostiles remain",
    "illegal round increment before all PCs acted",
}


class TestCombatExpandedGuardsOpenSpecContracts(unittest.TestCase):
    """Lock OpenSpec artifacts for expanded deterministic combat guards."""

    @classmethod
    def setUpClass(cls):
        change_root = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-expanded-deterministic-guards",
        )
        cls.paths = {
            "proposal": os.path.join(change_root, "proposal.md"),
            "design": os.path.join(change_root, "design.md"),
            "tasks": os.path.join(change_root, "tasks.md"),
            "mechanics_spec": os.path.join(
                change_root,
                "specs",
                "tt-combat-mechanics-contradiction-guards",
                "spec.md",
            ),
            "phase_spec": os.path.join(
                change_root,
                "specs",
                "tt-combat-phase-integrity-guards",
                "spec.md",
            ),
        }

        cls.content = {}
        for key, path in cls.paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_tasks_cover_steps_1_1_to_1_4(self):
        tasks_text = self.content["tasks"]
        self.assertIn("1.1 Add focused combat contract tests", tasks_text)
        self.assertIn("1.2 Add contract coverage for explicit HP/unconscious", tasks_text)
        self.assertIn("1.3 Add contract coverage for forbidden phase actor", tasks_text)
        self.assertIn("1.4 Add fail-open contract coverage", tasks_text)

    def test_proposal_locks_explicit_and_bounded_scope(self):
        proposal_text = self.content["proposal"]
        self.assertIn("deterministic combat guards for explicit contradictions only", proposal_text)
        self.assertIn("fail-open behavior for ambiguous or unparseable combat text", proposal_text)
        self.assertIn("`updateEncounter.ops`", proposal_text)
        self.assertIn("roll resolution or dice-engine behavior", proposal_text)

    def test_design_locks_fail_open_and_no_broad_nlp(self):
        design_text = self.content["design"]
        self.assertIn("Ambiguity fails open", design_text)
        self.assertIn("No roll resolution engine", design_text)
        self.assertIn("No style/tactics validation", design_text)


class TestCombatMechanicsContradictionLocks(unittest.TestCase):
    """Lock mechanics contradiction classes for deterministic guard expansion."""

    @classmethod
    def setUpClass(cls):
        spec_path = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-expanded-deterministic-guards",
            "specs",
            "tt-combat-mechanics-contradiction-guards",
            "spec.md",
        )
        design_path = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-expanded-deterministic-guards",
            "design.md",
        )
        with open(spec_path, "r", encoding="utf-8") as file_handle:
            cls.spec_text = file_handle.read()
        with open(design_path, "r", encoding="utf-8") as file_handle:
            cls.design_text = file_handle.read()

    def test_mechanics_contradiction_classes_locked_in_design(self):
        for contradiction_class in sorted(MECHANICS_CONTRADICTION_CLASSES):
            self.assertIn(contradiction_class, self.design_text)

    def test_mechanics_contradiction_scenarios_locked_in_spec(self):
        self.assertIn("Above-zero HP contradicts unconscious mechanical state", self.spec_text)
        self.assertIn("Explicit ranged-ammo spend underflows tracked ammunition", self.spec_text)
        self.assertIn("Explicit leveled combat cast underflows known slots", self.spec_text)

    def test_mechanics_fail_open_scenarios_locked_in_spec(self):
        self.assertIn("Combat deterministic mechanics guards SHALL fail open on ambiguity", self.spec_text)
        self.assertIn("SHALL NOT reject on that basis alone", self.spec_text)
        self.assertIn("SHALL defer to the existing validation path", self.spec_text)


class TestCombatPhaseIntegrityLocks(unittest.TestCase):
    """Lock phase-integrity contradiction classes for deterministic guard expansion."""

    @classmethod
    def setUpClass(cls):
        spec_path = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-expanded-deterministic-guards",
            "specs",
            "tt-combat-phase-integrity-guards",
            "spec.md",
        )
        design_path = os.path.join(
            REPO_ROOT,
            "openspec",
            "changes",
            "combat-expanded-deterministic-guards",
            "design.md",
        )
        with open(spec_path, "r", encoding="utf-8") as file_handle:
            cls.spec_text = file_handle.read()
        with open(design_path, "r", encoding="utf-8") as file_handle:
            cls.design_text = file_handle.read()

    def test_phase_integrity_classes_locked_in_design(self):
        for contradiction_class in sorted(PHASE_INTEGRITY_CONTRADICTION_CLASSES):
            self.assertIn(contradiction_class, self.design_text)

    def test_phase_integrity_scenarios_locked_in_spec(self):
        self.assertIn("Forbidden phase actor attempts an illegal action", self.spec_text)
        self.assertIn("Enemy batch stops before the next legal PC boundary", self.spec_text)
        self.assertIn("Combat exits while hostiles remain", self.spec_text)
        self.assertIn("Round increments before all required PCs acted", self.spec_text)

    def test_phase_integrity_fail_open_scenario_locked_in_spec(self):
        self.assertIn("Combat phase-integrity guards SHALL fail open on non-authoritative ambiguity", self.spec_text)
        self.assertIn("SHALL NOT reject solely from inferred phase assumptions", self.spec_text)


class TestCombatExpandedGuardsRuntimeTouchpoints(unittest.TestCase):
    """Lock source touchpoints expected for later deterministic guard implementation."""

    @classmethod
    def setUpClass(cls):
        cls.paths = {
            "combat_manager": os.path.join(REPO_ROOT, "core", "managers", "combat_manager.py"),
            "action_handler": os.path.join(REPO_ROOT, "core", "ai", "action_handler.py"),
        }
        cls.content = {}
        for key, path in cls.paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_runtime_touchpoint_files_exist(self):
        for path in self.paths.values():
            self.assertTrue(os.path.exists(path), msg=f"Missing expected runtime file: {path}")

    def test_combat_manager_contains_phase_integrity_surfaces(self):
        source = self.content["combat_manager"]
        self.assertIn("CURRENT_PHASE", source)
        self.assertIn("PC_PHASE_COMPLETE", source)
        self.assertIn("PENDING_ENEMIES", source)
        self.assertIn("All monsters have been defeated", source)
        self.assertIn("Include exit action", source)
        self.assertIn("You CANNOT end the round until ALL PCs have taken their turns", source)

    def test_combat_manager_wires_phase_integrity_precheck(self):
        source = self.content["combat_manager"]
        self.assertIn("validate_combat_phase_integrity_precheck", source)
        self.assertIn('"forbidden_actors": multi_pc_manager.get_forbidden_actors()', source)
        self.assertIn('"pending_enemies": multi_pc_manager.get_remaining_enemies_for_round()', source)
        self.assertIn('"pc_phase_complete": multi_pc_manager.pc_phase_complete', source)
        self.assertIn('"current_round": current_round', source)

    def test_action_handler_contains_narrow_action_contract_surfaces(self):
        source = self.content["action_handler"]
        self.assertIn('ACTION_REQUEST_ROLL = "requestRoll"', source)
        self.assertIn('ACTION_UPDATE_ENCOUNTER = "updateEncounter"', source)
        self.assertIn("validate_request_roll_parameters(parameters)", source)
        self.assertIn("encounter_id = parameters.get(\"encounterId\")", source)
        self.assertIn("changes = parameters.get(\"changes\")", source)

    def test_request_roll_runtime_boundary_remains_scaffold_only(self):
        source = self.content["action_handler"]
        self.assertIn("Runtime behavior remains narration-driven in this phase", source)
        self.assertIn("validate payload shape", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
