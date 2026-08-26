# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Game Loop Controller
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# MAIN.PY - GAME LOOP CONTROLLER
# ============================================================================
#
# ARCHITECTURE ROLE: Primary Controller in MVC Pattern
#
# This is the central orchestrator of the 5th edition Dungeon Master system, implementing
# the main game loop and coordinating all subsystems. It follows the Command Pattern
# where every game interaction is processed as a discrete action.
#
# KEY RESPONSIBILITIES:
# - Game session management and main loop execution
# - Action parsing and routing to appropriate handlers
# - AI response validation with NPC codex integration
# - Conversation history management and context compression
# - Module transition processing with timeline preservation
# - Real-time user feedback and status reporting
# - DM Note generation for authoritative current game state
# - AI-powered NPC validation system coordination
#
# DM NOTE DESIGN PHILOSOPHY:
# - AUTHORITATIVE SOURCE: DM Note contains current, dynamic game state
# - REAL-TIME DATA: Always reflects most up-to-date character information
# - AI CLARITY: Single source of truth prevents conflicting information
# - DYNAMIC FOCUS: HP, spell slots, conditions, and active effects
#
# DM NOTE CONTENT STRATEGY:
# Generated content includes:
#   - Current party status (HP, level, XP, spell slots)
#   - Active location and environmental conditions
#   - Time, date, and world state information
#   - Dynamic character states (not static reference data)
#
# INFORMATION ARCHITECTURE:
# - DM NOTES: Current state, real-time data, authoritative information
# - SYSTEM MESSAGES: Static character reference (conversation_utils.py)
# - SEPARATION PRINCIPLE: Prevents AI confusion from version conflicts
#
# ARCHITECTURAL INTEGRATION:
# - Coordinates with dm_wrapper.py for AI interactions
# - Uses action_handler.py for command processing
# - Manages state through party_tracker.json updates
# - Validates responses using multiple AI models with NPC codex verification
# - Integrates with ModulePathManager for file operations
# - Provides dynamic data to conversation_utils.py for context management
# - Leverages npc_codex_generator.py for AI-powered character validation
#
# DATA FLOW:
# User Input -> Action Processing -> AI Response -> NPC Codex Validation -> State Update -> DM Note Refresh
#
# This file embodies our "AI-First Design with Human Safety Nets" principle
# by combining powerful AI capabilities with rigorous validation layers and
# clear information architecture that prevents AI confusion.
# ============================================================================

import json
import copy
import hashlib
import subprocess
import os
import re
import sys
import codecs
import glob
import time
import shutil
import tempfile
from uuid import uuid4
from pathlib import Path
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T063", "main.py", 636)
register_callsite("T064", "main.py", 738)
register_callsite("T065", "main.py", 1946)
register_callsite("T066", "main.py", 2450)
register_callsite("T067", "main.py", 3817)
from datetime import datetime, timedelta
from termcolor import colored
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Import encoding utilities
from utils.encoding_utils import (
    sanitize_text,
    sanitize_dict,
    safe_json_load,
    safe_json_dump,
    fix_corrupted_location_name,
    setup_utf8_console
)

# Import token tracking
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass

# Import other necessary modules (config is now patched)
from core.managers.combat_manager import run_combat_simulation
from updates.plot_update import update_plot
from utils.player_stats import get_player_stat
from updates.update_world_time import update_world_time
from core.ai.conversation_utils import (
    _effects_runtime_view,
    _format_temporary_effects,
    update_conversation_history,
    update_character_data,
)
from updates.update_character_info import update_character_info
from core.managers.level_up_manager import LevelUpSession # Add this line
from core.ai.incremental_compression import IncrementalLocationCompressor

# Import new manager modules
from core.managers import location_manager
from utils.location_path_finder import LocationGraph
from core.ai import action_handler
from core.ai.cumulative_summary import (
    compact_with_accepted_departure_summary,
    enhance_location_summary,
    generate_location_summary,
)
from core.managers.status_manager import (
    status_manager, status_ready, status_processing_ai, status_validating,
    status_retrying, status_transitioning_location, status_generating_summary,
    status_updating_journal, status_compressing_history, status_updating_character,
    status_updating_party, status_updating_plot, status_advancing_time, status_saving
)

# Import atomic file operations
from utils.file_operations import safe_write_json, safe_read_json
from utils.module_path_manager import ModulePathManager
from core.managers.campaign_manager import CampaignManager
from core.ai.inventory_context_integration import (
    build_enhanced_dm_note,
    build_srd_context,
)
from utils.reconcile_campaign_state import reconcile_campaign_state

# Import training data collection
# from simple_training_collector import log_complete_interaction  # DISABLED
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.character_sheet_contract import repair_and_persist_character
from utils.startup_handoff_state import (
    load_state as load_startup_state,
    sync_wizard_completion,
    mark_wizard_complete,
    claim_kickoff_lease,
    mark_kickoff_done,
    mark_kickoff_failed,
    is_kickoff_claim_still_active,
    try_consume_forced_recovery,
    renew_kickoff_lease,
    lock_kickoff_processing,
    prepare_manual_recovery_state,
    issue_new_attempt_id,
)

# Set script name for logging
set_script_name(__name__)

import config

# LocationGraph will be initialized inside main() after modules are integrated
location_graph = None

# Temperature Configuration (remains the same)
TEMPERATURE = 0.8

SOLID_GREEN = "\033[38;2;0;180;0m"  # Slightly darker solid green for player name
LIGHT_OFF_GREEN = "\033[38;2;100;180;100m"  # More muted light green for stats
GOLD = "\033[38;2;255;215;0m"  # Gold color for status messages
RESET_COLOR = "\033[0m"

json_file = "modules/conversation_history/conversation_history.json"

needs_conversation_history_update = False


def _active_combat_recovery(party_tracker):
    """Return persisted recovery metadata when ordinary DM turns must stop."""
    if not isinstance(party_tracker, dict):
        return None
    encounter_id = (
        (party_tracker.get("worldConditions") or {})
        .get("activeCombatEncounter", "")
    )
    if not encounter_id:
        return None
    encounter = safe_json_load(
        os.path.join("modules", "encounters", f"encounter_{encounter_id}.json")
    )
    if not isinstance(encounter, dict):
        return None
    state = encounter.get("combatState") or {}
    if state.get("pipelineMode") != "agentic":
        return None
    if state.get("phase") != "recovery_required":
        return None
    if not state.get("pauseReason"):
        return None
    return {
        "encounter_id": encounter_id,
        "reason": state.get("pauseReason", "combat_recovery_required"),
    }
_conversation_history_dirty = False
_dirty_conversation_history = None
should_inject_creation_prompt = False  # Global flag for module creation prompt injection

# Message combination system state variables
held_response = None
awaiting_combat_resolution = False

# Status display configuration
current_status_line = None

def display_status(message):
    """Display status message above the command prompt"""
    global current_status_line
    # Clear previous status line if exists
    if current_status_line is not None:
        print(f"\r{' ' * len(current_status_line)}\r", end='', flush=True)
    # Display new status
    status_display = f"{GOLD}[{message}]{RESET_COLOR}"
    print(f"\r{status_display}", flush=True)
    current_status_line = status_display

# Set up status callback
def status_callback(message, is_processing):
    """Callback for status manager to display status updates"""
    if is_processing:
        display_status(message)
    else:
        # Clear status when ready
        global current_status_line
        if current_status_line is not None:
            print(f"\r{' ' * len(current_status_line)}\r", end='', flush=True)
            current_status_line = None

# Register the callback
status_manager.set_callback(status_callback)

# Note: Old summarization functions removed - using cumulative summary system instead


def emit_startup_marker(phase, **extra):
    """Emit a structured startup-handoff marker.

    The marker is always logged (file + console handlers) for debugging. In WEB
    mode it must ALSO be printed to the live sys.stdout: the web layer parses
    `STARTUP_MARKER:` lines off sys.stdout via WebOutputCapture to drive the
    `game_started` UI unlock. The logger's console handler is bound to the
    original stdout at import time (before WebOutputCapture is installed), so the
    logger alone never reaches the web parser -- leaving the UI stuck on
    "Starting..." until the slow prompt fallback fires.

    The print() is guarded to fire only when stdout is a capture wrapper
    (duck-typed via `original_stream`, the attribute WebOutputCapture exposes).
    In a plain terminal the logger already reaches the console, so printing there
    would double the output.
    """
    payload = {
        "phase": phase,
        "timestamp": datetime.now().isoformat(),
    }
    payload.update(extra)
    marker_line = f"STARTUP_MARKER: {json.dumps(payload, ensure_ascii=False)}"
    info(marker_line, category="startup")
    # Web-delivery path (see docstring). Guard prevents terminal-mode double print.
    if hasattr(sys.stdout, "original_stream"):
        try:
            print(marker_line, flush=True)
        except (BrokenPipeError, OSError, ValueError):
            pass


def _run_get_ai_response_with_timeout(conversation_history, timeout_seconds=120):
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(get_ai_response, conversation_history)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        future.cancel()
        raise
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _run_startup_kickoff_once(
    conversation_history,
    party_tracker_data,
    location_data,
    source,
    startup_state,
    precomputed_response=None,
):
    claim = claim_kickoff_lease(source=source)
    claim_status = claim.get("status")
    state = claim.get("state", startup_state)

    if claim_status in {"already_done", "lease_held", "not_ready", "lock_timeout"}:
        emit_startup_marker(
            "startup_kickoff_skipped",
            source=source,
            result=claim_status,
            startup_attempt_id=state.get("startup_attempt_id"),
            state_version=state.get("state_version"),
            lease_owner=state.get("lease_owner"),
            attempt_count=state.get("attempt_count"),
        )
        return claim_status

    startup_attempt_id = claim.get("startup_attempt_id")
    lease_owner = claim.get("lease_owner")
    start_ts = time.time()
    emit_startup_marker(
        "startup_kickoff_attempted",
        source=source,
        result="claimed",
        startup_attempt_id=startup_attempt_id,
        state_version=state.get("state_version"),
        lease_owner=lease_owner,
        attempt_count=state.get("attempt_count"),
    )

    try:
        if precomputed_response is not None:
            initial_ai_response = precomputed_response
        else:
            initial_ai_response = _run_get_ai_response_with_timeout(conversation_history, timeout_seconds=120)

        # Fence stale/expired workers before applying side effects.
        if not is_kickoff_claim_still_active(startup_attempt_id, lease_owner):
            emit_startup_marker(
                "startup_kickoff_stale_discarded",
                source=source,
                result="stale_discarded",
                startup_attempt_id=startup_attempt_id,
                lease_owner=lease_owner,
                attempt_count=state.get("attempt_count"),
            )
            return "stale_discarded"

        lease_renew = renew_kickoff_lease(startup_attempt_id, lease_owner, lease_seconds=900)
        if lease_renew.get("status") != "updated":
            emit_startup_marker(
                "startup_kickoff_stale_discarded",
                source=source,
                result=lease_renew.get("status", "stale"),
                startup_attempt_id=startup_attempt_id,
                lease_owner=lease_owner,
            )
            return "stale_discarded"

        processing_lock = lock_kickoff_processing(startup_attempt_id, lease_owner, lease_seconds=3600)
        if processing_lock.get("status") != "updated":
            emit_startup_marker(
                "startup_kickoff_stale_discarded",
                source=source,
                result=processing_lock.get("status", "stale"),
                startup_attempt_id=startup_attempt_id,
                lease_owner=lease_owner,
            )
            return "stale_discarded"

        process_result = process_ai_response(
            initial_ai_response,
            party_tracker_data,
            location_data,
            conversation_history,
        )
        (
            process_result,
            party_tracker_data,
            location_data,
            conversation_history,
        ) = resolve_retryable_ai_result(
            process_result,
            party_tracker_data,
            location_data,
            conversation_history,
        )
        if (
            isinstance(process_result, dict)
            and (
                process_result.get("retryable") is True
                or process_result.get("status") == "error"
            )
        ):
            raise RuntimeError(
                "startup response processing pending: "
                f"{process_result.get('status', 'unknown')}"
            )
        update_result = mark_kickoff_done(startup_attempt_id, lease_owner)
        if update_result.get("status") != "updated":
            emit_startup_marker(
                "startup_kickoff_stale_discarded",
                source=source,
                result=update_result.get("status", "stale"),
                startup_attempt_id=startup_attempt_id,
                state_version=update_result.get("state", {}).get("state_version"),
                lease_owner=lease_owner,
                attempt_count=update_result.get("state", {}).get("attempt_count"),
            )
            return "stale_discarded"
        elapsed_ms = int((time.time() - start_ts) * 1000)
        emit_startup_marker(
            "startup_kickoff_done",
            source=source,
            result=update_result.get("status", "updated"),
            duration_ms=elapsed_ms,
            startup_attempt_id=startup_attempt_id,
            state_version=update_result.get("state", {}).get("state_version"),
            lease_owner=lease_owner,
            attempt_count=update_result.get("state", {}).get("attempt_count"),
        )
        return "done"
    except FuturesTimeoutError:
        fail_result = mark_kickoff_failed(startup_attempt_id, lease_owner, "kickoff_timeout")
        emit_startup_marker(
            "startup_kickoff_failed",
            source=source,
            result="timeout",
            error_code="kickoff_timeout",
            startup_attempt_id=startup_attempt_id,
            state_version=fail_result.get("state", {}).get("state_version"),
            lease_owner=lease_owner,
            attempt_count=fail_result.get("state", {}).get("attempt_count"),
        )
        return "timeout"
    except Exception as exc:
        fail_result = mark_kickoff_failed(startup_attempt_id, lease_owner, str(exc))
        emit_startup_marker(
            "startup_kickoff_failed",
            source=source,
            result="error",
            error_code=type(exc).__name__,
            startup_attempt_id=startup_attempt_id,
            state_version=fail_result.get("state", {}).get("state_version"),
            lease_owner=lease_owner,
            attempt_count=fail_result.get("state", {}).get("attempt_count"),
        )
        return "error"


def run_startup_kickoff_with_recovery(
    conversation_history,
    party_tracker_data,
    location_data,
    precomputed_response=None,
):
    """Run startup kickoff with exactly-once lease and one fallback recovery attempt."""
    startup_state = load_startup_state()
    result = _run_startup_kickoff_once(
        conversation_history,
        party_tracker_data,
        location_data,
        source="normal",
        startup_state=startup_state,
        precomputed_response=precomputed_response,
    )
    if result == "done":
        return {"status": "done"}

    current = load_startup_state()
    if current.get("status") == "kickoff_done":
        return {"status": "done"}

    # Never escalate to forced recovery while another active lease exists.
    if result in {"lease_held", "not_ready", "lock_timeout", "stale_discarded"}:
        return {"status": "pending", "reason": result}

    # Circuit breaker: allow one forced recovery per startup attempt.
    if current.get("status") != "kickoff_failed":
        return {"status": "pending", "reason": result}

    consumed = try_consume_forced_recovery(current.get("startup_attempt_id", ""))
    if consumed.get("status") != "consumed":
        return {"status": "failed", "reason": result}

    emit_startup_marker(
        "startup_watchdog_forced_kickoff",
        source="watchdog",
        result="forcing_recovery",
        startup_attempt_id=current.get("startup_attempt_id"),
        state_version=current.get("state_version"),
        lease_owner=current.get("lease_owner"),
        attempt_count=current.get("attempt_count"),
    )
    retry_result = _run_startup_kickoff_once(
        conversation_history,
        party_tracker_data,
        location_data,
        source="watchdog",
        startup_state=load_startup_state(),
    )
    return {"status": "done" if retry_result == "done" else "failed", "reason": retry_result}


def recover_startup_handoff():
    """Manual recovery path for web action endpoint."""
    prep = prepare_manual_recovery_state()
    startup_state = prep.get("state", load_startup_state())
    if prep.get("status") == "already_ready":
        return {"status": "already_ready"}
    if prep.get("status") == "in_progress":
        return {"status": "in_progress"}
    if prep.get("status") != "recoverable":
        return {"status": "not_recoverable"}

    party_tracker_data = load_json_file("party_tracker.json")
    if not party_tracker_data:
        return {"status": "failed", "error": "party_tracker_missing"}

    conversation_history = load_json_file(json_file) or []
    location_data = get_location_data_from_party_tracker(party_tracker_data)
    if not location_data:
        return {"status": "failed", "error": "party_tracker_world_state_invalid"}

    emit_startup_marker(
        "startup_manual_recovery_requested",
        source="manual",
        result="requested",
        startup_attempt_id=startup_state.get("startup_attempt_id"),
        state_version=startup_state.get("state_version"),
        lease_owner=startup_state.get("lease_owner"),
        attempt_count=startup_state.get("attempt_count"),
    )
    result = run_startup_kickoff_with_recovery(conversation_history, party_tracker_data, location_data)
    if result.get("status") == "done":
        return {"status": "recovered"}
    if result.get("status") == "pending":
        return {"status": "in_progress"}
    return {"status": "failed", "error": result.get("reason", "unknown")}


# Add this new function near the top of the file
def exit_game():
    print("Fond farewell until we meet again!")
    exit()

def check_and_inject_return_message(conversation_history, is_combat_active=False, location_note=""):
    """
    Checks if a 'player has returned' message needs to be injected at startup.

    Args:
        conversation_history: List of conversation messages
        is_combat_active: Boolean indicating if combat is currently active (prevents duplicate injection)
        location_note: Optional authoritative "current location" clause (built from
            party_tracker worldConditions by the caller). Inserted into the resume
            note so the welcome-back narration reflects the authoritative location
            instead of a stale one inferred from interrupted-turn history (#210).
            Empty string keeps the original note byte-for-byte.

    Returns:
        Tuple of (updated_conversation_history, was_injected)
    """
    # Skip if no conversation history (first startup)
    if not conversation_history:
        debug("STATE_CHANGE: No conversation history found, skipping return message injection", category="session_management")
        return conversation_history, False
    
    # Check if there are any user messages (game has been played before)
    user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
    if not user_messages:
        debug("STATE_CHANGE: No user messages found, skipping return message injection", category="session_management")
        return conversation_history, False
    
    # Get the last message
    last_message = conversation_history[-1] if conversation_history else None
    if not last_message:
        debug("STATE_CHANGE: No last message found, skipping return message injection", category="session_management")
        return conversation_history, False
    
    # Check if last message is already a return message
    last_content = last_message.get("content", "")
    if "Resume the game, the player has returned" in last_content:
        debug("STATE_CHANGE: Return message already present, skipping injection", category="session_management")
        return conversation_history, False
    
    # Check if we're resuming from combat - if so, inject a different tracking message
    if is_combat_active:
        # Combat manager will handle its own resume message, so we just add a tracking marker
        tracking_message = {
            "role": "user",
            "content": "[SYSTEM: Combat was interrupted and is being resumed from crash]"
        }
        conversation_history.append(tracking_message)
        debug("STATE_CHANGE: Added combat resume tracking message", category="session_management")
        
        # Also add an assistant acknowledgment to mark the recovery point
        recovery_marker = {
            "role": "assistant",
            "content": "[SYSTEM: Combat recovery initiated - continuing from last known state]"
        }
        conversation_history.append(recovery_marker)
        debug("STATE_CHANGE: Added combat recovery marker", category="session_management")
        return conversation_history, True
    
    # Normal (non-combat) resume message injection. The optional location_note
    # (authoritative "current location" clause) is inserted AFTER the idempotency
    # key phrase ("Resume the game, the player has returned") so the guard at the
    # top of this function still matches; empty keeps the note byte-identical.
    return_message = {
        "role": "user",
        "content": "Dungeon Master Note: Resume the game, the player has returned. " + location_note + "Welcome the player back warmly. Have the party members acknowledge their return with brief in-character reactions. Provide a concise atmospheric recap of the immediate situation and surroundings, then naturally prompt for the player's next action while maintaining immersion in the ongoing narrative. IMPORTANT: Do NOT use transitionLocation action - the party is already at their current location. Just provide narrative and prompts."
    }
    conversation_history.append(return_message)
    debug("STATE_CHANGE: Injected 'player has returned' message at startup", category="session_management")
    return conversation_history, True


def get_location_data_from_party_tracker(party_tracker_data):
    """Build location_data using the current worldConditions from party tracker."""
    world_conditions = (party_tracker_data or {}).get("worldConditions") or {}
    current_area_id = world_conditions.get("currentAreaId")
    current_location = world_conditions.get("currentLocation")
    current_area = world_conditions.get("currentArea")
    if not (current_area_id and current_location and current_area):
        return None
    return location_manager.get_location_info(current_location, current_area, current_area_id)


def generate_transition_narration(transition_prompt, party_tracker_data):
    """Run layer 1/3 (T013) from committed, updated location context.

    Travel narration is deliberately a three-agent chain: T013 produces this
    transition/departure layer, T063 produces arrival from the exact target and
    roster, and T064 stitches both.  It is one player turn; do not collapse the
    chain into a static location description when enforcing the single-turn
    gameplay boundary.
    """
    destination = party_tracker_data["worldConditions"]["currentLocation"]
    messages = [
        {
            "role": "system",
            "content": (
                "Narrate this committed transition using only the supplied "
                "observable facts. Address the sole player character in second "
                "person (you/your), never as a third-person protagonist. Return "
                "plain narration only and invent no mechanics, creatures, traps, "
                "secrets, choices, or outcomes."
            ),
        },
        {"role": "user", "content": transition_prompt},
    ]
    try:
        from model_config import MODEL_PROVIDER

        if MODEL_PROVIDER == "openai":
            narration_config = config.DM_MAIN_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            narration_config = config.DM_MAIN_GEMINI_PRO_LOW
        elif MODEL_PROVIDER == "lmstudio":
            narration_config = config.DM_MAIN_LMSTUDIO
        else:
            narration_config = config.DM_MAIN_LEGACY
        response = capture_and_fanout(
            "T013",
            api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=messages,
            model=narration_config["model"],
            temperature=0.7,
            response_format=None,
            **{
                key: value
                for key, value in narration_config.items()
                if key != "model"
            },
        )
        try:
            from utils.api_logger import log_api_call

            log_api_call(
                "transition_narration",
                messages,
                response,
                metadata={
                    "temperature": 0.7,
                    "context": "committed_transition_layer_1_of_3",
                },
            )
        except Exception as log_error:
            debug(
                "T013 evidence logging unavailable: %s"
                % type(log_error).__name__,
                category="narrative_generation",
            )
        narration = sanitize_text(response.choices[0].message.content).strip()
        if not narration:
            raise ValueError("T013 returned empty narration")
        return narration
    except Exception as narration_error:
        warning(
            "T013 unavailable; retaining deterministic committed-arrival prose: %s"
            % type(narration_error).__name__,
            category="narrative_generation",
        )
        return "You complete the journey and arrive at %s." % destination

def generate_arrival_narration(departure_narration, party_tracker_data, conversation_history):
    """
    Run layer 2/3 (T063) from T013 plus the committed target/roster projection.
    """
    debug("STATE_CHANGE: Generating cinematic arrival narration...", category="narrative_generation")
    
    # Get details for the new location from the (now updated) party tracker
    new_location_name = party_tracker_data["worldConditions"]["currentLocation"]
    new_area_name = party_tracker_data["worldConditions"]["currentArea"]
    player_names = [str(name) for name in party_tracker_data.get("partyMembers", [])]
    npc_names = [
        str(item.get("name"))
        for item in party_tracker_data.get("partyNPCs", [])
        if isinstance(item, dict) and item.get("name")
    ]

    # Construct the special prompt
    arrival_prompt = f"""
    You are a master storyteller. The following text describes the party's departure from one location. Your task is to write a seamless, cinematic, and immersive description of their arrival at their destination, "{new_location_name}" in the "{new_area_name}" area.

    The arrival narration should:
    1.  Feel like a direct continuation of the departure text.
    2.  Focus on sensory details (sights, sounds, smells) of the new location.
    3.  Set the mood and atmosphere of the new environment.
    4.  Incorporate reactions only for actors in the exact committed roster below.
    5.  Do not repeat any information from the departure text. Just write the arrival part.

    EXACT COMMITTED ROSTER:
    Player characters: {json.dumps(player_names, ensure_ascii=False)}
    Party NPCs: {json.dumps(npc_names, ensure_ascii=False)}
    Do not add, imply, count, or describe any other companion.

    DEPARTURE NARRATION (for context):
    ---
    {departure_narration}
    ---

    Now, write the arrival narration.
    """
    
    narration_request_messages = [
        {
            "role": "system",
            "content": (
                "You narrate only the committed arrival supplied in this "
                "request. Address the sole player character in second person "
                "(you/your). The exact committed roster in the request is an "
                "actor boundary: do not import, imply, or count any other "
                "actor, event, or location from earlier conversation."
            ),
        },
        {"role": "user", "content": arrival_prompt}
    ]

    try:
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            narr_cfg = config.MINI_UTIL_GPT54MINI_NONE
        elif MODEL_PROVIDER == "gemini":
            narr_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            narr_cfg = config.MINI_UTIL_LMSTUDIO
        else:  # legacy
            narr_cfg = config.MINI_UTIL_LEGACY

        response = capture_and_fanout("T063", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=narration_request_messages,
            model=narr_cfg["model"],
            temperature=TEMPERATURE,
            response_format=None,
            **{k: v for k, v in narr_cfg.items() if k != "model"})

        # Log API call to master log
        try:
            from utils.api_logger import log_api_call
            log_api_call("narration_generator", narration_request_messages, response,
                        metadata={"temperature": TEMPERATURE, "context": "module_transition_arrival"})
        except Exception as e:
            print(f"[API_LOG] Warning: Failed to log narration call: {e}")

        # Track token usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(response, context={'endpoint': 'narration_generator', 'purpose': 'generate_narrative_summary'})
            except:
                pass
        
        arrival_text = response.choices[0].message.content.strip()
        if not arrival_text:
            raise ValueError("T063 returned empty arrival narration")

        # Sometimes the AI will still wrap its response in the one supported
        # JSON object. Other JSON roots/shapes are malformed, not narration.
        try:
            parsed_json = json.loads(arrival_text)
            if (
                not isinstance(parsed_json, dict)
                or set(parsed_json) != {"narration"}
                or not isinstance(parsed_json["narration"], str)
                or not parsed_json["narration"].strip()
            ):
                raise ValueError("T063 returned an unsupported JSON shape")
            arrival_text = parsed_json["narration"].strip()
        except json.JSONDecodeError:
            # It's just plain text, which is what we want.
            pass

        debug("SUCCESS: Arrival narration generated successfully.", category="narrative_generation")
        sanitized_arrival = sanitize_text(arrival_text).strip()
        if not sanitized_arrival:
            raise ValueError("T063 narration was empty after sanitization")
        return sanitized_arrival
    except Exception as e:
        error(f"FAILURE: Failed to generate arrival narration", exception=e, category="narrative_generation")
        return f"You arrive at {new_location_name}."  # Deterministic fallback.


# <--- NEW FUNCTION to blend the departure and arrival narrations --->
def generate_seamless_transition_narration(departure_narration, arrival_narration):
    """
    Run layer 3/3 (T064), preserving both accepted layers as one seamless turn.
    """
    debug("STATE_CHANGE: Blending departure and arrival narrations into a seamless whole...", category="narrative_generation")

    # If either part is empty, just return the other part to avoid weird API calls.
    if not departure_narration:
        return arrival_narration
    if not arrival_narration:
        return departure_narration

    stitching_prompt = f"""
You are a master storyteller and narrative editor. The following two text blocks describe a party's departure from one place and their subsequent arrival at another. The transition between them is abrupt because they were generated separately.

Your task is to rewrite them into a single, cohesive, and cinematic narration.
- Preserve all key details, sensory information, and character actions from both parts.
- Smooth out the transition so it feels like one continuous story beat.
- Enhance the prose where possible to create a more engaging and atmospheric experience.
- Do not add new plot points or actions; your role is to refine the existing narrative flow.
- Do not add, count, or imply any actor who is not explicitly identified in the source blocks.
- Address the sole player character only in second person (you/your), never as a third-person protagonist.
- End after the committed arrival with one open in-fiction invitation for the player to choose their next immediate action. Do not enumerate options and do not perform that next action.

DEPARTURE NARRATION:
---
{departure_narration}
---

ARRIVAL NARRATION:
---
{arrival_narration}
---

Now, provide the rewritten, seamless narration.
"""

    try:
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            narr_cfg = config.MINI_UTIL_GPT54MINI_NONE
        elif MODEL_PROVIDER == "gemini":
            narr_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            narr_cfg = config.MINI_UTIL_LMSTUDIO
        else:  # legacy
            narr_cfg = config.MINI_UTIL_LEGACY

        response = capture_and_fanout("T064", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=[
                {"role": "system", "content": "You are a master storyteller and editor, skilled at weaving separate narrative fragments into a single, seamless, and immersive piece of prose."},
                {"role": "user", "content": stitching_prompt}
            ],
            model=narr_cfg["model"],
            temperature=TEMPERATURE,
            response_format=None,
            **{k: v for k, v in narr_cfg.items() if k != "model"})

        # Log API call to master log
        try:
            from utils.api_logger import log_api_call
            log_api_call("narrative_stitcher", [
                {"role": "system", "content": "You are a master storyteller and editor, skilled at weaving separate narrative fragments into a single, seamless, and immersive piece of prose."},
                {"role": "user", "content": stitching_prompt}
            ], response, metadata={"temperature": TEMPERATURE, "context": "module_transition_stitch"})
        except Exception as e:
            print(f"[API_LOG] Warning: Failed to log stitcher call: {e}")

        # Track token usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(response, context={'endpoint': 'narrative_stitching', 'purpose': 'stitch_location_descriptions'})
            except:
                pass
        
        seamless_narration = response.choices[0].message.content.strip()
        if not seamless_narration:
            raise ValueError("T064 returned empty seamless narration")
        debug("SUCCESS: Seamless narration generated successfully.", category="narrative_generation")
        sanitized_narration = sanitize_text(seamless_narration).strip()
        if not sanitized_narration:
            raise ValueError("T064 narration was empty after sanitization")
        return sanitized_narration
    except Exception as e:
        error(f"FAILURE: Failed to generate seamless transition narration", exception=e, category="narrative_generation")
        # Fallback to simple concatenation if the API call fails
        debug("STATE_CHANGE: Falling back to simple concatenation.", category="narrative_generation")
        return f"{departure_narration}\n\n{arrival_narration}"


def _exact_party_module_projection(party):
    world = party.get("worldConditions") if isinstance(party, dict) else None
    world = world if isinstance(world, dict) else {}
    return {
        "module": party.get("module") if isinstance(party, dict) else None,
        "currentAreaId": world.get("currentAreaId"),
        "currentArea": world.get("currentArea"),
        "currentLocationId": world.get("currentLocationId"),
        "currentLocation": world.get("currentLocation"),
    }


def _transition_narration_action_context(checkpoint):
    """Expose accepted, receipt-backed turn facts to the prose-only narrator.

    The actions remain mechanical authority; this projection only prevents the
    final destination narration from erasing the player-visible meaning of the
    accepted turn.  Control-only actions retain their existing dedicated
    messages and are not folded into scene prose.
    """
    deferred = checkpoint.get("deferred_actions")
    records = deferred.get("actions") if isinstance(deferred, dict) else None
    if not isinstance(records, list):
        return ""
    public_actions = []
    for record in records:
        if not isinstance(record, dict):
            continue
        family = record.get("family")
        if family in {
            "saveGame",
            "listSaves",
            "deleteSave",
            "exitGame",
            "updatePartyTracker",
        }:
            continue
        action = record.get("action")
        receipt = record.get("receipt")
        if not isinstance(action, dict) or not isinstance(receipt, dict):
            continue
        fact = {
            "action": family,
            "parameters": copy.deepcopy(action.get("parameters") or {}),
        }
        if family == "updatePartyNPCs":
            before_names = [
                item.get("name")
                for item in receipt.get("roster_before", [])
                if isinstance(item, dict) and item.get("name")
            ]
            after_names = [
                item.get("name")
                for item in receipt.get("roster_after", [])
                if isinstance(item, dict) and item.get("name")
            ]
            fact["receiptResult"] = {
                "partyNPCNamesBefore": before_names,
                "partyNPCNamesAfter": after_names,
            }
        elif family == "updateTime":
            fact["receiptResult"] = {
                "before": copy.deepcopy(receipt.get("before")),
                "after": copy.deepcopy(receipt.get("after")),
            }
        public_actions.append(fact)
    if not public_actions:
        return ""
    return (
        "\n\nACCEPTED TURN FACTS (structured, receipt-backed; acknowledge "
        "every outcome without inventing details, extra companions, or "
        "mechanics. An NPC removed after arrival leaves the traveling party "
        "at this destination; names in partyNPCNamesAfter are the only NPC "
        "companions still traveling with the player):\n"
        + json.dumps(public_actions, ensure_ascii=False, sort_keys=True)
    )


def _transition_outcome_lines(checkpoint, party):
    """Render exact accepted outcomes that scene prose is not allowed to lose."""
    deferred = checkpoint.get("deferred_actions")
    records = deferred.get("actions") if isinstance(deferred, dict) else None
    if not isinstance(records, list):
        return []
    world = party.get("worldConditions") if isinstance(party, dict) else {}
    destination = (world or {}).get("currentLocation") or "the destination"
    lines = []
    for record in records:
        if not isinstance(record, dict):
            continue
        family = record.get("family")
        receipt = record.get("receipt")
        if not isinstance(receipt, dict):
            continue
        if family == "removeEffect":
            lines.append(
                "%s ends on %s."
                % (receipt.get("name") or "The effect", receipt.get("owner") or "its target")
            )
        elif family == "updatePartyNPCs":
            if receipt.get("operation") == "add":
                lines.append(
                    "%s joins your traveling party at %s."
                    % (receipt.get("npc_name"), destination)
                )
            elif receipt.get("operation") == "remove":
                lines.append(
                    "%s leaves your traveling party at %s."
                    % (receipt.get("npc_name"), destination)
                )
        elif family == "moveBackgroundNPC":
            proposal = receipt.get("proposal") or {}
            if proposal.get("action") == "move":
                lines.append(
                    "%s relocates to %s."
                    % (receipt.get("npc_name"), proposal.get("newLocation"))
                )
            elif proposal.get("action") == "remove":
                lines.append("%s leaves the area." % receipt.get("npc_name"))
            elif proposal.get("action") == "update_status":
                lines.append(
                    "%s's status changes as agreed." % receipt.get("npc_name")
                )
    return [line for line in lines if "None" not in line]


def _append_transition_outcomes(narration, checkpoint, party):
    lines = _transition_outcome_lines(checkpoint, party)
    if not lines:
        return narration
    return "%s\n\n%s" % (narration.rstrip(), " ".join(lines))


