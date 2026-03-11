# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - combat encounter ops Contract Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Step 1.1-1.3 contract tests for combat-encounter-ops-second-wave.
"""

import os
import re
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


SUPPORTED_ENEMY_ENCOUNTER_OPS = {
    "hp_delta",
    "set_hp",
    "condition_add",
    "condition_remove",
    "set_status",
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
    """Prefer main synced spec path; fall back to change-local delta spec."""
    main_spec = os.path.join(REPO_ROOT, "openspec", "specs", spec_slug, "spec.md")
    if os.path.exists(main_spec):
        return main_spec

    delta_spec = os.path.join(change_root, "specs", spec_slug, "spec.md")
    if os.path.exists(delta_spec):
        return delta_spec

    raise FileNotFoundError(f"Spec not found in main or delta paths: {spec_slug}")


class TestCombatEncounterOpsOpenSpecContracts(unittest.TestCase):
    """Lock OpenSpec artifacts for Workstream I Step 1.1-1.2."""

    @classmethod
    def setUpClass(cls):
        change_root = _resolve_archived_or_live_change_root(
            "combat-encounter-ops-second-wave"
        )
        cls.paths = {
            "proposal": os.path.join(change_root, "proposal.md"),
            "design": os.path.join(change_root, "design.md"),
            "tasks": os.path.join(change_root, "tasks.md"),
            "spec": _resolve_main_or_delta_spec(
                "tt-combat-structured-encounter-ops-routing",
                change_root,
            ),
        }
        cls.content = {}
        for key, path in cls.paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_tasks_include_step_1_1_scope(self):
        tasks_text = self.content["tasks"]
        self.assertIn("1.1 Add focused combat contract tests", tasks_text)
        self.assertIn("mixed `updateEncounter` payload preference", tasks_text)
        self.assertIn("routing separation", tasks_text)

    def test_spec_locks_mixed_update_encounter_payload_preference(self):
        spec_text = self.content["spec"]
        self.assertIn("mixed `updateEncounter` payloads", spec_text)
        self.assertIn("both `changes` and supported `ops`", spec_text)
        self.assertIn("Mixed combat payload is preferred for damaged enemy", spec_text)

    def test_spec_locks_routing_separation(self):
        spec_text = self.content["spec"]
        self.assertIn(
            "routing separation between enemy encounter ops and PC/allied character ops",
            spec_text,
        )
        self.assertIn("enemy-side state SHALL remain on `updateEncounter`", spec_text)
        self.assertIn("PC/allied state SHALL remain on `updateCharacterInfo`", spec_text)

    def test_design_and_proposal_preserve_boundary_language(self):
        proposal_text = self.content["proposal"]
        design_text = self.content["design"]
        self.assertIn("enemy-side combat mutations", proposal_text)
        self.assertIn("PC/allied mutations", proposal_text)
        self.assertIn("routing boundary", design_text)
        self.assertIn("Enemy-side combat mutations SHALL remain on `updateEncounter`", design_text)

    def test_tasks_include_step_1_2_scope(self):
        tasks_text = self.content["tasks"]
        self.assertIn("1.2 Add contract coverage for the approved first-wave enemy op family", tasks_text)
        self.assertIn("`set_status`", tasks_text)

    def test_tasks_include_step_1_3_scope(self):
        tasks_text = self.content["tasks"]
        self.assertIn("1.3 Preserve prose-only fallback coverage", tasks_text)
        self.assertIn("fail-open handling", tasks_text)

    def test_step_1_2_op_set_locked_in_proposal(self):
        proposal_text = self.content["proposal"]
        line_match = re.search(
            r"first-wave enemy op family for combat: ([^\n]+)\.",
            proposal_text,
        )
        if line_match is None:
            self.fail("Proposal missing first-wave enemy op family sentence")

        proposal_ops = set(re.findall(r"`([a-z_]+)`", line_match.group(1)))
        self.assertEqual(proposal_ops, SUPPORTED_ENEMY_ENCOUNTER_OPS)

    def test_step_1_2_op_set_locked_in_design(self):
        design_text = self.content["design"]
        start_marker = "**Decision:** The approved first-wave enemy op family SHALL be limited to:"
        end_marker = "**Rationale:**"
        start_index = design_text.find(start_marker)
        self.assertNotEqual(start_index, -1, msg="Design missing first-wave enemy op family decision block")

        end_index = design_text.find(end_marker, start_index)
        self.assertNotEqual(end_index, -1, msg="Design first-wave enemy op family block missing rationale boundary")

        decision_block = design_text[start_index:end_index]
        decision_ops = set(re.findall(r"`([a-z_]+)`", decision_block))
        self.assertEqual(decision_ops, SUPPORTED_ENEMY_ENCOUNTER_OPS)

    def test_step_1_2_op_set_locked_in_tasks(self):
        tasks_text = self.content["tasks"]
        line_match = re.search(
            r"1\.2 Add contract coverage for the approved first-wave enemy op family \(([^\n]+)\)\.",
            tasks_text,
        )
        if line_match is None:
            self.fail("Tasks missing Step 1.2 first-wave enemy op family list")

        task_ops = set(re.findall(r"`([a-z_]+)`", line_match.group(1)))
        self.assertEqual(task_ops, SUPPORTED_ENEMY_ENCOUNTER_OPS)

    def test_spec_keeps_supported_ops_boundary_language(self):
        spec_text = self.content["spec"]
        self.assertIn("supported `ops`", spec_text)
        self.assertIn("Unsupported enemy ops", spec_text)

    def test_spec_locks_prose_fallback_and_fail_open_scenarios(self):
        spec_text = self.content["spec"]
        self.assertIn("preserve compatibility fallback", spec_text)
        self.assertIn("Prose-only enemy payload remains valid during migration", spec_text)
        self.assertIn("Unsupported enemy ops do not remove safe fallback behavior", spec_text)
        self.assertIn("partial, unsupported, or ambiguous enemy `ops`", spec_text)

    def test_proposal_and_design_lock_fallback_contract(self):
        proposal_text = self.content["proposal"]
        design_text = self.content["design"]
        self.assertIn("fail-open fallback behavior for unsupported or ambiguous enemy ops payloads", proposal_text)
        self.assertIn("MUST preserve prose fallback for unsupported, partial, or ambiguous enemy ops payloads", proposal_text)
        self.assertIn("Unsupported or ambiguous enemy ops fail open to safe fallback", design_text)
        self.assertIn("preserve prose fallback behavior", design_text)


class TestCombatEncounterOpsRuntimeSourceContracts(unittest.TestCase):
    """Lock source touchpoints before prompt/runtime migration steps."""

    @classmethod
    def setUpClass(cls):
        cls.paths = {
            "action_handler": os.path.join(REPO_ROOT, "core", "ai", "action_handler.py"),
            "update_encounter": os.path.join(REPO_ROOT, "updates", "update_encounter.py"),
            "sim_prompt": os.path.join(
                REPO_ROOT,
                "prompts",
                "combat",
                "combat_sim_prompt_multipc_compressed.txt",
            ),
            "sim_prompt_mirror": os.path.join(
                REPO_ROOT,
                "prompts",
                "combat",
                "combat_sim_prompt_multipc.txt",
            ),
            "validation_prompt": os.path.join(
                REPO_ROOT,
                "prompts",
                "combat",
                "combat_validation_prompt_multipc_compressed.txt",
            ),
            "validation_prompt_mirror": os.path.join(
                REPO_ROOT,
                "prompts",
                "combat",
                "combat_validation_prompt_multipc.txt",
            ),
        }

        cls.content = {}
        for key, path in cls.paths.items():
            with open(path, "r", encoding="utf-8") as file_handle:
                cls.content[key] = file_handle.read()

    def test_runtime_touchpoint_files_exist(self):
        for path in self.paths.values():
            self.assertTrue(os.path.exists(path), msg=f"Missing expected source file: {path}")

    def test_action_handler_has_explicit_update_routing_surfaces(self):
        source = self.content["action_handler"]
        self.assertIn('ACTION_UPDATE_ENCOUNTER = "updateEncounter"', source)
        self.assertIn('ACTION_UPDATE_CHARACTER_INFO = "updateCharacterInfo"', source)
        self.assertIn("elif action_type == ACTION_UPDATE_ENCOUNTER:", source)
        self.assertIn("elif action_type == ACTION_UPDATE_CHARACTER_INFO:", source)

    def test_update_encounter_module_exposes_current_enemy_update_path(self):
        source = self.content["update_encounter"]
        self.assertIn("def update_encounter(encounter_id, changes", source)
        self.assertIn("Current encounter info", source)

    def test_update_encounter_signature_accepts_ops(self):
        source = self.content["update_encounter"]
        self.assertIn("def update_encounter(encounter_id, changes, ops=None, max_retries=3):", source)

    def test_action_handler_accepts_changes_or_ops_for_update_encounter(self):
        source = self.content["action_handler"]
        self.assertIn('changes = parameters.get("changes")', source)
        self.assertIn('ops = parameters.get("ops")', source)
        self.assertIn("if encounter_id and (has_changes_payload or has_ops_payload):", source)
        self.assertIn("Missing required parameters for updateEncounter", source)

    def test_action_handler_forwards_encounter_ops(self):
        source = self.content["action_handler"]
        self.assertIn("updated_encounter = update_encounter(", source)
        self.assertIn("ops=ops", source)

    def test_update_encounter_includes_deterministic_ops_routing(self):
        source = self.content["update_encounter"]
        self.assertIn("SUPPORTED_ENCOUNTER_OPS", source)
        self.assertIn("_prepare_supported_encounter_ops", source)
        self.assertIn("_apply_prepared_encounter_ops", source)
        self.assertIn("ENCOUNTER_OPS_ROUTE mode=ops reason=supported_ops_applied", source)

    def test_update_encounter_supported_op_family_is_narrow_and_exact(self):
        source = self.content["update_encounter"]
        set_match = re.search(r"SUPPORTED_ENCOUNTER_OPS\s*=\s*\{([^}]+)\}", source, re.DOTALL)
        if set_match is None:
            self.fail("SUPPORTED_ENCOUNTER_OPS constant not found")

        extracted_ops = set(re.findall(r'"([a-z_]+)"', set_match.group(1)))
        self.assertEqual(extracted_ops, SUPPORTED_ENEMY_ENCOUNTER_OPS)

    def test_update_encounter_does_not_expand_into_forbidden_runtime_domains(self):
        source = self.content["update_encounter"]
        forbidden_tokens = [
            '"spawn"',
            '"despawn"',
            '"initiative_set"',
            '"initiative_reorder"',
            '"position_set"',
            '"move_creature"',
            '"requestRoll"',
            '"rollType"',
        ]
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_combat_prompt_sources_contain_update_action_contract_terms(self):
        sim_text = self.content["sim_prompt"]
        sim_mirror_text = self.content["sim_prompt_mirror"]
        validation_text = self.content["validation_prompt"]
        validation_mirror_text = self.content["validation_prompt_mirror"]
        self.assertIn("updateEncounter", sim_text)
        self.assertIn("updateCharacterInfo", sim_text)
        self.assertIn("updateEncounter", sim_mirror_text)
        self.assertIn("updateCharacterInfo", sim_mirror_text)
        self.assertIn("updateEncounter", validation_text)
        self.assertIn("updateCharacterInfo", validation_text)
        self.assertIn("updateEncounter", validation_mirror_text)
        self.assertIn("updateCharacterInfo", validation_mirror_text)

    def test_sim_prompt_keeps_explicit_routing_boundary(self):
        sim_text = self.content["sim_prompt"]
        self.assertIn("pc_or_npc: \"updateCharacterInfo", sim_text)
        self.assertIn("enemy: \"updateEncounter", sim_text)
        self.assertIn("Any PC/NPC update via updateEncounter is INVALID", sim_text)
        self.assertIn("Never log enemy HP/conditions in updateCharacterInfo", sim_text)

    def test_validation_prompt_keeps_explicit_routing_boundary(self):
        validation_text = self.content["validation_prompt"]
        self.assertIn("never_cross: \"Do not use updateCharacterInfo for monsters; do not use updateEncounter for PCs/NPCs", validation_text)
        self.assertIn("updateCharacterInfo applied to enemy", validation_text)
        self.assertIn("updateEncounter changing PC/NPC HP", validation_text)

    def test_validation_prompt_prefers_enemy_mixed_payload_with_fallback(self):
        validation_text = self.content["validation_prompt"]
        self.assertIn("enemy_mixed_payload_preferred", validation_text)
        self.assertIn("supported_encounter_ops", validation_text)
        self.assertIn("changes-only updateEncounter remains compatibility-valid during migration", validation_text)
        self.assertNotIn("do not introduce updateEncounter.ops in this slice", validation_text)

    def test_sim_prompt_mirror_prefers_enemy_mixed_payload_with_fallback(self):
        sim_mirror_text = self.content["sim_prompt_mirror"]
        self.assertIn("prefer mixed payloads with BOTH `changes` and `ops` for supported enemy HP/status/condition mechanics", sim_mirror_text)
        self.assertIn("Supported enemy encounter ops in this slice: hp_delta, set_hp, condition_add, condition_remove, set_status.", sim_mirror_text)
        self.assertIn("changes-only updateEncounter remains compatibility-valid during migration", sim_mirror_text)
        self.assertNotIn("Do not include updateEncounter.parameters.ops in this slice", sim_mirror_text)

    def test_validation_prompt_mirror_prefers_enemy_mixed_payload_with_fallback(self):
        validation_mirror_text = self.content["validation_prompt_mirror"]
        self.assertIn("Prefer mixed payloads with BOTH changes and ops for supported enemy HP/status/condition mechanics.", validation_mirror_text)
        self.assertIn("Supported enemy encounter ops in this slice: hp_delta, set_hp, condition_add, condition_remove, set_status.", validation_mirror_text)
        self.assertIn("changes-only remains compatibility-valid during migration.", validation_mirror_text)
        self.assertNotIn("updateEncounter.parameters.ops is out of scope in this slice", validation_mirror_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
