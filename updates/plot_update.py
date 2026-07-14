# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

import copy
import json
from jsonschema import validate, ValidationError
from core.ai import api_client
import config
import time

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass

# Import model configuration from config.py
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_write_json, safe_read_json
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("plot_update")

from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T077", "updates/plot_update.py", 257)

# Constants
TEMPERATURE = 0.7

# ANSI escape codes - REMOVED per CLAUDE.md guidelines
# All color codes have been removed to prevent Windows console encoding errors

def load_schema():
    with open("schemas/plot_schema.json", "r") as schema_file:
        return json.load(schema_file)


def _find_plot_update_target(plot_info_data, plot_point_id):
    """Return ``(parent_plot_id, is_side_quest)`` for a stable plot ID."""
    for plot_point in plot_info_data.get("plotPoints", []):
        if plot_point.get("id") == plot_point_id:
            return plot_point_id, False
        if any(
            quest.get("id") == plot_point_id
            for quest in plot_point.get("sideQuests", [])
            if isinstance(quest, dict)
        ):
            return plot_point.get("id"), True
    return None, None


def _apply_plot_delta(
    base_plot_info,
    updated_sections,
    target_id,
    expected_status,
    expected_impact,
):
    """Validate T077's exact delta contract and apply it to a fresh snapshot.

    The model may update only the requested main plot point or side quest, and
    it must echo the requested status and impact exactly. This prevents a
    malformed retry from leaking unrelated or unsaved mutations into the
    caller-visible object.
    """
    parent_id, is_side_quest = _find_plot_update_target(base_plot_info, target_id)
    if parent_id is None:
        raise ValueError(f"Unknown plot or side-quest ID: {target_id}")
    if not isinstance(updated_sections, dict) or set(updated_sections) != {parent_id}:
        raise ValueError("T077 must return exactly the parent plot-point ID")

    update = updated_sections[parent_id]
    if not isinstance(update, dict):
        raise ValueError("T077 plot update must be an object")

    if is_side_quest:
        if set(update) != {"sideQuests"}:
            raise ValueError("T077 side-quest update may contain only sideQuests")
        side_quests = update["sideQuests"]
        if not isinstance(side_quests, list) or len(side_quests) != 1:
            raise ValueError("T077 must return exactly one side-quest delta")
        delta = side_quests[0]
        if not isinstance(delta, dict) or set(delta) != {
            "id",
            "status",
            "plotImpact",
        }:
            raise ValueError("T077 side-quest delta has an invalid shape")
        if delta["id"] != target_id:
            raise ValueError("T077 returned the wrong side-quest ID")
    else:
        if set(update) != {"status", "plotImpact"}:
            raise ValueError("T077 main-plot delta has an invalid shape")
        delta = update

    if delta.get("status") != expected_status:
        raise ValueError("T077 returned a status other than the requested status")
    if delta.get("plotImpact") != expected_impact:
        raise ValueError("T077 returned a plot impact other than the requested impact")

    candidate = copy.deepcopy(base_plot_info)
    for plot_point in candidate.get("plotPoints", []):
        if plot_point.get("id") != parent_id:
            continue
        if is_side_quest:
            for side_quest in plot_point.get("sideQuests", []):
                if side_quest.get("id") == target_id:
                    side_quest["status"] = delta["status"]
                    side_quest["plotImpact"] = delta["plotImpact"]
                    return candidate
        else:
            plot_point["status"] = delta["status"]
            plot_point["plotImpact"] = delta["plotImpact"]
            return candidate

    raise ValueError(f"Plot target disappeared while applying update: {target_id}")

