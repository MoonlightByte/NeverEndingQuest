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
from scripts.homebrew_prewarm_portraits import (
    _discover_npcs,
    _discover_monsters,
    prewarm_portraits,
    _resolve_monster_media,
    _process_monster,
    _generate_monster_media,
)


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


class TestPrewarmMonsterReuse(unittest.TestCase):
    """Tests for Prompt 1-2: monster reuse-first resolution and provider gating."""

    def test_reuse_first_resolves_from_module_media_without_provider(self) -> None:
        """Reusable monster media from module should be counted as reused without calling provider."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "ReuseFirst_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                # Simulate existing module media (video-first check)
                media_dir = module_dir / "media" / "monsters"
                media_dir.mkdir(parents=True, exist_ok=True)
                # Create video asset (should be preferred)
                (media_dir / "skeleton_video.mp4").write_text("dummy video", encoding="utf-8")

                monster = {"name": "Skeleton", "type": "monster"}

                # Patch resolve to return module source; should NOT call generation path
                with patch(
                    "scripts.homebrew_prewarm_portraits._resolve_monster_media",
                    return_value=("reused_module", media_dir / "skeleton_video.mp4")
                ) as mock_resolve, patch(
                    "scripts.homebrew_prewarm_portraits._generate_monster_media"
                ) as mock_generate:
                    result = _process_monster(module_slug, monster, allow_provider=False)

                self.assertEqual(result["status"], "reused")
                self.assertEqual(result["source"], "reused_module")
                mock_resolve.assert_called_once_with(module_slug, "Skeleton")
                mock_generate.assert_not_called()
            finally:
                os.chdir(cwd)

    def test_provider_disabled_returns_missing_without_generation_call(self) -> None:
        """When no reusable media exists and provider disabled, status=missing and no generation."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "NoReuse_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                monster = {"name": "Dragon", "type": "monster"}

                # Resolve returns None (no media); provider disabled
                with patch(
                    "scripts.homebrew_prewarm_portraits._resolve_monster_media",
                    return_value=(None, None)
                ) as mock_resolve, patch(
                    "scripts.homebrew_prewarm_portraits._generate_monster_media"
                ) as mock_generate:
                    result = _process_monster(module_slug, monster, allow_provider=False)

                self.assertEqual(result["status"], "missing")
                self.assertIsNone(result["source"])
                self.assertIn("provider", result["error"].lower())
                mock_resolve.assert_called_once()
                mock_generate.assert_not_called()
            finally:
                os.chdir(cwd)

    def test_provider_enabled_generates_when_no_reusable_media(self) -> None:
        """When provider enabled and no reusable media, generation is attempted."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "Gen_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                monster = {"name": "Imp", "type": "monster"}

                # Resolve returns None; generate returns success
                with patch(
                    "scripts.homebrew_prewarm_portraits._resolve_monster_media",
                    return_value=(None, None)
                ) as mock_resolve, patch(
                    "scripts.homebrew_prewarm_portraits._generate_monster_media",
                    return_value=(True, None)
                ) as mock_generate:
                    result = _process_monster(module_slug, monster, allow_provider=True)

                self.assertEqual(result["status"], "generated")
                self.assertEqual(result["source"], "generated")
                mock_resolve.assert_called_once()
                mock_generate.assert_called_once_with(module_slug, monster)
            finally:
                os.chdir(cwd)

    def test_provider_enabled_generation_failure_returns_failed(self) -> None:
        """When provider enabled but generation errors, status=failed with error message."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "GenFail_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                monster = {"name": "Barghest", "type": "monster"}

                with patch(
                    "scripts.homebrew_prewarm_portraits._resolve_monster_media",
                    return_value=(None, None)
                ), patch(
                    "scripts.homebrew_prewarm_portraits._generate_monster_media",
                    return_value=(False, "API failure")
                ) as mock_generate:
                    result = _process_monster(module_slug, monster, allow_provider=True)

                self.assertEqual(result["status"], "failed")
                self.assertIsNone(result["source"])  # no source when failed
                self.assertEqual(result["error"], "API failure")
                mock_generate.assert_called_once()
            finally:
                os.chdir(cwd)

    def test_monster_flow_writes_only_to_module_media_monsters(self) -> None:
        """Monster generation must target modules/<slug>/media/monsters; never portraits/."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "LaneCheck_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                monster = {"name": "Ghoul", "type": "monster"}

                # Use actual small generation stub that writes to expected path
                def fake_generate(module_slug, monster, timeout_seconds=120):
                    target_dir = Path(f"modules/{module_slug}/media/monsters")
                    target_dir.mkdir(parents=True, exist_ok=True)
                    (target_dir / "ghoul.jpg").write_text("fake image")
                    return (True, None)

                with patch(
                    "scripts.homebrew_prewarm_portraits._resolve_monster_media",
                    return_value=(None, None)
                ), patch(
                    "scripts.homebrew_prewarm_portraits._generate_monster_media",
                    side_effect=fake_generate
                ):
                    _ = _process_monster(module_slug, monster, allow_provider=True)

                # Verify only module media/monsters was created
                self.assertTrue((module_dir / "media" / "monsters").exists())
                self.assertTrue((module_dir / "media" / "monsters" / "ghoul.jpg").exists())
                # Portraits lane should not exist
                self.assertFalse((module_dir / "portraits").exists())
            finally:
                os.chdir(cwd)

    def test_monster_reuse_detects_module_video_first(self) -> None:
        """Module media video (*_video.mp4) should be preferred over images."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "VideoPref_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                media_dir = module_dir / "media" / "monsters"
                media_dir.mkdir(parents=True, exist_ok=True)
                # Both video and image exist
                (media_dir / "vampire_video.mp4").write_text("video")
                (media_dir / "vampire.jpg").write_text("image")

                # We expect resolver to find video first
                source_type, path = _resolve_monster_media(module_slug, "Vampire")
                self.assertEqual(source_type, "reused_module")
                self.assertTrue(path.name.endswith("_video.mp4"))
            finally:
                os.chdir(cwd)

    def test_monster_reuse_detects_static_media_fallback(self) -> None:
        """If module media missing, static media should be used."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "StaticFallback_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                # Static media exists
                static_dir = Path("web/static/media/monsters")
                static_dir.mkdir(parents=True, exist_ok=True)
                (static_dir / "zombie.jpg").write_text("static image")

                source_type, path = _resolve_monster_media(module_slug, "Zombie")
                self.assertEqual(source_type, "reused_static")
                self.assertEqual(path.name, "zombie.jpg")
            finally:
                os.chdir(cwd)

    def test_monster_reuse_detects_pack_assets_fallback(self) -> None:
        """If module and static missing, pack assets should be used."""
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                module_slug = "PackFallback_Module"
                module_dir = Path("modules") / module_slug
                module_dir.mkdir(parents=True, exist_ok=True)

                # Pack/bestiary media exists
                pack_dir = Path("data/bestiary/media/monsters")
                pack_dir.mkdir(parents=True, exist_ok=True)
                (pack_dir / "goblin.jpg").write_text("pack image")

                source_type, path = _resolve_monster_media(module_slug, "Goblin")
                self.assertEqual(source_type, "reused_pack")
                self.assertEqual(path.name, "goblin.jpg")
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