def _resume_cross_module_root(operation_id, *, publish=True):
    """Resume the random-ID module handoff, clock tail, and target narration."""
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    if checkpoint is None:
        return {"status": "none"}
    handoff = checkpoint.get("module_handoff")
    if not isinstance(handoff, dict):
        return {"status": "blocked", "reason": "module handoff receipt is missing"}
    party = load_json_file("party_tracker.json") or {}
    projection = _exact_party_module_projection(party)
    source = handoff["source_projection"]
    target = handoff["target_projection"]
    pending = {
        "from_module": source["module"],
        "to_module": target["module"],
        "completion_id": handoff["completion_id"],
        "party_tracker_data": copy.deepcopy(party),
    }
    history = load_json_file(json_file) or []
    if projection == source:
        transition_history = copy.deepcopy(handoff["transition_history"])
        marker = {
            "role": "user",
            "content": "Module transition: %s to %s"
            % (source["module"], target["module"]),
        }
        if not transition_history or transition_history[-1] != marker:
            transition_history.append(marker)
        from core.managers.campaign_manager import CampaignManager

        original, updated = CampaignManager().publish_party_module_transition(
            source["module"],
            target["module"],
            handoff["parameters"],
            transition_history,
            handoff["completion_id"],
        )
        pending["party_tracker_data"] = original
        save_conversation_history(
            transition_history, strict=True, allow_compression=False
        )
        party = updated
        projection = _exact_party_module_projection(party)
        checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
        checkpoint["module_handoff"]["status"] = "published"
        checkpoint["phase"] = "module_handoff_pending"
        action_handler._write_location_transition_checkpoint(checkpoint)
    if projection != target:
        return {
            "status": "blocked",
            "reason": "party state matches neither staged module projection",
        }

    targeted, completion = retry_staged_module_completions(
        pending,
        load_json_file(json_file) or [],
    )
    if completion["failed"] or completion["blocked"]:
        return {"status": "pending", "reason": "module completion remains pending"}
    if targeted is None and handoff["completion_id"] not in completion["completed"]:
        return {"status": "pending", "reason": "module completion receipt is absent"}
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    checkpoint["module_handoff"]["status"] = "authority_transferred"
    checkpoint["phase"] = "module_authority_transferred"
    action_handler._write_location_transition_checkpoint(checkpoint)

    deferred = checkpoint["deferred_actions"]
    while int(deferred.get("cursor", 0)) < len(deferred.get("actions", [])):
        cursor = int(deferred.get("cursor", 0))
        outcome = action_handler.apply_current_transition_action(operation_id, cursor)
        if outcome == "blocked_conflict":
            return {"status": "blocked", "reason": "handoff clock conflict"}
        checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
        deferred = checkpoint["deferred_actions"]
    checkpoint["phase"] = "handoff_clock_committed"
    action_handler._write_location_transition_checkpoint(checkpoint)

    history, party = rebuild_conversation_for_current_party(
        load_json_file(json_file) or [], return_party=True
    )
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    narration = checkpoint["narration"]
    if narration.get("status") == "deferred_to_module_handoff":
        first = generate_transition_narration(
            narration.get("source_prompt") or "Describe the committed arrival.",
            party,
        )
        arrival = generate_arrival_narration(first, party, history)
        final_text = generate_seamless_transition_narration(first, arrival)
        final_text = _append_transition_outcomes(final_text, checkpoint, party)
        entry = {
            "role": "assistant",
            "content": final_text,
            "message_id": narration["message_id"],
        }
        existing = next(
            (
                i
                for i, item in enumerate(history)
                if isinstance(item, dict)
                and item.get("message_id") == narration["message_id"]
            ),
            None,
        )
        narration.update(
            {
                "status": "retained",
                "text": final_text,
                "history_index": len(history) if existing is None else existing,
                "history_entry_after": entry,
            }
        )
        checkpoint["phase"] = "narration_retained"
        action_handler._write_location_transition_checkpoint(checkpoint)
        if existing is None:
            history.append(entry)
            save_conversation_history(history, strict=True, allow_compression=False)
        elif history[existing] != entry:
            return {"status": "blocked", "reason": "handoff narration conflict"}
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    if publish and checkpoint["narration"].get("status") == "retained":
        display_dm_narration(
            checkpoint["narration"]["text"],
            message_id=checkpoint["narration"]["message_id"],
        )
        checkpoint["narration"]["status"] = "published"
        action_handler._write_location_transition_checkpoint(checkpoint)
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    checkpoint["final_context"].update(
        {
            "status": "committed",
            "party_projection_after": _exact_party_module_projection(party),
        }
    )
    checkpoint["phase"] = "final_context_committed"
    action_handler._write_location_transition_checkpoint(checkpoint)
    final_text = checkpoint["narration"].get("text", "")
    action_handler.complete_location_transition_checkpoint(operation_id)
    return {"status": "completed", "narration": final_text}


def _resume_v2_location_transition(operation_id, *, publish=True):
    """Resume one committed-movement v2 workflow from its durable receipts."""
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    if checkpoint is None:
        return {"status": "none"}
    if checkpoint.get("movement_kind") == "cross_module_root":
        return _resume_cross_module_root(operation_id, publish=publish)
    party = load_json_file("party_tracker.json") or {}
    world = party.get("worldConditions", {})
    handoff = checkpoint.get("module_handoff")
    handoff_target_active = (
        isinstance(handoff, dict)
        and handoff.get("status") == "authority_transferred"
        and _exact_party_module_projection(party)
        == handoff.get("target_projection")
    )
    if not handoff_target_active and str(world.get("currentLocationId", "")) != str(
        checkpoint.get("destination_location_id", "")
    ):
        return {
            "status": "blocked",
            "reason": "party location no longer matches the staged destination",
        }
    context = {
        "origin_history_segment": checkpoint["origin_segment_before"],
        "origin_party_tracker": party,
        "origin_location_info": {
            "name": checkpoint["origin_location_name"],
            "locationId": checkpoint["origin_location_id"],
        },
    }
    reconciliation = checkpoint["location_reconciliation"]
    if reconciliation.get("status") not in {
        "committed",
        "attempted_unavailable",
    }:
        outcome = action_handler.resolve_current_transition_reconciliation(
            operation_id, context
        )
        if outcome == "blocked_conflict":
            return {"status": "blocked", "reason": "origin reconciliation conflict"}
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    if checkpoint["departure_commit"].get("status") != "committed":
        action_handler.resolve_current_transition_departure(operation_id, context)
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)

    narration_record = checkpoint["narration"]
    if narration_record.get("status") == "pending":
        destination_data = get_location_data_from_party_tracker(party) or {}
        transition_prompt = location_manager._build_transition_narration_prompt(
            destination_data,
            area_id=world.get("currentAreaId"),
            area_name=world.get("currentArea"),
            storage_description=location_manager.format_storage_description(
                location_manager.get_storage_at_location(
                    world.get("currentLocationId")
                )
            ),
        )
        transition_prompt += _transition_narration_action_context(checkpoint)
        first = generate_transition_narration(transition_prompt, party)
        arrival = generate_arrival_narration(
            first, party, load_json_file(json_file) or []
        )
        final_text = generate_seamless_transition_narration(first, arrival)
        final_text = _append_transition_outcomes(final_text, checkpoint, party)
        narration_entry = {
            "role": "assistant",
            "content": final_text,
            "message_id": narration_record["message_id"],
        }
        history = load_json_file(json_file) or []
        existing = next(
            (
                index
                for index, message in enumerate(history)
                if isinstance(message, dict)
                and message.get("message_id") == narration_record["message_id"]
            ),
            None,
        )
        narration_record.update(
            {
                "text": final_text,
                "history_index": len(history) if existing is None else existing,
                "history_entry_before": None,
                "history_entry_after": narration_entry,
            }
        )
        checkpoint["phase"] = "narration_pending"
        action_handler._write_location_transition_checkpoint(checkpoint)
        if existing is None:
            history.append(narration_entry)
            save_conversation_history(
                history, strict=True, allow_compression=False
            )
        elif history[existing] != narration_entry:
            return {"status": "blocked", "reason": "narration identity conflict"}
        checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
        checkpoint["narration"]["status"] = "retained"
        checkpoint["phase"] = "narration_retained"
        action_handler._write_location_transition_checkpoint(checkpoint)

    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    episode = checkpoint["episode"]
    if episode.get("status") == "pending":
        try:
            from core.npc.episode_capture import (
                boundary_turn_id_for_position,
                capture_location_episode,
            )

            boundary_turn_id = boundary_turn_id_for_position(
                sum(
                    1
                    for message in (load_json_file(json_file) or [])
                    if isinstance(message, dict)
                    and message.get("role") == "user"
                    and "Location transition:" in message.get("content", "")
                )
                + 1
            )
            episode["boundary_turn_id"] = boundary_turn_id
            episode_id = capture_location_episode(
                leaving_location_name=checkpoint["origin_location_name"],
                leaving_location_id=checkpoint["origin_location_id"],
                segment_messages=episode["source_entries_before"],
                party_tracker_data=party,
                path_manager=ModulePathManager(checkpoint["module_name"]),
                boundary_turn_id=boundary_turn_id,
                player_name=(party.get("partyMembers") or [""])[0],
            )
            episode["episode_id"] = episode_id
            episode["status"] = "committed" if episode_id else "attempted_unavailable"
        except Exception as exc:
            episode["status"] = "attempted_unavailable"
            warning(
                "T108 episode unavailable during transition resume: %s"
                % type(exc).__name__,
                category="conversation_management",
            )
        action_handler._write_location_transition_checkpoint(checkpoint)

    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    compaction = checkpoint["conversation_compaction"]
    if compaction.get("status") != "committed":
        from core.ai.cumulative_summary import compact_with_accepted_departure_summary

        current_history = load_json_file(json_file) or []
        summary_message_id = compaction.get("summary_message_id") or str(uuid4())
        compacted, summary_entry = compact_with_accepted_departure_summary(
            current_history,
            source_index=checkpoint["origin_history_boundary"],
            source_entries_before=checkpoint["origin_segment_before"],
            leaving_location_name=checkpoint["origin_location_name"],
            summary=checkpoint["departure_summary"]["text"],
            summary_message_id=summary_message_id,
        )
        marker = {
            "role": "user",
            "content": "Location transition: %s (%s) to %s (%s)"
            % (
                checkpoint["origin_location_name"],
                checkpoint["origin_location_id"],
                world.get("currentLocation"),
                world.get("currentLocationId"),
            ),
        }
        summary_index = next(
            i
            for i, message in enumerate(compacted)
            if isinstance(message, dict)
            and message.get("message_id") == summary_message_id
        )
        if summary_index + 1 >= len(compacted) or compacted[summary_index + 1] != marker:
            compacted.insert(summary_index + 1, marker)
        compaction.update(
            {
                "status": "pending",
                "source_index": checkpoint["origin_history_boundary"],
                "source_entries_before": checkpoint["origin_segment_before"],
                "result_entries_after": [summary_entry, marker],
                "summary_message_id": summary_message_id,
            }
        )
        action_handler._write_location_transition_checkpoint(checkpoint)
        save_conversation_history(compacted, strict=True, allow_compression=False)
        checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
        checkpoint["conversation_compaction"]["status"] = "committed"
        checkpoint["phase"] = "history_compacted"
        action_handler._write_location_transition_checkpoint(checkpoint)

    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    chronicle = checkpoint["chunked_chronicle"]
    if chronicle.get("status") == "pending":
        from core.ai.chunked_compression_integration import (
            check_and_perform_chunked_compression,
        )

        history_before = load_json_file(json_file) or []
        chronicle.update(
            {
                "source_index": 0,
                "source_entries_before": history_before,
                "result_entries_after": None,
            }
        )
        action_handler._write_location_transition_checkpoint(checkpoint)
        try:
            changed = check_and_perform_chunked_compression()
            history_after = load_json_file(json_file) or []
            checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
            checkpoint["chunked_chronicle"].update(
                {
                    "status": "committed" if changed else "not_due",
                    "result_entries_after": history_after,
                }
            )
        except Exception as exc:
            checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
            checkpoint["chunked_chronicle"]["status"] = "attempted_unavailable"
            warning(
                "T027 chronicle remained unavailable during resume: %s"
                % type(exc).__name__,
                category="conversation_management",
            )
        action_handler._write_location_transition_checkpoint(checkpoint)

    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    memory = checkpoint["legacy_memory"]
    if memory.get("status") == "pending":
        # [travel-clean #209] Legacy companion-memory reconciliation is deferred until the
        # voice/episodic line lands on main; CompanionMemoryManager.process_journal_operation
        # is absent here. Mark the phase resolved so recovery converges, then skip the block.
        memory["status"] = "not_applicable"
        action_handler._write_location_transition_checkpoint(checkpoint)
    if memory.get("status") == "__deferred_209__":
        from core.memories.companion_memory import CompanionMemoryManager
        from utils.npc_name_canonicalizer import get_canonical_name

        canonical_npcs = []
        for npc in party.get("partyNPCs", []):
            npc_name = npc.get("name", "") if isinstance(npc, dict) else str(npc)
            if npc_name:
                canonical = get_canonical_name(npc_name)
                if canonical:
                    canonical_npcs.append(canonical)
        memory["roster_before"] = canonical_npcs
        action_handler._write_location_transition_checkpoint(checkpoint)
        if canonical_npcs:
            manager = CompanionMemoryManager()
            manager.process_journal_operation(
                checkpoint["departure_commit"]["journal_entry_after"],
                canonical_npcs,
                checkpoint["operation_id"],
            )
            try:
                subprocess.run(
                    [
                        sys.executable,
                        "scripts/memory_management/compress_memories.py",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except Exception as exc:
                warning(
                    "Legacy memory compression remained unavailable: %s"
                    % type(exc).__name__,
                    category="conversation_management",
                )
            memory["status"] = "committed"
        else:
            memory["status"] = "not_applicable"
        checkpoint["phase"] = "enrichments_committed"
        action_handler._write_location_transition_checkpoint(checkpoint)

    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    deferred = checkpoint["deferred_actions"]
    while int(deferred.get("cursor", 0)) < len(deferred.get("actions", [])):
        cursor = int(deferred.get("cursor", 0))
        if deferred["actions"][cursor].get("family") in {"saveGame", "exitGame"}:
            break
        outcome = action_handler.apply_current_transition_action(operation_id, cursor)
        if outcome == "blocked_conflict":
            return {"status": "blocked", "reason": "deferred action conflict"}
        checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
        deferred = checkpoint["deferred_actions"]

    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    narration_record = checkpoint["narration"]
    handoff = checkpoint.get("module_handoff")
    if (
        narration_record.get("status") == "deferred_to_module_handoff"
        and isinstance(handoff, dict)
        and handoff.get("status") == "authority_transferred"
    ):
        target_party = load_json_file("party_tracker.json") or {}
        target_history, target_party = rebuild_conversation_for_current_party(
            load_json_file(json_file) or [], return_party=True
        )
        first = generate_transition_narration(
            "Describe the committed arrival at the new module from the "
            "authoritative destination context.",
            target_party,
        )
        arrival = generate_arrival_narration(first, target_party, target_history)
        final_text = generate_seamless_transition_narration(first, arrival)
        final_text = _append_transition_outcomes(
            final_text, checkpoint, target_party
        )
        entry = {
            "role": "assistant",
            "content": final_text,
            "message_id": narration_record["message_id"],
        }
        existing = next(
            (
                index
                for index, item in enumerate(target_history)
                if isinstance(item, dict)
                and item.get("message_id") == narration_record["message_id"]
            ),
            None,
        )
        narration_record.update(
            {
                "status": "retained",
                "text": final_text,
                "history_index": len(target_history)
                if existing is None
                else existing,
                "history_entry_after": entry,
            }
        )
        checkpoint["phase"] = "narration_retained"
        action_handler._write_location_transition_checkpoint(checkpoint)
        if existing is None:
            target_history.append(entry)
            save_conversation_history(
                target_history, strict=True, allow_compression=False
            )
        elif target_history[existing] != entry:
            return {"status": "blocked", "reason": "handoff narration conflict"}

    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    narration_record = checkpoint["narration"]
    if publish and narration_record.get("status") == "retained":
        display_dm_narration(
            narration_record["text"], message_id=narration_record["message_id"]
        )
        checkpoint["narration"]["status"] = "published"
        action_handler._write_location_transition_checkpoint(checkpoint)

    final_history = load_json_file(json_file) or []
    final_party = load_json_file("party_tracker.json") or {}
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    checkpoint["final_context"].update(
        {
            "status": "committed",
            "history_before": final_history,
            "history_after": final_history,
            "party_projection_after": _party_transition_projection(final_party),
            "context_after": get_location_data_from_party_tracker(final_party),
        }
    )
    checkpoint["phase"] = "final_context_committed"
    action_handler._write_location_transition_checkpoint(checkpoint)
    checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
    deferred = checkpoint["deferred_actions"]
    while int(deferred.get("cursor", 0)) < len(deferred.get("actions", [])):
        cursor = int(deferred.get("cursor", 0))
        if deferred["actions"][cursor].get("family") not in {"saveGame", "exitGame"}:
            raise RuntimeError(
                "only a final saveGame or exitGame may follow final context"
            )
        outcome = action_handler.apply_current_transition_action(operation_id, cursor)
        if outcome == "blocked_conflict":
            return {"status": "blocked", "reason": "save action conflict"}
        checkpoint = action_handler.load_current_transition_checkpoint(operation_id)
        deferred = checkpoint["deferred_actions"]
    terminal_action = None
    if checkpoint["deferred_actions"].get("actions"):
        last_family = checkpoint["deferred_actions"]["actions"][-1].get("family")
        if last_family == "exitGame":
            terminal_action = "exit"
    final_narration = checkpoint["narration"].get("text", "")
    action_handler.complete_location_transition_checkpoint(operation_id)
    return {
        "status": "completed",
        "operation_id": operation_id,
        "narration": final_narration,
        "terminal_action": terminal_action,
    }


def replace_transition_narration(
    conversation_history, narration, expected_placeholder=None
):
    """Replace the T013 placeholder belonging to the latest transition only.

    Searching backward for an arbitrary assistant message can overwrite output
    from another action that completed while T063/T064 were running.  The
    transition marker narrows the search and the exact value returned by T013
    identifies its placeholder even if a parallel completion lands first.
    """
    transition_index = None
    for index in range(len(conversation_history) - 1, -1, -1):
        message = conversation_history[index]
        if (
            message.get("role") == "user"
            and "Location transition:" in message.get("content", "")
        ):
            transition_index = index
            break

    if transition_index is None:
        return False

    for index in range(transition_index + 1, len(conversation_history)):
        message = conversation_history[index]
        if (
            message.get("role") == "assistant"
            and (
                expected_placeholder is None
                or message.get("content") == expected_placeholder
            )
        ):
            conversation_history[index]["content"] = narration
            return True
    return False


def remove_transition_placeholder(conversation_history, expected_placeholder):
    """Remove only the exact unseen T013 output for the latest transition."""
    if not isinstance(expected_placeholder, str) or not expected_placeholder:
        return False
    transition_index = None
    for index in range(len(conversation_history) - 1, -1, -1):
        message = conversation_history[index]
        if (
            message.get("role") == "user"
            and "Location transition:" in message.get("content", "")
        ):
            transition_index = index
            break
    if transition_index is None:
        return False
    for index in range(transition_index + 1, len(conversation_history)):
        message = conversation_history[index]
        if (
            message.get("role") == "assistant"
            and message.get("content") == expected_placeholder
        ):
            del conversation_history[index]
            return True
    return False

# Message combination system helper functions
def detect_create_encounter(parsed_data):
    """Check if the parsed response contains a createEncounter action"""
    if not isinstance(parsed_data, dict) or "actions" not in parsed_data:
        return False
    
    actions = parsed_data.get("actions", [])
    for action in actions:
        if isinstance(action, dict) and action.get("action") == "createEncounter":
            return True
    return False

def combine_messages(first_response, second_response):
    """Combine two JSON responses into a single cohesive message"""
    try:
        # Parse both responses
        first_data = json.loads(first_response)
        second_data = json.loads(second_response)
        
        # Combine narrations
        first_narration = first_data.get("narration", "")
        second_narration = second_data.get("narration", "")
        combined_narration = f"{first_narration}\n\n{second_narration}"
        
        # Combine actions
        first_actions = first_data.get("actions", [])
        second_actions = second_data.get("actions", [])
        combined_actions = first_actions + second_actions
        
        # Create combined response
        combined_data = {
            "narration": combined_narration,
            "actions": combined_actions
        }
        
        return json.dumps(combined_data, indent=2)
        
    except json.JSONDecodeError as e:
        error(f"FAILURE: Error combining messages", exception=e, category="narrative_generation")
        # Fallback: return second response if combination fails
        return second_response
    except Exception as e:
        error(f"FAILURE: Unexpected error combining messages", exception=e, category="narrative_generation")
        return second_response

def clear_message_buffer():
    """Reset the message buffering state"""
    global held_response, awaiting_combat_resolution
    held_response = None
    awaiting_combat_resolution = False

def get_npc_stat(npc_name, stat_name, time_estimate):
    debug(f"STATE_CHANGE: get_npc_stat called for {npc_name}, stat: {stat_name}", category="npc_management")
    # Load party tracker to get correct module
    party_data = load_json_file("party_tracker.json")
    module_name = party_data.get("module", "").replace(" ", "_")
    path_manager = ModulePathManager(module_name)
    npc_file = path_manager.get_character_path(npc_name)
    try:
        with open(npc_file, "r", encoding="utf-8") as file:
            npc_stats = json.load(file)
    except FileNotFoundError:
        error(f"FAILURE: {npc_file} not found. Stat retrieval failed.", category="file_operations")
        return "NPC stat not found"
    except json.JSONDecodeError:
        error(f"FAILURE: {npc_file} has an invalid JSON format. Stat retrieval failed.", category="file_operations")
        return "NPC stat not found"

    stat_value = None
    modifier_value = None

    if npc_stats:
        if stat_name.lower() in npc_stats["abilities"]:
            stat_value = npc_stats["abilities"][stat_name.lower()]
            modifier_value = (stat_value - 10) // 2

    if stat_value is not None and modifier_value is not None:
        # Update the world time based on the time estimate (in minutes)
        update_world_time(time_estimate)

        return f"NPC's {stat_name.capitalize()}: {stat_value} (Modifier: {modifier_value})"
    else:
        return "NPC stat not found"

def parse_json_safely(text):
    # First, try to parse as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract from code block
    json_content = extract_json_from_codeblock(text)
    try:
        return json.loads(json_content)
    except json.JSONDecodeError:
        pass

    # If all else fails, try to find any JSON-like structure
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError:
        pass

    # If we still can't parse it, raise an exception
    raise json.JSONDecodeError("Unable to parse JSON from the given text", text, 0)


def _parse_dm_validation_verdict(response_text):
    """Parse T065's exact semantic-validation response contract."""
    verdict = parse_json_safely(response_text)
    if (
        not isinstance(verdict, dict)
        or set(verdict) != {"valid", "reason"}
        or type(verdict["valid"]) is not bool
        or not isinstance(verdict["reason"], str)
        or not verdict["reason"].strip()
    ):
        raise ValueError(
            "T065 requires exactly a boolean valid field and nonempty reason"
        )
    return verdict["valid"], verdict["reason"].strip()

def create_module_validation_context(party_tracker_data, path_manager):
    """Create module data context for validation system to check location/NPC references"""
    try:
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]
        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
        current_module = party_tracker_data.get("module", "Unknown")
        
        validation_context = f"MODULE VALIDATION DATA:\nCurrent Module: {current_module}\nCurrent Area: {current_area_id}\nCurrent Location: {current_location_id}\n\n"
        
        # NPC context now dynamically built in validate_dm_response function
        # No longer loading static NPC compendium here
        
        # Get all valid locations in current area and location-specific NPCs
        area_file = path_manager.get_area_path(current_area_id)
        current_location_npcs = []
        area_locations_with_npcs = {}
        
        try:
            with open(area_file, "r", encoding="utf-8") as file:
                area_data = json.load(file)

            valid_location_ids = []
            for location in area_data.get("locations", []):
                loc_id = location.get("locationId", "")
                loc_name = location.get("name", "")
                if loc_id:
                    valid_location_ids.append(
                        f"{loc_id} ({loc_name})" if loc_name else loc_id
                    )
                    
                    # Track NPCs by location
                    location_npcs = [npc.get("name") for npc in location.get("npcs", []) if npc.get("name")]
                    if location_npcs:
                        area_locations_with_npcs[loc_id] = location_npcs
                    
                    # Collect NPCs for current location
                    if loc_id == current_location_id:
                        current_location_npcs = location_npcs.copy()  # Start with location NPCs

            # Add party NPCs to current location (they travel with the party)
            party_npcs = party_tracker_data.get("partyNPCs", [])
            for party_npc in party_npcs:
                npc_name = party_npc.get("name", "")
                if npc_name and npc_name not in current_location_npcs:
                    current_location_npcs.append(npc_name)
            
            # IDs AND names: the validator judges narration, and narration
            # speaks in names. An ids-only list made it reject the area's own
            # location names as hallucinations.
            validation_context += f"Current area ({current_area_id}) locations: "
            if valid_location_ids:
                validation_context += ", ".join(valid_location_ids)
            else:
                validation_context += "None found"
            validation_context += "\n\n"
                
        except (FileNotFoundError, json.JSONDecodeError):
            validation_context += f"ERROR: Could not load area data for {current_area_id}\n\n"
        
        # Add ALL accessible locations from the entire module using LocationGraph
        try:
            all_accessible_locations = []
            areas_included = set()

            graph = location_graph
            if graph is not None and not getattr(graph, "nodes", None):
                # A booted-but-empty graph has been observed live (0 nodes in
                # a hosted world); one reload attempt is cheap.
                try:
                    graph.reload()
                except Exception:
                    pass

            if graph is not None:
                for loc_id, node_info in graph.nodes.items():
                    area_id = node_info.get('area_id', '')
                    location_name = node_info.get('location_name', '')
                    if area_id and location_name:
                        areas_included.add(area_id)
                        all_accessible_locations.append(f"{loc_id} ({location_name}) in area {area_id}")

            if not all_accessible_locations:
                # NEVER hand the validator a context without the module-wide
                # location list: it treats the current-area list as the whole
                # world and auto-rejects every legitimate cross-area
                # reference. Scan the module's area files directly (live
                # first, pristine _BU as last resort).
                warning(
                    "VALIDATION: location graph unavailable/empty; building "
                    "validator location list from area files",
                    category="ai_validation",
                )
                seen_fallback = set()
                safe_module = str(current_module or "").replace(" ", "_")
                patterns = [
                    os.path.join("modules", safe_module, "areas", "*.json"),
                    os.path.join("modules", safe_module, "*.json"),
                ]
                candidate_files = []
                for pattern in patterns:
                    candidate_files.extend(glob.glob(pattern))
                live_files = [f for f in candidate_files
                              if not f.endswith(("_BU.json", "_backup.json"))]
                bu_files = [f for f in candidate_files if f.endswith("_BU.json")]
                for scan in (live_files, bu_files):
                    if all_accessible_locations:
                        break
                    for area_path in scan:
                        try:
                            area_data = safe_json_load(area_path)
                        except Exception:
                            continue
                        if not isinstance(area_data, dict):
                            continue
                        scanned_area_id = str(
                            area_data.get("areaId")
                            or os.path.splitext(os.path.basename(area_path))[0]
                            .replace("_BU", "")
                        )
                        for location in area_data.get("locations", []):
                            if not isinstance(location, dict):
                                continue
                            loc_id = str(location.get("locationId") or "").strip()
                            loc_name = str(location.get("name") or "").strip()
                            if not loc_id or loc_id.upper() in seen_fallback:
                                continue
                            seen_fallback.add(loc_id.upper())
                            areas_included.add(scanned_area_id)
                            all_accessible_locations.append(
                                f"{loc_id} ({loc_name}) in area {scanned_area_id}"
                            )

            validation_context += f"ALL ACCESSIBLE LOCATIONS (across {len(areas_included)} areas):\n"
            if all_accessible_locations:
                # Sort by area for clarity
                all_accessible_locations.sort()
                # Include all locations since we only have ~78 total which is manageable
                validation_context += "\n".join([f"- {loc}" for loc in all_accessible_locations])
            else:
                validation_context += "- No locations found in location graph"
            validation_context += "\n\n"
            validation_context += "MULTI-AREA TRAVEL NOTE: transitionLocation can target ANY accessible location above, not just those in the current area. Mentioning, revealing, or discussing ANY location above in narration is always valid and is NOT a hallucination.\n\n"
                
        except Exception as e:
            validation_context += f"ERROR: Could not load location graph data: {str(e)}\n\n"
        
        # Get all valid NPCs from ALL module codexes
        try:
            valid_npcs = []
            
            # Import all module codexes and merge their NPCs
            modules_dir = "modules"
            if os.path.exists(modules_dir):
                for item in os.listdir(modules_dir):
                    module_path = os.path.join(modules_dir, item)
                    if (os.path.isdir(module_path) and 
                        not item.startswith('.') and 
                        item not in ['campaign_archives', 'campaign_summaries', 'conversation_history', 'encounters', 'logs', 'backups']):
                        
                        # Check if this module has a codex file
                        codex_file = os.path.join(module_path, "npc_codex.json")
                        if os.path.exists(codex_file):
                            try:
                                with open(codex_file, "r", encoding="utf-8") as f:
                                    codex = json.load(f)
                                
                                for npc_entry in codex.get("npcs", []):
                                    if isinstance(npc_entry, dict) and "name" in npc_entry:
                                        npc_name = npc_entry["name"]
                                        source = npc_entry.get("source", "unknown")
                                        valid_npcs.append(f"{npc_name} (Module: {item})")
                            except Exception as e:
                                continue
            
            # DEBUG: Print what NPCs are being passed to validator
            # print("\n" + "="*60)
            # print("DEBUG: NPC VALIDATION CONTEXT BEING CREATED")
            # print("="*60)
            # print(f"Total NPCs found across all modules: {len(valid_npcs)}")
            # if valid_npcs:
            #     print("NPCs being passed to validator:")
            #     for npc in valid_npcs:
            #         print(f"  - {npc}")
            #         if "Kira" in npc:
            #             print(f"    ^^^ FOUND KIRA: {npc}")
            # else:
            #     print("WARNING: NO NPCs found in any module codex!")
            # print("="*60)
            # print()
            
            # Add party members to the valid characters list
            validation_context += "VALID CHARACTERS (Party Members and All Module NPCs):\n"
            
            # First add party members from party tracker
            party_members = party_tracker_data.get("partyMembers", [])
            for member in party_members:
                validation_context += f"- {member} (party member)\n"
            
            # Then add NPCs from codexes
            if valid_npcs:
                validation_context += "\n".join([f"- {npc}" for npc in valid_npcs])
            else:
                validation_context += "- No NPCs found in module codexes"
                
        except Exception as e:
            # Fallback to original character file method if codex fails
            # print(f"DEBUG: Exception in NPC codex loading: {e}")
            # print(f"DEBUG: Exception type: {type(e)}")
            # print("DEBUG: Falling back to character files method")
            # print(f"WARNING: NPC codex failed, falling back to character files: {e}")
            character_files = glob.glob(f"{path_manager.module_dir}/characters/*.json")
            
            valid_npcs = []
            for char_file in character_files:
                try:
                    with open(char_file, "r", encoding="utf-8") as file:
                        char_data = json.load(file)
                    char_name = char_data.get("name", "")
                    char_type = char_data.get("character_type", "unknown")
                    if char_name:
                        valid_npcs.append(f"{char_name} ({char_type})")
                except (json.JSONDecodeError, KeyError):
                    continue
            
            validation_context += "VALID CHARACTERS (Party Members and Module Characters):\n"
            
            # First add party members from party tracker
            party_members = party_tracker_data.get("partyMembers", [])
            for member in party_members:
                validation_context += f"- {member} (party member)\n"
            
            # Then add NPCs from character files
            if valid_npcs:
                validation_context += "\n".join([f"- {npc}" for npc in valid_npcs])
            else:
                validation_context += "- No character files found"
        
        # Add location-aware NPC context
        validation_context += f"\n\nLOCATION-AWARE NPC VALIDATION:\n"
        validation_context += f"Current Location: {current_location_id}\n"
        
        if current_location_npcs:
            validation_context += f"NPCs PRESENT at current location ({current_location_id}):\n"
            validation_context += "\n".join([f"- {npc}" for npc in current_location_npcs])
            validation_context += "\n\n"
        else:
            validation_context += f"NO NPCs present at current location ({current_location_id})\n\n"
        
        if area_locations_with_npcs:
            validation_context += "NPCs at OTHER locations in this area:\n"
            for loc_id, npcs in area_locations_with_npcs.items():
                if loc_id != current_location_id:  # Don't repeat current location
                    validation_context += f"  {loc_id}: {', '.join(npcs)}\n"
            validation_context += "\n"
        
        validation_context += """ENHANCED VALIDATION RULES:
1. For interactions happening AT the current location, ONLY use NPCs from the "PRESENT at current location" list
2. For references to NPCs at OTHER locations, they must exist in the "NPCs at OTHER locations" or module character lists
3. NEVER create new NPCs - all names must exist in the provided lists
4. If an NPC is referenced incorrectly, suggest the CORRECT NPC from the current location list
5. NPCs cannot be in multiple locations simultaneously - verify location consistency

CHARACTER NAME RULES FOR updateCharacterInfo:
- ALWAYS use the FULL character name exactly as it appears in the party tracker or NPC lists
- For party NPCs, use their complete name (e.g., "Scout Kira" not "kira", "Sir Aldric" not "aldric")
- For party members, use the exact name from partyMembers list
- NEVER shorten or modify character names in action parameters
- If a character has a title or descriptor, it MUST be included (e.g., "Scout Kira", "Knight Commander Marcus")

CRITICAL: If validation fails due to wrong NPC for location, provide specific correction using NPCs actually present at the current location."""
        
        return validation_context
        
    except Exception as e:
        # print(f"DEBUG: MAJOR EXCEPTION in create_module_validation_context: {e}")
        # print(f"DEBUG: Exception type: {type(e)}")
        # import traceback
        # print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return f"MODULE VALIDATION DATA: Error loading module data - {str(e)}"

def normalize_character_names_in_response(response_text, party_tracker_data):
    """
    Normalize NPC names in updateCharacterInfo actions before validation.
    Handles name variations like "Kira" -> "Scout Kira", "Ranger Kira" -> "Scout Kira"

    Returns:
        (normalized_response, message) or (None, error_message) if unresolvable
    """
    from utils.npc_name_normalizer import normalize_npc_name_for_action

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        # If it's not valid JSON, skip normalization
        return response_text, "JSON invalid - skipping NPC normalization"

    if 'actions' not in parsed or not isinstance(parsed['actions'], list):
        # No actions to normalize
        return response_text, "No actions to normalize"

    corrections = []
    rejections = []

    for i, action in enumerate(parsed['actions']):
        if not isinstance(action, dict):
            continue

        action_type = action.get('action')

        # Only normalize updateCharacterInfo actions
        if action_type == 'updateCharacterInfo':
            params = action.get('parameters', {})
            original_name = params.get('characterName')

            if original_name:
                print(f"[NPC_NORM] Checking updateCharacterInfo action with characterName='{original_name}'")

                # Try to normalize the name
                normalized_name, match_type = normalize_npc_name_for_action(
                    original_name, party_tracker_data, debug_print=True
                )

                if normalized_name is None:
                    # Could not resolve name - reject
                    rejections.append(f"Action {i+1}: '{original_name}' not in party tracker")
                    print(f"[NPC_NORM] REJECT: '{original_name}' cannot be matched to party tracker")

                elif normalized_name != original_name:
                    # Name was normalized
                    params['characterName'] = normalized_name
                    corrections.append(f"Action {i+1}: '{original_name}' -> '{normalized_name}'")
                    print(f"[NPC_NORM] CORRECTED: '{original_name}' -> '{normalized_name}'")

                else:
                    # Name was already correct
                    print(f"[NPC_NORM] OK: '{original_name}' matches party tracker")

    # If any rejections, return error
    if rejections:
        error_msg = "NPC names not in party tracker: " + "; ".join(rejections)
        error_msg += f". Valid party NPCs: {[npc.get('name') for npc in party_tracker_data.get('partyNPCs', [])]}"
        error_msg += f". Valid party members: {party_tracker_data.get('partyMembers', [])}"
        return None, error_msg

    # If corrections were made, return updated response
    if corrections:
        corrected_response = json.dumps(parsed, ensure_ascii=True, indent=2)
        message = "Auto-corrected NPC names: " + "; ".join(corrections)
        return corrected_response, message

    # No changes needed
    return response_text, "All NPC names valid"

def validate_json_structure(response_text):
    """
    Pre-validate JSON structure before sending to AI validator.
    Returns tuple: (is_valid, fixed_response, error_message)
    """
    try:
        # Parse the JSON
        parsed = json.loads(response_text)
        
        # Check top-level structure
        if not isinstance(parsed, dict):
            return False, None, "Response is not a JSON object"
        
        if "narration" not in parsed:
            return False, None, "Missing 'narration' field"
        
        if "actions" not in parsed:
            # Add empty actions array if missing
            parsed["actions"] = []
            fixed = json.dumps(parsed, ensure_ascii=True)
            return True, fixed, "Added missing actions array"
        
        if not isinstance(parsed["actions"], list):
            return False, None, "'actions' must be an array"
        
        # Check each action's structure
        fixed_actions = []
        structure_issues = []
        
        for i, action in enumerate(parsed["actions"]):
            if not isinstance(action, dict):
                structure_issues.append(f"Action {i+1} is not an object")
                continue
                
            # Check if action has correct structure
            if "action" in action and "parameters" in action:
                # Correct structure
                fixed_actions.append(action)
            elif len(action) == 1:
                # Likely wrong format like {"updatePlot": {...}}
                action_name = list(action.keys())[0]
                action_params = action[action_name]

                # Module publication is deliberately stricter than legacy
                # actions: do not silently rewrite another external contract
                # into createNewModule.
                if action_name == "createNewModule":
                    structure_issues.append(
                        f"Action {i+1} createNewModule has invalid structure"
                    )
                    continue
                
                # Auto-fix to correct structure
                fixed_action = {
                    "action": action_name,
                    "parameters": action_params if isinstance(action_params, dict) else {}
                }
                fixed_actions.append(fixed_action)
                structure_issues.append(f"Auto-fixed action {i+1}: {action_name}")
            else:
                structure_issues.append(f"Action {i+1} has invalid structure")
        
        structure_message = "Structure valid"
        validated_response = response_text

        # If we fixed any actions, retain that candidate for deterministic
        # action-specific validation below.
        if structure_issues and len(fixed_actions) == len(parsed["actions"]):
            parsed["actions"] = fixed_actions
            validated_response = json.dumps(parsed, ensure_ascii=True, indent=2)
            structure_message = (
                f"Auto-fixed structure issues: {'; '.join(structure_issues)}"
            )
        elif structure_issues:
            return False, None, f"Structure errors: {'; '.join(structure_issues)}"

        try:
            from core.ai.module_creation_contract import (
                validate_create_new_module_actions,
            )

            validate_create_new_module_actions(parsed["actions"])
        except ValueError as contract_error:
            return False, None, f"Module creation contract error: {contract_error}"

        return True, validated_response, structure_message
        
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return False, None, f"Validation error: {str(e)}"


_ENHANCED_DM_NOTE_PREFIX = "Dungeon Master Note:"
_ENHANCED_PLAYER_MARKER = " Player: "
_INVENTORY_CONTEXT_MARKER = "\n[Inventory Context:"
_SRD_CONTEXT_MARKER = "\n[SRD CONTEXT"


def _extract_raw_player_message(content):
    """Remove generated DM/inventory context from a persisted player turn."""
    if not isinstance(content, str):
        return ""
    if not content.startswith(_ENHANCED_DM_NOTE_PREFIX):
        return content
    if _ENHANCED_PLAYER_MARKER not in content:
        return ""

    player_text = content.rsplit(_ENHANCED_PLAYER_MARKER, 1)[1]
    generated_context_indexes = [
        index
        for index in (
            player_text.find(_INVENTORY_CONTEXT_MARKER),
            player_text.find(_SRD_CONTEXT_MARKER),
        )
        if index >= 0
    ]
    if generated_context_indexes:
        player_text = player_text[: min(generated_context_indexes)]
    return player_text.strip()


def _select_validation_history(conversation_history, raw_user_input, limit=4):
    """Return bounded player-authored history without injected prompt text."""
    history = conversation_history if isinstance(conversation_history, list) else []
    current_enhanced_index = None
    normalized_current = str(raw_user_input or "").strip()

    for index in range(len(history) - 1, -1, -1):
        message = history[index]
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content", "")
        if not isinstance(content, str) or not content.startswith(
            _ENHANCED_DM_NOTE_PREFIX
        ):
            continue
        if _extract_raw_player_message(content) == normalized_current:
            current_enhanced_index = index
            break

    recent_messages = []
    skip_next_assistant = False
    for index in range(len(history) - 1, -1, -1):
        if index == current_enhanced_index:
            continue
        message = history[index]
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content", "")
        if not isinstance(content, str):
            continue

        if role == "user" and content.startswith("Error Note:"):
            skip_next_assistant = True
            continue
        if role == "assistant" and skip_next_assistant:
            skip_next_assistant = False
            continue
        if role not in {"user", "assistant"}:
            continue
        if content.startswith(("Location transition:", "Module transition:")):
            continue

        if role == "user":
            content = _extract_raw_player_message(content)
            if not content:
                continue
        recent_messages.insert(0, {"role": role, "content": content})
        if len(recent_messages) >= limit:
            break

    while len(recent_messages) < limit:
        recent_messages.insert(
            0,
            {
                "role": "assistant",
                "content": "Previous context not available.",
            },
        )
    return recent_messages


def _assemble_validation_messages(
    validation_prefix,
    raw_user_input,
    candidate_response,
    compress_prefix=None,
    srd_context=None,
    local_template_tail=False,
):
    """Compress context first, then preserve the raw intent/candidate pair.

    local_template_tail (issue #168): the array otherwise ENDS on the assistant-role
    candidate message. Strict-alternation chat templates on local models (e.g. Gemma
    via LM Studio) treat a trailing assistant turn as an already-finished model turn
    and emit an immediate end-of-turn -> empty content, finish_reason=stop, on every
    call -- which hard-blocks gameplay now that T065 fails closed. For the Local/
    Custom provider ONLY, append one minimal mechanical closing user turn so the
    array ends on a user message with alternation intact. The exact raw-intent /
    candidate pair is preserved verbatim and adjacent; cloud/legacy/gemini requests
    are byte-identical to before.
    """
    prefix = [dict(message) for message in validation_prefix]
    if compress_prefix is not None:
        prefix = compress_prefix(prefix)
    if srd_context:
        prefix.append({"role": "system", "content": srd_context})
    tail = [
        {"role": "user", "content": str(raw_user_input or "")},
        {"role": "assistant", "content": candidate_response},
    ]
    if local_template_tail:
        tail.append({"role": "user", "content": "Return the JSON verdict now."})
    return prefix + tail


def validate_ai_response(
    primary_response,
    user_input,
    validation_prompt_text,
    conversation_history,
    party_tracker_data,
    srd_context=None,
    npc_voice_batch=None,
    transition_facts=None,
):
    print("DEBUG: NPC validation running...")
    status_validating()
    
    # Pre-validate JSON structure
    is_valid_structure, fixed_response, structure_message = validate_json_structure(primary_response)
    
    if not is_valid_structure:
        # Structure is too broken to fix automatically
        print(f"ERROR: JSON structure invalid - {structure_message}")
        return (False, f"JSON structure error: {structure_message}. Response must be valid JSON with 'narration' and 'actions' fields.")
    
    # Use fixed response if structure was auto-corrected
    response_to_validate = fixed_response if fixed_response != primary_response else primary_response

    if fixed_response != primary_response:
        print(f"INFO: Auto-fixed JSON structure - {structure_message}")

    # Pre-validate and normalize NPC names in updateCharacterInfo actions
    npc_normalized_response, npc_normalization_message = normalize_character_names_in_response(
        response_to_validate, party_tracker_data
    )

    if npc_normalized_response is None:
        # Name normalization failed - unresolvable NPC name
        print(f"ERROR: NPC name validation failed - {npc_normalization_message}")
        return (False, f"NPC name error: {npc_normalization_message}")

    if npc_normalized_response != response_to_validate:
        print(f"INFO: Auto-corrected NPC names - {npc_normalization_message}")
        response_to_validate = npc_normalized_response

    # Keep only player-authored text from prior enhanced turns. The current
    # enhanced DM note is excluded and reintroduced below as exact raw input.
    recent_messages = _select_validation_history(
        conversation_history, user_input, limit=4
    )

    # Get location data from party tracker
    current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]
    current_area_id = party_tracker_data["worldConditions"]["currentAreaId"]

    # Load the area data with correct module
    module_name = party_tracker_data.get("module", "").replace(" ", "_")
    path_manager = ModulePathManager(module_name)
    area_file = path_manager.get_area_path(current_area_id)
    try:
        with open(area_file, "r", encoding="utf-8") as file:
            area_data = json.load(file)
        location_data = next((loc for loc in area_data["locations"] if loc["locationId"] == current_location_id), None)
    except (FileNotFoundError, json.JSONDecodeError):
        location_data = None

    # Create the location details message
    if location_data:
        location_details = f"Location Details: {location_data['description']} {location_data.get('dmInstructions', '')}"
    else:
        location_details = "Location Details: Not available."
    
    # NOTE: Path validation now handled by transition intelligence agent in pre-validation
    # This old validation code is disabled to prevent conflicts
    if False and '"action": "transitionLocation"' in primary_response:
        try:
            # Extract the destination from the AI response
            destination_match = re.search(r'"newLocation":\s*"([^"]*)"', primary_response)
            if destination_match:
                destination = destination_match.group(1).strip()
                current_origin = current_location_id
                
                # Validate we have required data
                if not destination:
                    path_info = f"Path Validation ERROR: Empty destination in transitionLocation action."
                elif not current_origin:
                    path_info = f"Path Validation ERROR: Current location ID not available in party tracker."
                elif not location_graph:
                    path_info = f"Path Validation ERROR: Location graph not initialized."
                else:
                    # Check if location_graph is empty and reload if needed
                    if len(location_graph.nodes) == 0:
                        print("DEBUG: [LocationGraph] Global graph is empty, reloading...")
                        location_graph.reload()
                        print(f"DEBUG: [LocationGraph] Reload complete. Total nodes: {len(location_graph.nodes)}")

                    # Validate path using location graph
                    print(f"DEBUG: [LocationGraph] Path validation - From: {current_origin}, To: {destination}")
                    print(f"DEBUG: [LocationGraph] Current graph state - Nodes: {len(location_graph.nodes)}, Has origin: {current_origin in location_graph.nodes}")
                    success, path, message = location_graph.find_path(current_origin, destination)
                    
                    if success:
                        path_info = f"The party is currently at {current_origin} and desires to travel to {destination}. VALID PATH FOUND. The path of travel is: {' -> '.join(path)}."
                    else:
                        path_info = f"The party is currently at {current_origin} and desires to travel to {destination}. INVALID PATH: {message}"
                
                # Add path validation to location details
                location_details += f"\n\nPath Validation: {path_info}"
            else:
                # transitionLocation detected but no newLocation parameter found
                location_details += f"\n\nPath Validation ERROR: transitionLocation action detected but destination could not be extracted."
                
        except Exception as e:
            # Catch any unexpected errors in path validation
            location_details += f"\n\nPath Validation ERROR: Failed to validate path - {str(e)}"

    # Create module data context for location/NPC validation
    module_data_context = create_module_validation_context(party_tracker_data, path_manager)
    
    # Extract character names from updateCharacterInfo actions and load their inventories
    character_inventory_context = ""
    try:
        # Parse the primary response to find updateCharacterInfo actions
        response_data = json.loads(primary_response)
        if "actions" in response_data:
            characters_to_load = set()
            for action in response_data["actions"]:
                if action.get("action") == "updateCharacterInfo":
                    char_name = action.get("parameters", {}).get("characterName", "")
                    if char_name:
                        characters_to_load.add(char_name)
            
            # Load character sheets for identified characters
            if characters_to_load:
                character_inventory_context = "\n\nCHARACTER INVENTORY DATA FOR VALIDATION:\n"
                for char_name in characters_to_load:
                    # Try to load from characters directory
                    # Note: get_character_path already adds .json extension
                    char_file_name = char_name.lower().replace(" ", "_")
                    char_path = path_manager.get_character_path(char_file_name)
                    
                    if os.path.exists(char_path):
                        try:
                            with open(char_path, 'r', encoding='utf-8') as f:
                                char_data = json.load(f)
                            
                            # Extract relevant inventory data
                            ammunition = char_data.get("ammunition", [])
                            currency = char_data.get("currency", {})
                            equipment = char_data.get("equipment", [])
                            
                            character_inventory_context += f"\n{char_name}:\n"
                            character_inventory_context += f"  Currency: {currency.get('gold', 0)} gold, {currency.get('silver', 0)} silver, {currency.get('copper', 0)} copper\n"
                            
                            # Add ammunition
                            if ammunition:
                                character_inventory_context += "  Ammunition:\n"
                                for ammo in ammunition:
                                    character_inventory_context += f"    - {ammo.get('name', 'Unknown')}: {ammo.get('quantity', 0)}\n"
                            else:
                                character_inventory_context += "  Ammunition: None\n"
                            
                            # Add equipment and items (especially consumables like potions)
                            consumables = []
                            weapons = []
                            armor = []
                            other_equipment = []
                            
                            for item in equipment:
                                item_name = item.get("item_name", "Unknown")
                                item_type = item.get("item_type", "")
                                quantity = item.get("quantity", 1)
                                
                                if item_type == "consumable" or item.get("consumable", False):
                                    consumables.append(f"{item_name} (x{quantity})")
                                elif item_type == "weapon":
                                    weapons.append(item_name)
                                elif item_type == "armor":
                                    armor.append(item_name)
                                else:
                                    other_equipment.append(item_name)
                            
                            if consumables:
                                character_inventory_context += "  Consumables:\n"
                                for item in consumables:
                                    character_inventory_context += f"    - {item}\n"
                            
                            if weapons:
                                character_inventory_context += "  Weapons:\n"
                                for item in weapons:
                                    character_inventory_context += f"    - {item}\n"
                            
                            if armor:
                                character_inventory_context += "  Armor:\n"
                                for item in armor:
                                    character_inventory_context += f"    - {item}\n"
                            
                            if other_equipment:
                                character_inventory_context += "  Other Equipment:\n"
                                for item in other_equipment:
                                    character_inventory_context += f"    - {item}\n"
                        except Exception as e:
                            debug(f"VALIDATION: Could not load character data for {char_name}: {e}", category="ai_validation")
                    else:
                        debug(f"VALIDATION: Character file not found: {char_path}", category="ai_validation")
                
                if character_inventory_context != "\n\nCHARACTER INVENTORY DATA FOR VALIDATION:\n":
                    debug(f"VALIDATION: Loaded inventory data for: {', '.join(characters_to_load)}", category="ai_validation")
    except json.JSONDecodeError:
        # Response might not be valid JSON, skip inventory loading
        pass
    except Exception as e:
        debug(f"VALIDATION: Error extracting character names: {e}", category="ai_validation")
    
    # Add structure validation status to context
    structure_validation_note = ""
    if fixed_response != primary_response:
        structure_validation_note = f"JSON STRUCTURE PRE-VALIDATED: {structure_message}. Structure has been auto-corrected. Focus on validating CONTENT only (NPCs, locations, game rules)."
    else:
        structure_validation_note = "JSON STRUCTURE PRE-VALIDATED: Structure is correct. Focus on validating CONTENT only (NPCs, locations, game rules)."
    
    # Build dynamic NPC context
    npc_validation_context = ""
    try:
        from core.ai.build_npc_context import build_npc_validation_context
        
        # Get party NPCs from party tracker data
        party_npc_names = [npc.get('name') for npc in party_tracker_data.get('partyNPCs', [])]
        
        # Build compressed NPC context
        npc_validation_context = build_npc_validation_context(
            current_module=party_tracker_data.get('module', 'Unknown'),
            current_location=party_tracker_data.get('worldConditions', {}).get('currentLocationId', 'Unknown'),
            party_npcs=party_npc_names
        )
    except Exception as e:
        print(f"ERROR: Failed to build NPC context: {e}")
        import traceback
        traceback.print_exc()
    
    validation_conversation = [
        {"role": "system", "content": validation_prompt_text},
        {"role": "system", "content": structure_validation_note},
        (
            {
                "role": "system",
                "content": (
                    "Accepted Travel Agent facts for this turn (JSON): "
                    + json.dumps(
                        transition_facts,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                ),
            }
            if transition_facts
            else None
        ),
        {"role": "system", "content": npc_validation_context},  # Always include, even if empty
        {"role": "system", "content": location_details},
        {"role": "system", "content": module_data_context},
        {"role": "system", "content": character_inventory_context} if character_inventory_context else None,
    ]
    
    
    # Add recent conversation context
    validation_conversation.extend(recent_messages)
    
    # Filter out None entries
    validation_conversation = [msg for msg in validation_conversation if msg is not None]
    
    # Apply compression to validation messages if enabled
    from model_config import COMPRESSION_ENABLED
    if COMPRESSION_ENABLED:
        temp_file = None
        try:
            # Use the ParallelConversationCompressor to compress validation messages
            # This will automatically detect and compress location summaries, module contexts, etc.
            # The cache will prevent double-compression of already compressed content
            from utils.compression.conversation_compressor_parallel import ParallelConversationCompressor
            from pathlib import Path
            from tempfile import NamedTemporaryFile

            # Each validation owns its own closed temporary file. A fixed path
            # allowed parallel turns to overwrite or delete one another's
            # validation context before compression consumed it.
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="neq-main-validation-",
                suffix=".json",
                delete=False,
            ) as f:
                json.dump(validation_conversation, f, indent=2, ensure_ascii=False)
                temp_file = Path(f.name)
            
            # Compress using the parallel compressor with caching
            # Module creation flag is not available in validation context
            compressor = ParallelConversationCompressor(inject_module_creation=False)
            validation_messages_to_send = compressor.process_conversation_history(str(temp_file))
            
            debug("VALIDATION: Applied parallel compression to validation messages", category="ai_validation")
        except Exception as e:
            # If compression fails, use original messages
            warning(f"VALIDATION: Compression failed, using original messages: {e}", category="ai_validation")
            status_manager.emit_compression_event('compression_error', {'error': str(e)})
            validation_messages_to_send = validation_conversation
        finally:
            if temp_file is not None and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError as cleanup_error:
                    warning(
                        f"VALIDATION: Could not remove temporary context: {cleanup_error}",
                        category="ai_validation",
                    )
    else:
        validation_messages_to_send = validation_conversation

    # The semantic boundary is deliberately outside compression: the exact raw
    # player turn and exact candidate must remain the final adjacent pair.
    # Snapshot the provider once here; the model-config selection below reuses it.
    from model_config import MODEL_PROVIDER as _val_provider
    validation_messages_to_send = _assemble_validation_messages(
        validation_messages_to_send,
        user_input,
        response_to_validate,
        srd_context=srd_context,
        local_template_tail=(_val_provider == "lmstudio"),
    )

    if '"action": "createNewModule"' in response_to_validate:
        debug(
            "VALIDATION: createNewModule raw intent/candidate pair isolated",
            category="ai_validation",
        )
    
    # Export validation messages for debugging
    os.makedirs("debug/api_captures", exist_ok=True)
    with open("debug/api_captures/main_validation_messages_to_api.json", "w", encoding="utf-8") as f:
        json.dump(validation_messages_to_send, f, indent=2, ensure_ascii=False)
    print(f"DEBUG: [MAIN VALIDATION] Exported validation messages to debug/api_captures/main_validation_messages_to_api.json")
    
    # Select per-provider validation model config
    if _val_provider == "openai":
        validation_config = config.DM_VALIDATION_GPT52_LOW
    elif _val_provider == "gemini":
        validation_config = config.DM_VALIDATION_GEMINI_FLASH_LOW
    elif _val_provider == "lmstudio":
        validation_config = config.DM_VALIDATION_LMSTUDIO
    else:  # legacy
        validation_config = config.DM_VALIDATION_LEGACY

    attempt = 0
    while True:
        attempt += 1
        validation_result = capture_and_fanout("T065", api_client.create_completion,
            _request_provider=_val_provider,
            _live_selected=True,
            messages=validation_messages_to_send,
            model=validation_config["model"],
            temperature=0.1,
            **{k: v for k, v in validation_config.items() if k != "model"})

        # Log API call to master log
        try:
            from utils.api_logger import log_api_call
            log_api_call("validation", validation_messages_for_diagnostics, validation_result,
                        metadata={"attempt": attempt, "max_retries": None})
        except Exception as e:
            print(f"[API_LOG] Warning: Failed to log validation call: {e}")

        # Track token usage with context for telemetry
        if USAGE_TRACKING_AVAILABLE:
            try:
                from utils.openai_usage_tracker import get_global_tracker
                tracker = get_global_tracker()
                tracker.track(validation_result, context={'endpoint': 'validation', 'purpose': 'validate_dm_response'})
            except:
                pass

        validation_response = validation_result.choices[0].message.content.strip()

        try:
            is_valid, reason = _parse_dm_validation_verdict(validation_response)
            
            # Track validation pairs for quality control
            try:
                os.makedirs("debug/quality_control", exist_ok=True)
                validation_pair = {
                    "timestamp": datetime.now().isoformat(),
                    "user_input": user_input,  # What the user originally said
                    "assistant_response": response_to_validate,
                    "structure_validation": {
                        "needed_fix": fixed_response != primary_response,
                        "message": structure_message,
                        "original_response": primary_response if fixed_response != primary_response else None
                    },
                    "validation_result": {
                        "valid": is_valid,
                        "reason": reason,
                        "raw_response": validation_response
                    },
                    "attempt": attempt,
                    # Actual model: capture_and_fanout overrides to the registry
                    # binding before the call, so read it from the response, not
                    # the pre-override validation_config.
                    "model_used": getattr(validation_result, "model", None) or validation_config["model"]
                }
                
                # Append to validation pairs log
                validation_log_path = "debug/quality_control/validation_pairs.jsonl"
                with open(validation_log_path, "a", encoding="utf-8") as f:
                    json.dump(validation_pair, f, ensure_ascii=False)
                    f.write("\n")
            except Exception as e:
                debug(f"Failed to log validation pair: {e}", category="ai_validation")

            # Log only failed validations to prompt_validation.json
            if not is_valid:
                log_entry = {
                    "prompt": validation_conversation,
                    "response": validation_response,
                    "reason": reason
                }

                # Ensure debug/logs directory exists
                os.makedirs("debug/logs", exist_ok=True)

                with open("debug/logs/prompt_validation.json", "a", encoding="utf-8") as log_file:
                    json.dump(log_entry, log_file)
                    log_file.write("\n")  # Add a newline for better readability

                return (False, reason)  # Return tuple with failure status and reason
            else:
                debug("SUCCESS: Validation passed successfully", category="ai_validation")
                # Return the fixed/validated response content
                return (True, response_to_validate)  # Return tuple with validation status and content

        except (json.JSONDecodeError, ValueError, TypeError):
            debug(f"VALIDATION: Invalid JSON from validation model (attempt {attempt}); reissuing the same validation packet", category="ai_validation")
            debug(f"VALIDATION: Problematic response: {validation_response}", category="ai_validation")
            continue  # Retry the validation

