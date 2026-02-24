# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Character sheet stats resilience source-contract tests.

Validates Step 4.2 contracts for `pc-creation-startup-fixes`:
- null-safe displayCharacterStats behavior
- deterministic waiting/error states on null payload
- defensive try/catch guard for render failures
"""

import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCharacterSheetStatsResilienceContracts(unittest.TestCase):
    """Source-level contracts for stats rendering resilience."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.html_path = os.path.join(cls.repo_root, "web", "templates", "game_interface.html")
        with open(cls.html_path, "r", encoding="utf-8") as handle:
            cls.source = handle.read()

        start = cls.source.find("function displayCharacterStats(data, error)")
        end = cls.source.find("function displaySpellsAndMagic(data)", start)
        cls.stats_function = cls.source[start:end]

    def test_stats_renderer_signature_includes_error_context(self):
        """displayCharacterStats should accept (data, error)."""
        self.assertIn("function displayCharacterStats(data, error)", self.source)

    def test_null_guard_precedes_data_name_access(self):
        """Null guard must execute before any data.name access."""
        null_guard_pos = self.stats_function.find("if (!data)")
        data_name_pos = self.stats_function.find("data.name")
        return_pos = self.stats_function.find("return;", null_guard_pos)

        self.assertGreaterEqual(null_guard_pos, 0)
        self.assertGreater(return_pos, null_guard_pos)
        self.assertGreater(data_name_pos, return_pos)

    def test_null_payload_has_waiting_and_error_states(self):
        """Null path should differentiate waiting vs explicit backend error."""
        self.assertIn("if (error)", self.stats_function)
        self.assertIn("Error loading character stats:", self.stats_function)
        self.assertIn("Loading character stats... (waiting for data)", self.stats_function)
        self.assertIn("escapeRepairHtml(error)", self.stats_function)

    def test_defensive_try_catch_contract_present(self):
        """Main render path should be wrapped with try/catch fallback."""
        self.assertIn("try {", self.stats_function)
        self.assertIn("catch (renderError)", self.stats_function)
        self.assertIn("Error displaying character stats. Retrying...", self.stats_function)
        self.assertIn("console.error('[displayCharacterStats] Render error:'", self.stats_function)

    def test_stats_socket_handler_passes_error_context(self):
        """player_data_response stats branch should pass response.error."""
        pattern = r"response\.dataType === 'stats'[\s\S]*displayCharacterStats\(response\.data, response\.error\);"
        self.assertRegex(self.source, pattern)


if __name__ == "__main__":
    unittest.main(verbosity=2)
