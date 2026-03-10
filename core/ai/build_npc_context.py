#!/usr/bin/env python3
"""
Build comprehensive NPC context for validation by dynamically scanning all module areas.
Completely agnostic - extracts NPCs from the locations->npcs structure in area files.
"""

import os
import json
from pathlib import Path
from typing import Dict, Set, List, Optional
from utils.encoding_utils import safe_json_load

def extract_npcs_from_area(area_data: dict) -> Dict[str, Set[str]]:
    """
    Extract NPCs from area file structure.
    Returns dict of location_id -> set of NPC names
    """
    npcs_by_location = {}
    
    # Check if this area has locations
    if "locations" in area_data and isinstance(area_data["locations"], list):
        for location in area_data["locations"]:
            if not isinstance(location, dict):
                continue
                
            location_id = location.get("locationId", "")
            if not location_id:
                continue
            
            location_npcs = set()
            
            # Extract NPCs from the npcs field
            if "npcs" in location and isinstance(location["npcs"], list):
                for npc in location["npcs"]:
                    if isinstance(npc, dict) and "name" in npc:
                        # Clean the name (remove parentheticals and commas for cleaner parsing)
                        name = npc["name"].split("(")[0].strip()
                        name = name.replace(",", "")  # Remove commas to avoid parsing issues
                        if name:
                            location_npcs.add(name)
                    elif isinstance(npc, str):
                        # Sometimes NPCs are just strings
                        name = npc.split("(")[0].strip()
                        name = name.replace(",", "")  # Remove commas to avoid parsing issues
                        if name:
                            location_npcs.add(name)
            
            # Don't extract from monsters field - those are actual monsters, not NPCs
            
            # Check encounters for named NPCs
            if "encounters" in location and isinstance(location["encounters"], list):
                for encounter in location["encounters"]:
                    if isinstance(encounter, dict):
                        # Some encounters have NPCs
                        if "npcs" in encounter and isinstance(encounter["npcs"], list):
                            for npc in encounter["npcs"]:
                                if isinstance(npc, dict) and "name" in npc:
                                    name = npc["name"].split("(")[0].strip()
                                    name = name.replace(",", "")  # Remove commas to avoid parsing issues
                                    if name:
                                        location_npcs.add(name)
            
            if location_npcs:
                npcs_by_location[location_id] = location_npcs
    
    return npcs_by_location

def scan_module_areas(module_name: str) -> Dict[str, Set[str]]:
    """Scan all area files in a module for NPCs."""
    all_npcs = {}
    module_path = Path(f"modules/{module_name}")
    areas_path = module_path / "areas"
    
    if not areas_path.exists():
        return all_npcs
    
    # Process all JSON files in areas directory
    for json_file in areas_path.glob("*.json"):
        # Skip backup files
        if any(skip in json_file.name.lower() for skip in ["backup", ".bak", "_bu"]):
            continue
            
        try:
            data = safe_json_load(json_file)
            if data:
                npcs_in_area = extract_npcs_from_area(data)
                # Merge results
                for location_id, npcs in npcs_in_area.items():
                    if location_id in all_npcs:
                        all_npcs[location_id].update(npcs)
                    else:
                        all_npcs[location_id] = npcs
        except Exception as e:
            # Skip files that can't be loaded
            pass
    
    return all_npcs

def scan_all_modules() -> Dict[str, Dict[str, Set[str]]]:
    """Scan all modules dynamically."""
    all_modules = {}
    modules_path = Path("modules")
    
    if not modules_path.exists():
        return all_modules
    
    # Get all directories in modules/
    for item in modules_path.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            # Skip system directories
            if item.name in ["conversation_history", "campaign_archives", "campaign_summaries"]:
                continue
            
            # Check if it has an areas subdirectory
            areas_dir = item / "areas"
            if areas_dir.exists():
                module_npcs = scan_module_areas(item.name)
                if module_npcs:
                    all_modules[item.name] = module_npcs
    
    return all_modules