def load_validation_prompt():
    from model_config import COMPRESSION_ENABLED
    if COMPRESSION_ENABLED:
        # Use compressed validation prompt when compression is enabled
        prompt_file = "prompts/validation/validation_prompt_compressed.txt"
    else:
        prompt_file = "prompts/validation/validation_prompt.txt"
    
    with open(prompt_file, "r", encoding="utf-8") as file:
        return file.read().strip()

def load_json_file(file_path):
    """Load a JSON file, with error handling and encoding sanitization"""
    return safe_json_load(file_path)

def remove_duplicate_npcs(party_tracker_data):
    """Remove duplicate NPCs from party tracker, keeping first occurrence.
    
    Args:
        party_tracker_data: The party tracker dictionary
        
    Returns:
        tuple: (cleaned_data, changes_made) where changes_made is boolean
    """
    if not party_tracker_data or "partyNPCs" not in party_tracker_data:
        return party_tracker_data, False
    
    original_npcs = party_tracker_data["partyNPCs"]
    seen_names = set()
    unique_npcs = []
    duplicates_removed = []
    
    for npc in original_npcs:
        npc_name = npc.get("name", "")
        if npc_name not in seen_names:
            seen_names.add(npc_name)
            unique_npcs.append(npc)
        else:
            duplicates_removed.append(npc_name)
    
    if duplicates_removed:
        debug(f"STATE_CHANGE: Removing duplicate NPCs: {duplicates_removed}", category="npc_management")
        party_tracker_data["partyNPCs"] = unique_npcs
        return party_tracker_data, True
    
    return party_tracker_data, False

def process_conversation_history(history):
    debug("STATE_CHANGE: Processing conversation history", category="conversation_management")
    for message in history:
        if message["role"] == "user" and message["content"].startswith("Leveling Dungeon Master Guidance"):
            message["content"] = "DM Guidance: Proceed with leveling up the player character or the party NPC given the 5th Edition role playing game rules. Only level the player character or party NPC one level at a time to ensure no mistakes are made. If you are leveling up a party NPC then pass all changes at once using the 'updateCharacterInfo' action. If you are leveling up a player character then you must ask the player for important decisions and choices they would have control over. After the player has provided the needed information then use the 'updateCharacterInfo' to pass all changes to the players character sheet and include the experience goal for the next level. Do not update the player's information in segements."
    
    # Apply DM note truncation to clean up bloated messages
    history = truncate_dm_notes(history)
    
    debug("SUCCESS: Conversation history processing complete", category="conversation_management")
    return history

def remove_duplicate_messages(conversation_history):
    """Remove duplicate messages from conversation history, specifically targeting combat system messages"""
    if not conversation_history or len(conversation_history) < 2:
        return conversation_history
    
    cleaned_history = []
    seen_combat_system_messages = set()  # Track unique "[SYSTEM: Combat" messages
    
    for i, msg in enumerate(conversation_history):
        content = msg.get("content", "")
        
        # Check if this is a combat-related system message
        is_combat_system_msg = content.startswith("[SYSTEM: Combat")
        
        # Always keep the first message
        if i == 0:
            cleaned_history.append(msg)
            if is_combat_system_msg:
                seen_combat_system_messages.add(content)
        # For combat system messages, check if we've seen this exact message before
        elif is_combat_system_msg:
            if content not in seen_combat_system_messages:
                cleaned_history.append(msg)
                seen_combat_system_messages.add(content)
            else:
                debug(f"Removed duplicate combat system message at index {i}: {content[:60]}...", category="conversation_management")
        # For all other messages, only check against previous message (original behavior)
        elif msg != conversation_history[i-1]:
            cleaned_history.append(msg)
        else:
            debug(f"Removed duplicate message at index {i}", category="conversation_management")
    
    return cleaned_history

def truncate_dm_notes(conversation_history):
    from core.ai.cumulative_summary import normalize_legacy_dm_notes

    normalized = normalize_legacy_dm_notes(conversation_history)
    conversation_history[:] = normalized
    return conversation_history


def _legacy_absent_target(path):
    return {"path": str(path), "exists": False, "value": None}


def _legacy_json_target(path):
    path = Path(path)
    if not path.exists():
        return _legacy_absent_target(path)
    return {
        "path": str(path),
        "exists": True,
        "value": safe_json_load(path),
    }


def _find_legacy_location_repair(conversation_history):
    """Return the earliest raw legacy transition segment that can be repaired."""
    transitions = []
    for index, message in enumerate(conversation_history):
        content = message.get("content", "") if isinstance(message, dict) else ""
        if message.get("role") == "user" and content.startswith("Location transition:"):
            transitions.append((index, message))

    for ordinal, (transition_index, transition_message) in enumerate(transitions):
        if transition_index > 0:
            previous = conversation_history[transition_index - 1]
            if (
                previous.get("role") == "assistant"
                and previous.get("content", "").startswith("=== LOCATION SUMMARY ===")
            ):
                continue
        has_following_play = any(
            item.get("role") == "assistant"
            or (
                item.get("role") == "user"
                and not item.get("content", "").startswith("Dungeon Master Note:")
            )
            for item in conversation_history[transition_index + 1 :]
            if isinstance(item, dict)
        )
        if not has_following_play:
            continue

        previous_boundary = -1
        for index in range(transition_index - 1, -1, -1):
            item = conversation_history[index]
            content = item.get("content", "") if isinstance(item, dict) else ""
            if (
                item.get("role") == "user"
                and content.startswith("Location transition:")
            ) or (
                item.get("role") == "assistant"
                and content.startswith("=== LOCATION SUMMARY ===")
            ):
                previous_boundary = index
                break
        if previous_boundary < 0:
            for index in range(transition_index - 1, -1, -1):
                if conversation_history[index].get("role") == "system":
                    previous_boundary = index
                    break

        content = transition_message.get("content", "")
        match = re.match(
            r"Location transition: (.+?) \(([A-Z]+\d+)\) to (.+?) \(([A-Z]+\d+)\)$",
            content,
        )
        if match:
            leaving_name = match.group(1).strip()
        else:
            parts = content[len("Location transition:") :].split(" to ", 1)
            if len(parts) != 2 or not parts[0].strip():
                continue
            leaving_name = parts[0].strip()

        source_index = previous_boundary + 1
        source_entries = copy.deepcopy(
            conversation_history[source_index:transition_index]
        )
        summary_messages = [
            copy.deepcopy(item)
            for item in source_entries
            if item.get("role") != "system"
            and not (
                item.get("role") == "user"
                and item.get("content", "").startswith("Error Note:")
            )
        ]
        if not summary_messages:
            continue
        return {
            "transition_ordinal": ordinal,
            "transition_message": copy.deepcopy(transition_message),
            "source_index": source_index,
            "source_entries_before": source_entries,
            "summary_messages": summary_messages,
            "leaving_location_name": leaving_name,
        }
    return None


