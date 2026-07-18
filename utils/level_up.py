# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# level_up.py - Simplified level up system that returns changes dict

import json
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T086", "utils/level_up.py", 162)
from .file_operations import safe_read_json

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
- Set experience_points to 0
- Set exp_required_for_next_level based on the leveling table
- Add any new class features
- Update spell slots if applicable
- Apply any other changes

Remember to explain each new feature they gain!"""

def _dedup_class_features(existing, new):
    """Merge two classFeatures lists without duplicating entries.

    HIGH-5 (#127): the old raw `existing + new` concat duplicated features when a
    partial level-up was retried. Dedup by (name, source) for dict features and by
    value for plain-string features, preserving order (existing first).
    """
    merged = []
    seen = set()
    for feat in (existing or []) + (new or []):
        if isinstance(feat, dict):
            key = (feat.get("name"), feat.get("source"))
        else:
            key = ("__str__", feat)
        if key in seen:
            continue
        seen.add(key)
        merged.append(feat)
    return merged


def _validate_npc_level_up_changes(changes, new_level):
    """Validate T086's required state delta before reporting success."""
    required = {
        "level",
        "hitPoints",
        "maxHitPoints",
        "experience_points",
        "exp_required_for_next_level",
        "classFeatures",
    }
    if not isinstance(changes, dict) or not required.issubset(changes):
        raise ValueError("T086 response is missing required level-up fields")
    if type(changes["level"]) is not int or changes["level"] != new_level:
        raise ValueError("T086 level must exactly match the requested new level")
    for field in ("hitPoints", "maxHitPoints", "experience_points", "exp_required_for_next_level"):
        if type(changes[field]) is not int:
            raise ValueError(f"T086 {field} must be an integer")
    if changes["maxHitPoints"] < 1:
        raise ValueError("T086 maxHitPoints must be positive")
    if not 0 <= changes["hitPoints"] <= changes["maxHitPoints"]:
        raise ValueError("T086 hitPoints must be within the new maximum")
    if changes["experience_points"] != 0:
        raise ValueError("T086 experience_points must reset to zero")
    if changes["exp_required_for_next_level"] < 0:
        raise ValueError("T086 next-level experience cannot be negative")
    if not isinstance(changes["classFeatures"], list) or not all(
        isinstance(feature, (dict, str)) for feature in changes["classFeatures"]
    ):
        raise ValueError("T086 classFeatures must be an array of features")
    return changes

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
- experience_points: 0
- exp_required_for_next_level: (from leveling table)
- classFeatures: (array of new features to ADD, not replace)
- Any other fields that change

Example response format:
{{
    "level": 2,
    "hitPoints": 18,
    "maxHitPoints": 18,
    "experience_points": 0,
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
        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            conv_config = config.LEVELUP_CONV_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            conv_config = config.LEVELUP_CONV_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            conv_config = config.LEVELUP_CONV_LMSTUDIO
        else:  # legacy
            conv_config = config.LEVELUP_CONV_LEGACY

        # Get AI response
        response = capture_and_fanout("T086", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=[
                {"role": "system", "content": "You are a 5th edition of the world's most popular roleplaying game rules expert. Provide only valid JSON responses."},
                {"role": "user", "content": prompt}
            ],
            model=conv_config["model"],
            temperature=0.3,
            **{k: v for k, v in conv_config.items() if k != "model"})
        
        ai_response = response.choices[0].message.content.strip()
        
        # Remove markdown if present
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0].strip()
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0].strip()
        
        # Parse the changes
        changes = _validate_npc_level_up_changes(json.loads(ai_response), new_level)
        
        # Handle classFeatures properly - we need to merge with existing
        if "classFeatures" in changes and character_data.get("classFeatures"):
            # Combine existing features with new ones
            existing_features = character_data["classFeatures"]
            new_features = changes["classFeatures"]
            changes["classFeatures"] = _dedup_class_features(existing_features, new_features)
        
        return {
            "success": True,
            "changes": changes,
            "summary": f"{character_name} advanced to level {new_level}!"
        }
        
    except Exception as e:
        # HIGH-5 (#127): include attempted_changes so a batch caller can decide
        # whether to roll back partially-applied NPCs.
        return {
            "success": False,
            "error": f"Failed to generate level up changes: {str(e)}",
            "attempted_changes": locals().get("changes")
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