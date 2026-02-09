# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Character Creator Module
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Handles narrative-aware character creation with level support (1-20).
Provides pause/resume functionality for mid-campaign PC additions.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
import random
import re
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# Import utilities
from utils.file_operations import safe_write_json
from utils.encoding_utils import safe_json_dump, safe_json_load
from utils.startup_wizard import sanitize_json_string
from utils.enhanced_logger import debug, info, warning, error

# Constants
CONVERSATION_HISTORY_FILE = "modules/conversation_history/conversation_history.json"
CONVERSATION_BACKUP_FILE = "modules/conversation_history/conversation_history_backup.json"
CHARACTER_CREATION_MARKER = "modules/conversation_history/creation_mode_active.json"

# DMG Wealth by Level table (for starting equipment above level 1)
WEALTH_BY_LEVEL = {
    1: {"gp": 0, "items": "starting_equipment"},
    2: {"gp": 0, "items": "starting_equipment"},
    3: {"gp": 150, "items": "starting_plus_150gp"},
    4: {"gp": 375, "items": "starting_plus_375gp"},
    5: {"gp": 650, "items": "starting_plus_650gp_plus_uncommon"},
    6: {"gp": 900, "items": "starting_plus_900gp_plus_uncommon"},
    7: {"gp": 1200, "items": "starting_plus_1200gp_plus_uncommon"},
    8: {"gp": 1650, "items": "starting_plus_1650gp_plus_rare"},
    9: {"gp": 2250, "items": "starting_plus_2250gp_plus_rare"},
    10: {"gp": 3000, "items": "starting_plus_3000gp_plus_rare"},
    11: {"gp": 4000, "items": "starting_plus_4000gp_plus_very_rare"},
    12: {"gp": 5250, "items": "starting_plus_5250gp_plus_very_rare"},
    13: {"gp": 6750, "items": "starting_plus_6750gp_plus_very_rare"},
    14: {"gp": 8750, "items": "starting_plus_8750gp_plus_very_rare"},
    15: {"gp": 11250, "items": "starting_plus_11250gp_plus_legendary"},
    16: {"gp": 14500, "items": "starting_plus_14500gp_plus_legendary"},
    17: {"gp": 18750, "items": "starting_plus_18750gp_plus_legendary"},
    18: {"gp": 24250, "items": "starting_plus_24250gp_plus_legendary"},
    19: {"gp": 31250, "items": "starting_plus_31250gp_plus_legendary"},
    20: {"gp": 40000, "items": "starting_plus_40000gp_plus_legendary"},
}

# Experience points required for each level (minimum)
XP_BY_LEVEL = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}

# Transition narrative templates for ambiguous entrances
TRANSITION_TEMPLATES = [
    "A form shifts at the edge of your vision—a silhouette that seems to move with {mannerism} through the {atmosphere}. The {environment_feature} casts uncertain shadows, but something in the figure's bearing tugs at your memory.",
    "From the {location_edge}, a shape emerges—half-seen, half-imagined. The {lighting} plays tricks on your eyes, yet you cannot shake the feeling that this presence is somehow... familiar.",
    "The {atmosphere} stirs, and with it comes a figure. They move with {mannerism}, {distinctive_feature} catching the {lighting} just so. A fragment of memory surfaces, unbidden.",
    "At the periphery of your awareness, something shifts. A silhouette against the {environment_feature}, moving with purpose. The {atmosphere} seems to hold its breath as they approach.",
    "Shadows deepen near the {location_edge}, coalescing into a form that moves with {mannerism}. {distinctive_feature} marks them as no mere wanderer—but do you know this soul?",
]

MANNERISMS = [
    "confident purpose",
    "practiced caution",
    "the ease of one who knows these paths",
    "familiarity with shadow",
    "the grace of trained reflexes",
    "deliberate, measured steps",
]

ATMOSPHERES = [
    "fading light",
    "gathering dusk",
    "mist-shrouded air",
    "the stillness before dawn",
    "wind-touched silence",
    "electric anticipation",
]

ENVIRONMENT_FEATURES = [
    "twisted branches overhead",
    "ancient stonework",
    "shifting mist",
    "flickering torchlight",
    "moonbeams through clouds",
    "rustling leaves",
]

LOCATION_EDGES = [
    "tree line",
    "doorway's shadow",
    "fog's edge",
    "between two pillars",
    "the corner of your vision",
    "where light meets dark",
]

