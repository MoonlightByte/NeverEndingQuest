# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# reconcile_location_state.py

import copy
import json
import os
import shutil
import re
import threading
from datetime import datetime
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T091", "utils/reconcile_location_state.py", 346)

# Import project-specific modules
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json, safe_write_json
from utils.module_refresh_lock import module_refresh_lock
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("reconcile_location_state")


# A reconciliation reads and later replaces an entire area document.  The
# atomic writer prevents torn files, but it cannot by itself prevent two
# callers from both reading the same old document and then overwriting one
# another.  Serialize the complete read/model/validate/write transaction per
# area while still allowing reconciliations for different areas to proceed in
# parallel.
_area_transaction_locks = {}
_area_transaction_locks_guard = threading.Lock()


def _get_area_transaction_lock(area_file_path):
    canonical_path = os.path.normcase(os.path.realpath(area_file_path))
    with _area_transaction_locks_guard:
        return _area_transaction_locks.setdefault(canonical_path, threading.RLock())


def _json_fingerprint(value):
    """Return a type-sensitive, order-insensitive-for-object-keys identity."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_removal_only_subset(original_monsters, proposed_monsters):
    """Validate that the model only removed exact entries from the list.

    A valid proposal is an ordered subsequence of the original list.  Exact
    canonical JSON equality prevents the model from changing field values or
    JSON value types.  Duplicate proposed elements are rejected even if they
    happen to resemble an original entry.
    """
    if not isinstance(original_monsters, list):
        raise TypeError("Original monsters field is not a list.")
    if not isinstance(proposed_monsters, list):
        raise TypeError("AI response is not a JSON array.")

    original_fingerprints = [_json_fingerprint(item) for item in original_monsters]
    proposed_fingerprints = [_json_fingerprint(item) for item in proposed_monsters]

    if len(proposed_fingerprints) != len(set(proposed_fingerprints)):
        raise ValueError("AI response contains duplicate monster entries.")

    original_index = 0
    validated_original_elements = []
    for proposed_fingerprint in proposed_fingerprints:
        while (
            original_index < len(original_fingerprints)
            and original_fingerprints[original_index] != proposed_fingerprint
        ):
            original_index += 1
        if original_index == len(original_fingerprints):
            raise ValueError(
                "AI response added, reordered, or modified a monster entry."
            )
        # Persist the trusted original element, not a model-authored copy of
        # it.  The provider decides only which identities to remove.
        validated_original_elements.append(
            copy.deepcopy(original_monsters[original_index])
        )
        original_index += 1

    return validated_original_elements


def _read_json_document(path):
    with open(path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def _reject_duplicate_json_keys(pairs):
    parsed_object = {}
    for key, value in pairs:
        if key in parsed_object:
            raise ValueError(f"Duplicate JSON object key: {key}")
        parsed_object[key] = value
    return parsed_object


def _reject_json_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def _parse_strict_json_response(raw_response):
    return json.loads(
        raw_response,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
    )


def _verify_area_file(area_file_path, expected_area_data):
    try:
        persisted_area_data = _read_json_document(area_file_path)
        return _json_fingerprint(persisted_area_data) == _json_fingerprint(
            expected_area_data
        )
    except Exception as verify_error:
        error(
            f"RECONCILER: Could not verify area file '{area_file_path}': "
            f"{verify_error}",
            category="reconciliation",
        )
        return False


def _restore_original_area(area_file_path, backup_path, original_area_data):
    """Atomically restore the pre-transaction state after persistence failure."""
    restore_data = copy.deepcopy(original_area_data)
    if backup_path and os.path.exists(backup_path):
        try:
            backup_data = _read_json_document(backup_path)
            if _json_fingerprint(backup_data) == _json_fingerprint(original_area_data):
                restore_data = backup_data
        except Exception as backup_error:
            warning(
                f"RECONCILER: Could not read backup '{backup_path}'; restoring "
                f"from the in-memory snapshot instead: {backup_error}",
                category="reconciliation",
            )

    restored = safe_write_json(
        area_file_path,
        restore_data,
        create_backup=False,
    )
    if not restored or not _verify_area_file(area_file_path, original_area_data):
        error(
            f"RECONCILER: Rollback FAILED for '{area_file_path}'.",
            category="reconciliation",
        )
        return False

    info(
        f"RECONCILER: Restored area file '{area_file_path}' from its "
        "pre-reconciliation state.",
        category="reconciliation",
    )
    return True

def create_area_backup(area_file_path):
    """Creates a timestamped backup of an area file before modification."""
    if not os.path.exists(area_file_path):
        error(f"Cannot backup: Area file does not exist: {area_file_path}", category="file_operations")
        return None
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
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

    # Get the correct module path.
    try:
        party_tracker = safe_read_json("party_tracker.json")
        if not isinstance(party_tracker, dict):
            raise ValueError("party_tracker.json did not contain a JSON object")
        current_module = party_tracker.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(current_module)
        area_file_path = path_manager.get_area_path(area_id)
    except Exception as path_error:
        error(
            "RECONCILER: Could not resolve the area file. Aborting.",
            exception=path_error,
            category="reconciliation",
        )
        return False

    if not os.path.exists(area_file_path):
        error(f"RECONCILER: Area file not found at {area_file_path}. Aborting.", category="reconciliation")
        debug(f"[RECONCILER] FAILED - Could not find area file for {location_id}", category="reconciliation")
        return False

    # T088 snapshots this same area tree under module refresh. Keep refresh
    # outside the per-area transaction lock so every participant follows the
    # global refresh -> target order and T088 can never commit from a source
    # that this read/model/write transaction is still changing.
    with module_refresh_lock() as refresh_acquired:
        if not refresh_acquired:
            warning(
                "RECONCILER: Module refresh is busy; no location state was "
                "changed.",
                category="reconciliation",
            )
            return False

        area_transaction_lock = _get_area_transaction_lock(area_file_path)
        with area_transaction_lock:
            try:
                return _run_area_transaction(
                    area_file_path,
                    location_id,
                    conversation_history_segment,
                )
            except Exception as transaction_error:
                error(
                    f"RECONCILER: Area transaction failed for '{location_id}'.",
                    exception=transaction_error,
                    category="reconciliation",
                )
                return False


def _run_area_transaction(
    area_file_path,
    location_id,
    conversation_history_segment,
):
    """Run one serialized read/model/validate/write area transaction."""

    # Load the entire area data
    all_area_data = safe_read_json(area_file_path)
    if not isinstance(all_area_data, dict) or not all_area_data:
        error(f"RECONCILER: Could not load or parse area data from {area_file_path}. Aborting.", category="reconciliation")
        return False

    original_area_data = copy.deepcopy(all_area_data)

    # Find the specific location to update
    target_location_data = None
    location_index = -1
    for i, loc in enumerate(all_area_data.get("locations", [])):
        if loc.get("locationId") == location_id:
            target_location_data = loc
            location_index = i
            break

    if target_location_data is None:
        error(f"RECONCILER: Location ID '{location_id}' not found in {area_file_path}. Aborting.", category="reconciliation")
        return False

    original_monsters = copy.deepcopy(target_location_data.get("monsters", []))
    if not isinstance(original_monsters, list):
        error(
            f"RECONCILER: Monsters field for '{location_id}' is not a list. "
            "Aborting.",
            category="reconciliation",
        )
        return False
    if not original_monsters:
        info(f"RECONCILER: No monsters in original list for location '{location_id}'. Nothing to reconcile.", category="reconciliation")
        return True

    # Format the conversation history into a readable string for the prompt
    history_text = ""
    info(f"RECONCILER: Processing {len(conversation_history_segment)} messages for location {location_id}", category="reconciliation")
    
    try:
        for msg in conversation_history_segment:
            if not isinstance(msg, dict):
                raise TypeError("Conversation history entries must be objects.")
            role = "Player" if msg.get("role") == "user" else "DM"
            content = msg.get("content", "")
            if not isinstance(content, str):
                raise TypeError("Conversation history content must be text.")
            # Clean up DM notes for the prompt
            if "Dungeon Master Note:" in content:
                content = re.sub(r"Dungeon Master Note:.*Player:", "Player:", content, flags=re.DOTALL).strip()
            history_text += f"{role}: {content}\n\n"
    except Exception as history_error:
        error(
            "RECONCILER: Conversation history is malformed. Aborting.",
            exception=history_error,
            category="reconciliation",
        )
        return False
    
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
        raw_response = None
        try:
            # Select model config per provider
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                npc_config = config.NPC_INFO_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                npc_config = config.NPC_INFO_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                npc_config = config.NPC_INFO_LMSTUDIO
            else:  # legacy
                npc_config = config.NPC_INFO_LEGACY

            response = capture_and_fanout("T091", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=messages,
                model=npc_config["model"],
                temperature=0.2,
                response_format=None,
                **{k: v for k, v in npc_config.items() if k != "model"})
            response_content = response.choices[0].message.content
            if not isinstance(response_content, str):
                raise TypeError("Provider response content is not text.")
            raw_response = response_content.strip()

            # Parse the complete response.  Extracting an array from prose or
            # markdown would silently weaken the response contract.
            updated_monsters = _parse_strict_json_response(raw_response)
            updated_monsters = _validate_removal_only_subset(
                original_monsters,
                updated_monsters,
            )

            # All checks passed, proceed to update
            info(f"RECONCILER: AI proposed new monster list with {len(updated_monsters)} active monsters.", category="reconciliation")
            info(f"RECONCILER: Original monsters: {len(original_monsters)}, Updated monsters: {len(updated_monsters)}", category="reconciliation")
            
            if len(updated_monsters) == 0:
                info(f"RECONCILER: All monsters defeated - clearing monster list for {location_id}", category="reconciliation")
                debug(f"[RECONCILER] All monsters in {location_id} have been defeated - clearing list", category="reconciliation")

            # Create a recoverable snapshot before publishing any mutation.
            backup_path = create_area_backup(area_file_path)
            if not backup_path:
                error(
                    f"RECONCILER: Could not back up '{area_file_path}'. "
                    "The update was not written.",
                    category="reconciliation",
                )
                return False
            info(f"RECONCILER: Created backup at {backup_path}", category="reconciliation")

            # Stage a new whole-area document without mutating the original
            # in-memory snapshot used for rollback.
            updated_area_data = copy.deepcopy(all_area_data)
            updated_area_data["locations"][location_index]["monsters"] = updated_monsters

            # Save atomically using the repository's existing file helper.
            write_result = safe_write_json(area_file_path, updated_area_data)
            if not write_result:
                error(f"RECONCILER: Failed to write area file for location '{location_id}'. Restoring backup.", category="reconciliation")
                _restore_original_area(
                    area_file_path,
                    backup_path,
                    original_area_data,
                )
                return False

            # Verify the exact expected document, not merely parseability.
            if not _verify_area_file(area_file_path, updated_area_data):
                error(f"RECONCILER: Post-write verify FAILED for '{location_id}'. Restoring backup.", category="reconciliation")
                _restore_original_area(
                    area_file_path,
                    backup_path,
                    original_area_data,
                )
                return False

            info(f"RECONCILER: Successfully wrote and verified area file for location '{location_id}'.", category="reconciliation")
            info(f"RECONCILER: Reconciliation complete for location '{location_id}'.", category="reconciliation")
            debug(f"[RECONCILER] Successfully reconciled {location_id} - {len(original_monsters)} → {len(updated_monsters)} monsters", category="reconciliation")
            return True  # Success

        except Exception as e:
            error(
                f"RECONCILER: Provider response failed validation on attempt "
                f"{attempt + 1}/{max_retries}.",
                exception=e,
                category="reconciliation",
            )
            if raw_response is not None:
                debug(f"RECONCILER: Faulty AI response: {raw_response}", category="reconciliation")
            if attempt == max_retries - 1:
                error("RECONCILER: Max retries reached. Aborting reconciliation to prevent data corruption.", category="reconciliation")
                return False

    return False
