# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Module Context
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

#!/usr/bin/env python3
"""
Module Context Manager
Maintains consistency across all module generation by tracking references and relationships.
"""

import json
import re
import os
import glob
import copy
from typing import Dict, List, Any, Set
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ModuleContext:
    """Maintains the master context for module generation"""
    
    # Core module info
    module_name: str = ""
    module_id: str = ""
    
    # Area mappings
    areas: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # NPC tracking
    npcs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Location tracking
    locations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Plot scope tracking
    plot_scopes: Dict[str, str] = field(default_factory=dict)
    
    # Reference tracking
    references: Dict[str, Set[str]] = field(default_factory=dict)
    
    # Validation issues
    validation_issues: List[str] = field(default_factory=list)
    
    def add_area(self, area_id: str, area_name: str, area_type: str = ""):
        """Register a new area"""
        self.areas[area_id] = {
            "name": area_name,
            "type": area_type,
            "locations": [],
            "npcs": [],
            "plot_points": []
        }
    
    def add_npc(self, npc_name: str, area_id: str = None, location_id: str = None, 
                role: str = "", faction: str = "", description: str = ""):
        """
        Smarter NPC registration that finds or creates a canonical entry.
        It normalizes names and handles aliases/duplicates.
        """
        from updates.update_character_info import normalize_character_name
        
        # --- New Smart Matching Logic ---
        # 1. Get the "base name" by removing parenthetical descriptions (e.g., "Elder Myra")
        base_name = re.sub(r'\s*\([^)]*\)\s*', '', npc_name).strip()
        
        # 2. Search for an existing NPC with the same base name
        canonical_key = None
        for key, data in self.npcs.items():
            existing_base_name = re.sub(r'\s*\([^)]*\)\s*', '', data['name']).strip()
            if base_name.lower() == existing_base_name.lower():
                canonical_key = key
                break
        
        # 3. Handle special cases like "Specter of Abbot Liran" vs "Spirit of Abbot Liran"
        if not canonical_key:
            if "abbot liran" in base_name.lower():
                for key, data in self.npcs.items():
                    if "abbot liran" in data['name'].lower():
                        canonical_key = key
                        break

        # 4. If no match is found, create a NEW canonical entry
        if not canonical_key:
            canonical_key = normalize_character_name(base_name)  # The key is based on the clean name
            self.npcs[canonical_key] = {
                "name": base_name,  # Store the clean, canonical name
                "role": role,
                "faction": faction,
                "description": description,
                "appears_in": [],
                "aliases": [npc_name]  # Track the original generated name as an alias
            }
        # 5. If a match IS found, update the existing entry
        else:
            # Add the new variant as an alias if it's not already there
            if npc_name not in self.npcs[canonical_key].get("aliases", []):
                self.npcs[canonical_key].setdefault("aliases", []).append(npc_name)
            # If the new entry has a description and the old one doesn't, add it
            if description and not self.npcs[canonical_key].get("description"):
                self.npcs[canonical_key]["description"] = description
        
        # --- End of New Logic ---

        # Track where this NPC appears using the canonical entry
        if area_id and location_id:
            appearance = {"area": area_id, "location": location_id}
            if appearance not in self.npcs[canonical_key]["appears_in"]:
                self.npcs[canonical_key]["appears_in"].append(appearance)
        
        # Add to the area's NPC list using the canonical name
        if area_id and area_id in self.areas:
            canonical_name = self.npcs[canonical_key]['name']
            if canonical_name not in self.areas[area_id]["npcs"]:
                self.areas[area_id]["npcs"].append(canonical_name)

        return self.npcs[canonical_key]["name"]
    
    def add_location(self, location_id: str, location_name: str, area_id: str):
        """Register a location"""
        self.locations[location_id] = {
            "name": location_name,
            "area": area_id,
            "npcs": [],
            "connections": []
        }
        
        # Add to area tracking
        if area_id in self.areas:
            if location_id not in self.areas[area_id]["locations"]:
                self.areas[area_id]["locations"].append(location_id)
    
    def add_plot_point(self, plot_id: str, area_id: str, location_id: str = None):
        """Track which area a plot point belongs to"""
        self.plot_scopes[plot_id] = area_id
        
        # Add to area tracking
        if area_id in self.areas:
            if plot_id not in self.areas[area_id]["plot_points"]:
                self.areas[area_id]["plot_points"].append(plot_id)
    
    def add_reference(self, entity_type: str, entity_name: str, referenced_in: str):
        """Track where entities are referenced"""
        key = f"{entity_type}:{entity_name}"
        if key not in self.references:
            self.references[key] = set()
        self.references[key].add(referenced_in)
    
    def validate_npc_placement(self):
        """Check that all referenced NPCs are placed in locations"""
        issues = []
        
        # Helper function to extract base name (without parenthetical descriptions)
        def get_base_name(name):
            # Remove anything in parentheses and strip whitespace
            import re
            return re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
        
        # Create a mapping of base names to full NPC entries
        base_name_to_npcs = {}
        for npc_key, npc_data in self.npcs.items():
            base_name = get_base_name(npc_data['name']).lower()
            if base_name not in base_name_to_npcs:
                base_name_to_npcs[base_name] = []
            base_name_to_npcs[base_name].append((npc_key, npc_data))
        
        # Check each NPC
        for npc_key, npc_data in self.npcs.items():
            if not npc_data["appears_in"]:
                # Check if this NPC is referenced anywhere
                ref_key = f"npc:{npc_data['name']}"
                if ref_key in self.references and self.references[ref_key]:
                    # Before reporting as missing, check if there's a matching NPC by base name
                    base_name = get_base_name(npc_data['name']).lower()
                    
                    # Look for any NPC with the same base name that HAS been placed
                    found_placement = False
                    for _, other_npc_data in base_name_to_npcs.get(base_name, []):
                        if other_npc_data["appears_in"]:
                            found_placement = True
                            break
                    
                    # Only report as issue if no NPC with this base name was placed
                    if not found_placement:
                        referenced_in = list(self.references[ref_key])
                        issues.append(f"NPC '{npc_data['name']}' is referenced in {referenced_in} but not placed in any location")
        
        return issues
    
    def validate_plot_scope(self):
        """Check that plot points are in appropriate areas"""
        issues = []
        
        for plot_id, area_id in self.plot_scopes.items():
            if area_id not in self.areas:
                issues.append(f"Plot point {plot_id} references non-existent area {area_id}")
        
        return issues
    
    def validate_connections(self):
        """Check that all location connections are valid"""
        issues = []
        
        for loc_id, loc_data in self.locations.items():
            for connection in loc_data.get("connections", []):
                if connection not in self.locations:
                    issues.append(f"Location {loc_id} connects to non-existent location {connection}")
        
        return issues
    
    def validate_all(self):
        """Run all validation checks"""
        self.validation_issues = []
        self.validation_issues.extend(self.validate_npc_placement())
        self.validation_issues.extend(self.validate_plot_scope())
        self.validation_issues.extend(self.validate_connections())
        return self.validation_issues
    
    def get_validation_prompt(self):
        """Generate validation requirements for LLM prompts"""
        return f"""
VALIDATION REQUIREMENTS - MUST FOLLOW:

1. Module Name: {self.module_name}
   - Use this exact name consistently across all files

2. Area IDs and Names:
{json.dumps(self.areas, indent=2)}
   - Use these exact IDs and names for area references
   - Do NOT create new area IDs

3. NPCs Already Defined:
{json.dumps({k: v['name'] for k, v in self.npcs.items()}, indent=2)}
   - These NPCs MUST be placed in specific locations
   - Do NOT rename or create duplicates
   - Place each NPC in exactly ONE location

4. Plot Points by Area:
{json.dumps(self.plot_scopes, indent=2)}
   - Plot points MUST stay in their assigned areas
   - Do NOT place climax events in starter areas

5. Critical Consistency Rules:
   - Use exact area names for connectivity (e.g., "Gloamwood" not "Forsaken_Woods")
   - Place key NPCs from module/plot files in actual room locations
   - Ensure plot progression matches area progression
   - Maintain consistent naming for all entities

6. Required NPC Placements:
{self._get_required_npc_placements()}
"""
    
    def _get_required_npc_placements(self):
        """Generate specific NPC placement requirements"""
        requirements = []
        for npc_key, npc_data in self.npcs.items():
            if not npc_data["appears_in"]:
                requirements.append(f"   - {npc_data['name']}: MUST be placed in a specific location")
        return "\n".join(requirements) if requirements else "   - All NPCs are properly placed"
    
    def to_dict(self):
        """Convert context to dictionary for saving"""
        return {
            "module_name": self.module_name,
            "module_id": self.module_id,
            "areas": self.areas,
            "npcs": self.npcs,
            "locations": self.locations,
            "plot_scopes": self.plot_scopes,
            "references": {k: list(v) for k, v in self.references.items()},
            "validation_issues": self.validation_issues,
            "generated_at": datetime.now().isoformat()
        }
    
    def save(self, filepath: str):
        """Save context to file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, filepath: str):
        """Load context from file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        context = cls()
        context.module_name = data.get("module_name", "")
        context.module_id = data.get("module_id", "")
        context.areas = data.get("areas", {})
        context.npcs = data.get("npcs", {})
        context.locations = data.get("locations", {})
        context.plot_scopes = data.get("plot_scopes", {})
        context.references = {k: set(v) for k, v in data.get("references", {}).items()}
        context.validation_issues = data.get("validation_issues", [])

        return context

    @classmethod
    def from_artifacts(cls, module_dir: str, base_context: "ModuleContext" = None):
        """Rebuild the STRUCTURAL context (areas, locations, plot_scopes) from the
        final on-disk artifacts (areas/*.json + module_plot.json).

        NPC identity is owned by the T088 reconciler, so npcs/references are
        carried verbatim from base_context (the in-memory pre-reconciliation
        context) and NEVER rebuilt via add_npc (whose hard-coded/syntactic
        identity logic is unsuitable for projection). The active builder does not
        persist a [module]_module.json, so nothing is read from one.

        Supports BOTH plot location contracts: classic T028 stores AREA IDs in
        plotPoints[].location; story-first stores LOCATION IDs (resolved here to
        the containing area). An unknown/ambiguous plot location is left unscoped
        and recorded as a validation note rather than guessed.
        """
        context = cls()
        if base_context is not None:
            context.module_name = base_context.module_name
            context.module_id = base_context.module_id
            context.npcs = copy.deepcopy(base_context.npcs)
            context.references = {k: set(v) for k, v in base_context.references.items()}

        loc_to_area: Dict[str, str] = {}
        areas_dir = os.path.join(module_dir, "areas")
        if os.path.isdir(areas_dir):
            for path in sorted(glob.glob(os.path.join(areas_dir, "*.json"))):
                if path.endswith("_BU.json"):
                    continue
                try:
                    with open(path, "r") as handle:
                        area = json.load(handle)
                except (OSError, ValueError):
                    continue
                area_id = area.get("areaId")
                if not area_id:
                    continue
                context.add_area(area_id, area.get("areaName", ""), area.get("areaType", ""))
                for location in area.get("locations", []):
                    location_id = location.get("locationId")
                    if not location_id:
                        continue
                    context.add_location(location_id, location.get("name", ""), area_id)
                    loc_to_area[location_id] = area_id

        plot_path = os.path.join(module_dir, "module_plot.json")
        if os.path.isfile(plot_path):
            try:
                with open(plot_path, "r") as handle:
                    plot = json.load(handle)
            except (OSError, ValueError):
                plot = {}
            for point in plot.get("plotPoints", []):
                point_id = point.get("id")
                location = point.get("location")
                if not point_id:
                    continue
                if location in context.areas:            # classic T028: area ID
                    context.add_plot_point(point_id, location)
                elif location in loc_to_area:            # story-first: location ID
                    context.add_plot_point(point_id, loc_to_area[location])
                elif location:                           # unknown -> note, never guess
                    context.validation_issues.append(
                        f"plot point {point_id} references unknown location/area '{location}'"
                    )

        return context
