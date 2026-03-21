#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for authored hidden-NPC validation context."""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestHiddenNPCValidationContext(unittest.TestCase):
    def test_extract_hidden_npcs_from_location_finds_father_aldric(self):
        from core.ai.build_npc_context import extract_hidden_npcs_from_location
        from utils.file_operations import safe_read_json

        area_path = os.path.join(
            PROJECT_ROOT,
            "modules",
            "Night_of_the_Restless_Dead",
            "areas",
            "NIG001.json",
        )
        area_data = safe_read_json(area_path)
        nigr4 = next(loc for loc in area_data["locations"] if loc.get("locationId") == "NIG04")

        hidden_npcs = extract_hidden_npcs_from_location(nigr4)
        self.assertIn("Father Aldric", hidden_npcs)

    def test_build_npc_validation_context_marks_hidden_priest_present(self):
        from core.ai.build_npc_context import build_npc_validation_context

        context = build_npc_validation_context(
            current_module="Night_of_the_Restless_Dead",
            current_location="NIG04",
            party_npcs=[],
        )
        self.assertIn("@CURRENT_LOC[NIG04]: Father Aldric", context)

    def test_main_validation_context_documents_hidden_npc_rule(self):
        main_path = os.path.join(PROJECT_ROOT, "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn(
            "Hidden or revealable authored NPC identities from current-location investigation hooks count as PRESENT",
            source,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
