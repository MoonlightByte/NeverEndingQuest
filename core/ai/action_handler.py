# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Action Handler
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# ACTION_HANDLER.PY - COMMAND PATTERN IMPLEMENTATION
# ============================================================================
# 
# ARCHITECTURE ROLE: Action Processing Layer in Command Pattern
# 
# This module implements the Command Pattern for the 5e system, encapsulating
# all game interactions as discrete, typed actions with specific parameters.
# It serves as the central dispatcher for all game state modifications.
# 
# KEY RESPONSIBILITIES:
# - Parse and validate action commands from AI responses
# - Route actions to appropriate subsystem handlers
# - Module transition detection and marker insertion
# - Ensure atomic execution of compound operations
# - Maintain consistency across all game state updates
# - Provide standardized error handling for all actions
# 
# SUPPORTED ACTION TYPES:
# - updateCharacterInfo: Character stat and inventory management
# - transitionLocation: Movement and exploration actions
# - createEncounter: Combat encounter initialization
# - updatePlot: Module narrative progression
# - updateWorldTime: Game time advancement
# - And extensible action framework for future features
# 
# ARCHITECTURAL INTEGRATION:
# - Called by main.py as part of AI response processing
# - Coordinates with various managers (combat, location, character)
# - Uses ModulePathManager for file operations
# - Implements our "Data Integrity Above All" principle
# 
# DESIGN PATTERNS:
# - Command Pattern: Actions as first-class objects
# - Strategy Pattern: Different handlers for different action types
# - Template Method: Consistent action processing pipeline
# ============================================================================

import copy
import json
import hashlib
import subprocess
import sys
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4
from core.ai import api_client
import model_config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T013", "core/ai/action_handler.py", 1255)
register_callsite("T012", "core/ai/action_handler.py", 676)
register_callsite("T014", "core/ai/action_handler.py", 2506)
import config
from core.managers.location_manager import get_location_data
from utils.module_path_manager import ModulePathManager
from updates.plot_update import update_plot
from utils.encoding_utils import sanitize_text, safe_json_dump, safe_json_load
from utils.file_operations import safe_read_json, safe_write_json
from core.managers.status_manager import (
    status_transitioning_location, status_updating_character, status_updating_party,
    status_updating_plot, status_advancing_time, status_processing_levelup
)
from utils.location_path_finder import LocationGraph
from core.ai.conversation_utils import handle_module_conversation_segmentation
from utils.enhanced_logger import debug, info, warning, error, set_script_name


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _generator_script_path(filename):
    """Resolve generator subprocesses independently of the active game cwd."""
    return os.path.join(_PROJECT_ROOT, "core", "generators", filename)

# Import token tracking
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass

# Import socketio for web interface progress updates
try:
    from web.web_interface import socketio
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    socketio = None

# Set script name for logging
set_script_name("action_handler")


