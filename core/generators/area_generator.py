# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Community Tools - Area Generator
Copyright (c) 2024 MoonlightByte
Licensed under Apache License 2.0

See LICENSE-APACHE file for full terms.
"""

#!/usr/bin/env python3
# ============================================================================
# AREA_GENERATOR.PY - AI-DRIVEN LOCATION CONTENT CREATION
# ============================================================================
#
# ARCHITECTURE ROLE: Content Generation Layer - Location Content Creation
#
# This module provides AI-powered area and location generation with integrated
# map layouts, creating comprehensive location files that serve as the
# foundation for the module-centric geographic architecture.
#
# KEY RESPONSIBILITIES:
# - AI-driven area and location content generation
# - Map layout creation and ASCII map integration
# - Schema-compliant area file structure creation
# - Geographic relationship management within modules
# - Location feature and description generation
# - Integration with module builder for complete location systems
#

"""
Area Generator Script
Creates area JSON files with map layouts based on module requirements.
"""

import json
import random
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from utils.ai_client_factory import (
    create_chat_client,
    get_model_config,
    handle_provider_error,
)
from model_config import DM_MAIN_MODEL
from utils.module_path_manager import ModulePathManager
from utils.spatial_contract import (
    build_location_aliases,
    resolve_semantic_spatial_plan,
    build_tactical_grid,
)


@dataclass
class AreaConfig:
    """Configuration for area generation"""

    area_type: str = "dungeon"  # dungeon, wilderness, town, mixed
    size: str = "medium"  # small, medium, large
    complexity: str = "moderate"  # simple, moderate, complex
    danger_level: str = "medium"  # low, medium, high, extreme
    recommended_level: int = 1
    num_locations: int = None  # If specified, override size-based calculation


class MapLayoutGenerator:
    """Generates map layouts for areas"""

    def __init__(self):
        self.room_types = {
            "dungeon": [
                "entrance",
                "corridor",
                "chamber",
                "hall",
                "vault",
                "shrine",
                "prison",
                "laboratory",
                "throne room",
                "treasure room",
            ],
            "wilderness": [
                "clearing",
                "grove",
                "cave",
                "ravine",
                "hilltop",
                "riverside",
                "ruins",
                "campsite",
                "crossroads",
                "landmark",
            ],
            "town": [
                "square",
                "market",
                "tavern",
                "shop",
                "temple",
                "guild",
                "residence",
                "gate",
                "warehouse",
                "barracks",
            ],
        }

    def generate_thematic_names(
        self, room_data: List[Dict], area_context: Dict[str, Any]
    ) -> List[str]:
        """
        Use AI to generate thematic, immersive location names based on module context.

        Args:
            room_data: List of room dictionaries with id, type, connections
            area_context: Context including module name, area type, theme, etc.

        Returns:
            List of thematic names matching the room order
        """
        try:
            # Build context for AI
            module_name = area_context.get("module_name", "Unknown Module")
            area_name = area_context.get("area_name", "Unknown Area")
            area_type = area_context.get("area_type", "dungeon")
            theme = area_context.get("theme", "fantasy adventure")

            # Create room list for AI prompt
            room_list = []
            for i, room in enumerate(room_data):
                room_list.append(
                    f"{i + 1}. {room['type'].title()} ({room['id']}) - connects to {len(room['connections'])} other rooms"
                )

            rooms_text = "\\n".join(room_list)

            prompt = f"""You are creating thematic location names for a 5th edition of the world's most popular roleplaying game module called "{module_name}".

AREA CONTEXT:
- Area Name: {area_name}
- Area Type: {area_type}
- Theme: {theme}
- Total Locations: {len(room_data)}

ROOM LIST TO NAME:
{rooms_text}

NAMING REQUIREMENTS:
1. Create unique, memorable names that fit the module's theme
2. Names should be 2-4 words maximum  
3. Avoid generic terms like "Room 1" or including IDs
4. Consider the room's function and connections
5. Names should feel immersive and atmospheric
6. Use evocative adjectives (Ancient, Forgotten, Shattered, etc.)

EXAMPLES OF GOOD NAMES:
- entrance -> "Weathered Gate Chamber"
- throne room -> "Sunken Crown Hall" 
- corridor -> "Whispering Passage"
- shrine -> "Altar of Lost Hopes"
- marketplace -> "Merchant's Circle"