LIGHTING = [
    "failing light",
    "silver moonlight",
    "orange torch-glow",
    "pale dawn",
    "dappled shadows",
    "the last rays of sunset",
]

DISTINCTIVE_FEATURES = [
    "The glint of steel",
    "A particular stance",
    "The cut of their cloak",
    "A familiar sigil",
    "Their silhouette's profile",
    "The rhythm of their stride",
]


def backup_conversation_history() -> bool:
    """
    Backup the current conversation history before entering creation mode.
    
    Returns:
        True if backup successful, False otherwise
    """
    try:
        if os.path.exists(CONVERSATION_HISTORY_FILE):
            # Check if we already have a backup (don't overwrite original narrative)
            if os.path.exists(CONVERSATION_BACKUP_FILE):
                warning("Backup already exists, preserving original narrative", category="character_creation")
                # Still update marker with current info
                marker_data = {
                    "backup_created": datetime.now().isoformat(),
                    "original_file": CONVERSATION_HISTORY_FILE,
                    "backup_file": CONVERSATION_BACKUP_FILE,
                    "note": "Using existing backup - original narrative preserved",
                }
                safe_json_dump(marker_data, CHARACTER_CREATION_MARKER)
                return True
            
            shutil.copy2(CONVERSATION_HISTORY_FILE, CONVERSATION_BACKUP_FILE)
            
            # Create marker file to indicate creation mode is active
            marker_data = {
                "backup_created": datetime.now().isoformat(),
                "original_file": CONVERSATION_HISTORY_FILE,
                "backup_file": CONVERSATION_BACKUP_FILE,
            }
            safe_json_dump(marker_data, CHARACTER_CREATION_MARKER)
            
            info("Conversation history backed up for character creation", category="character_creation")
            return True
        else:
            warning("No conversation history to backup", category="character_creation")
            return False
    except Exception as e:
        error(f"Failed to backup conversation history: {e}", exception=e, category="character_creation")
        return False


def restore_conversation_history() -> bool:
    """
    Restore the conversation history from backup after creation is complete.
    
    Returns:
        True if restore successful, False otherwise
    """
    try:
        if os.path.exists(CONVERSATION_BACKUP_FILE):
            shutil.copy2(CONVERSATION_BACKUP_FILE, CONVERSATION_HISTORY_FILE)
            
            # Remove marker file
            if os.path.exists(CHARACTER_CREATION_MARKER):
                os.remove(CHARACTER_CREATION_MARKER)
            
            info("Conversation history restored after character creation", category="character_creation")
            return True
        else:
            warning("No conversation history backup found to restore", category="character_creation")
            return False
    except Exception as e:
        error(f"Failed to restore conversation history: {e}", exception=e, category="character_creation")
        return False


def is_creation_mode_active() -> bool:
    """Check if character creation mode is currently active."""
    return os.path.exists(CHARACTER_CREATION_MARKER)


def get_party_level(party_tracker_data: Dict[str, Any]) -> int:
    """
    Calculate the average level of the current party.
    
    Args:
        party_tracker_data: The party tracker dictionary
        
    Returns:
        Average party level (rounded), minimum 1
    """
    party_members = party_tracker_data.get("partyMembers", [])
    if not party_members:
        return 1
    
    total_level = 0
    character_count = 0
    
    for member_name in party_members:
        try:
            # Load character file
            char_filename = member_name.lower().replace(" ", "_") + ".json"
            char_path = os.path.join("characters", char_filename)
            
            if os.path.exists(char_path):
                char_data = safe_json_load(char_path)
                if char_data:
                    level = char_data.get("level", 1)
                    total_level += level
                    character_count += 1
        except Exception as e:
            debug(f"Could not load level for {member_name}: {e}", category="character_creation")
            continue
    
    if character_count == 0:
        return 1
    
    average_level = round(total_level / character_count)
    return max(1, min(20, average_level))  # Clamp between 1-20


def calculate_starting_wealth(target_level: int) -> Dict[str, Any]:
    """
    Calculate starting wealth and equipment guidelines for a given level.
    
    Args:
        target_level: The character's starting level (1-20)
        
    Returns:
        Dictionary with gp amount and equipment guidance
    """
    target_level = max(1, min(20, target_level))
    wealth_data = WEALTH_BY_LEVEL.get(target_level, WEALTH_BY_LEVEL[1])
    
    return {
        "level": target_level,
        "experience_points": XP_BY_LEVEL.get(target_level, 0),
        "gold_pieces": wealth_data["gp"],
        "equipment_guidance": wealth_data["items"],
        "exp_required_for_next_level": XP_BY_LEVEL.get(target_level + 1, XP_BY_LEVEL[20]) if target_level < 20 else 0,
    }


