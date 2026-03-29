# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

import json
import os
from jsonschema import validate, ValidationError
import time
import re
import copy
from typing import Any, Dict, List, Optional, Tuple
# Import model configuration from config.py
from config import ENCOUNTER_UPDATE_MODEL

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass
from utils.module_path_manager import ModulePathManager
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.ai_client_factory import create_chat_client, get_model_config  # OPENROUTER: Multi-provider support

# Set script name for logging
set_script_name("update_encounter")

# ANSI escape codes - REMOVED per CLAUDE.md guidelines
# All color codes have been removed to prevent Windows console encoding errors

# Constants
TEMPERATURE = 0.7

# Initialize AI client using factory (supports OpenAI and OpenRouter)
client = create_chat_client()

def load_encounter_schema():
    with open("schemas/encounter_schema.json", "r") as schema_file:
        return json.load(schema_file)


SUPPORTED_ENCOUNTER_OPS = {
    "hp_delta",
    "set_hp",
    "condition_add",
    "condition_remove",
    "set_status",
}

ALLOWED_STATUS_VALUES = {"alive", "dead", "unconscious", "defeated"}
NON_LIVING_ENEMY_STATUSES = {"dead", "unconscious", "defeated"}


def _coerce_int(value: Any, default: int = 0) -> int:
    """Safely coerce encounter numeric fields to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_name_key(value: str) -> str:
    """Normalize creature names for deterministic encounter-op matching."""
    return str(value).strip().lower().replace("_", " ").replace("-", " ")


def _preferred_non_living_status(current_status: str, original_status: str) -> str:
    """Pick a deterministic schema-legal non-living status for defeated enemies."""
    for candidate in (current_status, original_status):
        normalized = str(candidate or "").strip().lower()
        if normalized in NON_LIVING_ENEMY_STATUSES:
            return normalized
    return "dead"


def _normalize_enemy_defeat_states(
    encounter_info: Dict[str, Any],
    original_info: Dict[str, Any],
) -> None:
    """Clamp defeated enemy HP and prevent same-turn enemy resurrection drift."""
    original_enemy_index: Dict[str, Dict[str, Any]] = {}
    for creature in original_info.get("creatures", []):
        if str(creature.get("type", "")).lower() != "enemy":
            continue
        key = _normalize_name_key(creature.get("name", ""))
        if key and key not in original_enemy_index:
            original_enemy_index[key] = creature

    for creature in encounter_info.get("creatures", []):
        if str(creature.get("type", "")).lower() != "enemy":
            continue

        key = _normalize_name_key(creature.get("name", ""))
        original_creature = original_enemy_index.get(key, {})

        current_hp = _coerce_int(creature.get("currentHitPoints", 0), 0)
        current_status = str(creature.get("status", "alive")).strip().lower()
        original_hp = _coerce_int(original_creature.get("currentHitPoints", 0), 0)
        original_status = str(original_creature.get("status", "alive")).strip().lower()

        was_already_defeated = (
            bool(original_creature)
            and (
                original_hp <= 0
                or original_status in NON_LIVING_ENEMY_STATUSES
            )
        )

        if current_hp <= 0 or was_already_defeated:
            creature["currentHitPoints"] = 0
            creature["status"] = _preferred_non_living_status(current_status, original_status)
        else:
            creature["currentHitPoints"] = current_hp


def _resolve_enemy_creature(
    encounter_info: Dict[str, Any],
    op_data: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Resolve an enemy creature reference from an encounter op payload."""
    reference = op_data.get("creature") or op_data.get("name") or op_data.get("target")
    if not isinstance(reference, str) or not reference.strip():
        return None, "missing_creature_reference"

    normalized_ref = _normalize_name_key(reference)
    for creature in encounter_info.get("creatures", []):
        if creature.get("type") != "enemy":
            continue
        candidate_name = creature.get("name")
        if not isinstance(candidate_name, str):
            continue
        if _normalize_name_key(candidate_name) == normalized_ref:
            return creature, "ok"

    return None, f"enemy_not_found:{reference}"


