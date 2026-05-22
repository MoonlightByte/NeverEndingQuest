# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Community Tools - Npc Builder
Copyright (c) 2024 MoonlightByte
Licensed under Apache License 2.0

See LICENSE-APACHE file for full terms.
"""

# ============================================================================
# NPC_BUILDER.PY - AI-POWERED CHARACTER CREATION
# ============================================================================
#
# ARCHITECTURE ROLE: Content Generation Layer - Character Creation
#
# This module provides comprehensive AI-driven NPC creation with schema validation,
# generating detailed character profiles, stats, and background information
# for integration with the module-centric architecture.
#
# KEY RESPONSIBILITIES:
# - AI-powered NPC character generation with personality and background
# - Schema-compliant character data creation and validation
# - Integration with module path management for file organization
# - Character stat generation with 5th edition of the world's most popular roleplaying game rule compliance
# - NPC profile creation with narrative and mechanical consistency
# - Batch character creation for module population
#

import json
import sys
import os
import re

# Add the project root to the Python path so we can import from utils, core, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jsonschema import validate, ValidationError
import config
from core.ai import api_client
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.character_sheet_contract import repair_required_ammunition_field
from utils.file_operations import safe_write_json
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T035", "core/generators/npc_builder.py", 149)

# Token tracking import
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except ImportError:
    USAGE_TRACKING_AVAILABLE = False

# Set script name for logging
set_script_name("npc_builder")

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# For now, I'll assume OPENAI_API_KEY is correctly defined in your config.py as used by other scripts.

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

def load_prompt(file_name):
    try:
        with open(file_name, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"{RED}Error: File {file_name} not found.{RESET}")
        return None
    except Exception as e:
        print(f"{RED}Error reading {file_name}: {str(e)}{RESET}")
        return None

def save_json(file_name, data):
    """Atomically save JSON to file via safe_write_json.

    Routes through utils.file_operations.safe_write_json so a crash
    mid-write cannot corrupt the target file. Preserves the legacy
    (file_name, data) call order used by existing callers.
    """
    if safe_write_json(file_name, data):
        info(f"SUCCESS: NPC save ({file_name}) - PASS", category="npc_creation")
        return True
    print(f"{RED}Error saving to {file_name}: atomic write failed{RESET}")
    return False

def generate_npc(npc_name, schema, npc_race=None, npc_class=None, npc_level=None, npc_background=None):
    system_prompt_text = load_prompt("prompts/generators/npc_builder_prompt.txt") # Renamed variable
    if not system_prompt_text:
        return None

    system_message = f"""You are an assistant that creates NPC schema JSON files from a master NPC schema template for a 5e game. Given an NPC name and optional details, create a JSON representation of the NPC's stats and abilities according to 5e rules following the NPC schema template exactly. Ensure your new NPC JSON adheres to the provided schema template. Do not include any additional properties or nested 'type' and 'value' fields. Return only the JSON content without any markdown formatting.

NAME HANDLING: The `name` field must preserve the NPC's full name including any title or role prefix (Scout, Guard, Captain, Ranger, etc.). ONLY strip status condition words: 'corrupted', 'wounded', 'elite', 'enhanced'. Examples:
- 'Corrupted Ranger Thane' -> 'Ranger Thane'
- 'Scout Kira' -> 'Scout Kira'
- 'Guard Marcus' -> 'Guard Marcus'