def _prepare_legacy_memory_targets(journal_entry, party_tracker_data, operation_id):
    """Compute legacy companion-memory mutations in an isolated temporary tree."""
    # [travel-clean #209] Legacy companion-memory reconciliation is deferred until the
    # voice/episodic line lands on main; CompanionMemoryManager.process_journal_operation
    # is absent here, so there are no legacy-memory targets to prepare.
    return []
    source_dir = Path("data/companion_memories")
    before = {
        str(path): _legacy_json_target(path)
        for path in source_dir.glob("*.json")
    }
    with tempfile.TemporaryDirectory(prefix="neq-legacy-memory-") as temporary:
        temporary_root = Path(temporary)
        temporary_data = temporary_root / "data" / "companion_memories"
        temporary_data.parent.mkdir(parents=True, exist_ok=True)
        if source_dir.exists():
            shutil.copytree(source_dir, temporary_data)
        else:
            temporary_data.mkdir(parents=True, exist_ok=True)

        original_cwd = Path.cwd()
        repository_root = Path(__file__).resolve().parent
        try:
            os.chdir(temporary_root)
            from core.memories.companion_memory import CompanionMemoryManager
            from utils.npc_name_canonicalizer import get_canonical_name

            party_npcs = []
            for npc in party_tracker_data.get("partyNPCs", []):
                name = npc.get("name", "") if isinstance(npc, dict) else str(npc)
                if name:
                    canonical = get_canonical_name(name)
                    if canonical:
                        party_npcs.append(canonical)
            manager = CompanionMemoryManager()
            manager.process_journal_operation(
                copy.deepcopy(journal_entry), party_npcs, operation_id
            )
            compression = subprocess.run(
                [
                    sys.executable,
                    str(
                        repository_root
                        / "scripts"
                        / "memory_management"
                        / "compress_memories.py"
                    ),
                ],
                cwd=temporary_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if compression.returncode != 0:
                raise RuntimeError(
                    "legacy memory compression failed with exit code %s"
                    % compression.returncode
                )
        finally:
            os.chdir(original_cwd)

        after_paths = list(temporary_data.glob("*.json"))
        targets = []
        relative_paths = set(before)
        relative_paths.update(
            str(Path("data/companion_memories") / path.name)
            for path in after_paths
        )
        for relative in sorted(relative_paths):
            temporary_path = temporary_root / relative
            after = _legacy_json_target(temporary_path)
            after["path"] = relative
            prior = before.get(relative, _legacy_absent_target(relative))
            if prior["exists"] != after["exists"] or prior["value"] != after["value"]:
                targets.append({"before": prior, "after": after})
        return targets


def _apply_legacy_json_target(target):
    before = target["before"]
    after = target["after"]
    path = Path(after["path"])
    current = _legacy_json_target(path)
    if current["exists"] == after["exists"] and current["value"] == after["value"]:
        return "already_applied"
    if current["exists"] != before["exists"] or current["value"] != before["value"]:
        return "blocked_conflict"
    if after["exists"]:
        safe_json_dump(after["value"], path)
    elif path.exists():
        path.unlink()
    return "applied"


def _apply_legacy_repair_checkpoint_unlocked(checkpoint, conversation_history):
    repair = checkpoint.get("legacy_repair") or {}
    targets = [repair.get("journal")] + list(repair.get("memory_targets") or [])
    for target in targets:
        if not isinstance(target, dict):
            continue
        outcome = _apply_legacy_json_target(target)
        if outcome == "blocked_conflict":
            checkpoint["phase"] = "blocked_conflict"
            action_handler._write_location_transition_checkpoint(checkpoint)
            return conversation_history
        target["status"] = "committed"
        action_handler._write_location_transition_checkpoint(checkpoint)

    summary_entry = repair["summary_entry_after"]
    source_index = repair["source_index"]
    if (
        source_index < len(conversation_history)
        and conversation_history[source_index] == summary_entry
    ):
        compacted = conversation_history
    else:
        compacted, _ = compact_with_accepted_departure_summary(
            conversation_history,
            source_index=source_index,
            source_entries_before=repair["source_entries_before"],
            leaving_location_name=repair["leaving_location_name"],
            summary=repair["summary"],
            summary_message_id=repair["summary_message_id"],
        )
        save_conversation_history(compacted)
    repair["conversation_status"] = "committed"
    checkpoint["phase"] = "completed"
    action_handler._write_location_transition_checkpoint(checkpoint)
    action_handler._remove_location_transition_checkpoint()
    return compacted


def _apply_legacy_repair_checkpoint(checkpoint, conversation_history):
    from core.managers.campaign_manager import _party_module_transition_lock

    with _party_module_transition_lock():
        return _apply_legacy_repair_checkpoint_unlocked(
            checkpoint, conversation_history
        )

def check_and_process_location_transitions(conversation_history, party_tracker_data, path_manager):
    """
    Check if there are any unprocessed location transitions in the conversation history
    and process them to create summaries and compress the history.
    """
    existing = safe_json_load(action_handler.PENDING_LOCATION_TRANSITION_FILE)
    if isinstance(existing, dict):
        if existing.get("version") == 2 and existing.get("kind") == "legacy_repair":
            return _apply_legacy_repair_checkpoint(existing, conversation_history)
        return conversation_history

    repair = _find_legacy_location_repair(conversation_history)
    if repair is None:
        return conversation_history

    summary = generate_location_summary(
        repair["leaving_location_name"], repair["summary_messages"]
    )
    if not summary:
        return conversation_history
    enhanced_summary = enhance_location_summary(summary) or summary

    world = party_tracker_data.get("worldConditions") or {}
    journal_target_before = _legacy_json_target("journal.json")
    journal_before = copy.deepcopy(journal_target_before["value"])
    if not isinstance(journal_before, dict):
        journal_before = {"entries": []}
    journal_entry = {
        "date": "%s %s %s"
        % (world.get("year", "N/A"), world.get("month", "N/A"), world.get("day", "N/A")),
        "time": world.get("time", "N/A"),
        "location": repair["leaving_location_name"],
        "summary": enhanced_summary,
    }
    journal_after = copy.deepcopy(journal_before)
    journal_after.setdefault("entries", []).append(journal_entry)
    operation_id = str(uuid4())
    memory_targets = _prepare_legacy_memory_targets(
        journal_entry, party_tracker_data, operation_id
    )
    summary_message_id = str(uuid4())
    summary_entry = {
        "role": "assistant",
        "content": "=== LOCATION SUMMARY ===\n\n%s:\n%s\n%s"
        % (
            repair["leaving_location_name"],
            "-" * len(repair["leaving_location_name"] + ":"),
            enhanced_summary,
        ),
        "message_id": summary_message_id,
    }
    checkpoint = {
        "version": 2,
        "kind": "legacy_repair",
        "operation_id": operation_id,
        "phase": "staged",
        "legacy_repair": {
            "transition_ordinal": repair["transition_ordinal"],
            "transition_message": repair["transition_message"],
            "source_index": repair["source_index"],
            "source_entries_before": repair["source_entries_before"],
            "leaving_location_name": repair["leaving_location_name"],
            "summary": enhanced_summary,
            "summary_message_id": summary_message_id,
            "summary_entry_after": summary_entry,
            "journal": {
                "before": journal_target_before,
                "after": {
                    "path": "journal.json",
                    "exists": True,
                    "value": journal_after,
                },
                "status": "pending",
            },
            "memory_targets": memory_targets,
            "conversation_status": "pending",
        },
    }
    from core.managers.campaign_manager import _party_module_transition_lock

    with _party_module_transition_lock():
        if Path(action_handler.PENDING_LOCATION_TRANSITION_FILE).exists():
            return conversation_history
        action_handler._write_location_transition_checkpoint(checkpoint)
    return _apply_legacy_repair_checkpoint(checkpoint, conversation_history)

def check_and_process_module_transitions(conversation_history, party_tracker_data):
    """
    Check if there are any unprocessed module transitions in the conversation history
    and process them to create summaries and compress the history.
    Mirrors the logic of check_and_process_location_transitions().
    """
    # Find the most recent transition that hasn't been processed yet
    last_transition_index = None
    last_transition_content = None
    
    for i in range(len(conversation_history) - 1, -1, -1):
        msg = conversation_history[i]
        if msg.get("role") == "user" and "Module transition:" in msg.get("content", ""):
            last_transition_index = i
            last_transition_content = msg.get("content", "")
            break
    
    if last_transition_index is None:
        # No module transitions found
        return conversation_history
    
    # Check if this transition has already been processed (has a summary right before it)
    if last_transition_index > 0:
        prev_msg = conversation_history[last_transition_index - 1]
        if prev_msg.get("role") == "user" and prev_msg.get("content", "").startswith("Module summary:"):
            # This transition has already been processed
            return conversation_history
    
    # Check if there's already conversation after this transition
    # If there are regular conversation messages after the transition, we should process it
    has_conversation_after = False
    for i in range(last_transition_index + 1, len(conversation_history)):
        msg = conversation_history[i]
        # Skip system messages and DM notes
        if msg.get("role") == "assistant" or (msg.get("role") == "user" and "Dungeon Master Note:" not in msg.get("content", "")):
            has_conversation_after = True
            break
    
    if not has_conversation_after:
        # No conversation after the transition yet, wait for next round
        return conversation_history
    
    # Extract the leaving module from the transition message
    # Format: "Module transition: [from_module] to [to_module]"
    try:
        import re
        pattern = r'Module transition: (.+?) to (.+?)$'
        match = re.match(pattern, last_transition_content)
        
        if match:
            leaving_module_name = match.group(1)
            arriving_module_name = match.group(2)
            debug(f"STATE_CHANGE: Extracted module transition - From: {leaving_module_name}, To: {arriving_module_name}", category="module_transitions")
        else:
            warning("VALIDATION: Could not parse module transition message format", category="module_transitions")
            return conversation_history
    except Exception as e:
        error(f"FAILURE: Error parsing module transition message", exception=e, category="module_transitions")
        return conversation_history
    
    debug(f"STATE_CHANGE: Processing module transition from {leaving_module_name}", category="module_transitions")
    
    try:
        # Generate module summary using similar logic to location summaries
        module_summary = generate_module_summary(
            conversation_history,
            party_tracker_data,
            leaving_module_name,
            last_transition_index
        )
        
        if module_summary:
            # Compress conversation history for module transition
            compressed_history = compress_conversation_history_on_module_transition(
                conversation_history,
                leaving_module_name,
                module_summary,
                last_transition_index
            )
            
            debug("SUCCESS: Module summary and compression completed", category="module_transitions")
            return compressed_history
        else:
            debug("STATE_CHANGE: No module summary generated", category="module_transitions")
            return conversation_history
            
    except Exception as e:
        error(f"FAILURE: Failed to process module transition", exception=e, category="module_transitions")
        import traceback
        traceback.print_exc()
        return conversation_history

def generate_module_summary(conversation_history, party_tracker_data, module_name, transition_index):
    """Generate a summary for a module transition"""
    
    # Condition 1: Look for previous module transition OR module summary first
    boundary_index = None
    
    for i in range(transition_index - 1, -1, -1):
        msg = conversation_history[i]
        content = msg.get("content", "")
        
        # Look for either previous module transition or existing module summary
        if (msg.get("role") == "user" and 
            ("Module transition:" in content or "Module summary:" in content)):
            boundary_index = i + 1  # Start after previous transition/summary
            debug(f"VALIDATION: CONDITION 1 - Found previous module marker at index {i}, boundary at {boundary_index}", category="conversation_management")
            break
    
    # Condition 2: If no previous module transition/summary, find last system message
    if boundary_index is None:
        for i in range(transition_index - 1, -1, -1):
            msg = conversation_history[i]
            if msg.get("role") == "system":
                boundary_index = i + 1  # Start after last system message
                debug(f"VALIDATION: CONDITION 2 - Found last system message at index {i}, boundary at {boundary_index}", category="conversation_management")
                break
        
        # Fallback if no system message found (shouldn't happen)
        if boundary_index is None:
            boundary_index = 0
            debug(f"VALIDATION: FALLBACK - No system message found, using boundary at {boundary_index}", category="conversation_management")
    
    # Extract ONLY the conversation from boundary to transition (actual gameplay)
    module_conversation = conversation_history[boundary_index:transition_index]
    debug(f"STATE_CHANGE: Extracting {len(module_conversation)} messages from index {boundary_index} to {transition_index} for summary", category="conversation_management")
    
    # Generate summary from ACTUAL conversation history, not plot files
    try:
        # Filter out system messages and technical messages from the conversation
        meaningful_messages = []
        for msg in module_conversation:
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            # Skip technical messages but keep actual gameplay
            if (role in ["user", "assistant"] and 
                not content.startswith(("Location transition:", "Module transition:", 
                                      "Module summary:", "Dungeon Master Note:", "Error Note:"))):
                meaningful_messages.append(msg)
        
        debug(f"STATE_CHANGE: Found {len(meaningful_messages)} meaningful conversation messages to summarize", category="summary_building")
        
        # If we have substantial conversation, generate AI summary from actual gameplay
        if len(meaningful_messages) >= 3:
            try:
                import config

                # Prepare conversation for summarization
                conversation_text = ""
                for msg in meaningful_messages:  # All meaningful messages from this module
                    role = "Player" if msg.get("role") == "user" else "DM"
                    content = msg.get("content", "")
                    conversation_text += f"{role}: {content}\n\n"
                
                summary_prompt = f"""You are creating an adventure chronicle for a 5th edition session. Summarize this actual gameplay conversation from the {module_name} module into a compelling narrative story.

IMPORTANT: Only include events that actually happened in the conversation. Do not add events from other sources.

Focus on:
- Actual player actions and decisions made
- NPCs encountered and interactions that occurred  
- Locations visited and described
- Plot developments that happened
- Character relationships and moments

Write in an elevated fantasy prose style, like a chronicle or epic tale. Make it engaging but accurate to what actually occurred.

ACTUAL GAMEPLAY CONVERSATION:
{conversation_text}

Write a compelling chronicle of these actual events:"""

                from model_config import MODEL_PROVIDER
                if MODEL_PROVIDER == "openai":
                    summ_config = config.DM_SUMM_GPT54MINI_NONE
                elif MODEL_PROVIDER == "gemini":
                    summ_config = config.DM_SUMM_GEMINI_FLASH_LOW
                elif MODEL_PROVIDER == "lmstudio":
                    summ_config = config.DM_SUMM_LMSTUDIO
                else:  # legacy
                    summ_config = config.DM_SUMM_LEGACY

                response = capture_and_fanout("T066", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=[
                        {"role": "system", "content": "You are an expert at creating beautiful adventure chronicles from 5th edition gameplay, focusing only on events that actually occurred. Do NOT use markdown formatting (no **, no ###, no bullet points). Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    model=summ_config["model"],
                    temperature=0.7,
                    response_format=None,
                    **{k: v for k, v in summ_config.items() if k != "model"})

                # Log API call to master log
                try:
                    from utils.api_logger import log_api_call
                    log_api_call("module_summary", [
                        {"role": "system", "content": "You are an expert at creating beautiful adventure chronicles from 5th edition gameplay, focusing only on events that actually occurred. Do NOT use markdown formatting (no **, no ###, no bullet points). Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode."},
                        {"role": "user", "content": summary_prompt}
                    ], response, metadata={"temperature": 0.7, "module": module_name})
                except Exception as e:
                    print(f"[API_LOG] Warning: Failed to log summary call: {e}")

                # Track token usage with context for telemetry
                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(response, context={'endpoint': 'module_summary', 'purpose': 'generate_module_summary', 'module': module_name})
                    except:
                        pass
                
                ai_summary = response.choices[0].message.content.strip()
                if not ai_summary:
                    raise ValueError("T066 returned an empty module chronicle")
                ai_summary = sanitize_text(ai_summary).strip()
                if not ai_summary:
                    raise ValueError("T066 chronicle was empty after sanitization")
                formatted_summary = f"=== MODULE SUMMARY ===\n\n{module_name}:\n------------------------------\n{ai_summary}"
                debug(f"SUCCESS: Generated AI summary from actual conversation for {module_name}", category="summary_building")
                return formatted_summary
                
            except Exception as e:
                warning(f"FAILURE: Error generating AI summary from conversation, using fallback", category="summary_building")
        
        debug(f"STATE_CHANGE: Not enough meaningful conversation for AI summary ({len(meaningful_messages)} messages), using fallback", category="summary_building")
        
    except Exception as e:
        error(f"FAILURE: Error processing conversation for summary, using fallback", exception=e, category="summary_building")
    
    # Fallback to simple summary if no AI summary available
    meaningful_messages = [
        msg for msg in module_conversation 
        if msg.get("role") in ["user", "assistant"] and 
        not msg.get("content", "").startswith(("Location transition:", "Module transition:", "Module summary:"))
    ]
    
    if len(meaningful_messages) < 2:
        return f"Brief activities in {module_name}."
    elif len(meaningful_messages) <= 5:
        return f"Short adventure in {module_name} with several interactions."
    else:
        return f"Extended adventure in {module_name} with multiple significant events and discoveries."

def compress_conversation_history_on_module_transition(conversation_history, module_name, summary_text, transition_index):
    """Compress conversation history by replacing conversation segment with summary, preserving previous summaries"""
    
    # Find the boundary for compression - same logic as generate_module_summary
    boundary_index = None
    
    for i in range(transition_index - 1, -1, -1):
        msg = conversation_history[i]
        content = msg.get("content", "")
        
        # Look for either previous module transition or existing module summary
        if (msg.get("role") == "user" and 
            ("Module transition:" in content or "Module summary:" in content)):
            boundary_index = i + 1  # Start after previous transition/summary
            debug(f"VALIDATION: COMPRESSION - Found previous module marker at index {i}, boundary at {boundary_index}", category="conversation_management")
            break
    
    # If no previous module marker, find last system message
    if boundary_index is None:
        for i, msg in enumerate(conversation_history):
            if msg.get("role") == "system":
                boundary_index = i + 1  # Start after system message
                debug(f"VALIDATION: COMPRESSION - Found system message at index {i}, boundary at {boundary_index}", category="conversation_management")
                break
        
        if boundary_index is None:
            boundary_index = 0
            debug(f"VALIDATION: COMPRESSION - No system message found, using boundary at {boundary_index}", category="conversation_management")
    
    # Create summary message
    summary_message = {
        "role": "user",
        "content": f"Module summary: {summary_text}"
    }
    
    # Build compressed history: everything before boundary + summary + transition + everything after
    compressed_history = []
    
    # Keep everything before the boundary (includes system message + previous summaries)
    compressed_history.extend(conversation_history[:boundary_index])
    
    # Add the new summary for this module  
    compressed_history.append(summary_message)
    
    # Add transition marker and everything after
    compressed_history.extend(conversation_history[transition_index:])
    
    debug(f"SUCCESS: Compressed module conversation from {len(conversation_history)} to {len(compressed_history)} messages", category="conversation_management")
    debug(f"STATE_CHANGE: Preserved {boundary_index} messages before boundary, added 1 summary, kept {len(conversation_history) - transition_index} messages after transition", category="conversation_management")
    debug("STATE_CHANGE: Result structure: main system message + module summary + transition + new conversation", category="conversation_management")
    return compressed_history

def extract_json_from_codeblock(text):
    match = re.search(r'```json\n(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def retry_staged_module_completions(
    pending_archive_info=None,
    conversation_history=None,
):
    """Drain durable transition intents; failures remain queued for retry."""
    from core.managers.campaign_manager import CampaignManager

    manager = CampaignManager()
    targeted_result = None
    if pending_archive_info:
        targeted_result = manager.complete_staged_module_completion(
            pending_archive_info["from_module"],
            pending_archive_info["completion_id"],
            conversation_history=conversation_history,
        )
    outcome = manager.drain_module_completion_intents()
    return targeted_result, outcome


def require_staged_module_completions_drained():
    """Fail closed before building context or requesting new narration."""
    _targeted, outcome = retry_staged_module_completions()
    if outcome["failed"] or outcome["blocked"]:
        raise RuntimeError(
            "Module completion recovery remains active: "
            f"failed={len(outcome['failed'])}, "
            f"blocked={len(outcome['blocked'])}"
        )
    return outcome


def rebuild_conversation_for_current_party(
    conversation_history,
    *,
    return_party=False,
):
    """Force system/campaign context to match the authoritative party state."""
    from core.managers.campaign_manager import _party_module_transition_lock

    # Keep module identity stable across the initial path selection, the
    # updater's authoritative disk reload, and the strict raw persistence.
    with _party_module_transition_lock():
        history, party = _rebuild_conversation_for_current_party_locked(
            conversation_history
        )
    return (history, party) if return_party else history


def _rebuild_conversation_for_current_party_locked(conversation_history):
    party_tracker_data = load_json_file("party_tracker.json")
    if not isinstance(party_tracker_data, dict):
        raise RuntimeError(
            "Cannot rebuild AI context after module completion without party state"
        )
    module_name = party_tracker_data.get("module", "").replace(" ", "_")
    path_manager = ModulePathManager(module_name)
    plot_data = load_json_file(path_manager.get_plot_path())
    module_data = load_json_file(path_manager.get_module_file_path())
    refreshed = update_conversation_history(
        conversation_history,
        party_tracker_data,
        plot_data,
        module_data,
    )
    conversation_history[:] = refreshed
    save_conversation_history(
        conversation_history,
        strict=True,
        allow_compression=False,
    )
    return conversation_history, party_tracker_data


def _party_transition_projection(party_tracker_data):
    """Small identity used to reject narration for a superseded location."""
    if not isinstance(party_tracker_data, dict):
        return None
    world = party_tracker_data.get("worldConditions")
    if not isinstance(world, dict):
        world = {}
    return (
        party_tracker_data.get("module"),
        world.get("currentAreaId"),
        world.get("currentLocationId"),
    )








def _emit_committed_module_message(content, message_id):
    from web.shared_state import emit_player_output

    delivered = emit_player_output(
        {
            "type": "narration",
            "content": content,
            "message_id": message_id,
        }
    )
    if delivered is not True:
        print(colored("Dungeon Master:", "blue"), colored(content, "blue"))
    return delivered is True


def display_dm_narration(content, channel="main", color="blue", message_id=None):
    """Deliver DM narration through the frontend sink, else the console.

    A frontend (web or headless) that installed a player-output sink gets
    the narration structured and the console print is skipped; with no sink
    (plain terminal) the print is identical to the historical output.

    Empty content skips the sink: the historical scrapers suppressed empty
    narration blocks, and routing "" through the sink would render empty
    DM cards in the web UI.
    """
    from web.shared_state import emit_player_output

    delivered = False
    if content and content.strip():
        delivered = emit_player_output(
            {
                "type": "narration",
                "channel": channel,
                "content": content,
                "message_id": message_id,
            }
        )
    if delivered is not True:
        print(colored("Dungeon Master:", color), colored(content, color))










def prepare_conversation_for_ai_request(conversation_history):
    """Close queued transitions and rebuild context before any DM request.

    P2b: the per-turn publication-receipt recovery is gone -- module creation
    publishes atomically and narrates in the same turn, so there is nothing to
    recover here.
    """
    outcome = require_staged_module_completions_drained()
    if not (outcome["completed"] or outcome["cancelled"]):
        return outcome
    rebuild_conversation_for_current_party(conversation_history)
    return outcome


def _strictly_persist_conversation_history(conversation_history):
    """Persist the authoritative list and track literal failure as dirty."""
    global _conversation_history_dirty, _dirty_conversation_history
    try:
        saved = save_conversation_history(
            conversation_history,
            strict=True,
            allow_compression=False,
        )
    except Exception as save_error:
        error(
            "FAILURE: Safe action history could not be persisted",
            exception=save_error,
            category="conversation_management",
        )
        saved = False
    if saved is True:
        if (
            _dirty_conversation_history is None
            or _dirty_conversation_history is conversation_history
            or _dirty_conversation_history == conversation_history
        ):
            _conversation_history_dirty = False
            _dirty_conversation_history = None
    else:
        _conversation_history_dirty = True
        if _dirty_conversation_history is None:
            _dirty_conversation_history = conversation_history
    return saved is True


def _reload_conversation_history_if_safe(
    conversation_history,
    path=json_file,
):
    """Retry a dirty save before allowing disk to replace newer memory."""
    authoritative_history = (
        _dirty_conversation_history
        if _conversation_history_dirty
        and isinstance(_dirty_conversation_history, list)
        else conversation_history
    )
    if _conversation_history_dirty:
        if not _strictly_persist_conversation_history(authoritative_history):
            return authoritative_history
    loaded_history = load_json_file(path)
    if isinstance(loaded_history, list):
        return loaded_history
    return authoritative_history


def _ordinary_action_failure_message_id(response, action, conversation_history):
    """Derive one retry-stable identity from the accepted turn prefix."""
    from web.shared_state import SAFE_ACTION_FAILURE_MESSAGE

    prefix = list(conversation_history)
    if (
        prefix
        and isinstance(prefix[-1], dict)
        and prefix[-1].get("role") == "system"
        and prefix[-1].get("content") == SAFE_ACTION_FAILURE_MESSAGE
        and str(prefix[-1].get("message_id", "")).startswith(
            "action-failure:"
        )
    ):
        prefix.pop()
    if (
        prefix
        and isinstance(prefix[-1], dict)
        and prefix[-1].get("role") == "assistant"
        and prefix[-1].get("content") == response
    ):
        prefix.pop()
    identity = {
        "schema": "ordinary-action-failure-v1",
        "history_prefix": prefix,
        "accepted_response": response,
        "action": action,
    }
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "action-failure:" + hashlib.sha256(encoded).hexdigest()


def _action_failure_player_message(result):
    """Pick the CURATED player message for a terminal action error. A module
    lifecycle recovery-required failure gets a specific, actionable message
    (E2E 2e/W3); everything else gets the generic safe text. Selection is by the
    whitelisted `recovery_required` boolean only -- never raw internal text."""
    from web.shared_state import (
        SAFE_ACTION_FAILURE_MESSAGE,
        MODULE_RECOVERY_FAILURE_MESSAGE,
    )
    source_data = result.get("response_data") if isinstance(result, dict) else {}
    if isinstance(source_data, dict) and source_data.get("recovery_required") is True:
        return MODULE_RECOVERY_FAILURE_MESSAGE
    return SAFE_ACTION_FAILURE_MESSAGE


def _safe_action_failure_result(result, message_id):
    """Whitelist action-error metadata and attach the canonical player text."""
    player_message = _action_failure_player_message(result)

    source_data = result.get("response_data") if isinstance(result, dict) else {}
    if not isinstance(source_data, dict):
        source_data = {}
    response_data = {
        "player_message": player_message,
        "message_id": message_id,
    }
    for field in ("retryable", "state_changed", "recovery_required"):
        value = source_data.get(field)
        if field == "state_changed":
            if value is None or type(value) is bool:
                response_data[field] = value
        elif type(value) is bool:
            response_data[field] = value
    return {
        "status": "error",
        "success": False,
        "needs_update": (
            isinstance(result, dict) and result.get("needs_update") is True
        ),
        "needs_dm_response": False,
        "player_message": player_message,
        "message_id": message_id,
        "response_data": response_data,
    }


def _handle_ordinary_action_failure(
    result,
    response,
    action,
    conversation_history,
):
    """Persist and deliver one sanitized terminal error for an accepted turn."""
    from web.shared_state import emit_player_output

    # Curated player text: specific+actionable for a lifecycle recovery-required
    # refusal (E2E 2e/W3), generic otherwise. Never raw internal error text.
    player_message = _action_failure_player_message(result)

    message_id = _ordinary_action_failure_message_id(
        response, action, conversation_history
    )
    already_recorded = any(
        isinstance(message, dict) and message.get("message_id") == message_id
        for message in conversation_history
    )
    if not already_recorded:
        assistant_message = {"role": "assistant", "content": response}
        if not (
            conversation_history
            and conversation_history[-1] == assistant_message
        ):
            conversation_history.append(assistant_message)
        conversation_history.append(
            {
                "role": "system",
                "content": player_message,
                "message_id": message_id,
            }
        )

    _strictly_persist_conversation_history(conversation_history)
    emit_player_output(
        {
            "type": "error",
            "content": player_message,
            "message_id": message_id,
        }
    )
    try:
        status_ready()
    except Exception:
        pass
    return _safe_action_failure_result(result, message_id)








def _complete_committed_module_followup(
    result,
    response,
    conversation_history,
):
    """Serialize publication follow-up persistence against restore/reset."""
    from core.managers.campaign_manager import _party_module_transition_lock

    with _party_module_transition_lock():
        return _complete_committed_module_followup_locked(
            result,
            response,
            conversation_history,
        )


def _complete_committed_module_followup_locked(
    result,
    response,
    conversation_history,
):
    """Generate + deliver the creation narration for a just-published module.

    P2b: the module is ALREADY live (published atomically by publish_module_atomic
    before this returns). This runs the dedicated second DM call that narrates the
    creation. If anything here fails, the module stays live and the game keeps
    playing -- the player may simply not see the creation narration this turn
    (cosmetic, fail-forward; never hangs or corrupts).
    """
    response_data = result.get("response_data", {})
    module_name = response_data.get("module_name")
    try:
        accepted_message = {"role": "assistant", "content": response}
        if not (
            conversation_history
            and conversation_history[-1] == accepted_message
        ):
            conversation_history.append(accepted_message)
        dm_note = response_data.get("dm_note")
        if isinstance(dm_note, str) and dm_note.strip():
            conversation_history.append(
                {"role": "user", "content": dm_note.strip()}
            )
        if _strictly_persist_conversation_history(conversation_history) is not True:
            raise OSError("Accepted publication history did not persist")

        followup_history = list(conversation_history)
        followup_history, party_data = rebuild_conversation_for_current_party(
            followup_history,
            return_party=True,
        )
        get_location_data_from_party_tracker(party_data)
        ai_response = get_ai_response(followup_history)
        parsed = json.loads(extract_json_from_codeblock(ai_response))
        narration = parsed.get("narration") if isinstance(parsed, dict) else None
        actions = parsed.get("actions") if isinstance(parsed, dict) else None
        if (
            not isinstance(narration, str)
            or not narration.strip()
            or not isinstance(actions, list)
            or actions != []
        ):
            raise ValueError("Module follow-up was not useful narration-only JSON")
        narration = sanitize_text(narration).strip()
        if not narration:
            raise ValueError("Module follow-up narration became empty")

        followup_id = f"module-followup-{module_name}"
        followup_message = {
            "role": "assistant",
            "content": ai_response,
            "message_id": followup_id,
        }
        if not any(
            isinstance(message, dict)
            and message.get("message_id") == followup_id
            for message in followup_history
        ):
            followup_history.append(followup_message)
        saved = save_conversation_history(
            followup_history,
            strict=True,
            allow_compression=False,
        )
        if saved is not True:
            raise OSError("Module follow-up history did not report success")

        conversation_history[:] = followup_history
        _emit_committed_module_message(narration, followup_id)

        completed = dict(result)
        completed["status"] = "published"
        completed["needs_dm_response"] = False
        completed["state_changed"] = True
        completed["retryable"] = False
        completed_data = dict(response_data)
        completed_data["followup_message_id"] = followup_id
        completed["response_data"] = completed_data
        return completed
    except Exception as followup_error:
        # The module is already live; a narration failure must NOT hang or break
        # the game. Return a terminal published result -- the player keeps
        # playing; the creation narration is simply not shown this turn.
        error(
            "Published module creation narration could not be delivered; the "
            "module is live and the game continues",
            exception=followup_error,
            category="module_management",
        )
        fallback = dict(result)
        fallback["status"] = "published"
        fallback["needs_dm_response"] = False
        return fallback


def _agentic_post_combat_narration_pass(party_tracker_data):
    """Return whether this response follows an agentic authoritative commit."""
    if not getattr(process_ai_response, "_just_finished_combat", False):
        return False
    # One combat-return path recurses before the caller's in-memory tracker is
    # refreshed.  The committed tracker on disk is authoritative at this
    # boundary; otherwise a valid post-combat echo can bypass this gate.
    committed_tracker = safe_json_load("party_tracker.json")
    if isinstance(committed_tracker, dict):
        party_tracker_data = committed_tracker
    world = (party_tracker_data or {}).get("worldConditions") or {}
    encounter_id = world.get("lastCompletedEncounter")
    if not encounter_id:
        return False
    encounter = safe_json_load(
        os.path.join("modules", "encounters", "encounter_%s.json" % encounter_id)
    )
    return (
        isinstance(encounter, dict)
        and ((encounter.get("combatState") or {}).get("pipelineMode") == "agentic")
        and ((encounter.get("combatState") or {}).get("phase") == "complete")
    )


def _agentic_post_combat_engine_echo(action):
    """Block character mutations in the historical post-combat narration pass.

    Agentic combat has already committed HP, effects, resources, and rewards.
    This automatic provider response is based only on that historical summary,
    never on a new player action, so every character update it emits is an
    unsafe replay regardless of how the model phrases or combines the changes.
    """
    return (
        isinstance(action, dict)
        and action.get("action") == "updateCharacterInfo"
    )


_AGENTIC_POST_COMBAT_DROP_NOTICE = (
    "Character updates in this post-combat pass were ignored because combat "
    "already committed all changes. Re-issue genuinely new changes with the "
    "player's next action."
)


def _record_agentic_post_combat_updates_dropped(count):
    """Record one bounded post-combat guard outcome without gameplay data."""
    from core.ai.combat_diagnostics import record_combat_diagnostic

    return record_combat_diagnostic(
        record_type="window_outcome",
        callsite="POST_COMBAT",
        outcome="post_combat_update_dropped",
        dropped_actions=count,
    )


def process_ai_response(
    response,
    party_tracker_data,
    location_data,
    conversation_history,
    *,
    approved_transition_plan=None,
):
    global needs_conversation_history_update
    from contextlib import ExitStack

    json_content = extract_json_from_codeblock(response)
    parsed_response = json.loads(json_content)
    actions = parsed_response.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    first_action = actions[0] if actions and isinstance(actions[0], dict) else {}
    first_parameters = first_action.get("parameters", {})
    if not isinstance(first_parameters, dict):
        first_parameters = {}
    current_module = str((party_tracker_data or {}).get("module", ""))
    requested_module = str(first_parameters.get("module", ""))
    is_travel_workflow = any(
        isinstance(action, dict) and action.get("action") == "transitionLocation"
        for action in actions
    ) or (
        first_action.get("action") == "updatePartyTracker"
        and bool(requested_module)
        and requested_module != current_module
    )

    response_fences = ExitStack()

    try:
        from core.managers.campaign_manager import (
            _party_module_transition_lock,
        )

        # Preserve the legacy response-wide fence for ordinary responses.
        # Travel has its own checkpoint-v2 transaction and must release every
        # mutation lock before T091/T016/T015/T013/T063/T064 provider work.
        if not is_travel_workflow:
            response_fences.enter_context(_party_module_transition_lock())
        caller_projection = _party_transition_projection(party_tracker_data)
        if (
            caller_projection is not None
            and caller_projection[0]
            and caller_projection[2]
        ):
            authoritative_projection = _party_transition_projection(
                load_json_file("party_tracker.json")
            )
            if authoritative_projection != caller_projection:
                return {
                    "status": "stale_response_context",
                    "retryable": True,
                }

        # Finish transitions left ready by an earlier return/process crash.
        # Intents carry their own bounded history snapshot, so this cannot mix
        # later-module conversation into the archived visit.
        try:
            _targeted, drain_outcome = retry_staged_module_completions()
            if drain_outcome["failed"] or drain_outcome["blocked"]:
                error(
                    "FAILURE: Refusing to process a new response while an "
                    "older module completion remains unresolved",
                    category="module_management",
                )
                return {
                    "status": "module_completion_pending",
                    "retryable": True,
                    "completion_outcome": drain_outcome,
                }
            if drain_outcome["completed"] or drain_outcome["cancelled"]:
                # The provider response was assembled before this recovery
                # changed the authoritative timeline. Never execute its stale
                # actions or display its stale narration.
                return {
                    "status": "stale_response_context",
                    "retryable": True,
                    "completion_outcome": drain_outcome,
                }
        except Exception as drain_exc:
            error(
                "FAILURE: Could not retry staged module completions",
                exception=drain_exc,
                category="module_management",
            )
            return {
                "status": "module_completion_pending",
                "retryable": True,
                "error": str(drain_exc),
            }

        # Also drain the smaller within-module checkpoint before accepting a
        # new turn. This covers a surviving server after an action exception;
        # process restart uses the same helper during startup.
        transition_recovery = (
            action_handler.recover_pending_location_transition(
                load_json_file("party_tracker.json") or party_tracker_data,
                load_json_file(json_file) or conversation_history,
            )
        )
        if transition_recovery.get("status") == "blocked":
            return {
                "status": "transition_context_pending",
                "retryable": True,
                "error": transition_recovery.get("reason"),
            }
        if transition_recovery.get("status") == "resume_required":
            return {
                "status": "transition_context_pending",
                "retryable": True,
                "operation_id": transition_recovery.get("operation_id"),
                "phase": transition_recovery.get("phase"),
            }
        if transition_recovery.get("status") == "recovered":
            if transition_recovery.get("deferred_actions_not_replayed"):
                warning(
                    "Recovered transition narration without replaying "
                    f"{transition_recovery.get('deferred_action_count', 0)} "
                    "non-idempotent deferred action(s); authoritative state "
                    "must be reconciled by the next turn",
                    category="location_transitions",
                )
            return {
                "status": "transition_state_changed",
                "retryable": True,
            }

        # Movement is the transaction boundary for its response. Reject the
        # entire candidate before level-up or any other action can mutate
        # state when transitionLocation is not uniquely first.
        transition_indexes = [
            index
            for index, action in enumerate(actions)
            if isinstance(action, dict)
            and action.get("action") == "transitionLocation"
        ]
        if transition_indexes and (
            len(transition_indexes) != 1 or transition_indexes[0] != 0
        ):
            return {
                "status": "invalid_transition_actions",
                "retryable": True,
                "error": (
                    "A response containing transitionLocation must contain "
                    "exactly one transition and it must be the first action"
                ),
            }

        first_action = actions[0] if actions and isinstance(actions[0], dict) else {}
        first_params = first_action.get("parameters")
        first_params = first_params if isinstance(first_params, dict) else {}
        current_module = str((party_tracker_data or {}).get("module") or "")
        target_module = str(first_params.get("module") or "")
        if (
            first_action.get("action") == "updatePartyTracker"
            and target_module
            and target_module != current_module
        ):
            if len(actions) != 2 or not isinstance(actions[1], dict) or actions[1].get(
                "action"
            ) != "updateTime":
                return {
                    "status": "invalid_transition_actions",
                    "retryable": True,
                    "error": (
                        "Cross-module travel must be updatePartyTracker followed "
                        "by exactly one updateTime action"
                    ),
                }
            accepted_history = list(conversation_history)
            accepted_history.append({"role": "assistant", "content": response})
            checkpoint = action_handler.stage_cross_module_root_checkpoint(
                first_action,
                actions[1],
                accepted_history,
                load_json_file("party_tracker.json") or party_tracker_data,
                parsed_response.get("narration", ""),
            )
            resumed = _resume_v2_location_transition(
                checkpoint["operation_id"], publish=True
            )
            if resumed.get("status") != "completed":
                return {
                    "status": "transition_context_pending",
                    "retryable": True,
                    "error": resumed.get("reason", "module handoff remains pending"),
                }
            return {
                "role": "assistant",
                "content": json.dumps(
                    {"narration": resumed.get("narration", ""), "actions": []}
                ),
            }
        
        # --- START OF FIX: Detect levelUp action before printing narration ---
        is_levelup_action = any(action.get("action") == "levelUp" for action in actions)

        if is_levelup_action:
            debug("STATE_CHANGE: levelUp action detected. Suppressing initial narration and starting session.", category="level_up")
            # Process ONLY the levelUp action from the list to start the session.
            # This assumes the first levelUp action is the one to process.
            for action in actions:
                if action.get("action") == "levelUp":
                    # Directly call the action handler for just this action
                    try:
                        result = action_handler.process_action(
                            action,
                            party_tracker_data,
                            location_data,
                            conversation_history,
                        )
                    except Exception as action_error:
                        error(
                            "FAILURE: Level-up action handler raised unexpectedly",
                            exception=action_error,
                            category="level_up",
                        )
                        result = {"status": "error", "success": False}
                    if (
                        isinstance(result, dict)
                        and result.get("status") == "error"
                    ):
                        return _handle_ordinary_action_failure(
                            result,
                            response,
                            action,
                            conversation_history,
                        )
                    return result
            # Fallback in case the loop doesn't find it, though it should.
            return None
        # --- END OF FIX ---

        # --- NEW TRANSITION LOGIC ---
        is_transition = False
        transition_action_index = None
        departure_narration = ""
        # Check if the response contains a transition action
        for action_index, action in enumerate(parsed_response.get("actions", [])):
            if action.get("action") == "transitionLocation":
                if transition_action_index is not None:
                    return {
                        "status": "invalid_transition_actions",
                        "retryable": True,
                        "error": "Only one transitionLocation may be processed per response",
                    }
                is_transition = True
                transition_action_index = action_index
                departure_narration = parsed_response.get("narration", "")

        if is_transition:
            if transition_action_index != 0:
                return {
                    "status": "invalid_transition_actions",
                    "retryable": True,
                    "error": (
                        "transitionLocation must be the first action in a "
                        "response; state changes may only follow a committed "
                        "movement"
                    ),
                }
        
        # If it's a transition, handle it with the special two-step process
        if is_transition:
            debug("STATE_CHANGE: Transition action detected. Holding departure narration.", category="location_transitions")
            transition_placeholder = None
            committed_transition_prompt = None
            location_transition_id = None
            pending_archive_info = None

            # Step 1: Process actions to update state (summary, party_tracker, etc.)
            actions_processed = False
            needs_transition_dm_response = False
            pre_transition_message = None
            transition_actions = actions[: transition_action_index + 1]
            deferred_actions = actions[transition_action_index + 1 :]
            for action in transition_actions:
                if action.get("action") == "transitionLocation":
                    # Make the accepted command available to the transition
                    # publisher only when it is about to run. Earlier control
                    # signals must not persist an unseen future transition.
                    pre_transition_message = {
                        "role": "assistant",
                        "content": response,
                    }
                    conversation_history.append(pre_transition_message)
                result = action_handler.process_action(
                    action,
                    party_tracker_data,
                    location_data,
                    conversation_history,
                    approved_transition_plan=(
                        approved_transition_plan
                        if action.get("action") == "transitionLocation"
                        else None
                    ),
                    transition_deferred_actions=(
                        deferred_actions
                        if action.get("action") == "transitionLocation"
                        else None
                    ),
                )
                actions_processed = True
                if isinstance(result, dict):
                    response_data = result.get("response_data", {})
                    if not isinstance(response_data, dict):
                        response_data = {}
                    else:
                        pending = response_data.get("pending_archive")
                        if isinstance(pending, dict):
                            pending_archive_info = pending
                        placeholder = response_data.get("transition_narration")
                        if isinstance(placeholder, str) and placeholder:
                            transition_placeholder = placeholder
                        prompt_value = response_data.get("transition_prompt")
                        if isinstance(prompt_value, str) and prompt_value:
                            committed_transition_prompt = prompt_value
                        checkpoint_id = response_data.get(
                            "location_transition_id"
                        )
                        if isinstance(checkpoint_id, str) and checkpoint_id:
                            location_transition_id = checkpoint_id
                    if result.get("needs_update"):
                        needs_conversation_history_update = True
                    result_status = result.get("status")
                    if result_status == "error":
                        if (
                            action.get("action") == "transitionLocation"
                            and response_data.get("retryable") is True
                            and response_data.get("error_code")
                            == "transition_plan_stale"
                        ):
                            if pre_transition_message is not None:
                                for index in range(
                                    len(conversation_history) - 1, -1, -1
                                ):
                                    if conversation_history[index] is pre_transition_message:
                                        del conversation_history[index]
                                        break
                            return {
                                "status": "transition_plan_stale",
                                "retryable": True,
                                "error": response_data.get("error_message"),
                            }
                        # A pending_archive on an error is recovery metadata,
                        # not proof that the party/location transition
                        # committed. Do not render arrival narration, cancel a
                        # clean prepare as if successful, or run later actions.
                        recovery_required = response_data.get(
                            "transition_recovery_required"
                        )
                        if recovery_required is None:
                            # Older/non-transition result producers remain
                            # conservative unless they explicitly prove the
                            # durable publication state is absent.
                            recovery_required = pending_archive_info is not None
                        if pending_archive_info is not None and recovery_required:
                            # Movement may already be published. Preserve the
                            # correlated raw/marker/T013 suffix for recovery,
                            # but block later actions and surface the pending
                            # state explicitly to the outer loop.
                            return {
                                "status": "module_completion_pending",
                                "retryable": True,
                                "response_data": response_data,
                            }
                        if pre_transition_message is not None:
                            for index in range(
                                len(conversation_history) - 1,
                                -1,
                                -1,
                            ):
                                if (
                                    conversation_history[index]
                                    is pre_transition_message
                                ):
                                    del conversation_history[index]
                                    break
                        return _handle_ordinary_action_failure(
                            result,
                            response,
                            action,
                            conversation_history,
                        )
                    if result_status == "exit":
                        return "exit"
                    if result_status == "restart":
                        return "restart"
                    if result_status == "enter_levelup_mode":
                        return result
                    if result_status in {
                        "needs_response",
                        "needs_post_combat_narration",
                    }:
                        followup_history = (
                            load_json_file(json_file)
                            or conversation_history
                        )
                        (
                            followup_history,
                            party_tracker_data,
                        ) = rebuild_conversation_for_current_party(
                            followup_history,
                            return_party=True,
                        )
                        location_data = get_location_data_from_party_tracker(
                            party_tracker_data
                        )
                        ai_response = get_ai_response(followup_history)
                        if result_status == "needs_post_combat_narration":
                            process_ai_response._just_finished_combat = True
                        return process_ai_response(
                            ai_response,
                            party_tracker_data,
                            location_data,
                            followup_history,
                        )
                    # Check if we need to generate a DM response (e.g., after module creation)
                    if result.get("needs_dm_response"):
                        if action.get("action") == "transitionLocation":
                            needs_transition_dm_response = True
                            continue
                        followup_history = (
                            load_json_file(json_file)
                            or conversation_history
                        )
                        (
                            followup_history,
                            party_tracker_data,
                        ) = rebuild_conversation_for_current_party(
                            followup_history,
                            return_party=True,
                        )
                        location_data = get_location_data_from_party_tracker(
                            party_tracker_data
                        )
                        ai_response = get_ai_response(followup_history)
                        return process_ai_response(
                            ai_response,
                            party_tracker_data,
                            location_data,
                            followup_history,
                        )
                elif isinstance(result, bool) and result:
                    needs_conversation_history_update = True
            if actions_processed:
                party_tracker_data = load_json_file("party_tracker.json")

            if location_transition_id is not None:
                resumed = _resume_v2_location_transition(
                    location_transition_id, publish=True
                )
                if resumed.get("status") != "completed":
                    return {
                        "status": "transition_context_pending",
                        "retryable": True,
                        "error": resumed.get("reason", "transition resume pending"),
                    }
                if resumed.get("terminal_action") == "exit":
                    return "exit"
                return {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "narration": resumed.get("narration", ""),
                            "actions": [],
                        }
                    ),
                }
            
            # Step 2: Reload the state to get the NEW location context
            fresh_party_data = load_json_file("party_tracker.json")
            fresh_conversation_history = load_json_file(json_file) or []
            
            # Step 3: generate every prose layer from the committed, disclosure-
            # filtered destination projection. No transient placeholder is saved.
            transition_narration = generate_transition_narration(
                committed_transition_prompt or departure_narration,
                fresh_party_data,
            )
            arrival_narration = generate_arrival_narration(
                transition_narration,
                fresh_party_data,
                fresh_conversation_history,
            )
            
            # <--- MODIFIED SECTION: Use the new seamless narration generator --->
            # Step 4: Blend the departure and arrival narrations into a single, cohesive story.
            full_narration = generate_seamless_transition_narration(
                transition_narration, arrival_narration
            )

            # T063/T064 may overlap another worker's transition. Do not save
            # or display narration for a destination that was superseded while
            # those provider calls were running.
            from core.managers.campaign_manager import (
                _party_module_transition_lock,
            )

            with _party_module_transition_lock():
                authoritative_party = load_json_file("party_tracker.json")
                if _party_transition_projection(
                    authoritative_party
                ) != _party_transition_projection(fresh_party_data):
                    superseded_history = load_json_file(json_file) or []
                    if remove_transition_placeholder(
                        superseded_history,
                        transition_placeholder,
                    ):
                        save_conversation_history(
                            superseded_history,
                            strict=True,
                            allow_compression=False,
                        )
                    if location_transition_id is not None:
                        action_handler.complete_location_transition_checkpoint(
                            location_transition_id
                        )
                    return {
                        "status": "transition_state_changed",
                        "retryable": True,
                    }

            # Record deferred work before publishing final narration. If the
            # process dies after the history write, restart recovery must still
            # know that non-idempotent ordered actions were outstanding.
            if location_transition_id is not None:
                if not action_handler.mark_location_transition_deferred_pending(
                    location_transition_id,
                    deferred_actions,
                ):
                    warning(
                        "Transition checkpoint could not record deferred-action "
                        "state before final narration",
                        category="location_transitions",
                    )

            if location_transition_id is not None:
                transition_checkpoint = (
                    action_handler.load_current_transition_checkpoint(
                        location_transition_id
                    )
                )
                episode_record = transition_checkpoint["episode"]
                if episode_record.get("status") == "pending":
                    try:
                        from core.npc.episode_capture import (
                            boundary_turn_id_for_position,
                            capture_location_episode,
                        )

                        boundary_turn_id = boundary_turn_id_for_position(
                            sum(
                                1
                                for message in (
                                    load_json_file(json_file) or []
                                )
                                if isinstance(message, dict)
                                and message.get("role") == "user"
                                and "Location transition:"
                                in message.get("content", "")
                            )
                            + 1
                        )
                        episode_record["boundary_turn_id"] = boundary_turn_id
                        episode_id = capture_location_episode(
                            leaving_location_name=transition_checkpoint[
                                "origin_location_name"
                            ],
                            leaving_location_id=transition_checkpoint[
                                "origin_location_id"
                            ],
                            segment_messages=episode_record[
                                "source_entries_before"
                            ],
                            party_tracker_data=fresh_party_data,
                            path_manager=ModulePathManager(
                                transition_checkpoint["module_name"]
                            ),
                            boundary_turn_id=boundary_turn_id,
                            player_name=(
                                fresh_party_data.get("partyMembers") or [""]
                            )[0],
                        )
                        episode_record["status"] = (
                            "committed"
                            if episode_id
                            else "attempted_unavailable"
                        )
                        episode_record["episode_id"] = episode_id
                    except Exception as episode_error:
                        episode_record["status"] = "attempted_unavailable"
                        warning(
                            "T108 episode unavailable after local cleanup: %s"
                            % type(episode_error).__name__,
                            category="conversation_management",
                        )
                    action_handler._write_location_transition_checkpoint(
                        transition_checkpoint
                    )

                compaction_record = transition_checkpoint[
                    "conversation_compaction"
                ]
                if compaction_record.get("status") != "committed":
                    from core.ai.cumulative_summary import (
                        compact_with_accepted_departure_summary,
                    )

                    current_history = load_json_file(json_file) or []
                    summary_message_id = (
                        compaction_record.get("summary_message_id")
                        or str(uuid4())
                    )
                    compacted_history, summary_entry = (
                        compact_with_accepted_departure_summary(
                            current_history,
                            source_index=transition_checkpoint[
                                "origin_history_boundary"
                            ],
                            source_entries_before=transition_checkpoint[
                                "origin_segment_before"
                            ],
                            leaving_location_name=transition_checkpoint[
                                "origin_location_name"
                            ],
                            summary=transition_checkpoint[
                                "departure_summary"
                            ]["text"],
                            summary_message_id=summary_message_id,
                        )
                    )
                    world = fresh_party_data["worldConditions"]
                    transition_marker = {
                        "role": "user",
                        "content": (
                            "Location transition: %s (%s) to %s (%s)"
                            % (
                                transition_checkpoint["origin_location_name"],
                                transition_checkpoint["origin_location_id"],
                                world["currentLocation"],
                                world["currentLocationId"],
                            )
                        ),
                    }
                    summary_index = next(
                        index
                        for index, message in enumerate(compacted_history)
                        if isinstance(message, dict)
                        and message.get("message_id") == summary_message_id
                    )
                    if (
                        summary_index + 1 >= len(compacted_history)
                        or compacted_history[summary_index + 1]
                        != transition_marker
                    ):
                        compacted_history.insert(
                            summary_index + 1, transition_marker
                        )
                    compaction_record.update(
                        {
                            "status": "pending",
                            "source_index": transition_checkpoint[
                                "origin_history_boundary"
                            ],
                            "source_entries_before": transition_checkpoint[
                                "origin_segment_before"
                            ],
                            "result_entries_after": [
                                summary_entry,
                                transition_marker,
                            ],
                            "summary_message_id": summary_message_id,
                        }
                    )
                    action_handler._write_location_transition_checkpoint(
                        transition_checkpoint
                    )
                    save_conversation_history(
                        compacted_history,
                        strict=True,
                        allow_compression=False,
                    )
                    compaction_record["status"] = "committed"
                    transition_checkpoint["phase"] = "history_compacted"
                    action_handler._write_location_transition_checkpoint(
                        transition_checkpoint
                    )

                chronicle_record = transition_checkpoint["chunked_chronicle"]
                if chronicle_record.get("status") == "pending":
                    from core.ai.chunked_compression_integration import (
                        check_and_perform_chunked_compression,
                    )

                    history_before_chronicle = load_json_file(json_file) or []
                    chronicle_record.update(
                        {
                            "source_index": 0,
                            "source_entries_before": history_before_chronicle,
                            "result_entries_after": None,
                        }
                    )
                    action_handler._write_location_transition_checkpoint(
                        transition_checkpoint
                    )
                    chronicle_changed = check_and_perform_chunked_compression()
                    history_after_chronicle = load_json_file(json_file) or []
                    chronicle_record["result_entries_after"] = (
                        history_after_chronicle
                    )
                    chronicle_record["status"] = (
                        "committed" if chronicle_changed else "not_due"
                    )
                    action_handler._write_location_transition_checkpoint(
                        transition_checkpoint
                    )

                memory_record = transition_checkpoint["legacy_memory"]
                if memory_record.get("status") == "pending":
                    # [travel-clean #209] legacy companion-memory reconciliation deferred until
                    # the voice/episodic line lands; process_journal_operation is absent here.
                    memory_record["status"] = "not_applicable"
                    action_handler._write_location_transition_checkpoint(transition_checkpoint)
                if memory_record.get("status") == "__deferred_209__":
                    from core.memories.companion_memory import (
                        CompanionMemoryManager,
                    )
                    from utils.npc_name_canonicalizer import get_canonical_name

                    canonical_npcs = []
                    for npc in fresh_party_data.get("partyNPCs", []):
                        npc_name = (
                            npc.get("name", "")
                            if isinstance(npc, dict)
                            else str(npc)
                        )
                        if npc_name:
                            canonical_name = get_canonical_name(npc_name)
                            if canonical_name:
                                canonical_npcs.append(canonical_name)
                    memory_record["roster_before"] = canonical_npcs
                    action_handler._write_location_transition_checkpoint(
                        transition_checkpoint
                    )
                    if canonical_npcs:
                        memory_manager = CompanionMemoryManager()
                        memory_manager.process_journal_operation(
                            transition_checkpoint["departure_commit"][
                                "journal_entry_after"
                            ],
                            canonical_npcs,
                            transition_checkpoint["operation_id"],
                        )
                        try:
                            subprocess.run(
                                [
                                    sys.executable,
                                    "scripts/memory_management/compress_memories.py",
                                ],
                                capture_output=True,
                                text=True,
                                timeout=30,
                                check=False,
                            )
                        except Exception as memory_compression_error:
                            warning(
                                "Legacy memory compression remained unavailable: %s"
                                % type(memory_compression_error).__name__,
                                category="conversation_management",
                            )
                        memory_record["status"] = "committed"
                    else:
                        memory_record["status"] = "not_applicable"
                    transition_checkpoint["phase"] = "enrichments_committed"
                    action_handler._write_location_transition_checkpoint(
                        transition_checkpoint
                    )

            # Stage and retain the one final narration before player delivery.
            fresh_conversation_history = load_json_file(json_file) or []
            narration_message_id = None
            if location_transition_id is not None:
                transition_checkpoint = (
                    action_handler.load_current_transition_checkpoint(
                        location_transition_id
                    )
                )
                if transition_checkpoint is None:
                    return {
                        "status": "transition_context_pending",
                        "retryable": True,
                        "error": "transition checkpoint disappeared before narration",
                    }
                narration_record = transition_checkpoint["narration"]
                narration_message_id = narration_record["message_id"]
                narration_entry = {
                    "role": "assistant",
                    "content": full_narration,
                    "message_id": narration_message_id,
                }
                existing_index = next(
                    (
                        index
                        for index, message in enumerate(fresh_conversation_history)
                        if isinstance(message, dict)
                        and message.get("message_id") == narration_message_id
                    ),
                    None,
                )
                if existing_index is None:
                    narration_record.update(
                        {
                            "status": "pending",
                            "text": full_narration,
                            "history_index": len(fresh_conversation_history),
                            "history_entry_before": None,
                            "history_entry_after": narration_entry,
                        }
                    )
                    transition_checkpoint["phase"] = "narration_pending"
                    action_handler._write_location_transition_checkpoint(
                        transition_checkpoint
                    )
                    fresh_conversation_history.append(narration_entry)
                elif fresh_conversation_history[existing_index] != narration_entry:
                    return {
                        "status": "transition_context_pending",
                        "retryable": True,
                        "error": "stable narration identity conflicts with history",
                    }
            else:
                fresh_conversation_history.append(
                    {"role": "assistant", "content": full_narration}
                )

            save_conversation_history(
                fresh_conversation_history,
                strict=True,
                allow_compression=False,
            )
            if location_transition_id is not None:
                transition_checkpoint = (
                    action_handler.load_current_transition_checkpoint(
                        location_transition_id
                    )
                )
                transition_checkpoint["narration"]["status"] = "retained"
                transition_checkpoint["phase"] = "narration_retained"
                action_handler._write_location_transition_checkpoint(
                    transition_checkpoint
                )
            def finish_location_transition_checkpoint():
                if location_transition_id is None:
                    return
                if not action_handler.complete_location_transition_checkpoint(
                    location_transition_id
                ):
                    warning(
                        "Deferred transition actions finished, but checkpoint "
                        "cleanup could not be correlated",
                        category="location_transitions",
                    )

            # Party movement and the exact narration the player is about to
            # but it must not create a history/display mismatch.
            display_dm_narration(
                full_narration,
                message_id=narration_message_id,
            )
            if location_transition_id is not None:
                transition_checkpoint = (
                    action_handler.load_current_transition_checkpoint(
                        location_transition_id
                    )
                )
                transition_checkpoint["narration"]["status"] = "published"
                action_handler._write_location_transition_checkpoint(
                    transition_checkpoint
                )

            if pending_archive_info:
                try:
                    _targeted, completion_outcome = retry_staged_module_completions(
                        pending_archive_info,
                        fresh_conversation_history,
                    )
                    if (
                        completion_outcome["failed"]
                        or completion_outcome["blocked"]
                    ):
                        return {
                            "status": "module_completion_pending",
                            "retryable": True,
                            "completion_outcome": completion_outcome,
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "narration": full_narration,
                                    "actions": [],
                                }
                            ),
                        }
                    completion_confirmed = (
                        _targeted is not None
                        or pending_archive_info["completion_id"]
                        in completion_outcome["completed"]
                    )
                    if not completion_confirmed:
                        return {
                            "status": "module_completion_pending",
                            "retryable": True,
                            "error": (
                                "Transition completion was not receipt-backed"
                            ),
                            "completion_outcome": completion_outcome,
                        }
                except Exception as completion_exc:
                    error(
                        "FAILURE: Cross-module completion remains queued",
                        exception=completion_exc,
                        category="module_management",
                    )
                    return {
                        "status": "module_completion_pending",
                        "retryable": True,
                        "error": str(completion_exc),
                        "role": "assistant",
                        "content": json.dumps(
                            {"narration": full_narration, "actions": []}
                        ),
                    }

            # The transition's final displayed history and any ordered
            # completion are now durable. Force a rebuild even for a
            # within-module move: the targeted drain happened earlier, so the
            # normal pre-request hook cannot infer that its context is stale.
            try:
                (
                    fresh_conversation_history,
                    party_tracker_data,
                ) = (
                    rebuild_conversation_for_current_party(
                        fresh_conversation_history,
                        return_party=True,
                    )
                )
                deferred_location_data = (
                    get_location_data_from_party_tracker(
                        party_tracker_data
                    )
                )
            except Exception as context_exc:
                return {
                    "status": "transition_context_pending",
                    "retryable": True,
                    "error": str(context_exc),
                }

            # Only now may later actions (especially saveGame) observe and
            # snapshot the destination timeline.
            for deferred_index, action in enumerate(deferred_actions):
                if location_transition_id is not None:
                    staged_checkpoint = (
                        action_handler.load_current_transition_checkpoint(
                            location_transition_id
                        )
                    )
                    if staged_checkpoint is not None:
                        staged_result = (
                            action_handler.apply_current_transition_action(
                                location_transition_id, deferred_index
                            )
                        )
                        if staged_result == "blocked_conflict":
                            return {
                                "status": "transition_context_pending",
                                "retryable": True,
                                "error": (
                                    "a staged deferred action conflicts with "
                                    "the authoritative state"
                                ),
                            }
                        party_tracker_data = load_json_file("party_tracker.json")
                        deferred_location_data = (
                            get_location_data_from_party_tracker(
                                party_tracker_data
                            )
                        )
                        continue
                result = action_handler.process_action(
                    action,
                    party_tracker_data,
                    deferred_location_data,
                    fresh_conversation_history,
                )
                if isinstance(result, dict):
                    if result.get("needs_update"):
                        needs_conversation_history_update = True
                    result_status = result.get("status")
                    if result_status == "error":
                        return _handle_ordinary_action_failure(
                            result,
                            response,
                            action,
                            fresh_conversation_history,
                        )
                    response_data = result.get("response_data")
                    deferred_pending = (
                        response_data.get("pending_archive")
                        if isinstance(response_data, dict)
                        else None
                    )
                    if isinstance(deferred_pending, dict):
                        latest_history = (
                            load_json_file(json_file)
                            or fresh_conversation_history
                        )
                        try:
                            deferred_targeted, deferred_outcome = (
                                retry_staged_module_completions(
                                    deferred_pending,
                                    latest_history,
                                )
                            )
                        except Exception as deferred_completion_exc:
                            return {
                                "status": "module_completion_pending",
                                "retryable": True,
                                "error": str(deferred_completion_exc),
                            }
                        deferred_confirmed = (
                            deferred_targeted is not None
                            or deferred_pending["completion_id"]
                            in deferred_outcome["completed"]
                        )
                        if (
                            deferred_outcome["failed"]
                            or deferred_outcome["blocked"]
                            or not deferred_confirmed
                        ):
                            return {
                                "status": "module_completion_pending",
                                "retryable": True,
                                "completion_outcome": deferred_outcome,
                            }
                        (
                            fresh_conversation_history,
                            party_tracker_data,
                        ) = (
                            rebuild_conversation_for_current_party(
                                latest_history,
                                return_party=True,
                            )
                        )
                        deferred_location_data = (
                            get_location_data_from_party_tracker(
                                party_tracker_data
                            )
                        )
                    elif result.get("needs_update"):
                        fresh_conversation_history = (
                            load_json_file(json_file)
                            or fresh_conversation_history
                        )
                        refreshed_party = load_json_file(
                            "party_tracker.json"
                        )
                        if isinstance(refreshed_party, dict):
                            party_tracker_data = refreshed_party
                            deferred_location_data = (
                                get_location_data_from_party_tracker(
                                    party_tracker_data
                                )
                            )
                    if result_status == "exit":
                        finish_location_transition_checkpoint()
                        return "exit"
                    if result_status == "restart":
                        finish_location_transition_checkpoint()
                        return "restart"
                    if result_status == "enter_levelup_mode":
                        finish_location_transition_checkpoint()
                        return result
                    if (
                        result.get("needs_dm_response")
                        or result_status
                        in {
                            "needs_post_combat_narration",
                            "needs_response",
                        }
                    ):
                        followup_history = (
                            load_json_file(json_file)
                            or fresh_conversation_history
                        )
                        (
                            followup_history,
                            party_tracker_data,
                        ) = (
                            rebuild_conversation_for_current_party(
                                followup_history,
                                return_party=True,
                            )
                        )
                        deferred_location_data = (
                            get_location_data_from_party_tracker(
                                party_tracker_data
                            )
                        )
                        ai_response = get_ai_response(followup_history)
                        if result_status == "needs_post_combat_narration":
                            process_ai_response._just_finished_combat = True
                        finish_location_transition_checkpoint()
                        return process_ai_response(
                            ai_response,
                            party_tracker_data,
                            deferred_location_data,
                            followup_history,
                        )
                elif isinstance(result, str) and result in {"exit", "restart"}:
                    finish_location_transition_checkpoint()
                    return result
                elif isinstance(result, bool) and result:
                    needs_conversation_history_update = True
                    fresh_conversation_history = (
                        load_json_file(json_file)
                        or fresh_conversation_history
                    )
                    refreshed_party = load_json_file("party_tracker.json")
                    if isinstance(refreshed_party, dict):
                        party_tracker_data = refreshed_party
                        deferred_location_data = (
                            get_location_data_from_party_tracker(
                                party_tracker_data
                            )
                        )

            # Every ordered action returned successfully. Freeze and verify
            # the final accepted history/party/context before retiring the
            # runtime checkpoint; queued Save may run only after this point.
            if location_transition_id is not None:
                final_checkpoint = (
                    action_handler.load_current_transition_checkpoint(
                        location_transition_id
                    )
                )
                final_history = load_json_file(json_file) or []
                final_party = load_json_file("party_tracker.json") or {}
                final_context = get_location_data_from_party_tracker(final_party)
                final_checkpoint["final_context"].update(
                    {
                        "status": "committed",
                        "history_before": final_history,
                        "history_after": final_history,
                        "party_projection_after": _party_transition_projection(
                            final_party
                        ),
                        "context_after": final_context,
                    }
                )
                final_checkpoint["phase"] = "final_context_committed"
                action_handler._write_location_transition_checkpoint(
                    final_checkpoint
                )

            # Every receipt and final context is durable. Only now is the
            # within-module transition checkpoint safe to retire.
            finish_location_transition_checkpoint()

            if needs_transition_dm_response:
                followup_history = load_json_file(json_file) or fresh_conversation_history
                (
                    followup_history,
                    party_tracker_data,
                ) = rebuild_conversation_for_current_party(
                    followup_history,
                    return_party=True,
                )
                deferred_location_data = get_location_data_from_party_tracker(
                    party_tracker_data
                )
                ai_response = get_ai_response(followup_history)
                return process_ai_response(
                    ai_response,
                    party_tracker_data,
                    deferred_location_data,
                    followup_history,
                )

            return {"role": "assistant", "content": json.dumps({"narration": full_narration, "actions": []})}
        
        # --- END NEW TRANSITION LOGIC ---

        # If not a transition or levelup, proceed with normal processing
        narration = parsed_response.get("narration", "")
        sanitized_narration = sanitize_text(narration)
        display_dm_narration(sanitized_narration)

        actions_processed = False
        
        # Debug: Log what actions we received
        debug(f"STATE_CHANGE: Received {len(actions)} total actions", category="character_updates")
        print(f"DEBUG: STATE_CHANGE: Received {len(actions)} total actions")
        for i, action in enumerate(actions):
            debug(f"  Action {i+1}: {action.get('action', 'unknown')}", category="character_updates")
            print(f"DEBUG:   Action {i+1}: {action.get('action', 'unknown')}")
        
        # Separate updateCharacterInfo actions from the other action families.
        char_update_actions = [action for action in actions if action.get("action") == "updateCharacterInfo"]
        other_actions = [action for action in actions if action.get("action") != "updateCharacterInfo"]
        if char_update_actions and _agentic_post_combat_narration_pass(
            party_tracker_data
        ):
            retained_updates = []
            dropped_update_count = 0
            for action in char_update_actions:
                if _agentic_post_combat_engine_echo(action):
                    dropped_update_count += 1
                    debug(
                        "STATE_CHANGE: Ignoring an agentic post-combat "
                        "character-state echo; the committed combat state "
                        "is authoritative",
                        category="character_updates",
                    )
                else:
                    retained_updates.append(action)
            char_update_actions = retained_updates
            if dropped_update_count:
                drop_notice = {
                    "role": "system",
                    "content": _AGENTIC_POST_COMBAT_DROP_NOTICE,
                }
                conversation_history.append(drop_notice)
                save_conversation_history(conversation_history)
                display_dm_narration(
                    _AGENTIC_POST_COMBAT_DROP_NOTICE,
                    channel="system",
                    color="yellow",
                )
                _record_agentic_post_combat_updates_dropped(
                    dropped_update_count
                )
        
        debug(f"STATE_CHANGE: Separated into {len(char_update_actions)} character updates and {len(other_actions)} other actions", category="character_updates")
        print(f"DEBUG: STATE_CHANGE: Separated into {len(char_update_actions)} character updates and {len(other_actions)} other actions")
        
        # If there are no actions at all, signal that processing is complete
        if len(actions) == 0:
            try:
                from core.managers.status_manager import status_manager
                status_manager.update_status("Ready for input", is_processing=False)
                debug("STATE_CHANGE: No actions to process, setting status to ready", category="character_updates")
            except Exception as e:
                debug(f"Could not update status: {e}", category="status")
        
        # Character updates are ordered state mutations. Run them one at a
        # time so a failed update prevents every later sibling from starting.
        if char_update_actions:
            debug(
                f"STATE_CHANGE: Processing {len(char_update_actions)} "
                "character updates sequentially",
                category="character_updates",
            )
            print(
                "DEBUG: STATE_CHANGE: Processing "
                f"{len(char_update_actions)} character updates sequentially"
            )
            for action in char_update_actions:
                try:
                    result = action_handler.process_action(
                        action,
                        party_tracker_data,
                        location_data,
                        conversation_history,
                    )
                except Exception as action_error:
                    error(
                        "FAILURE: Character update handler raised unexpectedly",
                        exception=action_error,
                        category="character_updates",
                    )
                    result = {"status": "error"}
                actions_processed = True
                if isinstance(result, dict):
                    if result.get("status") == "error":
                        return _handle_ordinary_action_failure(
                            result,
                            response,
                            action,
                            conversation_history,
                        )
                    if result.get("needs_update"):
                        needs_conversation_history_update = True
                elif isinstance(result, bool) and result:
                    needs_conversation_history_update = True
        
        # Track pending archive info for delayed processing
        pending_archive_info = None
        
        # Process all other actions sequentially
        for action in other_actions:
            # Snapshot the history length BEFORE the handler runs: needs_response
            # producers append their user-role note to this same list, and the
            # follow-up block below must insert the assistant candidate BEFORE
            # that note to keep chronology (candidate came first) and a user-role
            # tail (issue #168: a trailing assistant turn makes strict-alternation
            # local templates emit an immediate empty end-of-turn).
            pre_action_len = len(conversation_history)
            try:
                result = action_handler.process_action(
                    action,
                    party_tracker_data,
                    location_data,
                    conversation_history,
                )
            except Exception as action_error:
                error(
                    "FAILURE: Action handler raised unexpectedly",
                    exception=action_error,
                    category="action_processing",
                )
                result = {"status": "error", "success": False}
            actions_processed = True

            # Standard action failures are terminal for this response. The
            # narration has already been displayed, so persist it exactly once
            # and stop before any later action can mutate game state.
            if isinstance(result, dict) and result.get("status") == "error":
                safe_result = _handle_ordinary_action_failure(
                    result,
                    response,
                    action,
                    conversation_history,
                )
                return safe_result

            if isinstance(result, dict) and result.get("needs_dm_response"):
                return _complete_committed_module_followup(
                    result,
                    response,
                    conversation_history,
                )
            if isinstance(result, dict) and result.get("status") == "published":
                # Module publication is an irreversible terminal action for
                # this response; never execute later sibling actions. (P2b: the
                # receipt-era published_replay/published_followup_pending states
                # are gone -- atomic publish + in-turn narration yields one
                # terminal "published" state.)
                return result
            
            # Check for pending archive flag from module transitions
            if isinstance(result, dict) and result.get("response_data", {}).get("pending_archive"):
                pending_archive_info = result["response_data"]["pending_archive"]
                print(f"DEBUG: [Module Transition] Captured pending archive info: from {pending_archive_info['from_module']} to {pending_archive_info['to_module']}")
                # Drain before any later action (especially saveGame) or
                # signal-driven early return can leave the switch behind.
                completion_history = list(conversation_history)
                completion_history.append(
                    {"role": "assistant", "content": response}
                )
                try:
                    _targeted, completion_outcome = retry_staged_module_completions(
                        pending_archive_info,
                        completion_history,
                    )
                    if (
                        completion_outcome["failed"]
                        or completion_outcome["blocked"]
                    ):
                        return {
                            "status": "module_completion_pending",
                            "retryable": True,
                            "completion_outcome": completion_outcome,
                        }
                    completion_confirmed = (
                        _targeted is not None
                        or pending_archive_info["completion_id"]
                        in completion_outcome["completed"]
                    )
                    if not completion_confirmed:
                        return {
                            "status": "module_completion_pending",
                            "retryable": True,
                            "error": (
                                "Transition completion was not receipt-backed"
                            ),
                            "completion_outcome": completion_outcome,
                        }
                except Exception as completion_exc:
                    error(
                        "FAILURE: Module completion remains queued before "
                        "subsequent actions",
                        exception=completion_exc,
                        category="module_management",
                    )
                    return {
                        "status": "module_completion_pending",
                        "retryable": True,
                        "error": str(completion_exc),
                    }
            
            # --- SIGNAL-BASED SUB-SYSTEM CONTROL ---
            # Check for special signals from the action handler that indicate a sub-system has completed.
            if isinstance(result, dict) and result.get("status") == "needs_post_combat_narration":
                # This signal means combat finished and its summary was added to the history.
                # The action_handler has already:
                # 1. Run the entire combat encounter
                # 2. Added the [COMBAT CONCLUDED...] summary to conversation_history
                # 3. Returned this signal instead of a normal response
                
                debug("STATE_CHANGE: Combat resolved. Requesting post-combat narration from AI.", category="combat_events")
                
                # We must reload the history from disk to ensure we have the combat summary.
                # This is necessary because the action_handler modified and saved the history independently.
                post_combat_history = load_json_file(json_file) or conversation_history
                ai_response_after_combat = get_ai_response(post_combat_history)
                
                # Set flag to indicate we just finished combat (for XP display fix)
                process_ai_response._just_finished_combat = True
                
                # Process the AI's post-combat response by calling this function again (recursively).
                # This ensures the post-combat narration is handled just like any other turn,
                # maintaining consistency in how we process AI responses.
                return process_ai_response(ai_response_after_combat, party_tracker_data, location_data, post_combat_history)
            # --- END SIGNAL-BASED SUB-SYSTEM CONTROL ---
            
            if isinstance(result, dict):
                if result.get("status") == "exit": return "exit"
                if result.get("status") == "restart": return "restart"
                # This check is now crucial for the level up flow
                if result.get("status") == "enter_levelup_mode":
                    return result
                if result.get("status") == "needs_response":
                    # The handler appended its user-role note (e.g. a storage
                    # error) to this same list and saved. Keep the candidate in
                    # history (the follow-up model must know what it already
                    # said) but INSERT it before the handler's note: the
                    # candidate chronologically precedes the note, and the
                    # history tail must stay user-role -- a trailing assistant
                    # turn makes strict-alternation local templates (Gemma via
                    # LM Studio) emit an immediate empty end-of-turn, killing
                    # the follow-up T067 call (issue #168 class).
                    current_response = {"role": "assistant", "content": response}
                    insert_at = min(pre_action_len, len(conversation_history))
                    conversation_history.insert(insert_at, current_response)
                    save_conversation_history(conversation_history)

                    # Now reload and get the new AI response
                    conversation_history = load_json_file("modules/conversation_history/conversation_history.json") or []
                    ai_response = get_ai_response(conversation_history)
                    return process_ai_response(ai_response, party_tracker_data, location_data, conversation_history)
                if result.get("needs_update"): needs_conversation_history_update = True
            elif result == "exit": return "exit"
            elif isinstance(result, bool) and result: needs_conversation_history_update = True

        if actions_processed:
            party_tracker_data = load_json_file("party_tracker.json")
            
            if hasattr(action_handler.process_action, 'level_up_summaries') and action_handler.process_action.level_up_summaries:
                debug(f"STATE_CHANGE: Injecting {len(action_handler.process_action.level_up_summaries)} level up summaries", category="level_up")
                
                combined_summary = "\n\n".join(action_handler.process_action.level_up_summaries)
                conversation_history.append({"role": "user", "content": combined_summary})
                save_conversation_history(conversation_history)
                
                action_handler.process_action.level_up_summaries = []
                
                ai_response = get_ai_response(conversation_history)
                return process_ai_response(ai_response, party_tracker_data, location_data, conversation_history)

        # STANDARD TURN COMPLETION: For a normal turn (no special signals or sub-systems),
        # we append the AI's response to history here in process_ai_response.
        # This centralizes history management - the main_game_loop no longer needs to handle it.
        # This ensures the history is saved atomically with the response processing,
        # preventing any possibility of the history and game state becoming out of sync.
        assistant_message = {"role": "assistant", "content": response}
        conversation_history.append(assistant_message)
        save_conversation_history(conversation_history)
        
        # DELAYED ARCHIVING: Process any pending archive after the AI response is saved
        if pending_archive_info:
            print(f"DEBUG: [Module Transition] Processing delayed archive for module: {pending_archive_info['from_module']}")
            try:
                # Reload conversation history to ensure we have the travel narrative
                fresh_conversation_history = load_json_file("modules/conversation_history/conversation_history.json") or []
                
                # The durable intent owns archive creation, T038/T039, visit
                # tracking, campaign merge, and crash recovery.
                summary, _outcome = retry_staged_module_completions(
                    pending_archive_info,
                    fresh_conversation_history,
                )
                print(f"DEBUG: [Module Transition] Summary generated and committed successfully")
                print(f"DEBUG: [Module Transition] Summary keys: {list(summary.keys()) if summary else 'None'}")
                info(
                    f"SUCCESS: Archived and summarized module: {pending_archive_info['from_module']}",
                    category="module_management",
                )
                    
            except Exception as e:
                print(f"ERROR: Failed to process delayed archive: {str(e)}")
                print(f"ERROR: Module name was: {pending_archive_info.get('from_module', 'UNKNOWN')}")
                print(f"ERROR: Pending archive info: {pending_archive_info}")
                import traceback
                traceback.print_exc()
                error(f"FAILURE: Delayed archive processing failed for {pending_archive_info.get('from_module', 'UNKNOWN')}", exception=e, category="module_management")
        
        return assistant_message

    except json.JSONDecodeError as e:
        print(f"Error: Unable to parse AI response as JSON: {e}")
        print(f"Problematic response: {response}")
        sanitized_response = sanitize_text(response)
        display_dm_narration(sanitized_response)
        # Even in error case, append to history
        assistant_message = {"role": "assistant", "content": response}
        conversation_history.append(assistant_message)
        save_conversation_history(conversation_history)
        return assistant_message
    finally:
        response_fences.close()


