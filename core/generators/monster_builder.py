# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Community Tools - Monster Builder
Copyright (c) 2024 MoonlightByte
Licensed under Apache License 2.0

See LICENSE-APACHE file for full terms.
"""

# ============================================================================
# MONSTER_BUILDER.PY - CONTENT GENERATION LAYER - MONSTERS
# ============================================================================
# 
# ARCHITECTURE ROLE: Content Generation Layer - AI-Powered Monster Creation
# 
# This module implements our Factory Pattern for monster creation, using
# AI-powered generation with strict schema validation. It demonstrates our
# "Schema-Driven Development" approach to content creation.
# 
# KEY RESPONSIBILITIES:
# - Generate 5e compliant monsters using AI
# - Validate all generated content against monster schema
# - Handle AI response parsing and cleanup
# - Provide robust error handling and validation feedback
# - Save generated monsters to module-specific directories
# 
# AI GENERATION PIPELINE:
# Schema Template → AI Prompt → Response Generation → JSON Parsing →
# Schema Validation → File Persistence → Path Resolution
# 
# VALIDATION STRATEGY:
# - JSON schema compliance checking
# - Automatic cleanup of AI response artifacts
# - Nested value field flattening
# - 5e rule validation through schema constraints
# 
# ARCHITECTURAL INTEGRATION:
# - Uses ModulePathManager for file operations
# - Integrates with mon_schema.json for validation
# - Called by DMs and automated module generation
# - Implements our "Defense in Depth" validation approach
# 
# DESIGN PATTERNS:
# - Factory Pattern: Creates monsters based on specifications
# - Template Method: Consistent generation and validation pipeline
# - Strategy Pattern: Configurable AI models for generation
# 
# This module exemplifies our approach to AI-powered content generation
# while maintaining strict data integrity and 5e rule compliance.
# ============================================================================

import json
import sys
import os
import re

# Add the project root to the Python path so we can import from utils, core, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from openai import OpenAI
from jsonschema import validate, ValidationError
import config
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T034", "core/generators/monster_builder.py", 181)

# Set script name for logging
set_script_name("monster_builder")

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# Use OPENAI_API_KEY from config
client = OpenAI(api_key=config.OPENAI_API_KEY)
# Note: The original monster_builder.py had a hardcoded API key here.
# It's better practice to use the one from config.py.

def load_schema(file_name):
    try:
        with open(file_name, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"{RED}Error: File {file_name} not found.{RESET}")
        return None
    except json.JSONDecodeError:
        print(f"{RED}Error: Invalid JSON in {file_name}.{RESET}")
        return None

def save_json(file_name, data):
    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(file_name)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"{YELLOW}Created directory: {directory}{RESET}")
        
        with open(file_name, 'w') as file:
            json.dump(data, file, indent=2)
        info(f"SUCCESS: Monster save ({file_name}) - PASS", category="monster_creation")
        return True
    except Exception as e:
        print(f"{RED}Error saving to {file_name}: {str(e)}{RESET}")
        return False

def generate_monster(monster_name, schema, party_level=1):
    # Build context-aware system prompt
    system_content = """You are an assistant that creates monster schema JSON files from a master monster schema template for a 5e game. Given a monster name, create a JSON representation of the monster's stats and abilities according to 5e rules following the monster schema template exactly.

CRITICAL RULE - MONSTER SCALING:
- NEVER scale UP monster stats from their standard values
- Standard monsters (Giant Rat, Goblin, Orc, etc.) MUST use their official stats
- Giant Rat = CR 1/4, 7 HP - regardless of party level
- Goblin = CR 1/4, 7 HP - regardless of party level  
- Orc = CR 1/2, 15 HP - regardless of party level
- For low-level parties (level 1-2), you may scale DOWN hit points, but NEVER scale UP
- To challenge higher level parties, use MORE monsters or DIFFERENT monsters, not buffed versions

CHALLENGE RATING GUIDANCE:
- Party Level 1: CR 1/8 to CR 1/2 for normal encounters, CR 1 for boss encounters
- Party Level 2: CR 1/4 to CR 1 for normal encounters, CR 2 for boss encounters  
- Party Level 3: CR 1/2 to CR 1 for normal encounters, CR 2-3 for boss encounters
- Party Level 4: CR 1/2 to CR 2 for normal encounters, CR 3-4 for boss encounters
- Party Level 5+: Scale accordingly, normal encounters should be CR (level-2) to CR (level), bosses CR (level+1) to CR (level+2)

ENCOUNTER BALANCE:
- "low" danger: Use lower end of CR range
- "medium" danger: Use middle of CR range  
- "high" danger: Use higher end of CR range, consider adding special abilities
- Multiple monsters: Reduce individual CR but increase tactical complexity

NAMING CONVENTIONS:
- ALWAYS use SINGULAR names (e.g., "Orc", "Skeleton", "Goblin")
- NEVER use plural names (e.g., "Orcs", "Skeletons", "Goblins")
- If a plural name is provided, convert to singular form automatically
- For generic names like "Orc_1" or "Bandit_2", use standard Monster Manual names and stats
- For unique names, create custom monsters with that exact name
- For corrupted/themed variants, add appropriate descriptors and abilities