Please respond with ONLY a JSON array of names in the exact order listed above:
["Name 1", "Name 2", "Name 3", ...]

No explanations, just the JSON array of thematic location names."""

            client = create_chat_client()
            config = get_model_config("generate_thematic_names", DM_MAIN_MODEL)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.chat.completions.create(
                        model=config["model"],
                        **config.get("extra_body", {}),
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert at creating immersive 5th edition of the world's most popular roleplaying game location names that enhance storytelling and world-building.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.8,
                    )
                    break
                except Exception as e:
                    error_result = handle_provider_error(e, "generate_thematic_names")
                    if error_result["should_fallback"] and attempt < max_retries - 1:
                        client = create_chat_client(use_fallback=True)
                        continue
                    raise

            response_text = response.choices[0].message.content.strip()

            # Parse JSON response
            import json

            try:
                names = json.loads(response_text)
                if isinstance(names, list) and len(names) == len(room_data):
                    print(
                        f"DEBUG: [Area Generator] AI generated {len(names)} thematic location names for {area_name}"
                    )
                    return names
                else:
                    print(
                        f"DEBUG: [Area Generator] Warning: AI returned {len(names) if isinstance(names, list) else 'invalid'} names, expected {len(room_data)}"
                    )
                    raise ValueError("Invalid AI response format")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"DEBUG: [Area Generator] Error parsing AI response: {e}")
                print(f"DEBUG: [Area Generator] AI Response: {response_text}")
                raise

        except Exception as e:
            print(f"DEBUG: [Area Generator] Error generating thematic names: {e}")
            print("DEBUG: [Area Generator] Falling back to enhanced generic names...")

            # Enhanced fallback with better naming
            fallback_names = []
            for room in room_data:
                room_type = room["type"]
                # Add atmospheric adjectives based on area type
                if area_context.get("area_type") == "dungeon":
                    adjectives = [
                        "Ancient",
                        "Forgotten",
                        "Dark",
                        "Crumbling",
                        "Hidden",
                        "Lost",
                        "Shadowed",
                    ]
                elif area_context.get("area_type") == "wilderness":
                    adjectives = [
                        "Wild",
                        "Misty",
                        "Windswept",
                        "Overgrown",
                        "Sacred",
                        "Remote",
                        "Weathered",
                    ]
                else:  # town
                    adjectives = [
                        "Bustling",
                        "Old",
                        "Grand",
                        "Cobbled",
                        "Noble",
                        "Merchant",
                        "Central",
                    ]

                adj = random.choice(adjectives)
                fallback_names.append(f"{adj} {room_type.title()}")

            return fallback_names

    def generate_layout(
        self,
        num_locations: int,
        prefix: str,
        area_type: str = "dungeon",
        area_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Generate a map layout with connected rooms and AI-generated thematic names"""
        # Calculate grid size
        grid_size = max(5, int((num_locations * 1.5) ** 0.5))

        # Initialize empty grid
        grid = [["   " for _ in range(grid_size)] for _ in range(grid_size)]
        connections = {}
        room_positions = {}

        # Place rooms
        placed_rooms = 0
        attempts = 0

        # Start in center
        center = grid_size // 2
        current_pos = (center, center)

        while placed_rooms < num_locations and attempts < num_locations * 10:
            x, y = current_pos

            if 0 <= x < grid_size and 0 <= y < grid_size and grid[y][x] == "   ":
                room_id = f"{prefix}{placed_rooms + 1:02d}"
                grid[y][x] = room_id
                room_positions[room_id] = (x, y)
                connections[room_id] = []

                # Connect to adjacent rooms
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < grid_size and 0 <= ny < grid_size:
                        neighbor = grid[ny][nx]
                        if neighbor != "   ":
                            connections[room_id].append(neighbor)
                            connections[neighbor].append(room_id)

                placed_rooms += 1

            # Move to a new position
            if placed_rooms > 0:
                # Find an empty spot adjacent to existing rooms
                candidates = []
                for room_id, (rx, ry) in room_positions.items():
                    for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        nx, ny = rx + dx, ry + dy
                        if (
                            0 <= nx < grid_size
                            and 0 <= ny < grid_size
                            and grid[ny][nx] == "   "
                        ):
                            candidates.append((nx, ny))

                if candidates:
                    current_pos = random.choice(candidates)
                else:
                    # Random position if no adjacent spots
                    current_pos = (
                        random.randint(0, grid_size - 1),
                        random.randint(0, grid_size - 1),
                    )

            attempts += 1

        # Clean up grid (remove empty rows/columns)
        cleaned_grid = self.clean_grid(grid)

        # Create room data with basic info first
        room_data = []
        for room_id in sorted(room_positions.keys()):
            x, y = room_positions[room_id]
            room_type = random.choice(self.room_types.get(area_type, ["room"]))

            # Get danger level from area context if available
            danger_level = (
                area_context.get("danger_level", "medium") if area_context else "medium"
            )

            room = {
                "id": room_id,
                "type": room_type,
                "connections": sorted(list(set(connections[room_id]))),
                "coordinates": f"X{x}Y{y}",
                # --- NEW optional fields for AI / navigation ---
                "directions": {},  # filled later by helper
                "tags": [],  # e.g. ["hub","rest","landmark"]
                "purpose": "unknown",  # e.g. "safe_haven","quest_goal","encounter"
                "landmark": False,  # True for hubs/quests
                "dangerLevel": danger_level,  # Pull from area config
            }

            # Auto-tag rooms for better AI understanding
            deg = len(room["connections"])
            if room_type in {"tavern", "campsite", "square", "gate", "entrance"}:
                room["tags"].append(
                    "rest" if room_type in {"tavern", "campsite"} else "hub"
                )
            if deg >= 3:
                room["tags"].append("hub")
            if deg == 1:
                room["landmark"] = True
                room["tags"].append("dead_end")

            # Set purpose based on room type (normalize spaces for comparison)
            normalized_type = room_type.replace(" ", "_")
            if room["purpose"] == "unknown":
                if normalized_type in {
                    "throne_room",
                    "treasure_room",
                    "vault",
                    "boss_chamber",
                }:
                    room["purpose"] = "quest_goal"
                elif room_type in {
                    "cave",
                    "lair",
                    "prison",
                    "hall",
                    "dungeon",
                    "laboratory",
                }:
                    room["purpose"] = "encounter"
                elif room_type in {"entrance", "exit", "gate", "portal", "crossroads"}:
                    room["purpose"] = "transition"
                elif "rest" in room["tags"]:  # Check tags after they're set
                    room["purpose"] = "safe_haven"

            room_data.append(room)

        # Generate AI-powered thematic names if context provided
        if area_context:
            try:
                thematic_names = self.generate_thematic_names(room_data, area_context)
                # Apply the thematic names
                for i, room in enumerate(room_data):
                    room["name"] = thematic_names[i]
            except Exception as e:
                print(f"DEBUG: [Area Generator] Failed to generate thematic names: {e}")
                # Fallback to enhanced generic names
                for room in room_data:
                    room["name"] = f"{room['type'].title()} {room['id']}"
        else:
            # No context provided, use original generic naming
            for room in room_data:
                room["name"] = f"{room['type'].title()} {room['id']}"

        rooms = room_data

        semantic_plan = resolve_semantic_spatial_plan(
            [
                {
                    "id": room.get("id"),
                    "name": room.get("name", ""),
                    "type": room.get("type", "room"),
                    "description": room.get("name", ""),
                    "connections": room.get("connections", []),
                }
                for room in rooms
            ],
            start_x=10,
            start_y=10,
            use_llm=False,
        )

        for room in rooms:
            room_id = room.get("id")
            if not isinstance(room_id, str):
                continue
            room["coordinates"] = semantic_plan["coordinates"].get(
                room_id, room.get("coordinates", "X10Y10")
            )
            room["directions"] = semantic_plan["directions"].get(room_id, {})

        if semantic_plan.get("layout"):
            cleaned_grid = semantic_plan["layout"]

        # Smart startRoom selection
        def pick_start_room(rooms_list):
            # 1) Look for entrance type
            for room in rooms_list:
                if room.get("type") == "entrance":
                    return room["id"]
            # 2) Pick room with highest degree (most connected = hub)
            rooms_by_degree = sorted(
                rooms_list, key=lambda r: len(r.get("connections", [])), reverse=True
            )
            if rooms_by_degree:
                return rooms_by_degree[0]["id"]
            # 3) Fallback to first room
            return rooms_list[0]["id"] if rooms_list else None

        start_room_id = pick_start_room(rooms)

        return {
            "mapId": f"MAP_{prefix}_{placed_rooms}",  # Unique with prefix
            "mapName": f"{area_type.title()} Map",
            "totalRooms": placed_rooms,
            "rooms": rooms,
            "layout": cleaned_grid,
            # --- NEW top-level metadata ---
            "startRoom": start_room_id,
            "version": "1.1",  # Version for future compatibility
            "notes": "Extended schema with AI-friendly navigation fields",
        }

    def clean_grid(self, grid: List[List[str]]) -> List[List[str]]:
        """Remove empty rows and columns from grid"""
        # Find bounds
        min_x, max_x = len(grid[0]), 0
        min_y, max_y = len(grid), 0

        for y in range(len(grid)):
            for x in range(len(grid[0])):
                if grid[y][x] != "   ":
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)

        # Extract non-empty portion
        if min_x <= max_x and min_y <= max_y:
            cleaned = []
            for y in range(min_y, max_y + 1):
                row = []
                for x in range(min_x, max_x + 1):
                    row.append(grid[y][x])
                cleaned.append(row)
            return cleaned

        return [[]]