def resolve_retryable_ai_result(
    final_result,
    party_tracker_data,
    location_data,
    conversation_history,
    *,
    max_state_retries=2,
):
    """Regenerate responses invalidated by a concurrent timeline change."""
    retry_statuses = {
        "invalid_transition_actions",
        "stale_response_context",
        "transition_state_changed",
    }
    retries = 0
    while (
        isinstance(final_result, dict)
        and final_result.get("retryable") is True
        and final_result.get("status") in retry_statuses
        and retries < max_state_retries
    ):
        retries += 1
        conversation_history = load_json_file(json_file) or conversation_history
        try:
            (
                conversation_history,
                party_tracker_data,
            ) = rebuild_conversation_for_current_party(
                conversation_history,
                return_party=True,
            )
        except Exception as context_exc:
            final_result = {
                "status": "transition_context_pending",
                "retryable": True,
                "error": str(context_exc),
            }
            break
        location_data = get_location_data_from_party_tracker(
            party_tracker_data
        )
        regenerated_response = get_ai_response(conversation_history)
        final_result = process_ai_response(
            regenerated_response,
            party_tracker_data,
            location_data,
            conversation_history,
        )
    return (
        final_result,
        party_tracker_data,
        location_data,
        conversation_history,
    )


def save_conversation_history(
    history,
    *,
    strict=False,
    allow_compression=True,
):
    history_to_save = history
    try:
        # Compression is an optional optimization.  Its constructor, local
        # context lookup, or provider call must never prevent the authoritative
        # conversation from being persisted.
        try:
            if allow_compression:
                compressor = IncrementalLocationCompressor()

                # Check compression conditions (15+ valid pairs at current location)
                if compressor.should_compress(history):
                    debug("Compression conditions met - applying incremental compression", category="compression")

                    # Apply compression (returns new list if successful)
                    compressed_history = compressor.apply_compression_to_list(history)
                    if compressed_history:
                        history_to_save = compressed_history
                        info("Conversation history compressed successfully", category="compression")
                    else:
                        debug("Compression not applied - conditions not fully met", category="compression")
        except Exception as compression_error:
            warning(
                "Conversation compression failed; saving uncompressed history: "
                f"{compression_error}",
                category="compression",
            )

        safe_json_dump(history_to_save, json_file)
        return True
    except Exception as e:
        error(f"FAILURE: Failed to save conversation history", exception=e, category="file_operations")
        if strict:
            raise
        return False

