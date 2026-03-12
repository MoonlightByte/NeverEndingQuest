# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# level_up.py - Simplified level up system that returns changes dict

import json
from openai import OpenAI
from config import OPENAI_API_KEY, LEVEL_UP_MODEL
from .file_operations import safe_read_json
from .xp_progression_utils import get_next_level_threshold

client = OpenAI(api_key=OPENAI_API_KEY)

def load_leveling_info():
    """Load leveling information from text file"""
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, '..')
    file_path = os.path.join(project_root, "prompts/leveling/leveling_info.txt")
    with open(file_path, "r") as file:
        return file.read().strip()

def get_level_up_guidance(character_name, current_level, new_level):
    """Get interactive guidance for player level up"""
    return f"""Leveling Dungeon Master Guidance: Proceed with leveling up {character_name} from level {current_level} to {new_level}. 

Ask the player about their choices:
- Hit Points: Do they want to roll their hit die or take the average?
- If they gain spell slots, which spells do they want to prepare?
- If they gain a feat or ability score improvement, what do they choose?
- Any other class-specific choices

Once all decisions are made, use the updateCharacterInfo action to apply ALL changes at once. Include:
- Set level to {new_level}
- Update hit points and max hit points based on their choice
- Preserve the current cumulative experience_points value
- Set exp_required_for_next_level to the cumulative XP threshold for the NEXT level after {new_level}
- Add any new class features
- Update spell slots if applicable
- Apply any other changes

Remember to explain each new feature they gain!"""

def get_npc_level_up_changes(character_name, character_data, current_level, new_level):
    """Get automatic level up changes for an NPC"""
    
    # Load leveling information
    leveling_info = load_leveling_info()
    
    # Build AI prompt for NPC level up
    prompt = f"""You are leveling up an NPC named {character_name} from level {current_level} to {new_level}.

Current character data:
{json.dumps(character_data, indent=2)}

Leveling information:
{leveling_info}

For this NPC level up:
1. Calculate HP increase (always take average + CON modifier)
2. List all new class features gained
3. Update spell slots if applicable
4. Determine new experience requirement for next level

Respond with ONLY a JSON object containing the changes to apply. Do not include unchanged fields.
The response must be a valid JSON object with these changes:
- level: {new_level}
- hitPoints: (new value)
- maxHitPoints: (new value)  
- experience_points: keep the current cumulative XP value from the character data
- exp_required_for_next_level: cumulative XP threshold for the NEXT level after {new_level}
- classFeatures: (array of new features to ADD, not replace)
- Any other fields that change

Example response format:
{{
    "level": 2,
    "hitPoints": 18,
    "maxHitPoints": 18,
    "experience_points": 300,
    "exp_required_for_next_level": 900,
    "classFeatures": [
        {{
            "name": "Action Surge",
            "description": "On your turn, you can take one additional action. Once per short rest.",
            "source": "Fighter",
            "usage": {{
                "current": 1,
                "max": 1,
                "refreshOn": "shortRest"
            }}
        }}
    ]
}}"""

    try:
        # Get AI response
        response = client.chat.completions.create(
            model=LEVEL_UP_MODEL,
            messages=[
                {"role": "system", "content": "You are a 5th edition of the world's most popular roleplaying game rules expert. Provide only valid JSON responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3  # Low temperature for consistency
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Remove markdown if present
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0].strip()
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0].strip()
        
        # Parse the changes
        changes = json.loads(ai_response)

        # Preserve cumulative XP semantics and deterministically repair
        # next-level threshold from the target level.
        current_xp = character_data.get("experience_points", 0)
        changes["experience_points"] = current_xp
        changes["exp_required_for_next_level"] = get_next_level_threshold(new_level)
        changes["level"] = new_level
        
        # Handle classFeatures properly - we need to merge with existing
        if "classFeatures" in changes and character_data.get("classFeatures"):
            # Combine existing features with new ones
            existing_features = character_data["classFeatures"]
            new_features = changes["classFeatures"]
            # Create combined list
            all_features = existing_features + new_features
            changes["classFeatures"] = all_features
        
        return {
            "success": True,
            "changes": changes,
            "summary": f"{character_name} advanced to level {new_level}!"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to generate level up changes: {str(e)}"
        }

def run_level_up_process(character_name, current_level=None, new_level=None):
    """
    Simplified level up process that returns changes or guidance
    
    Returns:
        For players: {"success": True, "interactive": True, "guidance": "..."}
        For NPCs: {"success": True, "changes": {...}, "summary": "..."}
    """
    
    # Load character data
    file_name = f"{character_name}.json"
    character_data = safe_read_json(file_name)
    
    if not character_data:
        # Try with characters/ prefix
        file_name = f"characters/{character_name}.json"
        character_data = safe_read_json(file_name)
    
    if not character_data:
        return {
            "success": False,
            "error": f"Could not load character data for {character_name}"
        }
    
    # Determine if this is a player or NPC
    is_player = character_data.get('character_role', 'player') == 'player'
    
    # Get levels
    if current_level is None:
        current_level = character_data.get('level', 1)
    if new_level is None:
        new_level = current_level + 1
    
    if is_player:
        # Return guidance for interactive level up
        return {
            "success": True,
            "interactive": True,
            "guidance": get_level_up_guidance(character_name, current_level, new_level)
        }
    else:
        # Get automatic changes for NPC
        return get_npc_level_up_changes(character_name, character_data, current_level, new_level)