class AreaGenerator:
    """Generates complete area files"""

    def __init__(self):
        self.map_gen = MapLayoutGenerator()
        self.client = create_chat_client()  # Use factory client

    def generate_area_name_and_description(
        self, initial_name: str, config: AreaConfig
    ) -> tuple[str, str]:
        """
        Generates a thematic area name and description using AI, ensuring the name is
        general enough for a region while locations within it can be specific.
        """
        prompt = f"""You are an expert fantasy world builder. Your task is to refine an area name and write a description for a 5th edition area.

**Initial Concept Name:** "{initial_name}"

**Area Details:**
- Type: {config.area_type}
- Danger Level: {config.danger_level}

**TASK:**
1.  **Refine the Name:** If the initial name is too specific (like a single building or landmark), broaden it into a more general, evocative name for the entire region. For example, if the initial name is "The Old Lighthouse," a better regional name would be "The Shipwreck Coast" or "The Cursed Headlands." If the initial name is already good for a region, you can keep it or make minor improvements.
2.  **Write a Description:** Write 1-2 atmospheric sentences for the refined area name. The description should capture the area's character, include sensory details, and match the danger level.

**CRITICAL RULES:**
- The refined name should describe a whole AREA/REGION, not a single location.
- The description must be for the refined name.

**Return ONLY a JSON object with this exact structure:**
{{
  "refinedName": "Your New, More General Area Name",
  "description": "Your 1-2 sentence atmospheric description."
}}
"""

        try:
            model_config = get_model_config("generate_area_name", DM_MAIN_MODEL)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=model_config["model"],
                        **model_config.get("extra_body", {}),
                        temperature=0.8,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert fantasy world builder specializing in creating evocative names and descriptions for 5th edition of the world's most popular roleplaying game areas.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        response_format={"type": "json_object"},
                    )
                    break
                except Exception as e:
                    error_result = handle_provider_error(e, "generate_area_name")
                    if error_result["should_fallback"] and attempt < max_retries - 1:
                        self.client = create_chat_client(use_fallback=True)
                        continue
                    raise

            result = json.loads(response.choices[0].message.content)
            refined_name = result.get("refinedName", initial_name)
            description = result.get(
                "description", f"A mysterious area known as {initial_name}."
            )

            return refined_name, description

        except Exception as e:
            print(
                f"DEBUG: [Area Generator] Warning: AI name/description generation failed: {e}"
            )
            # Fallback to a simple but functional name and description
            return (
                initial_name,
                f"A {config.danger_level} {config.area_type} area known as {initial_name}.",
            )

    def generate_area(
        self,
        area_name: str,
        area_id: str,
        module_context: Dict[str, Any],
        config: AreaConfig,
        prefix: str,
    ) -> Dict[str, Any]:
        """Generate a complete area file"""

        # Determine number of locations
        if config.num_locations is not None:
            num_locations = config.num_locations
            print(
                f"DEBUG: [AreaGenerator] Using explicit num_locations: {num_locations} for area: {area_name}"
            )
        else:
            # Use size-based calculation if not specified
            location_counts = {
                "small": random.randint(8, 12),
                "medium": random.randint(15, 20),
                "large": random.randint(25, 35),
            }
            num_locations = location_counts.get(config.size, 15)
            print(
                f"DEBUG: [AreaGenerator] Using size-based locations: {num_locations} for size: {config.size}"
            )

        # Generate a refined, general area name and its description
        refined_area_name, area_description = self.generate_area_name_and_description(
            area_name, config
        )

        # Build context for AI location naming using the refined area name
        area_context = {
            "module_name": module_context.get("moduleName", "Unknown Module"),
            "area_name": refined_area_name,  # Use the refined name
            "area_type": config.area_type,
            "theme": module_context.get("moduleDescription", "fantasy adventure"),
            "danger_level": config.danger_level,
            "recommended_level": config.recommended_level,
        }

        # Generate map layout with AI-powered thematic naming
        map_data = self.map_gen.generate_layout(
            num_locations, prefix, config.area_type, area_context
        )

        # Generate locations from map rooms
        locations = []
        for room in map_data.get("rooms", []):
            room_id = room.get("id")
            name = room.get("name")
            room_type = room.get("type", "room")

            # Generate location data matching Keep of Doom schema
            location = {
                "locationId": room_id,
                "name": name,
                "type": room_type,
                "description": f"A {room_type} in {area_name}.",
                "coordinates": room.get("coordinates", "X0Y0"),
                "connectivity": room.get("connections", []),
                "aliases": build_location_aliases(name, room_id),
                "tactical_grid": build_tactical_grid(name, room_type),
                "areaConnectivity": [],
                "areaConnectivityId": [],
                "npcs": [],
                "monsters": [],
                "lootTable": [],
                "plotHooks": [],
                "dmInstructions": f"This {room_type} is part of {area_name}. Adjust encounters based on party strength.",
                "doors": [],
                "traps": [],
                "dcChecks": [],
                "accessibility": "Normal access",
                "dangerLevel": config.danger_level.capitalize(),
                "features": self.generate_location_features(room_type),
                "encounters": [],
                "adventureSummary": "",
            }

            # Add some rare features like traps or hidden items
            if random.random() < 0.2:  # 20% chance
                if config.area_type == "dungeon":
                    location["traps"].append(
                        {
                            "name": "Simple Pressure Plate",
                            "description": "A hidden pressure plate that triggers when stepped on.",
                            "detectDC": 13,
                            "disableDC": 15,
                            "triggerDC": 12,
                            "damage": "1d6 piercing damage from hidden spikes",
                        }
                    )

            locations.append(location)

        # Create area structure
        area_data = {
            "areaId": area_id,
            "areaName": refined_area_name,  # Use the refined name
            "areaType": config.area_type,
            "areaDescription": area_description,  # Use the generated description
            "dangerLevel": config.danger_level,
            "recommendedLevel": config.recommended_level,
            "climate": self.determine_climate(config.area_type),
            "terrain": self.determine_terrain(config.area_type),
            "map": map_data,
            "locations": locations,
            "randomEncounters": self.generate_encounter_table(config),
            "areaFeatures": self.generate_area_features(config),
            "notes": self.generate_dm_notes(config),
            "spatialContractVersion": 1,
        }
        map_data["spatialContractVersion"] = 1

        return area_data

    def generate_area_description(self, area_name: str, config: AreaConfig) -> str:
        """Generate a thematic area description using AI"""
        prompt = f"""Generate a unique, atmospheric description for a 5th edition area named "{area_name}".

Area Details:
- Type: {config.area_type}
- Size: {config.size}
- Complexity: {config.complexity}
- Danger Level: {config.danger_level}
- Recommended Level: {config.recommended_level}

Requirements:
- Write 1-2 sentences that capture the area's atmosphere and character
- Make it unique and evocative, not generic
- Include sensory details appropriate to the area type
- Avoid using the exact phrase "where civilization meets the frontier"
- Match the danger level and complexity in the description

Return ONLY the area description text, no additional formatting or labels."""

        try:
            model_config = get_model_config("generate_area_description", DM_MAIN_MODEL)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=model_config["model"],
                        **model_config.get("extra_body", {}),
                        temperature=0.8,  # Higher temperature for more creative variety
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert fantasy world builder. Create unique, atmospheric descriptions for 5th edition of the world's most popular roleplaying game areas that avoid cliches and generic phrases.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                    )
                    break
                except Exception as e:
                    error_result = handle_provider_error(e, "generate_area_description")
                    if error_result["should_fallback"] and attempt < max_retries - 1:
                        self.client = create_chat_client(use_fallback=True)
                        continue
                    raise

            description = response.choices[0].message.content.strip()

            # Ensure we have a description
            if description and len(description) > 10:
                return description
            else:
                # Fallback to a simple but unique description
                return f"{area_name} presents unique challenges and opportunities for adventurers."

        except Exception as e:
            print(
                f"DEBUG: [Area Generator] Warning: Failed to generate area description via AI: {e}"
            )
            # Fallback to basic description without hardcoded templates
            area_adjectives = {
                "dungeon": ["ancient", "forgotten", "mysterious", "treacherous"],
                "wilderness": ["untamed", "wild", "dangerous", "pristine"],
                "town": ["bustling", "quiet", "prosperous", "troubled"],
                "mixed": ["unique", "varied", "complex", "intriguing"],
            }

            adjective = random.choice(
                area_adjectives.get(config.area_type, ["mysterious"])
            )
            return f"{area_name} is a {adjective} {config.area_type} area with {config.complexity} challenges suitable for level {config.recommended_level} adventurers."

    def determine_climate(self, area_type: str) -> str:
        """Determine appropriate climate for area type"""
        climates = {
            "dungeon": "controlled - cool and damp",
            "wilderness": random.choice(["temperate", "tropical", "arctic", "desert"]),
            "town": "temperate",
            "mixed": "varied",
        }
        return climates.get(area_type, "temperate")

    def determine_terrain(self, area_type: str) -> str:
        """Determine appropriate terrain for area type"""
        terrains = {
            "dungeon": "stone corridors and chambers",
            "wilderness": random.choice(
                ["forest", "mountains", "plains", "swamp", "coast"]
            ),
            "town": "urban streets and buildings",
            "mixed": "varied terrain",
        }
        return terrains.get(area_type, "varied")

    def generate_encounter_table(self, config: AreaConfig) -> List[Dict[str, Any]]:
        """Generate a random encounter table for the area"""
        encounter_types = {
            "low": ["wandering animal", "lost traveler", "environmental hazard"],
            "medium": ["hostile creature", "bandit patrol", "territorial beast"],
            "high": ["monster pack", "enemy squad", "dangerous predator"],
            "extreme": ["boss monster", "elite enemies", "deadly trap"],
        }

        encounters = []
        num_encounters = random.randint(6, 10)

        for i in range(num_encounters):
            roll_range = f"{i * 10 + 1}-{(i + 1) * 10}"
            encounter_type = random.choice(
                encounter_types.get(config.danger_level, ["creature"])
            )

            encounters.append(
                {
                    "roll": roll_range,
                    "encounter": encounter_type,
                    "description": f"A {encounter_type} appropriate for level {config.recommended_level} parties",
                }
            )

        return encounters

    def generate_area_features(self, config: AreaConfig) -> List[str]:
        """Generate notable features for the area"""
        features = {
            "dungeon": [
                "ancient murals",
                "mysterious mechanisms",
                "forgotten shrines",
                "hidden passages",
            ],
            "wilderness": [
                "ancient trees",
                "rock formations",
                "water sources",
                "animal dens",
            ],
            "town": [
                "market square",
                "local tavern",
                "guard posts",
                "merchant quarter",
            ],
            "mixed": ["ruins", "bridges", "crossroads", "landmarks"],
        }

        area_features = features.get(config.area_type, ["interesting locations"])
        return random.sample(area_features, min(3, len(area_features)))

    def generate_location_features(self, room_type: str) -> List[Dict[str, str]]:
        """Generate features for a specific location type"""
        feature_types = {
            "entrance": [
                "weathered door",
                "grand archway",
                "narrow passage",
                "hidden opening",
            ],
            "corridor": ["sconces", "tapestries", "cracks in walls", "echoing sound"],
            "chamber": ["furniture", "fireplace", "wall decorations", "floor symbols"],
            "hall": ["high ceiling", "support columns", "chandeliers", "banners"],
            "vault": [
                "locked chests",
                "shelves",
                "strange containers",
                "preservation magic",
            ],
            "shrine": ["altar", "religious symbols", "offering bowls", "prayer mats"],
            "prison": ["cell bars", "chains", "guard post", "scratches on walls"],
            "laboratory": [
                "workbenches",
                "alchemical equipment",
                "strange ingredients",
                "experiment notes",
            ],
            "clearing": [
                "fallen logs",
                "stone circle",
                "wild flowers",
                "animal tracks",
            ],
            "grove": [
                "ancient trees",
                "mushroom circles",
                "unusual plants",
                "birdsong",
            ],
            "cave": [
                "stalactites",
                "rock formations",
                "underground pool",
                "glowing fungi",
            ],
            "square": ["well", "notice board", "sitting area", "merchant stalls"],
            "market": [
                "vendor stalls",
                "crowd areas",
                "display tables",
                "haggling spots",
            ],
            "tavern": ["bar counter", "tables and chairs", "hearth", "trophy display"],
            "shop": [
                "merchandise displays",
                "counter",
                "backroom storage",
                "specialty items",
            ],
            "temple": [
                "worship area",
                "offering space",
                "religious symbols",
                "ritual items",
            ],
        }

        # Default features if room type not recognized
        default_features = ["dust", "signs of age", "interesting architecture"]

        # Get features for this room type, or use defaults
        room_features = feature_types.get(room_type, default_features)

        # Return 1-3 random features as objects with name and description
        num_features = random.randint(1, min(3, len(room_features)))
        selected_features = random.sample(room_features, num_features)

        # Convert to proper format
        return [
            {
                "name": feature.title(),
                "description": f"A {feature} that adds character to this {room_type}.",
            }
            for feature in selected_features
        ]

    def generate_dm_notes(self, config: AreaConfig) -> str:
        """Generate helpful DM notes for running the area"""
        notes = {
            "dungeon": "Consider lighting sources and trap placement. Underground areas may have limited resources.",
            "wilderness": "Weather and terrain should affect travel times. Random encounters keep exploration tense.",
            "town": "NPCs should have daily routines. Political factions create roleplay opportunities.",
            "mixed": "Balance combat, exploration, and social encounters. Transitions between areas should feel natural.",
        }

        return notes.get(
            config.area_type, "Customize this area to fit your module's needs."
        )

    def save_area(
        self, area_data: Dict[str, Any], filename: str = None, module_name: str = None
    ):
        """Save area data to file using ModulePathManager"""
        path_manager = ModulePathManager(module_name)

        # Ensure areas directory exists
        path_manager.ensure_areas_directory()

        if filename is None:
            # Use ModulePathManager to get the proper area file path
            filename = path_manager.get_area_path(area_data["areaId"])

        # Also save a separate map file (maps stay in root for now)
        map_data = area_data["map"]
        map_filename = path_manager.get_map_path(area_data["areaId"])

        with open(filename, "w") as f:
            json.dump(area_data, f, indent=2)

        with open(map_filename, "w") as f:
            json.dump(map_data, f, indent=2)

        print(f"DEBUG: [Area Generator] Area saved to {filename}")
        print(f"DEBUG: [Area Generator] Map saved to {map_filename}")


