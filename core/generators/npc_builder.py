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
# Import model configuration from config.py
from config import NPC_BUILDER_MODEL
from utils.ai_client_factory import create_chat_client, get_model_config, handle_provider_error
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name

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
    try:
        with open(file_name, 'w') as file:
            json.dump(data, file, indent=2)
        info(f"SUCCESS: NPC save ({file_name}) - PASS", category="npc_creation")
        return True
    except Exception as e:
        print(f"{RED}Error saving to {file_name}: {str(e)}{RESET}")
        return False

def generate_npc(npc_name, schema, npc_race=None, npc_class=None, npc_level=None, npc_background=None):
    system_prompt_text = load_prompt("prompts/generators/npc_builder_prompt.txt") # Renamed variable
    if not system_prompt_text:
        return None

    system_message = f"""You are an assistant that creates NPC schema JSON files from a master NPC schema template for a 5e game. Given an NPC name and optional details, create a JSON representation of the NPC's stats and abilities according to 5e rules following the NPC schema template exactly. Ensure your new NPC JSON adheres to the provided schema template. Do not include any additional properties or nested 'type' and 'value' fields. Return only the JSON content without any markdown formatting.

If the input name contains a status descriptor (like 'corrupted', 'wounded', 'elite'), ensure the `name` field in the output JSON contains only the character's base name. For example, an input of 'Corrupted Ranger Thane' should result in a `name` field of 'Ranger Thane'.

Use the following rules information when creating the NPC:

{system_prompt_text}

Adhere strictly to 5e rules and the provided schema."""

    # Create smarter level guidance
    level_guidance = npc_level if npc_level else "1-3 (appropriate for early adventuring parties)"
    
    prompt_messages = [ # Renamed variable
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Create an NPC named '{npc_name}' using 5e rules. Race: {npc_race or 'Any appropriate race'}, Class: {npc_class or 'Any appropriate class'}, Level: {level_guidance}, Background: {npc_background or 'Any appropriate background'}. Schema: {json.dumps(schema)}"}
    ]

    try:
        client = create_chat_client()
        config = get_model_config("npc_builder", NPC_BUILDER_MODEL)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=config["model"],
                    **config.get("extra_body", {}),
                    temperature=0.7,
                    messages=prompt_messages
                )
                break
            except Exception as e:
                error_result = handle_provider_error(e, "generate_npc")
                if error_result["should_fallback"] and attempt < max_retries - 1:
                    client = create_chat_client(use_fallback=True)
                    continue
                raise

        ai_response = response.choices[0].message.content.strip()
        #print(f"{YELLOW}AI Response:{RESET}\n{ai_response}")

        # Remove markdown code block if present
        ai_response = re.sub(r'^```json\s*|\s*```$', '', ai_response, flags=re.MULTILINE)

        try:
            npc_data = json.loads(ai_response)
            # Remove nested 'value' fields if they exist
            npc_data = remove_nested_values(npc_data)
            validate(instance=npc_data, schema=schema)
            return npc_data
        except json.JSONDecodeError as e:
            print(f"{RED}Error: Invalid JSON in AI response. {str(e)}{RESET}")
            print(f"{YELLOW}Processed AI response:{RESET}\n{ai_response}")
        except ValidationError as e:
            print(f"{RED}Error: Generated NPC data does not match schema. {str(e)}{RESET}")
            print(f"{YELLOW}Problematic NPC data:{RESET}\n{json.dumps(npc_data, indent=2)}") # Log problematic data
    except Exception as e:
        print(f"{RED}Error: Failed to generate NPC data. {str(e)}{RESET}")

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
    if len(sys.argv) < 2:
        print(f"{RED}Usage: python npc_builder.py <npc_name> [race] [class] [level] [background]{RESET}")
        sys.exit(1)

    npc_name_arg = sys.argv[1] # Renamed variable
    npc_race_arg = sys.argv[2] if len(sys.argv) > 2 else None # Renamed variable
    npc_class_arg = sys.argv[3] if len(sys.argv) > 3 else None # Renamed variable
    npc_level_arg = None # Renamed variable
    if len(sys.argv) > 4 and sys.argv[4].isdigit():
        try:
            npc_level_arg = int(sys.argv[4])
        except ValueError:
            print(f"{RED}Error: Level must be an integer.{RESET}")
            sys.exit(1)
    elif len(sys.argv) > 4 and not sys.argv[4].isdigit() and sys.argv[4] != '': # handle empty string for level
        print(f"{RED}Error: Level must be an integer or empty if not specified.{RESET}")
        sys.exit(1)


    npc_background_arg = sys.argv[5] if len(sys.argv) > 5 else None # Renamed variable

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