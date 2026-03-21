# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Party member auto-register normalization tests.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updates.update_character_info import (  # noqa: E402
    _dedupe_party_member_names,
    normalize_character_name,
)


class TestPartyMemberAutoRegisterNormalization(unittest.TestCase):
    """Runtime coverage for canonical party member dedupe behavior."""

    def test_dedupe_party_member_names_preserves_first_label(self):
        """Mixed-form variants collapse to one logical entry with first label preserved."""
        party_members = [
            "Xorn",
            "Redax",
            "Athelon",
            "Lidda Underbough",
            "xorn",
            "athelon",
            "lidda_underbough",
        ]

        deduped = _dedupe_party_member_names(party_members)
        self.assertEqual(deduped, ["Xorn", "Redax", "Athelon", "Lidda Underbough"])

    def test_autoregister_logic_does_not_append_duplicate_normalized_member(self):
        """Auto-register check should not append when normalized identity already exists."""
        initial_party_members = ["Xorn", "Redax", "xorn"]

        party_members = _dedupe_party_member_names(initial_party_members)
        display_name = "xorn"
        normalized_display = normalize_character_name(display_name)
        existing_normalized = {normalize_character_name(member) for member in party_members}

        if normalized_display and normalized_display not in existing_normalized:
            party_members.append(display_name)

        final_members = _dedupe_party_member_names(party_members)
        self.assertEqual(final_members, ["Xorn", "Redax"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
