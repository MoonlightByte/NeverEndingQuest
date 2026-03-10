# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Validation Compression Routing Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Tests for threshold-based validation compression routing.
"""

import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestValidationCompressionRoutingBehavior(unittest.TestCase):
    """Behavior tests for compression threshold helper."""

    def test_compression_disabled_returns_false(self):
        from utils.validation_routing import should_compress_validation_context

        self.assertFalse(
            should_compress_validation_context(
                total_chars=50000,
                compression_enabled=False,
                threshold_chars=1000,
            )
        )

    def test_below_threshold_returns_false(self):
        from utils.validation_routing import should_compress_validation_context

        self.assertFalse(
            should_compress_validation_context(
                total_chars=999,
                compression_enabled=True,
                threshold_chars=1000,
            )
        )

    def test_equal_or_above_threshold_returns_true(self):
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
                total_chars=4000,
                compression_enabled=True,
                threshold_chars=1000,
            )
        )


class TestValidationCompressionRoutingSourceContract(unittest.TestCase):
    """Source-contract tests for main pipeline wiring."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, "model_config.py"), "r", encoding="utf-8") as f:
            cls.model_config = f.read()
        with open(os.path.join(REPO_ROOT, "main.py"), "r", encoding="utf-8") as f:
            cls.main_source = f.read()

    def test_model_config_exposes_threshold_constant(self):
        self.assertIn("VALIDATION_COMPRESSION_MIN_CHARS", self.model_config)

    def test_main_uses_threshold_helper(self):
        self.assertIn("get_validation_compression_decision", self.main_source)
        self.assertIn("VALIDATION_COMPRESSION_MIN_CHARS", self.main_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