def _prepare_supported_encounter_ops(
    encounter_info: Dict[str, Any],
    ops_payload: Any,
) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """Validate and prepare supported encounter ops for deterministic apply."""
    if not isinstance(ops_payload, list):
        return None, "ops_not_list"
    if not ops_payload:
        return None, "ops_empty"

    prepared: List[Dict[str, Any]] = []

    for index, op_item in enumerate(ops_payload):
        if not isinstance(op_item, dict):
            return None, f"op_not_object:{index}"

        op_name = op_item.get("op")
        if not isinstance(op_name, str):
            return None, f"op_missing_name:{index}"
        if op_name not in SUPPORTED_ENCOUNTER_OPS:
            return None, f"unsupported_op:{op_name}"

        creature, reason = _resolve_enemy_creature(encounter_info, op_item)
        if creature is None:
            return None, f"{reason}:{index}"

        prepared_op: Dict[str, Any] = {
            "op": op_name,
            "creature": creature,
            "index": index,
        }

        if op_name == "hp_delta":
            delta = op_item.get("delta")
            if not isinstance(delta, int):
                return None, f"hp_delta_missing_int_delta:{index}"
            prepared_op["delta"] = delta
        elif op_name == "set_hp":
            hp_value = op_item.get("hp")
            if not isinstance(hp_value, int):
                return None, f"set_hp_missing_int_hp:{index}"
            prepared_op["hp"] = hp_value
        elif op_name in {"condition_add", "condition_remove"}:
            condition_value = op_item.get("condition")
            if not isinstance(condition_value, str) or not condition_value.strip():
                return None, f"{op_name}_missing_condition:{index}"
            prepared_op["condition"] = condition_value.strip()
        elif op_name == "set_status":
            status_value = op_item.get("status")
            if not isinstance(status_value, str):
                return None, f"set_status_missing_status:{index}"
            normalized_status = status_value.strip().lower()
            if normalized_status not in ALLOWED_STATUS_VALUES:
                return None, f"set_status_invalid_status:{status_value}"
            prepared_op["status"] = normalized_status

        prepared.append(prepared_op)

    return prepared, "ok"


def _extract_expected_enemy_transitions(changes: Any) -> Dict[str, Dict[str, Any]]:
    """Extract deterministic enemy final-state hints from combat prose mirror text."""
    if not isinstance(changes, str) or not changes.strip():
        return {}

    transitions: Dict[str, Dict[str, Any]] = {}
    pattern = re.compile(
        r"(?P<name>[A-Za-z0-9_][A-Za-z0-9_ '\-]*?)\s+takes\b[^()]*\(HP\s*(?P<old>-?\d+)\s*->\s*(?P<new>-?\d+)\)",
        re.IGNORECASE,
    )

    for match in pattern.finditer(changes):
        normalized_name = _normalize_name_key(match.group("name"))
        if not normalized_name:
            continue

        final_hp = max(0, _coerce_int(match.group("new"), 0))
        trailing_slice = changes[match.end():match.end() + 80].lower()
        final_status = None
        for status_value in NON_LIVING_ENEMY_STATUSES:
            if f"now {status_value}" in trailing_slice:
                final_status = status_value
                break

        transitions[normalized_name] = {
            "final_hp": final_hp,
            "final_status": final_status,
        }

    return transitions


