# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# reconcile_location_state.py

import json
import os
import shutil
import re
from datetime import datetime
from openai import OpenAI

# Import project-specific modules
from config import OPENAI_API_KEY, NPC_INFO_UPDATE_MODEL # Using a smaller, faster model is fine
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json, safe_write_json
from utils.location_context_hygiene import is_derived_location_context_message
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("reconcile_location_state")

client = OpenAI(api_key=OPENAI_API_KEY)

def create_area_backup(area_file_path):
    """Creates a timestamped backup of an area file before modification."""
    if not os.path.exists(area_file_path):
        error(f"Cannot backup: Area file does not exist: {area_file_path}", category="file_operations")
        return None
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{area_file_path}.backup_reconcile_{timestamp}"
        shutil.copy2(area_file_path, backup_path)
        debug(f"Created area backup: {os.path.basename(backup_path)}", category="file_operations")
        return backup_path
    except Exception as e:
        error(f"Failed to create area backup for {area_file_path}", exception=e, category="file_operations")
        return None

def run(area_id, location_id, conversation_history_segment):
    """
    Analyzes conversation history for a location and updates the monster list
    in the corresponding area JSON file.
    """
    info(f"RECONCILER: Starting reconciliation for location '{location_id}' in area '{area_id}'.")
    debug(f"[RECONCILER] Starting monster reconciliation for {location_id}", category="reconciliation")

    # Get the correct module path
    party_tracker = safe_read_json("party_tracker.json")
    current_module = party_tracker.get("module", "").replace(" ", "_")
    path_manager = ModulePathManager(current_module)
    area_file_path = path_manager.get_area_path(area_id)

    if not os.path.exists(area_file_path):
        error(f"RECONCILER: Area file not found at {area_file_path}. Aborting.", category="reconciliation")
        debug(f"[RECONCILER] FAILED - Could not find area file for {location_id}", category="reconciliation")
        return

    # Load the entire area data
    all_area_data = safe_read_json(area_file_path)
    if not all_area_data:
        error(f"RECONCILER: Could not load or parse area data from {area_file_path}. Aborting.", category="reconciliation")
        return

    # Find the specific location to update
    target_location_data = None
    location_index = -1
    for i, loc in enumerate(all_area_data.get("locations", [])):
        if loc.get("locationId") == location_id:
            target_location_data = loc
            location_index = i
            break

    if not target_location_data:
        error(f"RECONCILER: Location ID '{location_id}' not found in {area_file_path}. Aborting.", category="reconciliation")
        return

    original_monsters = target_location_data.get("monsters", [])
    if not original_monsters:
        info(f"RECONCILER: No monsters in original list for location '{location_id}'. Nothing to reconcile.", category="reconciliation")
        return

    # Format the conversation history into a readable string for the prompt
    history_text = ""
    info(f"RECONCILER: Processing {len(conversation_history_segment)} messages for location {location_id}", category="reconciliation")
    
    for msg in conversation_history_segment:
        if is_derived_location_context_message(msg):
            debug("RECONCILER: Skipping derived location context block in reconciliation input", category="reconciliation")
            continue
        role = "Player" if msg.get("role") == "user" else "DM"
        content = msg.get("content", "")
        # Clean up DM notes for the prompt
        if "Dungeon Master Note:" in content:
            content = re.sub(r"Dungeon Master Note:.*Player:", "Player:", content, flags=re.DOTALL).strip()
        history_text += f"{role}: {content}\n\n"
    
    # Debug: Log if we found combat information
    if "COMBAT CONCLUDED" in history_text:
        info(f"RECONCILER: Found combat conclusion in history for {location_id}", category="reconciliation")
    if "dead" in history_text.lower() or "defeated" in history_text.lower():
        info(f"RECONCILER: Found defeated/dead monsters mentioned in history", category="reconciliation")

    # Build the AI prompt
    system_prompt = """You are a game state reconciliation assistant. Your task is to analyze a conversation history segment and determine the final status of monsters in a specific location. Based on the narrative, you will return a new, updated JSON array of monsters that are still active and hostile.

RULES:
1. If a monster was killed, defeated, or permanently neutralized (e.g., trapped, banished, surrendered), REMOVE it from the list.
2. If a monster fled, was driven off, or is no longer a threat, REMOVE it from the list.
3. If the party never encountered a monster or left it undisturbed, you MUST KEEP it in the list.
4. Your response MUST be ONLY the final, updated JSON array for the `monsters` field. Do not include any other text, explanations, or markdown.
5. If all monsters were defeated, return an empty array `[]`.
"""

    user_prompt = f"""Original Monster List for this Location:
{json.dumps(original_monsters, indent=2)}

Conversation History for this Location:
---
{history_text}
---

Based on the conversation, what is the final list of active, hostile monsters remaining in this location? Respond with only the updated JSON array.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # AI call with retry loop, modeled after update_character_info.py
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=NPC_INFO_UPDATE_MODEL, # A smaller model is sufficient and faster
                messages=messages,
                temperature=0.2 # Low temperature for deterministic results
            )
            raw_response = response.choices[0].message.content.strip()

            # Clean and parse JSON response
            json_match = re.search(r'\[.*\]', raw_response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON array found in response.")

            clean_response = json_match.group()
            updated_monsters = json.loads(clean_response)

            # --- Validation Step ---
            if not isinstance(updated_monsters, list):
                raise TypeError("AI response is not a valid list.")

            # All checks passed, proceed to update
            info(f"RECONCILER: AI proposed new monster list with {len(updated_monsters)} active monsters.", category="reconciliation")
            info(f"RECONCILER: Original monsters: {len(original_monsters)}, Updated monsters: {len(updated_monsters)}", category="reconciliation")
            
            if len(updated_monsters) == 0:
                info(f"RECONCILER: All monsters defeated - clearing monster list for {location_id}", category="reconciliation")
                debug(f"[RECONCILER] All monsters in {location_id} have been defeated - clearing list", category="reconciliation")

            # Create a backup before writing
            backup_path = create_area_backup(area_file_path)
            if backup_path:
                info(f"RECONCILER: Created backup at {backup_path}", category="reconciliation")

            # Update the monster list in the loaded area data
            all_area_data["locations"][location_index]["monsters"] = updated_monsters

            # Save the entire area file back
            write_result = safe_write_json(area_file_path, all_area_data)
            if write_result:
                info(f"RECONCILER: Successfully wrote updated area file for location '{location_id}'.", category="reconciliation")
            else:
                error(f"RECONCILER: Failed to write area file for location '{location_id}'.", category="reconciliation")
            
            info(f"RECONCILER: Reconciliation complete for location '{location_id}'.", category="reconciliation")
            debug(f"[RECONCILER] Successfully reconciled {location_id} - {len(original_monsters)} -> {len(updated_monsters)} monsters", category="reconciliation")
            return # Success

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            error(f"RECONCILER: AI response validation failed on attempt {attempt + 1}/{max_retries}. Error: {e}", category="reconciliation")
            debug(f"RECONCILER: Faulty AI response: {raw_response}", category="reconciliation")
            if attempt == max_retries - 1:
                error("RECONCILER: Max retries reached. Aborting reconciliation to prevent data corruption.", category="reconciliation")
                return # Failure
        except Exception as e:
            error(f"RECONCILER: An unexpected error occurred on attempt {attempt + 1}", exception=e, category="reconciliation")
            if attempt == max_retries - 1:
                return # Failure