EQUIPMENT REQUIREMENTS: Equip the NPC fully. Minimum 5 equipped items including:
- Armor appropriate for class (studded leather for rogues, chain mail for fighters, etc.)
- Primary weapon (matching class proficiencies)
- Secondary/ranged weapon
- Shield (if class supports and build uses one)
- Class tools (thieves' tools, holy symbol, component pouch, etc.)
- At least 2 adventuring items (backpack, rope, rations, torches, etc.)

RACIAL TRAITS: Include ALL racial traits as separate entries in the racialTraits array. Every trait the race grants must be listed, including ability score increases. Examples:
- Human: [{{"name":"Ability Score Increase","description":"Your ability scores each increase by 1."}},{{"name":"Extra Language","description":"You can speak, read, and write one extra language of your choice."}}]
- Wood Elf: Darkvision, Keen Senses, Fey Ancestry, Trance, Mask of the Wild (5 traits)
- Hill Dwarf: Darkvision, Dwarven Resilience, Dwarven Combat Training, Stonecunning, Dwarven Toughness (5 traits)

Use the following rules information when creating the NPC:

{system_prompt_text}

Adhere strictly to 5e rules and the provided schema."""

    # Create smarter level guidance
    level_guidance = npc_level if npc_level else "1-3 (appropriate for early adventuring parties)"
    
    prompt_messages = [ # Renamed variable
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Create an NPC named '{npc_name}' using 5e rules. Race: {npc_race or 'Any appropriate race'}, Class: {npc_class or 'Any appropriate class'}, Level: {level_guidance}, Background: {npc_background or 'Any appropriate background'}. Schema: {json.dumps(schema)}"}
    ]

    # Select model config per provider
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        npc_config = config.NPC_BUILD_GPT52_NONE
    elif MODEL_PROVIDER == "gemini":
        npc_config = config.NPC_BUILD_GEMINI_FLASH_MINIMAL
    elif MODEL_PROVIDER == "lmstudio":
        npc_config = config.NPC_BUILD_LMSTUDIO
    else:  # legacy
        npc_config = config.NPC_BUILD_LEGACY

    # CH-H1: Retry on JSON parse / schema validation failures. The AI
    # occasionally returns truncated or malformed JSON on the first try;
    # retrying recovers without failing the whole combat/module build.
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
            response = capture_and_fanout("T035", api_client.create_completion,
                messages=prompt_messages,
                model=npc_config["model"],
                temperature=0.7,
                **{k: v for k, v in npc_config.items() if k != "model"})

            ai_response = response.choices[0].message.content.strip()
            #print(f"{YELLOW}AI Response:{RESET}\n{ai_response}")

            # Remove markdown code block if present
            ai_response = re.sub(r'^```json\s*|\s*```$', '', ai_response, flags=re.MULTILINE)
            last_ai_response = ai_response

            try:
                npc_data = json.loads(ai_response)
                # Remove nested 'value' fields if they exist
                npc_data = remove_nested_values(npc_data)
                npc_data, _ = repair_required_ammunition_field(npc_data)
                last_parsed_data = npc_data
                validate(instance=npc_data, schema=schema)
                return npc_data
            except json.JSONDecodeError as e:
                last_json_err = e
                last_validation_err = None
                warning(
                    f"NPC build attempt {attempt + 1}/{_max_retries + 1} "
                    f"returned invalid JSON: {str(e)}",
                    category="npc_creation",
                )
                continue
            except ValidationError as e:
                last_json_err = None
                last_validation_err = e
                warning(
                    f"NPC build attempt {attempt + 1}/{_max_retries + 1} "
                    f"failed schema validation: {str(e)}",
                    category="npc_creation",
                )
                continue
        except Exception as e:
            # Network / API failures are not retried here -- preserve the
            # original outer-Exception contract.
            print(f"{RED}Error: Failed to generate NPC data. {str(e)}{RESET}")
            return None

    # All retries exhausted -- emit the original-style final error
    # messages so log scrapers and operators see the familiar output.
    if last_json_err is not None:
        print(f"{RED}Error: Invalid JSON in AI response. {str(last_json_err)}{RESET}")
        print(f"{YELLOW}Processed AI response:{RESET}\n{last_ai_response}")
    elif last_validation_err is not None:
        print(f"{RED}Error: Generated NPC data does not match schema. {str(last_validation_err)}{RESET}")
        print(f"{YELLOW}Problematic NPC data:{RESET}\n{json.dumps(last_parsed_data, indent=2)}")

    return None

def remove_nested_values(data):
    if isinstance(data, dict):
        # Check if it's a dict with only 'value' and possibly 'type' keys
        # This was a specific pattern you wanted to remove.
        # However, the more general approach from generate_npc was:
        # remove_nested_values(v['value'] if isinstance(v, dict) and 'value' in v else v)
        # Let's stick to the logic that was in generate_npc for this function.
        new_dict = {}
        for k, v in data.items():
            if isinstance(v, dict) and 'value' in v and len(v) == 1: # Simple {'value': ...} case
                new_dict[k] = remove_nested_values(v['value'])
            elif isinstance(v, dict) and 'value' in v and 'type' in v and len(v) == 2: # {'type':..., 'value':...} case
                 new_dict[k] = remove_nested_values(v['value'])
            else:
                new_dict[k] = remove_nested_values(v)
        return new_dict
    elif isinstance(data, list):
        return [remove_nested_values(item) for item in data]
    else:
        return data

def main():
    # Use argparse so we can accept --party-level alongside the existing
    # positional args. Positional args remain optional for backward
    # compatibility with any legacy callers.
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate a 5e NPC JSON file.")
    parser.add_argument("npc_name", help="Name of the NPC to generate.")
    parser.add_argument("race", nargs="?", default=None,
                        help="Optional race override.")
    parser.add_argument("npc_class", nargs="?", default=None,
                        help="Optional class override.")
    parser.add_argument("level", nargs="?", default=None,
                        help="Optional explicit NPC level (integer or "
                             "empty string).")
    parser.add_argument("background", nargs="?", default=None,
                        help="Optional background override.")
    parser.add_argument("--party-level", type=int, default=None,
                        help="Average party level. When supplied, overrides "
                             "the default 'level 1-3' guidance used for "
                             "NPC creation if no explicit level is given.")
    args = parser.parse_args()

    npc_name_arg = args.npc_name
    npc_race_arg = args.race
    npc_class_arg = args.npc_class

    # Parse explicit positional level (preserve legacy validation).
    npc_level_arg = None
    if args.level is not None and args.level != "":
        if args.level.isdigit():
            try:
                npc_level_arg = int(args.level)
            except ValueError:
                print(f"{RED}Error: Level must be an integer.{RESET}")
                sys.exit(1)
        else:
            print(f"{RED}Error: Level must be an integer or empty if not specified.{RESET}")
            sys.exit(1)

    npc_background_arg = args.background

    # If no explicit positional level was supplied, use --party-level as
    # the level guidance so the NPC is scaled to the party.
    if npc_level_arg is None and args.party_level is not None:
        npc_level_arg = args.party_level

    debug(f"INPUT_PROCESSING: Received arguments - Name: {npc_name_arg}, Race: {npc_race_arg}, Class: {npc_class_arg}, Level: {npc_level_arg}, Background: {npc_background_arg}", category="npc_creation")

    npc_schema_data = load_schema("schemas/char_schema.json") # Use unified character schema
    if not npc_schema_data:
        sys.exit(1)

    generated_npc_data = generate_npc(npc_name_arg, npc_schema_data, npc_race_arg, npc_class_arg, npc_level_arg, npc_background_arg) # Renamed variable
    if generated_npc_data:
        # Extract the clean name from the generated JSON data.
        # This ensures the filename matches the character's actual name.
        # It falls back to the original argument if the 'name' field is missing.
        clean_npc_name = generated_npc_data.get("name", npc_name_arg)
        
        # Get current module from party tracker for consistent path resolution
        try:
            from utils.encoding_utils import safe_json_load
            party_tracker = safe_json_load("party_tracker.json")
            current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
            path_manager = ModulePathManager(current_module)
        except:
            path_manager = ModulePathManager()  # Fallback to reading from file
        
        # Use the 'clean_npc_name' to generate the file path
        full_path = path_manager.get_character_unified_path(clean_npc_name)  # Force unified path
        
        # Ensure characters directory exists
        characters_dir = os.path.dirname(full_path)
        os.makedirs(characters_dir, exist_ok=True)
        if save_json(full_path, generated_npc_data):
            info(f"SUCCESS: NPC creation ({clean_npc_name}) - PASS", category="npc_creation")
        else:
            error(f"FAILURE: NPC save ({clean_npc_name}) - FAIL", category="npc_creation")
            sys.exit(1)
    else:
        error(f"FAILURE: NPC creation ({npc_name_arg}) - FAIL", category="npc_creation")
        sys.exit(1)

if __name__ == "__main__":
    main()
