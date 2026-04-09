#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for tt-spatial-coordinate-grounding."""

import json
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.generators.area_generator import MapLayoutGenerator
from core.generators.location_generator import LocationGenerator
from core.importers.homebrewery_importer import _emit_neq_artifacts
from core.validation.validate_module_files import ModuleValidator
from remediate_module_coordinates import remediate_area_map_pair
from utils.spatial_contract import (
    parse_structured_spatial_response,
    resolve_authored_adjacency,
    resolve_semantic_spatial_plan,
)


class TestSpatialHelperContracts(unittest.TestCase):
    """Shared helper parsing and fail-open behavior."""

    def test_parse_structured_spatial_response_fallback_on_malformed(self):
        payload = parse_structured_spatial_response("not json", ["AAA01", "AAA02"])
        self.assertEqual(payload["coordinates"]["AAA01"], "X10Y10")
        self.assertIn("AAA02", payload["connectivity"]["AAA01"])

    def test_parse_structured_spatial_response_accepts_valid_payload(self):
        payload = parse_structured_spatial_response(
            json.dumps(
                {
                    "coordinates": {
                        "AAA01": "X10Y10",
                        "AAA02": "X10Y11",
                        "AAA03": "X11Y11",
                    },
                    "connectivity": {
                        "AAA01": ["AAA02"],
                        "AAA02": ["AAA01", "AAA03"],
                        "AAA03": ["AAA02"],
                    },
                }
            ),
            ["AAA01", "AAA02", "AAA03"],
        )

        self.assertEqual(payload["coordinates"]["AAA02"], "X10Y11")
        self.assertIn("south", payload["directions"]["AAA01"])
        self.assertEqual(payload["directions"]["AAA01"]["south"], "AAA02")

    def test_resolve_semantic_spatial_plan_uses_directional_hints(self):
        room_records = [
            {
                "id": "AAA01",
                "name": "Entry Hall",
                "description": "A narrow hall with a route to the north.",
                "connections": ["AAA02"],
            },
            {
                "id": "AAA02",
                "name": "Northern Shrine",
                "description": "Ancient shrine in the upper chamber.",
                "connections": ["AAA01"],
            },
        ]

        payload = resolve_semantic_spatial_plan(room_records, use_llm=False)
        self.assertEqual(payload["coordinates"]["AAA01"], "X10Y10")
        self.assertEqual(payload["coordinates"]["AAA02"], "X10Y9")
        self.assertEqual(payload["directions"]["AAA01"].get("north"), "AAA02")


class TestAuthoredAdjacencyExtraction(unittest.TestCase):
    """Deterministic authored adjacency extraction with fallback safeguards."""

    def test_explicit_room_reference_creates_non_sequential_edge(self):
        room_records = [
            {
                "id": "AAA01",
                "name": "Room 1: Entry",
                "description": "A hidden ladder leads to Room 3.",
                "source_room_number": 1,
            },
            {
                "id": "AAA02",
                "name": "Room 2: Storage",
                "description": "Dusty crates and stale air.",
                "source_room_number": 2,
            },
            {
                "id": "AAA03",
                "name": "Room 3: Shrine",
                "description": "The shrine descends back to Room 1.",
                "source_room_number": 3,
            },
        ]
        fallback = {
            "AAA01": ["AAA02"],
            "AAA02": ["AAA01", "AAA03"],
            "AAA03": ["AAA02"],
        }

        adjacency = resolve_authored_adjacency(
            room_records, fallback_connectivity=fallback
        )
        self.assertIn("AAA03", adjacency["AAA01"])
        self.assertIn("AAA01", adjacency["AAA03"])

    def test_directional_cues_can_resolve_target_without_room_number(self):
        room_records = [
            {
                "id": "AAA01",
                "name": "Room 1: Entry",
                "description": "A corridor extends north toward the shrine wing.",
                "source_room_number": 1,
            },
            {
                "id": "AAA02",
                "name": "Room 2: Northern Shrine",
                "description": "Cold incense and cracked altar stone.",
                "source_room_number": 2,
            },
        ]
        fallback = {
            "AAA01": ["AAA02"],
            "AAA02": ["AAA01"],
        }

        adjacency = resolve_authored_adjacency(
            room_records, fallback_connectivity=fallback
        )
        self.assertIn("AAA02", adjacency["AAA01"])

    def test_weak_prose_falls_back_to_safe_connectivity(self):
        room_records = [
            {
                "id": "AAA01",
                "name": "Room 1: Entry",
                "description": "Stone floor.",
                "source_room_number": 1,
            },
            {
                "id": "AAA02",
                "name": "Room 2: Hall",
                "description": "Stone walls.",
                "source_room_number": 2,
            },
        ]
        fallback = {
            "AAA01": ["AAA02"],
            "AAA02": ["AAA01"],
        }

        adjacency = resolve_authored_adjacency(
            room_records, fallback_connectivity=fallback
        )
        self.assertEqual(adjacency["AAA01"], ["AAA02"])
        self.assertEqual(adjacency["AAA02"], ["AAA01"])


