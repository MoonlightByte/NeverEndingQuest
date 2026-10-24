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
from core.ai import history_markers as hm
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
from utils.capture.live_provider_call import (
    LiveProviderCompletedError,
    LiveProviderSuperseded,
)
from utils.provider_errors import classify_provider_error
from core.combat.invocation import InvocationSupersededError
register_callsite("T012", "core/ai/action_handler.py", 676)
import config
from core.managers.current_location import current_location_data
from utils.module_path_manager import ModulePathManager
from utils.encoding_utils import sanitize_text, safe_json_dump, safe_json_load
from utils.file_operations import safe_read_json, safe_write_json
from utils.transient_filesystem import ReadOnlySaveStop
from core.managers.status_manager import (
    status_transitioning_location, status_updating_character, status_updating_party,
    status_updating_plot, status_advancing_time, status_processing_levelup
)
from utils.location_path_finder import LocationGraph
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from core.nql.journal import entry_id as journal_entry_id


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
ACTION_ROLL_CHECK = "rollCheck"
ACTION_AWARD_EXPERIENCE = "awardExperience"
ACTION_UPDATE_PARTY_NPCS = "updatePartyNPCs"
ACTION_CREATE_NEW_MODULE = "createNewModule"
ACTION_ESTABLISH_HUB = "establishHub"
ACTION_STORAGE_INTERACTION = "storageInteraction"
ACTION_TRANSFER_ITEM = "transferItem"
ACTION_ACQUIRE_ITEM = "acquireItem"
ACTION_EXPEND_CHARGES = "expendCharges"
ACTION_TRANSFER_CURRENCY = "transferCurrency"
ACTION_SPLIT_CURRENCY = "splitCurrency"
ACTION_REST = "rest"
ACTION_UPDATE_PARTY_TRACKER = "updatePartyTracker"
ACTION_MOVE_BACKGROUND_NPC = "moveBackgroundNPC"  # retired: forwarded to the occupant actions
ACTION_RESOLVE_OCCUPANT = "resolveOccupant"
ACTION_SET_OCCUPANT_ATTITUDE = "setOccupantAttitude"
ACTION_MOVE_OCCUPANT = "moveOccupant"
ACTION_RETURN_OCCUPANT = "returnOccupant"
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
    # "engine": the engine's map approved the move (C10b) and travel commits
    # it; "snapshot": NEQ's own route check did (the engine was unavailable).
    authority: str = "snapshot"
    # The engine's trip time in game minutes at SRD normal pace (C11); None
    # under NEQ's own route check (the DM's estimate stands).
    travel_minutes: object = None


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
    authority="snapshot",
    travel_minutes=None,
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
        authority=str(authority),
        travel_minutes=travel_minutes if type(travel_minutes) is int else None,
    )


def _write_location_transition_checkpoint(checkpoint):
    """Durably publish the small, non-secret within-module recovery record."""
    safe_json_dump(checkpoint, PENDING_LOCATION_TRANSITION_FILE)


def _read_journal_setting_aside(
    tail, before_rename=None, after_failed_rename=None, after_rename=None
):
    """Read journal.json, setting an unreadable one aside (then None).

    The chronicle is play history, not a rule input: an unreadable one
    must not stop travel (#620, #636). Its bytes are set aside, never
    overwritten, and the caller goes on as for a missing chronicle
    (D-620-1, D-636-2); `tail` ends the WARNING. A busy file is waited for
    and read again (D-303-2); if the set-aside itself is refused, the parse
    error stands as before. `before_rename` runs just before the rename and
    `after_failed_rename` first when it fails, so a caller's own record can
    bracket the rename alone; `after_rename(aside)` runs once it succeeded. A journal that parses but fails its schema
    counts as unreadable, since every departure would refuse it (#633)."""
    from utils.transient_filesystem import is_transient_filesystem_error
    from utils.capture.live_provider_call import (
        _interruptible_wait, get_live_provider_scope,
    )
    from core.ai import adv_summary

    while True:
        try:
            journal = safe_json_load("journal.json")
            failure = None
            if journal is not None:
                try:
                    failure = adv_summary.journal_schema_failure(journal)
                except adv_summary.DepartureSummaryError:
                    failure = None  # no schema to judge by: read as before
            if failure is not None:
                raise ValueError("does not match its schema: %s" % failure[:200])
            break
        except ValueError as exc:
            aside = "journal.json.unreadable-%s-%s" % (
                datetime.now().strftime("%Y%m%d-%H%M%S"), uuid4().hex
            )
            if before_rename is not None:
                before_rename()
            try:
                os.rename("journal.json", aside)
            except OSError as rename_exc:
                if after_failed_rename is not None:
                    after_failed_rename()
                if not is_transient_filesystem_error(rename_exc, allow_missing=True):
                    raise exc from rename_exc
            else:
                warning(
                    "TRAVEL: journal.json unreadable (%s); set aside as %s, "
                    % (exc, aside) + tail,
                    category="location_transitions",
                )
                if after_rename is not None:
                    try:
                        after_rename(aside)
                    except Exception as note_exc:
                        warning(
                            "TRAVEL: could not note the set-aside chronicle for the "
                            "companion-memory upgrade: %s" % note_exc,
                            category="location_transitions",
                        )
                journal = None
                break
        except OSError as exc:
            if not is_transient_filesystem_error(exc):
                raise
        _interruptible_wait(
            0.25, get_live_provider_scope(), "Reading the chronicle..."
        )
    return journal


def mark_upgrade_journal_replaced(aside):
    """Tell an in-progress companion-memory upgrade its chronicle was replaced.

    Passed as `after_rename` only by the callers that start a new chronicle
    (#653); the departure-marker recovery rebuilds the same one and does not.
    """
    from core.npc.episodic_upgrade import mark_journal_replaced

    mark_journal_replaced(aside)


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
    path=None,
    authority="snapshot",
    travel_minutes=None,
):
    """Build the approved v2 record without content-derived authority.
    `path` is the approved route, origin to destination (location ids): the
    engine's party walks it after the commit (core/nql/travel.py). With
    authority "engine" the engine approved the move and travels it, so no
    path is recorded to walk. `travel_minutes` is the engine's approved trip
    time (C11), kept for the commit's check; the deferred updateTime already
    carries the applied time (travel.timed_deferred)."""
    operation_id = str(uuid4())
    persisted_history = safe_json_load(
        "modules/conversation_history/conversation_history.json"
    )
    if not isinstance(persisted_history, list):
        persisted_history = json.loads(json.dumps(conversation_history))
    segment_start = 0
    for index in range(len(persisted_history) - 1, -1, -1):
        message = persisted_history[index]
        if hm.is_marker(message, hm.LOCATION_TRANSITION, *hm.MODULE_KINDS):
            segment_start = index + 1
            break
    origin_segment = persisted_history[segment_start:]
    journal = _read_journal_setting_aside(
        "and the chronicle starts again from the next recorded departure",
        after_rename=mark_upgrade_journal_replaced,
    )
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
        # J2: the prose is keyed by the engine's departure entry id.
        "id": journal_entry_id(str(module_name), operation_id, "departure"),
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
        "path": [str(item) for item in (path or ())],
        "authority": str(authority),
        "travel_minutes": travel_minutes if type(travel_minutes) is int else None,
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
            # T091 retired (P4-f): the engine's record is the origin roster.
            "status": "not_applicable",
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


class ModuleNotJoinedError(ValueError):
    """The destination module is installed but not joined to the world (#720),
    or the value is not a module id at all (#1287): then the joined ids are
    returned to the agent, never guessed from the value."""

    def __init__(self, module_name, joined_ids=None):
        self.module_name = module_name
        if joined_ids is not None:
            super().__init__(
                "module %r is not a module id; the joined module ids are: %s"
                % (module_name, ", ".join(sorted(joined_ids)))
            )
            return
        super().__init__(
            "module %s is installed but not joined to this world, so it is "
            "not a travel destination" % module_name
        )


def resolve_cross_module_target_projection(target_module, parameters):
    """Resolve one represented module destination to canonical IDs and names.

    The model chooses the module and may request an explicit represented
    destination.  Code owns identity reconciliation: it neither guesses from
    prose nor silently combines an area from one location with a location from
    another.  Invalid structured references return facts to the agent before
    any checkpoint or gameplay mutation exists.

    The destination must be a joined module (#720): one whose joining was
    refused, never checked, or blocked keeps only a bare registry stub, and
    its files on disk are not part of the world.
    """
    parameters = parameters if isinstance(parameters, dict) else {}
    from core.generators.module_stitcher import ModuleStitcher
    registry = safe_json_load(os.path.join("modules", "world_registry.json"))
    if not isinstance(registry, dict) or not isinstance(registry.get("modules"), dict):
        import errno
        raise OSError(errno.EIO, "World registry could not be verified")
    # #1287: the exact folder id only; a display form is refused, never stored.
    target_module = str(target_module or "")
    if target_module not in registry["modules"]:
        raise ModuleNotJoinedError(target_module, joined_ids=[
            key for key in registry["modules"]
            if ModuleStitcher.is_joined_registry_module(registry, key)
        ])
    if not ModuleStitcher.is_joined_registry_module(registry, target_module):
        raise ModuleNotJoinedError(target_module)
    from utils.path_encounter_analyzer import build_active_module_snapshot
    snapshot = build_active_module_snapshot(target_module)
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
        if not snapshot["nodes"]:
            if snapshot.get("read_errors"):
                import errno
                busy = any(item["kind"] == "busy" for item in snapshot["read_errors"])
                raise OSError(errno.EAGAIN if busy else errno.EIO, "Target module records could not be verified")
            raise ValueError("Target module has no live destination records")
        default_location_id, default_location_name, default_area_id, default_area_name = (
            get_module_starting_location(target_module, snapshot=snapshot)
        )
        supplied = {
            "currentAreaId": str(default_area_id),
            "currentArea": "",
            "currentLocationId": str(default_location_id),
            "currentLocation": "",
        }
    if not supplied["currentAreaId"] or not supplied["currentLocationId"]:
        raise ValueError(
            "an explicit module destination requires both currentAreaId and "
            "currentLocationId"
        )

    node = snapshot["nodes"].get(supplied["currentLocationId"])
    matched = None
    if node is not None and supplied["currentLocationId"] not in snapshot["invalid_location_ids"]:
        matched = (
            node["area_id"], node["area_name"],
            node["location_id"], node["location_name"],
        )
    if matched is None and snapshot.get("read_errors"):
        read_error = next(
            (item for item in snapshot["read_errors"] if item["kind"] == "busy"),
            snapshot["read_errors"][0],
        )
        import errno
        raise OSError(
            errno.EAGAIN if read_error["kind"] == "busy" else errno.EIO,
            "Target module records could not be verified",
            read_error["source_file"],
        )
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
    # C12: the switch travels over the join of the two modules; a later
    # crossing's updateTime takes the engine's floor.
    from core.nql import travel as _travel
    crossing = _travel.crossing(
        source_module,
        str(source_world.get("currentLocationId") or ""),
        target_module,
        target_values["currentLocationId"],
        clock_action,
    )
    clock_action = crossing["clock_action"]
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
        authority="engine" if crossing["join"] is not None else "snapshot",
        travel_minutes=crossing["minutes"],
    )
    checkpoint["movement_kind"] = "cross_module_root"
    if crossing["join"] is not None:
        join = dict(crossing["join"])
        join["operationId"] = join.get("operationId") or checkpoint["operation_id"]
        checkpoint["join"] = join
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


_PARTY_NPCS_DROP_WARNED = set()


def _drop_stored_party_npcs(checkpoint):
    """An updatePartyTracker stored before occupant ids may carry partyNPCs,
    which no writer may replace the roster with now. The key is dropped from
    the module handoff's parameters, a deferred record's action parameters
    and a prepared receipt's parameters, in memory only (the loader never
    writes); the rest of the stored change applies. One WARN per operation
    id per process, only when a key was removed."""
    removed = False
    handoff = checkpoint.get("module_handoff")
    if isinstance(handoff, dict) and isinstance(handoff.get("parameters"), dict):
        if "partyNPCs" in handoff["parameters"]:
            handoff["parameters"].pop("partyNPCs")
            removed = True
    deferred = checkpoint.get("deferred_actions")
    records = deferred.get("actions") if isinstance(deferred, dict) else None
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        action = record.get("action")
        if record.get("family") == ACTION_UPDATE_PARTY_TRACKER and isinstance(action, dict) \
                and isinstance(action.get("parameters"), dict) and "partyNPCs" in action["parameters"]:
            action["parameters"].pop("partyNPCs")
            removed = True
        receipt = record.get("receipt")
        if isinstance(receipt, dict) and receipt.get("kind") == ACTION_UPDATE_PARTY_TRACKER \
                and isinstance(receipt.get("parameters"), dict) and "partyNPCs" in receipt["parameters"]:
            receipt["parameters"].pop("partyNPCs")
            removed = True
    operation = checkpoint.get("operation_id")
    if removed and operation not in _PARTY_NPCS_DROP_WARNED:
        _PARTY_NPCS_DROP_WARNED.add(operation)
        warning(
            "TRAVEL: stored updatePartyTracker of %s carries partyNPCs; the key is "
            "dropped (the roster changes only through updatePartyNPCs) and the rest "
            "applies" % operation,
            category="location_transitions",
        )
    return checkpoint


