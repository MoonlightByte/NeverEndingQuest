# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Community Tools - Validate Module Files
Copyright (c) 2024 MoonlightByte
Licensed under Apache License 2.0

See LICENSE-APACHE file for full terms.
"""

#!/usr/bin/env python3
"""
Comprehensive Module File Validation Script

This script validates all game files in a module directory against their corresponding schemas.
It provides detailed reporting on validation passes, failures, and missing schemas.

Supports module-centric architecture for 5th edition content validation.
Portions derived from SRD 5.2.1, licensed under CC BY 4.0.
"""

import json
import os
import re
from pathlib import Path
from jsonschema import validate, ValidationError, Draft7Validator
from collections import defaultdict
from datetime import datetime
import sys

from utils.character_sheet_contract import repair_required_ammunition_field


class ModuleValidator:
    """Validates all module files against their schemas"""
    
    def __init__(self, module_path, schema_dir):
        self.module_path = Path(module_path)
        self.schema_dir = Path(schema_dir)
        self.results = defaultdict(lambda: {"files": [], "passed": 0, "failed": 0, "errors": []})
        self.schemas = {}
        self.encounter_creatures_checked = 0
        
    def load_schemas(self, strict: bool = False):
        """Load all available schemas.

        VAL-C2: When strict=True, the area schema is swapped for
        `locationfile_schema_strict.json`, which composes the top-level
        wrapper requirements from `locationfile_schema.json`
        (areaName/areaId/locations) with the full per-location
        requirements from `loca_schema.json` (all 21 location fields).
        This catches omissions (e.g. a missing `doors` array) that the
        legacy 3-field schema silently allowed.

        Default strict=False preserves backward compatibility with
        existing callers; only new entry points (e.g. module_stitcher's
        post-generation validation) opt in.
        """
        area_schema = (
            "locationfile_schema_strict.json" if strict
            else "locationfile_schema.json"
        )
        schema_mappings = {
            "module": "module_schema.json",
            "area": area_schema,  # VAL-C2: strict swaps in composed schema
            "character": "char_schema.json",
            "monster": "mon_schema.json",  # Monsters have their own schema
            "map": "map_schema.json",
            "plot": "plot_schema.json",
            "party": "party_schema.json",
            "encounter": "encounter_schema.json",
            "plan": "plan_schema.json",
            "journal": "journal_schema.json",
            "random_encounter": "random_encounter_schema.json"
        }
        
        print("Loading schemas...")
        for file_type, schema_file in schema_mappings.items():
            schema_path = self.schema_dir / schema_file
            if schema_path.exists():
                try:
                    with open(schema_path, 'r') as f:
                        self.schemas[file_type] = json.load(f)
                    print(f"  [OK] Loaded {file_type} schema from {schema_file}")
                except Exception as e:
                    print(f"  [ERROR] Failed to load {file_type} schema: {e}")
            else:
                print(f"  - Schema not found: {schema_file}")
                
    def validate_file(self, file_path, schema_type):
        """Validate a single file against its schema"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            if schema_type not in self.schemas:
                return False, f"No schema available for type: {schema_type}"

            if schema_type == "character" and isinstance(data, dict):
                data, _ = repair_required_ammunition_field(data)
                
            # Create validator to get better error messages
            validator = Draft7Validator(self.schemas[schema_type])
            errors = list(validator.iter_errors(data))
            
            if errors:
                error_messages = []
                for error in errors:
                    path = " -> ".join(str(p) for p in error.path) if error.path else "root"
                    error_messages.append(f"{path}: {error.message}")
                return False, "; ".join(error_messages[:3])  # Limit to first 3 errors
            
            return True, None
            
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        except Exception as e:
            return False, f"Error: {str(e)}"
            
    def validate_module_files(self):
        """Validate the main module file - DISABLED: *_module.json files not used in current architecture"""
        # *_module.json files are not used in the current architecture
        # The system uses individual JSON files (areas, plots, etc.) instead
        pass
                
    def validate_area_files(self):
        """Validate area/location files"""
        # Find area files dynamically - check both areas/ subdirectory and root
        import glob
        import os
        
        # First check the new areas/ subdirectory structure
        areas_dir = self.module_path / "areas"
        json_files = []
        
        if areas_dir.exists():
            json_files.extend(glob.glob(os.path.join(str(areas_dir), "*.json")))
        
        # Also check legacy root directory structure during migration
        root_json_files = glob.glob(os.path.join(str(self.module_path), "*.json"))
        
        for file_path in root_json_files:
            # Skip backup, module, and system files
            filename = os.path.basename(file_path)
            if any(part in filename for part in ["_BU", ".bak", ".backup", ".tmp", "module_", "party_", "campaign_", "map_"]):
                continue
            
            # Check if it's an area file by loading and checking structure
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data and 'areaId' in data and 'areaName' in data and 'locations' in data:
                    # This is an area file, add it to the list if not already found in areas/
                    area_filename = f"{data['areaId']}.json"
                    areas_path = areas_dir / area_filename if areas_dir.exists() else None
                    
                    # Only add legacy file if not already found in areas/ directory
                    if not areas_path or not areas_path.exists():
                        json_files.append(file_path)
            except Exception as e:
                # Not a valid JSON file, skip it
                continue
        
        # Validate all found area files
        for file_path in json_files:
            filename = os.path.basename(file_path)
            
            # Check if it's an area file by loading and checking structure
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data and 'areaId' in data and 'areaName' in data and 'locations' in data:
                    # This is an area file
                    success, error = self.validate_file(Path(file_path), "area")
                    # Include path info for areas/ vs root location
                    path_info = "(areas/)" if "areas/" in str(file_path) else "(root)"
                    self.results["area"]["files"].append(f"{filename} {path_info}")
                    
                    if success:
                        self.results["area"]["passed"] += 1
                    else:
                        self.results["area"]["failed"] += 1
                        self.results["area"]["errors"].append(f"{filename} {path_info}: {error}")
            except Exception as e:
                # Not a valid JSON file, skip it
                continue
                    
    def validate_character_files(self):
        """Validate character files"""
        char_dir = self.module_path / "characters"
        if not char_dir.exists():
            return
            
        for file_path in char_dir.glob("*.json"):
            if any(part in str(file_path) for part in ["_BU", ".bak", ".backup", ".tmp", "copy"]):
                continue
                
            success, error = self.validate_file(file_path, "character")
            self.results["character"]["files"].append(file_path.name)
            
            if success:
                self.results["character"]["passed"] += 1
            else:
                self.results["character"]["failed"] += 1
                self.results["character"]["errors"].append(f"{file_path.name}: {error}")
                
    def validate_monster_files(self):
        """Validate monster files"""
        monster_dir = self.module_path / "monsters"
        if not monster_dir.exists():
            return
            
        for file_path in monster_dir.glob("*.json"):
            if any(part in str(file_path) for part in ["_BU", ".bak", ".backup", ".tmp"]):
                continue
                
            success, error = self.validate_file(file_path, "monster")
            self.results["monster"]["files"].append(file_path.name)
            
            if success:
                self.results["monster"]["passed"] += 1
            else:
                self.results["monster"]["failed"] += 1
                self.results["monster"]["errors"].append(f"{file_path.name}: {error}")
                
    def validate_map_files(self):
        """Validate map files"""
        map_files = list(self.module_path.glob("map_*.json"))
        
        for file_path in map_files:
            if any(part in str(file_path) for part in ["_BU", ".bak", ".backup", ".tmp"]):
                continue
                
            success, error = self.validate_file(file_path, "map")
            self.results["map"]["files"].append(file_path.name)
            
            if success:
                self.results["map"]["passed"] += 1
            else:
                self.results["map"]["failed"] += 1
                self.results["map"]["errors"].append(f"{file_path.name}: {error}")
                
    def validate_plot_files(self):
        """Validate plot files"""
        plot_files = list(self.module_path.glob("*_plot.json"))
        
        for file_path in plot_files:
            if any(part in str(file_path) for part in ["_BU", ".bak", ".backup", ".tmp"]):
                continue
                
            success, error = self.validate_file(file_path, "plot")
            self.results["plot"]["files"].append(file_path.name)
            
            if success:
                self.results["plot"]["passed"] += 1
            else:
                self.results["plot"]["failed"] += 1
                self.results["plot"]["errors"].append(f"{file_path.name}: {error}")
                
    def validate_party_tracker(self):
        """Validate party tracker file"""
        party_file = self.module_path / "party_tracker.json"
        
        if party_file.exists():
            success, error = self.validate_file(party_file, "party")
            self.results["party"]["files"].append("party_tracker.json")
            
            if success:
                self.results["party"]["passed"] += 1
            else:
                self.results["party"]["failed"] += 1
                self.results["party"]["errors"].append(f"party_tracker.json: {error}")
                
    def validate_module_context(self):
        """Cross-check internal context locations against live area files."""
        context_file = self.module_path / "module_context.json"

        if not context_file.exists():
            self.results["module_context"]["not_applicable"] = 1
            return

        result = self.results["module_context"]
        result["files"].append("module_context.json")
        errors = []
        try:
            with open(context_file, "r", encoding="utf-8") as handle:
                context = json.load(handle)
        except Exception as exc:
            result["failed"] += 1
            result["errors"].append(f"module_context.json: unreadable context: {exc}")
            return

        expected_locations = {}
        expected_by_area = {}
        areas_dir = self.module_path / "areas"
        area_files = sorted(areas_dir.glob("*.json")) if areas_dir.exists() else []
        for area_file in area_files:
            if any(part in area_file.name for part in ["_BU", ".bak", ".backup", ".tmp"]):
                continue
            try:
                with open(area_file, "r", encoding="utf-8") as handle:
                    area = json.load(handle)
            except Exception:
                continue
            area_id = area.get("areaId")
            if not area_id:
                continue
            expected_by_area[area_id] = []
            for location in area.get("locations", []) or []:
                if not isinstance(location, dict):
                    continue
                location_id = location.get("locationId")
                if not location_id:
                    continue
                expected_by_area[area_id].append(location_id)
                connections = []
                for value in list(location.get("connectivity", []) or []) + list(
                    location.get("areaConnectivityId", []) or []
                ):
                    if isinstance(value, str) and value and value not in connections:
                        connections.append(value)
                expected_locations[location_id] = {
                    "name": location.get("name"),
                    "area": area_id,
                    "connections": connections,
                }

        actual_locations = context.get("locations")
        if not isinstance(actual_locations, dict):
            errors.append("locations must be an object")
            actual_locations = {}
        if set(actual_locations) != set(expected_locations):
            missing = sorted(set(expected_locations) - set(actual_locations))
            extra = sorted(set(actual_locations) - set(expected_locations))
            if missing:
                errors.append(f"locations missing live area IDs: {missing}")
            if extra:
                errors.append(f"locations contain unknown IDs: {extra}")

        for location_id, expected in expected_locations.items():
            actual = actual_locations.get(location_id)
            if not isinstance(actual, dict):
                continue
            for field in ("name", "area", "connections"):
                if actual.get(field) != expected[field]:
                    errors.append(
                        f"location '{location_id}' {field} differs from live area data"
                    )

        context_areas = context.get("areas")
        if not isinstance(context_areas, dict):
            errors.append("areas must be an object")
            context_areas = {}
        for area_id, expected_ids in expected_by_area.items():
            actual_area = context_areas.get(area_id)
            if not isinstance(actual_area, dict):
                errors.append(f"area '{area_id}' is missing from context")
                continue
            if actual_area.get("locations") != expected_ids:
                errors.append(
                    f"area '{area_id}' location list differs from live area data"
                )

        if errors:
            result["failed"] += 1
            result["errors"].extend(
                f"module_context.json: {message}" for message in errors
            )
        else:
            result["passed"] += 1
                
    def validate_encounter_files(self):
        """Validate encounter files"""
        encounter_dir = self.module_path / "encounters"
        if not encounter_dir.exists():
            return
            
        for file_path in encounter_dir.glob("*.json"):
            if any(part in str(file_path) for part in ["_BU", ".bak", ".backup", ".tmp"]):
                continue
                
            success, error = self.validate_file(file_path, "encounter")
            self.results["encounter"]["files"].append(file_path.name)
            
            if success:
                self.results["encounter"]["passed"] += 1
            else:
                self.results["encounter"]["failed"] += 1
                self.results["encounter"]["errors"].append(f"{file_path.name}: {error}")

    def validate_area_connectivity(self):
        """Validate that all areas are reachable from the starting area"""
        import json

        areas_dir = self.module_path / "areas"

        if not areas_dir.exists():
            return True, []

        # Load all area files
        area_data = {}
        # VAL-C1: exclude *_BU.json backups; live files are the source of truth.
        # Previously globbed BU files first, which caused stale backups to poison
        # connectivity validation by hiding the live (correct) area files.
        area_files = [
            f for f in areas_dir.glob("*.json")
            if not f.name.endswith("_BU.json")
        ]

        for file_path in area_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    area_id = data.get('areaId')
                    if area_id:
                        area_data[area_id] = {
                            'name': data.get('areaName'),
                            'locations': data.get('locations', [])
                        }
            except Exception:
                continue

        if len(area_data) <= 1:
            return True, []  # Single area modules don't need connectivity checks

        # Build connectivity graph
        area_connections = {}
        for area_id, data in area_data.items():
            area_connections[area_id] = set()
            for location in data['locations']:
                area_conn = location.get('areaConnectivity', [])

                # Map area names to area IDs
                for area_name in area_conn:
                    for target_id, target_data in area_data.items():
                        if target_data['name'] == area_name:
                            area_connections[area_id].add(target_id)
                            break

        # Find starting area (prefer town areas)
        sorted_areas = sorted(area_data.keys())
        starting_area = None

        for area_id in sorted_areas:
            if 'HFG' in area_id or 'VO' in area_id or 'TOWN' in area_id:
                starting_area = area_id
                break

        if not starting_area:
            starting_area = sorted_areas[0]

        # BFS to find all reachable areas
        visited = set()
        queue = [starting_area]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            for neighbor in area_connections.get(current, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        # Check for unreachable areas
        all_areas = set(area_data.keys())
        unreachable = all_areas - visited

        errors = []
        if unreachable:
            for area_id in sorted(unreachable):
                area_name = area_data[area_id]['name']
                errors.append(f"{area_id} ({area_name}) is unreachable from starting area {starting_area}")

        # Check for isolated starting area
        if not area_connections.get(starting_area):
            errors.append(f"Starting area {starting_area} ({area_data[starting_area]['name']}) has no connections - players cannot leave!")

        return len(errors) == 0, errors

    def validate_legacy_content_advisories(self):
        """Surface suspicious legacy content without rewriting or rejecting it."""
        advisories = []
        party_year = None
        party_file = self.module_path / "party_tracker.json"
        if party_file.exists():
            try:
                with open(party_file, "r", encoding="utf-8") as handle:
                    party = json.load(handle)
                party_year = (party.get("worldConditions") or {}).get("year")
            except Exception:
                pass

        areas_dir = self.module_path / "areas"
        area_files = sorted(areas_dir.glob("*.json")) if areas_dir.exists() else []
        for area_file in area_files:
            if any(part in area_file.name for part in ["_BU", ".bak", ".backup", ".tmp"]):
                continue
            try:
                with open(area_file, "r", encoding="utf-8") as handle:
                    area = json.load(handle)
            except Exception:
                continue

            levels = [
                int(value)
                for value in re.findall(r"\d+", str(area.get("recommendedLevel", "")))
            ]
            recommended_max = max(levels) if levels else None
            for location in area.get("locations", []) or []:
                if not isinstance(location, dict):
                    continue
                location_id = location.get("locationId", "unknown")
                source = f"{area_file.name}:{location_id}"

                for npc in location.get("npcs", []) or []:
                    if not isinstance(npc, dict):
                        continue
                    name = npc.get("name")
                    normalized = " ".join(name.split()) if isinstance(name, str) else ""
                    if (
                        not normalized
                        or len(normalized) > 120
                        or len(normalized.split()) > 18
                    ):
                        advisories.append(
                            f"{source}: NPC name is paragraph-shaped; review placement"
                        )

                for index, encounter in enumerate(location.get("encounters", []) or []):
                    if not isinstance(encounter, dict):
                        continue
                    encounter_year = (encounter.get("worldConditions") or {}).get("year")
                    if (
                        type(party_year) is int
                        and type(encounter_year) is int
                        and encounter_year != party_year
                    ):
                        advisories.append(
                            f"{source}: encounter[{index}] year {encounter_year} "
                            f"differs from campaign year {party_year}"
                        )

                danger = str(location.get("dangerLevel", "")).strip().casefold()
                if danger in {"very high", "extreme"} and (
                    recommended_max is not None and recommended_max <= 2
                ):
                    advisories.append(
                        f"{source}: danger '{location.get('dangerLevel')}' may be "
                        f"too severe for recommended level {area.get('recommendedLevel')}"
                    )

                for index, monster in enumerate(location.get("monsters", []) or []):
                    if not isinstance(monster, dict) or not str(
                        monster.get("name", "")
                    ).strip():
                        advisories.append(
                            f"{source}: lazy monster descriptor[{index}] has no usable name"
                        )
                        continue
                    quantity = monster.get("quantity")
                    if not isinstance(quantity, dict) or not all(
                        type(quantity.get(key)) is int for key in ("min", "max")
                    ):
                        advisories.append(
                            f"{source}: lazy monster '{monster['name']}' has an "
                            "unusable quantity range"
                        )

        result = self.results["content_advisories"]
        result["advisories"] = advisories
        result["not_applicable"] = int(not advisories)
        return advisories

    def validate_bidirectional_connectivity(self, module_path=None):
        """Validate that location-to-location connections are bidirectional.

        For each location L with connection target T in its `connectivity`
        array, verify that a location with ID T exists within the SAME area
        and lists L's ID in its own `connectivity`. `connectivity` entries
        are location IDs -- the generator, the ID remapper and the runtime
        pathfinder all treat them as IDs, and real module data is
        overwhelmingly ID-based (the schema description was corrected to
        match). An earlier attempt matched by name and produced dozens of
        false positives on valid modules; this is the ID-based version.

        This addresses VAL-H2 / MP-H4: one-way connections strand players,
        because navigation works A -> B but B does not list A so there is
        no way back.

        Vacuous case: if no location declares any connectivity, the
        bidirectional property is trivially satisfied -> (True, []).
        Unreachable-area detection is the job of
        `validate_area_connectivity`, not this validator.

        Args:
            module_path: Optional path to override `self.module_path`.
                When None, uses `self.module_path`.

        Returns:
            (passed, errors) tuple. `passed` is True iff `errors` is empty.
            Error format:
                "Location '<id>' connects to '<target_id>' but '<target_id>'
                 does not connect back"
            When `<target_id>` does not exist as a location at all, the error
            instead reads:
                "Location '<id>' connects to '<target_id>' but '<target_id>'
                 does not exist"
        """
        import json

        base_path = Path(module_path) if module_path is not None else self.module_path
        areas_dir = base_path / "areas"

        errors = []

        if not areas_dir.exists():
            return True, errors

        # VAL-C1: exclude *_BU.json backups; live files are the source of truth.
        area_files = [
            f for f in areas_dir.glob("*.json")
            if not f.name.endswith("_BU.json")
        ]

        for file_path in area_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                # Malformed area files are caught by schema validation
                # elsewhere; skip them here so this validator stays focused.
                continue

            locations = data.get('locations', []) or []

            # Build locationId -> connectivity-list map for THIS area only.
            # connectivity entries are location IDs within the same area
            # (areaConnectivity/areaConnectivityId handle cross-area links).
            id_to_conns = {}
            for loc in locations:
                if not isinstance(loc, dict):
                    continue
                loc_id = loc.get('locationId')
                if not loc_id:
                    continue
                conns = loc.get('connectivity', []) or []
                id_to_conns[loc_id] = list(conns)

            # Check each declared connection has a matching reverse edge.
            for src_id, conn_list in id_to_conns.items():
                for target_id in conn_list:
                    if target_id not in id_to_conns:
                        errors.append(
                            f"Location '{src_id}' connects to "
                            f"'{target_id}' but '{target_id}' does "
                            f"not exist"
                        )
                        continue
                    if src_id not in id_to_conns[target_id]:
                        errors.append(
                            f"Location '{src_id}' connects to "
                            f"'{target_id}' but '{target_id}' does "
                            f"not connect back"
                        )

        return len(errors) == 0, errors

    def validate_encounter_creature_resolution(self, module_path=None):
        """Validate that every enemy in every encounter resolves to a real
        monster stat block.

        Loads:
          - data/bestiary/monster_compendium.json (global bestiary; keys
            in the ``monsters`` dict are the snake_case monsterType ids)
          - modules/<module>/monsters/*.json (module-local stat blocks;
            the filename sans ``.json`` is the monsterType id)

        For each encounter file under modules/<module>/encounters/,
        iterates ``creatures[]``. Only creatures with ``type == 'enemy'``
        are checked; player/npc entries are skipped. The lookup key is
        ``creature['monsterType']`` (falling back to a snake_cased
        ``creature['name']`` if monsterType is absent). If the key
        resolves to neither the global bestiary nor a module-local
        monster file, an error is recorded.

        This addresses VAL-H4: the schema only requires ``monsterType``
        to be a string -- it does not verify that the string identifies
        a real monster. Encounters referencing nonexistent creatures
        (e.g. "ancient_purple_dragon") otherwise pass validation.

        Vacuous cases return (True, []) but leave
        ``encounter_creatures_checked`` at zero so callers report
        NOT_APPLICABLE rather than an unearned pass.

        Args:
            module_path: Optional path to override ``self.module_path``.
                When None, uses ``self.module_path``.

        Returns:
            (passed, errors) tuple. ``passed`` is True iff ``errors``
            is empty. Each error names the encounter filename and the
            unresolved monsterType so a fixer can locate the bug.
        """
        import json
        import os

        base_path = Path(module_path) if module_path is not None else self.module_path
        encounters_dir = base_path / "encounters"

        errors = []
        self.encounter_creatures_checked = 0

        # Load global bestiary keys. We tolerate the file being missing
        # or malformed -- in that case resolution falls back to the
        # module-local monsters dir only.
        #
        # Resolution order for the bestiary path:
        #   1. cwd-relative ``data/bestiary/monster_compendium.json``
        #      (used in production: the validator is run from repo root)
        #   2. repo-root-relative, resolved from this file's location
        #      (fallback for callers running from elsewhere)
        # Tests can isolate via ``monkeypatch.chdir`` to a fixture root
        # containing a fake ``data/bestiary/monster_compendium.json``.
        global_monster_keys = set()
        cwd_bestiary = Path.cwd() / "data" / "bestiary" / "monster_compendium.json"
        # core/validation/validate_module_files.py -> parents[2] is repo root
        repo_root = Path(__file__).resolve().parents[2]
        repo_bestiary = repo_root / "data" / "bestiary" / "monster_compendium.json"
        bestiary_path = cwd_bestiary if cwd_bestiary.exists() else repo_bestiary
        if bestiary_path.exists():
            try:
                with open(bestiary_path, "r", encoding="utf-8") as f:
                    bestiary_data = json.load(f)
                monsters = bestiary_data.get("monsters", {}) or {}
                if isinstance(monsters, dict):
                    global_monster_keys = set(monsters.keys())
            except Exception:
                # Malformed bestiary -- treat as empty, fall back to
                # module-local resolution only.
                global_monster_keys = set()

        # Load module-local monster file stems (filename sans .json).
        local_monster_keys = set()
        local_monsters_dir = base_path / "monsters"
        if local_monsters_dir.exists():
            for mon_file in local_monsters_dir.glob("*.json"):
                if any(part in mon_file.name for part in ["_BU", ".bak", ".backup", ".tmp"]):
                    continue
                local_monster_keys.add(mon_file.stem)

        known_keys = global_monster_keys | local_monster_keys

        def check_creatures(creatures, source_name):
            for creature in creatures or []:
                if not isinstance(creature, dict) or creature.get("type") != "enemy":
                    continue
                self.encounter_creatures_checked += 1
                key = creature.get("monsterType")
                if not key:
                    key = (creature.get("name") or "").strip().lower().replace(" ", "_")
                if not key:
                    continue
                if key not in known_keys:
                    errors.append(
                        f"{source_name}: creature monsterType '{key}' does not "
                        "resolve to any monster in "
                        "data/bestiary/monster_compendium.json or "
                        f"modules/{base_path.name}/monsters/"
                    )

        encounter_files = (
            sorted(encounters_dir.glob("*.json"))
            if encounters_dir.exists()
            else []
        )
        for enc_file in encounter_files:
            if any(part in enc_file.name for part in ["_BU", ".bak", ".backup", ".tmp"]):
                continue

            try:
                with open(enc_file, "r", encoding="utf-8") as f:
                    enc_data = json.load(f)
            except Exception:
                # Malformed JSON is caught by schema validation
                # elsewhere; skip here so this validator stays focused.
                continue

            check_creatures(enc_data.get("creatures", []), enc_file.name)

        # Embedded full encounters may also carry creatures[]. The separate
        # locations[].monsters entries are intentionally lazy spawn descriptors,
        # so they are not required to resolve to a prebuilt stat card here.
        areas_dir = base_path / "areas"
        area_files = sorted(areas_dir.glob("*.json")) if areas_dir.exists() else []
        for area_file in area_files:
            if any(part in area_file.name for part in ["_BU", ".bak", ".backup", ".tmp"]):
                continue
            try:
                with open(area_file, "r", encoding="utf-8") as handle:
                    area_data = json.load(handle)
            except Exception:
                continue
            for location in area_data.get("locations", []) or []:
                if not isinstance(location, dict):
                    continue
                location_id = location.get("locationId", "unknown")
                for index, encounter in enumerate(location.get("encounters", []) or []):
                    if not isinstance(encounter, dict) or "creatures" not in encounter:
                        continue
                    check_creatures(
                        encounter.get("creatures", []),
                        f"{area_file.name}:{location_id}:encounters[{index}]",
                    )

        return len(errors) == 0, errors

    def validate_all_files(self, strict: bool = False):
        """Validate all files and return results (required by module_stitcher).

        VAL-C2: Pass strict=True to enforce the composed
        `locationfile_schema_strict.json` for area files. Default
        strict=False preserves backward compatibility for existing
        callers that invoke `validate_all_files()` with no arguments.
        """
        self.run_all_validations(strict=strict)
        return self.results
    
    def get_success_rate(self):
        """Get overall validation success rate"""
        total_passed = sum(r["passed"] for r in self.results.values())
        total_failed = sum(r["failed"] for r in self.results.values())
        total_files = total_passed + total_failed
        
        if total_files == 0:
            return 1.0  # 100% if no files to validate
        
        return total_passed / total_files

    def run_all_validations(self, strict: bool = False):
        """Run all validation checks.

        VAL-C2: Forwards `strict` to `load_schemas()` so the stricter
        area schema is used when requested. Default strict=False keeps
        existing callers unaffected.
        """
        self.load_schemas(strict=strict)
        self.validate_module_files()
        self.validate_area_files()
        self.validate_character_files()
        self.validate_monster_files()
        self.validate_map_files()
        self.validate_plot_files()
        self.validate_party_tracker()
        self.validate_module_context()
        self.validate_encounter_files()
        self.validate_legacy_content_advisories()

        # Run connectivity validation
        success, errors = self.validate_area_connectivity()
        if success:
            self.results["connectivity"]["passed"] = 1
        else:
            self.results["connectivity"]["failed"] = 1
            self.results["connectivity"]["errors"] = errors

        # VAL-H2 / MP-H4: bidirectional location-to-location connectivity
        bi_success, bi_errors = self.validate_bidirectional_connectivity()
        if bi_success:
            self.results["bidirectional_connectivity"]["passed"] = 1
        else:
            self.results["bidirectional_connectivity"]["failed"] = 1
            self.results["bidirectional_connectivity"]["errors"] = bi_errors

        # VAL-H4: encounter creatures must resolve to real monster stat blocks
        enc_success, enc_errors = self.validate_encounter_creature_resolution()
        if self.encounter_creatures_checked == 0:
            self.results["encounter_creature_resolution"]["not_applicable"] = 1
        elif enc_success:
            self.results["encounter_creature_resolution"]["passed"] = 1
        else:
            self.results["encounter_creature_resolution"]["failed"] = 1
            self.results["encounter_creature_resolution"]["errors"] = enc_errors

    def run_validation(self, strict: bool = False):
        """Run all validations.

        VAL-C2: Pass strict=True to enforce the composed strict area
        schema. Default strict=False preserves backward compatibility
        with existing callers and the CLI entry point.
        """
        print(f"\nValidating module: {self.module_path}")
        print("=" * 80)

        self.load_schemas(strict=strict)
        print("\nRunning validations...")
        
        # Run all validation methods
        self.validate_module_files()
        self.validate_area_files()
        self.validate_character_files()
        self.validate_monster_files()
        self.validate_map_files()
        self.validate_plot_files()
        self.validate_party_tracker()
        self.validate_module_context()
        self.validate_encounter_files()
        self.validate_legacy_content_advisories()

        # VAL-H2 / MP-H4: bidirectional location-to-location connectivity
        bi_success, bi_errors = self.validate_bidirectional_connectivity()
        if bi_success:
            self.results["bidirectional_connectivity"]["passed"] = 1
        else:
            self.results["bidirectional_connectivity"]["failed"] = 1
            self.results["bidirectional_connectivity"]["errors"] = bi_errors

        # VAL-H4: encounter creatures must resolve to real monster stat blocks
        enc_success, enc_errors = self.validate_encounter_creature_resolution()
        if self.encounter_creatures_checked == 0:
            self.results["encounter_creature_resolution"]["not_applicable"] = 1
        elif enc_success:
            self.results["encounter_creature_resolution"]["passed"] = 1
        else:
            self.results["encounter_creature_resolution"]["failed"] = 1
            self.results["encounter_creature_resolution"]["errors"] = enc_errors

    def print_report(self):
        """Print comprehensive validation report"""
        print("\n" + "=" * 80)
        print("VALIDATION REPORT")
        print("=" * 80)
        print(f"Module: {self.module_path.name}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n")
        
        # Summary statistics
        total_passed = sum(r["passed"] for r in self.results.values())
        total_failed = sum(r["failed"] for r in self.results.values())
        total_files = total_passed + total_failed
        
        print(f"SUMMARY: {total_files} files validated")
        print(f"  [OK] Passed: {total_passed}")
        print(f"  [ERROR] Failed: {total_failed}")
        if total_files > 0:
            print(f"  Success Rate: {(total_passed/total_files)*100:.1f}%")
        print("\n")
        
        # Detailed results by file type
        print("DETAILED RESULTS BY FILE TYPE:")
        print("-" * 80)
        
        file_type_order = ["module", "area", "character", "monster", "map", "plot",
                          "party", "module_context", "encounter", "connectivity",
                          "bidirectional_connectivity", "encounter_creature_resolution",
                          "content_advisories"]

        for file_type in file_type_order:
            if file_type not in self.results:
                continue

            # Special handling for connectivity (no files list)
            if file_type == "connectivity":
                result = self.results[file_type]
                print(f"\nAREA CONNECTIVITY CHECK")
                if result.get("passed", 0) > 0:
                    print(f"  Status: [OK] ALL AREAS REACHABLE")
                elif result.get("failed", 0) > 0:
                    print(f"  Status: [ERROR] CONNECTIVITY ISSUES DETECTED")
                    print("  Errors:")
                    for error in result.get("errors", []):
                        print(f"    - {error}")
                else:
                    print(f"  Status: [SKIPPED] No multi-area module")
                continue

            # Special handling for bidirectional connectivity (no files list)
            if file_type == "bidirectional_connectivity":
                result = self.results[file_type]
                print(f"\nBIDIRECTIONAL CONNECTIVITY CHECK")
                if result.get("passed", 0) > 0:
                    print(f"  Status: [OK] ALL CONNECTIONS BIDIRECTIONAL")
                elif result.get("failed", 0) > 0:
                    print(f"  Status: [ERROR] ONE-WAY CONNECTIONS DETECTED")
                    print("  Errors:")
                    for error in result.get("errors", [])[:10]:
                        print(f"    - {error}")
                    remaining = len(result.get("errors", [])) - 10
                    if remaining > 0:
                        print(f"    ... and {remaining} more errors")
                else:
                    print(f"  Status: [SKIPPED]")
                continue

            # Special handling for encounter creature resolution (no files list)
            if file_type == "encounter_creature_resolution":
                result = self.results[file_type]
                print(f"\nENCOUNTER CREATURE RESOLUTION CHECK")
                if result.get("passed", 0) > 0:
                    print(f"  Status: [OK] ALL ENEMY CREATURES RESOLVE TO BESTIARY")
                elif result.get("failed", 0) > 0:
                    print(f"  Status: [ERROR] UNRESOLVED MONSTER REFERENCES DETECTED")
                    print("  Errors:")
                    for error in result.get("errors", [])[:10]:
                        print(f"    - {error}")
                    remaining = len(result.get("errors", [])) - 10
                    if remaining > 0:
                        print(f"    ... and {remaining} more errors")
                else:
                    print(f"  Status: [SKIPPED]")
                continue

            if file_type == "content_advisories":
                result = self.results[file_type]
                advisories = result.get("advisories", [])
                print("\nLEGACY CONTENT ADVISORIES")
                if advisories:
                    print(f"  Status: [REVIEW] {len(advisories)} non-blocking item(s)")
                    for advisory in advisories[:10]:
                        print(f"    - {advisory}")
                    remaining = len(advisories) - 10
                    if remaining > 0:
                        print(f"    ... and {remaining} more advisories")
                else:
                    print("  Status: [OK] No advisory patterns detected")
                continue

            if not self.results[file_type].get("files"):
                continue

            result = self.results[file_type]
            total = result["passed"] + result["failed"]

            print(f"\n{file_type.upper()} FILES ({total} files)")
            print(f"  Status: {'[OK] ALL PASSED' if result['failed'] == 0 else '[ERROR] FAILURES DETECTED'}")
            print(f"  Passed: {result['passed']}/{total}")

            if result["failed"] > 0:
                print(f"  Failed: {result['failed']}/{total}")
                print("  Errors:")
                for error in result["errors"][:5]:  # Show first 5 errors
                    print(f"    - {error}")
                if len(result["errors"]) > 5:
                    print(f"    ... and {len(result['errors']) - 5} more errors")
                    
        # Schema recommendations
        print("\n" + "-" * 80)
        print("SCHEMA RECOMMENDATIONS:")
        
        missing_schemas = []
        needs_refactoring = []
        
        # Check for missing schemas
        if "module_context" in self.results and self.results["module_context"]["failed"] > 0:
            for error in self.results["module_context"]["errors"]:
                if "No schema available" in error:
                    missing_schemas.append("module_context_schema.json")
                    
        # Check for high failure rates indicating schema issues
        for file_type, result in self.results.items():
            if result["files"] and result["failed"] > 0:
                failure_rate = result["failed"] / (result["passed"] + result["failed"])
                if failure_rate > 0.5:  # More than 50% failure rate
                    needs_refactoring.append(file_type)
                    
        if missing_schemas:
            print("\nMissing Schemas:")
            for schema in missing_schemas:
                print(f"  - {schema}")
                
        if needs_refactoring:
            print("\nSchemas Needing Review (high failure rate):")
            for file_type in needs_refactoring:
                schema_name = self.get_schema_name(file_type)
                print(f"  - {schema_name} ({file_type} files)")
                
        if not missing_schemas and not needs_refactoring:
            print("\n  [OK] All required schemas are present and functioning well")
            
        print("\n" + "=" * 80)
        
    def get_schema_name(self, file_type):
        """Get the schema filename for a file type"""
        mapping = {
            "module": "module_schema.json",
            "area": "locationfile_schema.json",
            "character": "char_schema.json",
            "monster": "mon_schema.json",
            "map": "map_schema.json",
            "plot": "plot_schema.json",
            "party": "party_schema.json",
            "encounter": "encounter_schema.json"
        }
        return mapping.get(file_type, f"{file_type}_schema.json")
        
    def save_report(self, output_file=None):
        """Save validation report to JSON file"""
        if not output_file:
            output_file = self.module_path / "validation_report.json"
            
        report = {
            "module": str(self.module_path.name),
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_files": sum(len(r["files"]) for r in self.results.values()),
                "total_passed": sum(r["passed"] for r in self.results.values()),
                "total_failed": sum(r["failed"] for r in self.results.values())
            },
            "results": dict(self.results)
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"\nDetailed report saved to: {output_file}")


def main():
    """Main execution function"""
    # Set paths
    module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "modules", "Keep_of_Doom")
    # issue #128: schemas live in repo_root/schemas, not repo_root. Without the
    # "schemas" segment the standalone validator can't load any schema file.
    schema_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "schemas")

    # Create validator and run
    validator = ModuleValidator(module_path, schema_dir)
    validator.run_validation()
    validator.print_report()
    validator.save_report()
    
    # Return exit code based on failures
    total_failed = sum(r["failed"] for r in validator.results.values())
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