class TestSpatialValidatorModes(unittest.TestCase):
    """Strict-new and warn-first legacy validation behavior."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.module_dir = self.temp_dir / "Test_Module"
        (self.module_dir / "areas").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_area_and_map(self, strict_marker: bool) -> None:
        area_data = {
            "areaId": "TST001",
            "areaName": "Test Area",
            "locations": [
                {
                    "locationId": "TST01",
                    "name": "Room One",
                    "description": "Desc",
                    "coordinates": "X10Y10",
                    "connectivity": ["TST02"],
                },
                {
                    "locationId": "TST02",
                    "name": "Room Two",
                    "description": "Desc",
                    "coordinates": "X11Y10",
                    "connectivity": ["TST01"],
                },
            ],
        }
        map_data = {
            "mapName": "Test",
            "mapId": "map_TST001",
            "totalRooms": 2,
            "rooms": [
                {
                    "id": "TST01",
                    "name": "Room One",
                    "connections": ["TST02"],
                    "coordinates": "X10Y10",
                },
                {
                    "id": "TST02",
                    "name": "Room Two",
                    "connections": ["TST01"],
                    "coordinates": "X11Y10",
                },
            ],
            "layout": [["TST01"], ["TST02"]],
        }
        if strict_marker:
            area_data["spatialContractVersion"] = 1
            map_data["spatialContractVersion"] = 1

        with open(
            self.module_dir / "areas" / "TST001.json", "w", encoding="utf-8"
        ) as handle:
            json.dump(area_data, handle)
        with open(self.module_dir / "map_TST001.json", "w", encoding="utf-8") as handle:
            json.dump(map_data, handle)

    def test_legacy_warn_first_for_missing_spatial_fields(self):
        self._write_area_and_map(strict_marker=False)

        validator = ModuleValidator(str(self.module_dir), str(REPO_ROOT))
        validator.load_schemas()
        validator.validate_spatial_contracts()

        self.assertEqual(validator.results["spatial_contract"]["failed"], 0)
        self.assertGreater(
            len(validator.results["spatial_contract_warning"]["errors"]), 0
        )

    def test_strict_fails_when_marker_present_and_fields_missing(self):
        self._write_area_and_map(strict_marker=True)

        validator = ModuleValidator(str(self.module_dir), str(REPO_ROOT))
        validator.load_schemas()
        validator.validate_spatial_contracts()

        self.assertGreater(validator.results["spatial_contract"]["failed"], 0)


class TestSpatialStrictCoherenceValidation(unittest.TestCase):
    """Strict spatial contract coherence checks for geometry and directions."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.module_dir = self.temp_dir / "Test_Module"
        (self.module_dir / "areas").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_area_and_map(
        self,
        room_one_coordinate: str,
        room_two_coordinate: str,
        direction_key: str,
        strict_marker: bool,
    ) -> None:
        area_data = {
            "areaId": "TST001",
            "areaName": "Test Area",
            "locations": [
                {
                    "locationId": "TST01",
                    "name": "Room One",
                    "description": "Desc",
                    "coordinates": room_one_coordinate,
                    "connectivity": ["TST02"],
                    "aliases": ["Room One"],
                    "tactical_grid": ["Open Space"] * 9,
                },
                {
                    "locationId": "TST02",
                    "name": "Room Two",
                    "description": "Desc",
                    "coordinates": room_two_coordinate,
                    "connectivity": ["TST01"],
                    "aliases": ["Room Two"],
                    "tactical_grid": ["Open Space"] * 9,
                },
            ],
        }
        map_data = {
            "mapName": "Test",
            "mapId": "map_TST001",
            "totalRooms": 2,
            "rooms": [
                {
                    "id": "TST01",
                    "name": "Room One",
                    "connections": ["TST02"],
                    "coordinates": room_one_coordinate,
                    "directions": {direction_key: "TST02"},
                },
                {
                    "id": "TST02",
                    "name": "Room Two",
                    "connections": ["TST01"],
                    "coordinates": room_two_coordinate,
                    "directions": {},
                },
            ],
            "layout": [["TST01"], ["TST02"]],
        }
        if strict_marker:
            area_data["spatialContractVersion"] = 1
            map_data["spatialContractVersion"] = 1

        with open(
            self.module_dir / "areas" / "TST001.json", "w", encoding="utf-8"
        ) as handle:
            json.dump(area_data, handle)
        with open(self.module_dir / "map_TST001.json", "w", encoding="utf-8") as handle:
            json.dump(map_data, handle)

    def test_strict_fails_for_non_adjacent_connected_rooms(self):
        self._write_area_and_map(
            room_one_coordinate="X10Y10",
            room_two_coordinate="X14Y10",
            direction_key="east",
            strict_marker=True,
        )

        validator = ModuleValidator(str(self.module_dir), str(REPO_ROOT))
        validator.load_schemas()
        validator.validate_spatial_contracts()

        self.assertGreater(validator.results["spatial_contract"]["failed"], 0)
        error_blob = "\n".join(validator.results["spatial_contract"]["errors"])
        self.assertIn("not cardinally adjacent", error_blob)

    def test_strict_fails_for_direction_coordinate_contradiction(self):
        self._write_area_and_map(
            room_one_coordinate="X10Y10",
            room_two_coordinate="X11Y10",
            direction_key="north",
            strict_marker=True,
        )

        validator = ModuleValidator(str(self.module_dir), str(REPO_ROOT))
        validator.load_schemas()
        validator.validate_spatial_contracts()

        self.assertGreater(validator.results["spatial_contract"]["failed"], 0)
        error_blob = "\n".join(validator.results["spatial_contract"]["errors"])
        self.assertIn("contradicts coordinate delta", error_blob)

    def test_legacy_mode_warns_for_geometry_without_strict_failure(self):
        self._write_area_and_map(
            room_one_coordinate="X10Y10",
            room_two_coordinate="X14Y10",
            direction_key="east",
            strict_marker=False,
        )

        validator = ModuleValidator(str(self.module_dir), str(REPO_ROOT))
        validator.load_schemas()
        validator.validate_spatial_contracts()

        self.assertEqual(validator.results["spatial_contract"]["failed"], 0)
        warning_blob = "\n".join(
            validator.results["spatial_contract_warning"]["errors"]
        )
        self.assertIn("contradicts coordinate delta", warning_blob)