def load_current_transition_checkpoint(operation_id=None):
    checkpoint = safe_json_load(PENDING_LOCATION_TRANSITION_FILE)
    if not isinstance(checkpoint, dict):
        return None
    if checkpoint.get("version") != 2 or checkpoint.get("kind") != "current_transition":
        return None
    if operation_id and checkpoint.get("operation_id") != operation_id:
        return None
    return _drop_stored_party_npcs(checkpoint)


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
            "moveOccupant",
            "resolveOccupant",
            "setOccupantAttitude",
            "returnOccupant",
        } or record.get(
            "receipt"
        ) is not None:
            continue
        parameters = record["action"].get("parameters", {})
        if family in (
            "moveOccupant",
            "resolveOccupant",
            "setOccupantAttitude",
            "returnOccupant",
        ):
            # P4-g: an escort (moveOccupant to the destination) rides the
            # travel receipt; any other occupant action is refused here with
            # its reason and never applied. The travel is never blocked.
            from core.nql import occupants as _occupants

            receipt = _occupants.prepare_travel_action(
                family,
                parameters,
                "dm:travel:%s:%d:%s" % (operation_id, index, family),
                str(checkpoint.get("module_name") or ""),
                str(checkpoint.get("origin_location_id") or ""),
                str(checkpoint.get("destination_location_id") or ""),
            )
            checkpoint = load_current_transition_checkpoint(operation_id)
            checkpoint["deferred_actions"]["actions"][index]["receipt"] = receipt
            _write_location_transition_checkpoint(checkpoint)
            continue
        if family == "updatePlot":
            # QS: the quest record is the engine's. The local checks run
            # before movement; the engine line is sent after arrival. A
            # refusal is recorded on the receipt and never stops travel.
            from utils import quest_record as _quest_record

            receipt = _quest_record.prepare_travel_update(
                parameters,
                "dm:travel:%s:%d:updatePlot" % (operation_id, index),
                str(checkpoint.get("module_name") or ""),
            )
            receipt["quest_projection"] = {"status": "pending"}
        elif family == "moveBackgroundNPC":
            # Retired (P4-e): the occupant record is the engine's. A travel
            # turn carries no roster outcome; the record is applied as a no-op.
            receipt = {
                "kind": "moveBackgroundNPC",
                "retired": True,
                "npc_name": parameters.get("npcName"),
                "before": None,
                "after": None,
            }
        elif family == "updateCharacterInfo":
            from core.managers.effects_runtime import (
                CharacterProposalDropped,
                prepare_character_update,
            )
            from updates.update_character_info import EngineRefusedChange

            party = safe_json_load("party_tracker.json") or {}
            character_name = (
                parameters.get("characterName")
                or parameters.get("npcName")
            )
            changes = parameters.get("changes")
            if isinstance(changes, dict):
                changes = json.dumps(changes)
            try:
                if not character_name:
                    # #914: no named character; dropped like an unworkable
                    # update, never written to a default character.
                    raise CharacterProposalDropped("A party member")
                receipt = prepare_character_update(
                    character_name, changes, party,
                    affects=parameters.get("affects"),
                    casting_resource=parameters.get("castingResource"),
                )
            except CharacterProposalDropped as dropped:
                # #855: no usable proposal within the bounded tries. The
                # change is dropped, the travel goes on, and the player is
                # told once after arrival.
                warning(
                    "TRAVEL: no usable sheet update for %s; dropped after "
                    "the bounded tries, travel goes on" % dropped.owner,
                    category="location_transitions",
                )
                receipt = {
                    "kind": "updateCharacterInfo",
                    "character_status": "dropped",
                    "owner": dropped.owner,
                    "message_id": str(uuid4()),
                }
            except EngineRefusedChange as refusal:
                # #855: the rules engine refused the change. It is dropped,
                # the travel goes on, and the arrival notice gives the
                # engine's reason.
                warning(
                    "TRAVEL: the rules refused the sheet update for %s; "
                    "dropped, travel goes on" % character_name,
                    category="location_transitions",
                )
                receipt = {
                    "kind": "updateCharacterInfo",
                    "character_status": "dropped",
                    "owner": character_name,
                    "reason_code": "engine_refused",
                    "engine_reason": str(refusal.reason),
                    "message_id": str(uuid4()),
                }
        elif family == "storageInteraction":
            from core.managers.storage_processor import process_storage_request
            from core.managers.storage_manager import StorageManager

            # Never a default character (#959).
            character_name = parameters.get("characterName")
            try:
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
            except _TRAVEL_PREPARE_PASSTHROUGH:
                raise
            except (ValueError, RuntimeError) as exc:
                # #855: dropped like a sheet update; the travel goes on.
                owner = character_name or "Your character"
                warning(
                    "TRAVEL: no usable storage change for %s; dropped after "
                    "the bounded tries, travel goes on (%s: %s)"
                    % (owner, type(exc).__name__, exc),
                    category="location_transitions",
                )
                receipt = {
                    "kind": "storageInteraction",
                    "storage_status": "dropped",
                    "owner": owner,
                    "message_id": str(uuid4()),
                }
        elif family == "updatePartyNPCs":
            try:
                receipt = prepare_party_npc_update(
                    parameters, record["operation_id"]
                )
            except _TRAVEL_PREPARE_PASSTHROUGH:
                raise
            except (ValueError, RuntimeError) as exc:
                # #855: a party change that cannot be prepared (no sheet
                # could be made, or a malformed request) is dropped and the
                # travel goes on. A failed add is told on arrival.
                npc = parameters.get("npc")
                npc_name = npc.get("name") if isinstance(npc, dict) else None
                owner = (
                    npc_name.strip()
                    if isinstance(npc_name, str) and npc_name.strip()
                    else None
                )
                warning(
                    "TRAVEL: no usable party change for %s; dropped, travel "
                    "goes on (%s: %s)"
                    % (owner or "an unnamed NPC", type(exc).__name__, exc),
                    category="location_transitions",
                )
                receipt = {
                    "kind": "updatePartyNPCs",
                    "npc_status": "dropped",
                    "operation": parameters.get("operation"),
                    "owner": owner,
                    "message_id": str(uuid4()),
                }
                if isinstance(exc, PartyChangeUnplanned):
                    receipt["npc_drop"] = "unplanned"
        else:
            source_module = str(checkpoint.get("module_name") or "")
            target_module = str(parameters.get("module") or "")
            if not target_module or target_module == source_module:
                raise ValueError("post-local module handoff requires another module")
            projection = resolve_cross_module_target_projection(target_module, parameters)
            exact_parameters = copy.deepcopy(parameters)
            exact_parameters.update(projection)
            exact_parameters["module"] = target_module
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
                    **projection,
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
    """The origin roster is the engine's record (P4-f); T091 is retired. The
    receipt is kept for old checkpoints: a pending one resolves as not
    applicable, a committed one stays as it is."""
    checkpoint = load_current_transition_checkpoint(operation_id)
    if checkpoint is None:
        raise RuntimeError("current transition checkpoint is unavailable")
    receipt = checkpoint["location_reconciliation"]
    if receipt.get("status") in {"committed", "attempted_unavailable", "not_applicable"}:
        return receipt["status"]
    receipt["status"] = "not_applicable"
    checkpoint["phase"] = "reconciliation_resolved"
    _write_location_transition_checkpoint(checkpoint)
    return receipt["status"]


def _departure_projection_status(action_record):
    """The workflow_status T016 sees for one deferred action (#686).

    A character update the engine has already staged (its typed receipt is
    in the record, applied on arrival) is the outcome of an action taken at
    the place being left, e.g. the item a scored check found (#594), so it
    is shown as staged_on_arrival. Everything else keeps the record's own
    status. The checkpoint record itself is never changed.
    """
    status = str(action_record.get("status") or "pending")
    receipt = action_record.get("receipt")
    if isinstance(receipt, dict) and "dropped" in (
        receipt.get("character_status"),
        receipt.get("storage_status"),
        receipt.get("npc_status"),
    ):
        # #855: dropped before movement; it is never applied on arrival.
        return "dropped"
    if (
        status == "pending"
        and isinstance(receipt, dict)
        and receipt.get("kind") == "updateCharacterInfo"
        and receipt.get("status") == "staged"
    ):
        return "staged_on_arrival"
    return status