def _get_ai_response_impl(
    conversation_history,
    validation_retry_count=0,
    *,
    npc_voice_batch=None,
    prepare_history=True,
    live_selected=False,
    detached_context=None,
):
    global should_inject_creation_prompt
    # This is the centralized terminal/web provider boundary. A transition
    # published by another worker between turns must finish (in durable order)
    # before model selection or request construction. If the drain changed
    # campaign state, rebuild the already-assembled system context in place.
    #
    # detached_context (issue #214): {scope, status} for the off-thread
    # startup welcome. The worker NEVER prepares history (the game thread owns
    # the authoritative drain), skips T082 (no player action to classify),
    # routes all liveness through the non-input-locking status sink, and its
    # provider calls run under the caller-owned cancellable scope.
    if prepare_history:
        prepare_conversation_for_ai_request(conversation_history)
    if detached_context:
        detached_status = detached_context.get("status")
        if detached_status is not None:
            detached_status("The DM is recalling your journey...")
    else:
        status_processing_ai()
    
    # Import action predictor and config
    from utils.action_predictor import predict_actions_required, extract_actual_actions, log_prediction_accuracy
    import config
    import core.ai.api_client as api_client
    
    # Get the last user message for action prediction
    user_input = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            user_input = msg.get("content", "")
            break
    
    # Check if module creation prompt is present in user input
    has_module_creation_prompt = "You are a master storyteller, cartographer of myth" in user_input
    
    # Predict if actions will be required (unless we're in a validation retry or module creation prompt)
    if detached_context:
        # #214: the detached startup welcome has no player action to classify.
        # Skip the synchronous, non-cancellable T082 call entirely and FORCE
        # the full T067 route (use_mini stays False). A legitimate updatePlot
        # from the welcome remains possible (D-214-3) - this is a routing
        # skip, not a semantic restriction.
        prediction = {"requires_actions": True, "reason": "skipped-welcome"}
    elif validation_retry_count == 0 and not has_module_creation_prompt:
        prediction = predict_actions_required(user_input)
    elif has_module_creation_prompt:
        # Force full model when module creation prompt is present
        prediction = {"requires_actions": True, "reason": "Module creation prompt detected - using full model"}
    else:
        # On validation retry, force full model and skip prediction
        prediction = {"requires_actions": True, "reason": "Validation retry - using full model"}
    
    # Determine which model to use based on intelligent routing and validation retry.
    # HIGH-1: carry the routing decision as a BOOLEAN (use_mini), not a model
    # string. selected_model is a snapshot of config.DM_MINI/FULL_MODEL; if
    # set_provider() rewrites those mid-session, an `== config.DM_MINI_MODEL`
    # compare below would silently always pick the full model and defeat
    # intelligent routing (a large cost regression on Gemini/GPT-5.x).
    use_mini = False
    if detached_context:
        # #214: forced full route for the detached welcome (never mini).
        print("DEBUG: MODEL ROUTING - Detached welcome: T082 skipped, using FULL MODEL")
    elif config.ENABLE_INTELLIGENT_ROUTING and validation_retry_count == 0 and not has_module_creation_prompt:
        # Use prediction to determine model (Phase 2 of token optimization)
        use_mini = not prediction["requires_actions"]

        # Log the routing decision
        routing_info = "MINI MODEL" if use_mini else "FULL MODEL"
        print(f"DEBUG: MODEL ROUTING - Selected: {routing_info} (Prediction: {prediction['requires_actions']}, Reason: {prediction['reason']})")
    else:
        # Use full model (default behavior or validation retry)
        if validation_retry_count > 0:
            print(f"DEBUG: MODEL ROUTING - VALIDATION RETRY {validation_retry_count}: Using FULL MODEL")
        else:
            print(f"DEBUG: MODEL ROUTING - Intelligent routing disabled, using FULL MODEL")
    
    # Honesty: capture_and_fanout() overrides the per-callsite model to the registry
    # binding (resolve_callsite_config) BEFORE the real API call, so the model that
    # ACTUALLY runs is the registry's T067 model -- not the config.DM_*_MODEL tier
    # string (which set_provider() rewrites to a bare gpt-5.2/gpt-5-mini). Log the
    # real model; use_mini is preserved separately as the routing signal.
    try:
        from model_config import MODEL_PROVIDER as _mp, resolve_callsite_config as _resolve_cfg
        selected_model = _resolve_cfg("T067", _mp)["model"]
    except Exception:
        selected_model = config.DM_FULL_MODEL

    # Track model selection decision for quality control
    print(f"DEBUG: Logging model selection - model={selected_model}, retry={validation_retry_count}")
    try:
        import json  # Ensure json is available in this scope
        os.makedirs("debug/quality_control", exist_ok=True)
        model_selection_record = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input[:200],  # First 200 chars
            "prediction": prediction if validation_retry_count == 0 and not has_module_creation_prompt else None,
            "selected_model": selected_model,
            "routing_use_mini": use_mini,
            "routing_reason": prediction.get("reason", "Validation retry or module creation") if validation_retry_count == 0 else f"Validation retry {validation_retry_count}",
            "validation_retry_count": validation_retry_count,
            "has_module_creation_prompt": has_module_creation_prompt,
            "intelligent_routing_enabled": config.ENABLE_INTELLIGENT_ROUTING
        }
        
        # Append to model selection log (locked single-line write, #214)
        from utils.api_logger import append_jsonl_record
        append_jsonl_record(
            "debug/quality_control/model_selection.jsonl",
            model_selection_record,
        )
    except Exception as e:
        print(f"ERROR: Failed to log model selection: {e}")
        debug(f"Failed to log model selection: {e}", category="ai_routing")
    
    # Check if compression is enabled and apply if needed
    temp_file = None
    try:
        from model_config import COMPRESSION_ENABLED
        if COMPRESSION_ENABLED:
            # Use our parallel compressor with caching
            from utils.compression.conversation_compressor_parallel import ParallelConversationCompressor
            import json
            from pathlib import Path
            from tempfile import NamedTemporaryFile

            # A request-unique closed file prevents parallel turns from
            # overwriting or deleting one another's compression input.
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="neq-main-conversation-",
                suffix=".json",
                delete=False,
            ) as f:
                json.dump(conversation_history, f, indent=2, ensure_ascii=False)
                temp_file = Path(f.name)
            
            # Compress using our working compressor with settings from config
            # Pass the module creation flag to the compressor (now a global variable)
            compressor = ParallelConversationCompressor(
                inject_module_creation=should_inject_creation_prompt,
                detached_context=detached_context,
            )
            messages_to_send = compressor.process_conversation_history(str(temp_file))
            
            print(f"DEBUG: Parallel compression applied successfully")
        else:
            messages_to_send = conversation_history
    except Exception as e:
        # If compression fails, use original history
        print(f"WARNING: Compression failed: {e}")
        status_manager.emit_compression_event('compression_error', {'error': str(e)})
        messages_to_send = conversation_history
    finally:
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError as cleanup_error:
                print(f"WARNING: Could not remove compression input: {cleanup_error}")
    
    # Export main conversation messages for debugging. Suppressed for the
    # detached welcome (#214): this is a fixed-path overwrite that would race
    # a concurrent player turn; the api master log still captures the request.
    if not detached_context:
        with open("main_conversation_messages_to_api.json", "w", encoding="utf-8") as f:
            json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
        print(f"DEBUG: [MAIN CONVERSATION] Exported conversation messages to main_conversation_messages_to_api.json")
    
    # Generate response with selected model (unified path -- provider-agnostic).
    # NOTE: the actual model is selected_config["model"] below, chosen by the use_mini
    # routing boolean. (The old "escalate to full model after 4 retries" reassignment
    # of selected_model was removed: it only changed the LOGGED model name, never the
    # real call, and contradicted the no-escalation-ladder rule.)
    from model_config import MODEL_PROVIDER

    # Select per-provider model config (model string + provider-specific params)
    if MODEL_PROVIDER == "openai":
        full_config = config.DM_FULL_MODEL_GPT52_NONE
        mini_config = config.DM_MINI_MODEL_GPT5MINI_LOW
    elif MODEL_PROVIDER == "gemini":
        full_config = config.DM_FULL_MODEL_GEMINI_PRO_LOW
        mini_config = config.DM_MINI_MODEL_GEMINI_FLASH_LOW
    elif MODEL_PROVIDER == "lmstudio":
        full_config = config.DM_FULL_MODEL_LMSTUDIO
        mini_config = config.DM_MINI_MODEL_LMSTUDIO
    else:  # legacy
        full_config = config.DM_FULL_MODEL_LEGACY
        mini_config = config.DM_MINI_MODEL_LEGACY

    # HIGH-1: select by the boolean routing decision, not a snapshot string
    # compare (which breaks when set_provider() rewrites config.DM_MINI_MODEL).
    if use_mini:
        selected_config = mini_config
    else:
        selected_config = full_config

    print(f"DEBUG: [MAIN.PY] Using model: {selected_config['model']} (provider: {MODEL_PROVIDER})")
    detached_t067_kwargs = {}
    if detached_context:
        # #214 stale-result fence (early-out, correctly NOT cancellation):
        # skip the final call when the welcome was already superseded.
        _welcome_scope = detached_context.get("scope")
        if _welcome_scope is not None and _welcome_scope.is_superseded():
            from utils.capture.live_provider_call import LiveProviderSuperseded
            raise LiveProviderSuperseded("startup welcome superseded")
        detached_t067_kwargs = {
            "_detached_scope": detached_context.get("scope"),
            "_detached_status": detached_context.get("status"),
        }
    response = capture_and_fanout("T067", api_client.create_completion,
        _request_provider=MODEL_PROVIDER,
        _live_selected=live_selected,
        messages=messages_to_send,
        model=selected_config["model"],
        temperature=TEMPERATURE,
        **detached_t067_kwargs,
        **{k: v for k, v in selected_config.items() if k != "model"})

    # Log API call to master log
    try:
        from utils.api_logger import log_api_call
        log_api_call("main_dm", messages_to_send, response,
                    metadata={"temperature": TEMPERATURE, "retry_count": validation_retry_count, "provider": MODEL_PROVIDER})
    except Exception as e:
        print(f"[API_LOG] Warning: Failed to log main DM call: {e}")

    # Track token usage with context for telemetry
    if USAGE_TRACKING_AVAILABLE:
        try:
            from utils.openai_usage_tracker import get_global_tracker
            tracker = get_global_tracker()
            tracker.track(response, context={'endpoint': 'main_dm', 'purpose': 'primary_game_response', 'model': getattr(response, "model", None) or selected_model})
        except:
            pass
    content = response.choices[0].message.content.strip()
    
    # Extract actual actions from the response for accuracy tracking (only on initial attempt)
    if validation_retry_count == 0:
        actual_actions = extract_actual_actions(content)
        # Log prediction accuracy
        log_prediction_accuracy(user_input, prediction, actual_actions)
        
        # Track model selection result for quality control
        try:
            # Update the model selection record with actual outcome
            model_result_record = {
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input[:200],
                "selected_model": getattr(response, "model", None) or selected_model,
                "prediction": prediction,
                "actual_actions": actual_actions,
                "prediction_correct": bool(actual_actions) == prediction["requires_actions"],
                "response_length": len(content)
            }
            
            # Append to model results log (locked single-line write, #214)
            from utils.api_logger import append_jsonl_record
            append_jsonl_record(
                "debug/quality_control/model_results.jsonl",
                model_result_record,
            )
        except Exception as e:
            debug(f"Failed to log model result: {e}", category="ai_routing")
    
    # The sanitization line that was here has been removed.
    # We now pass the raw, untouched JSON string to the next function.
    
    # Log training data - complete conversation history and AI response
    # DISABLED: Training data collection
    # try:
    #     log_complete_interaction(conversation_history, content)
    # except Exception as e:
    #     print(f"Warning: Could not log training data: {e}")
    
    return content


def get_ai_response(
    conversation_history,
    validation_retry_count=0,
    *,
    npc_voice_batch=None,
):
    """Legacy synchronous T067 path used outside the live player-turn seam."""
    return _get_ai_response_impl(
        conversation_history,
        validation_retry_count=validation_retry_count,
        npc_voice_batch=npc_voice_batch,
        prepare_history=True,
        live_selected=False,
    )


def _get_live_ai_response(
    prepared_request_history,
    validation_retry_count=0,
    *,
    npc_voice_batch=None,
):
    """Send an already-prepared, detached outer-turn T067 request."""
    return _get_ai_response_impl(
        prepared_request_history,
        validation_retry_count=validation_retry_count,
        npc_voice_batch=npc_voice_batch,
        prepare_history=False,
        live_selected=True,
    )

def ensure_main_system_prompt(conversation_history, main_system_prompt_text):
    """
    Ensure the main system prompt is first in the conversation history.
    This removes any existing instances of the main prompt and adds it at the beginning.
    """
    # Remove all existing system prompts that appear to be the main system prompt
    # We'll identify the main system prompt by checking if it starts with the first few words
    # of the actual system prompt content
    main_prompt_start = main_system_prompt_text[:50]  # First 50 characters as identifier
    
    # Also check for old format system prompts that we want to remove
    old_prompt_identifiers = [
        "These are Ashiralis's Sowhains' game rules",
        "## Section 1: Core Foundation"  # In case the old format started differently
    ]
    
    # Filter out any system message that matches our criteria
    filtered_history = []
    for msg in conversation_history:
        if msg["role"] == "system":
            # Check if it's the current main prompt
            if msg["content"].startswith(main_prompt_start):
                continue  # Skip this message as it's our current main system prompt
            # Check if it's an old format prompt
            if any(msg["content"].startswith(old_id) for old_id in old_prompt_identifiers):
                debug(f"Removing old format system prompt starting with: {msg['content'][:50]}...", category="conversation_management")
                continue  # Skip old format prompts
        filtered_history.append(msg)
    
    # Always place the main system prompt at the beginning
    return [{"role": "system", "content": main_system_prompt_text}] + filtered_history

def order_conversation_messages(conversation_history, main_system_prompt_text):
    """Order conversation messages with main system prompt first, followed by other system prompts"""
    main_prompt = None
    other_system_prompts = []
    non_system_messages = []

    for msg in conversation_history:
        if msg["role"] == "system":
            if msg["content"].startswith(main_system_prompt_text[:50]):
                main_prompt = msg
            else:
                other_system_prompts.append(msg)
        else:
            non_system_messages.append(msg)

    # Reconstruct with proper order
    ordered_history = []
    if main_prompt:
        ordered_history.append(main_prompt)
    ordered_history.extend(other_system_prompts)
    ordered_history.extend(non_system_messages)
    
    return ordered_history

def check_all_modules_plot_completion():
    """
    Check plot completion status for ALL available modules, not just the current one.
    Returns a dictionary with completion data for all modules.
    """
    import os
    import glob
    
    # Comprehensive module plot completion check (verbose logging removed)
    
    modules_dir = "modules"
    all_modules_data = {
        "modules_checked": [],
        "all_complete": True,
        "completion_summary": {}
    }
    
    if not os.path.exists(modules_dir):
        warning("FILE_OP: No modules directory found", category="module_management")
        return all_modules_data
    
    # Find all valid module directories
    available_modules = []
    for item in os.listdir(modules_dir):
        module_path = os.path.join(modules_dir, item)
        if os.path.isdir(module_path) and not item.startswith('.') and item not in ['campaign_archives', 'campaign_summaries']:
            # Check if this directory has area JSON files (indicating it's a valid module)
            area_files = []
            
            # Check root directory (legacy structure)
            try:
                root_area_files = [f for f in os.listdir(module_path) 
                                 if os.path.isfile(os.path.join(module_path, f)) 
                                 and f.endswith('.json') 
                                 and len(f.split('.')[0]) <= 7  # Area codes like HH001, G001, SR001
                                 and not f.startswith('map_') 
                                 and not f.startswith('plot_')
                                 and not f.startswith('party_')
                                 and not f.startswith('module_')
                                 and f not in ['campaign.json', 'world_registry.json', 'module_context.json']]
                area_files.extend(root_area_files)
            except Exception as e:
                error(f"FAILURE: Error checking root area files for {item}", exception=e, category="module_management")
            
            # Check areas/ subdirectory (new structure)
            areas_subdir = os.path.join(module_path, 'areas')
            if os.path.exists(areas_subdir) and os.path.isdir(areas_subdir):
                try:
                    subdir_area_files = [f for f in os.listdir(areas_subdir) 
                                       if os.path.isfile(os.path.join(areas_subdir, f)) 
                                       and f.endswith('.json') 
                                       and len(f.split('.')[0]) <= 7  # Area codes
                                       and not f.startswith('map_') 
                                       and not f.startswith('plot_')
                                       and not f.startswith('party_')
                                       and not f.startswith('module_')]
                    area_files.extend(subdir_area_files)
                except Exception as e:
                    error(f"FAILURE: Error checking areas subdirectory for {item}", exception=e, category="module_management")
            
            if area_files:
                available_modules.append(item)
    
    # Found modules: {available_modules} (consolidated logging)
    
    # Check plot completion for each module
    for module_name in available_modules:
        module_path_manager = ModulePathManager(module_name)
        plot_file_path = module_path_manager.get_plot_path()
        
        # Checking plot completion for module '{module_name}' at {plot_file_path}
        
        try:
            plot_data = load_json_file(plot_file_path)
            
            if plot_data and "plotPoints" in plot_data:
                # Only count main plot points (PP), not side quests (SQ)
                main_plots = [p for p in plot_data["plotPoints"] if p.get("id", "").startswith("PP")]
                total_plots = len(main_plots)
                completed_plots = 0
                
                for plot_point in main_plots:
                    status = plot_point.get("status", "unknown")
                    plot_id = plot_point.get("id", "unknown")
                    
                    if status == "completed":
                        completed_plots += 1
                
                # Module is complete when all main plots (PP) are done, side quests (SQ) are optional
                module_complete = completed_plots == total_plots and total_plots > 0
                
                all_modules_data["completion_summary"][module_name] = {
                    "total_plots": total_plots,
                    "completed_plots": completed_plots,
                    "is_complete": module_complete,
                    "plot_file_exists": True
                }
                
                if not module_complete:
                    all_modules_data["all_complete"] = False
                
                # Module {module_name} completion: {completed_plots}/{total_plots} ({module_complete})
                
            else:
                debug(f"STATE_CHANGE: Module {module_name} has no plot data or plotPoints", category="module_management")
                all_modules_data["completion_summary"][module_name] = {
                    "total_plots": 0,
                    "completed_plots": 0,
                    "is_complete": False,
                    "plot_file_exists": False
                }
                all_modules_data["all_complete"] = False
                
        except Exception as e:
            error(f"FAILURE: Error loading plot data for module {module_name}", exception=e, category="module_management")
            all_modules_data["completion_summary"][module_name] = {
                "total_plots": 0,
                "completed_plots": 0,
                "is_complete": False,
                "plot_file_exists": False,
                "error": str(e)
            }
            all_modules_data["all_complete"] = False
    
    all_modules_data["modules_checked"] = available_modules
    
    # Module completion check: {len(available_modules)} modules, all complete: {all_modules_data['all_complete']}
    
    return all_modules_data

