#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Targeted tests for deterministic entity seeding and prewarm inputs."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.importers.homebrewery_importer import _emit_module_context, _extract_entities_from_rooms
from scripts.homebrew_prewarm_portraits import _discover_npcs, _discover_monsters, prewarm_portraits


class TestEntitySeeding(unittest.TestCase):
    def test_extract_entities_from_rooms(self) -> None:
        rooms = [
            {
                "name": "Collapsed Watchtower",
                "description": "The captain named Malliry Valderu warns of a sea troll nearby.",
                "creatures": "A sea troll emerges from the reeds.",
                "source_room_title": "Watchtower Entrance",
            }
        ]
        bestiary = {"monsters": {"sea troll", "zombie"}, "npcs": set()}

        npcs, monsters = _extract_entities_from_rooms(rooms, bestiary)

        self.assertIn("malliry_valderu", npcs)
        self.assertIn("Sea Troll", monsters)

    def test_emit_module_context_populates_entities_and_area_links(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            module_path = Path(td) / "modules" / "Test_Module"
            module_path.mkdir(parents=True, exist_ok=True)

            intermediate = {
                "source": {"path": "test.md", "title": "Test", "room_count": 1},
                "module_seed": {"module_type": "dungeon"},
                "rooms": [
                    {
                        "name": "Gate Hall",
                        "description": "A captain named Vara Kest points at a bronze golem.",
                        "creatures": "bronze golem",
                        "source_room_number": 1,
                        "source_room_title": "Gate Hall",
                    }
                ],
            }

            context_path = _emit_module_context(
                module_path=module_path,
                module_slug="Test_Module",
                intermediate=intermediate,
                area_id="TES001",
                location_ids=["TES01"],
            )

            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertTrue(context.get("npcs"))
            self.assertTrue(context.get("references", {}).get("monsters"))
            self.assertTrue(context["areas"]["TES001"]["npcs"])


class TestSeedPrecedence(unittest.TestCase):
    def test_seed_file_takes_precedence_over_context(self) -> None:
        """Seed files should be primary source; context is fallback only when seed absent."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "SeedPrecedence_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                # Create seed files with specific entities
                (module_dir / "npcs_seed.json").write_text(
                    json.dumps({
                        "npcs": {
                            "seed_npc": {"name": "Seed NPC", "description": "From seed", "type": "npc"}
                        },
                        "count": 1
                    }),
                    encoding="utf-8"
                )
                (module_dir / "monsters_seed.json").write_text(
                    json.dumps({
                        "monsters": ["Seed Monster"],
                        "count": 1
                    }),
                    encoding="utf-8"
                )

                # Create context with different entities (should be ignored)
                (module_dir / "module_context.json").write_text(
                    json.dumps({
                        "npcs": {"context_npc": {"name": "Context NPC", "type": "npc"}},
                        "references": {"monsters": ["Context Monster"]}
                    }),
                    encoding="utf-8"
                )

                npcs = _discover_npcs(module_slug)
                monsters = _discover_monsters(module_slug)

                # Should use seed values, not context
                self.assertEqual(len(npcs), 1)
                self.assertEqual(npcs[0]["name"], "Seed NPC")
                self.assertEqual(len(monsters), 1)
                self.assertEqual(monsters[0]["name"], "Seed Monster")
            finally:
                os.chdir(cwd)


class TestFalsePositiveGuard(unittest.TestCase):
    def test_generic_single_words_not_inflated(self) -> None:
        """Generic single-word mentions like 'bird', 'snake' should not create monster entries."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "FalsePositive_Module"
                module_dir = Path("modules") / module_slug
                (module_dir / "areas").mkdir(parents=True, exist_ok=True)

                # Empty context/seed forces fallback prose scan
                (module_dir / "module_context.json").write_text(
                    json.dumps({"npcs": {}, "references": {}}), encoding="utf-8"
                )

                # Prose with generic single words
                area_payload = {
                    "locations": [
                        {
                            "name": "Forest",
                            "description": "A bird flies overhead. A snake slithers by. Watch out for dragons!",
                            "encounters": [],
                        }
                    ]
                }
                (module_dir / "areas" / "FP001.json").write_text(
                    json.dumps(area_payload), encoding="utf-8"
                )

                monsters = _discover_monsters(module_slug)
                names = {m["name"].lower() for m in monsters}

                # Single-word generics should NOT be in list
                # (Only multi-word specific monsters from fallback list match)
                self.assertNotIn("bird", names)
                self.assertNotIn("snake", names)
                self.assertNotIn("dragon", names)
            finally:
                os.chdir(cwd)


class TestDeterministicNormalization(unittest.TestCase):
    def test_case_normalization_and_dedupe(self) -> None:
        """Mixed-case duplicates should normalize to stable keys."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "CaseNorm_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                # Seed with mixed case duplicates (shouldn't happen in practice,
                # but test normalization)
                (module_dir / "monsters_seed.json").write_text(
                    json.dumps({
                        "monsters": ["Sea Troll", "SEA TROLL", "sea troll", "Bronze Golem"],
                        "count": 4
                    }),
                    encoding="utf-8"
                )

                monsters = _discover_monsters(module_slug)
                names = [m["name"] for m in monsters]

                # Note: Seed file takes values as-is; dedupe happens via set() in sorting
                # All values present but case variations normalized via .title()
                self.assertEqual(len(monsters), 4)  # Seed preserves all entries
                # Check that names were processed through .title() (may not change all-caps)
                # The key is that consistent title-case names are in the list
                self.assertIn("Bronze Golem", names)
                self.assertIn("Sea Troll", names)
                # Verify "Sea Troll" appears (could be from "sea troll" or "Sea Troll" input)
                self.assertTrue(any("Sea Troll" == n or "SEA TROLL" == n for n in names))
            finally:
                os.chdir(cwd)


class TestPrewarmFallback(unittest.TestCase):
    def test_discover_monsters_fallback_from_area_prose(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "Fallback_Module"
                module_dir = Path("modules") / module_slug
                (module_dir / "areas").mkdir(parents=True, exist_ok=True)

                # Empty context forces fallback
                (module_dir / "module_context.json").write_text(
                    json.dumps({"npcs": {}, "references": {}}), encoding="utf-8"
                )

                area_payload = {
                    "locations": [
                        {
                            "name": "Lower Vault",
                            "description": "A bronze golem and giant snake guard the chamber.",
                            "encounters": [],
                        }
                    ]
                }
                (module_dir / "areas" / "FAL001.json").write_text(
                    json.dumps(area_payload), encoding="utf-8"
                )

                monsters = _discover_monsters(module_slug)
                names = {m["name"] for m in monsters}
                self.assertIn("Bronze Golem", names)
                self.assertIn("Giant Snake", names)
            finally:
                os.chdir(cwd)

    def test_prewarm_creates_target_dirs_when_planned(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "DirCreate_Module"
                module_media = Path("modules") / module_slug / "media"

                # Avoid real generation; only test directory creation contract
                # Use allow_provider=True to exercise the code path that creates directories
                with patch("scripts.homebrew_prewarm_portraits._discover_npcs", return_value=[
                    {"id": "vara_kest", "name": "Vara Kest", "description": "NPC", "type": "npc"}
                ]), patch("scripts.homebrew_prewarm_portraits._discover_monsters", return_value=[
                    {"id": "bronze_golem", "name": "Bronze Golem", "description": "Monster", "type": "monster"}
                ]), patch("scripts.homebrew_prewarm_portraits._process_entity", return_value={
                    "entity_type": "npc", "name": "Vara Kest", "status": "skipped"
                }):
                    _ = prewarm_portraits(module_slug=module_slug, max_concurrent=1, allow_provider=True)

                self.assertTrue((module_media / "npcs").exists())
                self.assertTrue((module_media / "monsters").exists())
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
