#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Pre-implementation contract inventory for validator-authority-deconfliction.

This file intentionally locks the transcript families and payload shape that G4
must implement. It avoids asserting runtime behavior before G4 code changes.
"""

import json
import os
import unittest


class TestValidatorAuthorityDeconflictionContractInventory(unittest.TestCase):
    """Lock the planned G4 contract and transcript families before implementation."""

    def test_change_directory_exists(self):
        change_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "openspec",
            "changes",
            "validator-authority-deconfliction",
        )
        self.assertTrue(os.path.isdir(change_dir))

    def test_executor_prompt_lists_transcript_families(self):
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "openspec",
            "changes",
            "validator-authority-deconfliction",
            "executor_prompts.md",
        )
        with open(prompt_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("Travel reconciled, validator still complains", content)
        self.assertIn("NPC scene presence reconciled, validator still complains", content)
        self.assertIn("Mixed-domain failure", content)
        self.assertIn("Deterministic authoritative failure", content)
        self.assertIn("Telemetry path", content)

    def test_design_defines_exact_domain_payload_shape(self):
        design_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "openspec",
            "changes",
            "validator-authority-deconfliction",
            "design.md",
        )
        with open(design_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn('"travel_state_sync"', content)
        self.assertIn('"npc_state_sync"', content)
        self.assertIn('"mechanics_precheck"', content)
        self.assertIn('"all_authoritative_domains_passed"', content)
        self.assertIn('"reconciled_domains"', content)

    def test_new_spec_requires_domain_scoped_handoff(self):
        spec_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "openspec",
            "changes",
            "validator-authority-deconfliction",
            "specs",
            "tt-validator-authoritative-domain-handoff",
            "spec.md",
        )
        with open(spec_path, "r", encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("domain-scoped", content)
        self.assertIn("travel_state_sync", content)
        self.assertIn("npc_state_sync", content)
        self.assertIn("mechanics_precheck", content)


if __name__ == "__main__":
    unittest.main()
