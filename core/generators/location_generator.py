#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Location Generator Script
Creates detailed location JSON files based on schema requirements and plot needs.
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from core.ai import api_client
import config
import jsonschema
import random
from utils.module_path_manager import ModulePathManager
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T025", "core/generators/location_generator.py", 431)
register_callsite("T026", "core/generators/location_generator.py", 566)


@dataclass
class LocationPromptGuide:
    """Detailed prompts and examples for each location field"""
    
    name: str = """
    Location names should be evocative and specific to their purpose.
    They should hint at what players might find or experience.
    
    Examples by type:
    - Cave Entrance: "The Whispering Threshold", "Maw of Shadows"
    - Chamber: "Hall of Echoing Stone", "The Crystal Sanctum"  
    - Corridor: "The Winding Descent", "Passage of Whispers"
    - Throne Room: "Court of the Fallen King", "Ember Throne Chamber"
    
    Format: 2-5 words, capitalize major words
    Style: Atmospheric, hints at location's nature
    """
    
    type: str = """
    Location type defines its primary function and layout.
    Must match the area's theme (dungeon, wilderness, town, etc.)
    
    Dungeon types:
    - entrance, corridor, chamber, hall, vault, shrine, prison, 
      laboratory, throne room, treasure room, crypt, library
    
    Wilderness types:
    - clearing, grove, cave, ravine, hilltop, riverside, ruins, 
      campsite, crossroads, landmark, den, nest
    
    Town types:
    - square, market, tavern, shop, temple, guild, residence, 
      gate, warehouse, barracks, dock, alley
    
    Choose based on location's role in the adventure.
    """
    
    description: str = """
    The main description paints a vivid picture for players.
    Include sensory details and atmosphere.
    
    Structure (3-5 sentences):
    1. Overall impression and size
    2. Key visual features  
    3. Atmospheric details (sounds, smells, temperature)
    4. Notable objects or areas of interest
    5. Hints at danger or opportunity
    
    Example:
    "The chamber stretches thirty feet across, its vaulted ceiling 
    disappearing into darkness above. Ancient stone pillars, carved 
    with worn dwarven runes, support the weight of centuries. A musty 
    smell mingles with the faint scent of sulfur, while water drips 
    steadily from somewhere in the shadows. Against the far wall, a 
    massive stone door bears the seal of a hammer wreathed in flames."
    
    Length: 3-5 sentences
    Style: Present tense, immersive, specific details
    """
    
    dmInstructions: str = """
    DM instructions provide practical running advice not obvious to players.
    Include mechanics, secrets, and pacing guidance.
    
    Should cover:
    - Hidden elements (secret doors, traps, treasures)
    - Skill check DCs and their results
    - Combat tactics for inhabitants
    - Environmental hazards or effects
    - Connections to the larger plot
    - Timing considerations
    
    Example:
    "The pillars conceal pressure plates (DC 15 Perception to notice). 
    Triggering one releases poison darts (DC 13 Dex save, 2d4 poison 
    damage). The sealed door requires the proper ritual phrase or DC 20 
    Strength to force. Behind it lies the forge guardian, which activates 
    if the seal is broken violently. The sulfur smell intensifies near 
    the secret passage (DC 18 Investigation to find) leading to area R07."
    
    Length: 3-5 sentences
    Style: Mechanical, specific DCs and effects
    """
    
    accessibility: str = """
    How easily can this location be accessed?
    Describes physical entry/exit challenges.
    
    Examples:
    - "Open archway, easily accessible"
    - "Narrow passage requiring squeeze (DC 12 Athletics)"
    - "Locked iron door (DC 15 Thieves' Tools)"
    - "Hidden entrance behind waterfall (DC 16 Perception)"
    - "Rope bridge over chasm (DC 10 Acrobatics)"
    
    Include: Physical barriers, skill checks, special requirements
    """
    
    npcs: str = """
    NPCs found in this location (if any).
    List inhabitants with their disposition and purpose.
    
    Each NPC entry should have:
    - name: Their name or identifier
    - description: Brief physical/personality note
    - attitude: hostile, neutral, friendly, cautious, etc.
    
    Example:
    {
        "name": "Grimtooth the Gatekeeper",
        "description": "A scarred hobgoblin veteran with a missing eye",
        "attitude": "hostile"
    }
    
    NPCs should:
    - Fit the location's purpose
    - Have clear motivations
    - Connect to plot/quests when possible
    
    Note: Your main.py will generate full stats when needed.
    """
    
    monsters: str = """
    Creatures that may be encountered here.
    Include quantity ranges for scalability.
    
    CRITICAL NAMING REQUIREMENT:
    - Use SINGULAR names ONLY (e.g., "goblin", "skeleton", "orc")
    - NEVER use plural names (e.g., "goblins", "skeletons", "orcs")
    - Each monster entry represents a single creature type, not a group
    - Multiple creatures are handled through quantity, not plural names
    
    Each monster entry needs:
    - name: Creature type in SINGULAR form (e.g., "goblin", "dire wolf")
    - quantity: min/max range for group size
    
    Example:
    {
        "name": "stone guardian",
        "quantity": {"min": 1, "max": 2}
    }
    
    Consider:
    - Appropriate CR for area's danger level
    - Logical inhabitants for location type
    - Environmental fit (no fish in desert)
    - Plot connections (cultists in evil temple)
    
    Note: Combat stats generated separately by your system.
    """
    
    plotHooks: str = """
    Story elements that draw players deeper into the adventure.
    Brief hints that connect to larger plot or offer side quests.
    
    Examples:
    - "Fresh blood trails lead toward the eastern passage"
    - "A journal page mentions 'the ceremony at midnight'"
    - "Strange symbols match those from the stolen artifact"
    - "Voices echo from behind the sealed door"
    
    Format: 1-2 sentence hints or observations
    Quantity: 1-3 hooks per location
    Purpose: Guide players, provide clues, create tension
    """
    
    lootTable: str = """
    Potential treasures found through search or victory.
    Mix of monetary and useful items.
    
    Categories:
    - Currency: "50 gold pieces", "ancient silver coins"
    - Consumables: "healing potion", "scroll of fireball"
    - Equipment: "masterwork longsword", "boots of elvenkind"
    - Plot items: "crystal key", "coded message"
    - Mundane: "silk rope", "adventurer's kit"
    
    Balance value with danger level and effort required.
    Important items should require investigation or risk.
    """
    
    dangerLevel: str = """
    Overall threat assessment for the location.
    Must be one of: "Low", "Medium", "High", "Very High"
    
    Factors:
    - Low: Safe rest area, friendly NPCs, no traps
    - Medium: Some monsters, minor traps, environmental hazards
    - High: Deadly creatures, dangerous traps, hostile NPCs
    - Very High: Boss monsters, lethal traps, extreme conditions
    
    Should match the area's overall danger level but can vary.
    """
    
    connectivity: str = """
    Direct physical connections to other locations.
    List locationIds of adjacent rooms/areas.
    
    Examples: ["R01", "R03", "R07"]
    
    Connections should:
    - Match the map layout
    - Make logical sense (doors, passages, stairs)
    - Create interesting navigation choices
    - Allow multiple paths when possible
    """
    
    traps: str = """
    Mechanical or magical hazards in the location.
    Each trap needs detection, disabling, and effect details.
    
    Required fields:
    - name: Descriptive identifier
    - description: How it works and appears
    - detectDC: Perception/Investigation check
    - disableDC: Thieves' Tools/Arcana check
    - triggerDC: Save if triggered (or "automatic")
    - damage: Effect when triggered
    
    Example:
    {
        "name": "Flame Jet Trap",
        "description": "Hidden nozzles spray fire when triggered",
        "detectDC": 15,
        "disableDC": 13,
        "triggerDC": 14,
        "damage": "3d6 fire damage, DC 14 Dex save for half"
    }
    
    Balance lethality with level appropriateness.
    """
    
    features: str = """
    Notable non-trap elements that define the location.
    Interactive or descriptive elements.
    
    Each feature needs:
    - name: What to call it
    - description: What it looks like and does
    
    Examples:
    - Ancient altar (can be investigated)
    - Collapsed ceiling (difficult terrain)
    - Underground stream (water source)
    - Magical fountain (healing properties)
    - Crystal formation (valuable but dangerous)
    
    Features add character and opportunities for interaction.
    """
    
    dcChecks: str = """
    Skill challenges available in the location.
    Format: "SkillName DC XX: Result description"
    
    Examples:
    - "Perception DC 15: Notice the secret door behind the tapestry"
    - "Investigation DC 12: Find the hidden compartment in the altar"
    - "Athletics DC 18: Climb the crumbling wall to the upper level"
    - "Arcana DC 16: Identify the magical aura around the crystals"
    - "History DC 14: Recognize the dwarven clan symbols"
    
    Provide 2-4 meaningful checks per location.
    Results should offer advantages or information.
    """
    
    encounters: str = """
    Pre-planned encounters that occurred or may occur here.
    Used to track module history and planned events.
    
    Fields:
    - encounterId: Unique identifier (e.g., "R05-E1")
    - summary: Brief description of what happened/will happen
    - impact: How it affects the location or story
    - worldConditions: Date/time when it occurred
    
    Example:
    {
        "encounterId": "R05-E1",
        "summary": "Party fought and defeated the stone guardians",
        "impact": "Guardians destroyed, forge now accessible",
        "worldConditions": {
            "year": 1492,
            "month": "Hammer",
            "day": 15,
            "time": "14:30:00"
        }
    }
    
    Used for continuity and world persistence.
    """
    
    doors: str = """
    Detailed information about entrances and exits.
    Each door/passage needs security and condition details.
    
    Required fields:
    - name: Identifier (e.g., "North Door", "Secret Panel")
    - description: Physical appearance and material
    - type: Regular, secret, portcullis, magical, etc.
    - locked: true/false
    - lockDC: Difficulty to pick (0 if not locked)
    - breakDC: Difficulty to force open
    - keyname: What opens it (if applicable)
    - trapped: true/false
    - trap: Trap details if trapped
    
    Example:
    {
        "name": "Iron-bound Oak Door",
        "description": "Massive door reinforced with iron bands",
        "type": "heavy",
        "locked": true,
        "lockDC": 15,
        "breakDC": 20,
        "keyname": "Guardian's Key",
        "trapped": false,
        "trap": ""
    }
    
    Doors control flow and present challenges.
    """
    
    areaConnectivity: str = """
    Connections to different areas/maps entirely.
    Used for zone transitions.
    
    List area names this location connects to.
    Example: ["Ember Mines - Level 2", "Surface Exit"]
    
    Typically used for:
    - Stairs between dungeon levels
    - Exits to wilderness
    - Portals to other planes
    - Zone boundaries
    
    Helps track large-scale navigation.
    """
    
    areaConnectivityId: str = """
    Area IDs corresponding to areaConnectivity names.
    Maintains technical references.
    
    IMPORTANT RULES:
    - Use empty array [] if location doesn't connect to other areas
    - Only include IDs of OTHER areas, never the current area
    - Must match entries in areaConnectivity array
    
    Examples:
    - Internal room: []
    - Exit to another area: ["GW001"] (if connecting to Gloamwood)
    - Multi-area connection: ["EM002", "SURFACE"]
    
    Used by system for area transitions.
    """