def get_wealth_guidance_text(target_level: int) -> str:
    """
    Get human-readable guidance for equipment selection at a given level.
    
    Args:
        target_level: The character's starting level
        
    Returns:
        Guidance text for the LLM
    """
    if target_level <= 2:
        return """STARTING EQUIPMENT (Level 1-2):
- Use standard class starting equipment
- Background provides additional gear and gold
- No additional wealth beyond starting equipment"""
    
    elif target_level <= 4:
        return f"""STARTING EQUIPMENT (Level {target_level}):
- Standard class starting equipment
- Background gear and gold
- PLUS {WEALTH_BY_LEVEL[target_level]['gp']}gp to spend on additional gear
- Focus on mundane equipment, healing potions, and basic adventuring gear"""
    
    elif target_level <= 7:
        return f"""STARTING EQUIPMENT (Level {target_level}):
- Standard class starting equipment
- Background gear
- PLUS {WEALTH_BY_LEVEL[target_level]['gp']}gp
- Consider: Uncommon magic items (cloak of protection, +1 weapon/armor, bag of holding)
- Class-appropriate consumables (spell scrolls, potions)
- Quality adventuring gear"""
    
    elif target_level <= 10:
        return f"""STARTING EQUIPMENT (Level {target_level}):
- Standard class starting equipment
- Background gear
- PLUS {WEALTH_BY_LEVEL[target_level]['gp']}gp
- Should have: Rare magic items appropriate to class (2-3 items)
- Examples: +2 weapons/armor, winged boots, amulet of health
- Class-specific items (spellbooks for wizards, holy symbols for clerics)
- Substantial healing potion supply"""
    
    elif target_level <= 14:
        return f"""STARTING EQUIPMENT (Level {target_level}):
- Standard class starting equipment
- Background gear
- PLUS {WEALTH_BY_LEVEL[target_level]['gp']}gp
- Should have: Very Rare magic items (3-4 items)
- Examples: +3 weapons/armor, belt of giant strength, ring of protection
- Staff of power for spellcasters, legendary weapons for martials
- Significant consumable resources"""
    
    else:  # 15-20
        return f"""STARTING EQUIPMENT (Level {target_level}):
- Standard class starting equipment
- Background gear
- PLUS {WEALTH_BY_LEVEL[target_level]['gp']}gp
- Should have: Legendary-tier magic items (4-5 items)
- Examples: Vorpal sword, staff of the magi, ring of invisibility
- Artifacts or unique items appropriate to character concept
- Vast resources and consumables"""


