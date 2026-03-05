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
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

# jsonschema is optional at import time to allow --help to work without deps
# Individual validators will raise clear errors if called without jsonschema
try:
    from jsonschema import validate, ValidationError, Draft7Validator
    _JSONSCHEMA_AVAILABLE = True
except Exception:  # ImportError or missing deps
    _JSONSCHEMA_AVAILABLE = False
    # Provide fallback stubs to keep type checks and runtime clear
    class Draft7Validator:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("jsonschema is not installed")
        def iter_errors(self, *args, **kwargs):
            return []
    class ValidationError(Exception):
        pass
    def validate(*args, **kwargs):
        raise RuntimeError("jsonschema is not installed")


class ModuleValidator:
    """Validates all module files against their schemas"""
    
    def __init__(self, module_path, schema_dir):
        self.module_path = Path(module_path)
        self.schema_dir = Path(schema_dir)
        self.results = defaultdict(lambda: {"files": [], "passed": 0, "failed": 0, "errors": []})
        self.schemas = {}
        
    def load_schemas(self):
        """Load all available schemas"""
        schema_mappings = {
            "module": "module_schema.json",
            "area": "locationfile_schema.json",  # Area files use locationfile schema
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
            schema_path = self.schema_dir / "schemas" / schema_file
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
        # Runtime dependency check - allows --help to work without jsonschema
        if not _JSONSCHEMA_AVAILABLE:
            raise RuntimeError(
                "jsonschema is not installed. Install it via 'pip install jsonschema' "
                "to run module validation."
            )
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            if schema_type not in self.schemas:
                return False, f"No schema available for type: {schema_type}"
                
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
                
    @staticmethod
    def _normalize_monster_name(name):
        """Normalize monster name to slug format used by combat loader
        
        Lowercase, strip spaces, convert spaces to underscores,
        remove apostrophes and non-alphanumeric characters.
        """
        if not name:
            return ""
        # Lowercase and strip
        slug = name.lower().strip()
        # Remove apostrophes
        slug = slug.replace("'", "").replace('"', "")
        # Replace spaces and hyphens with underscores
        slug = slug.replace(" ", "_").replace("-", "_")
        # Remove any remaining non-alphanumeric except underscore
        slug = ''.join(c for c in slug if c.isalnum() or c == '_')
        return slug

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
        """Skip validation for module_context.json as it's an internal tracking file"""
        context_file = self.module_path / "module_context.json"
        
        if context_file.exists():
            # Mark as passed since it's an internal file that doesn't need validation
            self.results["module_context"]["files"].append("module_context.json")
            self.results["module_context"]["passed"] += 1
            print("  - Skipping module_context.json (internal tracking file)")
                
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

    def validate_monster_references(self):
        """Validate that area/location monster references resolve to monster files

        Checks all area files for monster references and verifies corresponding
        monster stat files exist in the module monsters/ directory.
        Records failures with detailed context for operator troubleshooting.
        """
        import json

        areas_dir = self.module_path / "areas"
        if not areas_dir.exists():
            return

        monster_dir = self.module_path / "monsters"
        if not monster_dir.exists():
            # No monsters directory means any references are unresolved
            monster_dir = None

        # Track which monster files exist (normalized names)
        available_monsters = set()
        if monster_dir and monster_dir.exists():
            for file_path in monster_dir.glob("*.json"):
                if any(part in str(file_path) for part in ["_BU", ".bak", ".backup", ".tmp"]):
                    continue
                # Store the slug name (without .json extension)
                available_monsters.add(file_path.stem.lower())

        # Scan all area files for monster references
        unresolved_references = []

        area_files = list(areas_dir.glob("*.json"))

        for file_path in area_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                area_id = data.get('areaId', file_path.stem)
                area_name = data.get('areaName', 'Unknown Area')
                locations = data.get('locations', [])

                for location in locations:
                    location_id = location.get('locationId', 'unknown')
                    location_name = location.get('locationName', 'Unknown Location')
                    monsters = location.get('monsters', [])

                    for monster_ref in monsters:
                        if isinstance(monster_ref, dict):
                            monster_name = monster_ref.get('name', '')
                        elif isinstance(monster_ref, str):
                            monster_name = monster_ref
                        else:
                            continue

                        if not monster_name:
                            continue

                        # Normalize to slug
                        normalized = self._normalize_monster_name(monster_name)

                        if normalized and normalized.lower() not in available_monsters:
                            expected_path = f"monsters/{normalized}.json"
                            unresolved_references.append({
                                'area_id': area_id,
                                'area_name': area_name,
                                'location_id': location_id,
                                'location_name': location_name,
                                'source_name': monster_name,
                                'expected_path': expected_path
                            })

            except Exception:
                # Skip files that can't be loaded
                continue

        # Record results
        if unresolved_references:
            self.results["reference_integrity"]["failed"] = len(unresolved_references)
            for ref in unresolved_references:
                error_msg = (f"{ref['source_name']} in {ref['area_name']}/{ref['location_name']} "
                           f"-> expected {ref['expected_path']}")
                self.results["reference_integrity"]["errors"].append(error_msg)
        else:
            # Mark as passed if we found no issues (or no monster references at all)
            self.results["reference_integrity"]["passed"] = 1

    def validate_area_connectivity(self):
        """Validate that all areas are reachable from the starting area"""
        import json

        areas_dir = self.module_path / "areas"

        if not areas_dir.exists():
            return True, []

        # Load all area files
        area_data = {}
        area_files = list(areas_dir.glob("*_BU.json"))

        if not area_files:
            area_files = list(areas_dir.glob("*.json"))

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

    def validate_all_files(self):
        """Validate all files and return results (required by module_stitcher)"""
        self.run_all_validations()
        return self.results
    
    def get_success_rate(self):
        """Get overall validation success rate"""
        total_passed = sum(r["passed"] for r in self.results.values())
        total_failed = sum(r["failed"] for r in self.results.values())
        total_files = total_passed + total_failed
        
        if total_files == 0:
            return 1.0  # 100% if no files to validate
        
        return total_passed / total_files

    def run_all_validations(self):
        """Run all validation checks"""
        self.validate_module_files()
        self.validate_area_files()
        self.validate_monster_references()
        self.validate_character_files()
        self.validate_monster_files()
        self.validate_map_files()
        self.validate_plot_files()
        self.validate_party_tracker()
        self.validate_module_context()
        self.validate_encounter_files()

        # Run connectivity validation
        success, errors = self.validate_area_connectivity()
        if success:
            self.results["connectivity"]["passed"] = 1
        else:
            self.results["connectivity"]["failed"] = 1
            self.results["connectivity"]["errors"] = errors
                
    def run_validation(self):
        """Run all validations"""
        print(f"\nValidating module: {self.module_path}")
        print("=" * 80)
        
        self.load_schemas()
        print("\nRunning validations...")
        
        # Run all validation methods
        self.validate_module_files()
        self.validate_area_files()
        self.validate_monster_references()
        self.validate_character_files()
        self.validate_monster_files()
        self.validate_map_files()
        self.validate_plot_files()
        self.validate_party_tracker()
        self.validate_module_context()
        self.validate_encounter_files()
        
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
        
        file_type_order = ["module", "area", "reference_integrity", "character", "monster", "map", "plot",
                          "party", "module_context", "encounter", "connectivity"]
        
        for file_type in file_type_order:
            if file_type not in self.results:
                continue

            # Special handling for reference_integrity (no files list)
            if file_type == "reference_integrity":
                result = self.results[file_type]
                print(f"\nMONSTER REFERENCE INTEGRITY CHECK")
                if result.get("passed", 0) > 0:
                    print(f"  Status: [OK] ALL MONSTER REFERENCES RESOLVED")
                elif result.get("failed", 0) > 0:
                    print(f"  Status: [ERROR] UNRESOLVED MONSTER REFERENCES")
                    print("  Errors:")
                    for error in result.get("errors", []):
                        print(f"    - {error}")
                else:
                    print(f"  Status: [SKIPPED] No area monster references to validate")
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


def _discover_all_modules():
    """Discover all module-like directories under modules/ for --all-modules."""
    modules_dir = Path(__file__).parent.parent.parent / "modules"
    if not modules_dir.exists():
        return []
    exclude = {
        "ingest", "conversation_history", "campaign_summaries", "backups",
        ".git", "__pycache__", "template", "example"
    }
    candidates = []
    for entry in sorted(modules_dir.iterdir()):
        if not entry.is_dir() or entry.name in exclude or entry.name.startswith('.'):
            continue
        areas_dir = entry / "areas"
        if areas_dir.exists() and any(areas_dir.glob("*.json")):
            candidates.append(entry.name)
    return candidates


def main():
    """Main execution with argparse"""
    parser = argparse.ArgumentParser(
        description="Validate module files against schemas",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--module",
        help="Validate a specific module by slug (e.g. The_Pumpkin_Kings_Curse)",
        type=str,
        default=None
    )
    parser.add_argument(
        "--module-path",
        help="Validate an explicit module path (absolute or relative)",
        type=str,
        default=None
    )
    parser.add_argument(
        "--all-modules",
        help="Validate all detected modules (registry plus module-like folders)",
        action="store_true"
    )
    parser.add_argument(
        "--json",
        help="Output combined JSON summary to stdout",
        action="store_true"
    )

    args = parser.parse_args()

    # Determine targets
    targets = []
    if args.module_path:
        p = Path(args.module_path)
        if not p.exists():
            parser.error(f"Module path does not exist: {args.module_path}")
        targets.append(p)
    elif args.module:
        base = Path(__file__).parent.parent.parent / "modules" / args.module
        if not base.exists():
            parser.error(f"Module not found: modules/{args.module}")
        targets.append(base)
    elif args.all_modules:
        targets = [Path(__file__).parent.parent.parent / "modules" / name for name in _discover_all_modules()]
    else:
        # Backward compatible default: Keep_of_Doom (if it exists), otherwise first discovered module
        default_path = Path(__file__).parent.parent.parent / "modules" / "Keep_of_Doom"
        if default_path.exists():
            targets = [default_path]
        else:
            # Fallback to discovery of any module to avoid complete failure
            discovered = _discover_all_modules()
            if discovered:
                targets = [Path(__file__).parent.parent.parent / "modules" / discovered[0]]
            else:
                parser.error("No modules found. Provide --module or --module-path.")

    schema_dir = Path(__file__).parent.parent.parent  # repo root where schemas/ lives
    all_results = {}
    overall_failed = False

    for module_path in targets:
        validator = ModuleValidator(module_path, schema_dir)
        try:
            validator.run_validation()
        except RuntimeError as e:
            # Unwrap dependency errors clearly for operators
            if "jsonschema" in str(e).lower():
                print(f"[ERROR] {e}")
                sys.exit(2)
            raise

        total_failed = sum(r["failed"] for r in validator.results.values())
        overall_failed = overall_failed or (total_failed > 0)

        if args.json:
            # Accumulate JSON results for all modules
            summary = {
                "module": str(module_path.name),
                "total_passed": sum(r["passed"] for r in validator.results.values()),
                "total_failed": total_failed,
                "files": dict(validator.results)
            }
            all_results[module_path.name] = summary
        else:
            # Human report per module
            validator.print_report()
            validator.save_report()

    if args.json:
        combined = {
            "modules": all_results,
            "summary": {
                "modules_total": len(targets),
                "any_failed": overall_failed
            }
        }
        print(json.dumps(combined, indent=2))

    return 0 if not overall_failed else 1


if __name__ == "__main__":
    sys.exit(main())