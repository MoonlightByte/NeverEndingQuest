# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Community Tools - Plot Generator
Copyright (c) 2024 MoonlightByte
Licensed under Apache License 2.0

See LICENSE-APACHE file for full terms.
"""

#!/usr/bin/env python3
# ============================================================================
# PLOT_GENERATOR.PY - AI-DRIVEN NARRATIVE CONTENT CREATION
# ============================================================================
#
# ARCHITECTURE ROLE: Content Generation Layer - Narrative Content Creation
#
# This module provides AI-powered plot generation for creating comprehensive
# narrative content with detailed storylines, quest structures, and plot
# progression systems compliant with module schemas.
#
# KEY RESPONSIBILITIES:
# - AI-driven plot and narrative content generation
# - Schema-compliant plot structure creation and validation
# - Quest system integration with module architecture
# - Narrative continuity management across plot elements
# - Plot progression tracking and state management
# - Integration with module builder and content generation pipeline
#

"""
Plot Generator Script
Creates plot JSON files with detailed content based on schema requirements.
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from core.ai import api_client
import config
import jsonschema
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T036", "core/generators/plot_generator.py", 359)
register_callsite("T037", "core/generators/plot_generator.py", 438)


@dataclass
class PlotPromptGuide:
    """Detailed prompts and examples for each plot field"""
    
    plotTitle: str = """
    The plot title should reflect the main theme or conflict of this specific area/module.
    It should complement but not duplicate the module name.
    
    Examples for an area within a larger module:
    - "The Curse of Ember Hollow" (for a haunted mining town)
    - "Secrets of the Sunken Temple" (for an underwater dungeon)
    - "The Baron's Betrayal" (for political intrigue)
    
    Format: Title case, 3-5 words
    Style: Evocative, specific to this adventure segment
    """
    
    mainObjective: str = """
    The primary goal for this specific area/module.
    This should be:
    - A concrete, achievable objective
    - Tied to the module's overall goal
    - Specific to this location/area
    
    Examples:
    - "Discover the source of the elemental disturbances in the mines"
    - "Retrieve the Amulet of Storms from the sunken temple"
    - "Expose Baron Aldric's conspiracy before the harvest festival"
    
    Format: Clear action verb + specific goal
    Length: One sentence, 10-20 words
    """
    
    plotPoints: str = """
    Plot points are the key story beats that drive the adventure forward.
    Each plot point represents a major decision point or revelation.
    
    Typically include 4-8 plot points that:
    - Build upon each other logically
    - Allow for player choice (branching paths)
    - Escalate tension toward climax
    - Include both combat and non-combat challenges
    
    Example plot point:
    {
        "id": "PP001",
        "title": "The Missing Miners",
        "description": "The party learns that several miners have vanished in the 
        lower levels. Investigation reveals strange elemental crystals growing in 
        the abandoned shafts. The foreman suspects sabotage but fears supernatural 
        causes.",
        "location": "R01",
        "nextPoints": ["PP002", "PP003"],
        "status": "not started",
        "plotImpact": "",
        "sideQuests": [
            {
                "id": "SQ001",
                "title": "The Miner's Daughter",
                "description": "Greta begs the party to find her missing father.",
                "involvedLocations": ["R07", "R12"],
                "status": "not started",
                "plotImpact": ""
            }
        ]
    }
    
    Key principles:
    - Each point should present a problem or revelation
    - Description should be 3-5 sentences
    - Include what players learn and what choices they face
    - Connect to specific locations (by locationId)
    - May include side quests that start at this plot point
    """
    
    plotPoints_id: str = """
    Plot point IDs should follow a consistent pattern.
    Format: "PP" + 3-digit number (e.g., "PP001", "PP002")
    
    Number them in rough chronological order, but remember:
    - Players might encounter them out of order
    - Some might be optional
    - Leave gaps for later additions (PP005, PP010, etc.)
    """
    
    plotPoints_title: str = """
    Plot point titles should be evocative and memorable.
    They serve as quick references for the DM.
    
    Examples:
    - "The Bloodstained Journal"
    - "Confrontation at the Bridge"
    - "The Foreman's Secret"
    - "Whispers in the Deep"
    
    Format: 2-4 words, capitalize major words
    Style: Dramatic but not spoiler-heavy
    """
    
    plotPoints_description: str = """
    Plot point descriptions provide the narrative meat.
    They should include:
    
    1. The situation/problem presented
    2. Key information players can discover
    3. NPCs involved (if any)
    4. Potential complications
    5. Hooks to next plot points
    
    Example:
    "The party discovers a bloodstained journal in the abandoned overseer's 
    office. Its pages detail strange visions and mentions of 'the burning 
    whispers' that drove miners mad. The final entry, dated three days ago, 
    speaks of a meeting with 'the Ember Speaker' in the lowest shaft. Several 
    pages have been torn out, and fresh boot prints lead toward the mine's 
    eastern tunnels."
    
    Length: 3-5 sentences
    Style: Present tense, atmospheric but clear
    Include: Concrete details players can act upon
    """
    
    plotPoints_location: str = """
    The location ID where this plot point occurs.
    Must match a locationId from the area's location file.
    
    Examples: "R01", "R14", "R22"
    
    Consider:
    - Some plot points might span multiple locations
    - Use the primary/starting location
    - Ensure the location makes sense for the event
    """
    
    plotPoints_nextPoints: str = """
    Array of plot point IDs that could follow this one.
    This creates the branching narrative structure.
    
    Typically 1-3 next points:
    - 1 next point: Linear progression
    - 2-3 next points: Player choice/branching
    - 0 next points: Conclusion or dead end
    
    Example: ["PP003", "PP004"] means players could go to either PP003 or PP004 next
    
    Design principles:
    - Major choices should lead to different paths
    - Some paths might converge later
    - Include both obvious and hidden connections
    """
    
    plotPoints_status: str = """
    The current status of this plot point.
    Must be one of: "not started", "in progress", "completed"
    
    For initial generation, typically use "not started"
    The game will update these as players progress.
    """
    
    plotPoints_plotImpact: str = """
    Description of how player actions affected this plot point.
    Initially empty (""), filled during gameplay.
    
    Examples of what might be added during play:
    - "Players chose to ally with the kobolds instead of fighting"
    - "The party failed to save the prisoner, changing NPC attitudes"
    - "Players discovered the secret passage, bypassing the trap"
    
    This helps track how the story diverged from expectations.
    """
    
    plotPoints_sideQuests: str = """
    Optional objectives that start at this plot point.
    Side quests should:
    - Provide character development opportunities
    - Offer unique rewards or information
    - Be truly optional (plot can progress without them)
    - Add flavor and depth to the world
    
    Each plot point can have 0-3 associated side quests.
    
    Example side quest:
    {
        "id": "SQ001",
        "title": "The Miner's Daughter",
        "description": "Greta, a young miner, begs the party to find her father 
        who disappeared near the crystal caverns. She offers her father's lucky 
        pickaxe as reward.",
        "involvedLocations": ["R07", "R12"],
        "status": "not started",
        "plotImpact": ""
    }
    """
    
    sideQuests_id: str = """
    Side quest IDs follow the pattern: "SQ" + 3-digit number
    Examples: "SQ001", "SQ002", "SQ003"
    
    Number them by:
    - Likely encounter order
    - Difficulty/level appropriateness
    - Thematic grouping
    """
    
    sideQuests_title: str = """
    Side quest titles should be personal and specific.
    They often reference NPCs or items.
    
    Examples:
    - "The Miner's Daughter"
    - "Crystals for the Alchemist"
    - "The Lost Shrine"
    - "Rat Problem in the Barracks"
    
    Format: 2-4 words
    Style: More personal/mundane than main plot titles
    """
    
    sideQuests_description: str = """
    Side quest descriptions provide hooks and motivation.
    Include:
    - Who gives the quest (if anyone)
    - What needs to be done
    - Why it matters (motivation)
    - What's offered as reward
    
    Example:
    "Old Henrik, the tavern keeper, complains about giant rats in his cellar. 
    They've been stealing his best ale and scaring away customers. He offers 
    free room and board for a week to anyone who clears them out. He mentions 
    the rats seem to come from a crack in the eastern wall."
    
    Length: 2-4 sentences
    Style: Conversational, include personality
    """
    
    sideQuests_involvedLocations: str = """
    Array of location IDs where this quest takes place.
    Can include multiple locations for multi-step quests.
    
    Examples:
    - ["R03"] - Single location quest
    - ["R03", "R08", "R15"] - Multi-location quest
    - ["R12", "R13"] - Quest spanning connected areas
    
    Ensure all referenced locations exist in the area.
    """
    
    sideQuests_status: str = """
    Quest status: "not started", "in progress", "completed"
    Initially "not started" for generation.
    
    Some quests might be:
    - Time-sensitive (fail if not done quickly)
    - Prerequisite-based (unlock after main plot progress)
    - Mutually exclusive (completing one fails another)
    """