def update_party_tracker(plot_point_id, new_status, plot_impact, plot_filename):
    # DEPRECATED: activeQuests tracking has been deprecated in favor of using module_plot.json as the single source of truth
    # The code below is commented out but preserved for reference and backward compatibility
    # All quest data should be read directly from module_plot.json
    
    party_tracker = safe_read_json("party_tracker.json")
    if not party_tracker:
        error("FAILURE: Could not read party_tracker.json", category="file_operations")
        return

    # Use ModulePathManager to get module plot path with current module
    current_module = party_tracker.get("module", "").replace(" ", "_")
    path_manager = ModulePathManager(current_module)
    plot_file_path = path_manager.get_plot_path()

    try:
        plot_info = safe_read_json(plot_file_path)
    except FileNotFoundError:
        error(f"FAILURE: Plot file {plot_filename} not found in update_party_tracker", category="file_operations")
        return
    except json.JSONDecodeError:
        error(f"FAILURE: Invalid JSON in {plot_filename} in update_party_tracker", category="file_operations")
        return

    # DEPRECATED: The following activeQuests update logic is no longer used
    # module_plot.json is now the authoritative source for all quest data
    """
    plot_point_to_update = next((p for p in plot_info.get("plotPoints", []) if p["id"] == plot_point_id), None)

    if plot_point_to_update:
        existing_quest = next((q for q in party_tracker.get("activeQuests", []) if q.get("id") == plot_point_id), None)
        if existing_quest:
            existing_quest["status"] = new_status
        elif new_status != "completed":
            party_tracker.setdefault("activeQuests", []).append({ # Use setdefault for safety
                "id": plot_point_id,
                "title": plot_point_to_update["title"],
                "description": plot_point_to_update["description"],
                "status": new_status
            })

        for side_quest in plot_point_to_update.get("sideQuests", []):
            existing_side_quest = next((q for q in party_tracker.get("activeQuests", []) if q.get("id") == side_quest["id"]), None)
            if existing_side_quest:
                existing_side_quest["status"] = side_quest["status"] # This should be new_status if it's for the SQ being updated
                                                                  # Or, if side quests are updated independently, this is fine.
                                                                  # Assuming side quests are updated based on their own status in plot_info.
            elif side_quest["status"] != "completed": # Check side_quest's status from plot_info
                 party_tracker.setdefault("activeQuests", []).append({
                    "id": side_quest["id"],
                    "title": side_quest["title"],
                    "description": side_quest["description"],
                    "status": side_quest["status"] # Use the status from plot_info
                })

    party_tracker["activeQuests"] = [q for q in party_tracker.get("activeQuests", []) if q.get("status") != "completed"]
    """

    # Still save party_tracker in case other parts were modified
    if not safe_write_json("party_tracker.json", party_tracker):
        error("FAILURE: Failed to save party_tracker.json", category="file_operations")

    debug(f"STATE_CHANGE: Party tracker updated for plot point {plot_point_id}", category="plot_updates")