SPELLCASTING MONSTERS:
- If the monster is described as a spellcaster (wizard, sorcerer, cleric, druid, etc.), include the "spellcasting" property
- Human spellcasters should have type "Humanoid", not "Fiend" or other types
- Sorcerers use Charisma, Wizards use Intelligence, Clerics/Druids use Wisdom
- CR 1: Usually has cantrips and 1st level spells (2-3 spell slots)
- CR 2-3: Has cantrips, 1st and 2nd level spells (4-6 total spell slots)
- CR 4-5: Has up to 3rd level spells
- Calculate spell save DC as: 8 + proficiency bonus + ability modifier
- Calculate spell attack bonus as: proficiency bonus + ability modifier
- Choose appropriate spells for the monster's theme and CR

Ensure your new monster JSON adheres to the provided schema template. Do not include any additional properties or nested 'type' and 'value' fields. For non-spellcasters, omit the spellcasting property entirely. Return only the JSON content without any markdown formatting."""

    # Build context-aware user prompt
    user_content = f"""Create a monster named '{monster_name}' using 5e rules.

PARTY LEVEL: {party_level}

CRITICAL NAMING REQUIREMENT:
- The monster name MUST be in SINGULAR form (e.g., "Orc", "Skeleton", "Goblin")
- If the provided name is plural (e.g., "Orcs", "Skeletons", "Goblins"), convert to singular
- Use singular names regardless of how many creatures will be in the encounter

IMPORTANT: If this is a standard monster (Giant Rat, Goblin, Orc, etc.), use the EXACT official stats. Do NOT scale up HP or other stats based on party level. A Giant Rat always has 7 HP, regardless of party level.

Only create custom stats for unique named monsters or special variants (e.g., "Corrupted Giant Rat" or "Elder Goblin").

If this monster name includes terms like 'sorcerer', 'wizard', 'cleric', 'druid', 'warlock', 'mage', or other spellcasting classes, make sure to include the spellcasting property with appropriate spells for their CR.

Schema: {json.dumps(schema)}"""
    
    prompt = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]

    try:
        response = capture_and_fanout("T034", client.chat.completions.create, messages=prompt, model=config.MONSTER_BUILDER_MODEL, temperature=0.7)

        ai_response = response.choices[0].message.content.strip()
        print(f"{YELLOW}AI Response:{RESET}\n{ai_response}")

        # Remove markdown code block if present
        ai_response = re.sub(r'^```json\s*|\s*```$', '', ai_response, flags=re.MULTILINE)

        try:
            monster_data = json.loads(ai_response)
            # Remove the outer "properties" object if it exists
            if "properties" in monster_data:
                monster_data = monster_data["properties"]
            # Remove nested 'value' fields if they exist
            monster_data = remove_nested_values(monster_data)
            validate(instance=monster_data, schema=schema)
            return monster_data
        except json.JSONDecodeError as e:
            print(f"{RED}Error: Invalid JSON in AI response. {str(e)}{RESET}")
            print(f"{YELLOW}Processed AI response:{RESET}\n{ai_response}")
        except ValidationError as e:
            print(f"{RED}Error: Generated monster data does not match schema. {str(e)}{RESET}")
            print(f"{YELLOW}Processed monster data:{RESET}\n{json.dumps(monster_data, indent=2)}") # Added indent for readability
    except Exception as e:
        print(f"{RED}Error: Failed to generate monster data. {str(e)}{RESET}")

    return None

def remove_nested_values(data):
    if isinstance(data, dict):
        return {k: remove_nested_values(v['value'] if isinstance(v, dict) and 'value' in v else v) for k, v in data.items()}
    elif isinstance(data, list):
        return [remove_nested_values(item) for item in data]
    else:
        return data

def main():
    if len(sys.argv) != 2:
        print(f"{RED}Usage: python monster_builder.py <monster_name>{RESET}")
        return

    monster_name_arg = sys.argv[1]
    
    # Get average party level from all character files
    party_level = 1
    try:
        from utils.encoding_utils import safe_json_load
        party_tracker = safe_json_load("party_tracker.json")
        if party_tracker and party_tracker.get("partyMembers"):
            levels = []
            for character_name in party_tracker["partyMembers"]:
                character_data = safe_json_load(f"characters/{character_name}.json")
                if character_data:
                    levels.append(character_data.get("level", 1))
            if levels:
                party_level = round(sum(levels) / len(levels))
    except:
        party_level = 1
    
    schema_data = load_schema("schemas/mon_schema.json")
    if not schema_data:
        return

    generated_monster_data = generate_monster(monster_name_arg, schema_data, party_level)
    if generated_monster_data:
        # Get current module from party tracker for consistent path resolution
        try:
            from utils.encoding_utils import safe_json_load
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        full_path = path_manager.get_monster_path(monster_name_arg)
        if save_json(full_path, generated_monster_data):
            info(f"SUCCESS: Monster creation ({monster_name_arg}) - PASS", category="monster_creation")
        else:
            error(f"FAILURE: Monster save ({monster_name_arg}) - FAIL", category="monster_creation")
            sys.exit(1) # Ensure exit with error code
    else:
        error(f"FAILURE: Monster creation ({monster_name_arg}) - FAIL", category="monster_creation")
        sys.exit(1)  # Exit with an error code

if __name__ == "__main__":
    main()