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

from core.ai import api_client
from jsonschema import validate, ValidationError
import config
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.file_operations import safe_write_json
from utils.single_target_generation import (
    load_valid_generated_target,
    single_target_generation,
)
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T034", "core/generators/monster_builder.py", 231)

# Set script name for logging
set_script_name("monster_builder")

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"


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
    """Atomically save JSON to file via safe_write_json.

    Routes through utils.file_operations.safe_write_json so a crash
    mid-write cannot corrupt the target file. Preserves the legacy
    (file_name, data) call order used by existing callers. The parent
    directory is created up-front because safe_write_json does not
    create directories.
    """
    # Create directory if it doesn't exist (safe_write_json does not).
    directory = os.path.dirname(file_name)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory)
            print(f"{YELLOW}Created directory: {directory}{RESET}")
        except OSError as e:
            print(f"{RED}Error creating directory {directory}: {str(e)}{RESET}")
            return False

    if safe_write_json(file_name, data):
        info(f"SUCCESS: Monster save ({file_name}) - PASS", category="monster_creation")
        return True
    print(f"{RED}Error saving to {file_name}: atomic write failed{RESET}")
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

    # Select model config per provider
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        monster_config = config.MONSTER_BUILD_GPT52_NONE
    elif MODEL_PROVIDER == "gemini":
        monster_config = config.MONSTER_BUILD_GEMINI_FLASH_LOW
    elif MODEL_PROVIDER == "lmstudio":
        monster_config = config.MONSTER_BUILD_LMSTUDIO
    else:  # legacy
        monster_config = config.MONSTER_BUILD_LEGACY

    # T034: force Gemini to emit the monster OBJECT, not DM narration. Reuse the
    # mon_schema already passed in (the same one used for jsonschema.validate below)
    # -- no second file load, no None risk. legacy/openai/lmstudio unaffected.
    _extra = {k: v for k, v in monster_config.items() if k != "model"}
    if MODEL_PROVIDER == "gemini":
        from model_config import convert_to_gemini_schema
        _extra["response_schema"] = convert_to_gemini_schema(schema)

    # CH-H1: Retry on JSON parse / schema validation failures. The AI
    # occasionally returns truncated or malformed JSON on the first try;
    # retrying recovers without failing the whole encounter build.
    # Bound by model_config.MAX_VALIDATION_RETRIES (default 1 => 2 total
    # attempts). Network/API exceptions are NOT retried -- only parse and
    # validation errors. Defensive fallback to 1 if the constant is
    # missing or model_config import fails.
    try:
        import model_config as _mc
        _max_retries = getattr(_mc, "MAX_VALIDATION_RETRIES", 1)
    except Exception:
        _max_retries = 1

    last_json_err = None
    last_validation_err = None
    last_ai_response = None
    last_parsed_data = None

    for attempt in range(_max_retries + 1):
        try:
            response = capture_and_fanout("T034", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=prompt,
                model=monster_config["model"],
                temperature=0.7,
                **_extra)

            ai_response = response.choices[0].message.content.strip()
            print(f"{YELLOW}AI Response:{RESET}\n{ai_response}")

            # Remove markdown code block if present
            ai_response = re.sub(r'^```json\s*|\s*```$', '', ai_response, flags=re.MULTILINE)
            last_ai_response = ai_response

            try:
                monster_data = json.loads(ai_response)
                # Remove the outer "properties" object if it exists
                if "properties" in monster_data:
                    monster_data = monster_data["properties"]
                # Remove nested 'value' fields if they exist
                monster_data = remove_nested_values(monster_data)
                last_parsed_data = monster_data
                validate(instance=monster_data, schema=schema)
                return monster_data
            except json.JSONDecodeError as e:
                last_json_err = e
                last_validation_err = None
                warning(
                    f"Monster build attempt {attempt + 1}/{_max_retries + 1} "
                    f"returned invalid JSON: {str(e)}",
                    category="monster_creation",
                )
                continue
            except ValidationError as e:
                last_json_err = None
                last_validation_err = e
                warning(
                    f"Monster build attempt {attempt + 1}/{_max_retries + 1} "
                    f"failed schema validation: {str(e)}",
                    category="monster_creation",
                )
                continue
        except Exception as e:
            # Network / API failures are not retried here -- preserve the
            # original outer-Exception contract.
            print(f"{RED}Error: Failed to generate monster data. {str(e)}{RESET}")
            return None

    # All retries exhausted -- emit the original-style final error
    # messages so log scrapers and operators see the familiar output.
    if last_json_err is not None:
        print(f"{RED}Error: Invalid JSON in AI response. {str(last_json_err)}{RESET}")
        print(f"{YELLOW}Processed AI response:{RESET}\n{last_ai_response}")
    elif last_validation_err is not None:
        print(f"{RED}Error: Generated monster data does not match schema. {str(last_validation_err)}{RESET}")
        print(f"{YELLOW}Processed monster data:{RESET}\n{json.dumps(last_parsed_data, indent=2)}")

    return None

