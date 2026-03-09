#!/usr/bin/env python3
"""Unit tests for continuity cross-module reference enrichment."""

from __future__ import annotations

import unittest

from continuity_cross_ref_enrichment import enrich_continuity_cross_refs


class TestContinuityCrossRefEnrichment(unittest.TestCase):
    def test_adds_refs_when_target_module_is_mentioned(self) -> None:
        module_context = {
            "module_name": "Night_of_the_Restless_Dead",
            "continuity": {
                "continuity_version": "v1",
                "entry_state_variants": {
                    "cold_start": {"summary": "x"},
                    "partial_context": {"summary": "y"},
                    "late_arc": {"summary": "z"},
                },
                "cross_module_refs": [],
                "standalone_fallback": {"enabled": True},
            },
            "faction_context": {
                "notes": "Miriam fears the Pumpkin King and seeks Thornwood druid lore."
            },
        }
        module_plot = {"summary": "Party learns Bramble ties and old debt."}

        result = enrich_continuity_cross_refs(
            module_slug="Night_of_the_Restless_Dead",
            module_context=module_context,
            module_plot=module_plot,
            known_modules=[
                "Night_of_the_Restless_Dead",
                "The_Pumpkin_Kings_Curse",
                "The_Thornwood_Watch",
            ],
        )

        self.assertTrue(result["changed"])
        refs = result["module_context"]["continuity"]["cross_module_refs"]
        targets = {row["target_module"] for row in refs}
        self.assertIn("The_Pumpkin_Kings_Curse", targets)
        self.assertIn("The_Thornwood_Watch", targets)

    def test_does_not_duplicate_existing_ref(self) -> None:
        module_context = {
            "module_name": "Keep_of_Doom",
            "continuity": {
                "cross_module_refs": [
                    {
                        "target_module": "The_Thornwood_Watch",
                        "entity_id": "scout_elen",
                        "relation": "reference",
                        "confidence": "high",
                    }
                ]
            },
            "narrative": "Travel from Thornwood to Harrow's Hollow.",
        }

        result = enrich_continuity_cross_refs(
            module_slug="Keep_of_Doom",
            module_context=module_context,
            module_plot={},
            known_modules=["Keep_of_Doom", "The_Thornwood_Watch"],
        )

        refs = result["module_context"]["continuity"]["cross_module_refs"]
        matching = [
            row
            for row in refs
            if row.get("target_module") == "The_Thornwood_Watch"
            and row.get("entity_id") == "scout_elen"
            and row.get("relation") == "reference"
        ]
        self.assertEqual(len(matching), 1)

    def test_no_change_when_no_mentions(self) -> None:
        module_context = {
            "module_name": "Keep_of_Doom",
            "continuity": {"cross_module_refs": []},
            "notes": "Standalone haunted keep story with no external references.",
        }

        result = enrich_continuity_cross_refs(
            module_slug="Keep_of_Doom",
            module_context=module_context,
            module_plot={},
            known_modules=["Keep_of_Doom", "Night_of_the_Restless_Dead"],
        )

        self.assertFalse(result["changed"])
        self.assertEqual(result["final_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
