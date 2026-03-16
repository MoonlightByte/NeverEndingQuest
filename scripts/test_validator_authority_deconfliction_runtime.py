# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Validator Authority Deconfliction Runtime Tests

Transcript-driven behavioral tests for G4 domain-based deconfliction helpers.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestValidatorAuthorityDeconflictionRuntime(unittest.TestCase):
    """Behavior tests for domain-scoped validation deconfliction."""

    def _build_handoff(self, travel_mode="arrival_autocommit", npc_mode="scene_presence_autocommit", mechanics_ok=True):
        from utils.validation_routing import build_authoritative_domain_handoff

        travel_sync_decision = {
            "valid": True,
            "reason": "",
            "reconciliation": travel_mode,
            "inferred_actions": [{"action": "transitionLocation", "parameters": {"newLocation": "NIG03"}}],
        }
        npc_sync_decision = {
            "valid": True,
            "reason": "",
            "reconciliation": npc_mode,
            "inferred_actions": [{"action": "moveBackgroundNPC", "parameters": {"npcName": "Spirit-Touched Hermit Maelo"}}],
        }
        return build_authoritative_domain_handoff(
            travel_sync_decision=travel_sync_decision,
            npc_sync_decision=npc_sync_decision,
            mechanics_ok=mechanics_ok,
            mechanics_reason="" if mechanics_ok else "mechanics precheck failed",
            payload_version="v1",
        )

    def test_travel_reconciled_validator_complaint_is_suppressed(self):
        from utils.validation_routing import apply_authoritative_domain_deconfliction

        handoff = self._build_handoff()
        reason = "Invalid: transitionLocation without updateTime indicates incomplete travel state sync"
        outcome = apply_authoritative_domain_deconfliction(
            is_valid=False,
            reason=reason,
            deterministic_handoff=handoff,
        )

        self.assertTrue(outcome["is_valid"])
        self.assertTrue(outcome["suppression_applied"])
        self.assertIn("travel_state_sync", outcome["suppressed_domains"])
        self.assertEqual(outcome["remaining_failure_domains"], [])

    def test_npc_reconciled_validator_complaint_is_suppressed(self):
        from utils.validation_routing import apply_authoritative_domain_deconfliction

        handoff = self._build_handoff()
        reason = "NPC arrival state sync failed: off-location NPC missing moveBackgroundNPC"
        outcome = apply_authoritative_domain_deconfliction(
            is_valid=False,
            reason=reason,
            deterministic_handoff=handoff,
        )

        self.assertTrue(outcome["is_valid"])
        self.assertTrue(outcome["suppression_applied"])
        self.assertIn("npc_state_sync", outcome["suppressed_domains"])
        self.assertEqual(outcome["remaining_failure_domains"], [])

    def test_mixed_domain_failure_remains_blocking(self):
        from utils.validation_routing import apply_authoritative_domain_deconfliction

        handoff = self._build_handoff()
        reason = "NPC arrival state sync failed, and action schema invalid for updatePlot payload"
        outcome = apply_authoritative_domain_deconfliction(
            is_valid=False,
            reason=reason,
            deterministic_handoff=handoff,
        )

        self.assertFalse(outcome["is_valid"])
        self.assertFalse(outcome["suppression_applied"])
        self.assertIn("npc_state_sync", outcome["suppressed_domains"])
        self.assertIn("unknown", outcome["remaining_failure_domains"])
        self.assertEqual(
            outcome["reason"],
            "Validation failed on unreconciled domain(s): unknown.",
            "Mixed-domain retry reason should only reference unreconciled domains",
        )

    def test_authoritative_domain_failure_is_not_suppressed(self):
        from utils.validation_routing import apply_authoritative_domain_deconfliction

        handoff = self._build_handoff(mechanics_ok=False)
        reason = "Mechanics precheck failed: HP contradiction"
        outcome = apply_authoritative_domain_deconfliction(
            is_valid=False,
            reason=reason,
            deterministic_handoff=handoff,
        )

        self.assertFalse(outcome["is_valid"])
        self.assertFalse(outcome["suppression_applied"])
        self.assertEqual(outcome["suppressed_domains"], [])
        self.assertIn("mechanics_precheck", outcome["remaining_failure_domains"])


class TestValidatorAuthorityDeconflictionSourceContract(unittest.TestCase):
    """Source-contract checks for main runtime wiring."""

    def test_main_uses_domain_deconfliction_helper(self):
        main_path = os.path.join(REPO_ROOT, "main.py")
        with open(main_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("apply_authoritative_domain_deconfliction", content)
        self.assertIn("domain-based deterministic handoff suppression", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