def _is_prepared_encounter_ops_replay(
    encounter_info: Dict[str, Any],
    prepared_ops: List[Dict[str, Any]],
    changes: Any,
) -> bool:
    """Detect already-applied resumed enemy ops using authoritative encounter state."""
    expected_transitions = _extract_expected_enemy_transitions(changes)
    if not expected_transitions or not prepared_ops:
        return False

    replay_verified = False

    for op_data in prepared_ops:
        op_name = op_data.get("op")
        if op_name not in {"hp_delta", "set_hp", "set_status"}:
            return False

        creature = op_data.get("creature")
        if not isinstance(creature, dict):
            return False

        normalized_name = _normalize_name_key(creature.get("name", ""))
        expected = expected_transitions.get(normalized_name)
        if not expected:
            return False

        current_hp = _coerce_int(creature.get("currentHitPoints", 0), 0)
        current_status = str(creature.get("status", "alive")).strip().lower()
        expected_hp = _coerce_int(expected.get("final_hp"), 0)
        expected_status = str(expected.get("final_status") or "").strip().lower()

        if current_hp != expected_hp:
            return False

        if expected_status:
            if current_status != expected_status:
                return False
        elif expected_hp <= 0 and current_status not in NON_LIVING_ENEMY_STATUSES:
            return False

        replay_verified = True

    return replay_verified