def main():
    """Interactive area generator"""
    generator = AreaGenerator()

    print("Area Generator")
    print("-" * 50)

    # Get area configuration
    area_name = input("Area name: ").strip() or "Mysterious Dungeon"
    area_id = input("Area ID (e.g., DG001): ").strip() or "DG001"

    area_type = (
        input("Area type (dungeon/wilderness/town/mixed): ").strip() or "dungeon"
    )
    size = input("Size (small/medium/large): ").strip() or "medium"
    complexity = input("Complexity (simple/moderate/complex): ").strip() or "moderate"
    danger_level = input("Danger level (low/medium/high/extreme): ").strip() or "medium"
    recommended_level = int(
        input("Recommended character level (1-20): ").strip() or "1"
    )

    config = AreaConfig(
        area_type=area_type,
        size=size,
        complexity=complexity,
        danger_level=danger_level,
        recommended_level=recommended_level,
    )

    # Mock module context
    module_context = {"moduleName": "Test Module", "theme": "Classic fantasy adventure"}

    # Generate area
    area_data = generator.generate_area(area_name, area_id, module_context, config)

    # Save
    generator.save_area(area_data)

    print("\nArea generation complete!")
    print(f"Locations: {len(area_data.get('locations', []))}")
    print(f"Danger level: {area_data['dangerLevel']}")


if __name__ == "__main__":
    main()
