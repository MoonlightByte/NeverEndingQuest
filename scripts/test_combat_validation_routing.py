# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Combat Validation Routing Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for combat validation compression-routing helper behavior and
combat-manager source-contract wiring expectations.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestCombatValidationCompressionBehavior(unittest.TestCase):
    """Behavior tests for shared compression-threshold routing helper."""

    def test_compression_disabled_returns_false_for_combat(self):
        from utils.validation_routing import should_compress_validation_context

        self.assertFalse(
            should_compress_validation_context(
                total_chars=40000,
                compression_enabled=False,
                threshold_chars=1000,
            )
        )

    def test_below_threshold_returns_false_for_combat(self):
        from utils.validation_routing import should_compress_validation_context

        self.assertFalse(
            should_compress_validation_context(
                total_chars=999,
                compression_enabled=True,
                threshold_chars=1000,
            )
        )

    def test_equal_or_above_threshold_returns_true_for_combat(self):
        from utils.validation_routing import should_compress_validation_context

        self.assertTrue(
            should_compress_validation_context(
                total_chars=1000,
                compression_enabled=True,
                threshold_chars=1000,
            )
        )
        self.assertTrue(
            should_compress_validation_context(
                total_chars=12001,
                compression_enabled=True,
                threshold_chars=12000,
            )
        )


class TestCombatValidationRoutingSourceContract(unittest.TestCase):
    """Source-contract tests for intended Step 3.2 combat wiring."""

    @classmethod
    def setUpClass(cls):
        model_config_path = os.path.join(REPO_ROOT, "model_config.py")
        combat_manager_path = os.path.join(
            REPO_ROOT,
            "core",
            "managers",
            "combat_manager.py",
        )

        with open(model_config_path, "r", encoding="utf-8") as file_handle:
            cls.model_config_source = file_handle.read()

        with open(combat_manager_path, "r", encoding="utf-8") as file_handle:
            cls.combat_manager_source = file_handle.read()

    def test_model_config_exposes_validation_threshold_constant(self):
        self.assertIn("VALIDATION_COMPRESSION_MIN_CHARS", self.model_config_source)

    def test_combat_manager_uses_threshold_routing_helper(self):
        self.assertTrue(
            "get_validation_compression_decision" in self.combat_manager_source,
            msg=(
                "Step 3.2 contract: combat_manager should use "
                "get_validation_compression_decision for threshold routing."
            ),
        )

    def test_combat_manager_records_payload_size_telemetry(self):
        self.assertTrue(
            "validation_payload_chars" in self.combat_manager_source,
            msg=(
                "Step 3.2 contract: combat_manager should emit "
                "validation_payload_chars in routing telemetry."
            ),
        )

    def test_combat_manager_records_compression_reason_code(self):
        self.assertTrue(
            "compression_reason" in self.combat_manager_source,
            msg=(
                "Step 3.2 contract: combat_manager should emit "
                "compression_reason in routing telemetry."
            ),
        )

    def test_combat_manager_emits_routing_telemetry_payload(self):
        self.assertTrue(
            "validation_routing_telemetry" in self.combat_manager_source,
            msg=(
                "Step 3.2 contract: combat_manager should create a "
                "validation_routing_telemetry payload."
            ),
        )

    def test_compression_decision_has_fail_open_fallback(self):
        self.assertIn(
            "decision_helper_error_default_uncompressed",
            self.combat_manager_source,
        )
        self.assertIn(
            "use_validation_compression = False",
            self.combat_manager_source,
        )

    def test_compression_apply_failure_falls_back_to_uncompressed_context(self):
        self.assertIn(
            "compression_apply_error_fallback_uncompressed",
            self.combat_manager_source,
        )
        self.assertIn(
            "falling back to uncompressed context",
            self.combat_manager_source,
        )

    def test_telemetry_helper_failure_uses_fallback_payload(self):
        self.assertIn(
            "telemetry_builder_error_fallback",
            self.combat_manager_source,
        )
        self.assertIn(
            "using fallback telemetry payload",
            self.combat_manager_source,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