class PlotGenerator:
    def __init__(self):
        self.prompt_guide = PlotPromptGuide()
        self.schema = self.load_schema()
    
    def load_schema(self) -> Dict[str, Any]:
        """Load the plot schema for validation"""
        with open("schemas/plot_schema.json", "r") as f:
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
        
        prompt = f"""Generate content for the '{field_path}' field of a 5e adventure plot.

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

        response = capture_and_fanout("T036", api_client.create_completion,
            messages=[
                {"role": "system", "content": "You are an expert 5e adventure designer. Return only the requested data in the exact format needed."},
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

    def generate_plot_structure(self, num_plot_points: int, 
                                context: Dict[str, Any],
                                context_header: str = "") -> Dict[str, Any]:
        """Generate the complete plot structure"""
        
        # Generate a full plot structure in one go for better coherence
        prompt = f"""{context_header}Create a complete plot structure for a 5e adventure with {num_plot_points} main plot points.

Context:
{json.dumps(context.to_dict() if hasattr(context, 'to_dict') else context, indent=2)}

The plot should:
1. Connect logically to the module theme
2. Build tension toward a climactic encounter
3. Provide meaningful player choices
4. Include a mix of combat, exploration, and social challenges
5. Have clear connections between plot points
6. Include 1-3 side quests per plot point where appropriate