class TestSpatialRemediationContract(unittest.TestCase):
    """Remediation behavior should preserve authored connectivity arrays."""

    def test_remediation_preserves_existing_connectivity(self):
        area_data = {
            "areaId": "TST001",
            "areaName": "Test",
            "locations": [
                {
                    "locationId": "TST01",
                    "name": "Room One",
                    "description": "Desc",
                    "connectivity": ["TST02"],
                },
                {
                    "locationId": "TST02",
                    "name": "Room Two",
                    "description": "Desc",
                    "connectivity": ["TST01"],
                },
            ],
        }
        map_data = {
            "mapName": "Test",
            "mapId": "map_TST001",
            "totalRooms": 2,
            "rooms": [
                {"id": "TST01", "name": "Room One", "connections": ["TST02"]},
                {"id": "TST02", "name": "Room Two", "connections": ["TST01"]},
            ],
            "layout": [["TST01"], ["TST02"]],
        }

        patched_area, patched_map, _ = remediate_area_map_pair(area_data, map_data)
        self.assertEqual(patched_area["locations"][0]["connectivity"], ["TST02"])
        self.assertEqual(patched_area["locations"][1]["connectivity"], ["TST01"])
        self.assertIn("directions", patched_map["rooms"][0])

    def test_remediation_aligns_area_coordinate_to_map_and_preserves_room_fields(self):
        area_data = {
            "areaId": "TST001",
            "areaName": "Test",
            "locations": [
                {
                    "locationId": "TST01",
                    "name": "Room One",
                    "description": "Desc",
                    "coordinates": "X99Y99",
                    "connectivity": ["TST02"],
                },
                {
                    "locationId": "TST02",
                    "name": "Room Two",
                    "description": "Desc",
                    "coordinates": "X98Y98",
                    "connectivity": ["TST01"],
                },
            ],
        }
        map_data = {
            "mapName": "Test",
            "mapId": "map_TST001",
            "totalRooms": 2,
            "rooms": [
                {
                    "id": "TST01",
                    "name": "Room One",
                    "connections": ["TST02"],
                    "coordinates": "X10Y10",
                    "tags": ["hub"],
                },
                {
                    "id": "TST02",
                    "name": "Room Two",
                    "connections": ["TST01"],
                    "coordinates": "X11Y10",
                    "tags": ["dead_end"],
                },
            ],
            "layout": [["TST01"], ["TST02"]],
        }

        patched_area, patched_map, _ = remediate_area_map_pair(area_data, map_data)
        self.assertEqual(patched_area["locations"][0]["coordinates"], "X10Y10")
        self.assertEqual(patched_area["locations"][1]["coordinates"], "X11Y10")
        room_by_id = {room["id"]: room for room in patched_map["rooms"]}
        self.assertEqual(room_by_id["TST01"]["tags"], ["hub"])
        self.assertEqual(room_by_id["TST02"]["tags"], ["dead_end"])

    def test_remediation_overrides_stale_map_connections_from_area_connectivity(self):
        area_data = {
            "areaId": "TST001",
            "areaName": "Test",
            "locations": [
                {
                    "locationId": "TST01",
                    "name": "Room One",
                    "description": "Desc",
                    "connectivity": ["TST02", "TST03"],
                },
                {
                    "locationId": "TST02",
                    "name": "Room Two",
                    "description": "Desc",
                    "connectivity": ["TST01"],
                },
                {
                    "locationId": "TST03",
                    "name": "Room Three",
                    "description": "Desc",
                    "connectivity": ["TST01"],
                },
            ],
        }
        # Deliberately stale/incorrect map connectivity to verify remediation repair.
        map_data = {
            "mapName": "Test",
            "mapId": "map_TST001",
            "totalRooms": 3,
            "rooms": [
                {"id": "TST01", "name": "Room One", "connections": ["TST02"]},
                {
                    "id": "TST02",
                    "name": "Room Two",
                    "connections": ["TST01", "TST03"],
                },
                {"id": "TST03", "name": "Room Three", "connections": []},
            ],
            "layout": [["TST01"], ["TST02"], ["TST03"]],
        }

        _, patched_map, _ = remediate_area_map_pair(area_data, map_data)
        room_by_id = {room["id"]: room for room in patched_map["rooms"]}

        self.assertEqual(room_by_id["TST01"]["connections"], ["TST02", "TST03"])
        self.assertEqual(room_by_id["TST02"]["connections"], ["TST01"])
        self.assertEqual(room_by_id["TST03"]["connections"], ["TST01"])