def remove_nested_values(data):
    if isinstance(data, dict):
        return {k: remove_nested_values(v['value'] if isinstance(v, dict) and 'value' in v else v) for k, v in data.items()}
    elif isinstance(data, list):
        return [remove_nested_values(item) for item in data]
    else:
        return data


def _active_module_path_manager():
    """Resolve the same active-module snapshot historically used by main()."""
    try:
        from utils.encoding_utils import safe_json_load

        party_tracker = safe_json_load("party_tracker.json")
        current_module = (
            party_tracker.get("module", "").replace(" ", "_")
            if party_tracker
            else None
        )
        return ModulePathManager(current_module)
    except Exception:
        return ModulePathManager()


def build_monster_file(monster_name, schema, party_level=1, path_manager=None):
    """Generate and save one monster as a deduplicated target transaction."""
    path_manager = path_manager or _active_module_path_manager()
    target_path = path_manager.get_monster_path(monster_name)

    with single_target_generation(target_path) as transaction:
        candidates = [transaction.resolved_target, target_path]
        for candidate in dict.fromkeys(path for path in candidates if path):
            existing = load_valid_generated_target(candidate, schema)
            if existing is not None:
                transaction.remember_target(candidate)
                info(
                    f"SUCCESS: Monster creation ({monster_name}) - already exists",
                    category="monster_creation",
                )
                return existing

        generated = generate_monster(monster_name, schema, party_level)
        if not generated:
            return None
        # Record the intended path before the atomic save. If this process dies
        # after os.replace but before returning, the next waiter still finds it.
        transaction.remember_target(target_path)
        if not save_json(target_path, generated):
            return None
        return generated

def main():
    # Parse args. --party-level is optional for backward compatibility:
    # legacy callers that supply only the monster name still work and
    # fall back to the party_tracker.json read below.
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate a 5e monster JSON file.")
    parser.add_argument("monster_name",
                        help="Name of the monster to generate.")
    parser.add_argument("--party-level", type=int, default=None,
                        help="Average party level for CR scaling. If "
                             "omitted, falls back to reading "
                             "party_tracker.json.")
    args = parser.parse_args()

    monster_name_arg = args.monster_name
    cli_party_level = args.party_level

    # Resolve party level: CLI flag wins, else fall back to reading
    # party_tracker.json (legacy behavior, used only when no --party-level
    # is supplied -- post T5-2 combat_builder always supplies it).
    # If the fallback read raises (corrupt party_tracker.json, parse
    # error in a character file, etc.) we used to silently default to
    # 1, which silently scaled a level-8 party down to CR 1/8 monsters.
    # Instead surface the failure (CH-C1).
    if cli_party_level is not None:
        party_level = cli_party_level
    else:
        party_level = 1
        try:
            from utils.encoding_utils import safe_json_load
            party_tracker = safe_json_load("party_tracker.json")
            if party_tracker and party_tracker.get("partyMembers"):
                levels = []
                for character_name in party_tracker["partyMembers"]:
                    character_data = safe_json_load(
                        f"characters/{character_name}.json")
                    if character_data:
                        levels.append(character_data.get("level", 1))
                if levels:
                    party_level = round(sum(levels) / len(levels))
        except Exception as e:
            print(
                f"{RED}ERROR: Could not read party_tracker.json for "
                f"party level fallback: {e}{RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
    
    schema_data = load_schema("schemas/mon_schema.json")
    if not schema_data:
        return

    generated_monster_data = build_monster_file(
        monster_name_arg, schema_data, party_level
    )
    if generated_monster_data:
        info(f"SUCCESS: Monster creation ({monster_name_arg}) - PASS", category="monster_creation")
    else:
        error(f"FAILURE: Monster creation ({monster_name_arg}) - FAIL", category="monster_creation")
        sys.exit(1)  # Exit with an error code

if __name__ == "__main__":
    main()