class LocationGenerator:
    def __init__(self):
        self.prompt_guide = LocationPromptGuide()
        self.schema = self.load_schema()
    
    def load_schema(self) -> Dict[str, Any]:
        """Load the location schema for validation"""
        with open("schemas/loca_schema.json", "r") as f:
            return json.load(f)
    
    def generate_field(self, field_path: str, schema_info: Dict[str, Any], 
                      context: Dict[str, Any]) -> Any:
        """Generate content for a specific field"""
        field_name = field_path.split(".")[-1]
        guide_attr = field_name
        
        # Handle nested fields with underscores
        if "." in field_path:
            guide_attr = field_path.replace(".", "_")
        
        guide_text = getattr(self.prompt_guide, guide_attr, "")
        
        prompt = f"""Generate content for the '{field_path}' field of a 5e location.

Field Schema:
{json.dumps(schema_info, indent=2)}

Detailed Guidelines:
{guide_text}

Context:
{json.dumps(context.to_dict() if hasattr(context, 'to_dict') else context, indent=2)}

Return ONLY the value for this field in the correct format.
For strings, return just the string.
For arrays, return just the array.
For objects, return just the object.
Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols.
"""

        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            main_cfg = config.DM_MAIN_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            main_cfg = config.DM_MAIN_GEMINI_PRO_LOW
        elif MODEL_PROVIDER == "lmstudio":
            main_cfg = config.DM_MAIN_LMSTUDIO
        else:  # legacy
            main_cfg = config.DM_MAIN_LEGACY

        response = capture_and_fanout("T025", api_client.create_completion,
            messages=[
                {"role": "system", "content": "You are an expert 5e location designer. Return only the requested data in the exact format needed."},
                {"role": "user", "content": prompt}
            ],
            model=main_cfg["model"],
            temperature=0.7,
            response_format=None,
            **{k: v for k, v in main_cfg.items() if k != "model"})

        content = response.choices[0].message.content.strip()

        # Try to parse as JSON if it looks like JSON
        if content.startswith(('[', '{')):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

        return content

    def generate_location_batch(self, 
                               area_data: Dict[str, Any],
                               plot_data: Dict[str, Any],
                               module_data: Dict[str, Any],
                               location_stubs: List[Dict[str, Any]],
                               context=None,
                               excluded_names=None,
                               context_header: str = "") -> Dict[str, Any]:
        """Generate all locations for an area in one go for better coherence"""
        
        generation_context = {
            "module": {
                "name": module_data.get("moduleName", ""),
                "description": module_data.get("moduleDescription", ""),
                "theme": module_data.get("worldSettings", {}).get("era", ""),
                "magicLevel": module_data.get("worldSettings", {}).get("magicPrevalence", "")
            },
            "area": {
                "name": area_data.get("areaName", ""),
                "type": area_data.get("areaType", "dungeon"),
                "description": area_data.get("areaDescription", ""),
                "dangerLevel": area_data.get("dangerLevel", "medium"),
                "recommendedLevel": area_data.get("recommendedLevel", 1)
            },
            "plot": {
                "title": plot_data.get("plotTitle", ""),
                "objective": plot_data.get("mainObjective", ""),
                "currentStage": plot_data.get("plotPoints", [{}])[0].get("description", "") if plot_data.get("plotPoints") else ""
            },
            "locationStubs": location_stubs
        }
        
        # Add validation requirements if context provided
        validation_prompt = ""
        if context:
            validation_prompt = context.get_validation_prompt()
        
        # Add party name exclusion to prompt
        party_exclusion_prompt = ""
        if excluded_names:
            party_exclusion_prompt = f"""
CRITICAL: Do NOT use these names for NPCs as they are existing party members: {', '.join(excluded_names)}
Create entirely different names that don't conflict with or resemble these party member names.
Avoid any variations, surnames, or titles using these names.
"""
        
        # Generate all locations with a single comprehensive prompt
        batch_prompt = f"""{context_header}Generate detailed 5e locations for {area_data.get('areaName', 'this area')}.

{party_exclusion_prompt}

Context:
{json.dumps(generation_context, indent=2)}

{validation_prompt}

For each location stub provided, generate complete location data following the schema.
Ensure locations:
1. Connect logically based on the map layout
2. Support the plot's needs (place key items, NPCs, and clues appropriately)
3. If a location stub already has an NPC entry (like a pre-placed antagonist), you MUST include that NPC. You can enhance their description, but their name and presence are mandatory
4. Vary in purpose and challenge
5. Include a mix of combat, exploration, and roleplay opportunities
6. Feel cohesive as part of the same {area_data.get('areaType', 'area')}

Return a JSON object with a 'locations' array containing all complete location objects.
Each location must include ALL required fields from the location schema.

CRITICAL: Field names must match the schema EXACTLY:
- Use "npcs" NOT "notableNPCs" (must be array of objects with name, description, attitude)
- Use "monsters" NOT "creatures"
- Use "lootTable" NOT "items" (must be array of strings, not objects)
- Use "connectivity" for room connections
- Use "areaConnectivity" for connections to other areas
- Use "areaConnectivityId" for area connection IDs (empty array [] if no connections to other areas, NEVER include current area ID)
- Use "plotHooks" NOT "clues"
- Use "dmInstructions" for DM-specific notes
- Use "doors" for door information (ALL fields required: name, description, type, locked, lockDC, breakDC, keyname, trapped, trap)
- Use "traps" for trap details (must include detectDC, disableDC, triggerDC, damage)
- Use "dcChecks" in format "SkillName DC XX: Description"
- Include "accessibility" (describe how easily the location can be accessed)
- Include "dangerLevel" (must be "Low", "Medium", "High", or "Very High")
- Include "features" (array of objects with name and description)

DOOR STRUCTURE: Every door must have ALL these fields:
- name (string): e.g., "North Door", "Secret Panel"
- description (string): physical appearance
- type (string): e.g., "regular", "secret", "heavy"
- locked (boolean): true or false
- lockDC (integer): difficulty to pick (0 if not locked)
- breakDC (integer): difficulty to force open
- keyname (string): what opens it (empty string if none)
- trapped (boolean): true or false
- trap (string): trap description (empty string if not trapped)

AREA CONNECTIVITY RULES:
- areaConnectivityId should be [] for locations that don't connect to other areas
- Only include other area IDs when location explicitly connects to different areas
- NEVER include the location's own area ID in areaConnectivityId

Check the location schema carefully for all required fields.
Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols.
"""

        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            main_cfg = config.DM_MAIN_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            main_cfg = config.DM_MAIN_GEMINI_PRO_LOW
        elif MODEL_PROVIDER == "lmstudio":
            main_cfg = config.DM_MAIN_LMSTUDIO
        else:  # legacy
            main_cfg = config.DM_MAIN_LEGACY

        response = capture_and_fanout("T026", api_client.create_completion,
            messages=[
                {"role": "system", "content": "You are an expert 5e dungeon designer creating cohesive, interconnected locations."},
                {"role": "user", "content": batch_prompt}
            ],
            model=main_cfg["model"],
            temperature=0.8,
            response_format={"type": "json_object"},
            **{k: v for k, v in main_cfg.items() if k != "model"})

        return json.loads(response.choices[0].message.content)
    
    def generate_locations(self,
                          area_data: Dict[str, Any],
                          plot_data: Dict[str, Any],
                          module_data: Dict[str, Any],
                          context=None,
                          excluded_names=None,
                          context_header: str = "") -> Dict[str, Any]:
        """Generate all locations for an area"""
        
        # Get location stubs from area data or create from map
        location_stubs = area_data.get("locations", [])
        
        if not location_stubs and "map" in area_data:
            # Create location stubs from map rooms
            location_stubs = []
            for room in area_data.get("map", {}).get("rooms", []):
                location_stub = {
                    "locationId": room["id"],
                    "name": room["name"],
                    "type": room["type"],
                    "connections": room["connections"],
                    "coordinates": room["coordinates"]
                }
                location_stubs.append(location_stub)
        
        if not location_stubs:
            print("DEBUG: [Location Generator] Warning: No location stubs or map found in area data")
            return {"locations": []}
        
        print(f"DEBUG: [Location Generator] Generating {len(location_stubs)} locations for {area_data.get('areaName', 'area')}...")
        
        # Generate all locations in batch
        location_data = self.generate_location_batch(
            area_data, plot_data, module_data, location_stubs, context, excluded_names, context_header)
        
        # Ensure each location has required fields and connections
        locations = location_data.get("locations", [])
        
        # Post-process to ensure consistency
        location_ids = set()
        for loc in locations:
            if isinstance(loc, dict) and "locationId" in loc:
                location_ids.add(loc["locationId"])
        
        for location in locations:
            # Validate connections exist
            raw_connectivity = location.get("connectivity", [])
            validated_connectivity = []
            
            for conn in raw_connectivity:
                # Handle both string and dict formats
                if isinstance(conn, str):
                    if conn in location_ids:
                        validated_connectivity.append(conn)
                elif isinstance(conn, dict) and "locationId" in conn:
                    if conn["locationId"] in location_ids:
                        validated_connectivity.append(conn["locationId"])
            
            location["connectivity"] = validated_connectivity
            
            # CRITICAL FIX: Update context with actual NPC placements
            if context:
                area_id = area_data.get("areaId")
                location_id = location.get("locationId")
                for npc in location.get("npcs", []):
                    npc_name = npc.get("name")
                    # --- CHANGE IS HERE ---
                    npc_description = npc.get("description", "")  # Get the description
                    if npc_name and area_id and location_id:
                        # Update context with full NPC info for better matching
                        context.add_npc(
                            npc_name=npc_name, 
                            area_id=area_id, 
                            location_id=location_id,
                            description=npc_description  # Pass the description
                        )
                        print(f"DEBUG: [Location Generator] Registered/Updated context for: {npc_name} in {area_id}:{location_id}")
            
            # Ensure plot-critical locations have appropriate content
            location_id = location["locationId"]
            
            # Check if this location is referenced in plot
            for plot_point in plot_data.get("plotPoints", []):
                if plot_point.get("location") == location_id:
                    # This is a plot-critical location
                    if not location.get("plotHooks"):
                        location["plotHooks"] = []
                    
                    # Add a plot hook if not already present
                    plot_hint = f"This area seems connected to {plot_point.get('title', 'current events')}"
                    if plot_hint not in location["plotHooks"]:
                        location["plotHooks"].append(plot_hint)
            
            # Set default values for optional fields
            if "encounters" not in location:
                location["encounters"] = []
            if "adventureSummary" not in location:
                location["adventureSummary"] = ""
        
        # Post-process: ensure name consistency between map and locations
        if "map" in area_data and "rooms" in area_data["map"]:
            for location in locations:
                # Find the corresponding map room
                for room in area_data["map"]["rooms"]:
                    if room["id"] == location["locationId"]:
                        # If names differ, update map room name to match location
                        if room["name"] != location["name"]:
                            room["name"] = location["name"]
                            print(f"DEBUG: [Location Generator] Updated map room {room['id']} name to match location: {location['name']}")
                        break
        
        return {"locations": locations}
    
    def validate_locations(self, location_data: Dict[str, Any]) -> List[str]:
        """Validate location data against schema and logical consistency"""
        errors = []
        
        # Schema validation for the container
        try:
            # Validate each location individually
            for location in location_data.get("locations", []):
                jsonschema.validate({"locations": [location]}, self.schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
            return errors
        
        # Content validation
        locations = location_data.get("locations", [])
        location_ids = {loc["locationId"] for loc in locations}
        
        for location in locations:
            loc_id = location["locationId"]
            
            # Check connections are valid
            for conn_id in location.get("connectivity", []):
                if conn_id not in location_ids:
                    errors.append(f"Location {loc_id} connects to non-existent location {conn_id}")
            
            # Check trap DCs are reasonable
            for trap in location.get("traps", []):
                for dc_field in ["detectDC", "disableDC"]:
                    dc_value = trap.get(dc_field, 0)
                    if dc_value < 10 or dc_value > 30:
                        errors.append(f"Location {loc_id} trap '{trap['name']}' has unreasonable {dc_field}: {dc_value}")
            
            # Check danger level consistency
            danger_level = location.get("dangerLevel", "Medium")
            monster_count = sum(m.get("quantity", {}).get("max", 0) for m in location.get("monsters", []))
            trap_count = len(location.get("traps", []))
            
            if danger_level == "Low" and (monster_count > 2 or trap_count > 1):
                errors.append(f"Location {loc_id} marked as Low danger but has many threats")
            elif danger_level == "Very High" and (monster_count == 0 and trap_count == 0):
                errors.append(f"Location {loc_id} marked as Very High danger but has no threats")
        
        return errors
    
    def save_locations(self, location_data: Dict[str, Any], area_id: str, module_name: str = None):
        """Save location data to file using ModulePathManager"""
        path_manager = ModulePathManager(module_name)
        
        # Ensure areas directory exists
        path_manager.ensure_areas_directory()
        
        # Get the proper area file path
        filename = path_manager.get_area_path(area_id)
        
        # Update the area file with full location data if it exists
        if os.path.exists(filename):
            with open(filename, "r") as f:
                area_data = json.load(f)
            
            area_data["locations"] = location_data["locations"]
            
            with open(filename, "w") as f:
                json.dump(area_data, f, indent=2)
            
            print(f"DEBUG: [Location Generator] Updated area file with locations: {filename}")
        else:
            # If area file doesn't exist, just save locations
            with open(filename, "w") as f:
                json.dump(location_data, f, indent=2)
            
            print(f"DEBUG: [Location Generator] Saved locations to: {filename}")

def main():
    """Interactive location generator for testing"""
    generator = LocationGenerator()
    
    print("Location Generator Test")
    print("-" * 50)
    
    # Mock data for testing
    mock_module = {
        "moduleName": "Echoes of the Elemental Forge",
        "moduleDescription": "Ancient dwarven magic threatens the realm",
        "worldSettings": {
            "era": "Age of Reclamation",
            "magicPrevalence": "uncommon"
        }
    }
    
    mock_area = {
        "areaId": "EM001",
        "areaName": "Ember Hollow Mines",
        "areaType": "dungeon",
        "areaDescription": "Abandoned dwarven mines with elemental activity",
        "dangerLevel": "medium",
        "recommendedLevel": 3,
        "locations": [
            {"locationId": "R01", "name": "Mine Entrance", "type": "entrance", "connections": ["R02"]},
            {"locationId": "R02", "name": "Guard Post", "type": "room", "connections": ["R01", "R03"]},
            {"locationId": "R03", "name": "Main Shaft", "type": "corridor", "connections": ["R02", "R04", "R05"]},
            {"locationId": "R04", "name": "Crystal Chamber", "type": "chamber", "connections": ["R03"]},
            {"locationId": "R05", "name": "Forge Room", "type": "hall", "connections": ["R03"]}
        ]
    }
    
    mock_plot = {
        "plotTitle": "Secrets of the Ember Forge",
        "mainObjective": "Stop the Ember cult from awakening the forge",
        "plotPoints": [
            {
                "id": "PP001",
                "title": "The Abandoned Mine",
                "description": "Investigate strange activities in the old mines",
                "location": "R01"
            },
            {
                "id": "PP002", 
                "title": "The Crystal Discovery",
                "description": "Find the source of the elemental crystals",
                "location": "R04"
            }
        ]
    }
    
    # Generate locations
    print("\nGenerating locations...")
    locations = generator.generate_locations(mock_area, mock_plot, mock_module)
    
    # Validate
    errors = generator.validate_locations(locations)
    if errors:
        print("\nValidation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\nValidation successful!")
        
        # Save
        generator.save_locations(locations, mock_area["areaId"])
        
        # Display summary
        print(f"\nGenerated {len(locations.get('locations', []))} locations")
        for loc in locations.get("locations", []):
            print(f"  - {loc['locationId']}: {loc['name']} ({loc['type']})")
            print(f"    Danger: {loc.get('dangerLevel', 'Unknown')}")
            print(f"    Monsters: {len(loc.get('monsters', []))}")
            print(f"    NPCs: {len(loc.get('npcs', []))}")
            print(f"    Traps: {len(loc.get('traps', []))}")

if __name__ == "__main__":
    main()