def build_npc_validation_context(current_module: str, current_location: str, party_npcs: List[str] = None) -> str:
    """
    Build compressed NPC context for validation.
    
    Args:
        current_module: Name of the current module
        current_location: Current location ID
        party_npcs: List of NPCs in the party
    
    Returns:
        Compressed machine-readable context string
    """
    # Scan all modules
    all_modules = scan_all_modules()
    
    # Build compressed format
    lines = []
    lines.append("@NPC_VALIDATION_DATA")
    
    # NPCs at current location
    current_loc_npcs = []
    if current_module in all_modules and current_location in all_modules[current_module]:
        current_loc_npcs = sorted(all_modules[current_module][current_location])
    lines.append(f"@CURRENT_LOC[{current_location}]: {','.join(current_loc_npcs) if current_loc_npcs else 'NONE'}")
    
    # NPCs in current module
    module_npcs = set()
    if current_module in all_modules:
        for loc_npcs in all_modules[current_module].values():
            module_npcs.update(loc_npcs)
    lines.append(f"@CURRENT_MODULE[{current_module}]: {','.join(sorted(module_npcs)[:50]) if module_npcs else 'NONE'}")
    
    # Party NPCs
    if party_npcs:
        lines.append(f"@PARTY_NPCS: {','.join(party_npcs)}")
    else:
        lines.append("@PARTY_NPCS: NONE")
    
    # All NPCs from other modules (compressed list)
    other_npcs = set()
    for module_name, locations in all_modules.items():
        if module_name != current_module:
            for loc_npcs in locations.values():
                other_npcs.update(loc_npcs)
    
    # Only include first 30 from other modules to save space
    other_npcs_list = sorted(other_npcs)[:30]
    lines.append(f"@OTHER_MODULES: {','.join(other_npcs_list) if other_npcs_list else 'NONE'}")
    
    # Total count for reference
    total_npcs = set()
    for module_name, locations in all_modules.items():
        for loc_npcs in locations.values():
            total_npcs.update(loc_npcs)
    lines.append(f"@TOTAL_NPC_COUNT: {len(total_npcs)}")
    
    # Compressed validation rules
    lines.append("@RULES: Listed NPCs are known entities. Ghosts/spirits/memories/dreams are VALID without state actions. EXPLICIT physical arrivals (arrives/enters/joins/appears/emerges/approaches) for off-location NPCs MUST have moveBackgroundNPC or updatePartyNPCs action. See @NPC_ARRIVAL_VALIDATION for details.")
    
    return "\n".join(lines)

def integrate_into_main():
    """
    Show how to integrate this into main.py validation context.
    """
    print("\n" + "="*60)
    print("Integration for main.py:")
    print("="*60)
    print("""
# In main.py, replace the NPC compendium loading with:

from build_npc_context import build_npc_validation_context

# In create_module_validation_context function:
npc_context = build_npc_validation_context(
    current_module=party_tracker_data.get('module', 'Unknown'),
    current_location=party_tracker_data.get('worldConditions', {}).get('currentLocationId', 'Unknown'),
    party_npcs=[npc.get('name') for npc in party_tracker_data.get('partyNPCs', [])]
)

validation_context += f"\\n\\n{npc_context}\\n"
""")

if __name__ == "__main__":
    # Test the system
    print("Scanning all modules for NPCs...")
    print("-" * 60)
    
    # Scan all modules
    all_modules = scan_all_modules()
    
    print(f"Found {len(all_modules)} modules with NPCs:")
    for module_name, locations in all_modules.items():
        total_npcs = len(set(npc for loc_npcs in locations.values() for npc in loc_npcs))
        print(f"  - {module_name}: {len(locations)} locations with NPCs, {total_npcs} unique NPCs")
    
    print("\n" + "-" * 60)
    
    # Test with first module found
    if all_modules:
        # Find first location with NPCs
        first_module = list(all_modules.keys())[0]
        first_location = list(all_modules[first_module].keys())[0] if all_modules[first_module] else "UNKNOWN"
        
        # Build sample context
        sample_context = build_npc_validation_context(
            current_module=first_module,
            current_location=first_location,
            party_npcs=[]
        )
        
        print(f"Sample context for {first_module} at {first_location}:")
        print(sample_context)
    else:
        print("No modules found with NPCs")
    
    # Show integration
    integrate_into_main()