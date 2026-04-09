#!/usr/bin/env python3
"""Unit tests for semantic publication probe harness."""

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.module_semantic_probe_harness import run_module_semantic_probes


class TestModuleSemanticProbeHarness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_module(self, slug: str, module_context: dict, module_plot: dict) -> Path:
        module_dir = self.temp_dir / slug
        (module_dir / "areas").mkdir(parents=True, exist_ok=True)
        with open(module_dir / "module_context.json", "w", encoding="utf-8") as handle:
            json.dump(module_context, handle, indent=2)
        with open(module_dir / "module_plot.json", "w", encoding="utf-8") as handle:
            json.dump(module_plot, handle, indent=2)
        return module_dir

    def test_travel_probe_fails_for_unresolved_player_facing_phrase(self):
        module_dir = self._write_module(
            "Probe_A",
            {
                "module_name": "Probe_A",
                "semantic_authority": {
                    "version": "v1",
                    "destination_phrases": {
                        "lintars place": {
                            "status": "unresolved",
                            "sources": [
                                "module_plot.json#plotPoints[PP001].description"
                            ],
                            "player_facing": True,
                            "observed": True,
                            "observation_count": 1,
                            "candidate_location_ids": [],
                        }
                    },
                    "npc_scene_authority": {},
                },
                "continuity": {"cross_module_refs": []},
            },
            {
                "plotPoints": [
                    {
                        "id": "PP001",
                        "location": "LOC08",
                        "description": "The party heads to Lintar's place.",
                    }
                ]
            },
        )

        result = run_module_semantic_probes(module_dir)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any(
                probe.get("failure_class") == "travel_unresolved_destination_phrase"
                for probe in result["probes"]
            )
        )

    def test_travel_probe_fails_for_misrouted_resolved_phrase(self):
        module_dir = self._write_module(
            "Probe_B",
            {
                "module_name": "Probe_B",
                "semantic_authority": {
                    "version": "v1",
                    "destination_phrases": {
                        "main hall": {
                            "status": "resolved",
                            "location_id": "LOC02",
                            "sources": [
                                "module_plot.json#plotPoints[PP002].description"
                            ],
                            "player_facing": True,
                            "observed": True,
                            "observation_count": 1,
                            "candidate_location_ids": ["LOC02"],
                        }
                    },
                    "npc_scene_authority": {},
                },
                "continuity": {"cross_module_refs": []},
            },
            {
                "plotPoints": [
                    {
                        "id": "PP002",
                        "location": "LOC01",
                        "description": "Return to the main hall.",
                    }
                ]
            },
        )

        result = run_module_semantic_probes(module_dir)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any(
                probe.get("failure_class") == "travel_misrouted_destination_phrase"
                for probe in result["probes"]
            )
        )

    def test_handoff_probe_catches_missing_target_module(self):
        module_dir = self._write_module(
            "Probe_C",
            {
                "module_name": "Probe_C",
                "semantic_authority": {
                    "version": "v1",
                    "destination_phrases": {},
                    "npc_scene_authority": {},
                },
                "continuity": {
                    "cross_module_refs": [
                        {
                            "target_module": "Missing_Module",
                            "entity_id": "scout_elen_handoff",
                            "relation": "reference",
                            "notes": "Scout Elen handoff thread links modules.",
                        }
                    ]
                },
            },
            {"plotPoints": []},
        )

        result = run_module_semantic_probes(module_dir)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any(
                probe.get("failure_class") == "handoff_target_module_absent"
                for probe in result["probes"]
            )
        )

    def test_hidden_npc_probe_catches_missing_authority(self):
        module_dir = self._write_module(
            "Probe_D",
            {
                "module_name": "Probe_D",
                "semantic_authority": {
                    "version": "v1",
                    "destination_phrases": {},
                    "npc_scene_authority": {
                        "Father Aldric": {
                            "name_slug": "father aldric",
                            "visible_location_ids": [],
                            "reveal_bindings": [],
                            "sources": ["module_context.json#npcs.father_aldric"],
                            "authored_mentions_count": 1,
                            "authored_mention_sources": [
                                "module_plot.json#plotPoints[PP003].description"
                            ],
                        }
                    },
                },
                "continuity": {"cross_module_refs": []},
            },
            {
                "plotPoints": [
                    {
                        "id": "PP003",
                        "location": "LOC03",
                        "description": "Father Aldric is said to be hiding nearby.",
                    }
                ]
            },
        )

        result = run_module_semantic_probes(module_dir)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any(
                probe.get("failure_class") == "hidden_npc_missing_authority"
                for probe in result["probes"]
            )
        )

    def test_noncritical_fixture_gap_is_degraded_not_fail(self):
        existing_target = self.temp_dir / "Keep_of_Doom"
        existing_target.mkdir(parents=True, exist_ok=True)
        module_dir = self._write_module(
            "Probe_E",
            {
                "module_name": "Probe_E",
                "semantic_authority": {
                    "version": "v1",
                    "destination_phrases": {},
                    "npc_scene_authority": {},
                },
                "continuity": {
                    "cross_module_refs": [
                        {
                            "target_module": "Keep_of_Doom",
                            "entity_id": "scout_elen_handoff",
                            "relation": "reference",
                            "notes": "Scout Elen handoff thread links modules.",
                        }
                    ]
                },
            },
            {"plotPoints": []},
        )

        result = run_module_semantic_probes(module_dir)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["summary"]["fail_count"], 0)
        self.assertGreaterEqual(result["summary"]["degraded_count"], 0)
        self.assertTrue(
            any(
                "travel_probe_fixture_missing" in warning
                or "hidden_npc_probe_fixture_missing" in warning
                or "semantic_authority" in warning
                or "handoff_probe_fixture_missing" in warning
                for warning in result["warnings"]
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