Return a JSON object with this structure:
{{
    "plotPoints": [
        {{
            "id": "PP001",
            "title": "...",
            "description": "...",
            "location": "R##",
            "nextPoints": ["PP002", "PP003"],
            "status": "not started",
            "plotImpact": "",
            "sideQuests": [
                {{
                    "id": "SQ001",
                    "title": "...",
                    "description": "...",
                    "involvedLocations": ["R##"],
                    "status": "not started",
                    "plotImpact": ""
                }}
            ]
        }}
    ]
}}

IMPORTANT: Each plot point should have its sideQuests array (can be empty). Side quests are nested within plot points, not at the root level.
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

        response = capture_and_fanout("T037", api_client.create_completion,
            messages=[
                {"role": "system", "content": "You are an expert 5e adventure designer."},
                {"role": "user", "content": prompt}
            ],
            model=main_cfg["model"],
            temperature=0.8,
            response_format={"type": "json_object"},
            **{k: v for k, v in main_cfg.items() if k != "model"})

        return json.loads(response.choices[0].message.content)
    
    def generate_plot(self, module_data: Dict[str, Any], 
                     area_data: Dict[str, Any],
                     location_data: Dict[str, Any],
                     initial_concept: str = None,
                     context=None,
                     context_header: str = "") -> Dict[str, Any]:
        """Generate a complete plot file for an area"""
        
        # Build generation context from existing data
        generation_context = {
            "module": {
                "name": module_data.get("moduleName", ""),
                "description": module_data.get("moduleDescription", ""),
                "mainObjective": module_data.get("mainPlot", {}).get("mainObjective", ""),
                "antagonist": module_data.get("mainPlot", {}).get("antagonist", "")
            },
            "area": {
                "name": area_data.get("regionName", ""),
                "description": area_data.get("regionDescription", ""),
                "dangerLevel": area_data.get("dangerLevel", ""),
                "recommendedLevel": area_data.get("recommendedLevel", 1)
            },
            "availableLocations": [
                {
                    "locationId": loc.get("locationId"),
                    "name": loc.get("name"),
                    "type": loc.get("type"),
                    "description": loc.get("description", "")
                }
                for loc in location_data.get("locations", [])
            ],
            "concept": initial_concept or f"Adventure in {area_data.get('regionName', 'unknown area')}"
        }
        
        # Add validation requirements if context provided
        validation_prompt = ""
        if context and hasattr(context, 'get_validation_prompt'):
            validation_prompt = context.get_validation_prompt()
        
        plot_data = {}
        
        # Create local context dict for field generation
        field_context = {}
        if context and hasattr(context, 'to_dict'):
            field_context = context.to_dict()
        elif isinstance(context, dict):
            field_context = context
        
        # Generate title and objective first
        plot_data["plotTitle"] = self.generate_field("plotTitle", 
            self.schema["properties"]["plotTitle"], field_context)
        field_context["plotTitle"] = plot_data["plotTitle"]
        
        plot_data["mainObjective"] = self.generate_field("mainObjective",
            self.schema["properties"]["mainObjective"], field_context)
        field_context["mainObjective"] = plot_data["mainObjective"]
        
        print(f"Generated plot title: {plot_data['plotTitle']}")
        print(f"Generated main objective: {plot_data['mainObjective']}")
        
        # Generate complete plot structure
        num_plot_points = min(8, max(4, len(location_data.get("locations", [])) // 3))
        
        plot_structure = self.generate_plot_structure(num_plot_points, field_context, context_header)
        
        plot_data["plotPoints"] = plot_structure["plotPoints"]
        
        # Ensure each plot point has proper structure
        for plot_point in plot_data["plotPoints"]:
            if "sideQuests" not in plot_point:
                plot_point["sideQuests"] = []
        
        return plot_data
    
    def validate_plot(self, plot_data: Dict[str, Any], 
                     location_data: Dict[str, Any]) -> List[str]:
        """Validate plot data against schema and logical consistency"""
        errors = []
        
        # Schema validation
        try:
            jsonschema.validate(plot_data, self.schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
            return errors  # Return early if schema invalid
        
        # Content validation
        available_locations = {loc["locationId"] for loc in location_data.get("locations", [])}
        
        # Check plot point locations exist
        for pp in plot_data.get("plotPoints", []):
            if pp["location"] not in available_locations:
                errors.append(f"Plot point {pp['id']} references non-existent location {pp['location']}")
            
            # Check next points exist
            all_pp_ids = {p["id"] for p in plot_data.get("plotPoints", [])}
            for next_id in pp.get("nextPoints", []):
                if next_id not in all_pp_ids:
                    errors.append(f"Plot point {pp['id']} references non-existent next point {next_id}")
            
            # Check side quest locations
            for sq in pp.get("sideQuests", []):
                for loc_id in sq.get("involvedLocations", []):
                    if loc_id not in available_locations:
                        errors.append(f"Side quest {sq['id']} references non-existent location {loc_id}")
        
        # Check for orphaned plot points (no incoming connections)
        all_next_points = set()
        for pp in plot_data.get("plotPoints", []):
            all_next_points.update(pp.get("nextPoints", []))
        
        first_point = plot_data.get("plotPoints", [{}])[0].get("id")
        for pp in plot_data.get("plotPoints", []):
            if pp["id"] != first_point and pp["id"] not in all_next_points:
                errors.append(f"Plot point {pp['id']} is orphaned (no incoming connections)")
        
        return errors
    
    def save_plot(self, plot_data: Dict[str, Any], filename: str = None):
        """Save plot data to file"""
        if filename is None:
            # Generate filename from plot title
            base_name = plot_data.get("plotTitle", "untitled").lower()
            base_name = base_name.replace(" ", "_")
            # Sanitize filename
            base_name = ''.join(c for c in base_name if c.isalnum() or c == '_')
            filename = f"plot_{base_name}.json"
        
        with open(filename, "w") as f:
            json.dump(plot_data, f, indent=2)
        
        print(f"Plot saved to {filename}")

def main():
    generator = PlotGenerator()
    
    print("Plot Generator")
    print("-" * 50)
    
    # For demonstration, create minimal mock data
    mock_module = {
        "moduleName": "Echoes of the Elemental Forge",
        "moduleDescription": "A group of adventurers must uncover the secrets of an ancient dwarven artifact to prevent catastrophic elemental chaos.",
        "mainPlot": {
            "mainObjective": "Prevent the Ember Enclave from misusing the Elemental Forge",
            "antagonist": "Rurik Emberstone, leader of the Ember Enclave"
        }
    }
    
    mock_area = {
        "regionName": "Old Mines of Ember Hollow",
        "regionDescription": "Long-abandoned dwarven mines now showing signs of elemental activity",
        "dangerLevel": "medium",
        "recommendedLevel": 3
    }
    
    mock_locations = {
        "locations": [
            {"locationId": "R01", "name": "Mine Entrance", "type": "entrance"},
            {"locationId": "R02", "name": "Overseer's Office", "type": "room"},
            {"locationId": "R03", "name": "Crystal Cavern", "type": "cavern"},
            {"locationId": "R04", "name": "Underground River", "type": "natural"},
            {"locationId": "R05", "name": "Forge Chamber", "type": "chamber"}
        ]
    }
    
    # Get concept from user or use default
    concept = input("Enter plot concept (or press Enter for default): ").strip()
    if not concept:
        concept = "Investigate elemental disturbances in the abandoned mines and discover their connection to the Elemental Forge"
    
    print(f"\nGenerating plot based on: {concept}")
    print("-" * 50)
    
    # Generate plot
    plot = generator.generate_plot(mock_module, mock_area, mock_locations, concept)
    
    # Validate
    errors = generator.validate_plot(plot, mock_locations)
    if errors:
        print("\nValidation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\nValidation successful!")
        
        # Save
        generator.save_plot(plot)
        
        # Display summary
        print("\nPlot Summary:")
        print(f"Title: {plot['plotTitle']}")
        print(f"Objective: {plot['mainObjective']}")
        print(f"Plot Points: {len(plot.get('plotPoints', []))}")
        
        # Count side quests correctly
        total_side_quests = 0
        for pp in plot.get('plotPoints', []):
            total_side_quests += len(pp.get('sideQuests', []))
        print(f"Side Quests: {total_side_quests}")

if __name__ == "__main__":
    main()