def generate_ambiguous_transition(
    character_data: Dict[str, Any],
    active_pc_name: str,
    location_context: Dict[str, Any],
    recognition_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate an ambiguous transition narrative for the new character's entrance.
    
    Args:
        character_data: The newly created character's data
        active_pc_name: Name of the currently active PC who gets scene-setting priority
        location_context: Current location information
        recognition_data: Optional dict with recognition info (who recognizes whom)
        
    Returns:
        Transition narrative text
    """
    # Select random elements
    template = random.choice(TRANSITION_TEMPLATES)
    mannerism = random.choice(MANNERISMS)
    atmosphere = random.choice(ATMOSPHERES)
    environment_feature = random.choice(ENVIRONMENT_FEATURES)
    location_edge = random.choice(LOCATION_EDGES)
    lighting = random.choice(LIGHTING)
    distinctive_feature = random.choice(DISTINCTIVE_FEATURES)
    
    # Format the template
    transition = template.format(
        mannerism=mannerism,
        atmosphere=atmosphere,
        environment_feature=environment_feature,
        location_edge=location_edge,
        lighting=lighting,
        distinctive_feature=distinctive_feature,
    )
    
    # Add character-specific details if available
    character_name = character_data.get("name", "the newcomer")
    character_class = character_data.get("class", "adventurer")
    
    # Build the full transition narrative
    full_transition = f"""{transition}

[CHARACTER ENTRANCE: {character_name}]

The figure steps into clearer view. {character_class.capitalize()} by the look of them—the way they carry themselves speaks of {mannerism}.

{active_pc_name}, as the one most attuned to your surroundings, you sense this moment first. How do you react? Do you recognize something in this stranger's bearing, or do you prepare for the unknown?

[AWAITING {active_pc_name}'s response to set the scene...]"""
    
    # Add recognition hook if applicable
    if recognition_data:
        recognized_party_member = recognition_data.get("recognized_party_member")
        connection_type = recognition_data.get("connection_type", "past acquaintance")
        
        if recognized_party_member:
            full_transition += f"""

[RECOGNITION: {character_name} knows {recognized_party_member} from their past—as a {connection_type}. This connection may become clear as the scene unfolds...]"""
    
    return full_transition


def get_level_appropriate_spell_guidance(target_level: int, character_class: str) -> str:
    """
    Get spell preparation guidance for spellcasting classes at a given level.
    
    Args:
        target_level: Character level (1-20)
        character_class: The character's class
        
    Returns:
        Spell guidance text
    """
    # Classes that prepare spells
    prepared_casters = ["cleric", "druid", "paladin", "wizard"]
    known_casters = ["bard", "sorcerer", "warlock", "ranger"]
    
    if character_class.lower() not in prepared_casters + known_casters:
        return ""
    
    spell_slots = calculate_spell_slots(target_level, character_class.lower())
    
    guidance = f"""

SPELLCASTING (Level {target_level} {character_class.capitalize()}):
"""
    
    if character_class.lower() in prepared_casters:
        guidance += f"""- This is a PREPARED spellcaster
- Spellbook/prayer list should include ALL spells available at this level
- Prepared spells selected based on character concept and anticipated needs
- Spell slots available: {format_spell_slots(spell_slots)}"""
    else:
        guidance += f"""- This is a KNOWN spellcaster (spells known permanently)
- Select spells known based on character concept
- Spell slots available: {format_spell_slots(spell_slots)}"""
    
    # Add cantrip guidance
    cantrip_count = get_cantrip_count(target_level, character_class.lower())
    guidance += f"""
- Cantrips known: {cantrip_count} (choose appropriate to character theme)"""
    
    return guidance


def calculate_spell_slots(level: int, character_class: str) -> Dict[str, int]:
    """Calculate spell slots for a given level and class."""
    # Full casters (wizard, sorcerer, bard, cleric, druid)
    full_caster_slots = {
        1: {"level1": 2},
        2: {"level1": 3},
        3: {"level1": 4, "level2": 2},
        4: {"level1": 4, "level2": 3},
        5: {"level1": 4, "level2": 3, "level3": 2},
        6: {"level1": 4, "level2": 3, "level3": 3},
        7: {"level1": 4, "level2": 3, "level3": 3, "level4": 1},
        8: {"level1": 4, "level2": 3, "level3": 3, "level4": 2},
        9: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 1},
        10: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2},
        11: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2, "level6": 1},
        12: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2, "level6": 1},
        13: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2, "level6": 1, "level7": 1},
        14: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2, "level6": 1, "level7": 1},
        15: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2, "level6": 1, "level7": 1, "level8": 1},
        16: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2, "level6": 1, "level7": 1, "level8": 1},
        17: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2, "level6": 1, "level7": 1, "level8": 1, "level9": 1},
        18: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 3, "level6": 1, "level7": 1, "level8": 1, "level9": 1},
        19: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 3, "level6": 2, "level7": 1, "level8": 1, "level9": 1},
        20: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 3, "level6": 2, "level7": 2, "level8": 1, "level9": 1},
    }
    
    # Half casters (paladin, ranger)
    half_caster_slots = {
        1: {}, 2: {"level1": 2}, 3: {"level1": 3}, 4: {"level1": 3},
        5: {"level1": 4, "level2": 2}, 6: {"level1": 4, "level2": 2},
        7: {"level1": 4, "level2": 3}, 8: {"level1": 4, "level2": 3},
        9: {"level1": 4, "level2": 3, "level3": 2}, 10: {"level1": 4, "level2": 3, "level3": 2},
        11: {"level1": 4, "level2": 3, "level3": 3}, 12: {"level1": 4, "level2": 3, "level3": 3},
        13: {"level1": 4, "level2": 3, "level3": 3, "level4": 1}, 14: {"level1": 4, "level2": 3, "level3": 3, "level4": 1},
        15: {"level1": 4, "level2": 3, "level3": 3, "level4": 2}, 16: {"level1": 4, "level2": 3, "level3": 3, "level4": 2},
        17: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 1}, 18: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 1},
        19: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2}, 20: {"level1": 4, "level2": 3, "level3": 3, "level4": 3, "level5": 2},
    }
    
    # Warlock (pact magic)
    warlock_slots = {
        1: {"level1": 1}, 2: {"level1": 2}, 3: {"level2": 2}, 4: {"level2": 2},
        5: {"level3": 2}, 6: {"level3": 2}, 7: {"level4": 2}, 8: {"level4": 2},
        9: {"level5": 2}, 10: {"level5": 2}, 11: {"level5": 3}, 12: {"level5": 3},
        13: {"level5": 3}, 14: {"level5": 3}, 15: {"level5": 3}, 16: {"level5": 3},
        17: {"level5": 4}, 18: {"level5": 4}, 19: {"level5": 4}, 20: {"level5": 4},
    }
    
    if character_class in ["paladin", "ranger"]:
        return half_caster_slots.get(level, {})
    elif character_class == "warlock":
        return warlock_slots.get(level, {})
    else:
        return full_caster_slots.get(level, {})