def _apply_prepared_encounter_ops(
    encounter_info: Dict[str, Any],
    prepared_ops: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply prepared supported encounter ops to enemy creatures only."""
    for op_data in prepared_ops:
        creature = op_data["creature"]
        op_name = op_data["op"]

        if op_name == "hp_delta":
            current_hp = creature.get("currentHitPoints", 0)
            if not isinstance(current_hp, int):
                current_hp = 0
            creature["currentHitPoints"] = current_hp + op_data["delta"]
        elif op_name == "set_hp":
            creature["currentHitPoints"] = op_data["hp"]
        elif op_name == "condition_add":
            conditions = creature.get("conditions")
            if not isinstance(conditions, list):
                conditions = []
            if op_data["condition"] not in conditions:
                conditions.append(op_data["condition"])
            creature["conditions"] = conditions
        elif op_name == "condition_remove":
            conditions = creature.get("conditions")
            if not isinstance(conditions, list):
                conditions = []
            creature["conditions"] = [c for c in conditions if c != op_data["condition"]]
        elif op_name == "set_status":
            creature["status"] = op_data["status"]

    return encounter_info


def _sync_non_enemy_creatures(encounter_info: Dict[str, Any], path_manager: ModulePathManager) -> None:
    """Sync player/NPC combat state from their source files."""
    for creature in encounter_info.get("creatures", []):
        if creature.get("type") == "player":
            from updates.update_character_info import normalize_character_name

            player_file = path_manager.get_character_path(normalize_character_name(creature["name"]))
            try:
                with open(player_file, "r") as file:
                    player_data = json.load(file)
                    creature["currentHitPoints"] = player_data.get("hitPoints", creature.get("currentHitPoints", 0))
                    creature["maxHitPoints"] = player_data.get("maxHitPoints", creature.get("maxHitPoints", 0))
                    creature["status"] = player_data.get("status", creature.get("status", "alive"))
                    creature["conditions"] = player_data.get("condition_affected", [])
                    if "armorClass" in player_data:
                        creature["armorClass"] = player_data["armorClass"]
            except Exception as e:
                print(f"ERROR: Failed to sync player data from {player_file}: {str(e)}")

        elif creature.get("type") == "npc":
            from updates.update_character_info import find_character_file_fuzzy

            matched_name = find_character_file_fuzzy(creature["name"])
            if matched_name:
                npc_file = path_manager.get_character_path(matched_name)
                try:
                    with open(npc_file, "r") as file:
                        npc_data = json.load(file)
                        creature["currentHitPoints"] = npc_data.get("hitPoints", creature.get("currentHitPoints", 0))
                        creature["maxHitPoints"] = npc_data.get("maxHitPoints", creature.get("maxHitPoints", 0))
                        creature["status"] = npc_data.get("status", creature.get("status", "alive"))
                        creature["conditions"] = npc_data.get("condition_affected", [])
                        if "armorClass" in npc_data:
                            creature["armorClass"] = npc_data["armorClass"]
                except Exception as e:
                    print(f"ERROR: Failed to sync NPC data from {npc_file}: {str(e)}")
            else:
                print(f"WARNING: Could not find NPC file for '{creature['name']}' using fuzzy matching")


def _normalize_creature_statuses(encounter_info: Dict[str, Any]) -> None:
    """Normalize creature status values to schema-legal vocabulary."""
    status_mapping = {
        "destroyed": "dead",
        "panicked": "alive",
        "fled": "defeated",
        "fleeing": "defeated",
        "dying": "unconscious",
    }

    for creature in encounter_info.get("creatures", []):
        current_status = creature.get("status", "alive")
        if current_status in status_mapping:
            print(
                f"INFO: Normalizing invalid status '{current_status}' to '{status_mapping[current_status]}' "
                f"for {creature.get('name', 'unknown')}"
            )
            creature["status"] = status_mapping[current_status]


def _finalize_encounter_update(
    encounter_info: Dict[str, Any],
    original_info: Dict[str, Any],
    schema: Dict[str, Any],
    encounter_id: str,
    path_manager: ModulePathManager,
) -> Dict[str, Any]:
    """Apply sync/normalization, validate, and persist encounter state."""
    _normalize_enemy_defeat_states(encounter_info, original_info)
    _sync_non_enemy_creatures(encounter_info, path_manager)
    _normalize_creature_statuses(encounter_info)

    validate(instance=encounter_info, schema=schema)
    compare_json(original_info, encounter_info)
    info("SUCCESS: Encounter update - PASS", category="encounter_updates")

    with open(f"modules/encounters/encounter_{encounter_id}.json", "w") as file:
        json.dump(encounter_info, file, indent=2)

    return encounter_info

def update_encounter(encounter_id, changes, ops=None, max_retries=3):
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

    has_changes_payload = isinstance(changes, str) and bool(changes.strip())

    # TABLETOP MODE: Prefer deterministic enemy encounter ops when supported.
    # Fail open to legacy prose-based encounter updates for ambiguous payloads.
    if ops is not None:
        prepared_ops, ops_reason = _prepare_supported_encounter_ops(encounter_info, ops)
        if prepared_ops is not None:
            try:
                if _is_prepared_encounter_ops_replay(encounter_info, prepared_ops, changes):
                    info(
                        "ENCOUNTER_OPS_ROUTE mode=noop reason=duplicate_replay_detected",
                        category="encounter_updates",
                    )
                    return original_info
                encounter_info = _apply_prepared_encounter_ops(encounter_info, prepared_ops)
                info(
                    "ENCOUNTER_OPS_ROUTE mode=ops reason=supported_ops_applied",
                    category="encounter_updates",
                )
                return _finalize_encounter_update(
                    encounter_info,
                    original_info,
                    schema,
                    encounter_id,
                    path_manager,
                )
            except ValidationError as e:
                warning(
                    f"ENCOUNTER_OPS_ROUTE mode=fallback reason=ops_validation_error detail={e}",
                    category="encounter_updates",
                )
                encounter_info = copy.deepcopy(original_info)
            except Exception as e:
                warning(
                    f"ENCOUNTER_OPS_ROUTE mode=fallback reason=ops_apply_exception detail={e}",
                    category="encounter_updates",
                )
                encounter_info = copy.deepcopy(original_info)
        else:
            warning(
                f"ENCOUNTER_OPS_ROUTE mode=fallback reason={ops_reason}",
                category="encounter_updates",
            )

    if not has_changes_payload:
        warning(
            "ENCOUNTER_OPS_ROUTE mode=noop reason=missing_changes_and_no_supported_ops",
            category="encounter_updates",
        )
        return original_info

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

        # Get AI's response
        config = get_model_config("encounter_update", ENCOUNTER_UPDATE_MODEL)  # OPENROUTER: 3-tier model selection
        response = client.chat.completions.create(
            model=config["model"], **config.get("extra_body", {}),
            temperature=TEMPERATURE,
            messages=prompt
        )
        
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
            encounter_info = copy.deepcopy(original_info)
            encounter_info = update_nested_dict(encounter_info, updates)

            return _finalize_encounter_update(
                encounter_info,
                original_info,
                schema,
                encounter_id,
                path_manager,
            )

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
