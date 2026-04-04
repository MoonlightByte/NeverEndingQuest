# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Adv Summary
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
import sys
import traceback
from datetime import datetime

# Add the project root to the Python path so we can import from utils, core, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T015", "core/ai/adv_summary.py", 240)
register_callsite("T016", "core/ai/adv_summary.py", 485)

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass

from jsonschema import validate, ValidationError
from utils.module_path_manager import ModulePathManager
from utils.encoding_utils import sanitize_text, safe_json_load, safe_json_dump
from core.managers.status_manager import status_generating_summary
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("adv_summary")

TEMPERATURE = 0.8

def get_current_location():
    try:
        return safe_json_load("current_location.json")
    except Exception as e:
        error(f"FAILURE: Failed to load current_location.json: {e}", category="file_operations")
        return None

def debug_print(text, log_to_file=True):
    """Print debug message and optionally log to file"""
    debug(f"PROCESSING: {text}", category="adventure_summary")
    if log_to_file:
        try:
            with open("modules/logs/adv_summary_debug.log", "a", encoding="utf-8") as log_file:
                log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {text}\n")
        except Exception as e:
            error(f"FAILURE: Could not write to debug log file: {str(e)}", category="file_operations")

def load_json_file(file_path):
    debug_print(f"Attempting to load file: {file_path}")
    try:
        content = safe_json_load(file_path)
        if content is not None:
            debug_print(f"File parsed successfully: {file_path}")
            return content
        else:
            debug_print(f"File not found: {file_path}")
            return None
    except json.JSONDecodeError as json_err:
        error_msg = f"Error: Invalid JSON in {file_path}. Error: {str(json_err)}"
        debug_print(error_msg)
        debug_print(f"JSON error at line {json_err.lineno}, column {json_err.colno}: {json_err.msg}")
        debug_print(traceback.format_exc())
        sys.exit(1)
    except FileNotFoundError:
        error_msg = f"Error: File {file_path} not found."
        debug_print(error_msg)
        debug_print(traceback.format_exc())
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unexpected error loading {file_path}: {str(e)}"
        debug_print(error_msg)
        debug_print(traceback.format_exc())
        sys.exit(1)

def get_game_time():
    party_tracker = load_json_file("party_tracker.json")
    world_conditions = party_tracker.get("worldConditions", {})
    year = world_conditions.get("year", "Unknown")
    month = world_conditions.get("month", "Unknown")
    day = world_conditions.get("day", "Unknown")
    time = world_conditions.get("time", "Unknown")
    return f"{year} {month} {day}, {time}"

def validate_location_json(location_data, schema):
    try:
        validate(instance=location_data, schema=schema)
    except ValidationError as e:
        debug_print(f"Error: Invalid location data structure. {e}")
        sys.exit(1) # Or raise the error to be caught by the caller