def format_spell_slots(slots: Dict[str, int]) -> str:
    """Format spell slots for display."""
    if not slots:
        return "None"
    return ", ".join([f"{k.replace('level', '')}st" if k == "level1" else 
                     f"{k.replace('level', '')}nd" if k == "level2" else
                     f"{k.replace('level', '')}rd" if k == "level3" else
                     f"{k.replace('level', '')}th" for k in slots.keys()])


def get_cantrip_count(level: int, character_class: str) -> int:
    """Get number of cantrips known for a class at a given level."""
    cantrip_progression = {
        "wizard": {1: 3, 4: 4, 10: 5},
        "sorcerer": {1: 4, 4: 5, 10: 6},
        "bard": {1: 2, 4: 3, 10: 4},
        "cleric": {1: 3, 4: 4, 10: 5},
        "druid": {1: 2, 4: 3, 10: 4},
        "warlock": {1: 2, 4: 3, 10: 4},
    }
    
    progression = cantrip_progression.get(character_class, {1: 0})
    count = 0
    for lvl, cnt in sorted(progression.items()):
        if level >= lvl:
            count = cnt
    return count


def sanitize_character_data(character_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize character data to ensure it meets schema requirements.
    
    Args:
        character_data: Raw character data from LLM
        
    Returns:
        Sanitized character data
    """
    # Ensure required fields exist
    required_fields = {
        "name": "Unknown Character",
        "race": "Human",
        "class": "Fighter",
        "level": 1,
        "alignment": "True Neutral",
        "abilityScores": {
            "strength": 10, "dexterity": 10, "constitution": 10,
            "intelligence": 10, "wisdom": 10, "charisma": 10
        },
        "hitPoints": {"current": 10, "maximum": 10, "temporary": 0},
        "armorClass": 10,
        "proficiencyBonus": 2,
        "speed": 30,
        "skills": [],
        "savingThrows": [],
        "equipment": [],
        "experience_points": 0,
    }
    
    for field, default_value in required_fields.items():
        if field not in character_data or character_data[field] is None:
            character_data[field] = default_value
    
    # Ensure skills is a list
    if isinstance(character_data.get("skills"), dict):
        character_data["skills"] = list(character_data["skills"].keys())
    elif not isinstance(character_data.get("skills"), list):
        character_data["skills"] = []
    
    # Ensure equipment is a list
    if not isinstance(character_data.get("equipment"), list):
        character_data["equipment"] = []
    
    # Ensure currency exists
    if "currency" not in character_data:
        character_data["currency"] = {"gold": 0, "silver": 0, "copper": 0}
    
    # Ensure character role is set
    character_data["character_role"] = "player"
    character_data["character_type"] = "player"
    
    return character_data


def load_text_file(filename: str) -> str:
    """Load text file content."""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        warning(f"Could not find {filename}", category="character_creation")
        return ""


# Export public API
__all__ = [
    'backup_conversation_history',
    'restore_conversation_history',
    'is_creation_mode_active',
    'get_party_level',
    'calculate_starting_wealth',
    'get_wealth_guidance_text',
    'generate_ambiguous_transition',
    'get_level_appropriate_spell_guidance',
    'sanitize_character_data',
]
