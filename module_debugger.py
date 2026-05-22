# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Module Debugger
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

#!/usr/bin/env python3
"""
Module Debugger Tool
Validates module data for compatibility with main.py and all game systems.
Tests the most recent module in the modules folder.
"""

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import jsonschema
from collections import defaultdict

class ModuleDebugger:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.schemas = {}
        self.module_data = {}
        self.module_path = None
        
    def log_error(self, message: str):
        """Log an error"""
        self.errors.append(f"ERROR: {message}")
        print(f"❌ ERROR: {message}")
        
    def log_warning(self, message: str):
        """Log a warning"""
        self.warnings.append(f"WARNING: {message}")
        print(f"⚠️  WARNING: {message}")
        
    def log_info(self, message: str):
        """Log info"""
        self.info.append(f"INFO: {message}")
        print(f"ℹ️  INFO: {message}")
        
    def log_success(self, message: str):
        """Log success"""
        print(f"✅ SUCCESS: {message}")
    
    def find_latest_module(self) -> str:
        """Find the most recent module folder"""
        modules_dir = Path("modules")
        if not modules_dir.exists():
            self.log_error("No modules directory found")
            return None
            
        module_folders = [d for d in modules_dir.iterdir() if d.is_dir()]
        if not module_folders:
            self.log_error("No module folders found")
            return None
            
        # Sort by modification time to get the most recent
        latest = max(module_folders, key=lambda d: d.stat().st_mtime)
        self.log_info(f"Found latest module: {latest.name}")
        return str(latest)
    
    def load_schemas(self) -> bool:
        """Load all JSON schemas"""
        schema_files = [
            "module_schema.json",
            "loca_schema.json", 
            "plot_schema.json",
            "party_schema.json",
            "char_schema.json",
            "npc_schema.json",
            "mon_schema.json",
            "map_schema.json",
            "encounter_schema.json",
            "room_schema.json"
        ]
        
        for schema_file in schema_files:
            try:
                with open(schema_file, 'r') as f:
                    self.schemas[schema_file] = json.load(f)
                    self.log_success(f"Loaded schema: {schema_file}")
            except FileNotFoundError:
                self.log_warning(f"Schema not found: {schema_file}")
            except json.JSONDecodeError as e:
                self.log_error(f"Invalid JSON in {schema_file}: {e}")
                return False
                
        return True
    
    def load_module_files(self) -> bool:
        """Load all files from the module directory"""
        if not self.module_path:
            return False
            
        module_files = list(Path(self.module_path).glob("*.json"))
        
        for file_path in module_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    filename = file_path.name
                    self.module_data[filename] = data
                    self.log_success(f"Loaded: {filename}")
            except json.JSONDecodeError as e:
                self.log_error(f"Invalid JSON in {filename}: {e}")
                return False
                
        return True
    
    def validate_schema_compliance(self):
        """Validate each file against its schema"""
        schema_mappings = {
            "*_module.json": "module_schema.json",
            "party_tracker.json": "party_schema.json",
            "map_*.json": "map_schema.json",
            "plot_*.json": "plot_schema.json",
            "module_context.json": None,  # Internal tracking file
            "validation_report.json": None,  # Generated report
            "debug_report.md": None  # Debug report
        }
        
        for filename, data in self.module_data.items():
            schema_name = None
            
            # Find matching schema
            for pattern, schema in schema_mappings.items():
                if pattern.startswith("*") and filename.endswith(pattern[1:]):
                    schema_name = schema
                    break
                elif pattern.endswith("*") and filename.startswith(pattern[:-1]):
                    schema_name = schema
                    break
                elif pattern == filename:
                    schema_name = schema
                    break
            
            # Handle mapping overrides
            if filename in schema_mappings:
                schema_name = schema_mappings[filename]
                
            # Special handling for area files (locations)
            # Detect area files by STRUCTURE (areaId + locations), not by
            # filename prefix. The previous hardcoded prefix allowlist
            # (HH/GV/BH/BV/DS/EM/DG) silently skipped any module using a
            # different prefix (e.g. VO, TOWN, ZZ).
            if self._is_area_file(data):
                self.validate_location_file(filename, data)
                continue
                
            if schema_name and schema_name in self.schemas:
                try:
                    jsonschema.validate(data, self.schemas[schema_name])
                    self.log_success(f"Valid schema: {filename} -> {schema_name}")
                except jsonschema.ValidationError as e:
                    # Special handling for common enum errors
                    if "is not one of" in str(e):
                        self.log_error(f"Schema validation failed for {filename}: {e.message}")
                        # Try to identify the exact issue
                        if '"' in str(e.instance):
                            self.log_info(f"Found value with embedded quotes: {e.instance}")
                            cleaned_value = str(e.instance).strip('"')
                            self.log_info(f"This should probably be: {cleaned_value}")
                    else:
                        self.log_error(f"Schema validation failed for {filename}: {e.message}")
            else:
                self.log_warning(f"No schema mapping for: {filename}")
    
    def _is_area_file(self, data: Any) -> bool:
        """Detect area files by structure, not filename prefix.

        Area files have both `areaId` and `locations` at the top level.
        Module-level files (e.g. *_module.json), party_tracker, plot
        files, and validation reports do not have this shape, so the
        check is sufficient to disambiguate without false positives.
        """
        return isinstance(data, dict) and "areaId" in data and "locations" in data

    def validate_location_file(self, filename: str, data: Dict[str, Any]):
        """Special validation for location files"""
        # Area files should have these fields
        required_area_fields = ["areaId", "areaName", "areaType", "map", "locations"]
        
        for field in required_area_fields:
            if field not in data:
                self.log_error(f"{filename} missing required field: {field}")
                return
        
        # Validate locations array against schema
        if "loca_schema.json" in self.schemas:
            try:
                location_wrapper = {"locations": data.get("locations", [])}
                jsonschema.validate(location_wrapper, self.schemas["loca_schema.json"])
                self.log_success(f"Valid locations in: {filename}")
            except jsonschema.ValidationError as e:
                self.log_error(f"Location validation failed for {filename}: {e.message}")
    
    def validate_references(self):
        """Validate all cross-references between files"""
        # Collect all IDs
        area_ids = set()
        location_ids = defaultdict(set)  # area_id -> set of location_ids
        npc_names = set()
        plot_locations = defaultdict(set)  # area_id -> set of plot location_ids
        
        # Extract IDs from files
        for filename, data in self.module_data.items():
            if "areaId" in data:
                area_id = data["areaId"]
                area_ids.add(area_id)
                
                # Get locations in this area
                if "locations" in data:
                    for location in data["locations"]:
                        location_ids[area_id].add(location.get("locationId"))
                        
                        # Collect NPCs
                        for npc in location.get("npcs", []):
                            if isinstance(npc, dict):
                                npc_names.add(npc.get("name"))
                            elif isinstance(npc, str):
                                npc_names.add(npc)
            
            # Check plot files
            if filename.startswith("plot_"):
                area_id = filename.replace("plot_", "").replace(".json", "")
                for plot_point in data.get("plotPoints", []):
                    if "location" in plot_point:
                        loc = plot_point["location"]
                        plot_locations[area_id].add(loc)
                    # Also check for nested side quests
                    for side_quest in plot_point.get("sideQuests", []):
                        if "location" in side_quest:
                            plot_locations[area_id].add(side_quest["location"])
        
        # Validate plot locations exist
        for area_id, plot_locs in plot_locations.items():
            area_locs = location_ids.get(area_id, set())
            for plot_loc in plot_locs:
                if plot_loc not in area_locs:
                    # Check if this is a special reference (like area ID itself)
                    if plot_loc == area_id:
                        self.log_warning(f"Plot references area ID {plot_loc} instead of specific location")
                    else:
                        self.log_error(f"Plot references non-existent location: {plot_loc} in area {area_id}")
                        # Provide helpful suggestions
                        if area_locs:
                            self.log_info(f"Available locations in {area_id}: {', '.join(sorted(area_locs))}")
        
        # Validate connectivity
        for filename, data in self.module_data.items():
            if "locations" in data:
                area_id = data.get("areaId")
                for location in data["locations"]:
                    # Check internal connectivity
                    for conn in location.get("connectivity", []):
                        if conn not in location_ids.get(area_id, set()):
                            self.log_error(f"Invalid connection {conn} in location {location.get('locationId')} of {area_id}")
                    
                    # Check area connectivity
                    for area_conn in location.get("areaConnectivityId", []):
                        if area_conn == area_id:
                            self.log_error(f"Location {location.get('locationId')} incorrectly references its own area {area_id}")
                        # Check if using incorrect format with location ID
                        elif "-" in area_conn and not area_conn.split("-")[0] in area_ids:
                            self.log_error(f"Location {location.get('locationId')} uses incorrect area connectivity format: '{area_conn}'. Should use just area ID, not location-specific ID.")
                        elif area_conn not in area_ids:
                            self.log_warning(f"Location {location.get('locationId')} references unknown area {area_conn}")
    
    def validate_party_tracker(self):
        """Validate party tracker references"""
        if "party_tracker.json" not in self.module_data:
            self.log_error("No party_tracker.json found")
            return
            
        tracker = self.module_data["party_tracker.json"]
        
        # Check current location exists
        current_area = tracker.get("worldConditions", {}).get("currentAreaId")
        current_location = tracker.get("worldConditions", {}).get("currentLocationId")
        
        if current_area and current_area not in [d.get("areaId") for d in self.module_data.values() if "areaId" in d]:
            self.log_error(f"Party tracker references non-existent area: {current_area}")
            
        # Check if location exists in the area
        area_data = None
        for data in self.module_data.values():
            if data.get("areaId") == current_area:
                area_data = data
                break
                
        if area_data and current_location:
            location_ids = [loc.get("locationId") for loc in area_data.get("locations", [])]
            if current_location not in location_ids:
                self.log_error(f"Party tracker references non-existent location: {current_location} in area {current_area}")
    
    def simulate_script_loading(self):
        """Simulate how various scripts would load the module"""
        print("\n--- Simulating Script Loading ---")
        
        # Check main.py requirements
        self.simulate_main_loading()
        
        # Check combat_manager.py requirements
        self.simulate_combat_manager()
        
        # Check location_manager.py requirements
        self.simulate_location_manager()
        
        # Check storyteller.py requirements
        self.simulate_storyteller()
        
        # Check plot_update.py requirements
        self.simulate_plot_update()
        
        # Check update scripts
        self.simulate_update_scripts()
        
        # Check dm.py and conversation systems
        self.simulate_dm_systems()
        
    def simulate_main_loading(self):
        """Simulate how main.py would load the module"""
        print("\n[main.py checks]")
        # Check required files for main.py
        required_files = [
            "party_tracker.json",
            "current_location.json",  # May be created by main.py
            "modules/conversation_history/chat_history.json",      # May be created by main.py
            "journal.json"            # May be created by main.py
        ]
        
        for req_file in required_files:
            if req_file not in self.module_data:
                if req_file in ["current_location.json", "modules/conversation_history/chat_history.json", "journal.json"]:
                    self.log_info(f"Optional file not found (will be created): {req_file}")
                else:
                    self.log_error(f"Required file missing: {req_file}")
        
        # Simulate loading party members
        if "party_tracker.json" in self.module_data:
            tracker = self.module_data["party_tracker.json"]
            for member in tracker.get("partyMembers", []):
                char_file = f"{member.lower()}.json"
                if char_file not in self.module_data:
                    # Check in parent directory (character files might be outside module folder)
                    if not os.path.exists(char_file):
                        self.log_warning(f"Character file not found: {char_file}")
                        
            # Check NPCs
            for npc in tracker.get("partyNPCs", []):
                npc_name = npc.get("name") if isinstance(npc, dict) else npc
                npc_file = f"{npc_name.lower()}.json"
                if npc_file not in self.module_data:
                    if not os.path.exists(npc_file):
                        self.log_warning(f"NPC file not found: {npc_file}")
    
    def simulate_combat_manager(self):
        """Simulate combat_manager.py loading"""
        print("\n[combat_manager.py checks]")
        
        # Check for encounter files
        encounter_dir = "modules/encounters"
        encounter_files = []
        if os.path.exists(encounter_dir):
            encounter_files = [f for f in os.listdir(encounter_dir) if f.startswith("encounter_") and f.endswith(".json")]
        if not encounter_files:
            self.log_info("No active encounter files found (normal for non-combat)")
        else:
            for enc_file in encounter_files:
                self.log_info(f"Found encounter file: {enc_file}")
                
        # Check monster files referenced in locations
        for filename, data in self.module_data.items():
            if "locations" in data:
                for location in data["locations"]:
                    for monster in location.get("monsters", []):
                        monster_name = monster.get("name") if isinstance(monster, dict) else monster
                        from update_character_info import normalize_character_name
                        monster_file = f"{normalize_character_name(monster_name)}.json"
                        if not os.path.exists(monster_file):
                            self.log_warning(f"Monster file not found: {monster_file} (referenced in {filename})")
    
    def simulate_location_manager(self):
        """Simulate location_manager.py loading"""
        print("\n[location_manager.py checks]")
        
        # Check current location consistency
        if "party_tracker.json" in self.module_data:
            tracker = self.module_data["party_tracker.json"]
            current_location = tracker.get("worldConditions", {}).get("currentLocationId")
            current_area = tracker.get("worldConditions", {}).get("currentAreaId")
            
            if current_area and current_location:
                # Find the area file
                area_file = f"{current_area}.json"
                if area_file in self.module_data:
                    area_data = self.module_data[area_file]
                    location_found = False
                    for loc in area_data.get("locations", []):
                        if loc.get("locationId") == current_location:
                            location_found = True
                            self.log_success(f"Current location {current_location} found in {current_area}")
                            break
                    if not location_found:
                        self.log_error(f"Current location {current_location} not found in area {current_area}")
    
    def simulate_storyteller(self):
        """Simulate storyteller.py loading"""
        print("\n[storyteller.py checks]")
        
        # Check for required plot and quest files
        if "party_tracker.json" in self.module_data:
            tracker = self.module_data["party_tracker.json"]
            module_name = tracker.get("module")
            
            # Check for quest progress
            if not os.path.exists("quest_progress.json"):
                self.log_info("quest_progress.json not found (will be created)")
            
            # Check for chronology
            if not os.path.exists("chronology.json"):
                self.log_info("chronology.json not found (will be created)")
    
    def simulate_plot_update(self):
        """Simulate plot_update.py loading"""
        print("\n[plot_update.py checks]")
        
        # Check plot files match areas
        area_ids = set()
        plot_ids = set()
        
        for filename, data in self.module_data.items():
            if "areaId" in data:
                area_ids.add(data["areaId"])
            if filename.startswith("plot_"):
                plot_id = filename.replace("plot_", "").replace(".json", "")
                plot_ids.add(plot_id)
        
        # Check for matching plot files
        for area_id in area_ids:
            if area_id not in plot_ids:
                self.log_warning(f"No plot file found for area {area_id}")
        
        for plot_id in plot_ids:
            if plot_id not in area_ids:
                self.log_warning(f"Plot file {plot_id} has no matching area")
    
    def simulate_update_scripts(self):
        """Simulate various update_*.py scripts"""
        print("\n[update_*.py scripts checks]")
        
        # update_player_info.py
        if "party_tracker.json" in self.module_data:
            tracker = self.module_data["party_tracker.json"]
            for member in tracker.get("partyMembers", []):
                self.log_info(f"update_player_info.py would update: {member}")
        
        # update_npc_info.py
        if "party_tracker.json" in self.module_data:
            tracker = self.module_data["party_tracker.json"]
            for npc in tracker.get("partyNPCs", []):
                npc_name = npc.get("name") if isinstance(npc, dict) else npc
                self.log_info(f"update_npc_info.py would update: {npc_name}")
        
        # update_world_time.py
        if "party_tracker.json" in self.module_data:
            world_conditions = self.module_data["party_tracker.json"].get("worldConditions", {})
            if "time" in world_conditions:
                self.log_success("World time data present for update_world_time.py")
            else:
                self.log_warning("No time data in worldConditions")
        
        # update_party_tracker.py
        self.log_info("update_party_tracker.py would synchronize all party data")
    
    def simulate_dm_systems(self):
        """Simulate dm.py and conversation systems"""
        print("\n[dm.py and conversation systems checks]")
        
        # Check for system prompt
        if not os.path.exists("system_prompt.txt"):
            self.log_warning("system_prompt.txt not found (using default)")
        
        # Check conversation history
        if not os.path.exists("modules/conversation_history/conversation_history.json"):
            self.log_info("conversation_history.json not found (will be created)")
            
        # Check module references in party tracker
        if "party_tracker.json" in self.module_data:
            tracker = self.module_data["party_tracker.json"]
            module_name = tracker.get("module")
            
            # Check if module file exists
            module_file = f"{module_name.replace(' ', '_')}_module.json"
            if module_file not in self.module_data:
                self.log_warning(f"Module file {module_file} not found for module '{module_name}'")
        
        # Check for validation prompt
        if not os.path.exists("prompts/validation/validation_prompt.txt"):
            self.log_info("validation_prompt.txt not found (using default)")
            
        # Check for summarization files
        if not os.path.exists("dialogue_summary.json"):
            self.log_info("dialogue_summary.json not found (will be created)")
            
        # Check dm_wrapper.py requirements
        print("\n[dm_wrapper.py checks]")
        current_area = None
        if "party_tracker.json" in self.module_data:
            tracker = self.module_data["party_tracker.json"]
            current_area = tracker.get("worldConditions", {}).get("currentAreaId")
            
            if current_area:
                # Check if the area has NPCs that dm.py would need to voice
                area_file = f"{current_area}.json"
                if area_file in self.module_data:
                    area_data = self.module_data[area_file]
                    for location in area_data.get("locations", []):
                        for npc in location.get("npcs", []):
                            if isinstance(npc, dict):
                                self.log_info(f"DM would voice NPC: {npc.get('name')} in {location.get('name')}")
                            else:
                                self.log_info(f"DM would voice NPC: {npc} in {location.get('name')}")
    
    def generate_report(self) -> str:
        """Generate a comprehensive report"""
        report = f"""
# Module Debug Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Module: {self.module_path}

## Summary
- Errors: {len(self.errors)}
- Warnings: {len(self.warnings)}
- Info: {len(self.info)}

## Files Loaded
"""
        for filename in sorted(self.module_data.keys()):
            report += f"- {filename}\n"
        
        if self.errors:
            report += "\n## Errors\n"
            for error in self.errors:
                report += f"- {error}\n"
                
        if self.warnings:
            report += "\n## Warnings\n"
            for warning in self.warnings:
                report += f"- {warning}\n"
                
        report += f"\n## Status\n"
        if not self.errors:
            report += "✅ Module is compatible with main.py\n"
        else:
            report += "❌ Module has errors that need to be fixed\n"
            
        return report
    
    def check_structural_issues(self):
        """Check for common structural issues in module files"""
        print("\n--- Checking Structural Issues ---")
        
        # Check for area consistency
        area_count = 0
        location_count = 0
        
        for filename, data in self.module_data.items():
            if "areaId" in data and "locations" in data:
                area_count += 1
                location_count += len(data["locations"])
                
                # Check for empty locations
                if not data["locations"]:
                    self.log_warning(f"Area {data['areaId']} has no locations")
                
                # Check for consistent area naming
                if data["areaId"] != filename.replace(".json", ""):
                    self.log_warning(f"Area ID {data['areaId']} doesn't match filename {filename}")
        
        self.log_info(f"Found {area_count} areas with {location_count} total locations")
        
        # Check plot consistency
        plot_count = 0
        for filename in self.module_data:
            if filename.startswith("plot_"):
                plot_count += 1
                
        if plot_count != area_count:
            self.log_warning(f"Mismatch: {area_count} areas but {plot_count} plot files")
    
    def run_debug(self):
        """Run the complete debug process"""
        print("=" * 50)
        print("MODULE DEBUGGER")
        print("=" * 50)
        
        # Find latest module
        self.module_path = self.find_latest_module()
        if not self.module_path:
            return
        
        # Load schemas
        if not self.load_schemas():
            return
            
        # Load module files
        if not self.load_module_files():
            return
            
        print("\n--- Validating Schemas ---")
        self.validate_schema_compliance()
        
        print("\n--- Validating References ---")
        self.validate_references()
        
        print("\n--- Validating Party Tracker ---")
        self.validate_party_tracker()
        
        print("\n--- Checking Structural Issues ---")
        self.check_structural_issues()
        
        print("\n--- Simulating Script Loading ---")
        self.simulate_script_loading()
        
        # Generate report
        report = self.generate_report()
        
        # Save report
        report_path = os.path.join(self.module_path, "debug_report.md")
        with open(report_path, 'w') as f:
            f.write(report)
            
        print(f"\n📄 Report saved to: {report_path}")
        print("\n" + "=" * 50)
        print(report)


def main():
    debugger = ModuleDebugger()
    debugger.run_debug()


if __name__ == "__main__":
    main()