#!/usr/bin/env python3
"""Unit tests for semantic authority enrichment and audit tooling."""

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.module_semantic_authority_audit import audit_module_semantic_authority
from utils.module_semantic_authority import enrich_module_semantic_authority


class TestModuleSemanticAuthority(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_module(
        self,
        module_slug: str,
        locations: list,
        context_npcs: dict | None = None,
        plot_points: list | None = None,
    ) -> Path:
        module_dir = self.temp_dir / module_slug
        (module_dir / "areas").mkdir(parents=True, exist_ok=True)

        area_payload = {
            "areaId": "TST001",
            "areaName": "Test Area",
            "locations": locations,
        }
        with open(
            module_dir / "areas" / "TST001.json", "w", encoding="utf-8"
        ) as handle:
            json.dump(area_payload, handle, indent=2)

        module_context = {
            "module_name": module_slug,
            "module_id": module_slug,
            "npcs": context_npcs or {},
        }
        with open(module_dir / "module_context.json", "w", encoding="utf-8") as handle:
            json.dump(module_context, handle, indent=2)

        module_plot = {
            "plotTitle": "Test Plot",
            "mainObjective": "Test objective",
            "plotPoints": plot_points or [],
        }
        with open(module_dir / "module_plot.json", "w", encoding="utf-8") as handle:
            json.dump(module_plot, handle, indent=2)

        return module_dir

    def test_alias_normalization_resolves_title_variants(self):
        module_dir = self._create_module(
            module_slug="Semantic_Test_A",
            locations=[
                {
                    "locationId": "LOC01",
                    "name": "Brother Lintar's Place",
                    "source_room_title": "Room 8: Brother Lintar's Place",
                    "aliases": ["The Priest's Lodging"],
                    "npcs": [],
                }
            ],
        )

        module_context = json.loads(
            (module_dir / "module_context.json").read_text(encoding="utf-8")
        )
        module_plot = json.loads(
            (module_dir / "module_plot.json").read_text(encoding="utf-8")
        )

        result = enrich_module_semantic_authority(
            module_slug="Semantic_Test_A",
            module_context=module_context,
            module_plot=module_plot,
            module_dir=module_dir,
        )

        self.assertIn(result["status"], {"success", "degraded"})
        payload = result["semantic_authority"]
        aliases = payload["location_aliases"]

        self.assertIn("brother lintars place", aliases)
        self.assertIn("lintars place", aliases)
        self.assertIn("priests lodging", aliases)
        self.assertEqual(aliases["lintars place"]["location_id"], "LOC01")

    def test_destination_phrase_ambiguity_is_recorded(self):
        module_dir = self._create_module(
            module_slug="Semantic_Test_B",
            locations=[
                {
                    "locationId": "LOC01",
                    "name": "North Hall",
                    "aliases": ["Main Hall"],
                    "npcs": [],
                },
                {
                    "locationId": "LOC02",
                    "name": "South Hall",
                    "aliases": ["Main Hall"],
                    "npcs": [],
                },
            ],
            plot_points=[
                {
                    "id": "PP001",
                    "title": "Test",
                    "description": "Return to the main hall.",
                    "location": "LOC01",
                }
            ],
        )

        module_context = json.loads(
            (module_dir / "module_context.json").read_text(encoding="utf-8")
        )
        module_plot = json.loads(
            (module_dir / "module_plot.json").read_text(encoding="utf-8")
        )

        result = enrich_module_semantic_authority(
            module_slug="Semantic_Test_B",
            module_context=module_context,
            module_plot=module_plot,
            module_dir=module_dir,
        )

        payload = result["semantic_authority"]
        phrases = payload["destination_phrases"]
        diagnostics = payload["diagnostics"]

        self.assertEqual(phrases["main hall"]["status"], "ambiguous")
        self.assertEqual(
            sorted(phrases["main hall"]["candidate_location_ids"]),
            ["LOC01", "LOC02"],
        )
        self.assertTrue(
            any(
                item.get("phrase") == "main hall"
                for item in diagnostics["ambiguous_destination_phrases"]
            )
        )

    def test_visible_and_revealable_npc_authority_is_derived(self):
        module_dir = self._create_module(
            module_slug="Semantic_Test_C",
            locations=[
                {
                    "locationId": "LOC01",
                    "name": "Brother Lintar's Place",
                    "description": "Brother Lintar keeps watch.",
                    "aliases": ["Lintar's Place"],
                    "npcs": [{"name": "Brother Lintar"}],
                },
                {
                    "locationId": "LOC02",
                    "name": "Priest's Lodging",
                    "description": "Father Aldric quietly warns the party in the dark.",
                    "aliases": ["Priest's Lodging"],
                    "npcs": [],
                },
            ],
            context_npcs={
                "brother_lintar": {"name": "Brother Lintar"},
                "father_aldric": {"name": "Father Aldric"},
            },
        )

        module_context = json.loads(
            (module_dir / "module_context.json").read_text(encoding="utf-8")
        )
        module_plot = json.loads(
            (module_dir / "module_plot.json").read_text(encoding="utf-8")
        )

        result = enrich_module_semantic_authority(
            module_slug="Semantic_Test_C",
            module_context=module_context,
            module_plot=module_plot,
            module_dir=module_dir,
        )

        payload = result["semantic_authority"]
        npc_map = payload["npc_scene_authority"]
        diagnostics = payload["diagnostics"]

        self.assertIn("Brother Lintar", npc_map)
        self.assertEqual(npc_map["Brother Lintar"]["visible_location_ids"], ["LOC01"])

        self.assertIn("Father Aldric", npc_map)
        self.assertEqual(npc_map["Father Aldric"]["visible_location_ids"], [])
        self.assertTrue(
            any(
                binding.get("location_id") == "LOC02"
                for binding in npc_map["Father Aldric"]["reveal_bindings"]
            )
        )
        self.assertFalse(
            any(
                item.get("npc") == "Father Aldric"
                for item in diagnostics["missing_npc_authority"]
            )
        )

    def test_missing_npc_authority_is_diagnostic_not_hard_failure(self):
        module_dir = self._create_module(
            module_slug="Semantic_Test_D",
            locations=[
                {
                    "locationId": "LOC01",
                    "name": "Entry Hall",
                    "description": "A quiet entry room.",
                    "aliases": ["Entry Hall"],
                    "npcs": [],
                }
            ],
            context_npcs={
                "hidden_priest": {"name": "Hidden Priest"},
            },
        )

        module_context = json.loads(
            (module_dir / "module_context.json").read_text(encoding="utf-8")
        )
        module_plot = json.loads(
            (module_dir / "module_plot.json").read_text(encoding="utf-8")
        )

        result = enrich_module_semantic_authority(
            module_slug="Semantic_Test_D",
            module_context=module_context,
            module_plot=module_plot,
            module_dir=module_dir,
        )

        self.assertEqual(result["status"], "degraded")
        missing = result["semantic_authority"]["diagnostics"]["missing_npc_authority"]
        self.assertTrue(any(item.get("npc") == "Hidden Priest" for item in missing))

    def test_evocative_prose_phrase_is_not_promoted_to_destination_authority(self):
        module_dir = self._create_module(
            module_slug="Semantic_Test_E",
            locations=[
                {
                    "locationId": "LOC01",
                    "name": "Outer Gate",
                    "description": "The party must find sanctuary before nightfall.",
                    "aliases": ["Gate"],
                    "npcs": [],
                }
            ],
            plot_points=[
                {
                    "id": "PP009",
                    "title": "Regroup",
                    "description": "The party must find sanctuary in the next hall.",
                    "location": "LOC01",
                }
            ],
        )

        module_context = json.loads(
            (module_dir / "module_context.json").read_text(encoding="utf-8")
        )
        module_plot = json.loads(
            (module_dir / "module_plot.json").read_text(encoding="utf-8")
        )

        result = enrich_module_semantic_authority(
            module_slug="Semantic_Test_E",
            module_context=module_context,
            module_plot=module_plot,
            module_dir=module_dir,
        )

        phrases = result["semantic_authority"]["destination_phrases"]
        self.assertNotIn("find sanctuary", phrases)
        self.assertNotIn("next hall", phrases)


class TestModuleSemanticAuthorityAudit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_module_context(self, slug: str, semantic_authority: dict) -> Path:
        module_dir = self.temp_dir / slug
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "areas").mkdir(exist_ok=True)
        with open(module_dir / "module_context.json", "w", encoding="utf-8") as handle:
            json.dump(
                {"module_name": slug, "semantic_authority": semantic_authority},
                handle,
                indent=2,
            )
        return module_dir

    def test_audit_degrades_on_weak_semantic_authority(self):
        payload = {
            "version": "v1",
            "location_aliases": {
                "priests lodging": {
                    "status": "resolved",
                    "location_id": "NIG04",
                    "candidate_location_ids": ["NIG04"],
                    "sources": ["areas/NIG001.json#locations[NIG04].name"],
                }
            },
            "destination_phrases": {
                "lintars place": {
                    "status": "unresolved",
                    "candidate_location_ids": [],
                    "sources": ["module_plot.json#plotPoints[PP008].description"],
                }
            },
            "npc_scene_authority": {
                "Father Aldric": {
                    "name_slug": "father aldric",
                    "visible_location_ids": [],
                    "reveal_bindings": [],
                    "sources": ["module_context.json#npcs.father_aldric"],
                }
            },
            "diagnostics": {
                "duplicate_location_aliases": [],
                "ambiguous_destination_phrases": [],
                "unresolved_destination_phrases": [{"phrase": "lintars place"}],
                "missing_npc_authority": [{"npc": "Father Aldric"}],
            },
        }
        module_dir = self._write_module_context("Semantic_Audit_A", payload)

        result = audit_module_semantic_authority(module_dir)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["exit_code"], 0)
        self.assertGreater(len(result["warnings"]), 0)

    def test_audit_fails_on_contradictory_status_shape(self):
        payload = {
            "version": "v1",
            "location_aliases": {
                "main hall": {
                    "status": "resolved",
                    "location_id": "LOC01",
                    "candidate_location_ids": ["LOC01"],
                    "sources": ["areas/TST001.json#locations[LOC01].aliases"],
                }
            },
            "destination_phrases": {
                "main hall": {
                    "status": "resolved",
                    "location_id": "LOC01",
                    "candidate_location_ids": ["LOC01", "LOC02"],
                    "sources": ["module_plot.json#plotPoints[PP001].description"],
                }
            },
            "npc_scene_authority": {
                "Brother Lintar": {
                    "name_slug": "brother lintar",
                    "visible_location_ids": ["LOC01"],
                    "reveal_bindings": [],
                    "sources": ["areas/TST001.json#locations[LOC01].npcs"],
                }
            },
            "diagnostics": {
                "duplicate_location_aliases": [],
                "ambiguous_destination_phrases": [],
                "unresolved_destination_phrases": [],
                "missing_npc_authority": [],
            },
        }
        module_dir = self._write_module_context("Semantic_Audit_B", payload)

        result = audit_module_semantic_authority(module_dir)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["exit_code"], 1)
        self.assertTrue(
            any(
                "candidate_location_ids count is 2" in item
                for item in result["blocking_errors"]
            )
        )

    def test_unresolved_player_facing_destination_phrase_fails(self):
        payload = {
            "version": "v1",
            "location_aliases": {
                "priests lodging": {
                    "status": "resolved",
                    "location_id": "NIG04",
                    "candidate_location_ids": ["NIG04"],
                    "sources": ["areas/NIG001.json#locations[NIG04].name"],
                }
            },
            "destination_phrases": {
                "lintars place": {
                    "status": "unresolved",
                    "candidate_location_ids": [],
                    "sources": ["module_plot.json#plotPoints[PP008].description"],
                    "player_facing": True,
                    "observed": True,
                    "observation_count": 1,
                }
            },
            "npc_scene_authority": {
                "Brother Lintar": {
                    "name_slug": "brother lintar",
                    "visible_location_ids": ["NIG08"],
                    "reveal_bindings": [],
                    "sources": ["areas/NIG001.json#locations[NIG08].npcs"],
                    "authored_mentions_count": 1,
                    "authored_mention_sources": [
                        "areas/NIG001.json#locations[NIG08].description"
                    ],
                }
            },
            "diagnostics": {
                "duplicate_location_aliases": [],
                "ambiguous_destination_phrases": [],
                "unresolved_destination_phrases": [
                    {"phrase": "lintars place", "player_facing": True}
                ],
                "missing_npc_authority": [],
            },
        }
        module_dir = self._write_module_context("Semantic_Audit_C", payload)

        result = audit_module_semantic_authority(module_dir)
        self.assertEqual(result["status"], "fail")
        self.assertIn("phase2_ambiguity_debt", result["blocker_classes"])

    def test_missing_npc_authority_with_authored_presence_fails(self):
        payload = {
            "version": "v1",
            "location_aliases": {},
            "destination_phrases": {},
            "npc_scene_authority": {
                "Father Aldric": {
                    "name_slug": "father aldric",
                    "visible_location_ids": [],
                    "reveal_bindings": [],
                    "sources": ["module_context.json#npcs.father_aldric"],
                    "authored_mentions_count": 2,
                    "authored_mention_sources": [
                        "module_plot.json#plotPoints[PP004].description",
                        "areas/NIG001.json#locations[NIG04].description",
                    ],
                }
            },
            "diagnostics": {
                "duplicate_location_aliases": [],
                "ambiguous_destination_phrases": [],
                "unresolved_destination_phrases": [],
                "missing_npc_authority": [
                    {"npc": "Father Aldric", "authored_mentions_count": 2}
                ],
            },
        }
        module_dir = self._write_module_context("Semantic_Audit_D", payload)

        result = audit_module_semantic_authority(module_dir)
        self.assertEqual(result["status"], "fail")
        self.assertIn("missing_npc_scene_authority", result["blocker_classes"])

    def test_non_player_facing_ambiguous_phrase_is_warning_only(self):
        payload = {
            "version": "v1",
            "location_aliases": {
                "main hall": {
                    "status": "ambiguous",
                    "candidate_location_ids": ["LOC01", "LOC02"],
                    "sources": ["areas/TST001.json#locations[LOC01].aliases"],
                }
            },
            "destination_phrases": {
                "main hall": {
                    "status": "ambiguous",
                    "candidate_location_ids": ["LOC01", "LOC02"],
                    "sources": ["areas/TST001.json#locations[LOC01].aliases"],
                    "player_facing": False,
                    "observed": False,
                    "observation_count": 0,
                }
            },
            "npc_scene_authority": {},
            "diagnostics": {
                "duplicate_location_aliases": [],
                "ambiguous_destination_phrases": [
                    {
                        "phrase": "main hall",
                        "candidate_location_ids": ["LOC01", "LOC02"],
                        "player_facing": False,
                    }
                ],
                "unresolved_destination_phrases": [],
                "missing_npc_authority": [],
            },
        }
        module_dir = self._write_module_context("Semantic_Audit_E", payload)

        result = audit_module_semantic_authority(module_dir)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["exit_code"], 0)
        self.assertNotIn("ambiguous_destination_phrase", result["blocker_classes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