def main_game_loop():
    global needs_conversation_history_update, should_inject_creation_prompt

    # Ensure debug directories and files exist
    import os
    os.makedirs("debug/logs", exist_ok=True)
    os.makedirs("debug/api_captures", exist_ok=True)
    os.makedirs("debug/combat", exist_ok=True)

    # Create prompt_validation.json if it doesn't exist
    if not os.path.exists("debug/logs/prompt_validation.json"):
        with open("debug/logs/prompt_validation.json", "w") as f:
            f.write("[]")  # Initialize with empty array

    # Issue #167 / E2E gate 2d: hydrate missing live module files from their _BU
    # masters on EVERY boot, not just new-game setup. The web entry runs this loop
    # directly (web_interface.py:run_game_loop), and its existing-party path
    # (startup_required() == False) otherwise never hydrates -- so an existing
    # party that lost an area file (or a game copied without runtime files) booted
    # into missing state that cached narration masked. main()/the wizard already
    # call this on their paths; doing it here covers the web existing-party boot
    # too. Idempotent (only-if-missing), guarded (never overwrites live files).
    try:
        from utils.startup_wizard import initialize_game_files_from_bu
        initialize_game_files_from_bu()
    except Exception as e:
        debug(f"Startup module hydration skipped (non-fatal): {e}", category="startup")

    # Initialize companion memories from journal if needed
    try:
        from core.memories.initialize_memories import check_and_initialize_on_startup
        check_and_initialize_on_startup()
    except Exception as e:
        debug(f"Could not initialize memories (non-fatal): {e}", category="startup")

    # Reset startup state for this session. The lease file persists "kickoff_done"
    # from the previous session, which causes claim_kickoff_lease() to return
    # "already_done" and skip process_ai_response() entirely. Resetting here
    # ensures the kickoff runs fresh each time the game starts.
    issue_new_attempt_id()

    startup_state = load_startup_state()
    emit_startup_marker(
        "startup_handoff_begin",
        source="normal",
        result="begin",
        startup_attempt_id=startup_state.get("startup_attempt_id"),
        state_version=startup_state.get("state_version"),
        lease_owner=startup_state.get("lease_owner"),
        attempt_count=startup_state.get("attempt_count"),
    )

    # Check if first-time setup is needed
    try:
        from utils.startup_wizard import startup_required, run_startup_sequence

        if startup_required():
            print("[D20] Welcome to your 5th Edition Adventure! [D20]")
            print("It looks like this is your first time, or you need to set up a character.")
            print("Let's get you ready for adventure!\n")

            success = run_startup_sequence()
            if not success:
                print("[ERROR] Setup was cancelled or failed. Cannot start game loop.")
                return
            wizard_state = mark_wizard_complete().get("state", load_startup_state())
            emit_startup_marker(
                "startup_wizard_complete",
                source="normal",
                result="updated",
                startup_attempt_id=wizard_state.get("startup_attempt_id"),
                state_version=wizard_state.get("state_version"),
                lease_owner=wizard_state.get("lease_owner"),
                attempt_count=wizard_state.get("attempt_count"),
            )
        else:
            party_data = load_json_file("party_tracker.json") or {}
            has_character_data = bool(party_data.get("module")) and bool(party_data.get("partyMembers"))

            # === LEGACY CHARACTER REPAIR ===
            # Repair and persist any missing fields in party member character files
            # This ensures players updating their game code don't hit broken bugs
            if has_character_data:
                repair_path_manager = ModulePathManager(party_data.get("module", ""))
                for member_name in party_data.get("partyMembers", []):
                    member_file = repair_path_manager.get_character_path(member_name)
                    result = repair_and_persist_character(member_file, character_type="player")
                    if result:
                        _, repairs = result
                        if repairs:
                            debug(
                                f"STARTUP_REPAIR: Fixed legacy character {member_name}: {', '.join(repairs)}",
                                category="startup",
                            )

                # Also repair party NPCs
                for npc_info in party_data.get("partyNPCs", []):
                    npc_name = npc_info.get("name", "") if isinstance(npc_info, dict) else str(npc_info)
                    if npc_name:
                        npc_file = repair_path_manager.get_character_path(npc_name)
                        result = repair_and_persist_character(npc_file, character_type="npc")
                        if result:
                            _, repairs = result
                            if repairs:
                                debug(
                                    f"STARTUP_REPAIR: Fixed legacy NPC {npc_name}: {', '.join(repairs)}",
                                    category="startup",
                                )
            # === END LEGACY CHARACTER REPAIR ===

            sync_result = sync_wizard_completion(has_character_data)
            synced_state = sync_result.get("state", load_startup_state())
            emit_startup_marker(
                "startup_wizard_sync",
                source="normal",
                result=sync_result.get("status", "unknown"),
                startup_attempt_id=synced_state.get("startup_attempt_id"),
                state_version=synced_state.get("state_version"),
                lease_owner=synced_state.get("lease_owner"),
                attempt_count=synced_state.get("attempt_count"),
            )
    except Exception as e:
        error(f"FAILURE: Startup wizard failed", exception=e, category="startup")
        return

    # A cross-module party/location transition can be durable before its
    # T038/T039 completion finishes. Resolve that intent before *any* startup
    # narration or campaign-context construction (normal terminal and web both
    # enter through this loop). If recovery cannot finish, fail closed instead
    # of displaying a first response built from the stale campaign projection.
    try:
        startup_drain = require_staged_module_completions_drained()
        if startup_drain["completed"] or startup_drain["cancelled"]:
            debug(
                f"STATE_CHANGE: Startup module-completion drain: {startup_drain}",
                category="startup",
            )
    except Exception as drain_exc:
        error(
            "FAILURE: Startup stopped before AI response because module "
            "completion recovery is unresolved",
            exception=drain_exc,
            category="startup",
        )
        return

    # --- START: COMBAT RESUMPTION LOGIC ---
    party_tracker_data = load_json_file("party_tracker.json")
    combat_was_resumed = False  # Track if we resumed from combat

    # Initialize variables needed in main loop for both paths (combat resume and normal startup)
    module_name = party_tracker_data.get("module", "").replace(" ", "_") if party_tracker_data else ""
    path_manager = ModulePathManager(module_name)
    debug(f"INITIALIZATION: Path manager initialized for module: '{module_name}'", category="module_management")

    # Convert legacy effect bookkeeping once, before combat resume or any new
    # model context is built. Active combat is a deliberate safe-boundary
    # deferral; a partially applied journal must recover before play continues.
    try:
        from core.managers.effects_migration import run_effects_migration

        effects_migration = run_effects_migration(create_backup=True)
        if effects_migration.get("status") == "migrated":
            print(
                "[SYSTEM] Temporary effects were upgraded safely. "
                "A pre-conversion save was created automatically."
            )
            debug(
                f"EFFECTS: Effects V2 migration completed: {effects_migration}",
                category="effects_tracking",
            )
        elif effects_migration.get("status") == "blocked":
            warning(
                f"EFFECTS: Automatic conversion was refused safely: {effects_migration}",
                category="effects_tracking",
            )
            print(
                "[SYSTEM] Temporary-effect conversion needs review. "
                "The campaign remains on its legacy effect handling for this session."
            )
    except Exception as effects_migration_exc:
        error(
            "FAILURE: Effects conversion/recovery did not reach a safe boundary",
            exception=effects_migration_exc,
            category="effects_tracking",
        )
        backup_folder = None
        try:
            from core.managers.effects_state import load_effects_state

            backup_folder = (
                (load_effects_state().get("migration") or {}).get("backupFolder")
            )
        except Exception:
            pass
        recovery = (
            f" Restore save '{backup_folder}' before retrying."
            if backup_folder
            else " Retry startup; if it repeats, restore the automatic pre-conversion save."
        )
        print(
            "[SYSTEM] Startup stopped because temporary-effect conversion "
            "could not be recovered safely." + recovery
        )
        return

    # Reload global location_graph to ensure it's current for the active module
    global location_graph
    print("DEBUG: [LocationGraph] Reloading location graph for current module...")
    location_graph = LocationGraph()
    location_graph.load_module_data()
    print(f"DEBUG: [LocationGraph] Reload complete. Total nodes: {len(location_graph.nodes)}, Total edges: {sum(len(edges) for edges in location_graph.edges.values())}")
    debug(f"INITIALIZATION: Location graph reloaded with {len(location_graph.nodes)} nodes", category="module_management")

    # A within-module move can commit before its marker or T013 narration is
    # saved. Close that gap before combat resumption, return narration, or any
    # new provider request. Recovery is deterministic and never moves twice.
    try:
        pending_history = load_json_file(json_file) or []
        pending_transition_recovery = (
            action_handler.recover_pending_location_transition(
                party_tracker_data, pending_history
            )
        )
        if pending_transition_recovery.get("status") == "blocked":
            # [travel #210] The interrupted transition is un-appliable (party
            # state matches neither its origin/destination nor a staged module
            # projection). recover() has already retired the residue. Startup is
            # a play path (B1): never engine_stop here -- surface a player-facing
            # notice and fall through to the playable loop at the authoritative
            # party location, where the player can continue or load a save.
            world = (party_tracker_data or {}).get("worldConditions", {}) or {}
            here = (
                world.get("currentLocation")
                or world.get("currentLocationId")
                or "where you are"
            )
            warning(
                "Interrupted location transition could not be auto-completed; "
                "the un-appliable record was discarded and startup continues "
                "from the authoritative party location. reason=%s"
                % pending_transition_recovery.get("reason"),
                category="location_transitions",
            )
            # Player-visible in web + headless + terminal: the DM narration
            # section is the only cross-mode player output surface (a bare
            # "[SYSTEM]" line would route to the debug stream). Register is an
            # owner decision (D-210-2); the out-of-fiction channel is issue #212.
            print(
                "Dungeon Master: A prior travel action didn't finish cleanly, "
                "so you remain where the party actually stands - %s. You can "
                "continue from here, or load an earlier save to redo that "
                "journey." % here
            )
            # [travel #210] Flush so the DM-narration section is emitted and
            # CLOSED before the next startup diagnostic line, which would
            # otherwise be absorbed into this notice's narration block. Guarded
            # like emit_startup_marker's flush so a broken/closed terminal pipe
            # cannot raise into the boot except-branch and abort startup.
            try:
                sys.stdout.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass
            # fall through: boot into the normal playable loop (no engine_stop)
        if pending_transition_recovery.get("status") == "recovered":
            if pending_transition_recovery.get(
                "deferred_actions_not_replayed"
            ):
                warning(
                    "Startup recovered transition narration but did not "
                    "replay non-idempotent deferred actions",
                    category="location_transitions",
                )
            debug(
                "STATE_CHANGE: Recovered interrupted within-module transition",
                category="location_transitions",
            )
    except Exception as transition_recovery_exc:
        error(
            "FAILURE: Startup stopped before AI response because location "
            "transition recovery is unresolved",
            exception=transition_recovery_exc,
            category="location_transitions",
        )
        return
    
    # Load validation prompt for both paths - needed in main loop
    validation_prompt_text = load_validation_prompt()
    debug("INITIALIZATION: Validation prompt loaded for both paths", category="initialization")
    
    # Load main system prompt for both paths - also needed in main loop
    with open("prompts/system_prompt.txt", "r", encoding="utf-8") as file:
        main_system_prompt_text = file.read()
    debug("INITIALIZATION: Main system prompt loaded for both paths", category="initialization")
    
    if party_tracker_data and party_tracker_data["worldConditions"].get("activeCombatEncounter"):
        active_encounter_id = party_tracker_data["worldConditions"]["activeCombatEncounter"]
        print(colored(f"[SYSTEM] Active combat encounter '{active_encounter_id}' detected. Resuming combat...", "yellow"))
        combat_was_resumed = True  # Mark that we're resuming from combat
        
        # Load conversation history and inject combat resume markers BEFORE starting combat
        conversation_history = load_json_file(json_file) or []
        
        # Inject combat recovery tracking messages
        tracking_message = {
            "role": "user",
            "content": "[SYSTEM: Combat was interrupted and is being resumed from crash]"
        }
        conversation_history.append(tracking_message)
        
        recovery_marker = {
            "role": "assistant",
            "content": "[SYSTEM: Combat recovery initiated - continuing from last known state]"
        }
        conversation_history.append(recovery_marker)
        
        # Save the updated conversation history
        save_conversation_history(conversation_history)
        debug("STATE_CHANGE: Added combat resume tracking messages before combat restart", category="session_management")
        
        # Directly get location info for the combat manager
        current_area_id_resume = party_tracker_data["worldConditions"]["currentAreaId"]
        location_data_resume = location_manager.get_location_info(
            party_tracker_data["worldConditions"]["currentLocation"],
            party_tracker_data["worldConditions"]["currentArea"],
            current_area_id_resume
        )

        # Call run_combat_simulation directly to get the return values
        from core.managers.combat_manager import run_combat_simulation
        dialogue_summary, _ = run_combat_simulation(active_encounter_id, party_tracker_data, location_data_resume)

        # After combat, reload everything to ensure state is fresh
        party_tracker_data = load_json_file("party_tracker.json")
        conversation_history = load_json_file(json_file) or []
        combat_still_active = (
            isinstance(party_tracker_data, dict)
            and (party_tracker_data.get("worldConditions") or {}).get(
                "activeCombatEncounter"
            ) == active_encounter_id
        )
        if combat_still_active:
            recovery = _active_combat_recovery(party_tracker_data)
            if recovery:
                display_dm_narration(
                    "Combat remains paused. Load or restore a save before "
                    "resuming encounter %s; no post-combat narration was "
                    "requested." % active_encounter_id,
                    channel="combat",
                    color="yellow",
                )
            else:
                display_dm_narration(
                    "Combat did not reach a confirmed completion state. "
                    "The active encounter was preserved for recovery and "
                    "no post-combat narration was requested.",
                    channel="combat",
                    color="yellow",
                )
        else:
            print(colored(
                "[SYSTEM] Combat resolved. Integrating summary and "
                "continuing adventure...",
                "yellow",
            ))

        # ** CRITICAL FIX: Integrate the combat summary into the main conversation history **
        if dialogue_summary and not combat_still_active:
            # We create a clear, systemic message indicating combat is over.
            # This mimics the handoff from action_handler.
            combat_summary_message = (
                "[COMBAT CONCLUDED] The encounter has ended. The following "
                "is a summary of events:\n\n%s\n\nIMPORTANT: This historical "
                "summary describes changes already applied by the combat "
                "system. Do not re-emit updateCharacterInfo actions for them."
                % dialogue_summary
            )
            conversation_history.append({"role": "user", "content": combat_summary_message})
            debug("STATE_CHANGE: Appended combat summary to main history after resumed session.", category="session_management")
            save_conversation_history(conversation_history)

        # ** CRITICAL FIX: Get a new AI response for post-combat narration **
        # This makes the resumed flow behave exactly like the normal flow.
        ai_response_after_combat = (
            None
            if combat_still_active
            else get_ai_response(conversation_history)
        )
        if ai_response_after_combat:
            # Process the AI's post-combat response to get the game moving again.
            # We need to load the fresh location data for this call.
            current_area_id_post_combat = party_tracker_data["worldConditions"]["currentAreaId"]
            location_data_post_combat = location_manager.get_location_info(
                party_tracker_data["worldConditions"]["currentLocation"],
                party_tracker_data["worldConditions"]["currentArea"],
                current_area_id_post_combat
            )
            # Match the uninterrupted-combat handoff: the committed combat
            # state owns HP/XP, so the immediate narration pass must not
            # reapply a model-authored echo after reconnect recovery.
            process_ai_response._just_finished_combat = True
            post_combat_result = process_ai_response(
                ai_response_after_combat,
                party_tracker_data,
                location_data_post_combat,
                conversation_history,
            )
            (
                post_combat_result,
                party_tracker_data,
                location_data_post_combat,
                conversation_history,
            ) = resolve_retryable_ai_result(
                post_combat_result,
                party_tracker_data,
                location_data_post_combat,
                conversation_history,
            )
            if (
                isinstance(post_combat_result, dict)
                and (
                    post_combat_result.get("retryable") is True
                    or post_combat_result.get("status") == "error"
                )
            ):
                retry_status = post_combat_result.get(
                    "status", "state_recovery_pending"
                )
                print(
                    "[SYSTEM] Post-combat narration is paused while game "
                    f"state recovers ({retry_status})."
                )
                warning(
                    f"Post-combat response processing paused: {retry_status}",
                    category="module_management",
                )
        
        print("[DEBUG] Combat resumption complete - should enter main game loop now")
        debug("CRITICAL: Combat resumption complete - attempting to enter main loop", category="session_management")
        
    # --- END: COMBAT RESUMPTION LOGIC ---
    else:
        # print("[DEBUG] Normal startup path - will enter main game loop")
        # Normal game loop (when not resuming from combat)
        # validation_prompt_text and main_system_prompt_text already loaded above for both paths 

        conversation_history = load_json_file(json_file) or []
    
        # CRITICAL: Check and inject return message BEFORE any processing
        # Don't inject if we already did it for combat resume
        was_injected = False  # Initialize to track if we generated a response for return message
        if not combat_was_resumed:
            # [travel #210] Name the authoritative current location in the resume
            # note so the welcome-back narrates THIS location, not a stale one
            # inferred from interrupted-turn history. Read the post-recovery
            # party_tracker (discard recovery above does not mutate it); degrade
            # to omit the clause if any field is missing (never raise at boot).
            resume_location_note = ""
            try:
                _pt_now = load_json_file("party_tracker.json") or {}
                _wc = (_pt_now.get("worldConditions") or {}) if isinstance(_pt_now, dict) else {}
                _loc_name = _wc.get("currentLocation")
                _loc_id = _wc.get("currentLocationId")
                _area_name = _wc.get("currentArea")
                if _loc_name and _loc_id:
                    _area_frag = (" in the %s area" % _area_name) if _area_name else ""
                    resume_location_note = (
                        "The party is currently at %s (%s)%s -- recap and narrate "
                        "THIS location and situation; refer to the location by name "
                        "in the narration; do not treat any earlier location in the "
                        "history as current. " % (_loc_name, _loc_id, _area_frag)
                    )
            except Exception:
                resume_location_note = ""
            conversation_history, was_injected = check_and_inject_return_message(
                conversation_history, is_combat_active=False,
                location_note=resume_location_note)
            if was_injected:
                save_conversation_history(conversation_history)
                # The leased kickoff generates from the fully reconciled and
                # rebuilt context below. An early provider call here would be
                # stale by the time campaign/location context is enriched.
                debug(
                    "STATE_CHANGE: Return message queued for leased kickoff",
                    category="startup",
                )
    
        party_tracker_data = load_json_file("party_tracker.json")
    
        # Verify party tracker loaded successfully
        if not party_tracker_data:
            print("[ERROR] Party tracker not found after setup. Something went wrong.")
            return

        # Reconcile startup-critical state before building conversation context.
        try:
            reconcile_result = reconcile_campaign_state()
            debug(f"STATE_CHANGE: reconcile_campaign_state result: {reconcile_result}", category="startup")
        except Exception as reconcile_exc:
            warning(f"INITIALIZATION: reconcile_campaign_state failed: {reconcile_exc}", category="startup")
    
        # Path manager already initialized above for both paths
        # Just verify it's using the correct module
        debug(f"INITIALIZATION: Path manager already initialized - module_name: '{path_manager.module_name}', module_dir: '{path_manager.module_dir}'", category="module_management")
    
        location_data = get_location_data_from_party_tracker(party_tracker_data)

        # Use current module from party tracker for plot data  
        current_module_name = party_tracker_data.get("module", "").replace(" ", "_")
        current_path_manager = ModulePathManager(current_module_name)
        plot_data = load_json_file(current_path_manager.get_plot_path())
        debug(f"FILE_OP: Plot file path: {current_path_manager.get_plot_path()}", category="module_management")
    
        module_data = load_json_file(current_path_manager.get_module_file_path())

        # CRITICAL: Reload party_tracker to get latest data after module integration
        # Module stitcher may have updated location IDs during integration
        party_tracker_data = load_json_file("party_tracker.json")
        print(f"DEBUG: [Before first update_conversation_history] Reloaded party tracker after integration. Location: {party_tracker_data.get('worldConditions', {}).get('currentLocationId', 'Unknown')}")

        location_data = get_location_data_from_party_tracker(party_tracker_data)

        conversation_history = ensure_main_system_prompt(conversation_history, main_system_prompt_text)
        debug(f"STATE_CHANGE: Before update_conversation_history - history has {len(conversation_history)} messages", category="conversation_management")
        context_state = load_startup_state()
        emit_startup_marker(
            "startup_context_built",
            source="normal",
            result="pre_update_conversation_history",
            startup_attempt_id=context_state.get("startup_attempt_id"),
            state_version=context_state.get("state_version"),
            lease_owner=context_state.get("lease_owner"),
            attempt_count=context_state.get("attempt_count"),
        )
        conversation_history = update_conversation_history(conversation_history, party_tracker_data, plot_data, module_data)
        debug(f"STATE_CHANGE: After update_conversation_history - history has {len(conversation_history)} messages", category="conversation_management")
        conversation_history = update_character_data(conversation_history, party_tracker_data)
    
        # Use the new order_conversation_messages function
        conversation_history = order_conversation_messages(conversation_history, main_system_prompt_text)
    
        # Old-format repair is intentionally deferred until the first real
        # prompt opens the cancellable player-turn scope. Startup must never
        # hide an unbounded provider call before Save/Load/Reset are reachable.
        save_conversation_history(conversation_history)

        # Exactly-once kickoff with recovery; process precomputed return-response if present.
        kickoff_result = run_startup_kickoff_with_recovery(
            conversation_history,
            party_tracker_data,
            location_data,
        )
        if kickoff_result.get("status") != "done":
            warning(
                f"INITIALIZATION: Startup kickoff did not complete cleanly: {kickoff_result}",
                category="startup",
            )

    # Add safeguard against infinite loops in non-interactive environments
    empty_input_count = 0
    max_empty_inputs = 5
    
    print("[DEBUG] ENTERING MAIN GAME LOOP - while True")
    if combat_was_resumed:
        print("[DEBUG] SUCCESS: Main loop reached after combat resumption!")
        debug("SUCCESS: Main game loop reached after combat resumption", category="session_management")
    while True:
        print("[DEBUG] Top of main game loop iteration")
        conversation_history = truncate_dm_notes(conversation_history)
        conversation_history = remove_duplicate_messages(conversation_history)

        if needs_conversation_history_update:
            debug("STATE_CHANGE: Reloading conversation history from disk due to needs_conversation_history_update flag", category="conversation_management")
            # A safe action message that failed to persist is newer than disk.
            # Retry its strict save before permitting any reload to replace it.
            conversation_history = _reload_conversation_history_if_safe(
                conversation_history
            )
            # CRITICAL: Also reload party tracker to get the latest module information
            party_tracker_data = load_json_file("party_tracker.json")
            print(f"DEBUG: [Main Loop] Reloaded party tracker after update. Module: {party_tracker_data.get('module', 'Unknown')}")
            conversation_history = process_conversation_history(conversation_history)
            conversation_history = remove_duplicate_messages(conversation_history)  # Clean any duplicates
            save_conversation_history(conversation_history)
            needs_conversation_history_update = False

        # DISABLED: Module summary insertion now handled by inject_campaign_summaries with separate system messages
        # conversation_history = check_and_process_module_transitions(conversation_history, party_tracker_data)
        save_conversation_history(conversation_history)
    
        # Retry a safe-boundary migration deferred by active combat, then run
        # deterministic expiry and exactly-once notification delivery.
        try:
            from core.managers.effects_migration import run_effects_migration
            from core.managers.effects_runtime import (
                acknowledge_effect_notifications,
                process_effect_lifecycle,
            )
            from core.managers.effects_state import campaign_effects_migrated

            debug("EFFECTS: Checking for expired effects", category="effects_tracking")
            if not campaign_effects_migrated():
                run_effects_migration(create_backup=True)
            if campaign_effects_migrated():
                acknowledge_effect_notifications(conversation_history)
                effect_notice = process_effect_lifecycle(conversation_history)
                if effect_notice:
                    conversation_history.append(effect_notice)
                    save_conversation_history(
                        conversation_history,
                        strict=True,
                        allow_compression=False,
                    )
                    acknowledge_effect_notifications(conversation_history)
            else:
                from updates.process_effect_expirations import process_all_effect_expirations

                process_all_effect_expirations()
        except Exception as e:
            warning(
                f"EFFECTS: Expiration processing failed safely: {str(e)}",
                category="effects_tracking",
            )


        # Set status to ready before accepting input
        status_ready()

        # Check if stdin is available (prevent infinite loops in non-interactive environments)
        if hasattr(sys.stdin, 'isatty') and not sys.stdin.isatty():
            warning("INITIALIZATION: Running in non-interactive environment. Stdin is not a terminal.", category="startup")
            print("Game loop stopped to prevent infinite empty input cycle.")
            print("To run interactively, ensure the program is run from a proper terminal.")
            break

        # --- Post-Combat State Refresh & UI Display ---
        # This is the core fix. After combat, we MUST reload all data from disk
        # to avoid using stale in-memory data from before the fight.
        if hasattr(process_ai_response, '_just_finished_combat') and process_ai_response._just_finished_combat:
            info("STATE_REFRESH: Post-combat state refresh triggered. Reloading data from disk.", category="game_loop")
            # Reload the party tracker first, as it's the source of truth.
            party_tracker_data = load_json_file("party_tracker.json")
            # Reset the flag so this only runs once per combat.
            process_ai_response._just_finished_combat = False
    
        # Now, get the player's name and load their character file for the UI.
        # This data will now be fresh if a refresh was just triggered.
        player_name_actual = party_tracker_data["partyMembers"][0]
        from updates.update_character_info import normalize_character_name
        player_name_normalized = normalize_character_name(player_name_actual)
        player_data_file = path_manager.get_character_path(player_name_normalized)
        player_data_current = load_json_file(player_data_file)
        if player_data_current:
            player_data_current = _effects_runtime_view(player_data_current)
    
        # Display the prompt with the (now correct) stats.
        if player_data_current:
            current_hp = player_data_current.get("hitPoints", "N/A")
            max_hp = player_data_current.get("maxHitPoints", "N/A")
            current_xp = player_data_current.get("experience_points", "N/A")
            next_level_xp = player_data_current.get("exp_required_for_next_level", "N/A")
            # Get time with context for display
            from utils.time_context import get_time_context
            current_time_str = party_tracker_data["worldConditions"]["time"]
            time_context = get_time_context(current_time_str)
            # Show both time and context in prompt
            time_display = f"{current_time_str[:5]} ({time_context})"  # Show HH:MM (context)
            stats_display = f"{LIGHT_OFF_GREEN}[{time_display}][HP:{current_hp}/{max_hp}][XP:{current_xp}/{next_level_xp}]{RESET_COLOR}"
            player_name_display = f"{SOLID_GREEN}{player_name_actual}{RESET_COLOR}"
            print("[DEBUG] About to show input prompt with stats")
            user_input_text = input(f"{stats_display} {player_name_display}: ")
        else:
            print("[DEBUG] About to show basic input prompt")
            user_input_text = input("User: ")

        # Skip processing if input is empty or only whitespace
        if not user_input_text or not user_input_text.strip():
            continue
        else:
            # Reset counter on valid input
            empty_input_count = 0
    
        party_tracker_data = load_json_file("party_tracker.json") 

        combat_recovery = _active_combat_recovery(party_tracker_data)
        if combat_recovery:
            display_dm_narration(
                "Combat is paused (%s). This input was not sent to the "
                "Dungeon Master. Load or restore a save before resuming "
                "encounter %s."
                % (
                    combat_recovery["reason"],
                    combat_recovery["encounter_id"],
                ),
                channel="combat",
                color="yellow",
            )
            continue

        # Remove duplicate NPCs if any exist
        party_tracker_data, npcs_were_cleaned = remove_duplicate_npcs(party_tracker_data)
        if npcs_were_cleaned:
            # Save the cleaned party tracker back to file
            safe_write_json("party_tracker.json", party_tracker_data)
            debug("FILE_OP: Updated party_tracker.json with duplicate NPCs removed", category="npc_management")

        party_members_stats = []
        for member_name_iter in party_tracker_data["partyMembers"]:
            member_file_path = path_manager.get_character_path(member_name_iter)
            member_data_iter = load_json_file(member_file_path)
            if member_data_iter:
                member_data_iter = _effects_runtime_view(member_data_iter)
                stats = {
                    "name": member_name_iter,  # Keep original case to match file names
                    "display_name": member_name_iter.capitalize(),  # For display purposes
                    "level": member_data_iter.get("level", "N/A"),
                    "xp": member_data_iter.get("experience_points", "N/A"),
                    "hp": member_data_iter.get("hitPoints", "N/A"),
                    "max_hp": member_data_iter.get("maxHitPoints", "N/A")
                }
                party_members_stats.append(stats)

        try:
            for npc_info_iter in party_tracker_data["partyNPCs"]:
                debug(f"STATE_CHANGE: Processing NPC: {npc_info_iter['name']}", category="npc_management")
                npc_name_iter = npc_info_iter["name"]
                npc_data_file = path_manager.get_character_path(npc_name_iter)
                debug(f"FILE_OP: NPC file path: {npc_data_file}", category="npc_management")
                npc_data_iter = load_json_file(npc_data_file)
                debug(f"FILE_OP: NPC data loaded: {npc_data_iter is not None}", category="npc_management")
                if npc_data_iter:
                    npc_data_iter = _effects_runtime_view(npc_data_iter)
                    stats = {
                        "name": npc_info_iter["name"],
                        "display_name": npc_info_iter["name"].capitalize(),  # For display purposes
                        "level": npc_data_iter.get("level", npc_info_iter.get("level", "N/A")),
                        "xp": npc_data_iter.get("experience_points", "N/A"),
                        "hp": npc_data_iter.get("hitPoints", "N/A"),
                        "max_hp": npc_data_iter.get("maxHitPoints", "N/A")
                    }
                    party_members_stats.append(stats)
                    debug(f"STATE_CHANGE: Added NPC stats: {stats}", category="npc_management")
        except Exception as e:
            error(f"FAILURE: Error processing NPCs", exception=e, category="npc_management")
            import traceback
            traceback.print_exc()
    
        # Reload current location_data for the DM note based on party_tracker
        # This ensures location_data is fresh for each DM note construction
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"] 
        location_data = location_manager.get_location_info( 
            party_tracker_data["worldConditions"]["currentLocation"],
            party_tracker_data["worldConditions"]["currentArea"],
            current_area_id
        )

        if party_members_stats:
            world_conditions = party_tracker_data["worldConditions"]
            # Use enhanced time formatting with context
            from utils.time_context import format_time_with_context
            date_time_str = format_time_with_context(world_conditions)
            party_stats_formatted = []
            for stats_item in party_members_stats:
                # Check if this is a player or an NPC
                if stats_item['name'] in party_tracker_data["partyMembers"]:
                    member_data_for_note = load_json_file(path_manager.get_character_path(stats_item['name']))
                else:
                    member_data_for_note = load_json_file(path_manager.get_character_path(stats_item['name']))
                if member_data_for_note:
                    member_data_for_note = _effects_runtime_view(member_data_for_note)
                    abilities = member_data_for_note.get("abilities", {})
                    ability_str = f"STR:{abilities.get('strength', 'N/A')} DEX:{abilities.get('dexterity', 'N/A')} CON:{abilities.get('constitution', 'N/A')} INT:{abilities.get('intelligence', 'N/A')} WIS:{abilities.get('wisdom', 'N/A')} CHA:{abilities.get('charisma', 'N/A')}"
                    next_level_xp_note = member_data_for_note.get("exp_required_for_next_level", "N/A")
                    display_name = stats_item.get('display_name', stats_item['name'].capitalize())
                
                    # Extract spell slot information if character has spellcasting
                    spell_slots_str = ""
                    spellcasting = member_data_for_note.get("spellcasting", {})
                    if spellcasting and "spellSlots" in spellcasting:
                        spell_slots = spellcasting["spellSlots"]
                        slot_parts = []
                        for level in range(1, 10):  # Spell levels 1-9
                            level_key = f"level{level}"
                            if level_key in spell_slots:
                                slot_data = spell_slots[level_key]
                                current = slot_data.get("current", 0)
                                maximum = slot_data.get("max", 0)
                                if maximum > 0:  # Only show levels with available slots
                                    slot_parts.append(f"L{level}:{current}/{maximum}")
                        if slot_parts:
                            spell_slots_str = f", Spell Slots: {' '.join(slot_parts)}"
                
                    # Extract currency
                    currency = member_data_for_note.get("currency", {})
                    gp = currency.get("gold", 0)
                    sp = currency.get("silver", 0)
                    cp = currency.get("copper", 0)
                    currency_parts = []
                    if gp: currency_parts.append(f"{gp}GP")
                    if sp: currency_parts.append(f"{sp}SP")
                    if cp: currency_parts.append(f"{cp}CP")
                    currency_str = f", Currency: {' '.join(currency_parts)}" if currency_parts else ", Currency: 0GP"

                    effects_str = _format_temporary_effects(member_data_for_note)
                    party_stats_formatted.append(f"{display_name}: Level {stats_item['level']}, XP {stats_item['xp']}/{next_level_xp_note}, HP {stats_item['hp']}/{stats_item['max_hp']}, {ability_str}{spell_slots_str}{currency_str}, Effects: {effects_str}")

            party_stats_str = "; ".join(party_stats_formatted)
            party_stats_str += ". (These values reflect the state before the player's current action.)"
            current_location_name_note = world_conditions["currentLocation"]
            current_location_id_note = world_conditions["currentLocationId"]
        
            # --- CONNECTIVITY SECTION ---
            connected_locations_display_str = "None listed"
            connected_areas_display_str = "" # Initialize as empty

            if location_data: # Ensure location_data is not None
                # Get connections within the current area
                if "connectivity" in location_data and location_data["connectivity"]:
                    connected_ids_current_area = location_data["connectivity"]
                    connected_names_current_area = []
                    # Load the current area's full data to get names from IDs
                    current_area_full_data = load_json_file(path_manager.get_area_path(current_area_id))
                    if current_area_full_data and "locations" in current_area_full_data:
                        for loc_id in connected_ids_current_area:
                            found_loc = next((l["name"] for l in current_area_full_data["locations"] if l["locationId"] == loc_id), loc_id)
                            connected_names_current_area.append(found_loc)
                    if connected_names_current_area:
                         connected_locations_display_str = ", ".join(connected_names_current_area)
            
                # Get connections to other areas
                if "areaConnectivityId" in location_data and location_data["areaConnectivityId"]:
                    # Use the global location_graph to get info about connected locations
                    connected_area_details = []
                    for connected_loc_id in location_data["areaConnectivityId"]:
                        # Get the full info for the connected location
                        conn_loc_info = location_graph.get_location_info(connected_loc_id)
                        if conn_loc_info:
                            conn_loc_name = conn_loc_info['location_name']
                            conn_area_name = location_graph.get_area_name_from_location_id(connected_loc_id)
                            connected_area_details.append(f"{conn_loc_name} (in {conn_area_name})")
                
                    if connected_area_details:
                        connected_areas_display_str = ". Connects to other areas via: " + ", ".join(connected_area_details)
        
            # --- INTER-MODULE CONNECTIVITY SECTION ---
            available_modules_str = ""
            try:
                # Load world registry to get all available modules
                world_registry_path = "modules/world_registry.json"
                world_registry = safe_read_json(world_registry_path)
            
                if world_registry and 'modules' in world_registry:
                    current_module = party_tracker_data.get('module', '').replace(' ', '_')
                    all_modules = list(world_registry['modules'].keys())
                    other_modules = [m for m in all_modules if m != current_module]
                
                    if other_modules:
                        # Get areas from other modules
                        other_module_areas = []
                        for module_name in other_modules:
                            module_info = world_registry['modules'][module_name]
                            # Get the areas for this module from the areas section
                            module_areas = []
                            for area_id, area_info in world_registry.get('areas', {}).items():
                                if area_info.get('module') == module_name:
                                    area_name = area_info.get('areaName', area_id)
                                    module_areas.append(f"{area_name} ({area_id})")
                        
                            if module_areas:
                                level_range = module_info.get('levelRange', {})
                                level_str = f"Level {level_range.get('min', '?')}-{level_range.get('max', '?')}"
                            
                                # Get starting location for this module
                                try:
                                    start_location_id, start_location_name, start_area_id, start_area_name = action_handler.get_module_starting_location(module_name)
                                    starting_info = f" (Starting location: {start_location_name} [{start_location_id}] in {start_area_name} [{start_area_id}])"
                                except Exception as e:
                                    print(f"Warning: Could not get starting location for {module_name}: {e}")
                                    starting_info = ""
                            
                                module_description = f"{module_name} [{level_str}]: {', '.join(module_areas[:3])}{starting_info}"
                                other_module_areas.append(module_description)
                    
                        if other_module_areas:
                            available_modules_str = ". Available modules for travel: " + "; ".join(other_module_areas)
            except Exception as e:
                error(f"FAILURE: Failed to load inter-module connectivity", exception=e, category="module_management")
            # --- END OF INTER-MODULE CONNECTIVITY SECTION ---
            # --- END OF CONNECTIVITY SECTION ---
        
            # Use current module from party tracker for plot data
            current_module_for_plot = party_tracker_data.get("module", "").replace(" ", "_")
            current_plot_manager = ModulePathManager(current_module_for_plot)
            plot_data_for_note = load_json_file(current_plot_manager.get_plot_path())
            debug(f"FILE_OP: Plot file path: {current_plot_manager.get_plot_path()}", category="module_management")
            debug(f"FILE_OP: Plot data loaded: {plot_data_for_note is not None}", category="module_management")
            if plot_data_for_note:
                debug(f"FILE_OP: Plot data keys: {list(plot_data_for_note.keys())}", category="module_management")
            else:
                debug("FILE_OP: No plot data loaded - plot_data_for_note is None", category="module_management") 
            current_plot_points = []
            all_active_plot_points = []
            if plot_data_for_note and "plotPoints" in plot_data_for_note:
                # Get plot points for current location
                current_plot_points = [
                    point for point in plot_data_for_note["plotPoints"]
                    if point.get("location") == current_area_id and point["status"] != "completed"
                ]
                # Get ALL active plot points in the module
                all_active_plot_points = [
                    point for point in plot_data_for_note["plotPoints"]
                    if point["status"] != "completed"
                ]
        
            # Format plot points - show current location plots first, then other active plots
            plot_points_parts = []
            if current_plot_points:
                plot_points_parts.append("At this location:")
                plot_points_parts.extend([f"- {point['id']}: {point['title']} [{point.get('status', 'active')}]" for point in current_plot_points])
        
            # Add other active plots from different locations
            other_plots = [p for p in all_active_plot_points if p not in current_plot_points]
            if other_plots:
                if plot_points_parts:  # Add separator if we have location plots
                    plot_points_parts.append("\nActive elsewhere in module:")
                plot_points_parts.extend([f"- {point['id']}: {point['title']} [{point.get('status', 'active')}] @{point.get('location', 'Unknown')}" for point in other_plots])
        
            plot_points_str = "\n".join(plot_points_parts) if plot_points_parts else "None active"
        
            side_quests = []
            # Get ALL side quests from ALL plot points (not just current location)
            for point in plot_data_for_note.get("plotPoints", []):
                for quest in point.get("sideQuests", []):
                    if quest["status"] != "completed":
                        location_info = f" [Location: {point.get('location', 'Unknown')}]" if point.get('location') != current_area_id else ""
                        side_quests.append(f"- {quest['id']}: {quest['title']} [{quest['status']}]{location_info}")
            side_quests_str = "\n".join(side_quests) if side_quests else "None active"

            traps_str = "None listed"
            if location_data and "traps" in location_data: 
                traps = location_data.get("traps", [])
                if traps:
                    traps_str = "\n".join([
                        f"- {trap.get('name', 'Unknown Trap')}: {trap.get('description', 'No description')} (Detect DC: {trap.get('detectDC', 'N/A')}, Disable DC: {trap.get('disableDC', 'N/A')}, Trigger DC: {trap.get('triggerDC', 'N/A')}, Damage: {trap.get('damage', 'N/A')})"
                        for trap in traps
                    ])

            monsters_str = "None listed"
            if location_data and "monsters" in location_data:
                monsters = location_data.get("monsters", [])
            
                # Bulletproof check: ensure monsters is actually a list/array
                if not isinstance(monsters, (list, tuple)):
                    monsters_str = f"Invalid monster data format: {type(monsters)}"
                elif monsters:
                    monster_list = []
                    for monster in monsters:
                        # Graceful handling for different monster formats
                        if isinstance(monster, str):
                            # Handle legacy string format (just use the string)
                            monster_list.append(f"- {monster}")
                        elif isinstance(monster, dict):
                            # Handle dictionary format (multiple schema versions)
                            name = monster.get('name', 'Unknown')
                        
                            # Try different quantity field names
                            qty = None
                            qty_str = "1"
                        
                            if 'quantity' in monster:
                                # Standard schema: {"quantity": {"min": 1, "max": 1}}
                                qty = monster.get('quantity', {})
                                if isinstance(qty, dict):
                                    qty_str = f"{qty.get('min', 1)}-{qty.get('max', 1)}"
                                else:
                                    qty_str = str(qty)
                            elif 'number' in monster:
                                # Keep of Doom schema: {"number": "2d4"}
                                qty_str = str(monster.get('number', 1))
                            elif 'count' in monster:
                                # Silver Vein schema: {"count": 2}
                                qty_str = str(monster.get('count', 1))
                        
                            monster_list.append(f"- {name} ({qty_str})")
                        else:
                            # Handle unexpected types
                            monster_list.append(f"- Unknown monster type: {type(monster)}")
                    monsters_str = "\n".join(monster_list)

            # Check ALL modules for plot completion before suggesting module creation
            module_creation_prompt = ""
            # should_inject_creation_prompt is now a global variable
            try:
                # Debug current module detection
                current_module = party_tracker_data.get('module', '').replace(' ', '_')
                debug(f"STATE_CHANGE: Current module from party tracker: '{current_module}'", category="module_management")
            
                # Use new comprehensive module completion checker
                all_modules_completion = check_all_modules_plot_completion()
            
                # Extract results
                all_modules_complete = all_modules_completion["all_complete"]
                modules_checked = all_modules_completion["modules_checked"]
                completion_summary = all_modules_completion["completion_summary"]
            
                # Print summary of all modules
                debug("STATE_CHANGE: === ALL MODULES COMPLETION SUMMARY ===", category="module_management")
                print("DEBUG: [Module Manager] === MODULE COMPLETION SUMMARY ===")
                for module_name, summary in completion_summary.items():
                    status = "COMPLETE" if summary["is_complete"] else "INCOMPLETE"
                    debug(f"STATE_CHANGE: {module_name}: {summary['completed_plots']}/{summary['total_plots']} plots - {status}", category="module_management")
                    print(f"DEBUG: [Module Manager] {module_name}: {summary['completed_plots']}/{summary['total_plots']} plots - {status}")
                debug("STATE_CHANGE: === END SUMMARY ===", category="module_management")
            
                # Determine if we should inject module creation prompt
                # Only suggest module creation if ALL modules are complete
                should_inject_creation_prompt = all_modules_complete and len(modules_checked) > 0
            
                debug(f"STATE_CHANGE: All modules complete: {all_modules_complete}", category="module_management")
                debug(f"STATE_CHANGE: Should inject module creation prompt: {should_inject_creation_prompt}", category="module_management")
                print(f"DEBUG: [Module Manager] All modules complete: {all_modules_complete}")
                print(f"DEBUG: [Module Manager] Module transfer available: {should_inject_creation_prompt}")
            
                # If ALL modules are complete, inject creation prompt
                if should_inject_creation_prompt:
                    debug("STATE_CHANGE: *** MODULE CREATION PROMPT INJECTION TRIGGERED ***", category="module_management")
                    debug("STATE_CHANGE: All available modules have completed plots - suggesting new module creation", category="module_management")
                    # Load the module creation prompt
                    import os
                    if os.path.exists("prompts/generators/module_creation_prompt.txt"):
                        with open("prompts/generators/module_creation_prompt.txt", "r", encoding="utf-8") as f:
                            module_creation_prompt = "\n\n" + f.read()
                        debug(f"FILE_OP: Module creation prompt loaded ({len(module_creation_prompt)} characters)", category="module_management")
                    else:
                        warning("FILE_OP: module_creation_prompt.txt not found!", category="module_management")

                else:
                    incomplete_modules = [name for name, summary in completion_summary.items() if not summary["is_complete"]]
                    if incomplete_modules:
                        debug(f"STATE_CHANGE: Module creation prompt NOT injected - incomplete modules: {incomplete_modules}", category="module_management")
                    else:
                        debug("STATE_CHANGE: Module creation prompt NOT injected - no modules found to check", category="module_management")
                
            except Exception as e:
                error(f"FAILURE: Module completion check failed", exception=e, category="module_management")
                import traceback
                traceback.print_exc()
        
            # Sanitize location name before using in DM note
            current_location_name_note = sanitize_text(current_location_name_note)
        
            # Get current module, season, and area for enhanced DM note
            current_module_name = party_tracker_data.get('module', 'Unknown')
            current_season = world_conditions.get('season', 'Unknown')
            current_area_name = world_conditions.get('currentArea', 'Unknown')
        
            # Format party members and NPCs for DM note
            party_members_list = party_tracker_data.get('partyMembers', [])
            party_members_str = ", ".join(party_members_list) if party_members_list else "None"
        
            party_npcs_list = party_tracker_data.get('partyNPCs', [])
            party_npcs_formatted = []
            for npc in party_npcs_list:
                party_npcs_formatted.append(f"{npc['name']} ({npc['role']})") 
            party_npcs_str = ", ".join(party_npcs_formatted) if party_npcs_formatted else "None"
        
            # Get established hubs information
            established_hubs_str = ""
            try:
                from core.managers.campaign_manager import CampaignManager
                campaign_manager = CampaignManager()
                hubs = campaign_manager.get_available_hubs()
                if hubs:
                    hub_details = []
                    for hub in hubs:
                        hub_data = campaign_manager.campaign_data['hubs'].get(hub, {})
                        ownership = hub_data.get('ownership', 'party')
                        hub_type = hub_data.get('hubType', 'settlement')
                        hub_details.append(f"{hub} ({hub_type}, {ownership})")
                    established_hubs_str = f" Established hubs: {', '.join(hub_details)}."
            except Exception as e:
                debug(f"Could not load hub information: {e}", category="dm_note")

            # Build DM note - exclude plot/quest info when module creation is active
            if should_inject_creation_prompt:
                # Simplified DM note for module creation - no confusing plot/quest info
                dm_note = (f"Dungeon Master Note: Current date and time: {date_time_str}, {current_season} season. "
                    f"Current module: {current_module_name}. "
                    f"Current location: {current_location_name_note} ({current_location_id_note}) in the {current_area_name} area. "
                    f"Party members: {party_members_str}. "
                    f"Party NPCs: {party_npcs_str}. "
                    f"Party stats: {party_stats_str}. "
                    f"Adjacent locations in this area: {connected_locations_display_str}{connected_areas_display_str}{available_modules_str}{established_hubs_str}.\n")
            else:
                # Normal DM note with all plot/quest/monster info
                dm_note = (f"Dungeon Master Note: Current date and time: {date_time_str}, {current_season} season. "
                    f"Current module: {current_module_name}. "
                    f"Current location: {current_location_name_note} ({current_location_id_note}) in the {current_area_name} area. "
                    f"Party members: {party_members_str}. "
                    f"Party NPCs: {party_npcs_str}. "
                    f"Party stats: {party_stats_str}. "
                    # --- MODIFIED LINE TO INCLUDE CONNECTIVITY ---
                    f"Adjacent locations in this area: {connected_locations_display_str}{connected_areas_display_str}{available_modules_str}{established_hubs_str}.\n"
                    # --- END OF MODIFIED LINE ---
                    f"Active plot points for this location:\n{plot_points_str}\n"
                    f"Active side quests for this location:\n{side_quests_str}\n"
                    f"Monsters in this location:\n{monsters_str}\n"
                    f"Traps in this location:\n{traps_str}\n"
                    "Monsters should be active threats per engagement rules. ")
        
            # Add common instructions
            dm_note += (
                "updateCharacterInfo for player and NPC character changes (inventory, stats, abilities), "
                "removeEffect only to deliberately end or dispel an active effect (durations expire automatically), "
                "updateTime for time passage, "
                "updatePlot for story progression, discovers, and new information, "
                "updatePartyNPCs for party composition changes to the party tracker, "
                "levelUp for advancement, "
                "establishHub when the party gains ownership or control of a location that could serve as a base of operations (stronghold, tavern, keep, etc.) - example: establishHub('The Silver Swan Inn', {hubType: 'tavern', description: 'Our permanent base of operations', services: ['rest', 'information'], ownership: 'party'}), "
                "exitGame for ending sessions, and "
                "transitionLocation should always be used when the player expresses a desire to move to a new location, "
                "Always roleplay the NPC and NPC party rolls without asking the player. "
                "Always ask the player character to roll for skill checks and other actions. "
                "Proactively narrate location NPCs, start conversations, and weave plot elements into the adventure. "
                "Use party NPCs to narrate if possible instead of always narrating from the DM's perspective, but don't overdo it. "
                "Maintain immersive and engaging storytelling similar to an adventure novel while accurately managing game mechanics. "
                "Update all relevant information immediately and confirm with the player before major actions. "
                "Consider whether the party's action trigger traps in this location. "
                "Consider updating the plot elements on every action the player and NPCs take."
                f"{module_creation_prompt}")
        else:
            dm_note = "Dungeon Master Note: Remember to take actions if necessary such as updating the plot, time, character sheets, and location if changes occur."

        # Resolve the named rule once. The same exact bounded block guides the
        # primary call, semantic validator, and any correction retry.
        turn_srd_context = build_srd_context(
            user_input_text,
            player_data_current,
        )

        # Enhance player input with the established inventory context. The
        # player sheet was already used above for SRD availability/resource
        # hints; keep the legacy inventory inputs unchanged on no-match turns.
        user_input_with_note = build_enhanced_dm_note(
            dm_note,
            user_input_text,
            None,
            party_tracker_data,
            None,  # characters_data not available at this scope
            in_combat=False,  # Always use general context for main conversation
            srd_context=turn_srd_context,
        )
        
        from utils.capture.live_provider_call import open_live_turn_scope

        live_turn_scope = open_live_turn_scope()

        pending_v2 = action_handler.recover_pending_location_transition(
            party_tracker_data,
            conversation_history,
        )
        if pending_v2.get("status") == "resume_required" and pending_v2.get(
            "operation_id"
        ):
            live_turn_scope.phase = "MUTATING"
            resumed_v2 = _resume_v2_location_transition(
                pending_v2["operation_id"], publish=True
            )
            if resumed_v2.get("status") != "completed":
                from utils.capture.live_provider_call import finish_live_turn_scope

                finish_live_turn_scope(live_turn_scope)
                print(
                    "[SYSTEM] The prior travel turn remains safely paused for "
                    "recovery; no new action was applied."
                )
                continue
            party_tracker_data = load_json_file("party_tracker.json") or party_tracker_data
            conversation_history = load_json_file(json_file) or conversation_history
            location_data = get_location_data_from_party_tracker(party_tracker_data)
            live_turn_scope.phase = "PRE_MUTATION"

        # Old-format repairs are advisory and may invoke T018/T019/T087/T027.
        # They run only after the real prompt/control surface exists and inside
        # the cancellable live scope; current v2 markers are already preceded
        # by their accepted T016 summary and therefore take this path zero times.
        transitions_were_processed = False
        while True:
            original_history = copy.deepcopy(conversation_history)
            repaired_history = check_and_process_location_transitions(
                conversation_history,
                party_tracker_data,
                path_manager,
            )
            if repaired_history == original_history:
                break
            conversation_history = repaired_history
            transitions_were_processed = True
        if transitions_were_processed:
            save_conversation_history(conversation_history)
            try:
                from core.ai.chunked_compression_integration import (
                    check_and_perform_chunked_compression,
                )

                check_and_perform_chunked_compression()
                conversation_history = load_json_file(json_file) or conversation_history
            except Exception as legacy_compression_error:
                warning(
                    "Legacy chronicle enrichment remained unavailable: %s"
                    % type(legacy_compression_error).__name__,
                    category="conversation_management",
                )
        pending_legacy = safe_json_load(
            action_handler.PENDING_LOCATION_TRANSITION_FILE
        )
        if (
            isinstance(pending_legacy, dict)
            and pending_legacy.get("version") == 2
            and pending_legacy.get("kind") == "legacy_repair"
        ):
            from utils.capture.live_provider_call import finish_live_turn_scope

            finish_live_turn_scope(live_turn_scope)
            print(
                "[SYSTEM] An older travel record is safely paused for exact "
                "recovery; no new action was applied."
            )
            continue
        pre_turn_accepted_history = copy.deepcopy(conversation_history)
        conversation_history.append({"role": "user", "content": user_input_with_note})
        save_conversation_history(conversation_history)

        validation_prefix_length = len(conversation_history)
        retry_count = 0
        valid_response_received = False
        ai_response_content = None
        approved_transition_plan = None
        rejected_candidate = None
        retry_correction = None
        planner_projection = None
        # [travel-clean #209] NPC voice advisory is deferred until the voice line
        # lands; keep the parameter inert so the turn threads None, not a NameError.
        npc_voice_batch = None

        while not valid_response_received:
            if live_turn_scope.is_superseded():
                conversation_history[:] = pre_turn_accepted_history
                save_conversation_history(conversation_history)
                break
            # Authorization belongs only to this candidate response. A retry
            # must obtain a new plan from the current atlas/evidence snapshot.
            approved_transition_plan = None
            # Durable completion/rebuild work sees authoritative accepted
            # history only. Retry material is appended to a detached view.
            prepare_conversation_for_ai_request(conversation_history)
            request_history = copy.deepcopy(conversation_history)
            if rejected_candidate:
                request_history.append(
                    {"role": "assistant", "content": rejected_candidate}
                )
            if planner_projection:
                request_history.append(
                    {
                        "role": "system",
                        "content": (
                            "Accepted Travel Agent facts for this turn (JSON): "
                            + json.dumps(
                                planner_projection,
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                        ),
                    }
                )
            if retry_correction:
                request_history.append(
                    {"role": "user", "content": retry_correction}
                )
            from utils.capture.live_provider_call import LiveProviderSuperseded
            try:
                ai_response_content = _get_live_ai_response(
                    request_history,
                    validation_retry_count=retry_count,
                )
            except LiveProviderSuperseded:
                conversation_history[:] = pre_turn_accepted_history
                save_conversation_history(conversation_history)
                break
            if live_turn_scope.is_superseded():
                conversation_history[:] = pre_turn_accepted_history
                save_conversation_history(conversation_history)
                break

            # PRE-PROCESSING: Fix incorrect updatePartyTracker usage for within-module travel
            # This must happen BEFORE any validation to prevent wrong action from being checked
            try:
                import json
                response_data = json.loads(ai_response_content)
                actions = response_data.get("actions", [])

                # Debug: Show what actions AI sent before any processing
                if actions:
                    action_list = [a.get("action") if isinstance(a, dict) else str(a) for a in actions]
                    print(f"DEBUG: [AI RESPONSE] Actions received: {action_list}")
                else:
                    print(f"DEBUG: [AI RESPONSE] No actions in response")

                current_module = party_tracker_data.get("module", "")
                actions_modified = False

                # Check for updatePartyTracker being used for within-module location changes
                for i, action in enumerate(actions):
                    if isinstance(action, dict) and action.get("action") == "updatePartyTracker":
                        params = action.get("parameters", {})

                        # Check if this is a location transition (has currentLocationId) vs party composition change
                        has_location_id = "currentLocationId" in params
                        has_module = "module" in params

                        if has_location_id and has_module:
                            # Check if module is the SAME as current module (within-module travel)
                            target_module = params.get("module", "")

                            if target_module == current_module:
                                # WRONG ACTION: Using updatePartyTracker for within-module travel
                                # Convert to transitionLocation
                                new_location_id = params.get("currentLocationId", "")

                                print(f"DEBUG: [ACTION FIX] Converting updatePartyTracker to transitionLocation({new_location_id}) - same module")
                                info(f"ACTION FIX: Converted updatePartyTracker to transitionLocation for within-module travel", category="action_preprocessing")

                                # Replace with transitionLocation
                                actions[i] = {
                                    "action": "transitionLocation",
                                    "parameters": {
                                        "newLocation": new_location_id
                                    }
                                }
                                actions_modified = True

                # Update response if we modified actions
                if actions_modified:
                    response_data['actions'] = actions
                    ai_response_content = json.dumps(response_data)
                    info(f"ACTION FIX: Updated response with corrected action types", category="action_preprocessing")

            except (json.JSONDecodeError, Exception) as e:
                debug(f"Could not pre-process actions: {e}", category="action_preprocessing")

            # Structural transition checks precede semantic validation. Route
            # authority follows T065, so mechanically safe but semantically
            # wrong candidates never consume T021 or atlas work.
            transition_check_passed = True
            transition_action = None
            try:
                response_data = json.loads(ai_response_content)
                actions = response_data.get("actions", [])

                transition_indexes = [
                    index
                    for index, candidate_action in enumerate(actions)
                    if isinstance(candidate_action, dict)
                    and candidate_action.get("action") == "transitionLocation"
                ]
                if transition_indexes and (
                    len(transition_indexes) != 1
                    or transition_indexes[0] != 0
                ):
                    retry_count += 1
                    transition_check_passed = False
                    rejected_candidate = ai_response_content
                    retry_correction = (
                        "The previous structured response was rejected: "
                        "transitionLocation must be the first action and may "
                        "appear only once. Put time, save, and all other state "
                        "changes after it. Return the complete corrected JSON."
                    )
                    info(
                        "VALIDATION: Rejected unsafe transition action order; "
                        f"retry {retry_count}",
                        category="location_transitions",
                    )

                for action in actions if transition_check_passed else []:
                    if isinstance(action, dict) and action.get("action") == "transitionLocation":
                        new_location = action.get("parameters", {}).get("newLocation", "")
                        current_location_id = party_tracker_data["worldConditions"]["currentLocationId"]

                        if new_location == current_location_id:
                            # Same location transition - STRIP the action instead of retrying
                            info(f"VALIDATION: Same-location transition detected ({current_location_id}), stripping action", category="location_transitions")
                            print(f"DEBUG: [SAME-LOCATION] Stripping transitionLocation({current_location_id}) from response")

                            # Remove this action from the actions array
                            actions.remove(action)

                            # Update the response content with stripped actions
                            response_data['actions'] = actions
                            ai_response_content = json.dumps(response_data)

                            # Don't retry - continue with modified response
                            info(f"VALIDATION: Same-location action stripped, continuing with narration only", category="location_transitions")
                            transition_action = None
                            break
                        transition_action = action
                        break

                first_candidate = (
                    actions[0]
                    if transition_check_passed
                    and actions
                    and isinstance(actions[0], dict)
                    else {}
                )
                first_candidate_params = first_candidate.get("parameters")
                first_candidate_params = (
                    first_candidate_params
                    if isinstance(first_candidate_params, dict)
                    else {}
                )
                candidate_module = str(first_candidate_params.get("module") or "")
                if (
                    transition_check_passed
                    and first_candidate.get("action") == "updatePartyTracker"
                    and candidate_module
                    and candidate_module
                    != str(party_tracker_data.get("module") or "")
                    and (
                        len(actions) != 2
                        or not isinstance(actions[1], dict)
                        or actions[1].get("action") != "updateTime"
                    )
                ):
                    retry_count += 1
                    transition_check_passed = False
                    rejected_candidate = ai_response_content
                    retry_correction = (
                        "The previous structured response was rejected: direct "
                        "travel to another existing module must contain exactly "
                        "two actions in this order: updatePartyTracker, then "
                        "updateTime. Do not add updatePlot or any later action. "
                        "Return the complete corrected JSON."
                    )
                    status_retrying(retry_count)

                if (
                    transition_check_passed
                    and first_candidate.get("action") == "updatePartyTracker"
                    and candidate_module
                    and candidate_module
                    != str(party_tracker_data.get("module") or "")
                ):
                    try:
                        action_handler.resolve_cross_module_target_projection(
                            candidate_module, first_candidate_params
                        )
                    except ValueError as exc:
                        retry_count += 1
                        transition_check_passed = False
                        rejected_candidate = ai_response_content
                        retry_correction = (
                            "The previous structured response was rejected "
                            "before mutation because its module destination "
                            "references conflict: %s. Use canonical IDs and "
                            "names from the target module, or provide only the "
                            "module so code can use its represented starting "
                            "location. Return the complete corrected JSON."
                            % str(exc)
                        )
                        status_retrying(retry_count)

                if transition_check_passed and transition_indexes:
                    # Owner ruling 2026-08-23: one model response resolves one
                    # immediate semantic beat.  After within-module travel,
                    # only travel-owned bookkeeping may remain in this turn.
                    # T065 owns the semantic judgment (including whether an
                    # updatePlot describes the immediate travel outcome); this
                    # structured-family envelope prevents future player plans
                    # from becoming additional post-arrival turns.
                    supported_siblings = {
                        "updateTime",
                        "updatePlot",
                    }
                    unsupported = [
                        item.get("action") if isinstance(item, dict) else type(item).__name__
                        for item in actions[1:]
                        if not isinstance(item, dict)
                        or item.get("action") not in supported_siblings
                    ]
                    contract_error = None
                    if unsupported:
                        contract_error = (
                            "Travel ends at the committed destination. These "
                            "actions belong to a later player turn and cannot "
                            "execute after arrival: %s. Preserve the later "
                            "intent in narration, invite the player's next "
                            "action, and return only transitionLocation plus "
                            "travel-owned updateTime/updatePlot bookkeeping."
                            % ", ".join(map(str, unsupported))
                        )
                    if contract_error:
                        retry_count += 1
                        transition_check_passed = False
                        rejected_candidate = ai_response_content
                        retry_correction = (
                            "The previous structured response was rejected. "
                            + contract_error
                            + " Return the complete corrected JSON."
                        )
                        status_retrying(retry_count)

            except json.JSONDecodeError as e:
                # Structural validation below owns malformed provider JSON.
                debug(f"Could not parse response for transition planning: {e}", category="location_transitions")
            except Exception as e:
                error(
                    "FAILURE: Transition structural check raised unexpectedly",
                    exception=e,
                    category="location_transitions",
                )
                retry_count += 1
                transition_check_passed = False
                rejected_candidate = ai_response_content
                retry_correction = (
                    "The previous structured response could not be checked "
                    "safely. Return a complete corrected JSON response."
                )

            if not transition_check_passed:
                continue  # Skip to next retry iteration

            if live_turn_scope.is_superseded():
                conversation_history[:] = pre_turn_accepted_history
                save_conversation_history(conversation_history)
                break

            try:
                validation_result = validate_ai_response(
                    ai_response_content,
                    user_input_text,
                    validation_prompt_text,
                    request_history,
                    party_tracker_data,
                    srd_context=turn_srd_context,
                    npc_voice_batch=npc_voice_batch,
                    transition_facts=planner_projection,
                )
            except LiveProviderSuperseded:
                conversation_history[:] = pre_turn_accepted_history
                save_conversation_history(conversation_history)
                break

            # Unpack the validation result tuple
            is_valid = False
            validation_reason = ""
            if isinstance(validation_result, tuple):
                is_valid, validated_content = validation_result
                if is_valid:
                    # Use the fixed/validated content if auto-fix was applied
                    ai_response_content = validated_content
                else:
                    validation_reason = validated_content  # It's the error message when invalid
            else:
                # Handle old-style return (shouldn't happen after our change)
                is_valid = validation_result is True
                validation_reason = validation_result if isinstance(validation_result, str) else ""

            if live_turn_scope.is_superseded():
                conversation_history[:] = pre_turn_accepted_history
                save_conversation_history(conversation_history)
                break
            
            if is_valid:
                # Semantic agreement is established before route authority.
                # Reparse after T065 because structural normalization may have
                # returned corrected candidate content.
                validated_data = json.loads(ai_response_content)
                validated_actions = validated_data.get("actions", [])
                validated_transition_indexes = [
                    index
                    for index, action in enumerate(validated_actions)
                    if isinstance(action, dict)
                    and action.get("action") == "transitionLocation"
                ]
                if validated_transition_indexes and (
                    len(validated_transition_indexes) != 1
                    or validated_transition_indexes[0] != 0
                ):
                    rejected_candidate = ai_response_content
                    retry_correction = (
                        "The normalized response is structurally unsafe: "
                        "transitionLocation must appear once and first. Return "
                        "the complete corrected JSON response."
                    )
                    retry_count += 1
                    status_retrying(retry_count)
                    continue
                transition_action = next(
                    (
                        action
                        for action in validated_actions
                        if isinstance(action, dict)
                        and action.get("action") == "transitionLocation"
                    ),
                    None,
                )
                if transition_action is not None:
                    proposed_location = str(
                        (transition_action.get("parameters") or {}).get(
                            "newLocation", ""
                        )
                    )
                    current_location = str(
                        party_tracker_data.get("worldConditions", {}).get(
                            "currentLocationId", ""
                        )
                    )
                    if proposed_location == current_location:
                        validated_actions.remove(transition_action)
                        validated_data["actions"] = validated_actions
                        ai_response_content = json.dumps(validated_data)
                        transition_action = None
                if transition_action is not None:
                    from core.ai.action_handler import pre_validate_transition

                    try:
                        route_outcome = pre_validate_transition(
                            transition_action.get("parameters", {}),
                            party_tracker_data,
                            conversation_history,
                            location_graph,
                            path_manager,
                            return_plan=True,
                        )
                    except LiveProviderSuperseded:
                        conversation_history[:] = pre_turn_accepted_history
                        save_conversation_history(conversation_history)
                        break
                    if not route_outcome.approved:
                        rejected_candidate = ai_response_content
                        planner_projection = {
                            "reason_code": route_outcome.reason_code,
                            **dict(route_outcome.facts or {}),
                        }
                        if route_outcome.reason_code == "intermediate_stop":
                            retry_correction = (
                                "Revise the complete response using the accepted "
                                "Travel Agent facts. Narrate movement toward the "
                                "player's original goal, but transition only to "
                                f"{route_outcome.intermediate_destination_id} "
                                f"({route_outcome.intermediate_destination_name}). "
                                "Use that transitionLocation first and do not "
                                "transition to the original final destination in "
                                "this turn."
                            )
                        elif route_outcome.reason_code in {
                            "no_valid_route",
                            "active_combat",
                        }:
                            retry_correction = (
                                "Revise the complete response from the accepted "
                                "Travel Agent facts. Do not include "
                                "transitionLocation or invent another destination. "
                                "Give one honest in-fiction explanation and leave "
                                "the next choice to the player."
                            )
                        elif route_outcome.reason_code in {
                            "destination_absent",
                            "destination_invalid",
                        }:
                            retry_correction = (
                                "The proposed destination is not a usable canonical "
                                "destination. Do not move the party or describe it "
                                "as an impassable known route. Ask the player one "
                                "focused clarification in the complete JSON response."
                            )
                        else:
                            retry_correction = (
                                "Travel planning did not produce an accepted route. "
                                "Keep the party in place and regenerate the complete "
                                "response from the supplied structured facts."
                            )
                        retry_count += 1
                        status_retrying(retry_count)
                        info(
                            "VALIDATION: Transition outcome %s; retry %s"
                            % (route_outcome.reason_code, retry_count),
                            category="location_transitions",
                        )
                        continue
                    approved_transition_plan = route_outcome.plan

                if live_turn_scope.is_superseded():
                    conversation_history[:] = pre_turn_accepted_history
                    save_conversation_history(conversation_history)
                    break

                valid_response_received = True
                live_turn_scope.phase = "MUTATING"
                debug(f"SUCCESS: Valid response generated on attempt {retry_count + 1}", category="ai_validation")

                # Failed candidates and validator feedback are retry context,
                # not durable game history. Only the accepted candidate may
                # cross into process_ai_response and its state handlers.
                conversation_history = conversation_history[
                    :validation_prefix_length
                ]
                save_conversation_history(conversation_history)
            
                # SIMPLIFIED ARCHITECTURE: process_ai_response now handles ALL complexity internally.
                # This includes:
                # - Standard turn processing
                # - Combat encounters (via needs_post_combat_narration signal)
                # - Location transitions (with seamless narration generation)
                # - Level-up sessions (returned as enter_levelup_mode signal)
                # - All conversation history updates
                # The main loop is now just a thin orchestration layer.
                final_result = process_ai_response(
                    ai_response_content,
                    party_tracker_data,
                    location_data,
                    conversation_history,
                    approved_transition_plan=approved_transition_plan,
                )
                (
                    final_result,
                    party_tracker_data,
                    location_data,
                    conversation_history,
                ) = resolve_retryable_ai_result(
                    final_result,
                    party_tracker_data,
                    location_data,
                    conversation_history,
                )

                if (
                    isinstance(final_result, dict)
                    and final_result.get("retryable") is True
                ):
                    retry_status = final_result.get(
                        "status", "state_recovery_pending"
                    )
                    print(
                        "[SYSTEM] The game state changed while that turn was "
                        f"processing ({retry_status}). Your state is safe; "
                        "please retry after recovery completes."
                    )
                    warning(
                        f"Response processing paused: {retry_status}",
                        category="module_management",
                    )
                elif (
                    isinstance(final_result, dict)
                    and final_result.get("status") == "error"
                ):
                    from web.shared_state import SAFE_ACTION_FAILURE_MESSAGE

                    processing_error = final_result.get("player_message")
                    if processing_error != SAFE_ACTION_FAILURE_MESSAGE:
                        processing_error = SAFE_ACTION_FAILURE_MESSAGE
                    print(f"[SYSTEM] {processing_error}")
                    warning(
                        "Response processing failed safely",
                        category="module_management",
                    )

                # After processing, we only need to check for control flow signals.
                # Everything else (including history updates) has been handled by process_ai_response.
                if final_result == "exit":
                    from utils.capture.live_provider_call import finish_live_turn_scope
                    finish_live_turn_scope(live_turn_scope)
                    return
                elif final_result == "restart":
                    from utils.capture.live_provider_call import finish_live_turn_scope
                    finish_live_turn_scope(live_turn_scope)
                    print("\n[SYSTEM] Restarting game with restored save...\n")
                    main_game_loop()
                    return
                elif isinstance(final_result, dict) and final_result.get("status") == "enter_levelup_mode":
                    # Enter the level up sub-loop
                    level_up_session = final_result["session"]

                    # Get the first message from the session
                    dm_response = level_up_session.start()

                    # The level-up AI may wrap its opening message in JSON
                    # ({"narration": ...}) depending on the prompt. Display/store the
                    # narration text, not the raw JSON blob -- mirrors the per-turn
                    # handling in the loop below. Plain-text greetings fall through
                    # unchanged (json.loads raises -> use raw text).
                    try:
                        _first_parsed = json.loads(dm_response)
                        first_display = (_first_parsed.get("narration", dm_response)
                                         if isinstance(_first_parsed, dict) else dm_response)
                    except (json.JSONDecodeError, TypeError):
                        first_display = dm_response

                    # Autonomous/NPC sessions may complete in start().  In that
                    # branch there is no input-loop response to populate the
                    # final narration, so the opening response is also the
                    # definitive completion narration.
                    completed_on_start = level_up_session.is_complete
                    final_narration = first_display

                    # Display the first message and add to history
                    display_dm_narration(first_display, channel="levelup")
                    conversation_history.append({"role": "assistant", "content": first_display})
                    save_conversation_history(conversation_history)

                    # Loop until the session is complete
                    while not level_up_session.is_complete:
                        # Get player input
                        player_name_display = f"{SOLID_GREEN}{player_name_actual}{RESET_COLOR}"
                        try:
                            level_up_input = input(f"{player_name_display} (Leveling Up): ")
                        except EOFError:
                            # Closed/piped stdin must abort the sub-loop, not
                            # crash the game (same guard the combat loop has).
                            warning("LEVELUP: Input stream ended during level up. Aborting session.", category="level_up")
                            if not level_up_session.summary:
                                # The post-loop failure path displays and
                                # persists this; without it the player gets
                                # an empty message.
                                level_up_session.summary = "The level up was interrupted before it could finish. It can be attempted again."
                            break

                        if not level_up_input or not level_up_input.strip():
                            continue
                    
                        # Handle the input and get the next AI response from the session
                        dm_response = level_up_session.handle_input(level_up_input)

                        # Check if the response is the final JSON or a conversational step
                        try:
                            # It's the final JSON response
                            parsed_data = json.loads(dm_response)
                            final_narration = parsed_data.get("narration", "Level up complete!")
                            display_dm_narration(final_narration, channel="levelup")
                            # The session is now complete, loop will exit
                        except (json.JSONDecodeError, TypeError):
                            # It's a normal conversational response
                            display_dm_narration(dm_response, channel="levelup")

                    # After the loop, the session is complete.
                    if level_up_session.success:
                        debug("SUCCESS: Level up successful. Using final narration for context.", category="level_up")
                        # Add the final, high-quality narration to the history as the definitive AI response.
                        # This provides perfect context for the next turn without an extra AI call.
                        final_history_message = {
                            "role": "assistant",
                            "content": json.dumps(
                                {"narration": final_narration, "actions": []}
                            ),
                        }
                        if completed_on_start and conversation_history:
                            # The start response was already displayed/persisted;
                            # canonicalize that record instead of duplicating it.
                            conversation_history[-1] = final_history_message
                        else:
                            conversation_history.append(final_history_message)
                        save_conversation_history(conversation_history)
                    else:
                        # If the level up failed, inform the player and log it.
                        display_dm_narration(level_up_session.summary, channel="levelup", color="red")
                        conversation_history.append({"role": "system", "content": level_up_session.summary})
                        save_conversation_history(conversation_history)

                    # Break the outer validation loop and proceed to the next turn.
                    break 

                # CRITICAL: Reload conversation history from disk.
                # Since process_ai_response handles all history updates internally (including sub-systems
                # like combat that may add multiple messages), we must reload to ensure our local
                # conversation_history variable matches the persisted state.
                # This is the ONLY place the main loop needs to manage conversation_history.
                conversation_history = _reload_conversation_history_if_safe(
                    conversation_history
                )
                # No need to save here, as process_ai_response already handled all persistence.

            elif not is_valid and validation_reason:
                # Validation failed with a reason
                debug(f"VALIDATION: Validation failed. Reason: {validation_reason}", category="ai_validation")
                status_retrying(retry_count + 1)
                correction_context = (
                    "\n\n%s" % turn_srd_context if turn_srd_context else ""
                )
                rejected_candidate = ai_response_content
                retry_correction = (
                    "Your previous response failed semantic validation. "
                    f"Reason: {validation_reason}. Return the complete corrected "
                    f"JSON response.{correction_context}"
                )
                retry_count += 1
            else: 
                warning(f"VALIDATION: Unexpected validation result: is_valid={is_valid}, reason={validation_reason}. Retrying.", category="ai_validation")
                rejected_candidate = ai_response_content
                retry_correction = (
                    "The previous validation result was not usable. Return the "
                    "complete corrected JSON response for the player's action."
                )
                retry_count += 1

        if not valid_response_received:
            from utils.capture.live_provider_call import finish_live_turn_scope

            finish_live_turn_scope(live_turn_scope)
            return

        # This block now only runs if a response was NOT held
        # CRITICAL: Reload party tracker to ensure we have the latest module information after any updates
        party_tracker_data = load_json_file("party_tracker.json")
        print(f"DEBUG: [Before update_conversation_history] Reloaded party tracker. Module: {party_tracker_data.get('module', 'Unknown')}")
    
        current_area_id = party_tracker_data["worldConditions"]["currentAreaId"] 
        # Use current module from party tracker for plot data  
        module_name_updated = party_tracker_data.get("module", "").replace(" ", "_")
        updated_path_manager = ModulePathManager(module_name_updated)
        plot_data = load_json_file(updated_path_manager.get_plot_path())
        module_data = load_json_file(updated_path_manager.get_module_file_path())
        debug(f"FILE_OP: Updated plot file path: {updated_path_manager.get_plot_path()}", category="module_management")

        debug(f"STATE_CHANGE: Before AI response update_conversation_history - history has {len(conversation_history)} messages", category="conversation_management")
        conversation_history = update_conversation_history(conversation_history, party_tracker_data, plot_data, module_data)
        debug(f"STATE_CHANGE: After AI response update_conversation_history - history has {len(conversation_history)} messages", category="conversation_management")
        conversation_history = update_character_data(conversation_history, party_tracker_data)
        conversation_history = ensure_main_system_prompt(conversation_history, main_system_prompt_text)
    
        # Use the new order_conversation_messages function
        conversation_history = order_conversation_messages(conversation_history, main_system_prompt_text)
    
        save_conversation_history(conversation_history)

        from utils.capture.live_provider_call import finish_live_turn_scope

        finish_live_turn_scope(live_turn_scope)

def main():
    """Main entry point with startup wizard integration"""
    setup_utf8_console()
    
    # Check if config.py exists, create from template if not
    import os
    import shutil
    if not os.path.exists('config.py'):
        print("[D20] Welcome to NeverEndingQuest! [D20]")
        print("\nFirst-time setup detected...")
        
        try:
            # Copy config_template.py to config.py
            shutil.copy('config_template.py', 'config.py')
            print("\n[OK] Created config.py from template")
            print("\n" + "="*60)
            print("IMPORTANT: OpenAI API Key Required")
            print("="*60)
            print("\n1. Open config.py in a text editor")
            print("2. Find the line: OPENAI_API_KEY = \"your_openai_api_key_here\"")
            print("3. Replace \"your_openai_api_key_here\" with your actual OpenAI API key")
            print("4. Save the file and run the game again")
            print("\nGet your API key at: https://platform.openai.com/api-keys")
            print("\nOr run fully local (no API key): install LM Studio/Ollama, then in Settings -> AI Provider pick Local and set your endpoint URL.")
            print("\n" + "="*60)
            input("\nPress Enter to exit...")
            return
        except Exception as e:
            print(f"[ERROR] Failed to create config.py: {e}")
            print("Please manually copy config_template.py to config.py")
            input("\nPress Enter to exit...")
            return
    
    # Initialize all required directories
    required_dirs = [
        "modules/conversation_history",
        "modules/campaign_archives", 
        "modules/campaign_summaries",
        "modules/backups",
        "modules/logs",
        "save_games",
        "characters",
        "combat_logs"
    ]
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    # DISABLED FOR DEBUGGING - Create empty party tracker if it doesn't exist (in root directory)
    # party_tracker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'party_tracker.json')
    # if not os.path.exists(party_tracker_path):
    #     empty_party_tracker = {
    #         "module": "",
    #         "partyMembers": [],
    #         "partyNPCs": [],
    #         "worldConditions": {
    #             "year": 1492,
    #             "month": "Springmonth",
    #             "day": 1,
    #             "time": "08:00:00",
    #             "weather": "",
    #             "season": "Spring",
    #             "dayNightCycle": "Day",
    #             "moonPhase": "New Moon",
    #             "currentLocation": "",
    #             "currentLocationId": "",
    #             "currentArea": "",
    #             "currentAreaId": "",
    #             "majorEventsUnderway": [],
    #             "politicalClimate": "",
    #             "activeEncounter": "",
    #             "activeCombatEncounter": ""
    #         }
    #     }
    #     try:
    #         with open(party_tracker_path, 'w', encoding='utf-8') as f:
    #             json.dump(empty_party_tracker, f, indent=2)
    #         print(f"[INFO] Created empty party_tracker.json in root directory for first-time setup")
    #     except Exception as e:
    #         print(f"[WARNING] Could not create party_tracker.json in root: {e}")
    
    # Always initialize game files from BU templates if needed
    from utils.startup_wizard import initialize_game_files_from_bu
    initialize_game_files_from_bu()
    
    # Run calendar migration check
    from utils.calendar_migration import run_calendar_migration
    run_calendar_migration()
    
    # Check if first-time setup is needed
    try:
        from utils.startup_wizard import startup_required, run_startup_sequence
        
        if startup_required():
            print("[D20] Welcome to your 5th Edition Adventure! [D20]")
            print("It looks like this is your first time, or you need to set up a character.")
            print("Let's get you ready for adventure!\n")
            
            success = run_startup_sequence()
            if not success:
                print("[ERROR] Setup was cancelled or failed. Exiting...")
                return
            
            print("Setup complete! Your adventure begins now...\n")
    
    except Exception as e:
        warning(f"INITIALIZATION: Startup wizard had an issue", category="startup")
        print("Continuing with main game (assuming setup is complete)...\n")

    # Initialize the global location graph AFTER all modules are stitched and ready
    global location_graph
    print("DEBUG: [LocationGraph] Initializing global graph for game session...")
    location_graph = LocationGraph()
    location_graph.load_module_data()
    print(f"DEBUG: [LocationGraph] Initialization complete. Total nodes loaded: {len(location_graph.nodes)}")
    print(f"DEBUG: [LocationGraph] Total edges loaded: {sum(len(edges) for edges in location_graph.edges.values())}")
    if len(location_graph.nodes) > 0:
        print(f"DEBUG: [LocationGraph] First 5 location IDs: {list(location_graph.nodes.keys())[:5]}")
    else:
        print("DEBUG: [LocationGraph] WARNING - No nodes loaded! Check if modules are integrated.")

    # Continue with normal game loop
    main_game_loop()

if __name__ == "__main__":
    main()