def _commit_departure_journal_only(
    checkpoint, summary_record, commit_record, journal_data, area_detail
):
    """Commit a departure whose area is left as it is (#1072, D-1072-1).

    The skip is recorded in the checkpoint before the journal is written, so a
    retry after a crash takes this path again even if the area reads cleanly
    by then; the entry at its staged index marks the commit done.
    """
    if not isinstance(journal_data, dict) or not isinstance(
        journal_data.get("entries"), list
    ):
        raise RuntimeError("journal is unavailable during departure commit")
    if not commit_record.get("area_skipped"):
        warning(
            "FALLBACK: departure area left as it is for %s: %s; the journal "
            "records the departure" % (checkpoint["origin_location_id"], area_detail),
            category="location_transitions",
        )
        commit_record["area_skipped"] = area_detail
        _write_location_transition_checkpoint(checkpoint)
    journal_index = commit_record["journal_entry_index"]
    entries = journal_data["entries"]
    if not (
        journal_index < len(entries)
        and entries[journal_index] == commit_record["journal_entry_after"]
    ):
        if len(entries) != journal_index:
            commit_record["status"] = "blocked_conflict"
            checkpoint["phase"] = "blocked_conflict"
            _write_location_transition_checkpoint(checkpoint)
            raise RuntimeError("departure journal changed outside the staged operation")
        from core.ai import adv_summary

        journal_after = copy.deepcopy(journal_data)
        journal_after["entries"].append(
            copy.deepcopy(commit_record["journal_entry_after"])
        )
        adv_summary.commit_departure_journal(journal_after)
    commit_record["status"] = "committed"
    checkpoint["phase"] = "departure_committed"
    _write_location_transition_checkpoint(checkpoint)
    return summary_record["text"]


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

    # An interrupted commit's marker is resolved first, from its own
    # snapshots, before anything here reads the area or the journal (#636,
    # D-636-11). An unreadable journal under it is set aside and rebuilt
    # from the marker (D-636-10).
    try:
        os.stat(adv_summary.PENDING_DEPARTURE_SUMMARY_FILE)
    except OSError:
        pass
    else:
        adv_summary.resolve_prior_departure_summary(
            lambda: _read_journal_setting_aside(
                "and the chronicle is rebuilt from the interrupted commit's record"
            )
        )

    # An unreadable chronicle must not stop the departure from finishing
    # (#636, D-636-2): it is set aside and the staged entry becomes entry 0
    # of a fresh one. The index is rebased just before the rename and put
    # back at once if the rename fails. While a departure-summary marker
    # exists, or cannot be checked, the journal is left as it is (D-636-5).
    try:
        os.stat(adv_summary.PENDING_DEPARTURE_SUMMARY_FILE)
    except FileNotFoundError:
        staged_index = commit_record["journal_entry_index"]

        def rebase(index):
            if commit_record["journal_entry_index"] != index:
                commit_record["journal_entry_index"] = index
                _write_location_transition_checkpoint(checkpoint)

        _read_journal_setting_aside(
            "and the chronicle starts again with the interrupted departure "
            "from %s (its entry, staged at index %s, is now entry 0)"
            % (commit_record["journal_entry_after"].get("location"), staged_index),
            before_rename=lambda: rebase(0),
            after_failed_rename=lambda: rebase(staged_index),
            after_rename=mark_upgrade_journal_replaced,
        )
    except OSError:
        pass

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
            projected_action["workflow_status"] = _departure_projection_status(
                action_record
            )
            action_projection.append(projected_action)
        proposal = adv_summary.prepare_departure_summary(
            transition_context["origin_history_segment"],
            transition_context["origin_party_tracker"],
            transition_context["origin_location_info"]["name"],
            checkpoint["origin_area_id"],
            checkpoint["origin_location_id"],
            structured_actions=action_projection,
            destination_location_name=checkpoint.get("destination_location_name"),
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
        if proposal["area_before"] is None:
            # #1072: the area could not be read strictly; only the journal
            # entry is committed and the area is left as it is.
            commit_record.update(
                {
                    "status": "staged",
                    "area_path": proposal["area_path"],
                    "area_skipped": proposal["area_unreadable"],
                    "journal_entry_after": staged_journal_entry,
                }
            )
        else:
            area_before = proposal["area_before"]
            location_index = next(
                index
                for index, location in enumerate(area_before["locations"])
                if location.get("locationId") == checkpoint["origin_location_id"]
            )
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

    area_status, area_data, area_detail = adv_summary.read_departure_area(
        transition_context["origin_party_tracker"],
        commit_record["area_path"],
        checkpoint["origin_area_id"],
        checkpoint["origin_location_id"],
    )
    if area_status not in (adv_summary.OK, adv_summary.UNREADABLE):
        area_data = safe_json_load(commit_record["area_path"])
    journal_exists = os.path.exists("journal.json")
    journal_data = safe_json_load("journal.json")
    if not journal_exists and journal_data is None:
        journal_data = {"entries": []}
    if area_status == adv_summary.UNREADABLE or commit_record.get("area_skipped"):
        return _commit_departure_journal_only(
            checkpoint, summary_record, commit_record, journal_data, area_detail
        )
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
    if family in (
        "moveOccupant",
        "resolveOccupant",
        "setOccupantAttitude",
        "returnOccupant",
    ):
        # P4-g: the occupant record is the engine's; the staged escort is
        # applied by its request id (a replay is answered as historical). A
        # refusal or an unavailable engine is recorded and the arrival goes
        # on. A checkpoint from before P4-g (no receipt) resolves as not
        # applicable.
        from core.nql import occupants as _occupants

        if not isinstance(receipt, dict):
            outcome = "not_applicable"
            record["receipt"] = {"kind": family, "status": outcome}
        else:
            outcome = _occupants.apply_travel_receipt(
                receipt, str(checkpoint.get("module_name") or "")
            )
        record["status"] = "committed"
        deferred["cursor"] = action_index + 1
        deferred["receipts"].append(
            {
                "operation_id": record["operation_id"],
                "kind": family,
                "status": "committed",
                "occupant_status": outcome,
            }
        )
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        return "committed"
    if not isinstance(receipt, dict):
        raise RuntimeError(
            "deferred action family %s has no approved v2 receipt" % family
        )

    from core.managers.campaign_manager import _party_module_transition_lock

    if family == "updatePlot":
        # QS: the quest record is the engine's. The prepared line is sent
        # by its travel request id (a replay is historical); a refusal or an
        # unavailable engine is recorded and the arrival goes on. T090's
        # journal steps run only after a committed change. A checkpoint from
        # before the switch (a T077 receipt: target_id, before, after) is
        # mapped to the same line first.
        from utils import quest_record as _quest_record
        from utils.quest_player_formatter import (
            apply_staged_player_quests,
            prepare_player_quests,
            refresh_staged_player_quest_source,
        )

        if receipt.get("kind") != "updatePlot" or "line" not in receipt:
            legacy_projection = receipt.get("quest_projection") or {"status": "pending"}
            receipt = _quest_record.receipt_from_legacy(
                receipt, "dm:travel:%s:%d:updatePlot" % (operation_id, action_index)
            )
            receipt["quest_projection"] = legacy_projection
            record["receipt"] = receipt
            _write_location_transition_checkpoint(checkpoint)
        if receipt.get("quest_status") == "prepared":
            quest_outcome = _quest_record.apply_travel_receipt(receipt)
            _write_location_transition_checkpoint(checkpoint)
        else:
            # refused before movement, or already committed / attempted on
            # a resumed checkpoint (the checkpoint owns receipt["status"])
            quest_outcome = str(receipt.get("quest_status") or "refused")
        if quest_outcome != "committed":
            record["status"] = "committed"
            deferred = checkpoint["deferred_actions"]
            deferred["cursor"] = action_index + 1
            deferred["receipts"].append(
                {
                    "operation_id": record["operation_id"],
                    "kind": family,
                    "status": "committed",
                    "quest_status": quest_outcome,
                }
            )
            if deferred["cursor"] >= len(deferred["actions"]):
                deferred["status"] = "committed"
            _write_location_transition_checkpoint(checkpoint)
            return "committed"

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
        # Retired (P4-e). A receipt materialized before the retirement (an
        # in-flight checkpoint) still applies its frozen area value; any other
        # is a no-op, so an old checkpoint never blocks the arrival.
        if receipt.get("after") is not None:
            outcome = apply_staged_background_npc_movement(receipt)
            if outcome == "blocked_conflict":
                record["status"] = "blocked_conflict"
                checkpoint["phase"] = "blocked_conflict"
                _write_location_transition_checkpoint(checkpoint)
                return outcome
        else:
            info(
                "moveBackgroundNPC for %s in a travel turn is retired; nothing applied"
                % receipt.get("npc_name"),
                category="npc_management",
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

        dropped = receipt.get("character_status") == "dropped"
        outcome = None if dropped else apply_staged_character_update(receipt)
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
        if dropped:
            deferred["receipts"][-1]["character_status"] = "dropped"
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        if dropped:
            # After the checkpoint write: shown at most once, never again
            # on a resume (the cursor is past this record).
            if receipt.get("reason_code") == "engine_refused":
                notice = _DROPPED_SHEET_RULES_NOTICE % (
                    receipt["owner"], receipt.get("engine_reason") or "no reason given"
                )
            else:
                notice = _DROPPED_SHEET_NOTICE % receipt["owner"]
            _show_transition_notice(receipt["message_id"], notice)
        return "committed"

    if family == "storageInteraction":
        from core.managers.storage_manager import StorageManager

        dropped = receipt.get("storage_status") == "dropped"
        if not dropped:
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
        if dropped:
            deferred["receipts"][-1]["storage_status"] = "dropped"
        if deferred["cursor"] >= len(records):
            deferred["status"] = "committed"
        _write_location_transition_checkpoint(checkpoint)
        if dropped:
            _show_transition_notice(
                receipt["message_id"], _DROPPED_STORAGE_NOTICE % receipt["owner"]
            )
        return "committed"

    if family == "updatePartyNPCs":
        party = safe_json_load("party_tracker.json")
        if receipt.get("npc_status") != "dropped" and "outcome_kind" not in receipt:
            # A receipt staged before occupant ids: adapted through the
            # planner at the commit location and written back before the
            # compare-and-swap, so a resume finds the same adapted receipt.
            if not isinstance(party, dict) or not isinstance(
                party.get("partyNPCs"), list
            ):
                raise RuntimeError("party roster is unavailable")
            try:
                adapted = _adapt_party_receipt(
                    receipt, party, action_index, checkpoint.get("operation_id")
                )
            except _TRAVEL_PREPARE_PASSTHROUGH:
                raise
            except (ValueError, RuntimeError) as exc:
                warning(
                    "TRAVEL: no usable party change for %s; dropped (%s: %s)"
                    % (receipt.get("npc_name") or "an unnamed NPC", type(exc).__name__, exc),
                    category="location_transitions",
                )
                adapted = None
            if not adapted:
                receipt.update(
                    {
                        "npc_status": "dropped",
                        "owner": receipt.get("npc_name"),
                        "message_id": str(uuid4()),
                    }
                )
                if adapted is False:
                    receipt["npc_drop"] = "unplanned"
            _write_location_transition_checkpoint(checkpoint)
        if receipt.get("npc_status") == "dropped":
            # #855: dropped before movement; the roster is not touched.
            record["status"] = "committed"
            deferred["cursor"] = action_index + 1
            deferred["receipts"].append(
                {
                    "operation_id": record["operation_id"],
                    "kind": family,
                    "status": "committed",
                    "npc_status": "dropped",
                }
            )
            if deferred["cursor"] >= len(records):
                deferred["status"] = "committed"
            _write_location_transition_checkpoint(checkpoint)
            if receipt.get("owner") and receipt.get("operation") in ("add", "remove"):
                if receipt.get("operation") == "remove":
                    notice = _DROPPED_NPC_LEAVE_NOTICE
                elif receipt.get("npc_drop") == "unplanned":
                    notice = _UNPLANNED_NPC_NOTICE
                else:
                    notice = _DROPPED_NPC_NOTICE
                _show_transition_notice(receipt["message_id"], notice % receipt["owner"])
            return "committed"
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
        elif "legacy_roster_after" in receipt and party["partyNPCs"] == receipt["legacy_roster_after"]:
            # The code before occupant ids already wrote its roster: the
            # adapted roster (the row with its id) replaces it.
            with _party_module_transition_lock():
                latest = safe_json_load("party_tracker.json")
                if latest.get("partyNPCs") != receipt["legacy_roster_after"]:
                    outcome = "blocked_conflict"
                else:
                    latest["partyNPCs"] = copy.deepcopy(receipt["roster_after"])
                    safe_json_dump(latest, "party_tracker.json")
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
        kind = receipt.get("outcome_kind")
        if kind == "noop":
            receipt["lifecycle_status"] = "not_applicable"
        else:
            lifecycle_ok = _apply_party_npc_lifecycle(
                safe_json_load("party_tracker.json") or party,
                "remove" if kind == "leave" else "add",
                receipt["npc_name"],
                receipt["npc_path"],
                receipt.get("lifecycle_context"),
                receipt["operation_id"],
                seed_profile=kind in ("join", "join_new"),
            )
            receipt["lifecycle_status"] = (
                "committed" if lifecycle_ok else "attempted_unavailable"
            )
        # The companion's occupant follows the roster (P4-e); best effort.
        # The lines are built again at the commit location from the
        # receipt's frozen fields (never the live roster, already written).
        from core.nql import occupants as _occupants

        _lc_party = safe_json_load("party_tracker.json") or party
        _lc_module = str(_lc_party.get("module") or "")
        _lc_location = str((_lc_party.get("worldConditions") or {}).get("currentLocationId") or "")
        _lc_context = receipt.get("lifecycle_context")
        _commit = plan_party_change(
            receipt["roster_before"],
            {
                "operation": receipt.get("operation"),
                "occupantId": receipt.get("occupant_id"),
                "npc": {"name": receipt.get("npc_name")},
                "lifecycleContext": _lc_context,
            },
            _occupants.party_world(_lc_module, _lc_location, create=False),
            turn_roster=receipt["roster_before"],
            module=_lc_module,
            location=_lc_location,
            request_id="dm:%s:party" % receipt["operation_id"],
            frozen_kind=kind,
        )
        _occupants.party_change(
            _commit["engine_lines"],
            _commit["request_id"],
            reason=_commit.get("reason"),
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
        marker = hm.marker(
            "user",
            "Module transition: %s to %s" % (source["module"], target["module"]),
            hm.MODULE_TRANSITION,
        )
        if current == source:
            transition_history = list(history)
            if not transition_history or not hm.same_message(transition_history[-1], marker):
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
        # #1420: the trip's arrival was committed when the engine trip
        # committed (commit_current_transition_arrival); the staged time is
        # reconciled to it and nothing is sent again.
        if type(receipt.get("arrivedTick")) is not int:
            _apply_staged_travel_time(checkpoint, record, receipt)
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


def _apply_staged_travel_time(checkpoint, record, receipt):
    """D4: the clock reaches the approved arrival through the engine (its
    trip ticks count toward it); the id makes a resume historical. The
    tracker follows the document and never moves backwards. #1420: the
    receipt keeps the clock at this commit, before any later sibling moves
    it; the travel narration states the trip from `before` to here."""
    from core.nql import game_clock

    game_clock.apply_staged(
        receipt,
        "travel:%s:time" % record["operation_id"],
        arrival=journal_entry_id(
            str(checkpoint.get("module_name") or ""),
            str(checkpoint.get("operation_id") or ""),
            "arrival",
        ),
    )
    arrived = game_clock.clock_tick()
    if arrived is not None:
        receipt["arrivedTick"] = arrived
    return arrived


def commit_current_transition_arrival(operation_id):
    """#1420: one committed arrival per trip, right after the engine trip
    commits and before any narration. The turn's first updateTime (the
    travel-owned one) is applied by its own request id and the clock then
    recorded on its receipt as `arrivedTick`, written once; the deferred
    loop later marks it committed without sending it again. Reloads the
    checkpoint under the transition lock (realign runs outside it). Returns
    the arrival tick, or None when the trip has no travel updateTime."""
    from core.managers.campaign_manager import _party_module_transition_lock

    with _party_module_transition_lock():
        checkpoint = load_current_transition_checkpoint(operation_id)
        if checkpoint is None:
            return None
        deferred = checkpoint.get("deferred_actions")
        records = deferred.get("actions") if isinstance(deferred, dict) else None
        record = next(
            (
                item
                for item in (records if isinstance(records, list) else [])
                if isinstance(item, dict) and item.get("family") == "updateTime"
            ),
            None,
        )
        receipt = record.get("receipt") if record is not None else None
        if not isinstance(receipt, dict):
            return None
        if type(receipt.get("arrivedTick")) is int or record.get("status") == "committed":
            arrived = receipt.get("arrivedTick")
            return arrived if type(arrived) is int else None
        arrived = _apply_staged_travel_time(checkpoint, record, receipt)
        _write_location_transition_checkpoint(checkpoint)
        return arrived


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
        conversation_history.append(hm.marker("user", marker, hm.LOCATION_TRANSITION))
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
    module_snapshot=None,
    detached_context=None,
    turn_context=None,
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
    from utils.capture.live_provider_call import LiveProviderSuperseded
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
        snapshot = module_snapshot
        if snapshot is None or snapshot["module_name"] != current_module:
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
            read_errors = [item for item in snapshot.get("read_errors", []) if item["kind"] != "absent"]
            if any(item["kind"] == "busy" for item in read_errors):
                reason_code = "travel_content_busy"
                path_message = "The travel records are temporarily busy; retry the read."
            elif read_errors:
                reason_code = "travel_content_unavailable"
                path_message = "The relevant travel records could not be read; destination absence is not established."
            elif new_location_id not in nodes:
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
                    "read_errors": read_errors,
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
        from utils import quest_record as _quest_record

        plot_data = _quest_record.module_plot(current_module) or {}

        # C10b: the engine's map leads the in-module move (Q5 rule A: the
        # party stops at every place it has not visited, and passes visited
        # places freely unless a hostile is present). With no engine answer
        # the route check below stays NEQ's own (T021).
        from core.nql import travel as _travel

        engine = _travel.engine_route(
            current_module, current_location_id, new_location_id, path
        )
        if engine is not None:
            nodes = snapshot.get("nodes", {})

            def place_name(location_id):
                return (nodes.get(location_id) or {}).get(
                    "location_name", location_id
                )

            verdict = engine["verdict"]
            info(
                "TRAVEL: engine route %s -> %s: %s"
                % (current_location_id, new_location_id, verdict),
                category="transition_validation",
            )
            if verdict == "halt":
                stop = engine["stop"]
                stop_name = place_name(stop)
                # #1351: who holds the stop is DM-only (occupants carry no
                # disclosure flag); the encounter flow reveals it, not travel.
                reason = "the party stops at %s on the way first" % stop_name
                return finish(
                    False,
                    "[TRAVEL SYSTEM] Travel stops early: %s. Transition only to "
                    "%s (%s) this turn." % (reason, stop, stop_name),
                    reason_code="intermediate_stop",
                    facts={
                        "original_destination_id": str(new_location_id),
                        "stop_location_id": str(stop),
                        "stop_location_name": str(stop_name),
                        "reason": reason,
                        "stop_reason": "hostile_presence",
                        "authority": "engine",
                    },
                    intermediate_destination_id=stop,
                    intermediate_destination_name=stop_name,
                )
            if verdict == "unvisited_stop":
                stop = engine.get("stop")
                fresh = [
                    {"id": loc, "name": place_name(loc)}
                    for loc in engine.get("fresh") or []
                ]
                if stop is None and not fresh:
                    return finish(
                        False,
                        "No route reaches that place from here through places "
                        "the party can travel now.",
                        reason_code="no_valid_route",
                        facts={
                            "requested_destination_id": str(new_location_id),
                            "route_reason": "no reachable place on the way",
                            "must_not_move": True,
                            "authority": "engine",
                        },
                    )
                stop_name = place_name(stop) if stop else ""
                reason = (
                    "the way to %s crosses places the party has not visited; "
                    "the party stops at each one first"
                    % place_name(new_location_id)
                )
                return finish(
                    False,
                    "[TRAVEL SYSTEM] Travel stops early: %s." % reason,
                    reason_code="unvisited_stop",
                    facts={
                        "original_destination_id": str(new_location_id),
                        "stop_location_id": str(stop or ""),
                        "stop_location_name": str(stop_name),
                        "reachable_unvisited": fresh,
                        "reason": reason,
                        "authority": "engine",
                    },
                    intermediate_destination_id=stop or "",
                    intermediate_destination_name=stop_name,
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
                authority="engine",
                travel_minutes=engine.get("minutes"),
            )
            travel_minutes = plan.travel_minutes
            return finish(
                True,
                "",
                plan,
                reason_code="approved",
                facts={
                    "module": current_module,
                    "destination_location_id": str(new_location_id),
                    "destination_location_name": nodes[new_location_id]["location_name"],
                    "destination_area_id": nodes[new_location_id]["area_id"],
                    "destination_area_name": nodes[new_location_id]["area_name"],
                    # Never ticks: the validator read raw route ticks as
                    # minutes (C10b live run). The trip time is given in
                    # game minutes (C11).
                    "engine_route": {"stops": engine.get("stops")},
                    **(
                        {
                            "travel_minutes": travel_minutes,
                            "min_travel_minutes": _travel.floor_minutes(travel_minutes),
                            "travel_time_rule": (
                                "travel_minutes is the trip at SRD normal pace, in game "
                                "minutes: use it as the travel-owned updateTime. A slow "
                                "pace, difficult terrain or a detour adds time. Only a "
                                "fast pace the narration shows (the party hurries) may "
                                "go lower, to min_travel_minutes. The code applies at "
                                "least min_travel_minutes and raises a lower value "
                                "itself."
                            ),
                        }
                        if travel_minutes is not None
                        else {}
                    ),
                    "authority": "engine",
                    "provisional_until_semantic_validation": True,
                },
            )

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

        # Explicit absence is meaningful: an engine-authored followup is not
        # fresh player intent (#193 D-NPC-PARTY-3). Preserve older callers that
        # do not supply turn_context; the shared reviewer supplies it always.
        player_request = ""
        if turn_context is not None:
            player_request = turn_context.get("player_input")
        else:
            for msg in reversed(conversation_history):
                words = hm.player_input(msg)
                if words:
                    player_request = words
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
            detached_context=detached_context,
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
            facts={
                "module": current_module,
                "destination_location_id": str(new_location_id),
                "destination_location_name": snapshot["nodes"][new_location_id]["location_name"],
                "destination_area_id": snapshot["nodes"][new_location_id]["area_id"],
                "destination_area_name": snapshot["nodes"][new_location_id]["area_name"],
                "path": list(path),
                "provisional_until_semantic_validation": True,
            },
        )

    except (InvocationSupersededError, LiveProviderSuperseded):
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
    if any(item["kind"] == "busy" for item in snapshot.get("read_errors", [])):
        # Preserve the typed temporary-read outcome for the caller's unlocked
        # reread; it is not evidence that the candidate route changed.
        import errno
        raise OSError(errno.EAGAIN, "Travel records are temporarily busy")
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
    from utils import quest_record as _quest_record

    plot_data = _quest_record.module_plot(current_module) or {}
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

def _recruit_identity(party, occupant_id):
    """The authored record of the person a recruit's occupant id names, read
    before the occupant is resolved as joined (#534); None when there is none."""
    from core.nql import occupants as _occupants

    return _occupants.person_identity(str(party.get("module") or ""), str(occupant_id or ""))


# Party companions by occupant id -------------------------------------------
#
# Every partyNPCs entry carries the occupant id of its person ("occupantId").
# One planner decides what an updatePartyNPCs does, by ids, slot numbers and
# entry equality only; one line builder assembles its engine lines; one
# finishing step builds the sheet at commit; occupants.party_change sends the
# lines. A row saved before ids has none: the party line numbers those rows
# as [slot n], counted from the roster the turn's DM note showed.

_PARTY_ERROR_TAIL = (
    "Later actions from this response have not executed. Do not repeat "
    "earlier completed actions."
)


def turn_key(invocation_claim):
    """The turn identity a TurnRoster pair is keyed by ("" without one)."""
    return str(getattr(invocation_claim, "logical_invocation_id", "") or "").strip()


def _current_roster():
    party = safe_json_load("party_tracker.json")
    roster = party.get("partyNPCs") if isinstance(party, dict) else None
    return copy.deepcopy(roster) if isinstance(roster, list) else []


class TurnRoster:
    """The roster a turn's slot numbers count from: one (key, roster) pair.

    The DM note build records the roster it rendered; bind() pairs it with
    the turn's logical invocation id when the turn claim begins (the current
    roster when no note rendered one). get() answers every response of that
    turn, its needs_response follow-ups included, from the pair; a key with
    no pair binds the current roster in its place. Nothing is kept under an
    empty key. Load, restore and reset clear it."""

    _lock = threading.Lock()
    _pair = None
    _rendered = None

    @classmethod
    def record(cls, roster):
        with cls._lock:
            cls._rendered = copy.deepcopy(roster) if isinstance(roster, list) else None

    @classmethod
    def bind(cls, key):
        with cls._lock:
            roster, cls._rendered = cls._rendered, None
            if roster is None:
                roster = _current_roster()
            if key:
                cls._pair = (key, roster)
            return copy.deepcopy(roster)

    @classmethod
    def get(cls, key):
        with cls._lock:
            if key and cls._pair is not None and cls._pair[0] == key:
                return copy.deepcopy(cls._pair[1])
            roster = _current_roster()
            if key:
                cls._pair = (key, roster)
            return copy.deepcopy(roster)

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._pair = None
            cls._rendered = None


def _row_id(entry):
    oid = entry.get("occupantId") if isinstance(entry, dict) else None
    return oid if isinstance(oid, str) and oid else ""


def _roster_ids(roster):
    return {_row_id(entry) for entry in roster or [] if _row_id(entry)}


def _turn_rows(turn_roster, roster):
    """The roster that numbers the [slot] rows: the turn's roster, or, when
    there is none, the roster being rendered or resolved. Every renderer and
    the slot resolver take it from here, so they number alike."""
    return roster if turn_roster is None else turn_roster


def _roster_slot(value):
    """A rosterSlot as a number: an integer, or a string of ASCII digits;
    None for anything else."""
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        return int(value.strip())
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _slot_numbers(turn_roster):
    """[(entry, n)]: the turn roster's rows without an id, numbered from 1."""
    slots = []
    for entry in turn_roster or []:
        if isinstance(entry, dict) and not _row_id(entry):
            slots.append((entry, len(slots) + 1))
    return slots


def party_rows(roster, turn_roster):
    """Each row as the party line shows it: "Name (role) [occ:...]", or
    "Name (role) [slot n]" numbered from the turn roster ("Name (role)" for
    a row without an id that the turn roster does not hold)."""
    slots = _slot_numbers(turn_roster)
    used = set()
    rows = []
    for entry in roster or []:
        if not isinstance(entry, dict):
            continue
        text = "%s (%s)" % (entry.get("name"), entry.get("role"))
        if _row_id(entry):
            rows.append("%s [%s]" % (text, _row_id(entry)))
            continue
        number = next((n for e, n in slots if n not in used and e == entry), None)
        if number is not None:
            used.add(number)
            text += " [slot %d]" % number
        rows.append(text)
    return rows


def party_note_lines(party_tracker, world, turn_roster, *, record=False):
    """(party_span, orphan_sentence) for the DM note, the validator and the
    corrections: "Party NPCs: <rows>." and, whenever joined people of this
    module are carried by no roster row, the sentence that goes
    after Party stats ("" when there are none). Only the DM note build
    passes record=True, which keeps the rendered roster for TurnRoster."""
    from core.nql import occupants as _occupants

    party = party_tracker if isinstance(party_tracker, dict) else {}
    roster = party.get("partyNPCs")
    roster = roster if isinstance(roster, list) else []
    if record:
        TurnRoster.record(roster)
    rows = party_rows(roster, _turn_rows(turn_roster, roster))
    span = "Party NPCs: %s." % (", ".join(rows) if rows else "None")
    orphans = _occupants.party_orphans(world, str(party.get("module") or ""), _roster_ids(roster))
    if not orphans:
        return span, ""
    listed = "; ".join("%s (%s)" % (o.get("id"), o.get("name")) for o in orphans)
    if any(isinstance(entry, dict) and not _row_id(entry) for entry in roster):
        sentence = (
            " Joined people with no party id (each may be the world person of a [slot] "
            "companion above): %s. When a [slot] companion who is one of them leaves, pass "
            "that id with the slot. Use returnOccupant only for someone who already left "
            "the party in the story and is not a [slot] companion." % listed
        )
    else:
        sentence = (
            " Joined people with no party id: %s. Use returnOccupant for someone who already "
            "left the party in the story, or add them again by id if they are with the party."
            % listed
        )
    return span, sentence


def _party_error(operation, text):
    """A refused updatePartyNPCs as the DM is told it (with the standard tail)."""
    return "Party Error: updatePartyNPCs %s did not complete: %s Nothing changed in the party roster. %s" % (
        operation if operation in ("add", "remove") else "change", text, _PARTY_ERROR_TAIL,
    )


def _party_sheet_path(module, name, *, wait=None):
    """The sheet path a companion name resolves to (the name lookup the
    sheets already use; the sheet gate keeps it one-to-one). With ``wait``,
    a busy sheet or listing waits (P3a)."""
    from updates.update_character_info import find_character_file_fuzzy, normalize_character_name

    name = str(name or "")
    path_manager = ModulePathManager(str(module or "").replace(" ", "_"))
    return path_manager.get_character_path(
        find_character_file_fuzzy(name, wait=wait) or normalize_character_name(name)
    )


def _party_id_suffix(invocation_claim, action_context):
    """c<t>i<k> for an id built while no world can be read: t the first 8
    characters of the hex after the last ":" of the turn's logical
    invocation id (a fresh uuid hex without one), k the action index."""
    turn_id = turn_key(invocation_claim)
    hex_part = turn_id.rpartition(":")[2][:8] if turn_id else uuid4().hex[:8]
    index = (action_context or {}).get("current_index") if isinstance(action_context, dict) else None
    return "c%si%d" % (hex_part, index if isinstance(index, int) else 0)


def _new_party_id(name, module, location, world, taken, id_suffix):
    """A new person's id here: the name's slug at this place (-2, -3 ... when
    taken); with no world, the slug with the typed suffix."""
    from core.nql import occupants as _occupants
    from utils.roster_conversion import slug

    place = _occupants.place_id(module, location or "unplaced")
    taken = set(taken) | {
        o.get("id") for o in (world or {}).get("occupants") or [] if isinstance(o, dict)
    }
    stem = slug(name)
    if world is None:
        stem = "%s-%s" % (stem, id_suffix or "c%si0" % uuid4().hex[:8])
    return _occupants._unique_id(place, stem, taken)


def build_lines(kind, occupant_id, display_name, module, location, world, *, reason=None):
    """The engine lines of one planned party change, the only place they
    are assembled: at plan time, and at a staged commit with the stored
    kind. A join resolves the person as joined (a "new" one is created here
    first); a re-add of a companion whose person was left behind (present,
    not joined) joins it again. A leave brings the person back here: an id
    of another module creates a new person here (that module's person stays
    joined); a joined person returns with its join reason, moved here when
    elsewhere; a person present but not joined is moved here; a person with
    another recorded fate gets no line (the fate stands); an id the world
    does not hold is created here."""
    from core.nql import occupants as _occupants
    from utils.roster_conversion import q

    oid = str(occupant_id or "")
    if not oid:
        return []
    place = _occupants.place_id(module, location or "unplaced")
    why = _occupants._reason(reason)
    join = "resolve occupant %s as joined%s;" % (q(oid), " because %s" % q(why) if why else "")

    def create(ident):
        return "create occupant %s named %s at %s { person; attitude friendly; };" % (
            q(ident), q(str(display_name or "")), q(place))

    def move():
        return "move occupant %s to %s;" % (q(oid), q(place))

    occupant = _occupants.world_occupant(world, oid)
    if kind == "noop":
        if occupant is not None and occupant.get("count") != 0 and _occupants.joined_entry(occupant) is None:
            return [join]
        return []
    if kind == "join":
        return [join]
    if kind == "join_new":
        return [create(oid), join]
    if kind != "leave":
        return []
    if not oid.startswith("occ:%s/" % str(module or "").replace(" ", "_")):
        return [create(_new_party_id(display_name, module, location, world, (), None))]
    if occupant is None:
        return [create(oid)]
    entry = _occupants.joined_entry(occupant)
    if entry is not None:
        lines = ["return occupant %s from joined%s;" % (
            q(oid), " %s" % q(entry["reason"]) if entry.get("reason") else "")]
        if occupant.get("location") != place:
            lines.append(move())
        return lines
    if occupant.get("count") != 0 and occupant.get("location") != place:
        return [move()]
    return []


def plan_party_change(roster_before, parameters, world, *, turn_roster, module, location,
                      request_id, id_suffix=None, frozen_kind=None):
    """What one updatePartyNPCs does, decided by ids, slot numbers and entry
    equality only, with no write: exactly one outcome {"kind": "noop" |
    "join" | "heal" | "leave" | "correction", ...}. "outcome_kind" is the
    stored kind ("join_new" for an add of "new"). `world` is the engine
    document (party_world), or None when neither the engine nor
    live_state.json can be read. `turn_roster` numbers the [slot] rows.
    `id_suffix` is the typed suffix of an id built with no world. With
    `frozen_kind` (a staged commit) nothing is validated: the stored kind and
    occupant id give the engine lines at this location."""
    from core.nql import occupants as _occupants

    p = parameters if isinstance(parameters, dict) else {}
    operation = p.get("operation")
    npc = p.get("npc") if isinstance(p.get("npc"), dict) else {}
    context = p.get("lifecycleContext")
    reason = context.get("reason") if isinstance(context, dict) else None
    roster = [entry for entry in roster_before] if isinstance(roster_before, list) else []
    turn_roster = _turn_rows(turn_roster, roster)
    oid = p.get("occupantId")
    oid = oid.strip() if isinstance(oid, str) else ""
    base = {
        "roster_before": copy.deepcopy(roster),
        "roster_after": copy.deepcopy(roster),
        "turn_roster": copy.deepcopy(turn_roster),
        "request_id": request_id,
        "module": module,
        "location": location,
        "reason": reason,
        "engine_lines": [],
    }

    def outcome(kind, outcome_kind, **fields):
        result = dict(copy.deepcopy(base), kind=kind, outcome_kind=outcome_kind)
        result.update(fields)
        return result

    def refused(text):
        return outcome("correction", None, text=text)

    def lines(kind, ident, name):
        return build_lines(kind, ident, name, module, location, world, reason=reason)

    if frozen_kind is not None:
        name = npc.get("name")
        return outcome("join" if frozen_kind == "join_new" else frozen_kind, frozen_kind,
                       occupant_id=oid or None, display_name=name,
                       engine_lines=lines(frozen_kind, oid, name))

    carried = _roster_ids(roster)
    if operation == "add":
        name = str(npc.get("name") or "")
        if oid and oid in carried:
            # Already on the roster by this id: a silent no-op (#534).
            row = next(entry for entry in roster if _row_id(entry) == oid)
            return outcome("noop", "noop", occupant_id=oid, display_name=row.get("name"),
                           engine_lines=lines("noop", oid, row.get("name")))
        module_key = str(module or "").replace(" ", "_")
        prefix = "occ:%s/" % module_key
        parts = oid[len(prefix):].split("/") if oid.startswith(prefix) else []
        if oid != "new" and not (len(parts) == 2 and all(parts)):
            return refused(_not_recruitable(oid, world, module, location))
        npc_path = _party_sheet_path(module, name)
        for entry in roster:
            if isinstance(entry, dict) and entry.get("name") and \
                    _party_sheet_path(module, entry["name"]) == npc_path:
                return refused(_already_with_party(name, entry, turn_roster))
        sheet = safe_json_load(npc_path) if os.path.exists(npc_path) else None
        display_name = (sheet.get("name") if isinstance(sheet, dict) else None) or name
        role = npc.get("role", npc.get("class", "Companion"))

        def joined(kind, outcome_kind, ident, engine_lines):
            entry = {"name": display_name, "role": role, "occupantId": ident}
            return outcome(kind, outcome_kind, roster_after=copy.deepcopy(roster) + [entry],
                           entry=copy.deepcopy(entry), occupant_id=ident,
                           display_name=display_name, npc_path=npc_path,
                           engine_lines=engine_lines)

        if oid == "new":
            ident = _new_party_id(name, module, location, world, carried, id_suffix)
            return joined("join", "join_new", ident, lines("join_new", ident, display_name))
        if world is None:
            # An engine outage never stops the roster: a well-formed id is
            # taken as given.
            return joined("join", "join", oid, lines("join", oid, display_name))
        occupant = _occupants.world_occupant(world, oid)
        if occupant is not None and occupant.get("kind") == "person" and occupant.get("count") != 0 \
                and str(occupant.get("location") or "").startswith("loc:%s/" % module_key):
            return joined("join", "join", oid, lines("join", oid, display_name))
        if occupant is not None and any(o.get("id") == oid for o in _occupants.party_orphans(world, module, carried)):
            # A joined person no row carries: the row is written, the world
            # already has them joined.
            return joined("heal", "heal", oid, [])
        return refused(_not_recruitable(oid, world, module, location))

    if operation == "remove":
        slot = _roster_slot(p.get("rosterSlot"))
        listing = " " + "".join(party_note_lines({"partyNPCs": roster, "module": module}, world, turn_roster))
        carrier = next((entry for entry in roster if oid and _row_id(entry) == oid), None)
        if carrier is not None:
            if slot is not None:
                warning("PARTY: rosterSlot %s ignored; %s is carried by a roster row" % (slot, oid),
                        category="character_updates")
            removed, ident = carrier, oid
        elif slot is not None:
            removed = next((entry for entry, n in _slot_numbers(turn_roster) if n == slot), None)
            if removed is None or removed not in roster:
                slot_rows = party_rows([entry for entry in roster if not _row_id(entry)], turn_roster)
                return refused("No companion in the party is [slot %d] now. Companions with a [slot]: %s."
                               % (slot, ", ".join(slot_rows) or "none"))
            if oid:
                orphan_ids = {o.get("id") for o in _occupants.party_orphans(world, module, carried)}
                if world is not None and oid not in orphan_ids:
                    return refused("%s is not one of the joined people with no party id. Pass rosterSlot "
                                   "alone for that companion, or with an id from that list.%s" % (oid, listing))
                ident = oid
            else:
                ident = _new_party_id(removed.get("name"), module, location, world, carried, id_suffix)
        elif oid:
            return refused(
                "No companion in the party carries %s. For a companion shown with a [slot], pass "
                "rosterSlot (and this id if it is that companion's person). To return someone who "
                "already left the party in the story, use returnOccupant.%s" % (oid, listing))
        else:
            return refused("A remove names the companion by the occupantId or the rosterSlot the "
                           "party line shows.%s" % listing)
        roster_after = copy.deepcopy(roster)
        roster_after.remove(removed)
        name = removed.get("name")
        return outcome("leave", "leave", roster_after=roster_after, removed_entry=copy.deepcopy(removed),
                       occupant_id=ident, display_name=name, npc_path=_party_sheet_path(module, name),
                       engine_lines=lines("leave", ident, name))

    # Neither add nor remove changes nothing, as before.
    return outcome("noop", "noop", occupant_id=None)


def party_change_companion(parameters, roster, turn_roster):
    """The companion an updatePartyNPCs names, for the review facts: the
    added npc's name, or the name of the roster row a remove's occupantId
    or rosterSlot points at (the npc's name when neither is found)."""
    p = parameters if isinstance(parameters, dict) else {}
    npc = p.get("npc") if isinstance(p.get("npc"), dict) else {}
    if p.get("operation") == "remove":
        oid = p.get("occupantId")
        row = next((entry for entry in roster or [] if oid and _row_id(entry) == oid), None)
        slot = _roster_slot(p.get("rosterSlot"))
        if row is None and slot is not None:
            row = next((entry for entry, n in _slot_numbers(_turn_rows(turn_roster, roster)) if n == slot), None)
        if isinstance(row, dict) and row.get("name"):
            return row["name"]
    return npc.get("name")


def _not_recruitable(oid, world, module, location):
    from core.nql import occupants as _occupants

    place = _occupants.place_id(module, location)
    people = [
        o for o in (world or {}).get("occupants") or []
        if isinstance(o, dict) and o.get("kind") == "person" and o.get("location") == place
        and o.get("count") != 0
    ]
    listed = "; ".join("%s (%s)" % (o.get("id"), o.get("name")) for o in people) or "none"
    return (
        "%s is not a person you can recruit here. People present: %s. Pass one of those ids, "
        "or \"new\" for a companion who is not listed." % (oid or "(no occupantId)", listed)
    )


def _already_with_party(name, entry, turn_roster):
    row = (party_rows([entry], turn_roster) or [""])[0]
    return (
        "%s is already with the party (%s). No add is needed. To recruit a different person, "
        "give them a distinct name." % (name, row)
    )


def _build_party_sheet(npc, name, party, identity):
    """Build a companion's sheet in process (T035), as the travel path and
    combat_builder build (#534), by the npc_builder.py command's argument
    rules: a placeholder is blank, and a level other than a whole number
    builds no sheet. The level defaults to the party's. Raises when no sheet
    was accepted."""
    from core.generators.npc_builder import UNSPECIFIED_ARGUMENTS, build_npc_file, load_schema
    from updates.update_character_info import normalize_character_name

    path_manager = ModulePathManager(str(party.get("module") or "").replace(" ", "_"))
    default_level = ""
    if not npc.get("level") and party.get("partyMembers"):
        player_file = path_manager.get_character_path(
            normalize_character_name(str(party["partyMembers"][0]))
        )
        if os.path.exists(player_file):
            try:
                player_data = safe_json_load(player_file)
                if player_data and "level" in player_data:
                    default_level = str(player_data["level"])
                    debug(f"STATE_CHANGE: Using party level {default_level} as default for NPC {name}", category="character_updates")
            except Exception as e:
                warning(f"FAILURE: Could not get party level, using default: {e}", category="character_updates")
    npc_level = str(npc.get("level") or default_level)

    def _given(value):
        text = str(value)
        return "" if text.strip().lower() in UNSPECIFIED_ARGUMENTS else text

    level_text = _given(npc_level)
    level = None
    if level_text:
        if not level_text.isdigit():
            raise ValueError(f"level {npc_level!r} is not a whole number")
        level = int(level_text)
    debug(f"STATE_CHANGE: Building NPC {name}: {npc.get('race', '')} {npc.get('class', '')} {npc_level} {npc.get('background', '')}", category="character_updates")
    schema = load_schema("schemas/char_schema.json")
    if not schema:
        raise RuntimeError("NPC character schema is unavailable")
    sheet = build_npc_file(
        name,
        schema,
        _given(npc.get("race", "")),
        _given(npc.get("class", "")),
        level,
        str(npc.get("background", "")),
        path_manager=path_manager,
        npc_identity=identity,
    )
    if not isinstance(sheet, dict):
        raise RuntimeError("no sheet was accepted")
    info(f"SUCCESS: NPC profile created for {name}", category="character_updates")
    return sheet


def finish_party_entry(outcome, parameters, *, party):
    """The one finishing step of a join or heal, run at commit on every path
    (in place, a staged prepare, an adapted receipt), never in a projection:
    build the sheet when none exists (T035; an existing sheet is never
    rebuilt), take the entry name from the sheet's own name, and run the
    sheet gate again on a built sheet's path. Returns the finished outcome,
    or a correction when the built sheet is already a companion's (it stays
    as an unbound sheet). Raises when no sheet could be built."""
    if not isinstance(outcome, dict) or outcome.get("kind") not in ("join", "heal"):
        return outcome
    finished = copy.deepcopy(outcome)
    module = finished.get("module")
    path = finished.get("npc_path") or _party_sheet_path(module, finished.get("display_name"))
    if not os.path.exists(path):
        p = parameters if isinstance(parameters, dict) else {}
        npc = p.get("npc") if isinstance(p.get("npc"), dict) else {}
        name = str(npc.get("name") or finished.get("display_name") or "")
        identity = None
        if finished.get("outcome_kind") != "join_new":
            identity = _recruit_identity(party, finished.get("occupant_id"))
        sheet = _build_party_sheet(npc, name, party, identity)
        built_name = sheet.get("name") or name
        path = _party_sheet_path(module, built_name)
        for entry in finished.get("roster_before") or []:
            if isinstance(entry, dict) and entry.get("name") and _party_sheet_path(module, entry["name"]) == path:
                finished.update(kind="correction", outcome_kind=None, engine_lines=[],
                                roster_after=copy.deepcopy(finished.get("roster_before") or []),
                                text=_already_with_party(built_name, entry, finished.get("turn_roster")))
                return finished
    sheet = safe_json_load(path) if os.path.exists(path) else None
    name = (sheet.get("name") if isinstance(sheet, dict) else None) or finished.get("display_name")
    if name != finished.get("display_name"):
        debug(f"STATE_CHANGE: Using character file name '{name}' for party tracker", category="character_updates")
    finished["display_name"] = name
    finished["npc_path"] = path
    finished["sheet"] = copy.deepcopy(sheet) if isinstance(sheet, dict) else None
    finished["entry"]["name"] = name
    finished["roster_after"] = copy.deepcopy(finished.get("roster_before") or []) + [copy.deepcopy(finished["entry"])]
    if finished.get("outcome_kind") == "join_new":
        # The created person takes the companion's final name.
        finished["engine_lines"] = build_lines(
            "join_new", finished.get("occupant_id"), name, module, finished.get("location"), None,
            reason=finished.get("reason"),
        )
    return finished


def update_party_npcs(party_tracker_data, parameters, *, turn_roster, request_id, id_suffix=None):
    """The in-place updatePartyNPCs: plan it on the world, finish a join or
    heal (its sheet) and write the roster. Returns the outcome (the caller
    fires its hooks by kind and sends its engine lines), or None only when
    an add's character sheet could not be built (nothing changed)."""
    from core.nql import occupants as _occupants

    module = str(party_tracker_data.get("module") or "")
    location = str((party_tracker_data.get("worldConditions") or {}).get("currentLocationId") or "")
    roster = party_tracker_data.get("partyNPCs")
    world = _occupants.party_world(module, location)
    outcome = plan_party_change(
        roster if isinstance(roster, list) else [], parameters, world,
        turn_roster=turn_roster, module=module, location=location,
        request_id=request_id, id_suffix=id_suffix,
    )
    if outcome["kind"] in ("join", "heal"):
        try:
            outcome = finish_party_entry(outcome, parameters, party=party_tracker_data)
        except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
            # A superseded live turn ends the turn by its own handler (#893).
            raise
        except Exception as e:
            error(f"FAILURE: Failed to create NPC profile for {outcome.get('display_name')}: {e}", category="character_updates")
            return None
    if outcome["kind"] in ("join", "heal", "leave"):
        party_tracker_data["partyNPCs"] = copy.deepcopy(outcome["roster_after"])
        safe_json_dump(party_tracker_data, "party_tracker.json")
        info(f"STATE_CHANGE: Party NPCs updated - {outcome['kind']} {outcome.get('display_name')} ({outcome.get('occupant_id')})", category="character_updates")
    return outcome


def _party_receipt(outcome, parameters, operation_id):
    path = outcome.get("npc_path") or ""
    sheet = outcome.get("sheet")
    if sheet is None and path and os.path.exists(path):
        sheet = safe_json_load(path)
    return {
        "kind": "updatePartyNPCs",
        "operation_id": operation_id,
        "phase": "sheet_ready",
        "operation": parameters.get("operation"),
        "npc_name": outcome.get("display_name"),
        "npc_path": path,
        "sheet": copy.deepcopy(sheet) if isinstance(sheet, dict) else None,
        "roster_before": copy.deepcopy(outcome["roster_before"]),
        "roster_after": copy.deepcopy(outcome["roster_after"]),
        "lifecycle_context": copy.deepcopy(parameters.get("lifecycleContext")),
        "lifecycle_status": "pending",
        "occupant_id": outcome.get("occupant_id"),
        "outcome_kind": outcome.get("outcome_kind"),
    }


class PartyChangeUnplanned(ValueError):
    """A staged updatePartyNPCs that cannot be worked out (a malformed
    request or a planner correction), as opposed to a sheet that could not
    be made."""


def prepare_party_npc_update(parameters, operation_id):
    """Freeze one roster change, planned like the in-place one, and its
    canonical sheet before movement. The engine lines are built at apply,
    at the commit location, from the receipt's frozen fields."""
    from core.nql import occupants as _occupants

    operation = parameters.get("operation")
    if operation not in {"add", "remove"}:
        raise PartyChangeUnplanned("updatePartyNPCs requires add or remove")
    if operation == "add":
        npc = parameters.get("npc")
        npc_name = npc.get("name") if isinstance(npc, dict) else None
        if not isinstance(npc_name, str) or not npc_name.strip():
            raise PartyChangeUnplanned("updatePartyNPCs add requires an exact NPC name")
        from updates.update_character_info import name_refusal
        refusal = name_refusal(npc_name)
        if refusal:
            raise PartyChangeUnplanned(f"updatePartyNPCs add refused: {refusal}")
    party = safe_json_load("party_tracker.json")
    if not isinstance(party, dict) or not isinstance(party.get("partyNPCs"), list):
        raise RuntimeError("party roster is unavailable")
    roster_before = copy.deepcopy(party["partyNPCs"])
    module = str(party.get("module") or "")
    location = str((party.get("worldConditions") or {}).get("currentLocationId") or "")
    world = _occupants.party_world(module, location, create=False)
    outcome = plan_party_change(
        roster_before, parameters, world, turn_roster=roster_before,
        module=module, location=location, request_id="dm:%s:party" % operation_id,
    )
    if outcome["kind"] in ("join", "heal"):
        outcome = finish_party_entry(outcome, parameters, party=party)
    if outcome["kind"] == "correction":
        raise PartyChangeUnplanned(outcome["text"])
    return _party_receipt(outcome, parameters, operation_id)


def _adapt_party_receipt(receipt, party, record_index, checkpoint_operation_id=None):
    """A receipt staged before occupant ids (no outcome_kind), adapted
    through the planner at the commit location: the added row (the
    roster_after entry absent from roster_before, by equality) as an add of
    "new"; the removed row (the roster_before entry absent from
    roster_after) as a leave with no link, so a new person is created here;
    no difference: a noop. The receipt takes the finished fields in place;
    when the adapted roster_after differs, the old one is kept as
    legacy_roster_after, the roster the old code may already have written.
    A fallback id takes <t> from the checkpoint's operation id. Returns
    False for a correction (the receipt is then dropped)."""
    from core.nql import occupants as _occupants

    before = receipt.get("roster_before") if isinstance(receipt.get("roster_before"), list) else []
    after = receipt.get("roster_after") if isinstance(receipt.get("roster_after"), list) else []
    added = [entry for entry in after if entry not in before]
    removed = [entry for entry in before if entry not in after]
    module = str(party.get("module") or "")
    location = str((party.get("worldConditions") or {}).get("currentLocationId") or "")
    context = receipt.get("lifecycle_context")
    if receipt.get("operation") == "add" and added and isinstance(added[0], dict):
        parameters = {"operation": "add", "occupantId": "new",
                      "npc": {"name": added[0].get("name"), "role": added[0].get("role")},
                      "lifecycleContext": context}
    elif receipt.get("operation") == "remove" and removed:
        slot = next((n for entry, n in _slot_numbers(before) if entry == removed[0]), None)
        if slot is None:
            return False
        parameters = {"operation": "remove", "rosterSlot": slot, "lifecycleContext": context}
    else:
        receipt.update(occupant_id=None, outcome_kind="noop", engine_lines=[])
        return True
    world = _occupants.party_world(module, location, create=False)
    op_hex = str(checkpoint_operation_id or "").replace("-", "")[:8]
    outcome = plan_party_change(
        before, parameters, world, turn_roster=before, module=module, location=location,
        request_id="dm:%s:party" % receipt.get("operation_id"),
        id_suffix="c%si%d" % (op_hex, record_index) if op_hex else None,
    )
    if outcome["kind"] in ("join", "heal"):
        outcome = finish_party_entry(outcome, parameters, party=party)
    if outcome["kind"] == "correction":
        warning("TRAVEL: a staged party change from before occupant ids could not be "
                "adapted; dropped: %s" % outcome.get("text"), category="location_transitions")
        return False
    if outcome["roster_after"] != after:
        receipt["legacy_roster_after"] = copy.deepcopy(after)
    receipt.update(
        occupant_id=outcome.get("occupant_id"),
        outcome_kind=outcome.get("outcome_kind"),
        roster_after=copy.deepcopy(outcome["roster_after"]),
        npc_name=outcome.get("display_name"),
        npc_path=outcome.get("npc_path") or receipt.get("npc_path"),
        engine_lines=list(outcome.get("engine_lines") or []),
    )
    return True


def _apply_party_npc_lifecycle(
    party_tracker_data,
    operation,
    npc_name,
    npc_file,
    lifecycle_context,
    source_turn_id,
    *,
    seed_profile=True,
):
    """Best-effort post-commit lifecycle hook; never rolls back the roster.
    seed_profile=False (a heal: the row of a person who already joined) marks
    the arrival without seeding the T107 profile."""
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
            before_arrival = store.snapshot()
            before_identity = before_arrival["identities"].get(npc_id, {})
            before_lifecycle = before_arrival["lifecycle"].get(npc_id, {})
            before_events = before_lifecycle.get("events", [])
            source_already_committed = bool(
                source_turn_id
                and before_events
                and before_events[-1].get("kind") in {"join", "rejoin"}
                and before_events[-1].get("sourceTurnId") == source_turn_id
                and before_identity.get("active") is True
            )
            arrival = (
                store.mark_rejoined
                if before_identity.get("active") is False
                or before_lifecycle.get("status") == "inactive"
                else store.mark_joined
            )
            arrival(
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
            if seed_profile:
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
            final_event = events[-1] if events else {}
            complete = (
                identity.get("active") is True
                and edge_key in final["relationships"]
                and (npc_id in final["profiles"] or not seed_profile)
                and final_event.get("kind") in {"join", "rejoin"}
                and final_event.get("sourceTurnId") == source_turn_id
                and (
                    final["revision"] > starting_revision
                    or source_already_committed
                )
            )
        else:
            complete = (
                identity.get("active") is False
                and bool(events)
                and events[-1].get("kind") == "depart"
            )
        if not complete:
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

def get_module_starting_location(module_name: str, snapshot=None) -> tuple:
    """Get the starting location for a module using AI analysis with caching.

    snapshot: the module's build_active_module_snapshot, when the caller
    already holds it; a model-chosen start is checked against it (#308)."""
    try:
        # The entry the module declares, when it resolves in its area files,
        # comes before a cached or model-chosen one.
        from utils import roster_conversion

        path_manager = ModulePathManager(module_name)
        declared = roster_conversion.declared_start(path_manager.module_dir)
        if declared and declared["areaId"] in (path_manager.get_area_ids() or []):
            area_data = safe_json_load(path_manager.get_area_path(declared["areaId"])) or {}
            locations = area_data.get("locations") if isinstance(area_data, dict) else None
            location = next((loc for loc in locations or [] if isinstance(loc, dict)
                             and loc.get("locationId") == declared["locationId"]), None)
            if location is not None and area_data.get("areaName") and location.get("name"):
                debug(f"FILE_OP: Using declared entry for {module_name}", category="module_loading")
                return (declared["locationId"], location["name"], declared["areaId"], area_data["areaName"])

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
            from utils import quest_record as _quest_record

            plot_data = _quest_record.module_plot(module_name)
            if plot_data:
                # Include key plot information
                module_analysis_data["plotData"] = {
                    "mainObjective": plot_data.get("mainObjective", ""),
                    "plotPoints": plot_data.get("plotPoints", [])  # All plot points
                }
        except Exception as e:
            warning(f"FILE_OP: Could not load plot data: {e}", category="file_operations")
        
        # Use AI to determine starting location
        starting_location, chosen_by = _ai_analyze_starting_location(module_analysis_data)
        if chosen_by == "model":
            resolved, reason = _resolved_model_start(module_name, starting_location, snapshot)
            if resolved is None:
                why = (f"the model's start {starting_location[2]}:{starting_location[0]} "
                       f"for {module_name} {reason}")
                starting_location = _get_fallback_starting_location(module_analysis_data)
                chosen_by = "fallback"
            else:
                starting_location = resolved
        else:
            why = f"start analysis failed for {module_name}"
        if chosen_by == "fallback":
            # The fallback is code's own substitute, so it must be a start the
            # resolver accepts: checked against the snapshot, else the first
            # valid node (#821).
            starting_location, replaced = _checked_fallback(module_name, starting_location, snapshot)
            warning(f"STARTING_LOCATION: {why}; using {starting_location[2]}:{starting_location[0]} "
                    f"for this entry, not cached{replaced}", category="module_loading")

        # Cache only a start the model chose and the resolver accepts (#308):
        # a fallback is used once, and the model is asked again next entry.
        if chosen_by == "model" and world_registry:
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
            except ReadOnlySaveStop:
                raise
            except Exception as cache_err:
                # INT-H5: a cache-WRITE failure must not discard an already-valid
                # starting location and strand the player; log and continue.
                warning(f"FILE_OP: Could not cache starting location for {module_name}: {cache_err}", category="module_loading")

        return starting_location

    except ReadOnlySaveStop:
        raise
    except Exception as e:
        # INT-H5: recover a REAL location from the module's area files rather
        # than writing placeholder IDs (A01/AREA001) that resolve to no area
        # file and strand the player at a non-existent location. It is checked
        # against the snapshot like the other fallbacks (#821).
        real = _first_real_location_from_files(module_name)
        replaced = ""
        if real:
            try:
                real, replaced = _checked_fallback(module_name, real, snapshot)
            except ReadOnlySaveStop:
                raise
            except Exception:
                pass  # this route must not raise again; keep the file start
        cause = f"looking up the start for {module_name} raised {type(e).__name__}: {e}"
        if real:
            error(f"STARTING_LOCATION: {cause}; using {real[2]}:{real[0]} for this entry, "
                  f"not cached{replaced}", exception=e, category="module_loading")
            return real
        error(f"STARTING_LOCATION: {cause}; no real location in its files, using the placeholder "
              f"AREA001:A01", exception=e, category="module_loading")
        return ("A01", "Unknown Location", "AREA001", "Unknown Area")

def _resolved_model_start(module_name, start, snapshot=None):
    """(start, None) as the transition resolver would accept it: the
    location is a valid node of the module's snapshot, and the area and names
    come from that node. (None, reason) when it does not resolve or the
    snapshot cannot be read (#308)."""
    if snapshot is None:
        try:
            from utils.path_encounter_analyzer import build_active_module_snapshot
            snapshot = build_active_module_snapshot(module_name)
        except OSError as exc:
            return None, f"could not be checked ({exc})"
    location_id = str(start[0])
    node = (snapshot.get("nodes") or {}).get(location_id)
    if node is None or location_id in (snapshot.get("invalid_location_ids") or ()):
        return None, "is not a valid location of the module"
    return (node["location_id"], node["location_name"], node["area_id"], node["area_name"]), None


def _first_valid_snapshot_start(snapshot):
    """The first valid node of the snapshot, in its own order, as a start
    tuple; None when it has no valid node (#821)."""
    invalid = set(snapshot.get("invalid_location_ids") or ())
    for node in (snapshot.get("nodes") or {}).values():
        if node["location_id"] not in invalid:
            return (node["location_id"], node["location_name"], node["area_id"], node["area_name"])
    return None


def _checked_fallback(module_name, start, snapshot):
    """(start, replaced) for a start code chose itself: the node when it is a
    valid location of the snapshot, else the snapshot's first valid node, else
    the start unchanged. replaced names the start the first valid node took
    the place of, else "". No snapshot: (start, "") (#821)."""
    if snapshot is None:
        return start, ""
    checked, _ = _resolved_model_start(module_name, start, snapshot)
    if checked is not None:
        return checked, ""
    checked = _first_valid_snapshot_start(snapshot)
    if checked is None:
        return start, ""
    return checked, (f" (the first-area fallback {start[2]}:{start[0]} "
                     f"is not a valid location of the module)")


def _ai_analyze_starting_location(module_data: dict) -> tuple:
    """Use AI to analyze module data and determine the best starting location.

    Returns (start, "model") for the model's answer and (start, "fallback")
    for the first-location fallback (#308)."""
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
                ), "model"
            else:
                print(f"ERROR: AI response missing required fields: {result}")
                
        except json.JSONDecodeError as e:
            print(f"ERROR: Could not parse AI response as JSON: {e}")
            print(f"AI response was: {ai_response}")
        
        # Fallback to first area/location if AI analysis fails
        print("WARNING: AI analysis failed, falling back to first available location")
        return _get_fallback_starting_location(module_data), "fallback"
        
    except Exception as e:
        print(f"ERROR: AI starting location analysis failed: {e}")
        return _get_fallback_starting_location(module_data), "fallback"

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

def _engine_request_id(invocation_claim, action_context, suffix):
    """A deterministic engine request id for one typed occupant action of
    one accepted turn: dm:<turn id>:<action index>:<suffix>, so a retried
    turn is answered as already applied. Without a turn identity the id is
    unique instead (the action still runs; only replay protection is lost)."""
    turn_id = str(getattr(invocation_claim, "logical_invocation_id", "") or "").strip()
    index = (action_context or {}).get("current_index") if isinstance(action_context, dict) else None
    if not turn_id or not isinstance(index, int):
        return "dm:%s:%s" % (uuid4(), suffix)
    return "dm:%s:%d:%s" % (turn_id, index, suffix)


def _show_rest_receipt(content):
    """Show the player the hit dice the engine rolled on a short rest (#840)."""
    from web.shared_state import emit_player_output

    if emit_player_output({"type": "narration", "channel": "system", "content": content}) is not True:
        print(content)


# Shown to the player when a travel turn drops a change it could not work out
# (#855, the #841 voice).
_DROPPED_SHEET_NOTICE = (
    "%s's character sheet was not changed: the update could not be worked "
    "out. If it still matters (for example damage taken on the road), say so "
    "in your next message."
)
_DROPPED_STORAGE_NOTICE = (
    "%s's storage change was not made: it could not be worked out. If it "
    "still matters, say so in your next message."
)
_DROPPED_SHEET_RULES_NOTICE = (
    "%s's character sheet was not changed: the rules did not allow it (%s). "
    "If it still matters, say so in your next message."
)
_DROPPED_NPC_NOTICE = (
    "%s did not join the party: their character sheet could not be made. If "
    "it still matters, say so in your next message."
)
_UNPLANNED_NPC_NOTICE = (
    "%s did not join the party: the change could not be worked out. If it "
    "still matters, say so in your next message."
)
_DROPPED_NPC_LEAVE_NOTICE = (
    "%s did not leave the party: the change could not be worked out. If it "
    "still matters, say so in your next message."
)
# Raised from a travel prepare step, these are never a dropped change: the
# turn was superseded, the save is read-only, or the provider refused (#855).
_TRAVEL_PREPARE_PASSTHROUGH = (
    LiveProviderSuperseded,
    InvocationSupersededError,
    LiveProviderCompletedError,
    ReadOnlySaveStop,
)


def _retire_unmoved_transition_checkpoint(operation_id):
    """Remove this move's own checkpoint after its prepare step failed (#855).

    Only this operation's record, with the party still at its origin (the
    rule recovery uses for a planned move), is removed; anything else is left
    to recovery, with one warning.
    """
    from core.managers.campaign_manager import _party_module_transition_lock

    try:
        with _party_module_transition_lock():
            checkpoint = safe_json_load(PENDING_LOCATION_TRANSITION_FILE)
            party = safe_json_load("party_tracker.json")
            world = party.get("worldConditions") if isinstance(party, dict) else None
            if (
                isinstance(checkpoint, dict)
                and checkpoint.get("operation_id") == operation_id
                and checkpoint.get("kind") == "current_transition"
                and isinstance(world, dict)
                and str(world.get("currentLocationId", ""))
                == str(checkpoint.get("origin_location_id", ""))
            ):
                _remove_location_transition_checkpoint()
                return True
    except ReadOnlySaveStop:
        raise
    except OSError as exc:
        # #943: a locked or vanished file must not replace the curated
        # prepare failure; the record is left for recovery.
        warning(
            "TRAVEL: the failed move's record was left for recovery (could "
            "not read or remove it: %s: %s)" % (type(exc).__name__, exc),
            category="location_transitions",
        )
        return False
    warning(
        "TRAVEL: the failed move's record was left for recovery",
        category="location_transitions",
    )
    return False


def _travel_prepare_failure(exc):
    """The curated error for a move whose prepare step failed (#855)."""
    response_data = {
        "error_message": "The move could not be prepared; nothing changed.",
        "retryable": False,
        "transition_recovery_required": False,
    }
    if isinstance(exc, LiveProviderCompletedError):
        # A provider refusal (#240): its class picks the account text the
        # player can act on (#432), as on the direct path.
        refusal = classify_provider_error(exc)
        response_data["provider_refusal"] = refusal["category"]
        response_data["provider_refusal_provider"] = refusal["provider"]
    return response_data


def _show_transition_notice(message_id, content):
    """Show the player one travel notice (#855).

    A frontend sink gets it with its message id. A sink that rejects it gets
    no console copy: its stdout scraper would show an untracked duplicate
    (the combat_manager pattern). Only a plain terminal, with no sink, prints.
    """
    from web.shared_state import emit_player_output, has_player_output_sink

    has_sink = has_player_output_sink()
    if emit_player_output({
        "type": "narration",
        "channel": "system",
        "content": content,
        "message_id": message_id,
    }) is True:
        return
    if has_sink:
        warning(
            "TRAVEL: the frontend did not accept the travel notice",
            category="location_transitions",
        )
        return
    print(content)


# The turn whose fight already failed to start once (#444). It is only ever
# compared with the current turn's id, so a value left from an earlier turn
# is harmless.
_last_failed_combat_turn = None

# Why a fight did not start, as the DM is told it. Fixed phrases only: never
# raw error text, and nothing parses them.
COMBAT_START_REASONS = {
    "builder_failed": "the combat builder failed",
    "builder_no_encounter": "the combat builder did not save an encounter",
    "location_unreadable": "the current location could not be loaded",
    "combat_not_started": "the combat could not start",
}


def _combat_start_failed(reason, conversation_history, invocation_claim):
    """Close a createEncounter that ended without a finished fight (#444).

    The tracker decides. A fight still active there stays saved and resumes
    at the next start, so the turn ends with the one failure line ("error").
    When no fight was activated the DM is told once per turn and answers
    again ("needs_response"). A second failure in the same turn, a turn with
    no identity, or an unreadable tracker ends with the failure line, so this
    can never loop.
    """
    global _last_failed_combat_turn
    error(
        "FAILURE: Combat did not start: %s" % COMBAT_START_REASONS[reason],
        category="combat_processing",
    )
    party = safe_json_load("party_tracker.json")
    world = party.get("worldConditions") if isinstance(party, dict) else None
    turn_id = str(getattr(invocation_claim, "logical_invocation_id", "") or "").strip()
    if (
        not isinstance(world, dict)
        or world.get("activeCombatEncounter")
        or not turn_id
        or turn_id == _last_failed_combat_turn
    ):
        return {"status": "error", "needs_update": False}
    _last_failed_combat_turn = turn_id
    conversation_history.append({
        "role": "user",
        "content": (
            "Combat Error: the encounter you requested could not be set up "
            "(%s), so no fight has started and nothing changed. Answer the "
            "player's last action again without this fight; request it again "
            "only if it still fits." % COMBAT_START_REASONS[reason]
        ),
    })
    return {"status": "needs_response", "needs_update": True}


def _built_encounter(result_path, returncode):
    """The encounter id the combat builder saved, or the reason it has none (#812).

    Decided only from the builder's typed result file and exit code, never
    from its printed lines (colored text broke the old parse). A saved id
    counts only when its encounter file names the same id.
    """
    try:
        with open(result_path, "r", encoding="utf-8") as result_file:
            result = json.load(result_file)
    except (OSError, ValueError):
        return None, "builder_failed"
    if not isinstance(result, dict) or result.get("version") != 1:
        return None, "builder_failed"
    if result.get("status") != "saved":
        return None, "builder_no_encounter"
    encounter_id = result.get("encounterId")
    if returncode != 0 or not isinstance(encounter_id, str) or not encounter_id.strip():
        return None, "builder_failed"
    encounter_path = os.path.join("modules", "encounters", "encounter_%s.json" % encounter_id)
    try:
        with open(encounter_path, "r", encoding="utf-8") as encounter_file:
            saved = json.load(encounter_file)
    except (OSError, ValueError):
        return None, "builder_no_encounter"
    if not isinstance(saved, dict) or saved.get("encounterId") != encounter_id:
        return None, "builder_no_encounter"
    return encounter_id, None


def process_action(
    action,
    party_tracker_data,
    location_data,
    conversation_history,
    *,
    approved_transition_plan=None,
    transition_deferred_actions=None,
    invocation_claim=None,
    action_context=None,
    level_up_context=None,
    turn_roster=None,
):
    """Process an action based on its type
    
    Returns:
        RestoreRequest for model-requested Load, before any restore mutation;
        the surface consumes it only after gameplay unwinds. Otherwise:
        dict: {
            "status": "continue" | "exit" | "needs_response",
            "needs_update": bool,
            "response_data": dict (optional) - data for generating new AI response
        }
    """
    # Import modules here to avoid circular imports
    from core.managers import location_manager
    from updates.update_world_time import update_world_time
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

        # #263: one automatic save point before the fight begins (never
        # during combat). Fail-forward: a failed checkpoint never stops it.
        try:
            from core.managers.status_manager import status_manager
            status_manager.update_status("Saving a checkpoint before the fight...", is_processing=True)
        except Exception:
            pass
        try:
            from updates.save_game_manager import SaveGameManager
            SaveGameManager().create_combat_checkpoint(
                (action.get("parameters") or {}).get("encounterSummary", "")
            )
        except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
            # A player's Load or Exit, or a read-only save stop, ends this
            # turn before the fight is built (#845, as below for #654).
            raise
        except Exception as e:
            warning(f"Combat checkpoint skipped: {e}", category="save_game")

        # Update status to lock input during encounter building
        try:
            from core.managers.status_manager import status_manager
            status_manager.update_status("Prepare for battle - building encounter...", is_processing=True)
            debug("STATE_CHANGE: Status updated to building encounter", category="combat_processing")
        except Exception as e:
            error(f"FAILURE: Could not update status for encounter building", exception=e, category="combat_processing")

        fight_finished = False
        try:
            print("[DEBUG ACTION_HANDLER] Calling combat_builder.py...")
            debug(f"SUBPROCESS: Sending to combat_builder.py: {json.dumps(action)}", category="combat_processing")
            # Get the path to combat_builder.py relative to the project root
            combat_builder_path = _generator_script_path("combat_builder.py")
            
            import shutil
            import tempfile

            result_dir = tempfile.mkdtemp(prefix="combat_builder_")
            try:
                from utils.encoding_utils import utf8_child_env
                result = subprocess.run(
                    [sys.executable, combat_builder_path, "--result-file",
                     os.path.join(result_dir, "result.json")],
                    input=json.dumps(action),
                    capture_output=True, encoding="utf-8", errors="replace",
                    env=utf8_child_env()
                )
                encounter_id, build_failure = _built_encounter(
                    os.path.join(result_dir, "result.json"), result.returncode
                )
            finally:
                shutil.rmtree(result_dir, ignore_errors=True)
            print(f"[DEBUG ACTION_HANDLER] combat_builder.py completed")
            print(f"[DEBUG ACTION_HANDLER] Output: {result.stdout[:200]}...")  # First 200 chars
            debug(f"SUBPROCESS: combat_builder.py output: {result.stdout}", category="combat_processing")
            debug(f"SUBPROCESS: combat_builder.py status: {result.stderr}", category="combat_processing")
            info("SUBPROCESS: combat_builder.py exited %d" % result.returncode, category="combat_processing")

            if encounter_id:
                print(f"[DEBUG ACTION_HANDLER] SUCCESS! Encounter created with ID: {encounter_id}")

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
                # Every enemy gets its engine occupant before the fight: the
                # declared ID, the present group of its type at the place, or a
                # new occupant created for a free name (P4-d). Never a stop.
                from core.nql import occupants as _occupants
                _occupants.declare_encounter(encounter_id)

                # Reload location data here
                current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
                current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
                # Use the reloaded location data for the combat simulation
                reloaded_location_data = current_location_data(party_tracker_data, consumer="combat start")


                if reloaded_location_data is None:
                    print(f"ERROR: Failed to load location data for {current_location_id}")
                    return _combat_start_failed(
                        "location_unreadable", conversation_history, invocation_claim
                    )

                print(f"[DEBUG ACTION_HANDLER] About to call run_combat_simulation with encounter: {encounter_id}")
                print("[DEBUG ACTION_HANDLER] This should start INTERACTIVE turn-based combat...")
                
                # Update status to show combat is starting
                try:
                    from core.managers.status_manager import status_manager
                    status_manager.update_status("Combat in progress...", is_processing=True)
                    debug("STATE_CHANGE: Status updated to combat in progress", category="combat_processing")
                except Exception as e:
                    error(f"FAILURE: Could not update status for combat start", exception=e, category="combat_processing")
                
                try:
                    combat_result = run_combat_simulation(
                        encounter_id,
                        party_tracker_data,
                        reloaded_location_data,
                        invocation_claim=invocation_claim,
                    )
                except LiveProviderCompletedError as refused:
                    # #1087: a refused combat call ends this window. Nothing
                    # was cleared: the fight stays active and resumes at the
                    # next start or Load. The one selector says why.
                    error(
                        "FAILURE: A combat provider call was refused; the fight is kept",
                        exception=refused,
                        category="combat_processing",
                    )
                    refusal = classify_provider_error(refused)
                    return create_return(status="error", response_data={
                        "provider_refusal": refusal["category"],
                        "provider_refusal_provider": refusal["provider"],
                        "provider_refusal_moment": "combat",
                    })

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

                # A quit at a combat prompt returns None and a stopped fight
                # (None, None); neither is a finished fight (#444).
                if not (
                    isinstance(combat_result, tuple)
                    and len(combat_result) == 2
                    and isinstance(combat_result[0], str)
                    and combat_result[0]
                ):
                    return _combat_start_failed(
                        "combat_not_started", conversation_history, invocation_claim
                    )
                dialogue_summary, updated_player_info = combat_result
                fight_finished = True

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

                # Copy combat summary to main conversation history. The fight's
                # exit wrote exactly this line and returned its summary, so the
                # record never comes from an earlier fight (#444).
                print("[DEBUG ACTION_HANDLER] Appending this fight's combat summary to conversation history")
                # Add clear historical marker to prevent Combat Commitment Point confusion
                from core.managers.combat_manager import (
                    combat_record_exit_kind, combat_record_joined_against_party,
                    combat_record_xp_receipt,
                    render_combat_record_marker,
                )
                modified_combat_summary = {
                    "role": "user",
                    "content": render_combat_record_marker(
                        "Combat Summary: " + dialogue_summary,
                        combat_record_exit_kind(encounter_id),
                        combat_record_xp_receipt(encounter_id),
                        combat_record_joined_against_party(encounter_id),
                    )
                }
                conversation_history.append(modified_combat_summary)
                # Import save_conversation_history from main
                if __name__ != "__main__":

                    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

                from main import save_conversation_history
                save_conversation_history(conversation_history)
                # The engine's location record: each enemy's typed end in
                # the fight resolves its occupant (P4-c). Never stops play.
                from core.nql import occupants as _occupants
                _occupants.resolve_combat(encounter_id)
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
                print(f"[DEBUG ACTION_HANDLER] FAILED! Encounter was not created successfully")
                print(f"[DEBUG ACTION_HANDLER] Full stdout: {result.stdout}")
                print(f"[DEBUG ACTION_HANDLER] Full stderr: {result.stderr}")
                print("[DEBUG ACTION_HANDLER] ========== CREATE ENCOUNTER END WITH FAILURE ==========\n")
                return _combat_start_failed(
                    build_failure, conversation_history, invocation_claim
                )

        except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
            # A read-only save stop inside the combat ends the session now,
            # not after the rest of this turn (issue #654).
            raise
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running combat_builder.py: {e}")
            print("Error output:", e.stderr)
            print("Standard output:", e.stdout)
            return _combat_start_failed(
                "builder_failed", conversation_history, invocation_claim
            )
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
            # This try also wraps the fight itself. After a finished fight the
            # turn ends with the one failure line; before that, the tracker
            # decides whether a fight is still active (#444).
            if fight_finished:
                return create_return(status="error", needs_update=False)
            return _combat_start_failed(
                "combat_not_started", conversation_history, invocation_claim
            )

    elif action_type == ACTION_UPDATE_TIME:
        status_advancing_time()
        time_estimate_str = str(parameters["timeEstimate"])
        # D4: the engine's document holds the clock; the tracker follows it.
        # The turn's id makes a retried turn historical, not a second wait.
        from core.nql import game_clock

        if not game_clock.advance_minutes(
            time_estimate_str,
            _engine_request_id(invocation_claim, action_context, "time"),
        ):
            update_world_time(time_estimate_str)

    elif action_type == ACTION_UPDATE_PLOT:
        # QS: the quest record is the engine's. One typed action, one engine
        # request; a refusal goes back to the DM as a Quest Error correction
        # and later actions of this response do not run. module_plot.json is
        # authored content and is never written here.
        status_updating_plot()
        from utils import quest_record as _quest_record

        _module = str(party_tracker_data.get("module") or "").replace(" ", "_")
        _outcome = _quest_record.apply_update(
            parameters,
            _engine_request_id(invocation_claim, action_context, "updatePlot"),
            _module,
        )
        if _outcome.get("outcome") == "applied":
            _quest_record.journal_after_change(_module)
        if _outcome.get("correction"):
            conversation_history.append({"role": "user", "content": _outcome["correction"]})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)

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
        from utils.transient_filesystem import is_transient_filesystem_error
        from utils.capture.live_provider_call import (
            _interruptible_wait, get_live_provider_scope,
        )

        transition_scope = get_live_provider_scope()
        while True:
            try:
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
                break
            except OSError as exc:
                if not is_transient_filesystem_error(exc):
                    raise
            _interruptible_wait(0.25, transition_scope, "Checking the travel map...")
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
        transition_checkpoint = None
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
                path=(
                    ()
                    if approved_transition_plan.authority == "engine"
                    else approved_transition_plan.path
                ),
                authority=approved_transition_plan.authority,
                travel_minutes=getattr(approved_transition_plan, "travel_minutes", None),
            )
            transition_id = transition_checkpoint["operation_id"]
            _write_location_transition_checkpoint(transition_checkpoint)

        # Required semantic sibling proposals are frozen before movement,
        # outside the party/module mutation lock. A provider wait can
        # therefore neither hold the transition fence nor strand a
        # partially applied player turn. A failure here ends this turn
        # cleanly (#855): nothing has moved, so the move's own checkpoint is
        # retired and the player gets the curated failure line.
        try:
            prepare_current_transition_actions(transition_id)
        except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
            raise
        except Exception as prepare_error:
            error(
                "FAILURE: travel prepare failed",
                exception=prepare_error,
                category="location_transitions",
            )
            _retire_unmoved_transition_checkpoint(transition_id)
            return create_return(
                status="error",
                response_data=_travel_prepare_failure(prepare_error),
            )
        
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
            )

        from core.managers.campaign_manager import (
            _party_module_transition_lock,
        )

        while True:
            with _party_module_transition_lock():
                try:
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
                except OSError as exc:
                    if not is_transient_filesystem_error(exc):
                        raise
                else:
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
                    # Never retry movement here: only the pre-commit reads
                    # above may wait and reacquire this lock.
                    transition_result = run_location_transition()
                    break
            _interruptible_wait(
                0.25, transition_scope, "Checking the travel map..."
            )
        transition_context = (
            transition_result if isinstance(transition_result, dict) else None
        )
        # handle_location_transition returns its context dict only when the
        # party moved (#773).
        movement_committed = transition_context is not None
        if movement_committed:
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
            # C10a: the engine's party walks the committed path (the
            # resume walks it again, answered from the record).
            from core.nql import travel
            travel.realign(current_checkpoint)
            commit_current_transition_arrival(transition_id)

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

            info("SUCCESS: Location movement and departure state committed", category="location_transitions")
            response_data = {
                "departure_summary": transition_context.get("departure_summary"),
            }
            response_data["location_transition_id"] = transition_checkpoint[
                "operation_id"
            ]
            return create_return(needs_update=True, response_data=response_data)
        else:
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
            from core.managers.level_up_session import LevelUpSession
            
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
            entry = level_up_context or {}
            level_up_session = LevelUpSession(
                entity_name, current_level, new_level,
                accepted_history=entry.get('accepted_history'),
                player_input=entry.get('player_input'),
            )
            
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
            # Never a default character: an update that names none changes nothing (#914)
        
        if character_name:
            debug(f"STATE_CHANGE: Updating character info for {character_name}", category="character_updates")
            try:
                from core.managers.effects_runtime import update_character_with_effects
                from updates.update_character_info import EngineRefusedChange

                debug(f"STATE_CHANGE: Calling effects-aware character update for {character_name}", category="character_updates")
                success = update_character_with_effects(
                    character_name,
                    changes,
                    party_tracker_data,
                    action_context=action_context,
                    affects=parameters.get("affects"),
                    casting_resource=parameters.get("castingResource"),
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
            except EngineRefusedChange as refusal:
                # The rules engine refused the change (coins, hit points, spell
                # slots or feature uses). Nothing was written; the model hears
                # why and answers again, and later actions from this response
                # do not run.
                print(f"ERROR: Engine refused character update for {character_name}: {refusal.reason}")
                conversation_history.append({"role": "user", "content": (
                    f"Rules Error: {refusal.reason}. Nothing changed on {character_name}'s sheet. Later actions from "
                    "this response have not executed. Do not repeat earlier completed actions; propose a change the "
                    "sheet can cover (a payment, a spell slot or a feature use that is still available) or narrate "
                    "why it cannot happen.")})
                needs_conversation_history_update = True
                return create_return(status="needs_response", needs_update=True)
            except Exception as e:
                error(f"FAILURE: Exception in character update", exception=e, category="character_updates")
                # Use print with separate arguments to avoid format string interpretation
                print("ERROR: Failed to update character info:", str(e))
                response_data = {
                    "error_message": "Character effect classification or update failed safely."
                }
                if isinstance(e, LiveProviderCompletedError):
                    # A provider refusal (#240): record its class so the one
                    # failure-message selector can tell the player why (#432).
                    refusal = classify_provider_error(e)
                    response_data["provider_refusal"] = refusal["category"]
                    response_data["provider_refusal_provider"] = refusal["provider"]
                return create_return(status="error", response_data=response_data)
            finally:
                # Always reset status after character update completes
                try:
                    from core.managers.status_manager import status_ready
                    status_ready()
                    debug("STATE_CHANGE: Status reset after character update", category="character_updates")
                except Exception:
                    pass
        else:
            print("ERROR: updateCharacterInfo names no character; nothing was changed (#914).")
            # Reset status even if no character was found
            try:
                from core.managers.status_manager import status_ready
                status_ready()
            except Exception:
                pass

    elif action_type == ACTION_ROLL_CHECK:
        # C2a: the DM names the check; the engine scores it. The player's own
        # dice come from the roll prompt before the next DM turn; companions
        # and engine-rolled checks resolve now. Results reach the next DM Note.
        try:
            from core.managers.checks_runtime import stage_roll_check

            outcome = stage_roll_check(parameters)
        except ReadOnlySaveStop:
            raise
        except Exception as exc:
            error("FAILURE: rollCheck failed safely", exception=exc, category="character_updates")
            return create_return(status="error", response_data={"error_message": "The check could not be staged safely."})
        if outcome.get("error"):
            return create_return(status="error", response_data={"error_message": outcome["error"]})
        return create_return()

    elif action_type == ACTION_AWARD_EXPERIENCE:
        # X1b: the DM names the amount; the engine adds it to the character's XP and
        # writes the next-level threshold and any earned level-up back to the sheet.
        status_updating_character()
        try:
            from core.managers.experience_runtime import award_experience

            outcome = award_experience(parameters)
        except ReadOnlySaveStop:
            raise
        except Exception as exc:
            error("FAILURE: awardExperience failed safely", exception=exc, category="character_updates")
            return create_return(status="error", response_data={"error_message": "The XP award could not be applied safely."})
        if outcome.get("error"):
            # Fail forward: the response goes on; the refusal is in the log and the sheet is unchanged.
            warning(f"XP: {outcome['error']}", category="character_updates")
            return create_return()
        return create_return()

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
        operation = parameters.get("operation")
        npc = parameters.get("npc") if isinstance(parameters.get("npc"), dict) else {}
        from updates.update_character_info import name_refusal
        from utils.status_words import NPC_STATUS_WORDS
        _refusal = name_refusal(npc.get("name")) if operation == "add" else None
        if _refusal:
            # #949: no sheet is built for a name that cannot name a character;
            # #1119: nor for a name carrying a status word.
            _name = str(npc.get("name") or "")
            conversation_history.append({"role": "user", "content": (
                f"Party Error: updatePartyNPCs add for {_name} did not complete: {_refusal}. Nothing was built "
                f"and nobody joined. Later actions from this response have not executed. Do not repeat earlier "
                f"completed actions. Give this companion its proper name: a name with letters that is not a "
                f"reserved engine name and has no status word ({', '.join(NPC_STATUS_WORDS)}).")})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)
        if turn_roster is None:
            turn_roster = TurnRoster.get(turn_key(invocation_claim))
        _request_id = _engine_request_id(invocation_claim, action_context, "party")
        _party_outcome = update_party_npcs(
            party_tracker_data,
            parameters,
            turn_roster=turn_roster,
            request_id=_request_id,
            id_suffix=_party_id_suffix(invocation_claim, action_context),
        )
        if _party_outcome is None:
            # The add's sheet could not be built: nothing joined. The DM is told
            # so, as for a refused quest or storage step, and later actions of
            # this response do not run (#534).
            _name = str(npc.get("name") or "")
            conversation_history.append({"role": "user", "content": (
                f"Party Error: updatePartyNPCs add for {_name} did not complete: no character sheet could be "
                f"built for {_name}. Nothing changed in the party roster; {_name} has not joined. Later actions "
                f"from this response have not executed. Do not repeat earlier completed actions. Narrate that "
                f"{_name} is not with the party yet; the player can ask again.")})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)
        if _party_outcome["kind"] == "correction":
            conversation_history.append({"role": "user", "content": _party_error(operation, _party_outcome["text"])})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)
        # T105: best-effort NPC-voice lifecycle hook after the roster commit,
        # fired by the outcome's kind: a join or heal is an arrival (a heal
        # seeds no T107 profile), a leave a departure; a noop fires nothing.
        # Always live and fail-open; it must never break the committed roster
        # action.
        if _party_outcome["kind"] in ("join", "heal", "leave"):
            needs_conversation_history_update = True
            try:
                lifecycle_context = parameters.get("lifecycleContext")
                source_turn_id = turn_key(invocation_claim)
                if not source_turn_id:
                    warning(
                        "T105 NPC lifecycle hook skipped after roster commit: "
                        "the accepted turn has no logical invocation identity",
                        category="character_updates",
                    )
                else:
                    _apply_party_npc_lifecycle(
                        party_tracker_data,
                        "remove" if _party_outcome["kind"] == "leave" else "add",
                        str(_party_outcome.get("display_name") or ""),
                        str(_party_outcome.get("npc_path") or ""),
                        lifecycle_context,
                        source_turn_id,
                        seed_profile=_party_outcome["kind"] == "join",
                    )
            except Exception as exc:
                warning(
                    "T105 NPC lifecycle hook raised after roster commit: %s: %s"
                    % (type(exc).__name__, str(exc)),
                    category="character_updates",
                )
        # The companion's occupant follows the roster (P4-e) by the planned
        # lines, for every outcome. Best effort; never undoes the roster.
        from core.nql import occupants as _occupants

        _occupants.party_change(
            _party_outcome["engine_lines"],
            _request_id,
            reason=_party_outcome.get("reason"),
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
                ModuleCreationBusyError,
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
            # The build takes module_refresh_lock itself, only to reserve its
            # name and to publish (issue #708); it is not held here while the
            # module generates.

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
                except ModuleCreationBusyError:
                    # Module refresh stayed busy before anything was built.
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
            # Never a default character: a request that names none changes nothing (#959)
            if not character_name:
                print(f"ERROR: No character name provided for storage interaction")
                conversation_history.append({"role": "user", "content": "Storage Error: No character name provided for storage interaction. This storage step and later actions have not executed. Do not repeat earlier completed actions; use current state."})
                return create_return(status="needs_response", needs_update=True)
                
            if not storage_description:
                print(f"ERROR: No storage description provided")
                conversation_history.append({"role": "user", "content": "Storage Error: No storage description provided. This storage step and later actions have not executed. Do not repeat earlier completed actions; use current state."})
                return create_return(status="needs_response", needs_update=True)
                
            debug(f"AI_CALL: Processing storage request for {character_name}: '{storage_description}'", category="storage_operations")
            
            # Process natural language description into operation
            processor_result = process_storage_request(storage_description, character_name)
            
            if not processor_result.get("success"):
                print(f"ERROR: Storage processor failed: {processor_result.get('error')}")
                
                # Add error message to conversation
                error_message = f"Storage Error: {processor_result.get('error', 'Unknown error processing storage request')}. This storage step failed; later actions from this response have not executed. Do not repeat earlier completed actions; use current state."
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
                equipment_prerequisite = execution_result.get("error_code") == "equipment_prerequisite"
                if not equipment_prerequisite:
                    print(f"ERROR: Storage operation failed: {execution_result.get('error')}")
                
                # Add error message to conversation
                error_message = f"Storage Error: {execution_result.get('error', 'Unknown error executing storage operation')}. This storage step failed; later actions from this response have not executed. Do not repeat earlier completed actions; use current state."
                if equipment_prerequisite:
                    error_message += (
                        " Canonical equipment facts: "
                        + json.dumps(execution_result["facts"], ensure_ascii=True)
                        + ". Use the existing character/effects tool to unequip before storing."
                    )
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                return create_return(
                    status="needs_response", needs_update=True,
                    response_data={"error_code": "equipment_prerequisite"} if equipment_prerequisite else None,
                )
                
        except (LiveProviderSuperseded, InvocationSupersededError):
            raise
        except Exception as e:
            print(f"ERROR: Exception while processing storage interaction: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Add error message to conversation
            error_message = f"Storage System Error: An unexpected error occurred while processing your storage request. Later actions from this response have not executed; check current state before proposing further changes. Do not repeat earlier completed actions."
            conversation_history.append({"role": "user", "content": error_message})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)

    elif action_type == ACTION_TRANSFER_ITEM:
        # One typed handoff between two party characters. The engine moves the
        # stock (core/nql/transfer.py) and both sheets are written together or
        # not at all, replacing the two independent updateCharacterInfo deltas.
        debug("STATE_CHANGE: Processing transferItem action", category="storage_operations")
        status_updating_character()
        try:
            from core.managers.item_transfer import execute_transfer

            result = execute_transfer(
                parameters.get("fromCharacter", ""),
                parameters.get("toCharacter", ""),
                parameters.get("itemName", ""),
                parameters.get("quantity", 1),
                party_tracker_data,
            )
            if result.get("success"):
                info(f"SUCCESS: {result.get('message')}", category="storage_operations")
                conversation_history.append({"role": "user", "content": f"Transfer: {result.get('message')}"})
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Transfer failed: {result.get('error')}")
                error_message = (
                    f"Transfer Error: {result.get('error', 'the handoff was refused')}. Nothing moved; both sheets are "
                    "unchanged. Later actions from this response have not executed. Do not repeat earlier completed "
                    "actions; propose the handoff again from the current sheets or narrate why it cannot happen."
                )
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                return create_return(status="needs_response", needs_update=True)
        except (LiveProviderSuperseded, InvocationSupersededError):
            raise
        except Exception as e:
            print(f"ERROR: Exception while processing transferItem: {str(e)}")
            import traceback
            traceback.print_exc()
            error_message = "Transfer System Error: An unexpected error occurred while handing the item over. Nothing moved. Later actions from this response have not executed; check current state before proposing further changes. Do not repeat earlier completed actions."
            conversation_history.append({"role": "user", "content": error_message})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)

    elif action_type == ACTION_EXPEND_CHARGES:
        # One typed charge spend (item charges H1): the engine holds the count
        # of every charged sheet row, spends exactly or refuses, and the sheet
        # count is rewritten from its view. A retried turn is answered from
        # the receipt on the sheet (chargeUses).
        debug("STATE_CHANGE: Processing expendCharges action", category="storage_operations")
        status_updating_character()
        try:
            from core.managers.item_charges import execute_expend

            result = execute_expend(
                parameters.get("characterName", ""),
                parameters.get("itemName", ""),
                parameters.get("charges", 1),
                _engine_request_id(invocation_claim, action_context, "expendCharges"),
                party_tracker_data,
            )
            if result.get("success"):
                info(f"SUCCESS: {result.get('message')}", category="storage_operations")
                conversation_history.append({"role": "user", "content": f"Charges: {result.get('message')}"})
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Charge spend failed: {result.get('error')}")
                error_message = (
                    f"Expend Error: {result.get('error', 'the spend was refused')}. Nothing changed: no charge was "
                    "spent. Later actions from this response have not executed. Do not repeat earlier completed "
                    "actions; spend a count the item has, name a charged item the character holds, or narrate why "
                    "the item cannot be used."
                )
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                return create_return(status="needs_response", needs_update=True)
        except (LiveProviderSuperseded, InvocationSupersededError):
            raise
        except Exception as e:
            print(f"ERROR: Exception while processing expendCharges: {str(e)}")
            import traceback
            traceback.print_exc()
            error_message = "Charges System Error: An unexpected error occurred while spending charges. Nothing changed. Later actions from this response have not executed; check current state before proposing further changes. Do not repeat earlier completed actions."
            conversation_history.append({"role": "user", "content": error_message})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)

    elif action_type == ACTION_ACQUIRE_ITEM:
        # One typed acquisition from the SRD item catalog (SA, #499): the host
        # prices it and makes change, one engine request pays and creates the
        # item from its catalog type, and the sheet row comes from the engine's
        # views. A retried turn is answered from the receipt on the sheet.
        debug("STATE_CHANGE: Processing acquireItem action", category="storage_operations")
        status_updating_character()
        try:
            from core.managers.item_acquisition import execute_acquisition

            result = execute_acquisition(
                parameters.get("characterName", ""),
                parameters.get("itemName", ""),
                parameters.get("quantity", 1),
                parameters.get("price"),
                _engine_request_id(invocation_claim, action_context, "acquireItem"),
                party_tracker_data,
                kind=parameters.get("kind"),
                catalog_id=parameters.get("catalogId"),
            )
            if result.get("success"):
                info(f"SUCCESS: {result.get('message')}", category="storage_operations")
                conversation_history.append({"role": "user", "content": f"Acquisition: {result.get('message')}"})
                needs_conversation_history_update = True
            else:
                print(f"ERROR: Acquisition failed: {result.get('error')}")
                if result.get("listing") is not None:
                    # P3a: a catalogId take is refused with its location's listing.
                    from core.managers.item_acquisition import dispatch_refusal
                    error_message = dispatch_refusal(result.get("error", "the acquisition was refused"), result["listing"])
                else:
                    error_message = (
                        f"Acquire Error: {result.get('error', 'the acquisition was refused')}. Nothing changed: no coins "
                        "moved and no item was added. Later actions from this response have not executed. Do not repeat "
                        "earlier completed actions; name a catalog item and a whole-lot quantity the character can pay "
                        "for, or, only when no catalog item can record what the narration showed, narrate briefly why it "
                        "changed."
                    )
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                return create_return(status="needs_response", needs_update=True)
        except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
            raise
        except Exception as e:
            print(f"ERROR: Exception while processing acquireItem: {str(e)}")
            import traceback
            traceback.print_exc()
            error_message = "Acquisition System Error: An unexpected error occurred while acquiring the item. Nothing changed. Later actions from this response have not executed; check current state before proposing further changes. Do not repeat earlier completed actions."
            conversation_history.append({"role": "user", "content": error_message})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)

    elif action_type in (ACTION_TRANSFER_CURRENCY, ACTION_SPLIT_CURRENCY):
        # Coins between party characters as one engine transaction across every
        # sheet involved (core/nql/currency.py); all sheets are written together
        # or none is.
        debug(f"STATE_CHANGE: Processing {action_type} action", category="storage_operations")
        status_updating_character()
        try:
            from core.managers.currency_transfer import execute_currency_split, execute_currency_transfer

            if action_type == ACTION_TRANSFER_CURRENCY:
                amounts = {coin: parameters.get(coin) for coin in ("gold", "silver", "copper")
                           if parameters.get(coin) not in (None, "", 0)}
                result = execute_currency_transfer(
                    parameters.get("fromCharacter", ""), parameters.get("toCharacter", ""), amounts, party_tracker_data,
                )
            else:
                result = execute_currency_split(
                    parameters.get("fromCharacter", ""), parameters.get("toCharacters"),
                    parameters.get("giverKeepsShare", True), party_tracker_data,
                    coins=parameters.get("coins") or None,
                )
            if result.get("success"):
                info(f"SUCCESS: {result.get('message')}", category="storage_operations")
                conversation_history.append({"role": "user", "content": f"Currency: {result.get('message')}"})
                needs_conversation_history_update = True
            else:
                print(f"ERROR: {action_type} failed: {result.get('error')}")
                error_message = (
                    f"Currency Error: {result.get('error', 'the coin transfer was refused')}. No coins moved; every "
                    "sheet is unchanged. Later actions from this response have not executed. Do not repeat earlier "
                    "completed actions; propose the transfer again from the current balances or narrate why it cannot happen."
                )
                conversation_history.append({"role": "user", "content": error_message})
                needs_conversation_history_update = True
                return create_return(status="needs_response", needs_update=True)
        except (LiveProviderSuperseded, InvocationSupersededError):
            raise
        except Exception as e:
            print(f"ERROR: Exception while processing {action_type}: {str(e)}")
            import traceback
            traceback.print_exc()
            error_message = "Currency System Error: An unexpected error occurred while moving coins. No coins moved. Later actions from this response have not executed; check current state before proposing further changes. Do not repeat earlier completed actions."
            conversation_history.append({"role": "user", "content": error_message})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)

    elif action_type == ACTION_REST:
        # A short or long rest for the whole party: the engine refills every
        # pool the rest recovers on every sheet in one request
        # (core/managers/rest_manager.py), then rest-bound effects clear.
        debug("STATE_CHANGE: Processing rest action", category="character_updates")
        status_updating_character()
        try:
            from core.managers.rest_manager import ask_hit_die_faces, execute_rest, player_hit_dice

            # 7b-host: the player rolls their own hit dice (or presses Enter
            # and the engine rolls); every other character's are the engine's.
            faces = None
            if str(parameters.get("restType") or "").strip().lower() == "short":
                ask = player_hit_dice(party_tracker_data or {}, parameters.get("hitDice"))
                if ask:
                    faces = {ask[0]: ask_hit_die_faces(*ask, read=input)}
            result = execute_rest(parameters.get("restType"), party_tracker_data, conversation_history,
                                  hit_dice=parameters.get("hitDice"), faces=faces)
            if result.get("success"):
                info(f"SUCCESS: {result.get('message')}", category="character_updates")
                conversation_history.append({"role": "user", "content": f"Rest: {result.get('message')}"})
                if result.get("hit_dice_receipts"):
                    # #840: the engine rolled the hit dice; the player sees the roll.
                    _show_rest_receipt(" ".join(result["hit_dice_receipts"]))
                if result.get("effects_note"):
                    # process_effect_lifecycle returns a complete message
                    # ({"role": "system", "content": ...}); append it as is.
                    conversation_history.append(result["effects_note"])
                needs_conversation_history_update = True
                if result.get("hit_dice_refused"):
                    # #1239 (D-1239-2 B, D-1239-4): the rest went ahead without some hit dice (refused
                    # before rolling as certain to heal nothing, or refused by the engine, D-KWA-7e); the
                    # DM tells the player now, in its own words.
                    conversation_history.append({"role": "user", "content": (
                        "Rest: some hit dice were not spent (the Rest line above says whose and why); the rest "
                        "itself went ahead and is applied. Later actions from this response have not executed. "
                        "Tell the player in the story which die is kept and why, without the record's field "
                        "names. Do not state the rest again and do not move the clock.")})
                    needs_conversation_history_update = True
                    return create_return(status="needs_response", needs_update=True)
            else:
                print(f"ERROR: rest failed: {result.get('error')}")
                conversation_history.append({"role": "user", "content": (
                    f"Rest Error: {result.get('error', 'the rest was refused')}. No sheet changed. Later actions from "
                    "this response have not executed. Do not repeat earlier completed actions; state the rest again "
                    "with restType short or long (hitDice only on a short rest), or narrate why the party cannot "
                    "rest.")})
                needs_conversation_history_update = True
                return create_return(status="needs_response", needs_update=True)
        except (LiveProviderSuperseded, InvocationSupersededError):
            raise
        except Exception as e:
            print(f"ERROR: Exception while processing rest: {str(e)}")
            import traceback
            traceback.print_exc()
            conversation_history.append({"role": "user", "content": (
                "Rest System Error: An unexpected error occurred while applying the rest. No sheet changed. Later "
                "actions from this response have not executed; check current state before proposing further changes.")})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)

    elif action_type == ACTION_UPDATE_PARTY_TRACKER:
        debug("STATE_CHANGE: Processing updatePartyTracker action", category="party_management")
        try:
            # Load current party tracker
            current_party_data = safe_json_load("party_tracker.json")
            if not current_party_data:
                current_party_data = party_tracker_data.copy() if party_tracker_data else {}
            
            current_module = current_party_data.get("module", "Unknown")

            # A direct tool caller must use the same transition executor and
            # its route authorization, never a raw tracker location write.
            if parameters.get("module") in (None, "", current_module) and (
                ("module" in parameters and parameters["module"] != current_module)
                or any(
                    key in parameters and parameters[key] != current_party_data.get("worldConditions", {}).get(key)
                    for key in ("currentLocationId", "currentLocation", "currentAreaId", "currentArea")
                )
            ):
                return create_return(status="error", needs_update=False, response_data={
                    "error_code": "transition_plan_stale", "retryable": True,
                    "error_message": "Within-module movement requires transitionLocation and fresh route preflight; no tracker fields were changed.",
                })
            
            # Check if module is being changed
            new_module = parameters.get("module")
            if new_module and new_module != current_module:
                # A usable destination requires both real IDs and an exact
                # module id (#1287). Models may emit the full field shape with
                # empty strings; treating those keys as "provided" publishes a
                # module with a blank world projection and strands the player
                # at "()" in the web UI. Resolved first, so a refusal reads and
                # builds nothing.
                parameters.update(
                    resolve_cross_module_target_projection(new_module, parameters)
                )
                print(f"DEBUG: [Module Transition] Module change detected: {current_module} -> {new_module}")
                print(f"DEBUG: [Party Tracker Before Update] Module: {current_party_data.get('module', 'Unknown')}")
                info(f"STATE_CHANGE: Module change detected: {current_module} -> {new_module}", category="module_management")
                
                # Insert module transition marker immediately when module change is detected
                transition_text = f"Module transition: {current_module} to {new_module}"
                transition_message = hm.marker("user", transition_text, hm.MODULE_TRANSITION)
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

    elif action_type in (
        ACTION_RESOLVE_OCCUPANT,
        ACTION_SET_OCCUPANT_ATTITUDE,
        ACTION_MOVE_OCCUPANT,
        ACTION_RETURN_OCCUPANT,
        ACTION_MOVE_BACKGROUND_NPC,
    ):
        # Typed story outcomes on the engine's occupant record (P4-e). The DM
        # decided what became of the occupant; the engine records it by id.
        # A refusal goes back to the DM as a correction with the present ids,
        # the way a refused handoff does; an unavailable engine never stops
        # the turn. The retired moveBackgroundNPC is forwarded to moveOccupant
        # when it names an occupant and a destination, else corrected.
        debug("STATE_CHANGE: Processing %s action" % action_type, category="npc_management")
        from core.nql import occupants as _occupants

        _module = str(party_tracker_data.get("module") or "")
        _location_id = str(
            (party_tracker_data.get("worldConditions") or {}).get("currentLocationId") or ""
        )
        _occupant_action = action_type
        _occupant_parameters = parameters
        _correction = None
        if action_type == ACTION_MOVE_BACKGROUND_NPC:
            _legacy = _occupants.legacy_move(parameters, _module, _location_id)
            if _legacy.get("forward"):
                _occupant_action = ACTION_MOVE_OCCUPANT
                _occupant_parameters = _legacy["forward"]
            else:
                _correction = _legacy.get("correction")
        if _occupant_action != ACTION_MOVE_BACKGROUND_NPC and _correction is None:
            # A companion's person is not moved or returned here: they part
            # ways through updatePartyNPCs. An unreadable roster refuses nothing.
            _roster = party_tracker_data.get("partyNPCs")
            _outcome = _occupants.apply_dm_action(
                _occupant_action,
                _occupant_parameters,
                _engine_request_id(invocation_claim, action_context, _occupant_action),
                _module,
                _location_id,
                companion_ids=frozenset(_roster_ids(_roster)) if isinstance(_roster, list) else frozenset(),
            )
            if _outcome.get("ok"):
                needs_conversation_history_update = True
            _correction = _outcome.get("correction")
        if _correction:
            conversation_history.append({"role": "user", "content": _correction})
            needs_conversation_history_update = True
            return create_return(status="needs_response", needs_update=True)

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
            from updates.save_game_manager import RestoreRequest, SaveGameManager
            
            # Extract parameters
            save_folder = parameters.get("saveFolder")
            
            if not save_folder:
                print("ERROR: Missing required parameter 'saveFolder' for restoreGame action")
                error_message = "Error: No save folder specified for restore operation"
                conversation_history.append({"role": "system", "content": error_message})
                needs_conversation_history_update = True
                return create_return(needs_update=needs_conversation_history_update)
            
            # Return a control proposal, not a mutation inside the old turn.
            # The surface applies it only after claims/scopes have unwound.
            manager = SaveGameManager()
            return RestoreRequest(manager, save_folder)
                
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