def deep_update(original, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and key in original and isinstance(original[key], dict):
            deep_update(original[key], value)
        else:
            original[key] = value

def compare_and_update(original, updates):
    changes = {}
    for key, value in updates.items():
        if key not in original or original[key] != value:
            if isinstance(value, dict) and key in original and isinstance(original[key], dict):
                nested_changes = compare_and_update(original[key], value)
                if nested_changes:
                    changes[key] = nested_changes
            else:
                changes[key] = value
    return changes

def update_location_json(adventure_summary, location_info, current_area_id_from_main):
    debug_print(f"Updating location JSON for {location_info['name']} with all changes")

    # Get the last completed encounter ID from party_tracker
    encounter_id = ""
    try:
        party_tracker = safe_json_load("party_tracker.json")
        if party_tracker:
            last_completed_id = party_tracker.get("worldConditions", {}).get("lastCompletedEncounter", "")
            if last_completed_id:
                encounter_id = last_completed_id
                debug_print(f"Found last completed encounter ID: {encounter_id}")
            else:
                debug_print("No last completed encounter ID found in party_tracker")
    except Exception as e:
        debug_print(f"Error getting last encounter ID: {str(e)}")

    loca_schema_full = load_json_file("schemas/loca_schema.json") # Load the full schema
    game_time = get_game_time()

    # --- DETAILED SCHEMA ACCESS DEBUGGING ---
    debug_print("Starting schema processing...")
    loca_single_item_schema = None
    
    # Check schema structure in detail with logging
    if loca_schema_full is None:
        debug_print("ERROR: loca_schema_full is None")
        sys.exit("Fatal: loca_schema.json loaded as None")
        
    debug_print(f"Schema type: {type(loca_schema_full)}")
    
    if not isinstance(loca_schema_full, dict):
        debug_print(f"ERROR: loca_schema_full is not a dict but {type(loca_schema_full)}")
        sys.exit("Fatal: loca_schema.json not a dictionary")
    
    debug_print(f"Schema keys: {list(loca_schema_full.keys())}")
    
    if 'properties' not in loca_schema_full:
        debug_print("ERROR: 'properties' key missing from schema")
        sys.exit("Fatal: loca_schema.json missing 'properties' key")
    
    debug_print(f"Properties keys: {list(loca_schema_full['properties'].keys())}")
    
    if 'locations' not in loca_schema_full['properties']:
        debug_print("ERROR: 'locations' key missing from schema properties")
        sys.exit("Fatal: loca_schema.json missing 'properties.locations' key")
    
    if not isinstance(loca_schema_full['properties']['locations'], dict):
        debug_print(f"ERROR: 'locations' is not a dict but {type(loca_schema_full['properties']['locations'])}")
        sys.exit("Fatal: 'properties.locations' is not a dictionary")
    
    debug_print(f"Location properties keys: {list(loca_schema_full['properties']['locations'].keys())}")
    
    if 'items' not in loca_schema_full['properties']['locations']:
        debug_print("ERROR: 'items' key missing from schema properties.locations")
        sys.exit("Fatal: loca_schema.json missing 'properties.locations.items' key")
    
    # If we get here, all checks passed
    loca_single_item_schema = loca_schema_full['properties']['locations']['items']
    debug_print("Schema structure validation passed")
    debug_print(f"Single item schema extracted, keys: {list(loca_single_item_schema.keys()) if isinstance(loca_single_item_schema, dict) else 'Not a dict'}")
    # --- END OF DETAILED SCHEMA ACCESS DEBUGGING ---

    # Update the prompt to include encounter ID if available
    encounter_id_instruction = ""
    if encounter_id:
        encounter_id_instruction = f"IMPORTANT: Use encounterId '{encounter_id}' for the encounter entry you create."

    location_updater_prompt = [
        {"role": "system", "content": f"""Given an adventure summary and the current location information, update the JSON schema for the corresponding location.
        The location name is "{location_info['name']}" and should not be changed.
        Update all relevant fields based on the events that have occurred, including but not limited to:
        - Update 'adventureSummary' with a brief summary of what occurred at this location (2-3 sentences).
        - Modify 'description' if the location has changed significantly.
        - Update 'npcs', 'monsters', 'resourcesAvailable', 'plotHooks', etc., based on recent events. Be aware of any mispellings of NPCs or monsters and make sure to not create new entities if the player commands it, directs it, or mispells. For example, if the area started with an NPC called Mordenkainen, and the player refers to the NPC as Mordy, don't add Mordy to the NPC list in addition to Mordenkainen.
        - Create a new 'encounter' entry for this update. The encounterId should be the location's locationId (e.g., 'R01', 'R02') appended with '-E' and then the next sequential number (e.g., if locationId is 'R01' and there are 2 existing encounters, the new encounterId should be 'R01-E3'). Do NOT include the area ID prefix.
        - Adjust 'dangerLevel' if applicable.
        - Update any other fields that may have changed due to the party's actions such as items removed or added, damage to the location, traps disabled, doors smashed, or anything else impacting the area.

        Your output must strictly adhere to the provided JSON structure for a single location, containing no text or information before or after the JSON document.

        Location Schema (return only a single location object, not the entire schema):
        {json.dumps(loca_single_item_schema, indent=2)}

        Adventure Summary:
        {adventure_summary}

        Current Game Time:
        {game_time}

        Current Location JSON:
        {json.dumps(location_info, indent=2)}

        {encounter_id_instruction}
        """}
    ]

    max_retries = 3
    for attempt in range(max_retries):
        debug_print(f"Attempt {attempt + 1} to update location JSON")
        try:
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                adv_config = config.ADV_SUMM_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                adv_config = config.ADV_SUMM_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                adv_config = config.ADV_SUMM_LMSTUDIO
            else:  # legacy
                adv_config = config.ADV_SUMM_LEGACY

            response = capture_and_fanout("T015", api_client.create_completion,
                messages=location_updater_prompt,
                model=adv_config["model"],
                temperature=TEMPERATURE,
                **{k: v for k, v in adv_config.items() if k != "model"})
            
            # Track usage if available
            if USAGE_TRACKING_AVAILABLE:
                try:
                    track_response(response)
                except:
                    pass
            
            location_updates = response.choices[0].message.content.strip()
            # Sanitize AI response to prevent encoding issues
            location_updates = sanitize_text(location_updates)
            location_updates = location_updates.replace("```json", "").replace("```", "").strip()
            updated_location = json.loads(location_updates)

            if updated_location.get("name") != location_info.get("name"): # Use .get for safety
                debug_print(f"WARNING: Location name was changed by AI or missing. Reverting/setting to original name: {location_info.get('name')}")
                updated_location["name"] = location_info.get("name") # Ensure name is present

            # Check and fix encounter ID if needed
            if updated_location.get("encounters") and isinstance(updated_location["encounters"], list) and updated_location["encounters"]:
                latest_encounter = updated_location["encounters"][-1]
                if not latest_encounter.get("encounterId") and encounter_id:
                    latest_encounter["encounterId"] = encounter_id
                    debug_print(f"Updated missing encounter ID to: {encounter_id}")
                elif latest_encounter.get("encounterId") == "":
                    latest_encounter["encounterId"] = encounter_id
                    debug_print(f"Fixed empty encounter ID to: {encounter_id}")

            validate_location_json(updated_location, loca_single_item_schema)

            debug_print(f"Getting area path for ID: {current_area_id_from_main}")
            # Get current module from party tracker for consistent path resolution
            try:
                from utils.encoding_utils import safe_json_load
                party_tracker = safe_json_load("party_tracker.json")
                current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
                path_manager = ModulePathManager(current_module)
            except:
                path_manager = ModulePathManager()  # Fallback to reading from file
            # Add extra debug for path manager to see if we're getting the right module data
            debug_print(f"ModulePathManager using module: {path_manager.module_name}")
            debug_print(f"ModulePathManager directory: {path_manager.module_dir}")
            
            all_locations_file = path_manager.get_area_path(current_area_id_from_main)
            debug_print(f"Area file path generated: {all_locations_file}")
            
            # Check if file exists before loading
            if not os.path.exists(all_locations_file):
                debug_print(f"ERROR: Area file does not exist: {all_locations_file}")
                debug_print(f"Current area ID: {current_area_id_from_main}")
                debug_print(f"Available files in module dir: {os.listdir(path_manager.module_dir) if os.path.exists(path_manager.module_dir) else 'Module directory not found'}")
                sys.exit(f"Fatal: Area file not found: {all_locations_file}")
            
            all_locations = load_json_file(all_locations_file)
            debug_print(f"All locations loaded from {all_locations_file}")
            
            # Check if locations key exists
            if "locations" not in all_locations:
                debug_print(f"ERROR: 'locations' key missing from {all_locations_file}")
                debug_print(f"File keys: {list(all_locations.keys())}")
                sys.exit(f"Fatal: 'locations' array missing from area file")
            
            debug_print(f"Locations count: {len(all_locations.get('locations', []))}")
            debug_print(f"Looking for location name: {location_info.get('name')}")
            
            # Detailed logging of all location names
            location_names = [loc.get('name', 'NO_NAME') for loc in all_locations.get("locations", [])]
            debug_print(f"Available location names: {location_names}")

            found_and_updated = False
            for i, location in enumerate(all_locations.get("locations", [])): # Use .get for safety
                debug_print(f"Checking location {i}: {location.get('name')}")
                if location.get("name") == location_info.get("name"): # Use .get for safety
                    debug_print(f"Found matching location at index {i}")
                    changes = compare_and_update(all_locations["locations"][i], updated_location)
                    debug_print(f"Changes to apply: {json.dumps(changes) if changes else 'No changes'}")
                    deep_update(all_locations["locations"][i], changes)
                    found_and_updated = True
                    debug_print("Location updated successfully")
                    break
            
            if not found_and_updated:
                debug_print(f"ERROR: Could not find location '{location_info.get('name')}' in '{all_locations_file}' to update.")
                debug_print(f"Looking for: {location_info.get('name')}")
                debug_print(f"Available: {location_names}")
                # We'll log the error but continue - this gives us more debugging info

            try:
                safe_json_dump(all_locations, all_locations_file)
            except IOError as e:
                debug_print(f"Error writing updated locations to {all_locations_file}: {e}")
                sys.exit(1)
            return updated_location
        except json.JSONDecodeError:
            debug_print(f"Invalid JSON from AI. Attempt {attempt + 1}/{max_retries}. Response: {location_updates}")
            if attempt < max_retries - 1:
                location_updater_prompt.append({"role": "assistant", "content": location_updates})
                location_updater_prompt.append({"role": "user", "content": "The JSON schema you provided is invalid. Please try again and ensure the output is a valid JSON format."})
            else:
                debug_print("Max retries reached. Unable to generate valid JSON.")
                sys.exit(1)
        except ValidationError as e_val: # Renamed to avoid conflict
            debug_print(f"JSON schema validation failed. Attempt {attempt + 1}/{max_retries}. Error: {e_val}")
            if attempt < max_retries - 1:
                location_updater_prompt.append({"role": "assistant", "content": location_updates}) # Send back faulty response
                location_updater_prompt.append({"role": "user", "content": f"The JSON schema you provided does not match the required structure. Error: {e_val}. Please try again."})
            else:
                debug_print("Max retries reached. Unable to generate valid JSON matching schema.")
                sys.exit(1)
        except Exception as e_gen: # Renamed to avoid conflict
            debug_print(f"Unexpected error in update_location_json: {str(e_gen)}")
            if attempt < max_retries - 1:
                debug_print(f"Retrying... Attempt {attempt + 2}/{max_retries}")
            else:
                debug_print("Max retries reached. Unable to update location JSON.")
                sys.exit(1)
    return None # Should only be reached if loop finishes without success (e.g. after retries)


def trim_conversation(summary_dump):
    trimmed_data = summary_dump[:3]
    relevant_messages = summary_dump[3:] # Messages after the initial system/user setup

    # Find the last 'Location transition:' message if any
    last_transition_index = -1
    for i, message in enumerate(relevant_messages):
        if message.get('role') == 'user' and 'Location transition:' in message.get('content', ''):
            last_transition_index = i
    
    # Start summarizing from after the last transition, or from the beginning of relevant messages
    start_summarize_from_index = last_transition_index + 1 if last_transition_index != -1 else 0
    messages_to_consider_for_summary = relevant_messages[start_summarize_from_index:]

    # Find the first assistant message in this considered segment
    first_assistant_index_in_segment = -1
    for i, message in enumerate(messages_to_consider_for_summary):
        if message.get('role') == 'assistant':
            first_assistant_index_in_segment = i
            break
            
    if first_assistant_index_in_segment != -1:
        # Take messages from the first assistant message onwards in this segment
        final_messages_for_dialogue = messages_to_consider_for_summary[first_assistant_index_in_segment:]
    else:
        # If no assistant message in the segment (e.g., only user messages after last transition),
        # then summarize what's available in that segment.
        final_messages_for_dialogue = messages_to_consider_for_summary

    trimmed_data.extend(final_messages_for_dialogue)
    return trimmed_data


def convert_to_dialogue(trimmed_data):
    dialogue = "Summarize this conversation per instructions:\n\n"
    # Iterate through messages intended for dialogue summary (those after the initial system setup)
    for message in trimmed_data[3:]: # Assuming first 3 are setup as before
        role = message.get('role')
        content = message.get('content', '')
        if role == 'assistant':
            dialogue += f"Dungeon Master: {content}\n\n"
        elif role == 'user':
            if 'Location transition:' in content: # This is a system note, not player dialogue for summary
                dialogue += f"[{content}]\n\n" # Keep as a note for context if needed by summarizer
            else: # Actual player input
                dialogue += f"Player: {content}\n\n"
    return [
        trimmed_data[0],
        {"role": "user", "content": dialogue.strip()}
    ]

def generate_adventure_summary(conversation_history_data, party_tracker_data, leaving_location_name):
    status_generating_summary()
    messages = [
        {
            "role": "system",
            "content": f"""You are a chronicler documenting the key events of a 5th Edition roleplaying game as a historical account. Generate a single, richly detailed narrative paragraph that describes all factual events that occurred during this visit to '{leaving_location_name}'. This is a retrospective summary, like a journal or chronicle—focused entirely on what actually happened during this specific visit, in clear chronological order.

Even if the visit was brief or just a pass-through, describe it from a narrative perspective. Note the atmosphere, any changes the party might have noticed since their last visit (if applicable), or their apparent purpose for moving through the area. The goal is to create a complete historical record for every time the party was present in this location.

The summary must be written in third person and past tense, and should read like a complete account of the party's time at that location. Include:
- Descriptions of the environment and ambiance, especially any changes from previous visits.
- Character actions and reactions, even if minor (hurried passage, cautious observation, etc.).
- Discoveries made and information gained.
- Consequences of actions and decisions.
- Emotional dynamics between characters (tension, trust, affection, conflict).
- Notable NPC interactions, or the absence of NPCs previously present.
- Any interpersonal developments (e.g., flirtation, bonding, solemn moments).
- The party's apparent purpose or destination if they're passing through.

You may include brief direct quotes only when they are notable turning points, emotionally charged, or central to the scene's meaning—such as symbolic phrases like 'playing house' or promises made. Keep these minimal and impactful.

Do NOT:
- Include events from previous or future locations.
- Speculate about the future or characters’ intentions.
- Use first-person narration or dialogue-heavy exchanges.
- Use bullet points, headings, or formatting.
- Include any JSON, schemas, or DM notes.
- Editorialize or guess what characters were thinking beyond observable behavior.

Your writing should feel immersive, literary, and grounded -- like a historical entry capturing a poignant moment in time. Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode. Do NOT use markdown formatting (no **, no ###, no bullet points)."""
        },
        {"role": "user", "content": "Summarize this conversation per instructions:"},
        *conversation_history_data
    ]
    dump_file_path = "summary_dump.json"
    if os.path.exists(dump_file_path):
        try:
            os.remove(dump_file_path)
        except OSError as e:
            debug_print(f"Error removing {dump_file_path}: {e}")

    try:
        safe_json_dump(messages, dump_file_path)
    except IOError as e:
        debug_print(f"Error writing to {dump_file_path}: {e}")

    trimmed_data = trim_conversation(messages)
    try:
        safe_json_dump(trimmed_data, 'trimmed_summary_dump.json')
    except IOError as e:
        debug_print(f"Error writing to trimmed_summary_dump.json: {e}")

    dialogue_data = convert_to_dialogue(trimmed_data)
    try:
        safe_json_dump(dialogue_data, 'dialogue_summary.json')
    except IOError as e:
        debug_print(f"Error writing to dialogue_summary.json: {e}")


    try:
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            adv_config = config.ADV_SUMM_GPT54MINI_NONE
        elif MODEL_PROVIDER == "gemini":
            adv_config = config.ADV_SUMM_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            adv_config = config.ADV_SUMM_LMSTUDIO
        else:  # legacy
            adv_config = config.ADV_SUMM_LEGACY

        response = capture_and_fanout("T016", api_client.create_completion,
            messages=dialogue_data,
            model=adv_config["model"],
            temperature=TEMPERATURE,
            response_format=None,
            **{k: v for k, v in adv_config.items() if k != "model"})
        
        # Track usage if available
        if USAGE_TRACKING_AVAILABLE:
            try:
                track_response(response)
            except:
                pass
        
        adventure_summary = response.choices[0].message.content.strip()
        # Sanitize AI response to prevent encoding issues
        adventure_summary = sanitize_text(adventure_summary)
        return adventure_summary
    except Exception as e:
        debug_print(f"ERROR: Failed to generate adventure summary. Error: {str(e)}")
        return None

def update_journal(adventure_summary, party_tracker_data, location_name):
    journal_schema = load_json_file("schemas/journal_schema.json")
    journal_data = {"entries": []} # Default to empty journal

    try:
        journal_data = safe_json_load("journal.json")
        if not journal_data or not isinstance(journal_data, dict) or "entries" not in journal_data or not isinstance(journal_data["entries"], list):
            debug_print("journal.json has invalid structure, reinitializing.")
            journal_data = {"module": "Keep_of_Doom", "entries": []}
    except Exception as e:
        debug_print(f"Error loading journal.json: {e}, creating new journal")
        journal_data = {"module": "Keep_of_Doom", "entries": []}
    
    world_conditions = party_tracker_data.get('worldConditions', {}) # Use .get for safety
    new_entry = {
        "date": f"{world_conditions.get('year', 'N/A')} {world_conditions.get('month','N/A')} {world_conditions.get('day','N/A')}",
        "time": world_conditions.get('time', 'N/A'),
        "location": location_name,
        "summary": adventure_summary
    }
    journal_data["entries"].append(new_entry)

    try:
        if journal_schema: # Only validate if schema was loaded
            validate(instance=journal_data, schema=journal_schema)
    except ValidationError as e:
        debug_print(f"Error: Invalid journal entry structure. {e}")
        return # Or handle error, e.g., don't save if invalid

    try:
        safe_json_dump(journal_data, "journal.json")
        debug_print("Journal updated successfully")
    except IOError as e:
        debug_print(f"Error writing to journal.json: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        debug_print("Usage: python adv_summary.py <conversation_history_file> <current_location_file> <leaving_location_name> <current_area_id>")
        sys.exit(1)

    conversation_history_file_arg = sys.argv[1]
    current_location_file_arg = sys.argv[2] # This is the JSON of the location *being left*
    leaving_location_name_arg = sys.argv[3]
    current_area_id_arg = sys.argv[4]

    conversation_history_content = load_json_file(conversation_history_file_arg)
    # The 'current_location_file_arg' contains the data for the location being left.
    # 'leaving_location_obj' will be this data.
    # We need to ensure `update_location_json` gets the correct `current_area_id` for loading `all_locations`.
    
    party_tracker_content = load_json_file("party_tracker.json")

    adventure_summary_text = generate_adventure_summary(conversation_history_content, party_tracker_content, leaving_location_name_arg)
    if adventure_summary_text is None:
        debug_print("ERROR: Unable to generate adventure summary. Exiting.")
        sys.exit(1)
    debug_print("Adventure Summary generated")

    update_journal(adventure_summary_text, party_tracker_content, leaving_location_name_arg)

    # Load the full data for the area being updated
    # Get current module from party tracker for consistent path resolution
    try:
        from utils.encoding_utils import safe_json_load
        party_tracker = safe_json_load("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
    except:
        path_manager = ModulePathManager()  # Fallback to reading from file
    area_file_to_update = path_manager.get_area_path(current_area_id_arg)
    all_locations_in_area = load_json_file(area_file_to_update)
    
    # Find the specific location object within that area's data that matches the name of the location being left
    leaving_location_obj_from_area = next((loc for loc in all_locations_in_area.get("locations", []) if loc.get("name") == leaving_location_name_arg), None)

    if leaving_location_obj_from_area:
        # Pass current_area_id_arg to update_location_json as it's needed to load the correct area file within that function
        updated_location_data = update_location_json(adventure_summary_text, leaving_location_obj_from_area, current_area_id_arg)
        
        if updated_location_data: # If update was successful
            # Update the main area file data in memory
            found_in_all_locations = False
            for i, location_in_list in enumerate(all_locations_in_area.get("locations", [])):
                if location_in_list.get("name") == leaving_location_name_arg:
                    all_locations_in_area["locations"][i] = updated_location_data
                    found_in_all_locations = True
                    break
            
            if found_in_all_locations:
                try:
                    safe_json_dump(all_locations_in_area, area_file_to_update)
                    debug_print(f"Successfully updated {leaving_location_name_arg} in {area_file_to_update}")
                except IOError as e:
                    debug_print(f"Error writing updated area data to {area_file_to_update}: {e}")
            else:
                debug_print(f"ERROR: Could not find {leaving_location_name_arg} in {area_file_to_update} after attempting update.")
        else:
            debug_print(f"ERROR: update_location_json did not return updated data for {leaving_location_name_arg}.")
    else:
        debug_print(f"ERROR: Could not find location data for '{leaving_location_name_arg}' in '{area_file_to_update}'.")
        sys.exit(1)