class _StubLocationGenerator(LocationGenerator):
    """Location generator with deterministic batch payload for regression checks."""

    def generate_location_batch(
        self,
        area_data,
        plot_data,
        module_data,
        location_stubs,
        context,
        excluded_names,
        context_header,
    ):
        return {
            "locations": [
                {
                    "locationId": "TST01",
                    "name": "Northern Entry",
                    "type": "entrance",
                    "description": "The entry archway faces north.",
                    "connectivity": ["TST02"],
                },
                {
                    "locationId": "TST02",
                    "name": "South Cellar",
                    "type": "chamber",
                    "description": "A cellar below the entry.",
                    "connectivity": ["TST01"],
                },
            ]
        }


class TestBuilderAndIngestParity(unittest.TestCase):
    """Builder and ingest should emit matching spatial contract fields."""

    def test_builder_map_generation_emits_coordinates_and_directions(self):
        random.seed(7)
        generator = MapLayoutGenerator()
        map_data = generator.generate_layout(
            num_locations=4,
            prefix="TST",
            area_type="dungeon",
            area_context=None,
        )

        self.assertTrue(map_data.get("rooms"))
        for room in map_data["rooms"]:
            self.assertRegex(room.get("coordinates", ""), r"^X[0-9]+Y[0-9]+$")
            self.assertIsInstance(room.get("directions"), dict)
            for direction_key in room.get("directions", {}).keys():
                self.assertIn(direction_key, {"north", "south", "east", "west"})

    def test_location_generator_postprocess_emits_aliases_and_tactical_grid(self):
        generator = _StubLocationGenerator()
        area_data = {
            "areaId": "TST001",
            "areaName": "Test Area",
            "map": {
                "rooms": [
                    {
                        "id": "TST01",
                        "name": "Northern Entry",
                        "type": "entrance",
                        "connections": ["TST02"],
                        "coordinates": "X10Y10",
                    },
                    {
                        "id": "TST02",
                        "name": "South Cellar",
                        "type": "chamber",
                        "connections": ["TST01"],
                        "coordinates": "X10Y11",
                    },
                ]
            },
            "locations": [],
        }
        payload = generator.generate_locations(area_data, {"plotPoints": []}, {})
        self.assertEqual(len(payload["locations"]), 2)
        for location in payload["locations"]:
            self.assertTrue(location.get("aliases"))
            self.assertEqual(len(location.get("tactical_grid", [])), 9)

    def test_ingest_emits_spatial_contract_fields_matching_builder_shape(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            intermediate = {
                "source": {"title": "Imported Adventure"},
                "module_seed": {"module_description": "Test import."},
                "rooms": [
                    {
                        "name": "North Gate",
                        "description": "The northern gate overlooks a cliff.",
                        "source_room_number": 1,
                        "source_room_title": "Gate",
                    },
                    {
                        "name": "Lower Passage",
                        "description": "A narrow lower passage descends south.",
                        "source_room_number": 2,
                        "source_room_title": "Passage",
                    },
                ],
                "chapters": [],
            }

            _emit_neq_artifacts(temp_dir, "Test_Module", intermediate)

            area_path = temp_dir / "areas" / "TES001.json"
            map_path = temp_dir / "map_TES001.json"
            self.assertTrue(area_path.exists())
            self.assertTrue(map_path.exists())

            area_data = json.loads(area_path.read_text(encoding="utf-8"))
            map_data = json.loads(map_path.read_text(encoding="utf-8"))

            self.assertEqual(area_data.get("spatialContractVersion"), 1)
            self.assertEqual(map_data.get("spatialContractVersion"), 1)

            for location in area_data.get("locations", []):
                self.assertRegex(location.get("coordinates", ""), r"^X[0-9]+Y[0-9]+$")
                self.assertTrue(location.get("aliases"))
                self.assertEqual(len(location.get("tactical_grid", [])), 9)

            for room in map_data.get("rooms", []):
                self.assertRegex(room.get("coordinates", ""), r"^X[0-9]+Y[0-9]+$")
                self.assertIsInstance(room.get("directions"), dict)
                for direction_key in room.get("directions", {}).keys():
                    self.assertIn(direction_key, {"north", "south", "east", "west"})

            validator = ModuleValidator(str(temp_dir), str(REPO_ROOT))
            validator.load_schemas()
            validator.validate_spatial_contracts()
            self.assertEqual(validator.results["spatial_contract"]["failed"], 0)
            self.assertEqual(
                len(validator.results["spatial_contract_warning"]["errors"]),
                0,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_ingest_uses_authored_non_linear_adjacency_when_available(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            intermediate = {
                "source": {"title": "Imported Adventure"},
                "module_seed": {"module_description": "Test import."},
                "rooms": [
                    {
                        "name": "Room 1: Entry Bridge",
                        "description": "A stone bridge leads to Room 3: Shrine of Echoes.",
                        "source_room_number": 1,
                        "source_room_title": "Entry Bridge",
                    },
                    {
                        "name": "Room 2: Archive Hall",
                        "description": "A rusted gate opens to Room 4: Vault Annex.",
                        "source_room_number": 2,
                        "source_room_title": "Archive Hall",
                    },
                    {
                        "name": "Room 3: Shrine of Echoes",
                        "description": "The shrine can be reached from Room 1.",
                        "source_room_number": 3,
                        "source_room_title": "Shrine of Echoes",
                    },
                    {
                        "name": "Room 4: Vault Annex",
                        "description": "The annex links back to Room 2.",
                        "source_room_number": 4,
                        "source_room_title": "Vault Annex",
                    },
                ],
                "chapters": [],
            }

            _emit_neq_artifacts(temp_dir, "Test_Module", intermediate)

            map_path = temp_dir / "map_TES001.json"
            self.assertTrue(map_path.exists())
            map_data = json.loads(map_path.read_text(encoding="utf-8"))
            room_by_id = {room["id"]: room for room in map_data.get("rooms", [])}

            self.assertIn("TES03", room_by_id["TES01"]["connections"])
            self.assertIn("TES04", room_by_id["TES02"]["connections"])
            self.assertNotIn("TES02", room_by_id["TES01"]["connections"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
