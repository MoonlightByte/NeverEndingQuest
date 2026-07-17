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

import copy
import json
import os
import sys
import threading
import traceback
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

# Add the project root to the Python path so we can import from utils, core, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T015", "core/ai/adv_summary.py", 417)
register_callsite("T016", "core/ai/adv_summary.py", 609)

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
from utils.file_operations import FileLockError, atomic_writer
from utils.module_refresh_lock import module_refresh_lock
from core.managers.status_manager import status_generating_summary
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("adv_summary")

TEMPERATURE = 0.8
PENDING_DEPARTURE_SUMMARY_FILE = (
    "modules/conversation_history/pending_departure_summary.json"
)


class DepartureSummaryError(RuntimeError):
    """An optional departure summary could not be staged or committed safely."""


_DEPARTURE_TRANSACTION_LOCKS = {}
_DEPARTURE_TRANSACTION_LOCKS_GUARD = threading.Lock()


def _departure_transaction_thread_lock(pending_path):
    canonical_path = os.path.abspath(os.path.normpath(pending_path))
    with _DEPARTURE_TRANSACTION_LOCKS_GUARD:
        return _DEPARTURE_TRANSACTION_LOCKS.setdefault(
            canonical_path,
            threading.RLock(),
        )


@contextmanager
def _departure_transaction_lock(pending_path):
    """Serialize marker, area, and journal state across threads/processes."""
    canonical_path = os.path.abspath(os.path.normpath(pending_path))
    lock_path = f"{canonical_path}.lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)

    with _departure_transaction_thread_lock(canonical_path):
        with open(lock_path, "a+b") as lock_file:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _process_is_alive(pid):
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        error_invalid_parameter = 87
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        )
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL

        process_handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not process_handle:
            # Access denied can describe a protected but live process. Only an
            # invalid PID is sufficient evidence that this lock is abandoned.
            return ctypes.get_last_error() != error_invalid_parameter
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(
                process_handle,
                ctypes.byref(exit_code),
            ):
                return True
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(process_handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _remove_abandoned_atomic_writer_lock(filepath):
    """Reclaim a target lock left by a process that exited mid-transaction."""
    lock_path = f"{filepath}.lock"
    try:
        with open(lock_path, "r", encoding="ascii") as lock_file:
            owner_pid = int(lock_file.read().strip())
    except (FileNotFoundError, OSError, ValueError):
        return
    if _process_is_alive(owner_pid):
        return
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass


@contextmanager
def _departure_target_locks(area_path, journal_path, pending_path):
    """Hold shared AtomicFileWriter locks in canonical path order."""
    canonical_pending = os.path.abspath(os.path.normpath(pending_path))
    canonical_targets = sorted(
        {
            os.path.abspath(os.path.normpath(area_path)),
            os.path.abspath(os.path.normpath(journal_path)),
        }
    )
    lock_resources = {
        canonical_pending,
        f"{canonical_pending}.lock",
        canonical_targets[0],
        f"{canonical_targets[0]}.lock",
        canonical_targets[-1],
        f"{canonical_targets[-1]}.lock",
    }
    if len(canonical_targets) != 2 or len(lock_resources) != 6:
        raise DepartureSummaryError(
            "departure transaction marker, area, journal, and their lock paths "
            "must be distinct"
        )

    acquired = []
    try:
        for filepath in canonical_targets:
            _remove_abandoned_atomic_writer_lock(filepath)
            try:
                atomic_writer.acquire_lock(filepath)
            except FileLockError as exc:
                raise DepartureSummaryError(
                    "could not acquire departure transaction target lock for "
                    f"{filepath}: {exc}"
                ) from exc
            except Exception as exc:
                raise DepartureSummaryError(
                    "unexpected failure acquiring departure transaction target "
                    f"lock for {filepath}: {exc}"
                ) from exc
            acquired.append(filepath)
        yield
    finally:
        for filepath in reversed(acquired):
            atomic_writer.release_lock(filepath)


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
        raise DepartureSummaryError(error_msg) from json_err
    except FileNotFoundError:
        error_msg = f"Error: File {file_path} not found."
        debug_print(error_msg)
        debug_print(traceback.format_exc())
        raise DepartureSummaryError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error loading {file_path}: {str(e)}"
        debug_print(error_msg)
        debug_print(traceback.format_exc())
        raise DepartureSummaryError(error_msg) from e

def get_game_time():
    party_tracker = load_json_file("party_tracker.json")
    world_conditions = party_tracker.get("worldConditions", {})
    year = world_conditions.get("year", "Unknown")
    month = world_conditions.get("month", "Unknown")
    day = world_conditions.get("day", "Unknown")
    time = world_conditions.get("time", "Unknown")
    return f"{year} {month} {day}, {time}"

def validate_location_json(location_data, schema):
    validate(instance=location_data, schema=schema)

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
        raise DepartureSummaryError("loca_schema.json loaded as None")
        
    debug_print(f"Schema type: {type(loca_schema_full)}")
    
    if not isinstance(loca_schema_full, dict):
        debug_print(f"ERROR: loca_schema_full is not a dict but {type(loca_schema_full)}")
        raise DepartureSummaryError("loca_schema.json is not a dictionary")
    
    debug_print(f"Schema keys: {list(loca_schema_full.keys())}")
    
    if 'properties' not in loca_schema_full:
        debug_print("ERROR: 'properties' key missing from schema")
        raise DepartureSummaryError("loca_schema.json is missing 'properties'")
    
    debug_print(f"Properties keys: {list(loca_schema_full['properties'].keys())}")
    
    if 'locations' not in loca_schema_full['properties']:
        debug_print("ERROR: 'locations' key missing from schema properties")
        raise DepartureSummaryError(
            "loca_schema.json is missing 'properties.locations'"
        )
    
    if not isinstance(loca_schema_full['properties']['locations'], dict):
        debug_print(f"ERROR: 'locations' is not a dict but {type(loca_schema_full['properties']['locations'])}")
        raise DepartureSummaryError("'properties.locations' is not a dictionary")
    
    debug_print(f"Location properties keys: {list(loca_schema_full['properties']['locations'].keys())}")
    
    if 'items' not in loca_schema_full['properties']['locations']:
        debug_print("ERROR: 'items' key missing from schema properties.locations")
        raise DepartureSummaryError(
            "loca_schema.json is missing 'properties.locations.items'"
        )
    
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
                _request_provider=MODEL_PROVIDER,
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

            # T015 only stages a validated location object. Journal and area
            # files are committed together later, after both AI calls succeed.
            return updated_location
        except json.JSONDecodeError:
            debug_print(f"Invalid JSON from AI. Attempt {attempt + 1}/{max_retries}. Response: {location_updates}")
            if attempt < max_retries - 1:
                location_updater_prompt.append({"role": "assistant", "content": location_updates})
                location_updater_prompt.append({"role": "user", "content": "The JSON schema you provided is invalid. Please try again and ensure the output is a valid JSON format."})
            else:
                debug_print("Max retries reached. Unable to generate valid JSON.")
                raise DepartureSummaryError(
                    "T015 exhausted retries after malformed JSON"
                )
        except ValidationError as e_val: # Renamed to avoid conflict
            debug_print(f"JSON schema validation failed. Attempt {attempt + 1}/{max_retries}. Error: {e_val}")
            if attempt < max_retries - 1:
                location_updater_prompt.append({"role": "assistant", "content": location_updates}) # Send back faulty response
                location_updater_prompt.append({"role": "user", "content": f"The JSON schema you provided does not match the required structure. Error: {e_val}. Please try again."})
            else:
                debug_print("Max retries reached. Unable to generate valid JSON matching schema.")
                raise DepartureSummaryError(
                    "T015 exhausted retries after schema validation failures"
                )
        except Exception as e_gen: # Renamed to avoid conflict
            debug_print(f"Unexpected error in update_location_json: {str(e_gen)}")
            if attempt < max_retries - 1:
                debug_print(f"Retrying... Attempt {attempt + 2}/{max_retries}")
            else:
                debug_print("Max retries reached. Unable to update location JSON.")
                raise DepartureSummaryError(
                    f"T015 exhausted retries: {e_gen}"
                ) from e_gen
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
            _request_provider=MODEL_PROVIDER,
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

def build_journal_update(adventure_summary, party_tracker_data, location_name):
    """Stage a validated journal update without writing runtime state."""
    journal_schema = load_json_file("schemas/journal_schema.json")
    if not isinstance(journal_schema, dict):
        raise DepartureSummaryError("journal schema is unavailable or invalid")

    try:
        existing_journal = safe_json_load("journal.json")
    except Exception as exc:
        raise DepartureSummaryError(f"could not load journal.json: {exc}") from exc

    if existing_journal is None:
        journal_data = {
            "module": party_tracker_data.get("module", "Keep_of_Doom"),
            "entries": [],
        }
    elif (
        not isinstance(existing_journal, dict)
        or not isinstance(existing_journal.get("entries"), list)
    ):
        raise DepartureSummaryError(
            "journal.json has invalid structure; prior state was preserved"
        )
    else:
        journal_data = copy.deepcopy(existing_journal)

    world_conditions = party_tracker_data.get("worldConditions", {})
    journal_data["entries"].append(
        {
            "date": (
                f"{world_conditions.get('year', 'N/A')} "
                f"{world_conditions.get('month', 'N/A')} "
                f"{world_conditions.get('day', 'N/A')}"
            ),
            "time": world_conditions.get("time", "N/A"),
            "location": location_name,
            "summary": adventure_summary,
        }
    )

    try:
        validate(instance=journal_data, schema=journal_schema)
    except ValidationError as exc:
        raise DepartureSummaryError(
            f"staged journal update failed schema validation: {exc.message}"
        ) from exc
    return journal_data


def update_journal(adventure_summary, party_tracker_data, location_name):
    """Compatibility wrapper for callers that only need a journal write."""
    journal_data = build_journal_update(
        adventure_summary,
        party_tracker_data,
        location_name,
    )
    safe_json_dump(journal_data, "journal.json")
    debug_print("Journal updated successfully")
    return journal_data


def _restore_json_snapshot(path, existed, snapshot):
    if existed:
        safe_json_dump(snapshot, path)
    elif os.path.exists(path):
        _durable_remove(path)


def _fsync_parent_directory(path):
    if os.name == "nt":
        return
    parent = os.path.dirname(os.path.abspath(path))
    directory_fd = os.open(parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _durable_remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    _fsync_parent_directory(path)


def _load_json_snapshot(path):
    existed = os.path.exists(path)
    if not existed:
        return False, None
    try:
        return True, safe_json_load(path)
    except Exception as exc:
        raise DepartureSummaryError(
            f"could not read departure transaction state {path}: {exc}"
        ) from exc


def _validate_pending_record(pending, pending_path):
    if not isinstance(pending, dict):
        raise DepartureSummaryError(
            f"invalid pending departure summary at {pending_path}"
        )

    required_values = (
        "transaction_id",
        "status",
        "area_path",
        "area_existed",
        "journal_existed",
        "area_before",
        "journal_before",
        "area_after",
        "journal_after",
    )
    missing = [key for key in required_values if key not in pending]
    if missing:
        raise DepartureSummaryError(
            "invalid pending departure summary at "
            f"{pending_path}; missing {', '.join(missing)}"
        )
    if not isinstance(pending["transaction_id"], str) or not pending[
        "transaction_id"
    ].strip():
        raise DepartureSummaryError(
            f"invalid pending departure summary transaction id at {pending_path}"
        )
    if pending["status"] not in {"staged", "rollback_required"}:
        raise DepartureSummaryError(
            "invalid pending departure summary status "
            f"{pending['status']!r} at {pending_path}"
        )
    if not isinstance(pending["area_path"], str) or not pending[
        "area_path"
    ].strip():
        raise DepartureSummaryError(
            f"pending departure summary at {pending_path} has no area path"
        )
    if (
        not isinstance(pending.get("journal_path", "journal.json"), str)
        or not pending.get("journal_path", "journal.json").strip()
    ):
        raise DepartureSummaryError(
            f"pending departure summary at {pending_path} has no journal path"
        )
    if not isinstance(pending["area_existed"], bool) or not isinstance(
        pending["journal_existed"], bool
    ):
        raise DepartureSummaryError(
            f"invalid pending departure summary existence flags at {pending_path}"
        )
    if not isinstance(pending["area_after"], dict) or not isinstance(
        pending["journal_after"], dict
    ):
        raise DepartureSummaryError(
            f"invalid pending departure summary snapshots at {pending_path}"
        )
    for prefix in ("area", "journal"):
        existed = pending[f"{prefix}_existed"]
        before = pending[f"{prefix}_before"]
        if (existed and not isinstance(before, dict)) or (
            not existed and before is not None
        ):
            raise DepartureSummaryError(
                "invalid pending departure summary before snapshot for "
                f"{prefix} at {pending_path}"
            )


def _snapshot_matches(existed, value, expected_existed, expected_value):
    return existed == expected_existed and (
        not expected_existed or value == expected_value
    )


def _recover_pending_summary_targets(pending, pending_path, area_path, journal_path):
    """Classify and repair target state while both target locks are held."""
    area_existed, current_area = _load_json_snapshot(area_path)
    journal_existed, current_journal = _load_json_snapshot(journal_path)

    area_matches_before = _snapshot_matches(
        area_existed,
        current_area,
        pending["area_existed"],
        pending["area_before"],
    )
    journal_matches_before = _snapshot_matches(
        journal_existed,
        current_journal,
        pending["journal_existed"],
        pending["journal_before"],
    )
    area_matches_after = _snapshot_matches(
        area_existed,
        current_area,
        True,
        pending["area_after"],
    )
    journal_matches_after = _snapshot_matches(
        journal_existed,
        current_journal,
        True,
        pending["journal_after"],
    )

    if (
        pending["status"] == "staged"
        and area_matches_after
        and journal_matches_after
    ):
        _durable_remove(pending_path)
        return {"status": "already_committed"}
    if area_matches_before and journal_matches_before:
        _durable_remove(pending_path)
        return {"status": "already_rolled_back"}
    if not (
        (area_matches_before or area_matches_after)
        and (journal_matches_before or journal_matches_after)
    ):
        raise DepartureSummaryError(
            "ambiguous departure summary recovery state; marker retained at "
            f"{pending_path}"
        )

    if pending["status"] == "rollback_required":
        targets = (
            (
                area_path,
                pending["area_existed"],
                pending["area_before"],
            ),
            (
                journal_path,
                pending["journal_existed"],
                pending["journal_before"],
            ),
        )
        recovered_status = "recovered_rollback"
    else:
        targets = (
            (area_path, True, pending["area_after"]),
            (journal_path, True, pending["journal_after"]),
        )
        recovered_status = "recovered_forward"

    try:
        for path, should_exist, snapshot in targets:
            _restore_json_snapshot(path, should_exist, snapshot)
        for path, should_exist, snapshot in targets:
            actual_existed, actual_value = _load_json_snapshot(path)
            if not _snapshot_matches(
                actual_existed,
                actual_value,
                should_exist,
                snapshot,
            ):
                raise DepartureSummaryError(
                    f"recovery verification failed for {path}"
                )
    except Exception as exc:
        if isinstance(exc, DepartureSummaryError):
            detail = str(exc)
        else:
            detail = repr(exc)
        raise DepartureSummaryError(
            "departure summary recovery failed; marker retained at "
            f"{pending_path}: {detail}"
        ) from exc

    _durable_remove(pending_path)
    return {"status": recovered_status}


def _resolve_prior_pending_summary_unlocked(pending_path):
    if not os.path.exists(pending_path):
        return {"status": "none"}
    try:
        pending = safe_json_load(pending_path)
    except Exception as exc:
        raise DepartureSummaryError(
            f"unreadable pending departure summary at {pending_path}: {exc}"
        ) from exc
    _validate_pending_record(pending, pending_path)

    area_path = pending["area_path"]
    journal_path = pending.get("journal_path", "journal.json")
    with _departure_target_locks(area_path, journal_path, pending_path):
        return _recover_pending_summary_targets(
            pending,
            pending_path,
            area_path,
            journal_path,
        )


def _resolve_prior_pending_summary(pending_path=PENDING_DEPARTURE_SUMMARY_FILE):
    """Resolve a prior transaction under the same lock used by commits."""
    # Recovery may replace an area document, so module refresh must remain the
    # outermost module-tree fence. The marker/target locks are lower-ranked.
    with module_refresh_lock() as refresh_acquired:
        if not refresh_acquired:
            raise DepartureSummaryError(
                "module refresh is busy; departure recovery made no changes"
            )
        with _departure_transaction_lock(pending_path):
            return _resolve_prior_pending_summary_unlocked(pending_path)


def _journal_before_from_appended_update(journal_after):
    if not isinstance(journal_after, dict) or not isinstance(
        journal_after.get("entries"), list
    ):
        raise DepartureSummaryError(
            "staged journal update has no entries array"
        )
    if not journal_after["entries"]:
        raise DepartureSummaryError(
            "staged journal update contains no departure entry"
        )
    journal_before = copy.deepcopy(journal_after)
    journal_before["entries"].pop()
    return journal_before


def _commit_departure_summary_targets_locked(
    area_path,
    area_before,
    area_after,
    journal_after,
    pending_path,
    journal_path,
    expected_journal_before,
):
    """Commit after caller has acquired the shared target locks."""
    area_existed, current_area = _load_json_snapshot(area_path)
    journal_existed, journal_before = _load_json_snapshot(journal_path)

    if not area_existed or current_area != area_before:
        raise DepartureSummaryError(
            "departure area changed concurrently; staged summary was not "
            "committed"
        )
    if journal_existed:
        journal_matches_base = journal_before == expected_journal_before
    else:
        journal_matches_base = not expected_journal_before.get("entries")
    if not journal_matches_base:
        raise DepartureSummaryError(
            "departure journal changed concurrently; staged summary was not "
            "committed"
        )

    pending_record = {
        "transaction_id": uuid4().hex,
        "status": "staged",
        "area_path": os.path.abspath(area_path),
        "journal_path": os.path.abspath(journal_path),
        "area_existed": area_existed,
        "journal_existed": journal_existed,
        "area_before": copy.deepcopy(current_area),
        "journal_before": copy.deepcopy(journal_before),
        "area_after": copy.deepcopy(area_after),
        "journal_after": copy.deepcopy(journal_after),
    }
    try:
        safe_json_dump(pending_record, pending_path)
    except Exception as exc:
        raise DepartureSummaryError(
            f"could not create departure summary recovery marker: {exc}"
        ) from exc

    try:
        # A hard exit between these writes leaves a staged marker whose
        # deterministic policy is to finish the recorded after snapshots.
        safe_json_dump(area_after, area_path)
        safe_json_dump(journal_after, journal_path)
        committed_area = _load_json_snapshot(area_path)
        committed_journal = _load_json_snapshot(journal_path)
        if not _snapshot_matches(
            *committed_area,
            True,
            area_after,
        ) or not _snapshot_matches(
            *committed_journal,
            True,
            journal_after,
        ):
            raise DepartureSummaryError(
                "departure summary commit verification failed"
            )
    except Exception as commit_exc:
        pending_record["status"] = "rollback_required"
        pending_record["commit_error"] = str(commit_exc)
        try:
            safe_json_dump(pending_record, pending_path)
        except Exception as marker_exc:
            raise DepartureSummaryError(
                "departure summary commit failed; staged recovery marker "
                f"retained at {pending_path}: {marker_exc}"
            ) from commit_exc

        rollback_errors = []
        for path, existed, snapshot in (
            (area_path, area_existed, current_area),
            (journal_path, journal_existed, journal_before),
        ):
            try:
                _restore_json_snapshot(path, existed, snapshot)
            except Exception as rollback_exc:
                rollback_errors.append(f"{path}: {rollback_exc}")

        if rollback_errors:
            pending_record["rollback_errors"] = rollback_errors
            try:
                safe_json_dump(pending_record, pending_path)
            except Exception:
                pass
            raise DepartureSummaryError(
                "departure summary commit failed; recovery marker retained at "
                f"{pending_path}: {'; '.join(rollback_errors)}"
            ) from commit_exc

        try:
            _durable_remove(pending_path)
        except OSError:
            pass
        raise DepartureSummaryError(
            f"departure summary commit failed; prior state restored: {commit_exc}"
        ) from commit_exc

    try:
        _durable_remove(pending_path)
    except OSError as exc:
        debug_print(
            "Summary committed, but the resolved recovery marker could not be "
            f"removed: {exc}"
        )
    return {
        "success": True,
        "status": "committed",
        "area_path": area_path,
    }


def commit_departure_summary(
    area_path,
    area_before,
    area_after,
    journal_after,
    pending_path=PENDING_DEPARTURE_SUMMARY_FILE,
):
    """Commit one crash-recoverable area/journal pair under shared locks."""
    journal_path = "journal.json"
    expected_journal_before = _journal_before_from_appended_update(journal_after)

    # Lock order is module refresh, marker, then canonical targets. Ordinary
    # AtomicFileWriter callers acquire only target locks, so they cannot form
    # a target -> marker cycle with this transaction.
    with module_refresh_lock() as refresh_acquired:
        if not refresh_acquired:
            raise DepartureSummaryError(
                "module refresh is busy; departure summary made no changes"
            )
        with _departure_transaction_lock(pending_path):
            _resolve_prior_pending_summary_unlocked(pending_path)
            with _departure_target_locks(area_path, journal_path, pending_path):
                return _commit_departure_summary_targets_locked(
                    area_path,
                    area_before,
                    area_after,
                    journal_after,
                    pending_path,
                    journal_path,
                    expected_journal_before,
                )


def run_departure_summary(
    conversation_history_file,
    current_location_file,
    leaving_location_name,
    current_area_id,
):
    """Run T016 then T015 and commit their derived state as one transaction."""
    del current_location_file  # Kept in the CLI contract for caller compatibility.
    # Repair any prior interrupted commit before reading state or invoking a
    # provider for the next departure.
    _resolve_prior_pending_summary()
    conversation_history = load_json_file(conversation_history_file)
    party_tracker = load_json_file("party_tracker.json")
    if not isinstance(conversation_history, list):
        raise DepartureSummaryError("conversation history is unavailable or invalid")
    if not isinstance(party_tracker, dict):
        raise DepartureSummaryError("party tracker is unavailable or invalid")

    adventure_summary = generate_adventure_summary(
        conversation_history,
        party_tracker,
        leaving_location_name,
    )
    if not isinstance(adventure_summary, str) or not adventure_summary.strip():
        raise DepartureSummaryError("T016 did not produce an adventure summary")
    debug_print("Adventure Summary generated")

    current_module = party_tracker.get("module", "").replace(" ", "_")
    path_manager = ModulePathManager(current_module or None)
    area_path = path_manager.get_area_path(current_area_id)
    area_before = load_json_file(area_path)
    if not isinstance(area_before, dict) or not isinstance(
        area_before.get("locations"), list
    ):
        raise DepartureSummaryError(f"area data is unavailable or invalid: {area_path}")

    leaving_index = next(
        (
            index
            for index, location in enumerate(area_before["locations"])
            if isinstance(location, dict)
            and location.get("name") == leaving_location_name
        ),
        None,
    )
    if leaving_index is None:
        raise DepartureSummaryError(
            f"could not find leaving location '{leaving_location_name}' in {area_path}"
        )

    updated_location = update_location_json(
        adventure_summary,
        copy.deepcopy(area_before["locations"][leaving_index]),
        current_area_id,
    )
    if not isinstance(updated_location, dict):
        raise DepartureSummaryError("T015 did not produce a location update")

    area_after = copy.deepcopy(area_before)
    area_after["locations"][leaving_index] = updated_location
    journal_after = build_journal_update(
        adventure_summary,
        party_tracker,
        leaving_location_name,
    )
    return commit_departure_summary(
        area_path,
        area_before,
        area_after,
        journal_after,
    )


if __name__ == "__main__":
    if len(sys.argv) != 5:
        debug_print("Usage: python adv_summary.py <conversation_history_file> <current_location_file> <leaving_location_name> <current_area_id>")
        sys.exit(1)

    try:
        result = run_departure_summary(*sys.argv[1:5])
        debug_print(
            "Departure summary transaction committed: "
            + json.dumps(result, sort_keys=True)
        )
    except DepartureSummaryError as exc:
        debug_print(f"DEPARTURE SUMMARY UNAVAILABLE: {exc}")
        sys.exit(2)
    except Exception as exc:
        debug_print(f"DEPARTURE SUMMARY FAILED UNEXPECTEDLY: {exc}")
        sys.exit(2)
