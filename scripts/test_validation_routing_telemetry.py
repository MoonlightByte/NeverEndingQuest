# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Validation Routing Telemetry Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Contracts for deterministic routing telemetry fields and reason codes.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestValidationRoutingTelemetryBehavior(unittest.TestCase):
    """Behavior tests for telemetry helper functions."""

    def test_compression_decision_reason_codes(self):
        from utils.validation_routing import get_validation_compression_decision

        use_comp, reason = get_validation_compression_decision(
            total_chars=500,
            compression_enabled=False,
            threshold_chars=1000,
        )
        self.assertFalse(use_comp)
        self.assertEqual(reason, "compression_disabled")

        use_comp, reason = get_validation_compression_decision(
            total_chars=999,
            compression_enabled=True,
            threshold_chars=1000,
        )
        self.assertFalse(use_comp)
        self.assertEqual(reason, "below_threshold")

        use_comp, reason = get_validation_compression_decision(
            total_chars=1000,
            compression_enabled=True,
            threshold_chars=1000,
        )
        self.assertTrue(use_comp)
        self.assertEqual(reason, "at_or_above_threshold")

    def test_build_routing_telemetry_shape(self):
        from utils.validation_routing import build_validation_routing_telemetry

        telemetry = build_validation_routing_telemetry(
            skip_llm_validation=True,
            skip_reason="narration_only",
            used_validation_compression=False,
            compression_reason="below_threshold",
            validation_payload_chars=850,
        )

        self.assertEqual(set(telemetry.keys()), {
            "skip_llm_validation",
            "skip_reason",
            "used_validation_compression",
            "compression_reason",
            "validation_payload_chars",
        })
        self.assertTrue(telemetry["skip_llm_validation"])
        self.assertEqual(telemetry["skip_reason"], "narration_only")
        self.assertEqual(telemetry["compression_reason"], "below_threshold")
        self.assertEqual(telemetry["validation_payload_chars"], 850)


class TestValidationRoutingTelemetrySourceContract(unittest.TestCase):
    """Source-contract tests for main validation wiring."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "main.py"), "r", encoding="utf-8") as f:
            cls.main_source = f.read()

    def test_main_records_validation_routing_telemetry(self):
        self.assertIn("validation_routing_telemetry", self.main_source)
        self.assertIn("VALIDATION_ROUTING_TELEMETRY", self.main_source)

    def test_main_uses_compression_reason_codes(self):
        self.assertIn("compression_reason", self.main_source)
        self.assertIn("skip_reason", self.main_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