def update_plot(plot_point_id_param, new_status_param, plot_impact_param, plot_filename_param, max_retries=3): # Renamed params
    try:
        # Use unified module plot file with current module from party tracker
        party_tracker = safe_read_json("party_tracker.json")
        current_module = party_tracker.get("module", "").replace(" ", "_") if party_tracker else None
        path_manager = ModulePathManager(current_module)
        plot_file_path = path_manager.get_plot_path()
            
        plot_info_data = safe_read_json(plot_file_path)
        if not plot_info_data:
            error("FAILURE: Could not read plot file", category="file_operations")
            return None

        # MED-4 (#127): snapshot the on-disk plot state before mutating, so we can
        # return a consistent (disk-matching) object if the write later fails.
        _plot_pre_mutation = copy.deepcopy(plot_info_data)
    except FileNotFoundError:
        error(f"FAILURE: Plot file {plot_filename_param} not found", category="file_operations")
        return None # Or raise error
    except json.JSONDecodeError:
        error(f"FAILURE: Invalid JSON in {plot_filename_param}", category="file_operations")
        return None # Or raise error


    plot_schema_data = load_schema() # Renamed variable
    parent_id, _is_side_quest = _find_plot_update_target(
        _plot_pre_mutation, plot_point_id_param
    )
    if parent_id is None:
        error(
            f"FAILURE: Plot target {plot_point_id_param} does not exist",
            category="plot_updates",
        )
        return copy.deepcopy(_plot_pre_mutation)

    for attempt in range(max_retries):
        prompt_messages = [ # Renamed variable
            {"role": "system", "content": """You are an assistant that updates plot information for a role playing game. Given the current plot information and a plot point ID with its new status and plot impact, return only the updated sections of the JSON. Ensure that the updates adhere to the provided schema. Pay close attention to enum values and required fields. Be sure to update both the 'status' and 'plotImpact' fields for the specified plot point. Return the updated sections as a JSON object with the plot point ID as the key.

Examples:
1. Input: Plot point to update: PP001, New status: in progress, Plot impact: The party has entered the mines and met Old Miner Gregor.
   Output: {"PP001": {"status": "in progress", "plotImpact": "The party has entered the mines and met Old Miner Gregor."}}

2. Input: Plot point to update: PP003, New status: completed, Plot impact: The party successfully navigated the collapsed passage and found signs of recent excavation.
   Output: {"PP003": {"status": "completed", "plotImpact": "The party successfully navigated the collapsed passage and found signs of recent excavation."}}

3. Input: Plot point to update: PP005, New status: in progress, Plot impact: The party is currently battling the Fire Beetles and investigating the strange energy source.
   Output: {"PP005": {"status": "in progress", "plotImpact": "The party is currently battling the Fire Beetles and investigating the strange energy source."}}

4. Input: Plot point to update: SQ001, New status: completed, Plot impact: The party found Old Miner Gregor's lost tools in the Equipment Storage.
   Output: {"PP001": {"sideQuests": [{"id": "SQ001", "status": "completed", "plotImpact": "The party found Old Miner Gregor's lost tools in the Equipment Storage."}]}}

5. Input: Plot point to update: PP011, New status: in progress, Plot impact: The party is exploring the Crystal Cavern and deciphering hidden messages left by the dwarves.
   Output: {"PP011": {"status": "in progress", "plotImpact": "The party is exploring the Crystal Cavern and deciphering hidden messages left by the dwarves."}}"""
            },
            {"role": "user", "content": f"Current plot info: {json.dumps(_plot_pre_mutation)}\n\nPlot point to update: {plot_point_id_param}\nNew status: {new_status_param}\nPlot impact: {plot_impact_param}"}
        ]

        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            plot_config = config.PLOT_UPD_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            plot_config = config.PLOT_UPD_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            plot_config = config.PLOT_UPD_LMSTUDIO
        else:  # legacy
            plot_config = config.PLOT_UPD_LEGACY

        try:
            response = capture_and_fanout("T077", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=prompt_messages,
                model=plot_config["model"],
                temperature=TEMPERATURE,
                **{k: v for k, v in plot_config.items() if k != "model"})

            # Track usage if available
            if USAGE_TRACKING_AVAILABLE:
                try:
                    track_response(response)
                except Exception:
                    pass

            ai_response_content = response.choices[0].message.content.strip()
            if ai_response_content.startswith("```json"):
                ai_response_content = ai_response_content.split("```json", 1)[1]
            if ai_response_content.endswith("```"):
                ai_response_content = ai_response_content.rsplit("```", 1)[0]
            ai_response_content = ai_response_content.strip()

            updated_sections = json.loads(ai_response_content)
            candidate_plot = _apply_plot_delta(
                _plot_pre_mutation,
                updated_sections,
                plot_point_id_param,
                new_status_param,
                plot_impact_param,
            )
            validate(instance=candidate_plot, schema=plot_schema_data)

            info(f"SUCCESS: Updated and validated plot info on attempt {attempt + 1}", category="plot_updates")

            try:
                write_succeeded = safe_write_json(plot_file_path, candidate_plot)
            except Exception as write_error:
                write_succeeded = False
                error(
                    f"FAILURE: Plot write raised an exception: {write_error}",
                    category="file_operations",
                )
            if not write_succeeded:
                # MED-4 (#127): write failed -- discard the unsaved in-memory mutation
                # and return the pre-mutation (disk-matching) state, so the returned
                # object stays consistent with what is actually on disk. party_tracker
                # is NOT updated (early return below the write), keeping them consistent.
                error("FAILURE: Failed to save plot file; rolling back in-memory mutation",
                      category="file_operations")
                return copy.deepcopy(_plot_pre_mutation)

            update_party_tracker(plot_point_id_param, new_status_param, plot_impact_param, plot_filename_param)

            debug(f"STATE_CHANGE: Plot information updated for plot point {plot_point_id_param}", category="plot_updates")
            
            # Generate player-friendly quest descriptions
            try:
                from utils.quest_player_formatter import format_quests_for_player
                if current_module:
                    debug(f"QUEST_FORMAT: Updating player-friendly quests for module {current_module}", category="plot_updates")
                    format_quests_for_player(current_module)
            except Exception as e:
                warning(f"QUEST_FORMAT: Failed to update player-friendly quests: {e}", category="plot_updates")
            
            return candidate_plot

        except (json.JSONDecodeError, ValidationError, ValueError, TypeError, KeyError, AttributeError) as e:
            warning(
                f"VALIDATION: T077 attempt {attempt + 1} rejected: {e}",
                category="plot_updates",
            )
        except Exception as e:
            warning(
                f"AI_PROCESSING: T077 provider attempt {attempt + 1} failed: {e}",
                category="ai_processing",
            )

        if attempt == max_retries - 1:
            error(f"FAILURE: Failed to update plot info after {max_retries} attempts. Returning original plot info", category="plot_updates")
            return copy.deepcopy(_plot_pre_mutation)

        time.sleep(1)

    return copy.deepcopy(_plot_pre_mutation)