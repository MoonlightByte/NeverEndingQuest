# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Expanded Deterministic Guards Contract Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Prompt 1 contract tests for the expanded deterministic-guards change.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


CHANGE_NAME = "prompt-validator-expanded-deterministic-guards"
CHANGE_ROOT = os.path.join(REPO_ROOT, "openspec", "changes", CHANGE_NAME)

GUARD_DOMAINS = {
    "cantrip_no_slot": "cantrip/no-slot legality",
    "slot_underflow": "slot-underflow",
    "unconscious_hp": "unconscious-vs-HP",
    "ammo_legality": "ammo legality",
    "rest_duration": "rest-duration legality",
}


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()


class TestExpandedGuardsOpenSpecArtifacts(unittest.TestCase):
    """Lock OpenSpec artifact coverage for new deterministic guard domains."""

    @classmethod
    def setUpClass(cls):
        cls.files = {
            "proposal": os.path.join(CHANGE_ROOT, "proposal.md"),
            "design": os.path.join(CHANGE_ROOT, "design.md"),
            "tasks": os.path.join(CHANGE_ROOT, "tasks.md"),
            "executor_prompts": os.path.join(CHANGE_ROOT, "executor_prompts.md"),
            "spec_spell": os.path.join(
                CHANGE_ROOT,
                "specs",
                "tt-spell-slot-legality-guard",
                "spec.md",
            ),
            "spec_unconscious": os.path.join(
                CHANGE_ROOT,
                "specs",
                "tt-unconscious-hp-integrity-guard",
                "spec.md",
            ),
            "spec_ammo": os.path.join(
                CHANGE_ROOT,
                "specs",
                "tt-ammo-legality-guard",
                "spec.md",
            ),
            "spec_rest": os.path.join(
                CHANGE_ROOT,
                "specs",
                "tt-rest-duration-precheck",
                "spec.md",
            ),
            "spec_modified_base": os.path.join(
                CHANGE_ROOT,
                "specs",
                "tt-deterministic-mechanics-precheck",
                "spec.md",
            ),
        }
        cls.content = {name: _read_text(path) for name, path in cls.files.items()}

    def test_all_artifact_files_exist(self):
        for path in self.files.values():
            self.assertTrue(os.path.exists(path), msg=f"Missing artifact: {path}")

    def test_proposal_covers_all_guard_domains(self):
        proposal = self.content["proposal"]
        for domain_phrase in GUARD_DOMAINS.values():
            self.assertIn(domain_phrase, proposal)

    def test_design_preserves_fail_open_philosophy(self):
        design = self.content["design"].lower()
        self.assertIn("fail-open", design)
        self.assertIn("ambiguous", design)
        self.assertIn("explicit", design)

    def test_tasks_prompt1_scope_is_test_only(self):
        prompts = self.content["executor_prompts"].lower()
        self.assertIn("prompt 1", prompts)
        self.assertIn("test-only", prompts)
        self.assertIn("no runtime helper edits yet", prompts)

    def test_spell_slot_spec_mentions_both_spell_guards(self):
        spec = self.content["spec_spell"].lower()
        self.assertIn("cantrip", spec)
        self.assertIn("underflow", spec)

    def test_unconscious_spec_mentions_hp_above_zero_contradiction(self):
        spec = self.content["spec_unconscious"].lower()
        self.assertIn("above 0 hp", spec)
        self.assertIn("unconscious", spec)

    def test_ammo_spec_mentions_use_or_fire_language(self):
        spec = self.content["spec_ammo"].lower()
        self.assertIn("fired", spec)
        self.assertIn("spent", spec)
        self.assertIn("used", spec)

    def test_rest_spec_locks_short_and_long_duration_minimums(self):
        spec = self.content["spec_rest"].lower()
        self.assertIn("less than 60 minutes", spec)
        self.assertIn("less than 8 hours", spec)
        self.assertIn("fail open", spec)

    def test_modified_base_spec_preserves_ambiguity_pass_through(self):
        spec = self.content["spec_modified_base"].lower()
        self.assertIn("ambiguous", spec)
        self.assertIn("pass", spec)


class TestExpandedGuardsTouchpointContracts(unittest.TestCase):
    """Lock likely implementation touchpoints for Prompt 2 helper work."""

    def test_expected_touchpoint_files_exist(self):
        expected = [
            os.path.join(REPO_ROOT, "utils", "deterministic_mechanics_precheck.py"),
            os.path.join(REPO_ROOT, "scripts", "test_deterministic_mechanics_precheck.py"),
            os.path.join(REPO_ROOT, "main.py"),
            os.path.join(REPO_ROOT, "prompts", "system_prompt_compressed.txt"),
            os.path.join(REPO_ROOT, "prompts", "validation", "validation_prompt_compressed.txt"),
        ]
        for path in expected:
            self.assertTrue(os.path.exists(path), msg=f"Missing expected touchpoint file: {path}")

    def test_current_precheck_has_stable_integration_anchor(self):
        precheck_source = _read_text(os.path.join(REPO_ROOT, "utils", "deterministic_mechanics_precheck.py"))
        self.assertIn("def validate_deterministic_mechanics_precheck", precheck_source)
        self.assertIn("Fail-open", precheck_source)

    def test_main_pipeline_references_precheck(self):
        main_source = _read_text(os.path.join(REPO_ROOT, "main.py"))
        self.assertIn("validate_deterministic_mechanics_precheck", main_source)


class TestFailOpenBaselineContracts(unittest.TestCase):
    """Prompt 1 contract tests preserve fail-open baseline for ambiguity."""

    def test_unparseable_magic_text_is_fail_open(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Mystic energies surge unpredictably.",
                    },
                }
            ]
        }

        def loader(_name):
            return {"maxHitPoints": 21}

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_unmatched_ammo_token_is_fail_open(self):
        from utils.deterministic_mechanics_precheck import validate_deterministic_mechanics_precheck

        response_json = {
            "actions": [
                {
                    "action": "updateCharacterInfo",
                    "parameters": {
                        "characterName": "Acheron",
                        "changes": "Removed 2 moon shards from inventory.",
                    },
                }
            ]
        }

        def loader(_name):
            return {
                "maxHitPoints": 21,
                "ammunition": [{"name": "Arrow", "quantity": 5}],
                "equipment": [],
            }

        valid, reason = validate_deterministic_mechanics_precheck(response_json, character_loader=loader)
        self.assertTrue(valid)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
