#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for module-authorized monster hydration."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.module_monster_authority import (
    authorize_module_monster,
    materialize_authorized_monster_file,
)


class TestModuleMonsterAuthority(unittest.TestCase):
    def test_night_cultist_is_authorized_from_authored_module_content(self):
        result = authorize_module_monster("Night_of_the_Restless_Dead", "Cultist")
        self.assertTrue(result["authorized"])
        self.assertEqual(result["slug"], "cultist")
        self.assertTrue(result["sources"])

    def test_night_cult_fanatic_is_not_authorized(self):
        result = authorize_module_monster("Night_of_the_Restless_Dead", "Cult Fanatic")
        self.assertFalse(result["authorized"])
        self.assertEqual(result["slug"], "cult_fanatic")

    def test_unauthorized_monster_fails_closed_without_hydration(self):
        with patch("utils.module_monster_authority.find_reusable_monster_path") as mock_reuse, \
             patch("utils.module_monster_authority.subprocess.run") as mock_run:
            result = materialize_authorized_monster_file(
                "Night_of_the_Restless_Dead",
                "Cult Fanatic",
                "core/generators/monster_builder.py",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_class"], "unauthorized_monster_reference")
        mock_reuse.assert_not_called()
        mock_run.assert_not_called()

    def test_authorized_missing_monster_attempts_builder_hydration(self):
        builder_calls = []

        def _record_builder(args, capture_output, text):
            builder_calls.append(args)
            return SimpleNamespace(returncode=1, stdout="", stderr="builder failed")

        with patch("utils.module_monster_authority.find_reusable_monster_path", return_value=None), \
             patch("utils.module_monster_authority.subprocess.run", side_effect=_record_builder):
            result = materialize_authorized_monster_file(
                "Night_of_the_Restless_Dead",
                "Cultist",
                "core/generators/monster_builder.py",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_class"], "authorized_monster_hydration_failed")
        self.assertEqual(builder_calls[0][0], sys.executable)
        self.assertIn("--module", builder_calls[0])
        self.assertIn("Night_of_the_Restless_Dead", builder_calls[0])


class TestCombatBuilderSourceContracts(unittest.TestCase):
    def test_combat_builder_uses_authorized_materialization_helper(self):
        file_path = os.path.join(PROJECT_ROOT, "core", "generators", "combat_builder.py")
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("from utils.module_monster_authority import materialize_authorized_monster_file", source)
        self.assertIn("resolution_result = materialize_authorized_monster_file(", source)
        self.assertIn("error_class = resolution_result.get(\"error_class\"", source)
        self.assertIn("error_message = resolution_result.get(\"error_message\"", source)

    def test_action_handler_surfaces_new_monster_failure_classes(self):
        file_path = os.path.join(PROJECT_ROOT, "core", "ai", "action_handler.py")
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("unauthorized_monster_reference", source)
        self.assertIn("authorized_monster_hydration_failed", source)
        self.assertIn("authored module content", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
