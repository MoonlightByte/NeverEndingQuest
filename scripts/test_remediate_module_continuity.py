#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Unit tests for continuity remediation script."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from remediate_module_continuity import remediate_module_context


class TestRemediateModuleContinuity(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backfills_required_continuity_keys(self) -> None:
        payload = {"module_name": "Test Module"}
        updated, changes = remediate_module_context(payload, "Test_Module")

        continuity = updated.get("continuity", {})
        self.assertTrue(changes)
        self.assertEqual(continuity.get("continuity_version"), "v1")
        self.assertIn("cold_start", continuity.get("entry_state_variants", {}))
        self.assertIn("partial_context", continuity.get("entry_state_variants", {}))
        self.assertIn("late_arc", continuity.get("entry_state_variants", {}))
        self.assertIsInstance(continuity.get("cross_module_refs"), list)
        self.assertIsInstance(continuity.get("standalone_fallback"), dict)

    def test_preserves_existing_authored_values(self) -> None:
        payload = {
            "module_name": "Test Module",
            "continuity": {
                "continuity_version": "v1",
                "entry_state_variants": {
                    "cold_start": {"summary": "custom cold start"},
                },
                "cross_module_refs": [
                    {
                        "target_module": "Other",
                        "entity_id": "npc.test",
                        "relation": "echo",
                        "confidence": "low",
                    }
                ],
                "standalone_fallback": {"enabled": False},
            },
        }

        updated, changes = remediate_module_context(payload, "Test_Module")

        continuity = updated["continuity"]
        self.assertEqual(continuity["entry_state_variants"]["cold_start"]["summary"], "custom cold start")
        self.assertEqual(continuity["cross_module_refs"][0]["target_module"], "Other")
        self.assertFalse(continuity["standalone_fallback"]["enabled"])
        self.assertIn("continuity.entry_state_variants.partial_context", changes)
        self.assertIn("continuity.entry_state_variants.late_arc", changes)

    def test_idempotent_on_second_pass(self) -> None:
        payload = {"module_name": "Test Module"}
        first, first_changes = remediate_module_context(payload, "Test_Module")
        second, second_changes = remediate_module_context(first, "Test_Module")

        self.assertTrue(first_changes)
        self.assertEqual(second_changes, [])
        self.assertEqual(second["continuity"]["continuity_version"], "v1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
