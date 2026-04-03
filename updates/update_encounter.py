# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

import json
import os
from jsonschema import validate, ValidationError
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T081", "updates/update_encounter.py", 95)
import time
import re
import copy
# Import model configuration from config.py

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("update_encounter")

# ANSI escape codes - REMOVED per CLAUDE.md guidelines
# All color codes have been removed to prevent Windows console encoding errors

# Constants
TEMPERATURE = 0.7


def load_encounter_schema():
    with open("schemas/encounter_schema.json", "r") as schema_file:
        return json.load(schema_file)

def update_encounter(encounter_id, changes, max_retries=3):
    # Load the current encounter info and schema
    # Get current module from party tracker for consistent path resolution
    try:
        from utils.encoding_utils import safe_json_load
        party_tracker = safe_json_load("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    with open(f"modules/encounters/encounter_{encounter_id}.json", "r") as file:
        encounter_info = json.load(file)

    original_info = copy.deepcopy(encounter_info)  # Keep a copy of the original info
    schema = load_encounter_schema()

    for attempt in range(max_retries):
        # Prepare the prompt for the AI
        prompt = [
            {"role": "system", "content": """You are an assistant that updates encounter information in a 5th Edition roleplaying game. Given the current encounter information and a description of changes, you must return only the updated sections as a JSON object. Do not include unchanged fields. Your response should be a valid JSON object representing only the modified parts of the encounter data. 

Focus only on updating the monster information within the 'creatures' array. Do not modify player or NPC data.

Here's an example of a proper JSON structure for updates:

Input: The orc took 8 damage and is now bloodied.
Output: {
  "creatures": [
    {
      "name": "Orc",
      "type": "enemy",
      "currentHitPoints": 7,
      "status": "alive"
    }
  ]
}

Remember to only update monster information and leave player and NPC data unchanged."""},
            {"role": "user", "content": f"Current encounter info: {json.dumps(encounter_info)}\n\nChanges to apply: {changes}\n\nRespond with ONLY the updated JSON object representing the changed sections of the encounter data, with no additional text or explanation."}
        ]

        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            encounter_config = config.ENCOUNTER_UPD_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            encounter_config = config.ENCOUNTER_UPD_GEMINI_FLASH_MINIMAL
        elif MODEL_PROVIDER == "lmstudio":
            encounter_config = config.ENCOUNTER_UPD_LMSTUDIO
        else:  # legacy
            encounter_config = config.ENCOUNTER_UPD_LEGACY

        # Get AI's response
        response = capture_and_fanout("T081", api_client.create_completion,
            messages=prompt,
            model=encounter_config["model"],
            temperature=TEMPERATURE,
            **{k: v for k, v in encounter_config.items() if k != "model"})
        
        # Track usage
        if USAGE_TRACKING_AVAILABLE:
            try:
                track_response(response)
            except:
                pass

        ai_response = response.choices[0].message.content.strip()

        # Write the raw AI response to a debug file
        os.makedirs("debug", exist_ok=True)
        with open("debug/debug_encounter_update.json", "w") as debug_file:
            json.dump({"raw_ai_response": ai_response}, debug_file, indent=2)

        debug("AI_RESPONSE: Raw AI response written to debug/debug_encounter_update.json", category="encounter_updates")

        # Remove markdown code blocks if present
        ai_response = re.sub(r'```json\n|\n```', '', ai_response)

        try:
            updates = json.loads(ai_response)

            # Apply updates to the encounter_info
            encounter_info = update_nested_dict(encounter_info, updates)

            # Now sync player and NPC information from their respective files
            for creature in encounter_info["creatures"]:
                if creature["type"] == "player":
                    # Import normalize_character_name for consistent naming
                    from updates.update_character_info import normalize_character_name
                    player_file = path_manager.get_character_path(normalize_character_name(creature['name']))
                    try:
                        with open(player_file, "r") as file:
                            player_data = json.load(file)
                            # Only sync combat-relevant state
                            creature["currentHitPoints"] = player_data.get("hitPoints", creature.get("currentHitPoints", 0))
                            creature["maxHitPoints"] = player_data.get("maxHitPoints", creature.get("maxHitPoints", 0))
                            creature["status"] = player_data.get("status", creature.get("status", "alive"))
                            creature["conditions"] = player_data.get("condition_affected", [])
                            # Copy armorClass if it exists in player data
                            if "armorClass" in player_data:
                                creature["armorClass"] = player_data["armorClass"]
                    except Exception as e:
                        print(f"ERROR: Failed to sync player data from {player_file}: {str(e)}")
                        
                elif creature["type"] == "npc":
                    # Import the fuzzy matching function
                    from updates.update_character_info import find_character_file_fuzzy
                    
                    # Use fuzzy matching to find the correct NPC file
                    matched_name = find_character_file_fuzzy(creature['name'])
                    if matched_name:
                        npc_file = path_manager.get_character_path(matched_name)
                        try:
                            with open(npc_file, "r") as file:
                                npc_data = json.load(file)
                                # Only sync combat-relevant state
                                creature["currentHitPoints"] = npc_data.get("hitPoints", creature.get("currentHitPoints", 0))
                                creature["maxHitPoints"] = npc_data.get("maxHitPoints", creature.get("maxHitPoints", 0))
                                creature["status"] = npc_data.get("status", creature.get("status", "alive"))
                                creature["conditions"] = npc_data.get("condition_affected", [])
                                # Copy armorClass if it exists in NPC data
                                if "armorClass" in npc_data:
                                    creature["armorClass"] = npc_data["armorClass"]
                        except Exception as e:
                            print(f"ERROR: Failed to sync NPC data from {npc_file}: {str(e)}")
                    else:
                        print(f"WARNING: Could not find NPC file for '{creature['name']}' using fuzzy matching")

            # Normalize creature statuses before validation
            # Map invalid statuses to valid ones
            status_mapping = {
                "destroyed": "dead",
                "panicked": "alive",
                "fled": "defeated",
                "fleeing": "defeated",
                "dying": "unconscious"
            }
            
            for creature in encounter_info.get("creatures", []):
                current_status = creature.get("status", "alive")
                if current_status in status_mapping:
                    print(f"INFO: Normalizing invalid status '{current_status}' to '{status_mapping[current_status]}' for {creature.get('name', 'unknown')}")
                    creature["status"] = status_mapping[current_status]

            # Validate the updated info against the schema
            validate(instance=encounter_info, schema=schema)

            # If we reach here, validation was successful

            # Compare original and updated info (but don't print it)
            diff = compare_json(original_info, encounter_info)
            info(f"SUCCESS: Encounter update - PASS", category="encounter_updates")

            # Save the updated encounter info
            with open(f"modules/encounters/encounter_{encounter_id}.json", "w") as file:
                json.dump(encounter_info, file, indent=2)

            return encounter_info

        except json.JSONDecodeError as e:
            warning(f"VALIDATION: AI response is not valid JSON. Error: {e}. Retrying", category="encounter_updates")
        except ValidationError as e:
            print(f"ERROR: Updated info does not match the schema. Error: {e}. Retrying...")

        # If we've reached the maximum number of retries, return the original encounter info
        if attempt == max_retries - 1:
            error(f"FAILURE: Encounter update - FAIL", category="encounter_updates")
            return original_info

        # Wait for a short time before retrying
        time.sleep(1)

    # This line should never be reached, but just in case:
    return original_info

def update_nested_dict(d, u):
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = update_nested_dict(d.get(k, {}), v)
        elif isinstance(v, list):
            if k not in d:
                d[k] = []
            for item in v:
                if isinstance(item, dict):
                    existing = next((i for i in d[k] if i.get('name') == item.get('name')), None)
                    if existing:
                        update_nested_dict(existing, item)
                    else:
                        d[k].append(item)
                else:
                    if item not in d[k]:
                        d[k].append(item)
        else:
            d[k] = v
    return d

def compare_json(old, new):
    diff = {}
    for key in new:
        if key not in old:
            diff[key] = new[key]
        elif old[key] != new[key]:
            if isinstance(new[key], dict):
                nested_diff = compare_json(old[key], new[key])
                if nested_diff:
                    diff[key] = nested_diff
            elif isinstance(new[key], list):
                # This is the original simpler list diffing.
                if key not in diff: # This line was problematic as diff[key] might not be a list
                    diff[key] = [] # Initialize diff[key] as a list if it's not already
                # The original code for list diffing was complex and potentially buggy.
                # A common simple approach if lists differ is just to show the new list.
                # Or, if the AI is meant to return the whole new list if it's changed, then
                # the update_nested_dict should just replace d[k] = v for lists.
                # Given the prompt, AI should return *only modified sections*.
                # If 'creatures' is returned, it's likely the new state of modified creatures.
                # For simplicity and to revert to original intent, if lists are different,
                # we can just indicate the new list.
                if old[key] != new[key]: # A simple check if lists are different
                    diff[key] = new[key] # Store the new list as the difference
            else:
                diff[key] = new[key]
    return diff