def _module_transition_completion_id(
    from_module: str,
    to_module: str,
    conversation_history,
) -> str:
    """Derive one stable identity for the same persisted transition event."""
    canonical_event = {
        "from_module": from_module,
        "to_module": to_module,
        "conversation_history": conversation_history,
    }
    encoded = json.dumps(
        canonical_event,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _completion_publication_state(campaign_manager, pending_archive):
    """Classify whether failed publication left durable recovery work."""
    try:
        return campaign_manager.get_module_completion_publication_state(
            pending_archive["from_module"],
            pending_archive["completion_id"],
        )
    except Exception as state_exc:
        warning(
            "FAILURE: Could not classify module-transition publication "
            f"state: {state_exc}",
            category="module_management",
        )
        return "unknown"

# Action type constants
ACTION_CREATE_ENCOUNTER = "createEncounter"
ACTION_UPDATE_ENCOUNTER = "updateEncounter"
ACTION_UPDATE_TIME = "updateTime"
ACTION_UPDATE_PLOT = "updatePlot"
ACTION_EXIT_GAME = "exitGame"
ACTION_TRANSITION_LOCATION = "transitionLocation"
ACTION_LEVEL_UP = "levelUp"
ACTION_UPDATE_CHARACTER_INFO = "updateCharacterInfo"
ACTION_REMOVE_EFFECT = "removeEffect"
ACTION_UPDATE_PARTY_NPCS = "updatePartyNPCs"
ACTION_CREATE_NEW_MODULE = "createNewModule"
ACTION_ESTABLISH_HUB = "establishHub"
ACTION_STORAGE_INTERACTION = "storageInteraction"
ACTION_UPDATE_PARTY_TRACKER = "updatePartyTracker"
ACTION_MOVE_BACKGROUND_NPC = "moveBackgroundNPC"
ACTION_SAVE_GAME = "saveGame"
ACTION_RESTORE_GAME = "restoreGame"
ACTION_LIST_SAVES = "listSaves"
ACTION_DELETE_SAVE = "deleteSave"


_NPC_MOVEMENT_LOCKS = {}
_NPC_MOVEMENT_LOCKS_GUARD = threading.Lock()
PENDING_LOCATION_TRANSITION_FILE = (
    "modules/conversation_history/pending_location_transition.json"
)


@dataclass(frozen=True)
class ApprovedTransitionPlan:
    """Immutable authorization created by pre-validation for one exact move.

    This object deliberately stays in memory.  It is passed with the accepted
    provider response and is never persisted or placed in a process-global
    cache where a later request could accidentally reuse it.
    """

    origin_location_id: str
    destination_location_id: str
    module_name: str
    path: tuple
    topology_identity: str
    evidence_identity: str


@dataclass(frozen=True)
class TransitionPrevalidationOutcome:
    """Private, non-persisted result of one transition prevalidation pass."""

    approved: bool
    reason_code: str
    message: str = ""
    facts: dict = None
    plan: object = None
    intermediate_destination_id: str = ""
    intermediate_destination_name: str = ""


def _stable_transition_hash(value):
    """Return a deterministic identity for JSON-like transition evidence."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _transition_topology_identity(location_graph, path, module_name):
    """Adapter for the canonical snapshot API, with a legacy graph fallback."""
    identity_provider = getattr(
        location_graph, "get_transition_snapshot_identity", None
    )
    if callable(identity_provider):
        identity = identity_provider(path=path, module_name=module_name)
        if isinstance(identity, dict):
            identity = identity.get("topology_identity") or identity.get("id")
        if identity:
            return str(identity)

    relevant_nodes = {}
    relevant_edges = {}
    for location_id in path:
        relevant_nodes[location_id] = location_graph.nodes.get(location_id)
        relevant_edges[location_id] = sorted(
            str(item) for item in location_graph.edges.get(location_id, [])
        )
    return _stable_transition_hash(
        {
            "module": module_name,
            "path": list(path),
            "nodes": relevant_nodes,
            "edges": relevant_edges,
        }
    )


def _transition_evidence_identity(path_analysis, plot_data):
    """Adapter for analyzer-owned evidence identities, with a data fallback."""
    if isinstance(path_analysis, dict):
        supplied = (
            path_analysis.get("evidence_identity")
            or path_analysis.get("snapshot_identity")
        )
        if supplied:
            return _stable_transition_hash(
                {
                    "route_evidence_identity": str(supplied),
                    "plot_identity": _stable_transition_hash(plot_data),
                }
            )
    return _stable_transition_hash(
        {"path_analysis": path_analysis, "plot_data": plot_data}
    )


def _approved_transition_plan(
    *,
    origin_location_id,
    destination_location_id,
    module_name,
    path,
    path_analysis,
    plot_data,
    location_graph,
    topology_identity=None,
):
    return ApprovedTransitionPlan(
        origin_location_id=str(origin_location_id),
        destination_location_id=str(destination_location_id),
        module_name=str(module_name),
        path=tuple(str(item) for item in path),
        topology_identity=(
            str(topology_identity)
            if topology_identity
            else _transition_topology_identity(
                location_graph, path, module_name
            )
        ),
        evidence_identity=_transition_evidence_identity(
            path_analysis, plot_data
        ),
    )


def _write_location_transition_checkpoint(checkpoint):
    """Durably publish the small, non-secret within-module recovery record."""
    safe_json_dump(checkpoint, PENDING_LOCATION_TRANSITION_FILE)


def _new_current_transition_checkpoint(
    *,
    module_name,
    origin_area_id,
    origin_location_id,
    origin_location_name,
    destination_location_id,
    destination_location_name,
    destination_area_id,
    destination_area_name,
    conversation_history,
    deferred_actions,
    origin_party_tracker,
):
    """Build the approved v2 record without content-derived authority."""
    operation_id = str(uuid4())
    persisted_history = safe_json_load(
        "modules/conversation_history/conversation_history.json"
    )
    if not isinstance(persisted_history, list):
        persisted_history = json.loads(json.dumps(conversation_history))
    segment_start = 0
    for index in range(len(persisted_history) - 1, -1, -1):
        message = persisted_history[index]
        content = message.get("content", "") if isinstance(message, dict) else ""
        if isinstance(message, dict) and message.get("role") == "user" and (
            "Location transition:" in content or "Module transition:" in content
        ):
            segment_start = index + 1
            break
    origin_segment = persisted_history[segment_start:]
    journal = safe_json_load("journal.json")
    journal_entries = (
        journal.get("entries", [])
        if isinstance(journal, dict) and isinstance(journal.get("entries"), list)
        else []
    )
    world = origin_party_tracker.get("worldConditions", {})
    staged_journal_entry = {
        "date": "%s %s %s"
        % (
            world.get("year", "N/A"),
            world.get("month", "N/A"),
            world.get("day", "N/A"),
        ),
        "time": world.get("time", "N/A"),
        "location": sanitize_text(origin_location_name),
        "summary": None,
    }
    path_manager = ModulePathManager(str(module_name))
    action_records = []
    for index, action in enumerate(deferred_actions or []):
        action_record = {
            "index": index,
            "operation_id": str(uuid4()),
            "family": action.get("action") if isinstance(action, dict) else None,
            "status": "pending",
            "action": json.loads(json.dumps(action)),
            "receipt": None,
        }
        if action_record["family"] == "updateTime":
            from updates.update_world_time import calculate_world_time_fields

            parameters = action.get("parameters", {})
            minutes = int(parameters.get("timeEstimate"))
            clock_before = {
                field: world.get(field)
                for field in ("time", "day", "month", "year")
            }
            action_record["receipt"] = {
                "kind": "updateTime",
                "minutes": minutes,
                "before": clock_before,
                "after": calculate_world_time_fields(world, minutes),
            }
        elif action_record["family"] == "removeEffect":
            from core.managers.effects_runtime import prepare_remove_effect

            parameters = action.get("parameters", {})
            action_record["receipt"] = prepare_remove_effect(
                parameters.get("characterName"),
                effect_id=parameters.get("effectId"),
                name=parameters.get("effectName"),
                reason=parameters.get("reason") or "removed",
            )
        elif action_record["family"] == "establishHub":
            from core.managers.campaign_manager import prepare_hub_establishment

            parameters = action.get("parameters", {})
            hub_name = parameters.get("hubName")
            if not hub_name:
                raise ValueError("establishHub requires hubName")
            action_record["receipt"] = prepare_hub_establishment(
                hub_name,
                {
                    "hubType": parameters.get("hubType", "settlement"),
                    "description": parameters.get("description", ""),
                    "services": parameters.get("services", []),
                    "ownership": parameters.get("ownership", "party"),
                },
            )
            action_record["receipt"]["note"] = {
                "message_id": str(uuid4()),
                "content": (
                    "Dungeon Master Note: '%s' has been established as a hub "
                    "location. The party can now return here from other adventures."
                    % sanitize_text(hub_name)
                ),
            }
        elif action_record["family"] == "listSaves":
            action_record["receipt"] = {
                "kind": "listSaves",
                "message_id": str(uuid4()),
            }
        elif action_record["family"] == "saveGame":
            parameters = action.get("parameters", {})
            action_record["receipt"] = {
                "kind": "saveGame",
                "description": parameters.get("description", ""),
                "save_mode": parameters.get("saveMode", "essential"),
                "save_folder": "save_%s_%s"
                % (
                    datetime.now().strftime("%Y%m%d_%H%M%S"),
                    action_record["operation_id"].split("-")[0],
                ),
                "message_id": str(uuid4()),
            }
        elif action_record["family"] == "deleteSave":
            from updates.save_game_manager import SaveGameManager

            parameters = action.get("parameters", {})
            action_record["receipt"] = SaveGameManager().prepare_staged_delete(
                parameters.get("saveFolder"), action_record["operation_id"]
            )
            action_record["receipt"]["message_id"] = str(uuid4())
        elif action_record["family"] == "exitGame":
            action_record["receipt"] = {"kind": "exitGame"}
        action_records.append(action_record)
    return {
        "version": 2,
        "kind": "current_transition",
        "movement_kind": "within_module",
        "operation_id": operation_id,
        # Compatibility key for callers which correlate v1 and v2 without
        # interpreting either record's identity scheme.
        "transition_id": operation_id,
        "module_name": str(module_name),
        "origin_area_id": str(origin_area_id),
        "origin_area_path": path_manager.get_area_path(str(origin_area_id)),
        "origin_location_id": str(origin_location_id),
        "origin_location_name": sanitize_text(origin_location_name),
        "destination_location_id": str(destination_location_id),
        "destination_location_name": sanitize_text(destination_location_name),
        "destination_area_id": str(destination_area_id),
        "destination_area_name": sanitize_text(destination_area_name),
        "origin_history_boundary": segment_start,
        "origin_segment_before": json.loads(json.dumps(origin_segment)),
        "departure_summary": {"status": "pending", "text": None, "provider_response_id": None},
        "departure_commit": {
            "status": "pending",
            "transaction_id": str(uuid4()),
            "area_path": path_manager.get_area_path(str(origin_area_id)),
            "area_owned_before": None,
            "area_owned_after": None,
            "journal_entry_index": len(journal_entries),
            "journal_entry_before": None,
            "journal_entry_after": staged_journal_entry,
        },
        "location_reconciliation": {
            "status": "pending",
            "operation_id": str(uuid4()),
            "area_path": path_manager.get_area_path(str(origin_area_id)),
            "location_id": str(origin_location_id),
            "monsters_before": None,
            "monsters_after": None,
        },
        "narration": {
            "status": "pending",
            "text": None,
            "message_id": str(uuid4()),
            "history_index": None,
            "history_entry_before": None,
            "history_entry_after": None,
        },
        "conversation_compaction": {"status": "pending"},
        "chunked_chronicle": {"status": "pending"},
        "legacy_memory": {"status": "pending", "journal_operation_id": operation_id, "targets": []},
        "episode": {
            "status": "pending",
            "episode_operation_id": str(uuid4()),
            "boundary_turn_id": None,
            "source_entries_before": json.loads(json.dumps(origin_segment)),
            "episode_id": None,
        },
        "deferred_actions": {
            "status": "pending" if action_records else "committed",
            "actions": action_records,
            "cursor": 0,
            "receipts": [],
        },
        "plot_update": None,
        "module_handoff": None,
        "legacy_repair": None,
        "final_context": {"status": "pending"},
        "phase": "planned",
    }


def resolve_cross_module_target_projection(target_module, parameters):
    """Resolve one represented module destination to canonical IDs and names.

    The model chooses the module and may request an explicit represented
    destination.  Code owns identity reconciliation: it neither guesses from
    prose nor silently combines an area from one location with a location from
    another.  Invalid structured references return facts to the agent before
    any checkpoint or gameplay mutation exists.
    """
    parameters = parameters if isinstance(parameters, dict) else {}
    default_location_id, default_location_name, default_area_id, default_area_name = (
        get_module_starting_location(target_module)
    )
    supplied = {
        key: str(parameters.get(key) or "").strip()
        for key in (
            "currentAreaId",
            "currentArea",
            "currentLocationId",
            "currentLocation",
        )
    }
    if not any(supplied.values()):
        return {
            "currentAreaId": str(default_area_id),
            "currentArea": str(default_area_name),
            "currentLocationId": str(default_location_id),
            "currentLocation": str(default_location_name),
        }
    if not supplied["currentAreaId"] or not supplied["currentLocationId"]:
        raise ValueError(
            "an explicit module destination requires both currentAreaId and "
            "currentLocationId"
        )

    path_manager = ModulePathManager(str(target_module))
    matched = None
    for candidate_area_id in path_manager.get_area_ids() or []:
        area_data = safe_json_load(path_manager.get_area_path(candidate_area_id))
        if not isinstance(area_data, dict):
            continue
        for location in area_data.get("locations") or []:
            if (
                isinstance(location, dict)
                and str(location.get("locationId") or "")
                == supplied["currentLocationId"]
            ):
                matched = (
                    str(area_data.get("areaId") or candidate_area_id),
                    str(area_data.get("areaName") or ""),
                    str(location.get("locationId") or ""),
                    str(location.get("name") or ""),
                )
                break
        if matched is not None:
            break
    if matched is None:
        raise ValueError(
            "currentLocationId %s does not exist in module %s"
            % (supplied["currentLocationId"], target_module)
        )
    area_id, area_name, location_id, location_name = matched
    if supplied["currentAreaId"] != area_id:
        raise ValueError(
            "currentLocationId %s belongs to currentAreaId %s, not %s"
            % (location_id, area_id, supplied["currentAreaId"])
        )
    if supplied["currentArea"] and supplied["currentArea"] != area_name:
        raise ValueError(
            "currentAreaId %s is named %s, not %s"
            % (area_id, area_name, supplied["currentArea"])
        )
    if supplied["currentLocation"] and supplied["currentLocation"] != location_name:
        raise ValueError(
            "currentLocationId %s is named %s, not %s"
            % (location_id, location_name, supplied["currentLocation"])
        )
    return {
        "currentAreaId": area_id,
        "currentArea": area_name,
        "currentLocationId": location_id,
        "currentLocation": location_name,
    }


def stage_cross_module_root_checkpoint(
    action,
    clock_action,
    conversation_history,
    party_tracker_data,
    narration_source,
):
    """Stage canonical updatePartyTracker -> updateTime module travel."""
    from core.managers.campaign_manager import _party_module_transition_lock

    if not isinstance(action, dict) or action.get("action") != "updatePartyTracker":
        raise ValueError("cross-module travel must begin with updatePartyTracker")
    if not isinstance(clock_action, dict) or clock_action.get("action") != "updateTime":
        raise ValueError("cross-module travel requires one updateTime tail")
    parameters = copy.deepcopy(action.get("parameters") or {})
    source_module = str(party_tracker_data.get("module") or "")
    target_module = str(parameters.get("module") or "")
    if not source_module or not target_module or source_module == target_module:
        raise ValueError("cross-module travel requires a different module")
    target_values = resolve_cross_module_target_projection(
        target_module, parameters
    )
    parameters.update(target_values)
    parameters["module"] = target_module
    source_world = party_tracker_data.get("worldConditions") or {}
    checkpoint = _new_current_transition_checkpoint(
        module_name=source_module,
        origin_area_id=source_world.get("currentAreaId", ""),
        origin_location_id=source_world.get("currentLocationId", ""),
        origin_location_name=source_world.get("currentLocation", ""),
        destination_location_id=target_values["currentLocationId"],
        destination_location_name=target_values["currentLocation"],
        destination_area_id=target_values["currentAreaId"],
        destination_area_name=target_values["currentArea"],
        conversation_history=conversation_history,
        deferred_actions=[clock_action],
        origin_party_tracker=party_tracker_data,
    )
    checkpoint["movement_kind"] = "cross_module_root"
    source_projection = {
        "module": source_module,
        **{
            key: source_world.get(key)
            for key in (
                "currentAreaId",
                "currentArea",
                "currentLocationId",
                "currentLocation",
            )
        },
    }
    target_projection = {"module": target_module, **target_values}
    checkpoint["module_handoff"] = {
        "status": "pending",
        "completion_id": checkpoint["operation_id"],
        "source_projection": source_projection,
        "target_projection": target_projection,
        "parameters": parameters,
        "transition_history": json.loads(json.dumps(conversation_history)),
    }
    checkpoint["location_reconciliation"]["status"] = "not_applicable"
    checkpoint["departure_summary"]["status"] = "not_applicable"
    checkpoint["departure_commit"]["status"] = "not_applicable"
    checkpoint["episode"]["status"] = "not_applicable"
    checkpoint["conversation_compaction"]["status"] = "not_applicable"
    checkpoint["chunked_chronicle"]["status"] = "not_applicable"
    checkpoint["legacy_memory"]["status"] = "not_applicable"
    checkpoint["narration"]["source_prompt"] = str(narration_source or "")
    checkpoint["narration"]["status"] = "deferred_to_module_handoff"
    checkpoint["phase"] = "narration_deferred"
    with _party_module_transition_lock():
        existing = safe_json_load(PENDING_LOCATION_TRANSITION_FILE)
        if isinstance(existing, dict):
            raise RuntimeError("a prior location transition is awaiting recovery")
        _write_location_transition_checkpoint(checkpoint)
    return checkpoint


def load_current_transition_checkpoint(operation_id=None):
    checkpoint = safe_json_load(PENDING_LOCATION_TRANSITION_FILE)
    if not isinstance(checkpoint, dict):
        return None
    if checkpoint.get("version") != 2 or checkpoint.get("kind") != "current_transition":
        return None
    if operation_id and checkpoint.get("operation_id") != operation_id:
        return None
    return checkpoint


def prepare_current_transition_actions(operation_id):
    """Freeze required semantic sibling proposals before movement."""
    checkpoint = load_current_transition_checkpoint(operation_id)
    if checkpoint is None:
        raise RuntimeError("current transition checkpoint is unavailable")
    records = checkpoint["deferred_actions"]["actions"]
    for index, record in enumerate(records):
        family = record.get("family")
        if family not in {
            "updatePlot",
            "moveBackgroundNPC",
            "updateCharacterInfo",
            "storageInteraction",
            "updatePartyNPCs",
            "updatePartyTracker",
        } or record.get(
            "receipt"
        ) is not None:
            continue
        parameters = record["action"].get("parameters", {})
        if family == "updatePlot":
            from updates.plot_update import prepare_plot_update

            receipt = prepare_plot_update(
                parameters.get("plotPointId"),
                parameters.get("newStatus"),
                parameters.get("plotImpact"),
            )
            receipt["quest_projection"] = {"status": "pending"}
        elif family == "moveBackgroundNPC":
            receipt = prepare_background_npc_movement(
                parameters.get("npcName"),
                parameters.get("context", ""),
                parameters.get("currentLocation"),
                safe_json_load("party_tracker.json"),
            )
        elif family == "updateCharacterInfo":
            from core.managers.effects_runtime import prepare_character_update

            party = safe_json_load("party_tracker.json") or {}
            character_name = (
                parameters.get("characterName")
                or parameters.get("npcName")
                or next(iter(party.get("partyMembers", []) or []), None)
            )
            changes = parameters.get("changes")
            if isinstance(changes, dict):
                changes = json.dumps(changes)
            receipt = prepare_character_update(
                character_name, changes, party
            )
        elif family == "storageInteraction":
            from core.managers.storage_processor import process_storage_request
            from core.managers.storage_manager import StorageManager

            party = safe_json_load("party_tracker.json") or {}
            character_name = parameters.get("characterName") or next(
                iter(party.get("partyMembers", []) or []), None
            )
            if not character_name:
                raise ValueError("storageInteraction requires a character")
            description = parameters.get("description")
            if not isinstance(description, str) or not description.strip():
                raise ValueError("storageInteraction requires a description")
            proposal = process_storage_request(
                description,
                character_name,
                structural_reissue=True,
            )
            if not proposal.get("success"):
                raise RuntimeError("required storage proposal was not accepted")
            receipt = StorageManager(
                ensure_storage=False
            ).prepare_staged_operation(
                proposal["operation"], record["operation_id"]
            )
            receipt["message_id"] = str(uuid4())
        elif family == "updatePartyNPCs":
            receipt = prepare_party_npc_update(
                parameters, record["operation_id"]
            )
        else:
            source_module = str(checkpoint.get("module_name") or "")
            target_module = str(parameters.get("module") or "")
            if not target_module or target_module == source_module:
                raise ValueError("post-local module handoff requires another module")
            location_id, location_name, area_id, area_name = (
                get_module_starting_location(target_module)
            )
            supplied_area = str(parameters.get("currentAreaId") or "").strip()
            supplied_location = str(
                parameters.get("currentLocationId") or ""
            ).strip()
            if supplied_area and supplied_area != str(area_id):
                raise ValueError("module handoff area ID is not canonical")
            if supplied_location and supplied_location != str(location_id):
                raise ValueError("module handoff location ID is not canonical")
            exact_parameters = copy.deepcopy(parameters)
            exact_parameters.update(
                {
                    "module": target_module,
                    "currentAreaId": str(area_id),
                    "currentArea": str(area_name),
                    "currentLocationId": str(location_id),
                    "currentLocation": str(location_name),
                }
            )
            receipt = {
                "kind": "updatePartyTracker",
                "operation_id": record["operation_id"],
                "completion_id": record["operation_id"],
                "status": "staged",
                "parameters": exact_parameters,
                "source_projection": {
                    "module": source_module,
                    "currentAreaId": checkpoint.get("destination_area_id"),
                    "currentArea": checkpoint.get("destination_area_name"),
                    "currentLocationId": checkpoint.get(
                        "destination_location_id"
                    ),
                    "currentLocation": checkpoint.get(
                        "destination_location_name"
                    ),
                },
                "target_projection": {
                    "module": target_module,
                    "currentAreaId": str(area_id),
                    "currentArea": str(area_name),
                    "currentLocationId": str(location_id),
                    "currentLocation": str(location_name),
                },
            }
        receipt.update(
            {
                "operation_id": record["operation_id"],
                "status": "staged",
            }
        )
        checkpoint = load_current_transition_checkpoint(operation_id)
        checkpoint["deferred_actions"]["actions"][index]["receipt"] = receipt
        if family == "updatePartyTracker":
            checkpoint["module_handoff"] = {
                "status": "pending",
                "action_index": index,
                "completion_id": receipt["completion_id"],
                "source_projection": copy.deepcopy(receipt["source_projection"]),
                "target_projection": copy.deepcopy(receipt["target_projection"]),
            }
            checkpoint["narration"]["status"] = "deferred_to_module_handoff"
            checkpoint["phase"] = "narration_deferred"
        _write_location_transition_checkpoint(checkpoint)
    return load_current_transition_checkpoint(operation_id)


def update_current_transition_checkpoint(operation_id, **changes):
    checkpoint = load_current_transition_checkpoint(operation_id)
    if checkpoint is None:
        return None
    checkpoint.update(changes)
    _write_location_transition_checkpoint(checkpoint)
    return checkpoint


def resolve_current_transition_reconciliation(operation_id, transition_context):
    """Resolve advisory T091 and durably receipt its exact owned values."""
    checkpoint = load_current_transition_checkpoint(operation_id)
    if checkpoint is None:
        raise RuntimeError("current transition checkpoint is unavailable")
    receipt = checkpoint["location_reconciliation"]
    if receipt.get("status") in {"committed", "attempted_unavailable"}:
        return receipt["status"]

    from utils import reconcile_location_state
    from utils.capture.live_provider_call import LiveProviderUnavailable

    try:
        proposal = reconcile_location_state.prepare_reconciliation(
            checkpoint["origin_area_id"],
            checkpoint["origin_location_id"],
            transition_context["origin_history_segment"],
        )
    except LiveProviderUnavailable:
        receipt["status"] = "attempted_unavailable"
        _write_location_transition_checkpoint(checkpoint)
        return receipt["status"]
    receipt.update(
        {
            "status": "pending",
            "area_path": proposal["area_path"],
            "location_id": proposal["location_id"],
            "monsters_before": proposal["monsters_before"],
            "monsters_after": proposal["monsters_after"],
        }
    )
    _write_location_transition_checkpoint(checkpoint)
    outcome = reconcile_location_state.apply_reconciliation(receipt)
    receipt["status"] = (
        "committed" if outcome in {"committed", "already_committed"}
        else "blocked_conflict"
    )
    checkpoint["phase"] = (
        "reconciliation_resolved"
        if receipt["status"] == "committed"
        else "blocked_conflict"
    )
    _write_location_transition_checkpoint(checkpoint)
    return receipt["status"]


def resolve_current_transition_departure(operation_id, transition_context):
    """Run required T016/T015 outside locks, then commit once on game thread."""
    checkpoint = load_current_transition_checkpoint(operation_id)
    if checkpoint is None:
        raise RuntimeError("current transition checkpoint is unavailable")
    summary_record = checkpoint["departure_summary"]
    commit_record = checkpoint["departure_commit"]
    if commit_record.get("status") == "committed":
        return summary_record.get("text")

    from core.ai import adv_summary

    if summary_record.get("status") != "accepted":
        action_projection = [
            {
                "action": "transitionLocation",
                "parameters": {
                    "newLocation": checkpoint["destination_location_id"]
                },
                "workflow_status": "committed",
            }
        ]
        for action_record in checkpoint["deferred_actions"].get("actions", []):
            projected_action = copy.deepcopy(action_record.get("action"))
            if not isinstance(projected_action, dict):
                continue
            projected_action["workflow_status"] = str(
                action_record.get("status") or "pending"
            )
            action_projection.append(projected_action)
        proposal = adv_summary.prepare_departure_summary(
            transition_context["origin_history_segment"],
            transition_context["origin_party_tracker"],
            transition_context["origin_location_info"]["name"],
            checkpoint["origin_area_id"],
            checkpoint["origin_location_id"],
            structured_actions=action_projection,
        )
        area_before = proposal["area_before"]
        location_index = next(
            index
            for index, location in enumerate(area_before["locations"])
            if location.get("locationId") == checkpoint["origin_location_id"]
        )
        summary_record.update(
            {
                "status": "accepted",
                "text": proposal["summary"],
                "provider_response_id": None,
            }
        )
        staged_journal_entry = copy.deepcopy(
            commit_record["journal_entry_after"]
        )
        staged_journal_entry["summary"] = proposal["summary"]
        commit_record.update(
            {
                "status": "staged",
                "area_path": proposal["area_path"],
                "area_owned_before": copy.deepcopy(
                    proposal["area_before"]["locations"][location_index]
                ),
                "area_owned_after": copy.deepcopy(
                    proposal["area_after"]["locations"][location_index]
                ),
                "journal_entry_after": staged_journal_entry,
            }
        )
        checkpoint["phase"] = "departure_pending"
        _write_location_transition_checkpoint(checkpoint)

    area_data = safe_json_load(commit_record["area_path"])
    journal_exists = os.path.exists("journal.json")
    journal_data = safe_json_load("journal.json")
    if not journal_exists and journal_data is None:
        journal_data = {"entries": []}
    if not isinstance(area_data, dict) or not isinstance(
        area_data.get("locations"), list
    ):
        raise RuntimeError("departure area is unavailable during commit")
    elif not isinstance(journal_data, dict) or not isinstance(
        journal_data.get("entries"), list
    ):
        raise RuntimeError("journal is unavailable during departure commit")
    target = next(
        (
            location
            for location in area_data["locations"]
            if location.get("locationId") == checkpoint["origin_location_id"]
        ),
        None,
    )
    if target == commit_record["area_owned_after"]:
        journal_index = commit_record["journal_entry_index"]
        if (
            journal_index < len(journal_data["entries"])
            and journal_data["entries"][journal_index]
            == commit_record["journal_entry_after"]
        ):
            commit_record["status"] = "committed"
            checkpoint["phase"] = "departure_committed"
            _write_location_transition_checkpoint(checkpoint)
            return summary_record["text"]
    if target != commit_record["area_owned_before"]:
        commit_record["status"] = "blocked_conflict"
        checkpoint["phase"] = "blocked_conflict"
        _write_location_transition_checkpoint(checkpoint)
        raise RuntimeError("departure area changed outside the staged operation")
    if len(journal_data["entries"]) != commit_record["journal_entry_index"]:
        commit_record["status"] = "blocked_conflict"
        checkpoint["phase"] = "blocked_conflict"
        _write_location_transition_checkpoint(checkpoint)
        raise RuntimeError("departure journal changed outside the staged operation")

    area_after = copy.deepcopy(area_data)
    for index, location in enumerate(area_after["locations"]):
        if location.get("locationId") == checkpoint["origin_location_id"]:
            area_after["locations"][index] = copy.deepcopy(
                commit_record["area_owned_after"]
            )
            break
    journal_after = copy.deepcopy(journal_data)
    journal_after["entries"].append(
        copy.deepcopy(commit_record["journal_entry_after"])
    )
    adv_summary.commit_departure_summary(
        commit_record["area_path"],
        area_data,
        area_after,
        journal_after,
    )
    commit_record["status"] = "committed"
    checkpoint["phase"] = "departure_committed"
    _write_location_transition_checkpoint(checkpoint)
    return summary_record["text"]


def _remove_location_transition_checkpoint():
    try:
        os.remove(PENDING_LOCATION_TRANSITION_FILE)
    except FileNotFoundError:
        return


def complete_location_transition_checkpoint(transition_id):
    """Remove only the checkpoint correlated with durable final narration."""
    if not transition_id:
        return False
    checkpoint = safe_json_load(PENDING_LOCATION_TRANSITION_FILE)
    if not isinstance(checkpoint, dict):
        return False
    checkpoint_identity = checkpoint.get("operation_id") or checkpoint.get("transition_id")
    if checkpoint_identity != transition_id:
        return False
    checkpoint["phase"] = "completed"
    _write_location_transition_checkpoint(checkpoint)
    _remove_location_transition_checkpoint()
    return True


def mark_location_transition_deferred_pending(transition_id, deferred_actions):
    """Record that final narration is durable but ordered actions remain.

    Only an action count and hash are persisted. Generic actions are not
    universally idempotent, so recovery must never replay them blindly.
    """
    if not transition_id:
        return False
    checkpoint = safe_json_load(PENDING_LOCATION_TRANSITION_FILE)
    if not isinstance(checkpoint, dict):
        return False
    checkpoint_identity = checkpoint.get("operation_id") or checkpoint.get("transition_id")
    if checkpoint_identity != transition_id:
        return False
    if checkpoint.get("version") == 2:
        deferred = checkpoint.get("deferred_actions")
        if not isinstance(deferred, dict):
            return False
        staged_actions = deferred.get("actions")
        if not isinstance(staged_actions, list):
            return False
        if [item.get("action") for item in staged_actions] != list(deferred_actions or []):
            return False
        checkpoint["phase"] = "deferred_actions_pending"
        deferred["status"] = "pending" if staged_actions else "committed"
        _write_location_transition_checkpoint(checkpoint)
        return True
    checkpoint["phase"] = "deferred_actions_pending"
    checkpoint["deferred_action_count"] = len(deferred_actions or [])
    checkpoint["deferred_actions_identity"] = _stable_transition_hash(
        deferred_actions or []
    )
    _write_location_transition_checkpoint(checkpoint)
    return True


def _publish_stable_transition_message(message_id, content, *, role="system"):
    """Append one checkpoint-owned message to canonical history exactly once."""
    history_path = "modules/conversation_history/conversation_history.json"
    history = safe_json_load(history_path)
    if not isinstance(history, list):
        raise RuntimeError("conversation history is unavailable")
    if any(
        isinstance(item, dict) and item.get("message_id") == message_id
        for item in history
    ):
        return "already_published"
    history.append(
        {"role": role, "content": content, "message_id": message_id}
    )
    safe_json_dump(history, history_path)
    return "published"


def _current_save_listing():
    from updates.save_game_manager import SaveGameManager

    saves = SaveGameManager().list_save_games()
    if not saves:
        return "No save games found."
    lines = ["Available save games:"]
    for index, save in enumerate(saves, 1):
        lines.extend(
            [
                "%s. %s" % (index, save.get("save_folder", "Unknown")),
                "   Date: %s" % save.get("save_date_readable", "Unknown date"),
                "   Module: %s" % save.get("module", "Unknown"),
                "   Mode: %s" % save.get("save_mode", "unknown"),
                "   Description: %s" % save.get("description", "No description"),
                "",
            ]
        )
    return "\n".join(lines)


def apply_current_transition_action(operation_id, action_index):
    """Apply one staged v2 sibling through its reviewed family receipt."""
    checkpoint = load_current_transition_checkpoint(operation_id)
    if checkpoint is None:
        raise RuntimeError("current transition checkpoint is unavailable")
    deferred = checkpoint.get("deferred_actions")
    records = deferred.get("actions") if isinstance(deferred, dict) else None
    if not isinstance(records, list) or action_index >= len(records):
        raise RuntimeError("staged deferred action is unavailable")
    record = records[action_index]
    if record.get("index") != action_index:
        raise RuntimeError("staged deferred action order is invalid")
    if record.get("status") == "committed":
        deferred["cursor"] = max(int(deferred.get("cursor", 0)), action_index + 1)
        return "committed"
    family = record.get("family")
    receipt = record.get("receipt")
    if not isinstance(receipt, dict):
        raise RuntimeError(
            "deferred action family %s has no approved v2 receipt" % family
        )

    from core.managers.campaign_manager import _party_module_transition_lock
    from updates.update_world_time import apply_staged_world_time

    if family == "updatePlot":
        from updates.plot_update import apply_staged_plot_update
        from utils.quest_player_formatter import (
            apply_staged_player_quests,
            prepare_player_quests,
            refresh_staged_player_quest_source,
        )

        if receipt.get("status") != "plot_committed":
            with _party_module_transition_lock():
                outcome = apply_staged_plot_update(receipt)
                if outcome == "blocked_conflict":
                    record["status"] = "blocked_conflict"
                    checkpoint["phase"] = "blocked_conflict"
                    _write_location_transition_checkpoint(checkpoint)
                    return outcome
                receipt["status"] = "plot_committed"
                _write_location_transition_checkpoint(checkpoint)

        checkpoint = load_current_transition_checkpoint(operation_id)
        record = checkpoint["deferred_actions"]["actions"][action_index]
        receipt = record["receipt"]
        quest_receipt = receipt.get("quest_projection")
        if quest_receipt == {"status": "pending"}:
            quest_receipt = prepare_player_quests(receipt["module"])
            checkpoint = load_current_transition_checkpoint(operation_id)
            record = checkpoint["deferred_actions"]["actions"][action_index]
            record["receipt"]["quest_projection"] = quest_receipt
            _write_location_transition_checkpoint(checkpoint)

        checkpoint = load_current_transition_checkpoint(operation_id)
        record = checkpoint["deferred_actions"]["actions"][action_index]
        receipt = record["receipt"]
        if receipt["quest_projection"].get("status") == "staged":
            source_outcome = refresh_staged_player_quest_source(
                receipt["quest_projection"]
            )
            if source_outcome == "blocked_conflict":
                record["status"] = "blocked_conflict"
                checkpoint["phase"] = "blocked_conflict"
                _write_location_transition_checkpoint(checkpoint)
                return source_outcome
            _write_location_transition_checkpoint(checkpoint)
        outcome = apply_staged_player_quests(receipt["quest_projection"])
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        record["receipt"]["quest_projection"]["status"] = (
            "attempted_unavailable"
            if outcome == "attempted_unavailable"
            else "committed"
        )
        record["status"] = "committed"
        deferred = checkpoint["deferred_actions"]
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(deferred["actions"]):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "removeEffect":
        from core.managers.effects_runtime import apply_staged_remove_effect

        outcome = apply_staged_remove_effect(receipt)
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "establishHub":
        from core.managers.campaign_manager import apply_staged_hub_establishment

        outcome = apply_staged_hub_establishment(receipt)
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        note = receipt["note"]
        _publish_stable_transition_message(
            note["message_id"], note["content"], role="user"
        )
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "listSaves":
        _publish_stable_transition_message(
            receipt["message_id"], _current_save_listing()
        )
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "moveBackgroundNPC":
        if receipt.get("before") is None:
            materialize_staged_background_npc_movement(receipt)
            _write_location_transition_checkpoint(checkpoint)
        outcome = apply_staged_background_npc_movement(receipt)
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "saveGame":
        from updates.save_game_manager import SaveGameManager

        success, message = SaveGameManager().create_save_game(
            receipt["description"],
            receipt["save_mode"],
            save_folder=receipt["save_folder"],
        )
        if not success:
            raise RuntimeError("staged save could not complete: %s" % message)
        _publish_stable_transition_message(
            receipt["message_id"], "Game saved successfully! %s" % message
        )
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
                "save_folder": receipt["save_folder"],
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "deleteSave":
        from updates.save_game_manager import SaveGameManager

        outcome = SaveGameManager().apply_staged_delete(receipt)
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        _publish_stable_transition_message(
            receipt["message_id"],
            "Save game deleted: %s" % receipt["save_folder"],
        )
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "exitGame":
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "updateCharacterInfo":
        from core.managers.effects_runtime import apply_staged_character_update

        outcome = apply_staged_character_update(receipt)
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "storageInteraction":
        from core.managers.storage_manager import StorageManager

        outcome = StorageManager.apply_staged_operation(receipt)
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        _publish_stable_transition_message(
            receipt["message_id"], "Storage: %s" % receipt["message"]
        )
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "updatePartyNPCs":
        party = safe_json_load("party_tracker.json")
        if not isinstance(party, dict) or not isinstance(
            party.get("partyNPCs"), list
        ):
            raise RuntimeError("party roster is unavailable")
        if party["partyNPCs"] == receipt["roster_before"]:
            with _party_module_transition_lock():
                latest = safe_json_load("party_tracker.json")
                if latest.get("partyNPCs") != receipt["roster_before"]:
                    outcome = "blocked_conflict"
                else:
                    latest["partyNPCs"] = copy.deepcopy(receipt["roster_after"])
                    safe_json_dump(latest, "party_tracker.json")
                    outcome = "committed"
        elif party["partyNPCs"] == receipt["roster_after"]:
            outcome = "committed"
        else:
            outcome = "blocked_conflict"
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        receipt["phase"] = "roster_committed"
        _write_location_transition_checkpoint(checkpoint)
        lifecycle_ok = _apply_party_npc_lifecycle(
            safe_json_load("party_tracker.json") or party,
            receipt["operation"],
            receipt["npc_name"],
            receipt["npc_path"],
            receipt.get("lifecycle_context"),
            receipt["operation_id"],
        )
        receipt["lifecycle_status"] = (
            "committed" if lifecycle_ok else "attempted_unavailable"
        )
        receipt["phase"] = "lifecycle_resolved"
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
                "lifecycle": receipt["lifecycle_status"],
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family == "updatePartyTracker":
        from core.managers.campaign_manager import CampaignManager
        from main import retry_staged_module_completions, save_conversation_history

        def projection(value):
            world = value.get("worldConditions") if isinstance(value, dict) else None
            world = world if isinstance(world, dict) else {}
            return {
                "module": value.get("module") if isinstance(value, dict) else None,
                "currentAreaId": world.get("currentAreaId"),
                "currentArea": world.get("currentArea"),
                "currentLocationId": world.get("currentLocationId"),
                "currentLocation": world.get("currentLocation"),
            }

        party = safe_json_load("party_tracker.json") or {}
        current = projection(party)
        completion_party = copy.deepcopy(party)
        source = receipt["source_projection"]
        target = receipt["target_projection"]
        history = safe_json_load(
            "modules/conversation_history/conversation_history.json"
        ) or []
        marker = {
            "role": "user",
            "content": "Module transition: %s to %s"
            % (source["module"], target["module"]),
        }
        if current == source:
            transition_history = list(history)
            if not transition_history or transition_history[-1] != marker:
                transition_history.append(marker)
            original, updated = CampaignManager().publish_party_module_transition(
                source["module"],
                target["module"],
                receipt["parameters"],
                transition_history,
                receipt["completion_id"],
            )
            save_conversation_history(
                transition_history, strict=True, allow_compression=False
            )
            party = updated
            completion_party = original
            current = projection(party)
        elif current != target:
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return "blocked_conflict"
        pending = {
            "from_module": source["module"],
            "to_module": target["module"],
            "party_tracker_data": completion_party,
            "completion_id": receipt["completion_id"],
        }
        targeted, completion = retry_staged_module_completions(
            pending, safe_json_load(
                "modules/conversation_history/conversation_history.json"
            ) or []
        )
        if completion["failed"] or completion["blocked"]:
            raise RuntimeError("module handoff completion remains pending")
        if targeted is None and receipt["completion_id"] not in completion["completed"]:
            raise RuntimeError("module handoff completion receipt is absent")
        receipt["status"] = "authority_transferred"
        checkpoint["module_handoff"]["status"] = "authority_transferred"
        checkpoint["phase"] = "module_authority_transferred"
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
                "completion_id": receipt["completion_id"],
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"

    if family != "updateTime":
        raise RuntimeError(
            "deferred action family %s has no approved v2 receipt" % family
        )

    with _party_module_transition_lock():
        outcome = apply_staged_world_time(receipt["before"], receipt["after"])
        if outcome == "blocked_conflict":
            record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            return outcome
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
    return "committed"


def recover_pending_location_transition(party_tracker_data, conversation_history):
    """Finish or cancel an interrupted within-module transition exactly once.

    Movement itself is authoritative in party_tracker.json.  A planned record
    with the party still at its origin made no movement and is discarded for a
    fresh re-plan.  If the party reached the destination, missing history is
    completed with deterministic prose; recovery never calls a provider.
    """
    checkpoint = safe_json_load(PENDING_LOCATION_TRANSITION_FILE)
    if not isinstance(checkpoint, dict):
        return {"status": "none"}

    if checkpoint.get("version") == 2:
        if checkpoint.get("kind") != "current_transition":
            return {
                "status": "resume_required",
                "kind": checkpoint.get("kind"),
            }
        if checkpoint.get("movement_kind") == "cross_module_root":
            handoff = checkpoint.get("module_handoff")
            party_projection = {
                "module": party_tracker_data.get("module"),
                **{
                    key: (party_tracker_data.get("worldConditions") or {}).get(key)
                    for key in (
                        "currentAreaId",
                        "currentArea",
                        "currentLocationId",
                        "currentLocation",
                    )
                },
            }
            if isinstance(handoff, dict) and party_projection in (
                handoff.get("source_projection"),
                handoff.get("target_projection"),
            ):
                return {
                    "status": "resume_required",
                    "operation_id": checkpoint.get("operation_id"),
                    "phase": checkpoint.get("phase"),
                }
            # [travel #210] The staged cross-module transition is un-appliable:
            # authoritative party state matches neither the source nor target
            # projection. Retire the residue here (the lifecycle owner) so it
            # cannot re-block every subsequent boot (#167), and fail forward.
            warning(
                "Discarding un-appliable interrupted transition "
                "(cross-module op=%s phase=%s): authoritative party state "
                "matches neither staged module projection."
                % (checkpoint.get("operation_id"), checkpoint.get("phase")),
                category="location_transitions",
            )
            _remove_location_transition_checkpoint()
            return {
                "status": "blocked",
                "discarded": True,
                "reason": "party state matches neither staged module projection",
            }
        handoff = checkpoint.get("module_handoff")
        if isinstance(handoff, dict):
            world = party_tracker_data.get("worldConditions") or {}
            party_projection = {
                "module": party_tracker_data.get("module"),
                "currentAreaId": world.get("currentAreaId"),
                "currentArea": world.get("currentArea"),
                "currentLocationId": world.get("currentLocationId"),
                "currentLocation": world.get("currentLocation"),
            }
            if party_projection == handoff.get("target_projection"):
                return {
                    "status": "resume_required",
                    "operation_id": checkpoint.get("operation_id"),
                    "phase": checkpoint.get("phase"),
                }
        current_id = str(
            party_tracker_data.get("worldConditions", {}).get(
                "currentLocationId", ""
            )
        )
        origin_id = str(checkpoint.get("origin_location_id", ""))
        destination_id = str(checkpoint.get("destination_location_id", ""))
        phase = checkpoint.get("phase")
        if phase == "completed":
            _remove_location_transition_checkpoint()
            return {"status": "completed"}
        if phase == "planned" and current_id == origin_id:
            _remove_location_transition_checkpoint()
            return {"status": "replan_required"}
        if current_id != destination_id:
            # [travel #210] Un-appliable: party is at neither origin nor the
            # staged destination, so the transition can never be resumed
            # (resume requires party-at-destination). Retire it and fail
            # forward instead of leaving residue that re-blocks every boot.
            warning(
                "Discarding un-appliable interrupted transition "
                "(v2 origin=%s dest=%s current=%s): party location matches "
                "neither." % (origin_id, destination_id, current_id),
                category="location_transitions",
            )
            _remove_location_transition_checkpoint()
            return {
                "status": "blocked",
                "discarded": True,
                "reason": (
                    "party location does not match the v2 transition's "
                    "staged destination"
                ),
            }
        final_context = checkpoint.get("final_context")
        deferred = checkpoint.get("deferred_actions")
        narration = checkpoint.get("narration")
        if (
            isinstance(final_context, dict)
            and final_context.get("status") == "committed"
            and isinstance(deferred, dict)
            and deferred.get("status") == "committed"
            and isinstance(narration, dict)
            and narration.get("status") == "published"
        ):
            _remove_location_transition_checkpoint()
            return {
                "status": "completed",
                "operation_id": checkpoint.get("operation_id"),
            }
        # V2 never falls into the v1 deterministic-close path: doing so would
        # discard accepted summary/enrichment/sibling work. The live workflow
        # resumes this exact record under provider supervision.
        return {
            "status": "resume_required",
            "operation_id": checkpoint.get("operation_id"),
            "phase": phase,
        }

    origin_id = str(checkpoint.get("origin_location_id", ""))
    destination_id = str(checkpoint.get("destination_location_id", ""))
    phase = checkpoint.get("phase")
    current_id = str(
        party_tracker_data.get("worldConditions", {}).get(
            "currentLocationId", ""
        )
    )
    if phase == "completed":
        _remove_location_transition_checkpoint()
        return {"status": "completed"}
    if current_id == origin_id and phase == "planned":
        _remove_location_transition_checkpoint()
        return {"status": "replan_required"}
    if current_id != destination_id:
        # [travel #210] Un-appliable v1 residue: party at neither origin nor
        # destination. Retire it and fail forward (see the v2 sites above).
        warning(
            "Discarding un-appliable interrupted transition "
            "(v1 origin=%s dest=%s current=%s): party location matches "
            "neither." % (origin_id, destination_id, current_id),
            category="location_transitions",
        )
        _remove_location_transition_checkpoint()
        return {
            "status": "blocked",
            "discarded": True,
            "reason": "party location does not match pending transition",
        }

    origin_name = checkpoint.get("origin_location_name") or origin_id
    destination_name = checkpoint.get("destination_location_name") or destination_id
    marker = (
        f"Location transition: {sanitize_text(origin_name)} ({origin_id}) "
        f"to {sanitize_text(destination_name)} ({destination_id})"
    )
    history_boundary = checkpoint.get("history_boundary", 0)
    if not isinstance(history_boundary, int) or history_boundary < 0:
        history_boundary = 0
    history_boundary = min(history_boundary, len(conversation_history))
    marker_index = next(
        (
            index
            for index, message in enumerate(
                conversation_history[history_boundary:],
                start=history_boundary,
            )
            if isinstance(message, dict)
            and message.get("role") == "user"
            and message.get("content") == marker
        ),
        None,
    )
    if marker_index is None:
        conversation_history.append({"role": "user", "content": marker})
        marker_index = len(conversation_history) - 1

    # A saved assistant message after our exact marker proves T013 completed.
    # Otherwise deterministic prose closes the display/history gap without a
    # provider call that could fail again during startup.
    has_narration = any(
        isinstance(message, dict)
        and message.get("role") == "assistant"
        and isinstance(message.get("content"), str)
        and message.get("content").strip()
        for message in conversation_history[marker_index + 1 :]
    )
    if not has_narration:
        conversation_history.append(
            {
                "role": "assistant",
                "content": f"The party travels to {destination_name}.",
            }
        )

    from main import save_conversation_history

    save_conversation_history(
        conversation_history, strict=True, allow_compression=False
    )
    checkpoint["phase"] = "completed"
    _write_location_transition_checkpoint(checkpoint)
    _remove_location_transition_checkpoint()
    result = {
        "status": "recovered",
        "transition_id": checkpoint.get("transition_id"),
    }
    if phase == "deferred_actions_pending":
        result.update(
            {
                "deferred_actions_not_replayed": True,
                "deferred_action_count": checkpoint.get(
                    "deferred_action_count", 0
                ),
            }
        )
    return result


def _npc_movement_lock(module_name):
    """Return the shared transaction lock for one module's area files."""
    with _NPC_MOVEMENT_LOCKS_GUARD:
        return _NPC_MOVEMENT_LOCKS.setdefault(module_name, threading.RLock())

# Module conversation segmentation has been moved to conversation_utils.py
# to work with the regular conversation update cycle

def _module_creation_error_result(*, recovery_required=False, message=None):
    """Return one sanitized, non-automatic-retry module failure shape."""
    if recovery_required:
        error_message = message or (
            "Module publication could not be confirmed. The party was not "
            "moved. Do not retry until recovery resolves the module state."
        )
        response_data = {
            "error_code": "module_publication_recovery_required",
            "error_message": error_message,
            "retryable": False,
            "state_changed": None,
            "recovery_required": True,
        }
    else:
        error_message = message or (
            "Module generation failed validation; no game state was changed. "
            "It is safe to retry."
        )
        response_data = {
            "error_code": "module_generation_not_published",
            "error_message": error_message,
            "retryable": True,
            "state_changed": False,
            "recovery_required": False,
        }
    return {
        "status": "error",
        "success": False,
        "needs_update": False,
        "needs_dm_response": False,
        "response_data": response_data,
    }


def pre_validate_transition(
    parameters,
    party_tracker_data,
    conversation_history,
    location_graph,
    path_manager,
    *,
    return_plan=False,
    invocation_claim=None,
):
    """
    Pre-validate a transitionLocation action using the transition intelligence agent.
    This runs BEFORE the main validator, similar to how validation runs before execution.

    Args:
        parameters: Action parameters dict with newLocation
        party_tracker_data: Current party tracker data
        conversation_history: Current conversation history
        location_graph: LocationGraph instance
        path_manager: ModulePathManager instance

    Returns:
        Tuple (approved: bool, error_message: str), or a private
        TransitionPrevalidationOutcome when ``return_plan=True``.
        - If approved: (True, "")
        - If blocked: (False, "Detailed error message with instructions")
    """
    from utils.path_encounter_analyzer import (
        analyze_path_for_encounters,
        build_active_module_snapshot,
        find_path_in_snapshot,
    )
    from core.ai.transition_validator import validate_transition_request
    from core.combat.invocation import InvocationSupersededError
    from utils.file_operations import safe_read_json

    def finish(
        approved,
        message,
        plan=None,
        *,
        reason_code=None,
        facts=None,
        intermediate_destination_id="",
        intermediate_destination_name="",
    ):
        if return_plan:
            return TransitionPrevalidationOutcome(
                approved=bool(approved),
                reason_code=reason_code or ("approved" if approved else "uncertain"),
                message=message or "",
                facts=dict(facts or {}),
                plan=plan,
                intermediate_destination_id=str(intermediate_destination_id or ""),
                intermediate_destination_name=str(intermediate_destination_name or ""),
            )
        return approved, message

    try:
        new_location_id = parameters.get("newLocation", "")
        if not new_location_id:
            return finish(
                False,
                "transitionLocation requires a canonical newLocation value.",
                reason_code="destination_absent",
            )

        world_conditions = party_tracker_data.get("worldConditions", {})
        if world_conditions.get("activeCombatEncounter"):
            return finish(
                False,
                "[TRAVEL SYSTEM] Travel is unavailable while combat is active. "
                "Resolve or explicitly end the active combat encounter before "
                "using transitionLocation.",
                reason_code="active_combat",
                facts={"active_combat": True},
            )

        # Get current location from party tracker
        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
        current_location_name = party_tracker_data["worldConditions"]["currentLocation"]
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
        current_area_name = party_tracker_data["worldConditions"]["currentArea"]

        current_module = party_tracker_data.get("module", "").replace(" ", "_")
        snapshot = build_active_module_snapshot(current_module)
        route = find_path_in_snapshot(
            snapshot, current_location_id, new_location_id
        )
        success = route.get("success") is True
        path = route.get("path", [])
        path_message = route.get("reason", "")

        if not success:
            nodes = snapshot.get("nodes", {})
            invalid_ids = set(snapshot.get("invalid_location_ids", []))
            if new_location_id not in nodes:
                reason_code = "destination_absent"
            elif new_location_id in invalid_ids:
                reason_code = "destination_invalid"
            else:
                reason_code = "no_valid_route"
            return finish(
                False,
                path_message or "No fully valid route exists.",
                reason_code=reason_code,
                facts={
                    "requested_destination_id": str(new_location_id),
                    "route_reason": path_message or "No fully valid route exists.",
                    "must_not_move": True,
                },
            )

        # Analyze path for encounters and blocking
        path_analysis = analyze_path_for_encounters(
            path,
            location_graph,
            current_module,
            snapshot=snapshot,
        )
        # T021 now consumes route-scoped evidence. Keep the compatibility
        # argument empty instead of building a second, potentially divergent
        # atlas from the legacy global graph.
        transition_atlas = ""

        # Load plot data
        plot_data = safe_read_json(path_manager.get_plot_path()) or {}

        # Get party level
        party_level = 1
        if party_tracker_data.get("partyMembers"):
            try:
                first_member = party_tracker_data["partyMembers"][0]
                from updates.update_character_info import normalize_character_name
                char_name = normalize_character_name(first_member)
                char_file = path_manager.get_character_path(char_name)
                if os.path.exists(char_file):
                    char_data = safe_read_json(char_file)
                    if char_data:
                        party_level = char_data.get("level", 1)
            except Exception:
                pass

        # Get player request from conversation history
        player_request = ""
        for msg in reversed(conversation_history):
            if msg.get("role") == "user" and not msg.get("content", "").startswith("Error Note:"):
                player_request = msg.get("content", "")
                break

        # Call transition intelligence agent
        print(f"DEBUG: [TRANSITION AGENT] Checking travel: {current_location_id} -> {new_location_id}")
        info(f"TRANSITION AGENT: Validating travel request {current_location_id} -> {new_location_id}", category="transition_validation")

        transition_result = validate_transition_request(
            player_request=player_request,
            current_location_id=current_location_id,
            current_location_name=current_location_name,
            current_area_id=current_area_id,
            current_area_name=current_area_name,
            target_location_id=new_location_id,
            path=path,
            path_analysis=path_analysis,
            transition_atlas=transition_atlas,
            plot_data=plot_data,
            party_level=party_level,
            invocation_claim=invocation_claim,
        )

        # Log agent decision
        agent_decision = "APPROVED" if transition_result.get("approved") is True else "BLOCKED"
        print(f"[TRANSITION AGENT] Decision: {agent_decision}")
        info(f"TRANSITION AGENT: {agent_decision} - {transition_result.get('reason', 'No reason')}", category="transition_validation")

        # Check if approved
        if transition_result.get("approved") is not True:
            if transition_result.get("approved") is not False:
                return finish(
                    False,
                    "[TRAVEL SYSTEM] The route review returned an uncertain "
                    "or invalid decision. Do not move the party; regenerate "
                    "the response and plan the route again.",
                    reason_code="uncertain",
                    facts={"must_not_move": True},
                )
            # Build error message with explicit instructions
            stop_location = transition_result.get("stop_location", "")
            stop_location_name = transition_result.get("stop_location_name", "Unknown")
            reason = transition_result.get("reason", "Unknown")
            narrative_guidance = transition_result.get("narrative_guidance", "")
            requires_encounter = transition_result.get("requires_encounter", False)

            # Check if stop location is the current location
            if stop_location == current_location_id:
                # Already at the blocking location - don't use transitionLocation
                error_msg = f"[TRAVEL AGENT] Travel Blocked: {reason}\n\n"
                error_msg += f"REQUIRED ACTION: You must revise your response to:\n"
                error_msg += f"1. The party is already at {stop_location} ({stop_location_name})\n"
                error_msg += f"2. DO NOT use transitionLocation (already at this location)\n"
                error_msg += f"3. Narrate that the path forward/backward is blocked by the encounter\n"
                error_msg += f"4. Describe the blocking encounter appearing, set scene, prompt player for action\n"
                error_msg += f"5. Player must resolve this encounter before they can continue traveling\n"
            else:
                # Need to stop at a different location
                error_msg = f"[TRAVEL AGENT] Travel Blocked: {reason}\n\n"
                error_msg += f"REQUIRED ACTION: You must revise your response to:\n"
                error_msg += f"1. Stop the party at {stop_location} ({stop_location_name})\n"
                error_msg += f"2. Use transitionLocation action with newLocation: \"{stop_location}\"\n"
                error_msg += f"3. DO NOT use createEncounter action - let the player arrive and explore first\n"
                error_msg += f"4. Describe the arrival at this location, set the scene, and prompt player for action\n"

            if requires_encounter:
                error_msg += f"\nNOTE: This location has a potential encounter, but wait for player interaction before triggering it.\n"

            error_msg += f"\nNARRATIVE GUIDANCE:\n{narrative_guidance}"

            if transition_result.get("plot_guidance"):
                error_msg += f"\n\nPLOT GUIDANCE: {transition_result['plot_guidance']}"

            return finish(
                False,
                error_msg,
                reason_code="intermediate_stop",
                facts={
                    "original_destination_id": str(new_location_id),
                    "stop_location_id": str(stop_location or ""),
                    "stop_location_name": str(stop_location_name or ""),
                    "reason": str(reason or ""),
                    "narrative_guidance": str(narrative_guidance or ""),
                    "requires_encounter": bool(requires_encounter),
                    "plot_guidance": transition_result.get("plot_guidance"),
                },
                intermediate_destination_id=stop_location,
                intermediate_destination_name=stop_location_name,
            )

        plan = _approved_transition_plan(
            origin_location_id=current_location_id,
            destination_location_id=new_location_id,
            module_name=current_module,
            path=path,
            path_analysis=path_analysis,
            plot_data=plot_data,
            location_graph=location_graph,
            topology_identity=snapshot.get("topology_identity")
            or snapshot.get("snapshot_hash"),
        )
        return finish(
            True,
            "",
            plan,
            reason_code="approved",
            facts={"destination_location_id": str(new_location_id)},
        )

    except InvocationSupersededError:
        raise
    except Exception as e:
        debug(f"Transition pre-validation error: {e}", category="location_transitions")
        return finish(
            False,
            "[TRAVEL SYSTEM] Travel planning could not be completed safely. "
            "Do not move the party; regenerate the response or ask the player "
            "to try the route again.",
            reason_code="planning_exception",
            facts={"must_not_move": True},
        )


def verify_approved_transition_plan(
    approved_plan,
    *,
    party_tracker_data,
    destination_location_id,
    location_graph,
    return_context=False,
):
    """Recheck one in-memory authorization against authoritative live inputs."""
    if not isinstance(approved_plan, ApprovedTransitionPlan):
        result = (False, "Transition has no approved in-memory travel plan")
        return (*result, None) if return_context else result

    world_conditions = party_tracker_data.get("worldConditions", {})
    if world_conditions.get("activeCombatEncounter"):
        result = (False, "Travel is unavailable while combat is active")
        return (*result, None) if return_context else result

    current_location_id = str(world_conditions.get("currentLocationId", ""))
    current_module = str(party_tracker_data.get("module", "")).replace(" ", "_")
    destination_location_id = str(destination_location_id)
    if current_location_id != approved_plan.origin_location_id:
        result = (False, "Travel plan origin is stale")
        return (*result, None) if return_context else result
    if destination_location_id != approved_plan.destination_location_id:
        result = (False, "Travel plan destination does not match the action")
        return (*result, None) if return_context else result
    if current_module != approved_plan.module_name:
        result = (False, "Travel plan module is stale")
        return (*result, None) if return_context else result

    from utils.path_encounter_analyzer import (
        analyze_path_for_encounters,
        build_active_module_snapshot,
        find_path_in_snapshot,
    )

    snapshot = build_active_module_snapshot(current_module)
    route = find_path_in_snapshot(
        snapshot, current_location_id, destination_location_id
    )
    success = route.get("success") is True
    path = route.get("path", [])
    path_message = route.get("reason", "")
    if not success:
        result = (False, path_message or "The approved route no longer exists")
        return (*result, None) if return_context else result
    if tuple(str(item) for item in path) != approved_plan.path:
        result = (False, "The approved route changed before movement")
        return (*result, None) if return_context else result

    path_analysis = analyze_path_for_encounters(
        path, location_graph, current_module, snapshot=snapshot
    )
    plot_data = safe_read_json(
        ModulePathManager(current_module).get_plot_path()
    ) or {}
    topology_identity = str(
        snapshot.get("topology_identity") or snapshot.get("snapshot_hash") or ""
    )
    evidence_identity = _transition_evidence_identity(path_analysis, plot_data)
    if topology_identity != approved_plan.topology_identity:
        result = (False, "Atlas topology changed before movement")
        return (*result, None) if return_context else result
    if evidence_identity != approved_plan.evidence_identity:
        result = (False, "Travel evidence changed before movement")
        return (*result, None) if return_context else result
    result = (True, "")
    if not return_context:
        return result
    return (
        *result,
        {
            "snapshot_hash": snapshot.get("snapshot_hash", ""),
            "topology_identity": topology_identity,
            "origin": snapshot.get("nodes", {}).get(current_location_id),
            "destination": snapshot.get("nodes", {}).get(destination_location_id),
        },
    )


def validate_location_transition(location_graph, current_location_id, destination_location_id):
    """
    Validate that a location transition is possible using the location graph.
    
    Args:
        location_graph (LocationGraph): Initialized location graph
        current_location_id (str): Current location ID (e.g., "E02")
        destination_location_id (str): Destination location ID (e.g., "B01")
    
    Returns:
        tuple: (bool, str, str) - (is_valid, error_message, area_connectivity_id)
    """
    try:
        # Validate destination location exists
        if not location_graph.validate_location_id_format(destination_location_id):
            return False, f"Destination location '{destination_location_id}' does not exist in module", None
        
        # Use pathfinding to validate that a connected path exists
        success, path, path_message = location_graph.find_path(current_location_id, destination_location_id)
        if not success:
            return False, f"No valid path exists between '{current_location_id}' and '{destination_location_id}': {path_message}", None
        
        # Check if this is a cross-area transition
        is_cross_area = location_graph.is_cross_area_transition(current_location_id, destination_location_id)
        if is_cross_area is None:
            return False, f"Invalid location ID format: current='{current_location_id}', destination='{destination_location_id}'", None
        
        # Generate area connectivity ID if needed (for backward compatibility with location_manager)
        area_connectivity_id = None
        if is_cross_area:
            dest_area_id = location_graph.get_area_id_from_location_id(destination_location_id)
            area_connectivity_id = f"{dest_area_id}-{destination_location_id}"
        
        debug("VALIDATION: Location transition validation passed", category="location_transitions")
        debug(f"VALIDATION: Path found: {' -> '.join(path) if path else 'Direct connection'}", category="location_transitions")
        debug(f"VALIDATION: Cross-area transition: {is_cross_area}", category="location_transitions")
        if area_connectivity_id:
            debug(f"VALIDATION: Generated area connectivity ID: {area_connectivity_id}", category="location_transitions")
        
        return True, "", area_connectivity_id
        
    except Exception as e:
        return False, f"Location validation failed with exception: {str(e)}", None

def update_party_npcs(party_tracker_data, operation, npc):
    """Update NPC party members (add or remove)"""
    if operation == "add":
        # Get the correct module from party tracker
        module_name = party_tracker_data.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(module_name)
        
        # Use fuzzy matching to find the NPC file
        from updates.update_character_info import find_character_file_fuzzy
        matched_name = find_character_file_fuzzy(npc['name'])
        
        if matched_name:
            npc_file = path_manager.get_character_path(matched_name)
        else:
            # If no match found, use the original name for potential creation
            npc_file = path_manager.get_character_path(npc['name'])
        
        if not os.path.exists(npc_file):
            # NPC file doesn't exist, so we need to create it
            try:
                # Get party level as default if no level specified
                default_level = ''
                if not npc.get('level'):
                    # Get the first party member's level as default
                    if party_tracker_data.get("partyMembers"):
                        player_name = party_tracker_data["partyMembers"][0]
                        # Normalize name for file access
                        from updates.update_character_info import normalize_character_name
                        player_name_normalized = normalize_character_name(player_name)
                        player_file = path_manager.get_character_path(player_name_normalized)
                        if os.path.exists(player_file):
                            try:
                                from utils.encoding_utils import safe_json_load
                                player_data = safe_json_load(player_file)
                                if player_data and 'level' in player_data:
                                    default_level = str(player_data['level'])
                                    debug(f"STATE_CHANGE: Using party level {default_level} as default for NPC {npc['name']}", category="character_updates")
                            except Exception as e:
                                warning(f"FAILURE: Could not get party level, using default: {e}", category="character_updates")
                
                npc_level = str(npc.get('level', default_level))
                
                # Add this debug line right before the subprocess.run call
                debug(f"SUBPROCESS: Calling npc_builder.py with arguments: {npc['name']} {npc.get('race', '')} {npc.get('class', '')} {npc_level} {npc.get('background', '')}", category="character_updates")

                subprocess.run([
                    sys.executable, _generator_script_path("npc_builder.py"),
                    npc['name'],
                    npc.get('race', ''),
                    npc.get('class', ''),
                    npc_level,
                    npc.get('background', '')
                ], check=True, stdin=subprocess.DEVNULL)
                info(f"SUCCESS: NPC profile created for {npc['name']}", category="character_updates")
            except subprocess.CalledProcessError as e:
                error(f"FAILURE: Failed to create NPC profile for {npc['name']}: {e}", category="character_updates")
                return

        # Now we can add the NPC to the party
        # Create entry matching the party_schema.json requirements (name and role)
        npc_entry = {
            "name": npc.get('name'),
            "role": npc.get('role', npc.get('class', 'Companion'))  # Use role if provided, else class, else default
        }
        
        # Load the actual NPC data to get the correct display name
        from utils.encoding_utils import safe_json_load
        from updates.update_character_info import normalize_character_name, find_character_file_fuzzy
        
        # Use fuzzy matching to find the correct NPC file
        matched_name = find_character_file_fuzzy(npc['name'])
        if matched_name:
            npc_file = path_manager.get_character_path(matched_name)
        else:
            # Fallback to normalized name if no match found
            normalized_name = normalize_character_name(npc['name'])
            npc_file = path_manager.get_character_path(normalized_name)
        
        if os.path.exists(npc_file):
            npc_data = safe_json_load(npc_file)
            if npc_data and 'name' in npc_data:
                # Use the name from the character file for consistency
                npc_entry['name'] = npc_data['name']
                debug(f"STATE_CHANGE: Using character file name '{npc_data['name']}' for party tracker", category="character_updates")
        
        # Idempotent add: skip if this NPC (by resolved display name) is already
        # on the roster, so a duplicate add is a true no-op (T105 lifecycle relies
        # on before/after roster equality to decide whether to fire).
        _existing_names = {
            str(x.get("name")) for x in party_tracker_data["partyNPCs"]
        }
        if npc_entry["name"] not in _existing_names:
            party_tracker_data["partyNPCs"].append(npc_entry)
    elif operation == "remove":
        party_tracker_data["partyNPCs"] = [x for x in party_tracker_data["partyNPCs"] if x["name"] != npc["name"]]

    safe_json_dump(party_tracker_data, "party_tracker.json")
    info(f"STATE_CHANGE: Party NPCs updated - {operation} {npc['name']}", category="character_updates")


def prepare_party_npc_update(parameters, operation_id):
    """Freeze one roster mutation and its canonical sheet before movement."""
    operation = parameters.get("operation")
    npc = parameters.get("npc")
    if operation not in {"add", "remove"} or not isinstance(npc, dict):
        raise ValueError("updatePartyNPCs requires add/remove and an npc object")
    npc_name = npc.get("name")
    if not isinstance(npc_name, str) or not npc_name.strip():
        raise ValueError("updatePartyNPCs requires an exact NPC name")
    party = safe_json_load("party_tracker.json")
    if not isinstance(party, dict) or not isinstance(party.get("partyNPCs"), list):
        raise RuntimeError("party roster is unavailable")
    roster_before = copy.deepcopy(party["partyNPCs"])
    module_name = str(party.get("module", "")).replace(" ", "_")
    path_manager = ModulePathManager(module_name)
    from updates.update_character_info import (
        find_character_file_fuzzy,
        normalize_character_name,
    )

    matched_name = find_character_file_fuzzy(npc_name)
    npc_path = path_manager.get_character_path(
        matched_name or normalize_character_name(npc_name)
    )
    sheet = safe_json_load(npc_path) if os.path.exists(npc_path) else None
    if operation == "add" and not isinstance(sheet, dict):
        from core.generators.npc_builder import build_npc_file, load_schema

        schema = load_schema("schemas/char_schema.json")
        if not isinstance(schema, dict):
            raise RuntimeError("NPC character schema is unavailable")
        party_level = None
        members = party.get("partyMembers") or []
        if members:
            player_path = path_manager.get_character_path(
                normalize_character_name(str(members[0]))
            )
            player_sheet = safe_json_load(player_path)
            if isinstance(player_sheet, dict):
                party_level = player_sheet.get("level")
        sheet = build_npc_file(
            npc_name,
            schema,
            npc.get("race"),
            npc.get("class"),
            npc.get("level") or party_level,
            npc.get("background"),
            path_manager=path_manager,
            structural_reissue=True,
        )
        if not isinstance(sheet, dict):
            raise RuntimeError("required NPC sheet was not accepted")
        resolved_name = sheet.get("name") or npc_name
        npc_path = path_manager.get_character_path(
            normalize_character_name(resolved_name)
        )
        sheet = safe_json_load(npc_path) or sheet
    elif operation == "remove" and not isinstance(sheet, dict):
        # Removal still uses the canonical roster display identity. A missing
        # sheet is retained as an explicit lifecycle-unavailable fact rather
        # than causing code to invent another NPC identity.
        roster_match = next(
            (
                item
                for item in roster_before
                if isinstance(item, dict) and item.get("name") == npc_name
            ),
            None,
        )
        if roster_match is None:
            raise ValueError("NPC is not present in the party roster")

    display_name = (
        sheet.get("name") if isinstance(sheet, dict) else npc_name
    ) or npc_name
    roster_after = copy.deepcopy(roster_before)
    if operation == "add":
        if not any(
            isinstance(item, dict) and item.get("name") == display_name
            for item in roster_after
        ):
            roster_after.append(
                {
                    "name": display_name,
                    "role": npc.get("role", npc.get("class", "Companion")),
                }
            )
    else:
        roster_after = [
            item
            for item in roster_after
            if not isinstance(item, dict) or item.get("name") != npc_name
        ]
    return {
        "kind": "updatePartyNPCs",
        "operation_id": operation_id,
        "phase": "sheet_ready",
        "operation": operation,
        "npc_name": display_name,
        "npc_path": npc_path,
        "sheet": copy.deepcopy(sheet),
        "roster_before": roster_before,
        "roster_after": roster_after,
        "lifecycle_context": copy.deepcopy(parameters.get("lifecycleContext")),
        "lifecycle_status": "pending",
    }


def _apply_party_npc_lifecycle(
    party_tracker_data,
    operation,
    npc_name,
    npc_file,
    lifecycle_context,
    source_turn_id,
):
    """Best-effort post-commit lifecycle hook; never rolls back the roster."""
    try:
        from core.npc.profile_service import seed_profile_best_effort
        from core.npc.relationship_store import RelationshipStore, game_day_ordinal

        context = lifecycle_context if isinstance(lifecycle_context, dict) else {}
        module = str(party_tracker_data.get("module") or "")
        world = party_tracker_data.get("worldConditions", {})
        world = world if isinstance(world, dict) else {}
        location_id = str(world.get("currentLocationId") or "")
        game_day = game_day_ordinal(world)
        player_names = party_tracker_data.get("partyMembers", [])
        player_name = (
            str(player_names[0]).strip()
            if isinstance(player_names, list) and player_names
            else ""
        )
        if not player_name or not npc_name or not npc_file:
            raise ValueError("lifecycle hook is missing a committed identity path")
        path_manager = ModulePathManager(module.replace(" ", "_"))
        player_file = path_manager.get_character_path(player_name)
        store = RelationshipStore()
        if store.read_only:
            raise RuntimeError(
                "sidecar opened read-only: %s"
                % (getattr(store, "read_only_reason", None) or "unknown")
            )
        starting_revision = store.snapshot()["revision"]
        npc_id = store.ensure_identity(
            kind="npc",
            display_name=npc_name,
            sheet_path=npc_file,
            module=module,
            location_id=location_id,
            active=None,
        )
        player_id = store.ensure_identity(
            kind="player",
            display_name=player_name,
            sheet_path=player_file,
            module=module,
            location_id=location_id,
        )
        store.get_relationship(npc_id, player_id, game_day=game_day)
        if operation == "add":
            store.migrate_legacy_identity(npc_id, player_id, game_day=game_day)
            store.mark_joined(
                npc_id,
                player_id,
                game_day=game_day,
                module=module,
                location_id=location_id,
                source_turn_id=source_turn_id,
                lifecycle_context=context,
            )
            sheet = safe_json_load(npc_file)
            if not isinstance(sheet, dict):
                raise ValueError("committed NPC sheet became unreadable")
            lifecycle_events = (
                store.snapshot().get("lifecycle", {}).get(npc_id, {}).get(
                    "events", []
                )
            )
            original_join = next(
                (
                    event
                    for event in lifecycle_events
                    if isinstance(event, dict) and event.get("kind") == "join"
                ),
                {},
            )
            lifecycle_source = {
                "reason": original_join.get("cause", "unknown"),
                "invitedBy": original_join.get("invitedBy", "unknown"),
                "terms": original_join.get("terms", ""),
                "personalObjective": original_join.get("personalObjective", ""),
                "redLines": original_join.get("redLines", []),
                "compensation": original_join.get("compensation", ""),
                "expectedDuration": original_join.get(
                    "expectedDuration", "unknown"
                ),
            }
            seed_profile_best_effort(
                store=store,
                npc_id=npc_id,
                npc_name=npc_name,
                sheet=sheet,
                lifecycle=lifecycle_source,
            )
        elif operation == "remove":
            store.mark_departed(
                npc_id,
                module=module,
                location_id=location_id,
                cause=str(context.get("reason") or "unknown"),
                departure_kind=str(context.get("departureKind") or "unknown"),
                destination=str(context.get("destination") or "unknown"),
                return_hook=str(context.get("returnHook") or ""),
                unresolved_obligations=context.get("unresolvedObligations", []),
                game_day=game_day,
                source_turn_id=source_turn_id,
            )
        else:
            raise ValueError("party NPC lifecycle operation is invalid")

        final = store.snapshot()
        edge_key = "%s|%s" % (npc_id, player_id)
        identity = final["identities"].get(npc_id, {})
        events = final["lifecycle"].get(npc_id, {}).get("events", [])
        if operation == "add":
            complete = (
                identity.get("active") is True
                and edge_key in final["relationships"]
                and npc_id in final["profiles"]
                and bool(events)
                and events[-1].get("kind") in {"join", "rejoin"}
            )
        else:
            complete = (
                identity.get("active") is False
                and bool(events)
                and events[-1].get("kind") == "depart"
            )
        if not complete or final["revision"] <= starting_revision:
            raise RuntimeError("sidecar lifecycle update did not commit completely")
        return True
    except Exception as exc:
        warning(
            "T105 NPC lifecycle sidecar update failed open: %s: %s"
            % (type(exc).__name__, str(exc)),
            category="character_updates",
        )
        return False


def run_combat_simulation(
    encounter_id,
    party_tracker_data,
    location_data,
    invocation_claim=None,
):
    """Run the combat simulation"""
    # Import here to avoid circular imports
    from core.managers.combat_manager import run_combat_simulation as run_combat
    return run_combat(
        encounter_id,
        party_tracker_data,
        location_data,
        invocation_claim=invocation_claim,
    )


def _cache_module_starting_location(
    module_name: str,
    starting_location: tuple,
    *,
    registry_path: str = "modules/world_registry.json",
) -> bool:
    """Merge one cache entry into the latest registry under its write lock."""
    from utils.module_refresh_lock import module_refresh_lock

    if (
        not isinstance(module_name, str)
        or not module_name
        or not isinstance(starting_location, (tuple, list))
        or len(starting_location) < 4
    ):
        return False
    with module_refresh_lock() as acquired:
        if not acquired:
            return False
        world_registry = safe_json_load(registry_path)
        if not isinstance(world_registry, dict):
            return False
        modules = world_registry.get("modules")
        if not isinstance(modules, dict):
            return False
        module_data = modules.get(module_name)
        # Never resurrect a module removed while the model call was in flight.
        if not isinstance(module_data, dict):
            return False
        module_data["startingLocation"] = {
            "locationId": starting_location[0],
            "locationName": starting_location[1],
            "areaId": starting_location[2],
            "areaName": starting_location[3],
            "determinedBy": "AI",
            "timestamp": datetime.now().isoformat(),
        }
        safe_json_dump(world_registry, registry_path)
        return True

def get_module_starting_location(module_name: str) -> tuple:
    """Get the starting location for a module using AI analysis with caching"""
    try:
        # Check world registry for cached starting location
        world_registry_path = "modules/world_registry.json"
        world_registry = safe_json_load(world_registry_path)
        
        if world_registry and 'modules' in world_registry:
            module_data = world_registry['modules'].get(module_name, {})
            cached_start = module_data.get('startingLocation')
            
            # INT-H5: only trust the cache if it has the real IDs. A partial
            # cache (missing locationId/areaId) must NOT yield A01/AREA001
            # placeholders that strand the player -- fall through to analysis.
            if cached_start and cached_start.get('locationId') and cached_start.get('areaId'):
                debug(f"FILE_OP: Using cached starting location for {module_name}", category="module_loading")
                return (
                    cached_start['locationId'],
                    cached_start.get('locationName', 'Unknown Location'),
                    cached_start['areaId'],
                    cached_start.get('areaName', 'Unknown Area')
                )
        
        # No cached result, use AI to analyze module
        debug(f"AI_CALL: No cached starting location found, analyzing {module_name} with AI", category="module_loading")
        
        path_manager = ModulePathManager(module_name)
        area_ids = path_manager.get_area_ids()
        
        if not area_ids:
            error(f"FAILURE: Module {module_name} has no area files; cannot "
                  f"determine a valid starting location.", category="module_loading")
            return ("A01", "Unknown Location", "AREA001", "Unknown Area")
        
        # Gather all module data for AI analysis
        module_analysis_data = {
            "moduleName": module_name,
            "areas": {},
            "plotData": None
        }
        
        # Load all area files
        for area_id in area_ids:
            try:
                area_file = path_manager.get_area_path(area_id)
                area_data = safe_json_load(area_file)
                if area_data:
                    # Include key information for AI analysis
                    module_analysis_data["areas"][area_id] = {
                        "areaName": area_data.get("areaName", ""),
                        "areaType": area_data.get("areaType", ""),
                        "areaDescription": area_data.get("areaDescription", ""),
                        "recommendedLevel": area_data.get("recommendedLevel", 1),
                        "dangerLevel": area_data.get("dangerLevel", "unknown"),
                        "locations": area_data.get("locations", [])  # All locations for analysis
                    }
            except Exception as e:
                warning(f"FILE_OP: Could not load area {area_id}: {e}", category="file_operations")
                continue
        
        # Load plot data
        try:
            plot_file = path_manager.get_plot_path()
            plot_data = safe_json_load(plot_file)
            if plot_data:
                # Include key plot information
                module_analysis_data["plotData"] = {
                    "mainObjective": plot_data.get("mainObjective", ""),
                    "plotPoints": plot_data.get("plotPoints", [])  # All plot points
                }
        except Exception as e:
            warning(f"FILE_OP: Could not load plot data: {e}", category="file_operations")
        
        # Use AI to determine starting location
        starting_location = _ai_analyze_starting_location(module_analysis_data)
        
        # Cache the result in world registry
        if starting_location and world_registry:
            try:
                cached = _cache_module_starting_location(
                    module_name,
                    starting_location,
                    registry_path=world_registry_path,
                )
                if cached:
                    info(f"SUCCESS: Cached AI-determined starting location for {module_name}", category="module_loading")
                else:
                    warning(f"FILE_OP: Starting-location cache skipped for {module_name}; registry changed or refresh was busy", category="module_loading")
            except Exception as cache_err:
                # INT-H5: a cache-WRITE failure must not discard an already-valid
                # starting location and strand the player; log and continue.
                warning(f"FILE_OP: Could not cache starting location for {module_name}: {cache_err}", category="module_loading")

        return starting_location

    except Exception as e:
        error(f"FAILURE: Could not get starting location for {module_name}: {e}", category="module_loading")
        # INT-H5: recover a REAL location from the module's area files rather
        # than writing placeholder IDs (A01/AREA001) that resolve to no area
        # file and strand the player at a non-existent location.
        real = _first_real_location_from_files(module_name)
        if real:
            warning(f"STARTING_LOCATION: falling back to first real location "
                    f"{real[2]}:{real[0]} for {module_name}", category="module_loading")
            return real
        return ("A01", "Unknown Location", "AREA001", "Unknown Area")

def _ai_analyze_starting_location(module_data: dict) -> tuple:
    """Use AI to analyze module data and determine the best starting location"""
    try:
        system_prompt = """You are an expert 5th edition adventure module analyst. Analyze the provided module data to determine the most logical starting location for player characters entering this adventure module.

ANALYSIS CRITERIA:
1. **Adventure Flow**: Look at plot points (PP001 usually indicates starting area)
2. **Area Types**: Towns/settlements are typical starting points, dungeons/ruins typically aren't
3. **NPCs**: Areas with guides, quest-givers, or friendly NPCs often indicate starting locations
4. **Danger Level**: Lower danger areas are more suitable for arrivals
5. **Logical Narrative**: Where would adventurers most likely arrive or be directed to begin?

RETURN FORMAT:
Respond with ONLY a JSON object in this exact format:
{
  "locationId": "R01",
  "locationName": "Specific Location Name", 
  "areaId": "SR001",
  "areaName": "Area Name",
  "reasoning": "Brief explanation of why this is the starting location"
}

Use the EXACT locationId and areaId from the provided data. Do not create new IDs."""

        user_prompt = f"""Analyze this 5th edition adventure module to determine the starting location:

MODULE DATA:
{json.dumps(module_data, indent=2)}

Determine the most logical starting location based on adventure flow, area types, NPCs, and narrative logic."""

        # T012: starting-location analysis helper (mini-tier JSON extraction).
        # Route through the provider-aware router so MODEL_PROVIDER toggle
        # actually drives which provider/model handles the call.
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            locstart_cfg = config.DM_LOCSTART_T012_GPT5MINI
        elif MODEL_PROVIDER == "gemini":
            locstart_cfg = config.DM_LOCSTART_T012_GEMINI_FLASHLITE_LOW
        elif MODEL_PROVIDER == "lmstudio":
            locstart_cfg = config.DM_LOCSTART_T012_LMSTUDIO
        else:  # legacy
            locstart_cfg = config.DM_LOCSTART_T012_LEGACY

        # T012: fail loud (gemini-only) if response_schema is missing. Without it,
        # gemini-flash-lite emits narration instead of the location JSON, forcing a
        # degraded first-area fallback.
        if MODEL_PROVIDER == "gemini" and locstart_cfg.get("response_schema") is None:
            raise RuntimeError(
                "T012 starting-location analysis aborted: Gemini response_schema is "
                "None. Refusing to run -- Gemini would emit narration and force a "
                "degraded fallback location."
            )

        response = capture_and_fanout("T012", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=locstart_cfg["model"],
            temperature=0.1,
            **{k: v for k, v in locstart_cfg.items() if k != "model"})
        
        # Track token usage
        if USAGE_TRACKING_AVAILABLE:
            try:
                track_response(response)
            except:
                pass
        
        ai_response = response.choices[0].message.content.strip()
        debug(f"AI_CALL: Starting location analysis response: {ai_response}", category="ai_operations")
        
        # Parse AI response - handle markdown code blocks
        json_content = ai_response
        if ai_response.startswith('```json'):
            # Extract JSON from markdown code block
            lines = ai_response.split('\n')
            json_lines = []
            in_json_block = False
            for line in lines:
                if line.strip() == '```json':
                    in_json_block = True
                    continue
                elif line.strip() == '```' and in_json_block:
                    break
                elif in_json_block:
                    json_lines.append(line)
            json_content = '\n'.join(json_lines)
            debug(f"AI_CALL: Extracted JSON from code block: {json_content}", category="ai_operations")
        
        try:
            result = json.loads(json_content)
            
            # Validate required fields
            required_fields = ['locationId', 'locationName', 'areaId', 'areaName']
            if all(field in result for field in required_fields):
                info(f"AI_CALL: AI determined starting location: {result['areaId']}/{result['locationId']} - {result['locationName']}", category="module_loading")
                debug(f"AI_CALL: AI reasoning: {result.get('reasoning', 'No reasoning provided')}", category="ai_operations")
                
                return (
                    result['locationId'],
                    result['locationName'],
                    result['areaId'], 
                    result['areaName']
                )
            else:
                print(f"ERROR: AI response missing required fields: {result}")
                
        except json.JSONDecodeError as e:
            print(f"ERROR: Could not parse AI response as JSON: {e}")
            print(f"AI response was: {ai_response}")
        
        # Fallback to first area/location if AI analysis fails
        print("WARNING: AI analysis failed, falling back to first available location")
        return _get_fallback_starting_location(module_data)
        
    except Exception as e:
        print(f"ERROR: AI starting location analysis failed: {e}")
        return _get_fallback_starting_location(module_data)

def _get_fallback_starting_location(module_data: dict) -> tuple:
    """Fallback method to get first available location if AI analysis fails"""
    try:
        areas = module_data.get('areas', {})
        if areas:
            # Get first area
            first_area_id = next(iter(areas.keys()))
            first_area = areas[first_area_id]
            
            locations = first_area.get('locations', [])
            if locations:
                first_location = locations[0]
                return (
                    first_location.get('locationId', 'A01'),
                    first_location.get('name', 'Unknown Location'),
                    first_area_id,
                    first_area.get('areaName', 'Unknown Area')
                )
        
        return ("A01", "Unknown Location", "AREA001", "Unknown Area")

    except Exception as e:
        print(f"WARNING: Fallback location detection failed: {e}")
        return ("A01", "Unknown Location", "AREA001", "Unknown Area")

def _first_real_location_from_files(module_name: str) -> tuple:
    """Scan a module's area files on disk and return the first REAL
    (locationId, locationName, areaId, areaName), or None if none exists.

    INT-H5 safety net: used when get_module_starting_location's primary path
    fails, so the player is never written into party_tracker.json at a
    placeholder location (A01/AREA001) that resolves to no area file.
    """
    try:
        path_manager = ModulePathManager(module_name)
        for area_id in sorted(path_manager.get_area_ids() or []):
            try:
                area_data = safe_json_load(path_manager.get_area_path(area_id))
            except Exception:
                continue
            if not area_data:
                continue
            locations = area_data.get("locations") or []
            if locations and isinstance(locations[0], dict) and locations[0].get("locationId"):
                loc = locations[0]
                return (
                    loc["locationId"],
                    loc.get("name", "Unknown Location"),
                    area_data.get("areaId", area_id),
                    area_data.get("areaName", "Unknown Area"),
                )
    except Exception:
        pass
    return None

def get_travel_narration(target_module: str) -> str:
    """Get AI-generated travel narration for module transition"""
    try:
        world_registry = safe_json_load("modules/world_registry.json")
        if world_registry and "modules" in world_registry:
            module_data = world_registry["modules"].get(target_module, {})
            travel_data = module_data.get("travelNarration", {})
            return travel_data.get("travelNarration", 
                f"The party travels to the {target_module} region, where new adventures await.")
    except:
        return f"The party travels to the {target_module} region, where new adventures await."

def process_action(
    action,
    party_tracker_data,
    location_data,
    conversation_history,
    *,
    approved_transition_plan=None,
    transition_deferred_actions=None,
    invocation_claim=None,
):
    """Process an action based on its type
    
    Returns:
        dict: {
            "status": "continue" | "exit" | "needs_response",
            "needs_update": bool,
            "response_data": dict (optional) - data for generating new AI response
        }
    """
    # Import modules here to avoid circular imports
    from core.managers import location_manager
    from updates.update_world_time import update_world_time
    from updates.plot_update import update_plot
    from updates.update_character_info import update_character_info

    # Helper function to create consistent return values
    def create_return(status="continue", needs_update=False, response_data=None):
        result = {"status": status, "needs_update": needs_update}
        if response_data:
            result["response_data"] = response_data
        return result

    global needs_conversation_history_update
    needs_conversation_history_update = False
    
    action_type = action.get("action")
    parameters = action.get("parameters", {})

    if action_type == ACTION_CREATE_ENCOUNTER:
        print("\n[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER START ==========")
        print(f"[DEBUG ACTION_HANDLER] Action received: {action}")
        debug("INITIALIZATION: Creating combat encounter", category="combat_processing")

        # The model cannot replace or duplicate an encounter that is still
        # authoritative. This is especially important when an agentic fight
        # is paused for recovery: its tracker entry must survive until the
        # player restores/heals/loads rather than being overwritten by a new
        # createEncounter response.
        authoritative_party = safe_json_load("party_tracker.json")
        authoritative_party = authoritative_party or party_tracker_data
        active_encounter = (
            authoritative_party.get("worldConditions", {})
            .get("activeCombatEncounter", "")
        )
        if active_encounter:
            active_path = os.path.join(
                "modules", "encounters", f"encounter_{active_encounter}.json"
            )
            active_data = safe_json_load(active_path)
            stale_active = not isinstance(active_data, dict)
            if isinstance(active_data, dict):
                from core.managers.combat_state import (
                    all_hostiles_resolved,
                    all_party_resolved,
                )
                active_state = active_data.get("combatState") or {}
                if active_state.get("pipelineMode") == "agentic":
                    stale_active = (
                        (active_state.get("completion") or {}).get("status")
                        == "closed"
                    )
                else:
                    stale_active = (
                        all_hostiles_resolved(active_data)
                        or all_party_resolved(active_data)
                    )
            if stale_active:
                warning(
                    "Clearing stale active encounter %s before creating a new one"
                    % active_encounter,
                    category="combat_processing",
                )
                authoritative_party.setdefault("worldConditions", {})[
                    "activeCombatEncounter"
                ] = ""
                party_tracker_data.setdefault("worldConditions", {})[
                    "activeCombatEncounter"
                ] = ""
                if not safe_write_json("party_tracker.json", authoritative_party):
                    return create_return(
                        status="combat_recovery_required",
                        needs_update=False,
                        response_data={
                            "recovery_required": True,
                            "active_encounter": active_encounter,
                        },
                    )
            else:
                warning(
                    "Rejected createEncounter while %s remains active"
                    % active_encounter,
                    category="combat_processing",
                )
                return create_return(
                    status="combat_recovery_required",
                    needs_update=False,
                    response_data={
                        "recovery_required": True,
                        "active_encounter": active_encounter,
                        "player_message": (
                            "The existing combat remains active. Wait for the "
                            "player to load or restore a save; do not create "
                            "another encounter."
                        ),
                    },
                )
        
        # Update status to lock input during encounter building
        try:
            from core.managers.status_manager import status_manager
            status_manager.update_status("Prepare for battle - building encounter...", is_processing=True)
            debug("STATE_CHANGE: Status updated to building encounter", category="combat_processing")
        except Exception as e:
            error(f"FAILURE: Could not update status for encounter building", exception=e, category="combat_processing")
        
        try:
            print("[DEBUG ACTION_HANDLER] Calling combat_builder.py...")
            debug(f"SUBPROCESS: Sending to combat_builder.py: {json.dumps(action)}", category="combat_processing")
            # Get the path to combat_builder.py relative to the project root
            combat_builder_path = _generator_script_path("combat_builder.py")
            
            result = subprocess.run(
                [sys.executable, combat_builder_path],
                input=json.dumps(action),
                check=True, capture_output=True, text=True
            )
            print(f"[DEBUG ACTION_HANDLER] combat_builder.py completed")
            print(f"[DEBUG ACTION_HANDLER] Output: {result.stdout[:200]}...")  # First 200 chars
            debug(f"SUBPROCESS: combat_builder.py output: {result.stdout}", category="combat_processing")
            debug(f"SUBPROCESS: combat_builder.py status: {result.stderr}", category="combat_processing")
            info("SUCCESS: Combat encounter created successfully", category="combat_processing")

            print(f"[DEBUG ACTION_HANDLER] Checking for success in output...")
            if "Encounter successfully built and saved to" in result.stdout:
                # Extract encounter ID from the full path
                # Example: "modules/encounters/encounter_TW03-E2.json" -> "TW03-E2"
                for line in result.stdout.split('\n'):
                    if "Encounter successfully built and saved to" in line:
                        encounter_path = line.split()[-1]
                        encounter_id = encounter_path.split('encounter_')[-1].replace('.json', '')
                        print(f"[DEBUG ACTION_HANDLER] SUCCESS! Encounter created with ID: {encounter_id}")
                        break

                # The builder persists an inactive typed candidate. Combat
                # setup writes the complete history marker and conditionally
                # activates it immediately before provider-backed play. If a
                # competing encounter already won, resume that authority.
                authoritative_party = safe_json_load("party_tracker.json")
                activated_id = (
                    (authoritative_party or {})
                    .get("worldConditions", {})
                    .get("activeCombatEncounter", "")
                )
                if activated_id and activated_id != encounter_id:
                    warning(
                        "Prepared encounter %s lost activation to %s; resuming it"
                        % (encounter_id, activated_id),
                        category="combat_processing",
                    )
                    encounter_id = activated_id
                party_tracker_data.clear()
                party_tracker_data.update(authoritative_party or {})
                debug(
                    f"STATE_CHANGE: Preparing combat encounter ID: {encounter_id}",
                    category="combat_processing",
                )

                # Reload location data here
                current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
                current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
                # Use the reloaded location data for the combat simulation
                reloaded_location_data = get_location_data(current_location_id, current_area_id)


                if reloaded_location_data is None:
                    print(f"ERROR: Failed to load location data for {current_location_id}")
                    return # Or handle error appropriately

                print(f"[DEBUG ACTION_HANDLER] About to call run_combat_simulation with encounter: {encounter_id}")
                print("[DEBUG ACTION_HANDLER] This should start INTERACTIVE turn-based combat...")
                
                # Update status to show combat is starting
                try:
                    from core.managers.status_manager import status_manager
                    status_manager.update_status("Combat in progress...", is_processing=True)
                    debug("STATE_CHANGE: Status updated to combat in progress", category="combat_processing")
                except Exception as e:
                    error(f"FAILURE: Could not update status for combat start", exception=e, category="combat_processing")
                
                dialogue_summary, updated_player_info = run_combat_simulation(
                    encounter_id,
                    party_tracker_data,
                    reloaded_location_data,
                    invocation_claim=invocation_claim,
                )

                authoritative_party = safe_json_load("party_tracker.json")
                active_after_combat = (
                    (authoritative_party or party_tracker_data)
                    .get("worldConditions", {})
                    .get("activeCombatEncounter", "")
                )
                if active_after_combat:
                    encounter_id = active_after_combat
                active_after_data = (
                    safe_json_load(
                        os.path.join(
                            "modules",
                            "encounters",
                            f"encounter_{active_after_combat}.json",
                        )
                    )
                    if active_after_combat
                    else None
                )
                active_after_state = (
                    active_after_data.get("combatState")
                    if isinstance(active_after_data, dict)
                    else {}
                ) or {}
                if (
                    active_after_combat == encounter_id
                    and active_after_state.get("pipelineMode") == "agentic"
                    and active_after_state.get("phase") == "recovery_required"
                    and active_after_state.get("pauseReason")
                ):
                    print(
                        "[DEBUG ACTION_HANDLER] Combat remains active; "
                        "skipping stale-summary and post-combat handling."
                    )
                    return create_return(
                        status="combat_recovery_required",
                        needs_update=False,
                        response_data={
                            "recovery_required": True,
                            "active_encounter": encounter_id,
                            "player_message": (
                                "Combat is paused. Wait for the player to load "
                                "or restore a save; do not request another "
                                "encounter."
                            ),
                        },
                    )
                
                print(f"[DEBUG ACTION_HANDLER] Combat simulation returned. Type of result: {type(dialogue_summary)}")
                print(f"[DEBUG ACTION_HANDLER] Dialogue summary preview: {str(dialogue_summary)[:200]}...")

                player_name = next((member for member in party_tracker_data["partyMembers"]), None)
                if player_name and updated_player_info is not None:
                    # Get the correct module from party tracker
                    module_name = party_tracker_data.get("module", "").replace(" ", "_")
                    path_manager = ModulePathManager(module_name)
                    # Normalize name for file access
                    from updates.update_character_info import normalize_character_name
                    player_name_normalized = normalize_character_name(player_name)
                    player_file = path_manager.get_character_path(player_name_normalized)
                    safe_json_dump(updated_player_info, player_file)
                    debug(f"FILE_OP: Updated player file for {player_name}", category="character_updates")
                else:
                    print("WARNING: Combat simulation did not return valid player info. Player file not updated.")

                # Copy combat summary to main conversation history
                print("[DEBUG ACTION_HANDLER] Loading combat conversation history...")
                combat_history = safe_json_load("modules/conversation_history/combat_conversation_history.json")
                print(f"[DEBUG ACTION_HANDLER] Combat history has {len(combat_history) if combat_history else 0} entries")
                
                combat_summary = next((entry for entry in reversed(combat_history) if entry["role"] == "assistant" and "Combat Summary:" in entry["content"]), None)

                if combat_summary:
                    print("[DEBUG ACTION_HANDLER] Found combat summary, appending to conversation history")
                    # Add clear historical marker to prevent Combat Commitment Point confusion
                    modified_combat_summary = {
                        "role": "user",
                        "content": "[COMBAT CONCLUDED - HISTORICAL RECORD]\n" + combat_summary["content"] + "\n[END OF COMBAT RECORD - Please continue the narrative after this combat]\n\nIMPORTANT: This historical record describes character changes already applied by the combat system, including HP, spell slots, effects, XP, treasure, currency, items, and other rewards. Do not re-emit updateCharacterInfo actions for those changes."
                    }
                    conversation_history.append(modified_combat_summary)
                    # Import save_conversation_history from main
                    if __name__ != "__main__":

                        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

                    from main import save_conversation_history
                    save_conversation_history(conversation_history)
                    print("[DEBUG ACTION_HANDLER] Returning with status='needs_post_combat_narration' - main loop will get follow-up from AI")
                    print("[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END ==========\n")
                    # SIGNAL-BASED ARCHITECTURE: This return value is crucial for maintaining chronological history.
                    # When combat ends, we've already added the [COMBAT CONCLUDED...] summary to conversation_history.
                    # This signal tells main.py to:
                    # 1. NOT append the original createEncounter message (preventing duplication)
                    # 2. Request a new AI response for natural post-combat narration
                    # This ensures players get seamless transitions like Kira's dialogue after combat.
                    return {"status": "needs_post_combat_narration"}
                else:
                    print("ERROR: Combat summary not found in combat conversation history")
                    print("[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END WITH ERROR ==========\n")
                    # Reset status on error
                    try:
                        from core.managers.status_manager import status_ready
                        status_ready()
                    except Exception:
                        pass
            else:
                print(f"[DEBUG ACTION_HANDLER] FAILED! Encounter was not created successfully")
                print(f"[DEBUG ACTION_HANDLER] Full stdout: {result.stdout}")
                print(f"[DEBUG ACTION_HANDLER] Full stderr: {result.stderr}")
                print("[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END WITH FAILURE ==========\n")
                # Reset status on failure
                try:
                    from core.managers.status_manager import status_ready
                    status_ready()
                except Exception:
                    pass

        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running combat_builder.py: {e}")
            print("Error output:", e.stderr)
            print("Standard output:", e.stdout)
            # Reset status on exception
            try:
                from core.managers.status_manager import status_ready
                status_ready()
            except Exception:
                pass
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
            # Reset status on exception
            try:
                from core.managers.status_manager import status_ready
                status_ready()
            except Exception:
                pass

    elif action_type == ACTION_UPDATE_TIME:
        status_advancing_time()
        time_estimate_str = str(parameters["timeEstimate"])
        update_world_time(time_estimate_str)

    elif action_type == ACTION_UPDATE_PLOT:
        status_updating_plot()
        plot_point_id = parameters["plotPointId"]
        new_status = parameters["newStatus"]
        plot_impact = parameters.get("plotImpact", "")
        plot_filename = "module_plot.json"  # Now using unified plot file
        updated_plot = update_plot(plot_point_id, new_status, plot_impact, plot_filename)

    elif action_type == ACTION_EXIT_GAME:
        # Don't add return message here - it will be added when the player actually returns
        if __name__ != "__main__":

            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        from main import save_conversation_history, exit_game
        save_conversation_history(conversation_history)
        exit_game()
        return create_return(status="exit")

    elif action_type == ACTION_TRANSITION_LOCATION:
        status_transitioning_location()
        new_location_name_or_id = parameters["newLocation"] # This should be a location ID now
        
        # Sanitize location names to prevent encoding issues
        current_location_name = sanitize_text(party_tracker_data["worldConditions"]["currentLocation"])
        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
        current_area_name = party_tracker_data["worldConditions"]["currentArea"]
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]

        if party_tracker_data["worldConditions"].get("activeCombatEncounter"):
            return create_return(
                status="error",
                needs_update=False,
                response_data={
                    "error_message": (
                        "Travel is unavailable while combat is active. "
                        "Resolve or end combat before moving the party."
                    ),
                    "retryable": True,
                },
            )
        
        # An authorized transition already has a canonical active-module ID.
        # Do not load or consult the all-module legacy graph: duplicate IDs in
        # another installed module must not reinterpret the approved action.
        location_graph = None

        # Re-read the same canonical active-module snapshot used during
        # planning. The legacy global graph remains available for names and
        # cross-module compatibility, but it is no longer a second authority
        # for an approved within-module route.
        authoritative_party = safe_json_load("party_tracker.json")
        if not isinstance(authoritative_party, dict):
            authoritative_party = party_tracker_data
        plan_valid, plan_error, verified_transition_context = verify_approved_transition_plan(
            approved_transition_plan,
            party_tracker_data=authoritative_party,
            destination_location_id=new_location_name_or_id,
            location_graph=location_graph,
            return_context=True,
        )
        if plan_valid:
            origin_node = verified_transition_context.get("origin") or {}
            destination_node = verified_transition_context.get("destination") or {}
            origin_area_id = origin_node.get("area_id")
            destination_area_id = destination_node.get("area_id")
            auto_area_connectivity_id = (
                f"{destination_area_id}-{new_location_name_or_id}"
                if origin_area_id
                and destination_area_id
                and origin_area_id != destination_area_id
                else None
            )
            is_valid, error_message = True, ""
        else:
            is_valid = False
            error_message = plan_error

        if not plan_valid:
            warning(
                f"Rejected transition without a fresh authorization: {plan_error}",
                category="location_transitions",
            )
            return create_return(
                status="error",
                needs_update=False,
                response_data={
                    "error_message": plan_error,
                    "retryable": True,
                    "error_code": "transition_plan_stale",
                },
            )
        
        if not is_valid:
            # Check if this is a cross-module transition attempt
            from core.managers.campaign_manager import CampaignManager
            campaign_manager = CampaignManager()
            
            # Determine which module owns the target location
            target_module = campaign_manager.get_module_from_location(new_location_name_or_id)
            current_module = party_tracker_data.get("module", "")
            
            if target_module and target_module != current_module:
                # This is a cross-module transition attempt!
                print(f"INFO: Cross-module transition detected: {current_module} -> {target_module}")
                
                # Get target location details for better error message
                target_location_name = "Unknown"
                if location_graph.nodes.get(new_location_name_or_id):
                    target_location_name = location_graph.nodes[new_location_name_or_id].get('location_name', 'Unknown')
                
                # Create helpful error message that guides the AI
                error_msg = (
                    f"Module Transition Required: The location '{new_location_name_or_id}' ({target_location_name}) "
                    f"is in the '{target_module}' module, but you are currently in the '{current_module}' module. "
                    f"If the player intends to travel to a different module (e.g., 'take me back to my keep', "
                    f"'let's return to {target_module}'), use the updatePartyTracker action with module parameter. "
                    f"If the player wants to stay in the current module (e.g., 'let's go to the inn'), "
                    f"use the appropriate location in the current module instead. "
                    f"For module travel, use: updatePartyTracker with module='{target_module}'"
                )
                
                print(f"ERROR: {error_msg}")
                return create_return(
                    status="error",
                    needs_update=False,
                    response_data={"error_message": error_msg}
                )
            
            # Original error for non-module path issues
            print(f"ERROR: {error_message}")
            return create_return(
                status="error",
                needs_update=False,
                response_data={"error_message": f"Path Validation: {error_message}"}
            )

        # NOTE: Transition intelligence agent now runs in PRE-VALIDATION (main.py)
        # before this action handler is called. If we reach here, the transition
        # was already approved by the agent.

        # Debug the exact string values for easier troubleshooting
        info(f"STATE_CHANGE: Transitioning from '{current_location_name}' to '{new_location_name_or_id}'", category="location_transitions")
        debug(f"VALIDATION: Current location string (hex): {current_location_name.encode('utf-8').hex()}", category="location_transitions")
        debug(f"VALIDATION: New location string (hex): {new_location_name_or_id.encode('utf-8').hex()}", category="location_transitions")

        # A request-bound transition plan is created from one active-module
        # snapshot, so both endpoints are already proven to belong to that
        # module. Do not ask the global multi-module registry to classify the
        # same IDs again: generated modules may legally reuse bare location
        # IDs and could turn an authorized local move into a false module
        # transition. Real module changes use updatePartyTracker and its
        # existing publication transaction instead.
        pending_archive = None
        campaign_manager = None

        transition_checkpoint = None
        if pending_archive is None:
            from core.managers.campaign_manager import (
                _party_module_transition_lock,
            )

            with _party_module_transition_lock():
                existing_checkpoint = safe_json_load(
                    PENDING_LOCATION_TRANSITION_FILE
                )
                if isinstance(existing_checkpoint, dict):
                    return create_return(
                        status="error",
                        needs_update=False,
                        response_data={
                            "error_message": (
                                "A prior location transition is awaiting recovery"
                            ),
                            "retryable": True,
                            "error_code": "transition_plan_stale",
                        },
                    )
                transition_checkpoint = _new_current_transition_checkpoint(
                    module_name=approved_transition_plan.module_name,
                    origin_area_id=current_area_id,
                    origin_location_id=current_location_id,
                    origin_location_name=current_location_name,
                    destination_location_id=new_location_name_or_id,
                    destination_location_name=destination_node.get(
                        "location_name", new_location_name_or_id
                    ),
                    destination_area_id=destination_node.get("area_id", ""),
                    destination_area_name=destination_node.get("area_name", ""),
                    conversation_history=conversation_history,
                    deferred_actions=transition_deferred_actions,
                    origin_party_tracker=authoritative_party,
                )
                transition_id = transition_checkpoint["operation_id"]
                _write_location_transition_checkpoint(transition_checkpoint)

            # Required semantic sibling proposals are frozen before movement,
            # outside the party/module mutation lock. A provider wait can
            # therefore neither hold the transition fence nor strand a
            # partially applied player turn.
            prepare_current_transition_actions(transition_id)
        
        # Use enhanced location manager with auto-generated area connectivity ID
        def run_location_transition():
            return location_manager.handle_location_transition(
                current_location_name,
                new_location_name_or_id,
                current_area_name,
                current_area_id,
                auto_area_connectivity_id,
                authorized_destination={
                    "module_name": approved_transition_plan.module_name,
                    "snapshot_hash": verified_transition_context.get("snapshot_hash"),
                    "topology_identity": verified_transition_context.get("topology_identity"),
                    **destination_node,
                },
                defer_post_commit=True,
            )

        if pending_archive is not None:
            try:
                transition_prompt, _transitioned_party = (
                    campaign_manager.publish_location_module_transition(
                        pending_archive["from_module"],
                        pending_archive["to_module"],
                        conversation_history,
                        pending_archive["completion_id"],
                        run_location_transition,
                    )
                )
            except Exception as e:
                error(
                    "FAILURE: Could not publish cross-module location transition",
                    exception=e,
                    category="module_management",
                )
                publication_state = _completion_publication_state(
                    campaign_manager,
                    pending_archive,
                )
                return create_return(
                    status="error",
                    needs_update=False,
                    response_data={
                        "error_message": str(e),
                        "pending_archive": pending_archive,
                        "completion_publication_state": publication_state,
                        "transition_recovery_required": (
                            publication_state != "absent"
                        ),
                    },
                )
        else:
            from core.managers.campaign_manager import (
                _party_module_transition_lock,
            )

            with _party_module_transition_lock():
                locked_party = safe_json_load("party_tracker.json")
                locked_valid, locked_error, _locked_context = (
                    verify_approved_transition_plan(
                        approved_transition_plan,
                        party_tracker_data=locked_party,
                        destination_location_id=new_location_name_or_id,
                        location_graph=None,
                        return_context=True,
                    )
                )
                if not locked_valid:
                    pending = load_current_transition_checkpoint(transition_id)
                    if pending is not None and pending.get("phase") == "planned":
                        _remove_location_transition_checkpoint()
                    return create_return(
                        status="error",
                        needs_update=False,
                        response_data={
                            "error_message": locked_error,
                            "retryable": True,
                            "error_code": "transition_plan_stale",
                        },
                    )
                transition_result = run_location_transition()
            transition_context = (
                transition_result if isinstance(transition_result, dict) else None
            )
            transition_prompt = (
                transition_context.get("transition_prompt")
                if transition_context is not None
                else transition_result
            )
            if transition_prompt and transition_checkpoint is not None:
                with _party_module_transition_lock():
                    current_checkpoint = load_current_transition_checkpoint(
                        transition_id
                    )
                    if current_checkpoint is None:
                        raise RuntimeError(
                            "current transition checkpoint disappeared before movement receipt"
                        )
                    current_checkpoint["phase"] = "movement_committed"
                    _write_location_transition_checkpoint(current_checkpoint)

            if transition_prompt and transition_context is not None:
                reconciliation_status = resolve_current_transition_reconciliation(
                    transition_id, transition_context
                )
                if reconciliation_status == "blocked_conflict":
                    return create_return(
                        status="error",
                        needs_update=False,
                        response_data={
                            "error_message": (
                                "The origin location changed while its committed "
                                "departure was being reconciled. Recovery is "
                                "required before another turn."
                            ),
                            "retryable": False,
                            "error_code": "transition_recovery_conflict",
                        },
                    )
                departure_summary = resolve_current_transition_departure(
                    transition_id, transition_context
                )
                transition_context["departure_summary"] = departure_summary

        if transition_prompt:
            info("SUCCESS: Location movement and departure state committed", category="location_transitions")
            response_data = {
                "transition_prompt": transition_prompt,
                "departure_summary": transition_context.get("departure_summary"),
            }
            if transition_checkpoint is not None:
                response_data["location_transition_id"] = transition_checkpoint[
                    "operation_id"
                ]
            return create_return(needs_update=True, response_data=response_data)
             # After transition, the current_location_data in the main loop might be stale.
            # We need to ensure the AI response processing uses the *new* location data.
            # This might require process_ai_response to reload location data or for main_game_loop to handle it.
            # For now, let's assume the main loop will reload it before the next AI call.
        else:
            if transition_checkpoint is not None:
                authoritative_after = safe_json_load("party_tracker.json") or {}
                after_location = authoritative_after.get(
                    "worldConditions", {}
                ).get("currentLocationId")
                if str(after_location or "") == str(current_location_id):
                    _remove_location_transition_checkpoint()
            print("ERROR: Failed to handle location transition")
            # Create error message for the AI DM
            error_message = f"""SYSTEM ERROR: Location Transition Failed

The attempted transition to '{new_location_name_or_id}' failed because this location does not exist or is not connected from the current location '{current_location_name}'.

Please use a valid location that exists in the current area ({current_area_id}) and is connected to the current location. Check the map data and connectivity information to ensure valid transitions."""
            
            # Append error to conversation history
            conversation_history.append({"role": "user", "content": error_message})
            
            # Import necessary functions from main
            if __name__ != "__main__":

                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

            from main import save_conversation_history
            save_conversation_history(conversation_history)
            
            # Return signal to get new AI response
            return create_return(status="needs_response", needs_update=True)

    elif action_type == ACTION_LEVEL_UP:
        status_processing_levelup()
        entity_name = parameters.get("entityName")
        new_level = parameters.get("newLevel")
        info(f"INITIALIZATION: Starting levelUp session for {entity_name} to level {new_level}", category="character_updates")

        try:
            # Import the session manager
            from core.managers.level_up_manager import LevelUpSession
            
            # Find character file to get current level
            from updates.update_character_info import normalize_character_name
            module_name = party_tracker_data.get("module", "").replace(" ", "_")
            path_manager = ModulePathManager(module_name)
            char_file = path_manager.get_character_path(normalize_character_name(entity_name))
            character_data = safe_read_json(char_file)
            
            if not character_data:
                print(f"ERROR: Could not find character {entity_name} to start level up.")
                # Return an error message to display in the UI
                return create_return(status="error", response_data={"error_message": "Character data not found."})

            current_level = character_data.get("level", 1)

            # Create a new level up session object
            level_up_session = LevelUpSession(entity_name, current_level, new_level)
            
            # Return a special status to the main loop, passing the session object
            return {
                "status": "enter_levelup_mode",
                "session": level_up_session
            }

        except Exception as e:
            print(f"ERROR: A critical error occurred while initializing the level up session: {e}")
            import traceback
            traceback.print_exc()
            return create_return(status="error", response_data={"error_message": "System error during level up."})

    elif action_type == ACTION_UPDATE_CHARACTER_INFO:
        status_updating_character()
        debug("STATE_CHANGE: Processing updateCharacterInfo action", category="character_updates")
        changes = parameters.get("changes")
        
        # Validate changes parameter
        if not changes or not isinstance(changes, (str, dict)):
            print(f"ERROR: Invalid changes parameter: {changes} (type: {type(changes)})")
            return create_return(status="continue", needs_update=False)
        
        # Convert dict to string if needed
        if isinstance(changes, dict):
            changes = json.dumps(changes)
        
        character_name = parameters.get("characterName")
        
        # Backward compatibility: if no characterName provided, try legacy parameters
        if not character_name:
            # Try npcName first (for NPC updates)
            character_name = parameters.get("npcName")
            if not character_name:
                # Fall back to player name from party tracker
                character_name = next((member.lower() for member in party_tracker_data["partyMembers"]), None)
        
        if character_name:
            debug(f"STATE_CHANGE: Updating character info for {character_name}", category="character_updates")
            try:
                from core.managers.effects_runtime import update_character_with_effects

                debug(f"STATE_CHANGE: Calling effects-aware character update for {character_name}", category="character_updates")
                success = update_character_with_effects(
                    character_name,
                    changes,
                    party_tracker_data,
                )
                debug(f"STATE_CHANGE: effects-aware character update returned {success}", category="character_updates")
                if success:
                    info("SUCCESS: Character info updated successfully", category="character_updates")
                    needs_conversation_history_update = True
                else:
                    error(f"FAILURE: Failed to update character info for {character_name}", category="character_updates")
                    print(f"ERROR: Failed to update character info for {character_name}")
                    return create_return(
                        status="error",
                        response_data={
                            "error_message": "Character update failed safely; no partial effect was applied."
                        },
                    )
            except Exception as e:
                error(f"FAILURE: Exception in character update", exception=e, category="character_updates")
                # Use print with separate arguments to avoid format string interpretation
                print("ERROR: Failed to update character info:", str(e))
                return create_return(
                    status="error",
                    response_data={
                        "error_message": "Character effect classification or update failed safely."
                    },
                )
            finally:
                # Always reset status after character update completes
                try:
                    from core.managers.status_manager import status_ready
                    status_ready()
                    debug("STATE_CHANGE: Status reset after character update", category="character_updates")
                except Exception:
                    pass
        else:
            print("ERROR: No character name provided and no player found in party tracker.")
            # Reset status even if no character was found
            try:
                from core.managers.status_manager import status_ready
                status_ready()
            except Exception:
                pass

    elif action_type == ACTION_REMOVE_EFFECT:
        status_updating_character()
        try:
            from core.managers.effects_state import campaign_effects_migrated

            if not campaign_effects_migrated():
                return create_return(
                    status="error",
                    response_data={
                        "error_message": (
                            "removeEffect is available after the campaign's "
                            "temporary-effect conversion completes."
                        )
                    },
                )
            from core.managers.effects_runtime import remove_effect

            character_name = parameters.get("characterName")
            if not character_name:
                return create_return(
                    status="error",
                    response_data={"error_message": "removeEffect requires characterName."},
                )
            remove_effect(
                character_name,
                effect_id=parameters.get("effectId"),
                name=parameters.get("effectName"),
                reason=parameters.get("reason") or "removed",
            )
            return create_return(needs_update=True)
        except Exception as exc:
            error("FAILURE: removeEffect failed safely", exception=exc, category="effects_tracking")
            return create_return(
                status="error",
                response_data={"error_message": "The requested effect could not be removed safely."},
            )
        finally:
            try:
                from core.managers.status_manager import status_ready
                status_ready()
            except Exception:
                pass


    elif action_type == ACTION_UPDATE_PARTY_NPCS:
        operation = parameters["operation"]
        npc = parameters["npc"]
        # Capture the roster before the commit so we can tell whether this action
        # actually changed state (idempotent duplicate add / no-op remove must not
        # trigger a lifecycle hook or a conversation-history refresh).
        _roster_before = [
            dict(x) for x in party_tracker_data.get("partyNPCs", [])
        ]
        update_party_npcs(party_tracker_data, operation, npc)
        _roster_after = party_tracker_data.get("partyNPCs", [])
        _state_changed = _roster_after != _roster_before
        # T105: best-effort NPC-voice lifecycle hook after the roster commit.
        # Only fires when the roster actually changed (idempotent duplicate add /
        # no-op remove is a true no-op). Always live and fail-open; it must never break
        # the committed roster action.
        if _state_changed:
            needs_conversation_history_update = True
            try:
                lifecycle_context = parameters.get("lifecycleContext")
                source_turn_id = str(
                    getattr(invocation_claim, "logical_invocation_id", "") or ""
                ).strip()
                if not source_turn_id:
                    warning(
                        "T105 NPC lifecycle hook skipped after roster commit: "
                        "the accepted turn has no logical invocation identity",
                        category="character_updates",
                    )
                else:
                    npc_name = str(npc.get("name") or "")
                    npc_file = ""
                    try:
                        _lc_module = party_tracker_data.get("module", "").replace(" ", "_")
                        _lc_pm = ModulePathManager(_lc_module)
                        from updates.update_character_info import (
                            find_character_file_fuzzy,
                            normalize_character_name,
                        )
                        _matched = find_character_file_fuzzy(npc_name)
                        if _matched:
                            npc_file = _lc_pm.get_character_path(_matched)
                        else:
                            npc_file = _lc_pm.get_character_path(
                                normalize_character_name(npc_name)
                            )
                    except Exception:
                        npc_file = ""
                    _apply_party_npc_lifecycle(
                        party_tracker_data,
                        operation,
                        npc_name,
                        npc_file,
                        lifecycle_context,
                        source_turn_id,
                    )
            except Exception as exc:
                warning(
                    "T105 NPC lifecycle hook raised after roster commit: %s: %s"
                    % (type(exc).__name__, str(exc)),
                    category="character_updates",
                )

    elif action_type == ACTION_UPDATE_ENCOUNTER:
        debug("STATE_CHANGE: Processing updateEncounter action", category="combat_processing")
        encounter_id = parameters.get("encounterId")
        changes = parameters.get("changes")
        
        if encounter_id and changes:
            try:
                # Import the update_encounter function
                from updates.update_encounter import update_encounter
                
                # Update the encounter
                encounter_updated, updated_encounter = update_encounter(
                    encounter_id, changes
                )
                
                if encounter_updated:
                    info(f"SUCCESS: Encounter {encounter_id} updated successfully", category="combat_processing")
                    needs_conversation_history_update = True
                else:
                    print(f"ERROR: Failed to update encounter {encounter_id}")
            except Exception as e:
                print(f"ERROR: Exception while updating encounter: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            print(f"ERROR: Missing required parameters for updateEncounter. encounterId: {encounter_id}, changes: {changes}")

    elif action_type == ACTION_CREATE_NEW_MODULE:
        debug("STATE_CHANGE: Processing createNewModule action", category="module_management")

        # Allocate before any optional module imports so even import/contract
        # failures have one correlated terminal payload. Reuse an already
        # active usage identity when this action is nested in its build scope.
        build_id = str(uuid4())
        try:
            from utils.openai_usage_tracker import (
                get_module_build_usage_context,
            )

            active_build_context = get_module_build_usage_context()
            if active_build_context is not None:
                build_id = str(active_build_context.build_id)
        except Exception:
            # The fallback UUID still correlates progress if usage tracking is
            # unavailable; the later protected import owns the safe failure.
            pass
        progress_lock = threading.Lock()
        progress_state = {
            "last_stage": -1,
            "last_percentage": -1,
            "total_stages": 9,
            "terminal_emitted": False,
        }

        def _bounded_progress_int(value, default, minimum, maximum):
            if isinstance(value, bool):
                value = default
            try:
                value = int(value)
            except (TypeError, ValueError, OverflowError):
                value = default
            return max(minimum, min(maximum, value))

        def _progress_text(value, default):
            if not isinstance(value, str) or not value.strip():
                return default
            return value.strip()[:500]

        def _queue_module_progress(payload):
            try:
                from web.shared_state import module_progress_queue

                module_progress_queue.put(payload)
                debug(
                    "MODULE_PROGRESS: Queued for web - Stage "
                    f"{payload.get('stage')}/{payload.get('total_stages')} - "
                    f"{payload.get('message')}",
                    category="module_management",
                )
            except ImportError:
                debug(
                    f"MODULE_PROGRESS: {payload.get('message')}",
                    category="module_management",
                )
            except Exception as progress_error:
                warning(
                    f"Could not queue module progress: {progress_error}",
                    category="module_management",
                )

        def module_progress_callback(progress_data):
            """Coerce child callbacks into one monotonic running envelope."""
            if not isinstance(progress_data, dict):
                return False
            with progress_lock:
                if progress_state["terminal_emitted"]:
                    return False
                total_stages = _bounded_progress_int(
                    progress_data.get("total_stages"),
                    progress_state["total_stages"],
                    1,
                    99,
                )
                stage = _bounded_progress_int(
                    progress_data.get("stage"),
                    progress_state["last_stage"] + 1,
                    0,
                    total_stages,
                )
                total_stages = max(
                    progress_state["total_stages"], total_stages, stage
                )
                percentage = _bounded_progress_int(
                    progress_data.get("percentage"),
                    max(0, progress_state["last_percentage"]),
                    0,
                    99,
                )
                if (
                    stage < progress_state["last_stage"]
                    or percentage < progress_state["last_percentage"]
                ):
                    return False
                if (
                    stage == progress_state["last_stage"]
                    and percentage == progress_state["last_percentage"]
                ):
                    return False
                progress_state["last_stage"] = stage
                progress_state["last_percentage"] = percentage
                progress_state["total_stages"] = total_stages
                payload = {
                    "build_id": build_id,
                    "stage": stage,
                    "total_stages": total_stages,
                    "stage_name": _progress_text(
                        progress_data.get("stage_name"), "Processing"
                    ),
                    "percentage": percentage,
                    "message": _progress_text(
                        progress_data.get("message"), "Working..."
                    ),
                    "status": "running",
                    "terminal": False,
                }
                # Keep queue order within the same lock that linearizes stage
                # state so a terminal can never overtake accepted progress.
                _queue_module_progress(payload)
                return True

        def terminal_progress(status, message, module_name=None):
            terminal_status = (
                status
                if status in {"published", "generated", "failed"}
                else "failed"
            )
            with progress_lock:
                if progress_state["terminal_emitted"]:
                    return False
                progress_state["terminal_emitted"] = True
                total_stages = max(progress_state["total_stages"], 9)
                payload = {
                    "build_id": build_id,
                    "stage": total_stages,
                    "total_stages": total_stages,
                    "stage_name": {
                        "published": "Published",
                        "generated": "Generated",
                        "failed": "Failed",
                    }[terminal_status],
                    "percentage": 100,
                    "message": _progress_text(
                        message,
                        "Module creation finished.",
                    ),
                    "status": terminal_status,
                    "terminal": True,
                    "success": terminal_status in {"published", "generated"},
                }
                if isinstance(module_name, str) and module_name.strip():
                    payload["module_name"] = module_name.strip()[:200]
                _queue_module_progress(payload)
                return True

        def module_failure(**kwargs):
            failure = _module_creation_error_result(**kwargs)
            failure["build_id"] = build_id
            failure["response_data"]["build_id"] = build_id
            return failure

        def published_result(module_name):
            dm_note = (
                "Dungeon Master Note: New module "
                f"'{module_name}' has been successfully created and integrated "
                "into the world. Provide a useful player-facing transition "
                "narration and return no actions."
            )
            # P2b: atomic publish replaces the receipt subsystem. The module is
            # already live; always ask the DM to narrate its creation
            # (needs_dm_response). A crash before narration leaves the module live
            # with no narration shown (cosmetic, fail-forward) -- there is no
            # cross-turn dedup, so a later recreate yields a harmless spare module.
            return {
                "status": "published",
                "success": True,
                "build_id": build_id,
                "state_changed": True,
                "retryable": False,
                "needs_update": True,
                "needs_dm_response": True,
                "response_data": {
                    "build_id": build_id,
                    "module_name": module_name,
                    "dm_note": dm_note,
                },
            }

        # Establish the active build in the reducer before any optional import,
        # contract check, or lock attempt can fail and emit its terminal event.
        module_progress_callback(
            {
                "stage": 0,
                "total_stages": 9,
                "stage_name": "Initializing",
                "percentage": 0,
                "message": "Starting module creation...",
            }
        )

        try:
            from core.ai.module_creation_contract import (
                ModuleCreationContractError,
                validate_create_new_module_action,
            )
            from core.generators.module_builder import (
                ModuleCreationCancelledError,
                ModuleCreationFailedError,
                ai_driven_module_creation,
            )
            from core.generators.module_stitcher import get_module_stitcher
            from utils.openai_usage_tracker import (
                mark_module_build_outcome,
                module_build_usage_scope,
            )
            # Build + publish are one atomic unit: the module is built in a
            # hidden temp workspace and swapped into modules/ in a single rename,
            # so a failure never leaves a half-built module live (fail-forward).
            from utils.module_refresh_lock import module_refresh_lock

            with module_build_usage_scope(build_id=build_id) as build_context:
                build_id = str(build_context.build_id)
                try:
                    validate_create_new_module_action(action)
                except ModuleCreationContractError:
                    mark_module_build_outcome("contract_rejected")
                    failure = module_failure()
                    terminal_progress(
                        "failed", failure["response_data"]["error_message"]
                    )
                    return failure

                with module_refresh_lock() as publication_acquired:
                    if not publication_acquired:
                        mark_module_build_outcome("lock_unavailable")
                        failure = module_failure(
                            message=(
                                "Module creation is busy; no game state was "
                                "changed. Please retry shortly."
                            )
                        )
                        terminal_progress(
                            "failed", failure["response_data"]["error_message"]
                        )
                        return failure

                    # No cross-turn idempotency dedup: a createNewModule may carry
                    # only a narrative (no module_name), and the allocated final
                    # name may differ, so nothing can reliably match a retry to a
                    # prior build. A crash-then-recreate yields a harmless SPARE
                    # module the player can delete -- fail-forward, never a broken
                    # or corrupted game. No prior in-flight state ever BLOCKS a
                    # new build.
                    stitcher = get_module_stitcher()
                    try:
                        # Builds into a hidden temp workspace and atomically swaps
                        # the module into modules/<name> in one rename, updating
                        # the advisory registry via the store-free helper. A
                        # failure here NEVER touches live state -- the build simply
                        # did not happen and the player keeps playing.
                        success, module_name = ai_driven_module_creation(
                            parameters,
                            progress_callback=module_progress_callback,
                            policy="game",
                            prepare_candidate=(
                                stitcher.build_publication_registry_bytes
                            ),
                        )
                    except ModuleCreationCancelledError:
                        mark_module_build_outcome("not_generated")
                        failure = module_failure()
                        terminal_progress(
                            "failed", failure["response_data"]["error_message"]
                        )
                        return failure
                    except ModuleCreationFailedError as build_error:
                        # The build reports its reason instead of returning a bare
                        # failure (issue #130). Log the detail, but keep the
                        # player-facing message sanitized: provider output must
                        # not leak into the DM conversation.
                        error(
                            f"Module creation failed: {build_error}",
                            exception=build_error,
                            category="module_creation",
                        )
                        mark_module_build_outcome("not_generated")
                        failure = module_failure()
                        terminal_progress(
                            "failed", failure["response_data"]["error_message"]
                        )
                        return failure

                    if not success or not module_name:
                        mark_module_build_outcome("not_generated")
                        failure = module_failure()
                        terminal_progress(
                            "failed", failure["response_data"]["error_message"]
                        )
                        return failure

                    mark_module_build_outcome("published")
                    terminal_progress(
                        "published",
                        f"Module {module_name} was published successfully.",
                        module_name,
                    )
                    info(
                        f"SUCCESS: Module '{module_name}' created and published",
                        category="module_management",
                    )
                    needs_conversation_history_update = True
                    return published_result(module_name)
        except Exception as module_error:
            error(
                "FAILURE: Unexpected module creation pipeline error",
                exception=module_error,
                category="module_management",
            )
            failure = module_failure(recovery_required=True)
            terminal_progress(
                "failed", failure["response_data"]["error_message"]
            )
            return failure
        finally:
            try:
                from core.managers.status_manager import status_ready

                status_ready()
                debug(
                    "STATE_CHANGE: Status reset after module creation",
                    category="session_management",
                )
            except Exception:
                pass

    elif action_type == ACTION_ESTABLISH_HUB:
        debug("STATE_CHANGE: Processing establishHub action", category="module_management")
        try:
            # Extract hub parameters
            hub_name = parameters.get('hubName')
            hub_type = parameters.get('hubType', 'settlement')
            description = parameters.get('description', '')
            services = parameters.get('services', [])
            ownership = parameters.get('ownership', 'party')
            
            if hub_name:
                # Import campaign manager
                from core.managers.campaign_manager import CampaignManager
                campaign_manager = CampaignManager()
                
                # Establish the hub
                hub_data = {
                    "hubType": hub_type,
                    "description": description, 
                    "services": services,
                    "ownership": ownership
                }
                
                campaign_manager.establish_hub(hub_name, hub_data)
                
                info(f"SUCCESS: Hub '{hub_name}' established successfully", category="module_management")
                
                # Add DM note about hub establishment
                dm_note = f"Dungeon Master Note: '{hub_name}' has been established as a hub location. The party can now return here from other adventures."
                conversation_history.append({"role": "user", "content": dm_note})
                
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Missing required parameter 'hubName' for establishHub action")
                
        except Exception as e:
            print(f"ERROR: Exception while establishing hub: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_STORAGE_INTERACTION:
        debug("STATE_CHANGE: Processing storageInteraction action", category="storage_operations")
        try:
            # Import storage modules
            from core.managers.storage_processor import process_storage_request
            from core.managers.storage_manager import execute_storage_operation
            
            # Get storage description from parameters
            storage_description = parameters.get("description", "")
            character_name = parameters.get("characterName", "")
            
            # Fallback to party member if no character specified
            if not character_name:
                character_name = next((member for member in party_tracker_data["partyMembers"]), None)
                
            if not character_name:
                print(f"ERROR: No character name provided for storage interaction")
                return create_return(status="continue", needs_update=False)
                
            if not storage_description:
                print(f"ERROR: No storage description provided")
                return create_return(status="continue", needs_update=False)
                
            debug(f"AI_CALL: Processing storage request for {character_name}: '{storage_description}'", category="storage_operations")
            
            # Process natural language description into operation
            processor_result = process_storage_request(storage_description, character_name)
            
            if not processor_result.get("success"):
                print(f"ERROR: Storage processor failed: {processor_result.get('error')}")
                
                # Add error message to conversation
                error_message = f"Storage Error: {processor_result.get('error', 'Unknown error processing storage request')}"
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                return create_return(status="needs_response", needs_update=True)
                
            # Execute the validated storage operation
            operation = processor_result["operation"]
            debug(f"STATE_CHANGE: Executing storage operation: {operation}", category="storage_operations")
            
            execution_result = execute_storage_operation(operation)
            
            if execution_result.get("success"):
                info(f"SUCCESS: Storage operation successful: {execution_result.get('message')}", category="storage_operations")
                
                # Add success message to conversation
                success_message = f"Storage: {execution_result.get('message')}"
                conversation_history.append({"role": "user", "content": success_message})
                needs_conversation_history_update = True
                
            else:
                print(f"ERROR: Storage operation failed: {execution_result.get('error')}")
                
                # Add error message to conversation
                error_message = f"Storage Error: {execution_result.get('error', 'Unknown error executing storage operation')}"
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing storage interaction: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Add error message to conversation
            error_message = f"Storage System Error: An unexpected error occurred while processing your storage request."
            conversation_history.append({"role": "user", "content": error_message})
            needs_conversation_history_update = True

    elif action_type == ACTION_UPDATE_PARTY_TRACKER:
        debug("STATE_CHANGE: Processing updatePartyTracker action", category="party_management")
        try:
            # Load current party tracker
            current_party_data = safe_json_load("party_tracker.json")
            if not current_party_data:
                current_party_data = party_tracker_data.copy() if party_tracker_data else {}
            
            current_module = current_party_data.get("module", "Unknown")
            
            # Check if module is being changed
            new_module = parameters.get("module")
            if new_module and new_module != current_module:
                print(f"DEBUG: [Module Transition] Module change detected: {current_module} -> {new_module}")
                print(f"DEBUG: [Party Tracker Before Update] Module: {current_party_data.get('module', 'Unknown')}")
                info(f"STATE_CHANGE: Module change detected: {current_module} -> {new_module}", category="module_management")
                
                # Insert module transition marker immediately when module change is detected
                transition_text = f"Module transition: {current_module} to {new_module}"
                transition_message = {
                    "role": "user",
                    "content": transition_text
                }
                transition_history = list(conversation_history)
                transition_history.append(transition_message)
                print(f"DEBUG: [Module Transition] Inserted transition marker: '{transition_text}'")
                debug(f"STATE_CHANGE: Inserted module transition marker: '{transition_text}'", category="module_management")
                
                # Import campaign manager for auto-archiving
                from core.managers.campaign_manager import CampaignManager
                from main import save_conversation_history
                campaign_manager = CampaignManager()
                
                # DELAYED ARCHIVING: Don't archive immediately, set a flag instead
                # This allows the travel narrative to be added to conversation history first
                if current_module != "Unknown":
                    print(f"DEBUG: [Module Transition] Setting pending archive flag for module: {current_module}")
                    info(f"STATE_CHANGE: Module transition detected - archiving will occur after travel narrative", category="module_management")
                    
                    # Store the pending archive info in the return result
                    pending_archive = {
                        "from_module": current_module,
                        "to_module": new_module,
                        "party_tracker_data": current_party_data.copy(),
                        # The appended transition marker makes this stable for
                        # duplicate workers while later visits naturally hash
                        # a longer/different history.
                        "completion_id": _module_transition_completion_id(
                            current_module,
                            new_module,
                            transition_history,
                        ),
                    }
                    # Inject accumulated campaign context for the new module
                    debug(f"AI_CALL: Requesting campaign context for module: {new_module}", category="module_management")
                    campaign_context = campaign_manager.get_accumulated_summaries_context(new_module)
                    debug(f"AI_CALL: Campaign context received - Length: {len(campaign_context) if campaign_context else 0} characters", category="module_management")
                    if campaign_context:
                        transition_history.append({
                            "role": "system", 
                            "content": f"=== CAMPAIGN CONTEXT ===\n{campaign_context}"
                        })
                        info(f"SUCCESS: Campaign context prepared for {new_module}", category="module_management")
                    else:
                        warning(f"STATE_CHANGE: No campaign context to inject for {new_module} - context was empty", category="module_management")
                
                # A usable destination requires both real IDs. Models may emit
                # the full field shape with empty strings; treating those keys
                # as "provided" publishes a module with a blank world
                # projection and strands the player at "()" in the web UI.
                destination_area_id = str(
                    parameters.get("currentAreaId") or ""
                ).strip()
                destination_location_id = str(
                    parameters.get("currentLocationId") or ""
                ).strip()
                if not destination_area_id or not destination_location_id:
                    try:
                        location_id, location_name, area_id, area_name = get_module_starting_location(new_module)
                        info(f"STATE_CHANGE: Auto-setting starting location for {new_module}: {location_name} [{location_id}] in {area_name} [{area_id}]", category="module_management")
                        
                        # Add starting location to parameters for processing below
                        parameters["currentLocationId"] = location_id
                        parameters["currentLocation"] = location_name
                        parameters["currentAreaId"] = area_id
                        parameters["currentArea"] = area_name
                    except Exception as e:
                        print(f"WARNING: Could not auto-set starting location for {new_module}: {e}")
            
            # Update party tracker with all provided parameters
            for key, value in parameters.items():
                if key in ["currentLocationId", "currentLocation", "currentAreaId", "currentArea"]:
                    if "worldConditions" not in current_party_data:
                        current_party_data["worldConditions"] = {}
                    current_party_data["worldConditions"][key] = value
                elif key == "module":
                    current_party_data["module"] = value
                else:
                    # Handle any other party tracker fields
                    current_party_data[key] = value
            
            # Publish cross-module state under one fresh party transaction so
            # competing stale workers cannot both ready different intents.
            if (
                new_module
                and new_module != current_module
                and current_module != "Unknown"
            ):
                original_party, current_party_data = (
                    campaign_manager.publish_party_module_transition(
                        current_module,
                        new_module,
                        parameters,
                        transition_history,
                        pending_archive["completion_id"],
                    )
                )
                pending_archive["party_tracker_data"] = original_party
            else:
                safe_json_dump(current_party_data, "party_tracker.json")
            if new_module and new_module != current_module:
                conversation_history[:] = transition_history
                save_conversation_history(
                    conversation_history,
                    strict=True,
                    allow_compression=False,
                )
            print(f"DEBUG: [Party Tracker After Update] Module: {current_party_data.get('module', 'Unknown')}")
            info("SUCCESS: Party tracker updated successfully", category="party_management")
            # Always reload conversation history to pick up changes
            needs_conversation_history_update = True
            
            # If we set a pending archive flag, include it in the return
            if new_module and new_module != current_module and current_module != "Unknown":
                print(f"DEBUG: [Module Transition] Returning with pending_archive flag")
                return create_return(
                    needs_update=needs_conversation_history_update,
                    response_data={"pending_archive": pending_archive}
                )
            
        except Exception as e:
            print(f"ERROR: Exception while updating party tracker: {str(e)}")
            import traceback
            traceback.print_exc()
            response_data = {"error_message": str(e)}
            if (
                "pending_archive" in locals()
                and "campaign_manager" in locals()
            ):
                publication_state = _completion_publication_state(
                    campaign_manager,
                    pending_archive,
                )
                response_data["pending_archive"] = pending_archive
                response_data["completion_publication_state"] = (
                    publication_state
                )
                response_data["transition_recovery_required"] = (
                    publication_state != "absent"
                )
            return create_return(
                status="error",
                needs_update=True,
                response_data=response_data,
            )

    elif action_type == ACTION_MOVE_BACKGROUND_NPC:
        debug("STATE_CHANGE: Processing moveBackgroundNPC action", category="npc_management")
        try:
            # Extract parameters
            npc_name = parameters.get("npcName")
            context = parameters.get("context", "")
            current_location = parameters.get("currentLocation")
            
            if not npc_name:
                print(f"ERROR: Missing required parameter 'npcName' for moveBackgroundNPC action")
                return create_return(status="continue", needs_update=False)
            
            # Process the NPC movement
            success = move_background_npc(npc_name, context, current_location, party_tracker_data)
            
            if success:
                info(f"SUCCESS: Processed movement for NPC: {npc_name}", category="npc_management")
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Failed to process movement for NPC: {npc_name}")
                
        except Exception as e:
            print(f"ERROR: Exception while processing moveBackgroundNPC: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_SAVE_GAME:
        debug("STATE_CHANGE: Processing save game action", category="save_game")
        try:
            from updates.save_game_manager import SaveGameManager
            
            # Extract parameters
            description = parameters.get("description", "")
            save_mode = parameters.get("saveMode", "essential")  # "essential" or "full"
            
            # Create save game
            manager = SaveGameManager()
            success, message = manager.create_save_game(description, save_mode)
            
            if success:
                info(f"SUCCESS: Save game created: {message}", category="save_game")
                # Add success message to conversation
                save_message = f"Game saved successfully! {message}"
                conversation_history.append({"role": "system", "content": save_message})
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Failed to save game: {message}")
                # Add error message to conversation  
                error_message = f"Failed to save game: {message}"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing saveGame: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_RESTORE_GAME:
        debug("STATE_CHANGE: Processing restore game action", category="save_game")
        try:
            from updates.save_game_manager import SaveGameManager
            
            # Extract parameters
            save_folder = parameters.get("saveFolder")
            
            if not save_folder:
                print("ERROR: Missing required parameter 'saveFolder' for restoreGame action")
                error_message = "Error: No save folder specified for restore operation"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                return create_return(needs_update=needs_conversation_history_update)
            
            # Restore save game
            manager = SaveGameManager()
            success, message = manager.restore_save_game(save_folder)
            
            if success:
                info(f"SUCCESS: Save game restored: {message}", category="save_game")
                # Add success message to conversation
                restore_message = f"Game restored successfully! {message}\nRestarting game session..."
                conversation_history.append({"role": "system", "content": restore_message})
                needs_conversation_history_update = True
                # Return special status to indicate game should restart
                return create_return(status="restart", needs_update=needs_conversation_history_update)
            else:
                print(f"ERROR: Failed to restore game: {message}")
                # Add error message to conversation
                error_message = f"Failed to restore game: {message}"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing restoreGame: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_LIST_SAVES:
        debug("STATE_CHANGE: Processing list saves action", category="save_game")
        try:
            from updates.save_game_manager import SaveGameManager
            
            # Get list of save games
            manager = SaveGameManager()
            saves = manager.list_save_games()
            
            if saves:
                save_list_text = "Available save games:\n"
                for i, save in enumerate(saves, 1):
                    save_date = save.get("save_date_readable", "Unknown date")
                    description = save.get("description", "No description")
                    save_mode = save.get("save_mode", "unknown")
                    module = save.get("module", "Unknown")
                    save_folder = save.get("save_folder", "Unknown")
                    
                    save_list_text += f"{i}. {save_folder}\n"
                    save_list_text += f"   Date: {save_date}\n"
                    save_list_text += f"   Module: {module}\n"
                    save_list_text += f"   Mode: {save_mode}\n"
                    save_list_text += f"   Description: {description}\n\n"
            else:
                save_list_text = "No save games found."
            
            debug(f"VALIDATION: Found {len(saves)} save games", category="save_game")
            conversation_history.append({"role": "system", "content": save_list_text})
            needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing listSaves: {str(e)}")
            import traceback
            traceback.print_exc()

    elif action_type == ACTION_DELETE_SAVE:
        debug("STATE_CHANGE: Processing delete save action", category="save_game")
        try:
            from updates.save_game_manager import SaveGameManager
            
            # Extract parameters
            save_folder = parameters.get("saveFolder")
            
            if not save_folder:
                print("ERROR: Missing required parameter 'saveFolder' for deleteSave action")
                error_message = "Error: No save folder specified for delete operation"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                return create_return(needs_update=needs_conversation_history_update)
            
            # Delete save game
            manager = SaveGameManager()
            success, message = manager.delete_save_game(save_folder)
            
            if success:
                info(f"SUCCESS: Save game deleted: {message}", category="save_game")
                conversation_history.append({"role": "system", "content": message})
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Failed to delete save game: {message}")
                conversation_history.append({"role": "system", "content": f"Error: {message}"})
                needs_conversation_history_update = True
                
        except Exception as e:
            print(f"ERROR: Exception while processing deleteSave: {str(e)}")
            import traceback
            traceback.print_exc()

    else:
        print(f"WARNING: Unknown action type: {action_type}")
    
    return create_return(needs_update=needs_conversation_history_update)

def move_background_npc(npc_name, context, current_location_hint=None, party_tracker_data=None):
    """
    AI-driven function to handle NPC movement/status changes with atomic safety
    
    Args:
        npc_name (str): Name of the NPC to move/update
        context (str): Narrative context explaining what happened to the NPC
        current_location_hint (str, optional): Hint about current location if not found automatically
        party_tracker_data (dict, optional): Party tracker data for module context
        
    Returns:
        bool: True if successful, False otherwise
    """
    import json
    import copy
    import shutil
    import os
    import time
    from datetime import datetime
    from utils.file_operations import safe_write_json, safe_read_json
    
    debug(f"STATE_CHANGE: moveBackgroundNPC called for {npc_name}", category="npc_management")
    debug(f"AI_CALL: Context: {context}", category="npc_management")
    
    if not party_tracker_data:
        party_tracker_data = safe_read_json("party_tracker.json")
        if not party_tracker_data:
            print("ERROR: Could not load party tracker data")
            return False

    module_name = party_tracker_data.get("module", "").replace(" ", "_")
    if not module_name:
        print("ERROR: No current module found in party tracker")
        return False

    # The complete read -> AI decision -> mutate -> write sequence is one
    # transaction.  A lock created inside this function cannot protect two
    # invocations, so share a re-entrant lock by module instead.
    from contextlib import ExitStack
    from utils.module_refresh_lock import module_refresh_lock

    with ExitStack() as movement_locks:
        refresh_acquired = movement_locks.enter_context(module_refresh_lock())
        if not refresh_acquired:
            warning(
                "Background NPC movement deferred while modules are refreshing",
                category="npc_management",
            )
            return False
        movement_locks.enter_context(_npc_movement_lock(module_name))
        try:
            path_manager = ModulePathManager(module_name)
            
            # Find the NPC in area files
            npc_location = find_npc_in_areas(npc_name, path_manager, current_location_hint)
            if not npc_location:
                print(f"ERROR: Could not find NPC '{npc_name}' in any location")
                return False
                
            area_file, location_id, npc_data = npc_location
            debug(f"VALIDATION: Found {npc_name} in {area_file} at location {location_id}", category="npc_management")
            
            # Load area data with backup
            area_data = safe_read_json(area_file)
            if not area_data:
                print(f"ERROR: Could not load area data from {area_file}")
                return False
                
            # Create backup
            backup_path = create_area_backup(area_file)
            if not backup_path:
                print("WARNING: Could not create backup, proceeding anyway")
            
            # Get party NPCs for validation
            party_npcs = party_tracker_data.get("partyNPCs", [])
            
            # Retry loop with fallback system
            ai_decision = None
            max_attempts = 5
            
            for attempt in range(1, max_attempts + 1):
                debug(f"AI_CALL: AI decision attempt {attempt}/{max_attempts}", category="npc_management")
                
                # Get AI decision on what to do with the NPC
                ai_decision = get_ai_npc_movement_decision(
                    npc_name, context, npc_data, area_data, location_id, module_name, party_npcs, attempt
                )
                
                if ai_decision:
                    # Validate the AI decision
                    validation_result = validate_npc_movement_decision(ai_decision, area_data, location_id, party_npcs)
                    if validation_result["valid"]:
                        info(f"SUCCESS: AI decision validated on attempt {attempt}", category="npc_management")
                        break
                    else:
                        warning(f"VALIDATION: AI decision failed on attempt {attempt}: {validation_result['reason']}", category="npc_management")
                        if attempt == max_attempts:
                            print("ERROR: Max attempts reached, AI could not generate valid decision")
                            return False
                        else:
                            # Add validation feedback to context for retry
                            context += f"\n\nPREVIOUS ATTEMPT FAILED: {validation_result['reason']}"
                else:
                    error(f"FAILURE: AI could not generate decision on attempt {attempt}", category="npc_management")
                    if attempt == max_attempts:
                        print("ERROR: Max attempts reached, AI could not determine appropriate action")
                        return False
            
            if not ai_decision:
                print("ERROR: AI could not determine appropriate action after all attempts")
                return False
                
            info(f"AI_CALL: Final AI decision: {ai_decision.get('action')} - {ai_decision.get('reasoning', 'No reasoning')}", category="npc_management")
            
            # Execute the AI decision with surgical updates
            success = execute_npc_movement_decision(ai_decision, area_data, location_id, npc_name, path_manager)
            
            if success:
                # Save updated area data
                if safe_write_json(area_file, area_data):
                    info(f"SUCCESS: Updated area file {area_file}", category="file_operations")
                    # Clean up old backups
                    cleanup_old_area_backups(area_file)
                    return True
                else:
                    print(f"ERROR: Failed to save updated area data")
                    # Restore from backup if save failed
                    if backup_path and os.path.exists(backup_path):
                        try:
                            shutil.copy2(backup_path, area_file)
                            warning("FILE_OP: Restored area file from backup due to save failure", category="file_operations")
                        except Exception as e:
                            print(f"ERROR: Could not restore from backup: {e}")
                    return False
            else:
                print("ERROR: Failed to execute NPC movement decision")
                return False
                
        except Exception as e:
            print(f"ERROR: Exception in move_background_npc: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def prepare_background_npc_movement(
    npc_name, context, current_location_hint=None, party_tracker_data=None
):
    """Freeze one required T014 decision and its exact area mutation."""
    from utils.module_refresh_lock import module_refresh_lock

    party = party_tracker_data or safe_json_load("party_tracker.json")
    module_name = str((party or {}).get("module", "")).replace(" ", "_")
    if not module_name:
        raise RuntimeError("No current module for moveBackgroundNPC")
    path_manager = ModulePathManager(module_name)
    with module_refresh_lock() as acquired:
        if not acquired:
            raise RuntimeError("module refresh is busy")
        with _npc_movement_lock(module_name):
            found = find_npc_in_areas(
                npc_name, path_manager, current_location_hint
            )
            if not found:
                raise ValueError("referenced background NPC does not exist")
            area_file, location_id, npc_data = found
            area_before = safe_json_load(area_file)
    correction = context
    attempt = 1
    while True:
        decision = get_ai_npc_movement_decision(
            npc_name,
            correction,
            npc_data,
            area_before,
            location_id,
            module_name,
            (party or {}).get("partyNPCs", []),
            attempt,
        )
        validation = validate_npc_movement_decision(
            decision, area_before, location_id, (party or {}).get("partyNPCs", [])
        )
        if validation["valid"]:
            break
        correction = "%s\n\nCorrection facts: %s" % (
            context,
            validation["reason"],
        )
        attempt += 1
    return {
        "kind": "moveBackgroundNPC",
        "module": module_name,
        "area_path": area_file,
        "location_id": location_id,
        "npc_name": npc_name,
        "proposal": decision,
        # The semantic decision is frozen before movement. Its exact file
        # values are materialized only after earlier travel stages finish, so
        # the departure summary cannot become a false whole-area conflict.
        "before": None,
        "after": None,
    }


def materialize_staged_background_npc_movement(receipt):
    """Freeze T014's exact post-departure area values before its first write."""
    import copy
    from utils.module_refresh_lock import module_refresh_lock

    if receipt.get("before") is not None:
        return receipt
    with module_refresh_lock() as acquired:
        if not acquired:
            raise RuntimeError("module refresh is busy")
        with _npc_movement_lock(receipt["module"]):
            current = safe_json_load(receipt["area_path"])
            if not isinstance(current, dict):
                raise RuntimeError("background NPC area is unavailable")
            after = copy.deepcopy(current)
            path_manager = ModulePathManager(receipt["module"])
            if not execute_npc_movement_decision(
                receipt["proposal"],
                after,
                receipt["location_id"],
                receipt["npc_name"],
                path_manager,
            ):
                raise RuntimeError(
                    "accepted background NPC proposal no longer matches current state"
                )
            receipt["before"] = current
            receipt["after"] = after
    return receipt


def apply_staged_background_npc_movement(receipt):
    """Apply or recognize one frozen T014 area value."""
    from utils.module_refresh_lock import module_refresh_lock

    with module_refresh_lock() as acquired:
        if not acquired:
            raise RuntimeError("module refresh is busy")
        with _npc_movement_lock(receipt["module"]):
            current = safe_json_load(receipt["area_path"])
            if current == receipt["after"]:
                return "already_committed"
            if current != receipt["before"]:
                return "blocked_conflict"
            if not safe_write_json(receipt["area_path"], receipt["after"]):
                raise RuntimeError("background NPC area write failed")
    return "committed"

def find_npc_in_areas(npc_name, path_manager, location_hint=None):
    """Find an NPC in area files, returning (area_file, location_id, npc_data)"""
    import glob
    import os
    from utils.file_operations import safe_read_json
    
    # Get all area files in the module, excluding backup files
    area_pattern = f"{path_manager.module_dir}/areas/*.json"
    all_files = glob.glob(area_pattern)
    
    # Filter out backup files (_BU.json) and backup copies (.backup_*)
    area_files = []
    for file_path in all_files:
        filename = os.path.basename(file_path)
        # Skip backup files
        if filename.endswith('_BU.json') or '.backup_' in filename:
            debug(f"FILE_OP: Skipping backup file: {filename}", category="file_operations")
            continue
        area_files.append(file_path)
    
    debug(f"FILE_OP: Searching {len(area_files)} active area files (excluded {len(all_files) - len(area_files)} backup files)", category="file_operations")
    
    for area_file in area_files:
        try:
            area_data = safe_read_json(area_file)
            if not area_data:
                continue
                
            # Search through all locations in this area
            for location in area_data.get("locations", []):
                location_id = location.get("locationId", "")
                
                # If location hint provided, check if this matches
                if location_hint and location_hint != location_id:
                    continue
                    
                # Search NPCs in this location
                for npc in location.get("npcs", []):
                    if npc.get("name", "").lower() == npc_name.lower():
                        return (area_file, location_id, npc)
                        
        except Exception as e:
            warning(f"FILE_OP: Could not search area file {area_file}: {e}", category="file_operations")
            continue
    
    return None

def get_ai_npc_movement_decision(npc_name, context, npc_data, area_data, location_id, module_name, party_npcs=None, attempt=1):
    """Use AI to determine what to do with the NPC based on context"""
    try:
        # Get available locations for potential moves
        available_locations = []
        for location in area_data.get("locations", []):
            loc_id = location.get("locationId", "")
            loc_name = location.get("name", "")
            if loc_id and loc_name and loc_id != location_id:
                available_locations.append(f"{loc_id} ({loc_name})")
        
        # Check if this is a party NPC vs background NPC
        party_npc_names = [npc.get("name", "").lower() for npc in (party_npcs or [])]
        is_party_npc = npc_name.lower() in party_npc_names
        
        # Load and validate against location schema
        from jsonschema import validate, ValidationError
        import json
        
        try:
            with open("schemas/loca_schema.json", "r") as f:
                location_schema = json.load(f)
        except Exception as e:
            warning(f"FILE_OP: Could not load location schema: {e}", category="file_operations")
            location_schema = None
        
        system_prompt = f"""You are an expert 5th edition narrative manager specialized in NPC movement and status changes. Your job is to make intelligent decisions about background NPCs based on narrative context while maintaining strict game world consistency.

CRITICAL DISTINCTIONS:
- BACKGROUND NPCs: NPCs found in location files who are not traveling with the party
- PARTY NPCs: NPCs actively traveling with and assisting the party (managed separately)
- This action is ONLY for BACKGROUND NPCs - NPCs who exist in specific locations

CURRENT NPC CLASSIFICATION:
- {npc_name} is {'a PARTY NPC (ERROR - use updatePartyNPCs instead)' if is_party_npc else 'a BACKGROUND NPC (correct for this action)'}

AVAILABLE ACTIONS FOR BACKGROUND NPCs:
1. "remove" - Remove NPC from location entirely
   - Use for: Captured and taken elsewhere, fled permanently, left the area
   - Result: NPC disappears from location, may add location description update
   
2. "update_status" - Keep NPC in location but change their description  
   - Use for: Death, injury, status change, but NPC remains in place
   - Result: NPC description updated, location may be updated too
   
3. "move" - Move NPC to different location within same area
   - Use for: NPC relocated to another nearby location
   - Result: NPC moves between locations, descriptions updated

SCHEMA VALIDATION REQUIREMENTS:
All NPC objects must maintain this exact structure:
{{
  "name": "string (required)",
  "description": "string (required)", 
  "attitude": "string (required)"
}}

CONTEXT INFORMATION:
- Module: {module_name}
- Current Location: {location_id}
- Available Target Locations: {', '.join(available_locations) if available_locations else 'None (cannot use move action)'}
- Attempt: {attempt}/5

RESPONSE FORMAT (JSON only):
{{
  "action": "remove|update_status|move",
  "reasoning": "Brief explanation of decision based on narrative context",
  "newDescription": "Updated NPC description if action is update_status (required field)",
  "newAttitude": "Updated attitude if action is update_status (required field)", 
  "newLocation": "Target location ID if action is move (must match available locations exactly)",
  "locationUpdate": "Addition to location description explaining change (optional)"
}}

DECISION GUIDELINES WITH EXAMPLES:

CAPTURE SCENARIO:
Context: "Rusk was captured by the party and taken to Thornwood"
Decision: "remove" - Rusk is no longer at this location
Reasoning: "Captured and removed from area by party"

DEATH SCENARIO:  
Context: "The merchant was killed by bandits"
Decision: "update_status" - Body remains in location
New Description: "The merchant's lifeless body lies sprawled among scattered goods..."
New Attitude: "Dead"
Location Update: "Signs of violence and blood stain the ground"

RELOCATION SCENARIO:
Context: "Elen went to report to the watchtower"  
Decision: "move" - IF watchtower location exists in available locations
New Location: "WT01" (only if this exact ID exists)
Reasoning: "Moved to fulfill duty obligations"

INJURY SCENARIO:
Context: "The guard was wounded but survived the attack"
Decision: "update_status" - Guard stays but is injured
New Description: "A wounded guard with bandaged arms, still determined despite recent injuries..."
New Attitude: "Cautious but resilient"

IMPORTANT VALIDATION RULES:
- NEVER move party NPCs (they travel with the party automatically)
- ONLY use exact location IDs from the available locations list
- ALWAYS provide required fields: newDescription and newAttitude for update_status
- Keep descriptions realistic and immersive
- Maintain narrative consistency with established world"""

        user_prompt = f"""Background NPC Movement Decision Request:

NPC Name: {npc_name}
Current Description: {npc_data.get('description', 'No description available')}
Current Attitude: {npc_data.get('attitude', 'No attitude specified')}
Narrative Context: {context}
Current Location: {location_id}

Based on this narrative context, determine the most appropriate action for this background NPC. Consider the story implications and choose the action that best maintains narrative consistency.

Remember: This is a background NPC management action, not party NPC management."""

        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            npc_config = config.NPC_INFO_GPT54MINI_NONE
        elif MODEL_PROVIDER == "gemini":
            # T014 uses its OWN gemini config (NPC_MOVEMENT_T014_*), NOT the shared
            # NPC_INFO_GEMINI_FLASH_LOW -- that one is shared with T091 whose
            # output is a JSON ARRAY; attaching this object schema there would corrupt
            # T091's monster reconciliation.
            npc_config = config.NPC_MOVEMENT_T014_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            npc_config = config.NPC_INFO_LMSTUDIO
        else:  # legacy
            npc_config = config.NPC_INFO_LEGACY

        # T014: fail loud (gemini-only) if response_schema is missing. Without it,
        # gemini-flash emits narration instead of the action/reasoning decision JSON
        # and the NPC update is silently dropped.
        if MODEL_PROVIDER == "gemini" and npc_config.get("response_schema") is None:
            raise RuntimeError(
                "T014 NPC movement decision aborted: Gemini response_schema is None. "
                "Refusing to run -- Gemini would emit narration and silently drop the "
                "NPC update."
            )

        response = capture_and_fanout("T014", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=npc_config["model"],
            temperature=0.3,  # MED-9 (#127): lower temp reduces JSON parse failures on NPC movement
            **{k: v for k, v in npc_config.items() if k != "model"})
        
        # Track token usage
        if USAGE_TRACKING_AVAILABLE:
            try:
                track_response(response)
            except:
                pass
        
        ai_response = response.choices[0].message.content.strip()
        debug(f"AI_CALL: Movement decision response: {ai_response}", category="ai_operations")
        
        # Parse the structured response directly. Gameplay meaning comes from
        # the typed fields, never a brace-shaped substring found in prose.
        if ai_response.startswith("```json"):
            ai_response = ai_response[len("```json") :]
        if ai_response.endswith("```"):
            ai_response = ai_response[: -len("```")]
        return json.loads(ai_response.strip())
            
    except Exception as e:
        error(f"AI_CALL: AI decision failed: {str(e)}", category="ai_operations")
        return None

def validate_npc_movement_decision(decision, area_data, location_id, party_npcs):
    """Validate AI decision against schema and game rules"""
    try:
        # Check required fields
        if not isinstance(decision, dict):
            return {"valid": False, "reason": "Decision must be a JSON object"}
            
        action = decision.get("action")
        if action not in ["remove", "update_status", "move"]:
            return {"valid": False, "reason": f"Invalid action '{action}'. Must be: remove, update_status, or move"}
        
        # Validate action-specific requirements
        if action == "update_status":
            if not decision.get("newDescription"):
                return {"valid": False, "reason": "update_status action requires newDescription field"}
            if not decision.get("newAttitude"):
                return {"valid": False, "reason": "update_status action requires newAttitude field"}
            
            if not isinstance(decision.get("newDescription"), str):
                return {"valid": False, "reason": "newDescription must be a string"}
                
        elif action == "move":
            new_location = decision.get("newLocation")
            if not new_location:
                return {"valid": False, "reason": "move action requires newLocation field"}
                
            # Check if target location exists
            valid_locations = [loc.get("locationId") for loc in area_data.get("locations", [])]
            if new_location not in valid_locations:
                return {"valid": False, "reason": f"Target location '{new_location}' does not exist. Valid locations: {valid_locations}"}
        
        location_update = decision.get("locationUpdate")
        if location_update is not None and not isinstance(location_update, str):
            return {"valid": False, "reason": "locationUpdate must be a string or null"}
        
        # Schema validation - check NPC structure requirements
        if action == "update_status":
            # Simulate the NPC object that would be created
            test_npc = {
                "name": "test",
                "description": decision.get("newDescription"),
                "attitude": decision.get("newAttitude")
            }
            
            # Basic validation
            for field in ["name", "description", "attitude"]:
                if not test_npc.get(field):
                    return {"valid": False, "reason": f"NPC object missing required field: {field}"}
                if not isinstance(test_npc[field], str):
                    return {"valid": False, "reason": f"NPC field '{field}' must be a string"}
        
        return {"valid": True, "reason": "Decision validated successfully"}
        
    except Exception as e:
        return {"valid": False, "reason": f"Validation error: {str(e)}"}

def execute_npc_movement_decision(decision, area_data, location_id, npc_name, path_manager):
    """Execute the AI's decision with surgical updates to area data"""
    try:
        action = decision.get("action")
        
        # Find the location and NPC in area data
        target_location = None
        npc_index = None
        
        for location in area_data.get("locations", []):
            if location.get("locationId") == location_id:
                target_location = location
                # Find NPC index
                for i, npc in enumerate(location.get("npcs", [])):
                    if npc.get("name", "").lower() == npc_name.lower():
                        npc_index = i
                        break
                break
        
        if not target_location or npc_index is None:
            error("VALIDATION: Could not find location or NPC in area data", category="npc_management")
            return False
        
        if action == "remove":
            # Remove NPC from location
            target_location["npcs"].pop(npc_index)
            info(f"STATE_CHANGE: Removed {npc_name} from {location_id}", category="npc_management")
            
            # Update location description if provided
            location_update = decision.get("locationUpdate")
            if location_update:
                current_desc = target_location.get("description", "")
                target_location["description"] = f"{current_desc} {location_update}".strip()
                
        elif action == "update_status":
            # Update NPC description and attitude
            new_description = decision.get("newDescription")
            new_attitude = decision.get("newAttitude")
            
            if new_description:
                target_location["npcs"][npc_index]["description"] = new_description
                info(f"STATE_CHANGE: Updated description for {npc_name}", category="npc_management")
            
            if new_attitude:
                target_location["npcs"][npc_index]["attitude"] = new_attitude
                info(f"STATE_CHANGE: Updated attitude for {npc_name}", category="npc_management")
                
            # Update location description if provided
            location_update = decision.get("locationUpdate")
            if location_update:
                current_desc = target_location.get("description", "")
                target_location["description"] = f"{current_desc} {location_update}".strip()
                    
        elif action == "move":
            # Move NPC to different location
            new_location_id = decision.get("newLocation")
            if not new_location_id:
                error("VALIDATION: Move action specified but no target location provided", category="npc_management")
                return False
                
            # Find target location
            target_new_location = None
            for location in area_data.get("locations", []):
                if location.get("locationId") == new_location_id:
                    target_new_location = location
                    break
                    
            if not target_new_location:
                error(f"VALIDATION: Target location {new_location_id} not found", category="npc_management")
                return False
                
            # Move NPC
            npc_to_move = target_location["npcs"].pop(npc_index)
            target_new_location["npcs"].append(npc_to_move)
            info(f"STATE_CHANGE: Moved {npc_name} from {location_id} to {new_location_id}", category="npc_management")
            
            # Update both location descriptions if provided
            location_update = decision.get("locationUpdate")
            if location_update:
                # Update source location
                current_desc = target_location.get("description", "")
                target_location["description"] = f"{current_desc} {location_update}".strip()
        
        else:
            error(f"VALIDATION: Unknown action: {action}", category="npc_management")
            return False
            
        return True
        
    except Exception as e:
        error(f"FAILURE: Failed to execute decision: {str(e)}", category="npc_management")
        return False

def create_area_backup(area_file):
    """Create timestamped backup of area file"""
    import shutil
    import os
    from datetime import datetime
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{area_file}.backup_npc_move_{timestamp}"
        shutil.copy2(area_file, backup_name)
        debug(f"FILE_OP: Created area backup: {os.path.basename(backup_name)}", category="file_operations")
        return backup_name
    except Exception as e:
        error(f"FILE_OP: Could not create area backup: {e}", category="file_operations")
        return None

def cleanup_old_area_backups(area_file, max_backups=5):
    """Clean up old area backup files"""
    import os
    
    try:
        directory = os.path.dirname(area_file)
        base_name = os.path.basename(area_file)
        
        backup_files = []
        for file in os.listdir(directory):
            if file.startswith(f"{base_name}.backup_npc_move_") and file.endswith(".json"):
                backup_path = os.path.join(directory, file)
                mtime = os.path.getmtime(backup_path)
                backup_files.append((mtime, backup_path))
        
        # Sort by modification time (newest first) and remove old ones
        backup_files.sort(reverse=True)
        if len(backup_files) > max_backups:
            for _, old_backup in backup_files[max_backups:]:
                try:
                    os.remove(old_backup)
                    debug(f"FILE_OP: Removed old backup: {os.path.basename(old_backup)}", category="file_operations")
                except Exception as e:
                    warning(f"FILE_OP: Could not remove old backup: {e}", category="file_operations")
                    
    except Exception as e:
        warning(f"FILE_OP: Backup cleanup failed: {e}", category="file_operations")
