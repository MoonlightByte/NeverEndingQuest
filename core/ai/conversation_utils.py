# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# CONVERSATION_UTILS.PY - AI CONTEXT MANAGEMENT LAYER
# ============================================================================
# 
# ARCHITECTURE ROLE: AI Integration Layer - Context and History Management
# 
# This module manages AI conversation context, history compression, and
# memory optimization to maintain coherent long-term game sessions while
# respecting AI model token limitations.
# 
# KEY RESPONSIBILITIES:
# - Conversation history management and persistence
# - Intelligent context trimming and compression
# - Game state synchronization with AI context
# - Memory optimization for long-running sessions
# - Context rebuilding after session interruptions
# - Character data formatting for AI consumption
# 
# CONTEXT MANAGEMENT STRATEGY:
# - Rolling conversation window with intelligent pruning
# - Key game state preservation across context reductions
# - Selective history compression based on importance
# - Real-time context size monitoring and optimization
# 
# INFORMATION ARCHITECTURE DESIGN:
# - SYSTEM MESSAGES: Static character reference data (stats, abilities, spells)
# - DM NOTES: Dynamic, frequently-changing data (HP, spell slots, status)
# - SEPARATION PRINCIPLE: Prevents AI confusion from conflicting data versions
# - SINGLE SOURCE OF TRUTH: DM Note is authoritative for current character state
# 
# DATA SEPARATION STRATEGY:
# System Messages (Static Reference):
#   - Ability scores, skills, proficiencies
#   - Class features, racial traits, equipment lists
#   - Spellcasting ability/DC/bonus, known spells
#   - Personality traits, background information
# 
# DM Notes (Dynamic Current State):
#   - Current/max hit points
#   - Current/max spell slots
#   - Active conditions and temporary effects
#   - Real-time combat status
# 
# COMPRESSION TECHNIQUES:
# - Adventure summary generation for long-term memory
# - Character state snapshots for quick context rebuilding
# - Important event highlighting and preservation
# - Redundant information removal while preserving continuity
# 
# ARCHITECTURAL INTEGRATION:
# - Core dependency for dm_wrapper.py AI interactions
# - Integrates with main.py for session management
# - Uses file_operations.py for conversation persistence
# - Supports cumulative_summary.py for long-term memory
# 
# AI CONTEXT OPTIMIZATION:
# - Token-aware context management
# - Model-specific optimization strategies
# - Intelligent prompt construction with relevant history
# - Context freshness tracking and stale data removal
# - Conflict prevention through data source separation
# 
# DESIGN PATTERNS:
# - Memento Pattern: Conversation state snapshots
# - Strategy Pattern: Different compression strategies
# - Observer Pattern: Context size change notifications
# - Single Source of Truth: Dynamic data authority separation
# 
# This module ensures AI maintains coherent understanding of ongoing
# adventures while optimizing performance and token usage, and prevents
# confusion through clear separation of static vs dynamic character data.
# ============================================================================

import json
import os
import re
from utils.module_path_manager import ModulePathManager
from utils.encoding_utils import safe_json_load
from utils.character_sheet_contract import normalize_for_runtime
from utils.plot_formatting import format_plot_for_ai
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from core.ai.atlas_builder import build_atlas_for_module, format_atlas_for_conversation


def _effects_runtime_view(character_data):
    try:
        from core.effects.effective import effective_sheet
        return effective_sheet(character_data)
    except Exception:
        pass
    return character_data


def _format_temporary_effects(character_data):
    values = []
    for effect in character_data.get("temporaryEffects", []) or []:
        if not isinstance(effect, dict) or not effect.get("name"):
            continue
        duration = effect.get("duration")
        if effect.get("roundsRemaining") is not None:
            duration = f"{effect['roundsRemaining']} rounds remaining"
        elif effect.get("expiration"):
            duration = f"until {effect['expiration']}"
        values.append(
            f"{effect['name']} ({duration})" if duration else str(effect["name"])
        )
    return ", ".join(values) if values else "none"

# Set script name for logging
set_script_name("conversation_utils")

# ============================================================================
# CAMPAIGN SUMMARY INJECTION
# ============================================================================

def inject_campaign_summaries(new_history, current_module=None):
    """Inject campaign summaries as system messages into conversation history
    
    Args:
        new_history: The conversation history list to append summaries to
        current_module: The current module name to exclude from summaries
    """
    try:
        summaries_dir = "modules/campaign_summaries"
        if os.path.exists(summaries_dir):
            summary_files = [f for f in os.listdir(summaries_dir) if '_summary_' in f and f.endswith('.json')]
            
            # Load all summaries with their completion dates for proper chronological sorting
            summaries_with_dates = []
            for summary_file in summary_files:
                try:
                    summary_path = os.path.join(summaries_dir, summary_file)
                    summary_data = safe_json_load(summary_path)
                    if summary_data and "completionDate" in summary_data:
                        summaries_with_dates.append((summary_data["completionDate"], summary_file, summary_data))
                except Exception as e:
                    debug(f"WARNING: Could not load completion date from {summary_file}", exception=e, category="campaign_context")
            
            # Sort by completion date (chronological order)
            summaries_with_dates.sort(key=lambda x: x[0])
            
            if summaries_with_dates:
                for completion_date, summary_file, summary_data in summaries_with_dates:
                    try:
                        if summary_data and "summary" in summary_data:
                            module_name = summary_data.get("moduleName", "Unknown Module")
                            sequence = summary_data.get("sequenceNumber", 1)
                            
                            # Skip the current module's summaries
                            # Normalize module names for comparison (handle underscore vs space differences)
                            normalized_module_name = module_name.replace('_', ' ')
                            normalized_current = current_module.replace('_', ' ') if current_module else None
                            
                            if normalized_current and normalized_module_name == normalized_current:
                                debug(f"INFO: Skipping summary for current module {module_name}", category="campaign_context")
                                continue
                            
                            # Create the full content for this single chronicle
                            chronicle_content = (
                                f"=== CAMPAIGN CONTEXT ===\n\n"
                                f"--- {module_name} (Chronicle {sequence:03d}) ---\n"
                                f"{summary_data['summary']}"
                            )
                            
                            # Append it as a new, separate system message
                            new_history.append({"role": "system", "content": chronicle_content})
                            
                            debug(f"SUCCESS: Injected chronicle for {module_name} (completed {completion_date}) as a separate system message", category="campaign_context")
                    except Exception as e:
                        debug(f"FAILURE: Could not inject summary {summary_file}", exception=e, category="campaign_context")
            else:
                debug(f"INFO: No campaign summary files found in {summaries_dir}", category="campaign_context")
    except Exception as e:
        debug(f"FAILURE: Error injecting campaign summaries", exception=e, category="campaign_context")

# ============================================================================
# MODULE TRANSITION DETECTION AND HANDLING
# ============================================================================

def find_last_module_transition_index(conversation_history):
    """Find the index of the last module transition marker"""
    for i in range(len(conversation_history) - 1, -1, -1):
        message = conversation_history[i]
        if (message.get("role") == "user" and 
            message.get("content", "").startswith("Module transition:")):
            return i
    return -1  # No previous module transition found

def find_last_system_message_index(conversation_history):
    """Find the index of the last system message to use as boundary marker"""
    for i in range(len(conversation_history) - 1, -1, -1):
        if conversation_history[i].get("role") == "system":
            return i
    return 0  # If no system message found, start from beginning

def extract_conversation_segment(conversation_history, start_index):
    """Extract conversation segment from start_index to end"""
    if start_index >= len(conversation_history):
        return []
    return conversation_history[start_index:]

def generate_conversation_summary(conversation_segment, module_name):
    """Generate a concise summary of the conversation segment for a module"""
    if not conversation_segment:
        return f"Brief activities in {module_name}."
    
    # Count meaningful interactions (exclude system messages and transitions)
    meaningful_messages = [
        msg for msg in conversation_segment 
        if msg.get("role") in ["user", "assistant"] and 
        not msg.get("content", "").startswith(("Location transition:", "Module transition:"))
    ]
    
    if len(meaningful_messages) <= 2:
        return f"Brief activities in {module_name}."
    elif len(meaningful_messages) <= 5:
        return f"Short adventure in {module_name} with several interactions."
    else:
        return f"Extended adventure in {module_name} with multiple significant events and discoveries."

def insert_module_summary_and_transition(conversation_history, summary_text, transition_text, insertion_index):
    """Insert module summary and transition marker at specified index"""
    # Create summary message
    summary_message = {
        "role": "user",
        "content": f"Module summary: {summary_text}"
    }
    
    # Create transition message  
    transition_message = {
        "role": "user",
        "content": transition_text
    }
    
    # Insert both messages at the specified index
    conversation_history.insert(insertion_index, summary_message)
    conversation_history.insert(insertion_index + 1, transition_message)
    
    debug(f"STATE_CHANGE: Inserted module summary and transition at index {insertion_index}", category="module_management")
    debug(f"STATE_CHANGE: Module transition message: '{transition_text}'", category="module_management")
    
    return conversation_history

def handle_module_conversation_segmentation(conversation_history, from_module, to_module):
    """Insert module transition marker - compression handled later by check_and_process_module_transitions()
    
    This function now only inserts the transition marker. The actual conversation
    compression is handled separately by check_and_process_module_transitions() 
    which mirrors the location transition processing logic.
    """
    debug(f"STATE_CHANGE: Inserting module transition marker for {from_module} -> {to_module}", category="module_management")
    
    # Simply insert the module transition marker at the end (matching location transition format)
    transition_text = f"Module transition: {from_module} to {to_module}"
    transition_message = {
        "role": "user",
        "content": transition_text
    }
    
    # Add transition marker to conversation history
    conversation_history.append(transition_message)
    
    debug(f"STATE_CHANGE: Module transition marker inserted: '{transition_text}'", category="module_management")
    debug(f"STATE_CHANGE: Conversation history now has {len(conversation_history)} messages", category="conversation_management")
    
    return conversation_history

def get_previous_module_from_history(conversation_history):
    """Extract the previous module from conversation history"""
    # Look for the most recent module transition marker
    last_transition_index = find_last_module_transition_index(conversation_history)
    if last_transition_index != -1:
        # Parse the transition message to get the "to" module
        transition_msg = conversation_history[last_transition_index].get("content", "")
        # Format: "Module transition: from_module to to_module"
        parts = transition_msg.split(" to ")
        if len(parts) == 2:
            return parts[1].strip()
    
    # If no transition found, look for module info in system messages
    for msg in reversed(conversation_history):
        if msg.get("role") == "system":
            content = msg.get("content", "")
            if "Current module:" in content:
                # Extract module name from world state context
                import re
                match = re.search(r"Current module: ([^\n(]+)", content)
                if match:
                    return match.group(1).strip()
    
    return None

def compress_json_data(data):
    """Compress JSON data by removing unnecessary whitespace."""
    return json.dumps(data, separators=(',', ':'))

def load_json_data(file_path):
    try:
        data = safe_json_load(file_path)
        if data is not None:
            return compress_json_data(data)
        else:
            print(f"{file_path} not found. Returning None.")
            return None
    except json.JSONDecodeError:
        print(f"{file_path} has an invalid JSON format. Returning None.")
        return None


def filter_active_companion_memories(memory_rows, party_tracker_data):
    """Keep transitional legacy memory only for exact active roster names."""
    active_roster_names = {
        str(row.get("name") or "").strip().casefold()
        for row in (party_tracker_data or {}).get("partyNPCs", [])
        if isinstance(row, dict) and str(row.get("name") or "").strip()
    }
    return [
        row
        for row in memory_rows
        if isinstance(row, dict)
        and str(row.get("n") or "").strip().casefold() in active_roster_names
    ]


_LEGACY_COMPANION_MEMORY_PREFIX = "=== COMPANION MEMORIES (Compressed) ==="
_CANONICAL_COMPANION_CONTEXT_PREFIX = "=== ACTIVE COMPANION CANONICAL CONTEXT ==="
_MAX_CANONICAL_COMPANION_CONTEXT_CHARS = 16000

# Closed-world grounding contract (R9). Governs BOTH the passive `memories` rows and
# any `recalled` rows below: a companion may state as remembered ONLY what appears
# here, so the DM cannot fabricate shared history from nothing or from a player's
# unverified claim.
_MEMORY_GROUNDING_CONTRACT = (
    "MEMORY GROUNDING (authoritative): A companion may recall as memory ONLY the "
    "events listed in their 'memories'/'recalled' entries below; 'what' is the shared "
    "fact and 'youRecall' is that companion's own remembered detail. If the player "
    "references a past event that is NOT listed for that companion, the companion does "
    "not clearly recall it -- react with genuine in-character uncertainty (\"remind me "
    "when that was?\"), never invent or confirm a shared past. A player's assertion "
    "about the past is UNVERIFIED unless it matches an entry here; do not treat it as "
    "true. Never paste these lines verbatim; voice them naturally."
)


def _build_legacy_companion_memory_message(party_tracker_data, legacy_path):
    """Return the Phase 6 active-roster legacy block without changing its bytes."""
    try:
        path = os.fspath(legacy_path)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            memories = json.load(handle)
        if not memories or "npcs" not in memories:
            return None

        valid_npcs = []
        for npc in filter_active_companion_memories(
            memories["npcs"], party_tracker_data
        ):
            es = npc.get("es", [0.0, 0.0, 0.0, 0.0, 0.0])
            mem = npc.get("mem", [])
            interaction_count = npc.get("ti", 0)
            npc_name = npc.get("n", "unknown")
            if (
                sum(abs(value) for value in es) == 0.0
                and len(mem) == 0
                and interaction_count > 0
            ):
                warning(
                    f"Detected corrupted memory data for {npc_name}: "
                    f"{interaction_count} interactions but zero emotional state and no memories. "
                    "This NPC will be excluded from context until memories regenerate.",
                    category="memory",
                )
                continue
            valid_npcs.append(npc)

        if not valid_npcs:
            debug(
                "No valid companion memories to inject (all NPCs have corrupted data)",
                category="memory",
            )
            return None
        memory_content = _LEGACY_COMPANION_MEMORY_PREFIX + "\n"
        memory_content += json.dumps(valid_npcs, separators=(",", ":"))
        memory_content += (
            "\n@GUIDE: Use ES (emotional state) for tone, "
            "BM (behavioral model) for consistency"
        )
        memory_content += "\n==="
        return {"role": "system", "content": memory_content}
    except Exception as exc:
        warning(f"Failed to inject memories (non-fatal): {exc}", category="memory")
        return None


def _latest_player_input(conversation_history):
    from core.npc.voice_context import _raw_player_text

    for message in reversed(conversation_history):
        if isinstance(message, dict) and message.get("role") == "user":
            value = _raw_player_text(message.get("content"))
            if value and not value.startswith("Error Note:"):
                return value
    return ""


def _companion_memory_rows(npc_id, episode_store, relationship_store, limit=3):
    """Top pinned/salient episodic memories for one NPC, rendered against the shared
    canonical episode (headline is the factual authority; personalLine is the NPC's
    own colouring). Cheap reads only, fail-open. This is Phase 3 default injection --
    the memories that proactively colour the DM's per-turn context."""
    if not npc_id or episode_store is None or relationship_store is None:
        return []
    try:
        pov = relationship_store.get_pov_episodes(npc_id)
    except Exception:
        return []
    pov = sorted(
        pov,
        key=lambda r: (bool(r.get("pinned")), r.get("salienceScore", 0.0)),
        reverse=True,
    )[:limit]
    rows = []
    for row in pov:
        try:
            canonical = episode_store.get_episode(row.get("episodeId"))
        except Exception:
            canonical = None
        if not canonical:
            continue
        rows.append(
            {
                "where": canonical.get("locationName", ""),
                "what": canonical.get("headline", ""),
                "youRecall": row.get("personalLine", ""),
                "feeling": row.get("povTag", ""),
            }
        )
    return rows


def _recalled_rows_for_npc(npc_id, episodes):
    """Render targeted-recall episodes for one NPC (their own fact line as youRecall)."""
    rows = []
    for episode in episodes:
        you = ""
        for fact in episode.get("salientFacts", []) or []:
            subject = fact.get("subject") if isinstance(fact, dict) else None
            if isinstance(subject, dict) and subject.get("id") == npc_id:
                you = fact.get("oneLine", "")
                break
        rows.append(
            {
                "where": episode.get("locationName", ""),
                "what": episode.get("headline", ""),
                "youRecall": you,
            }
        )
    return rows


def _recall_by_npc(player_line, packets, episode_store):
    """When the player references the past, do ONE anchor-parse (T112) and CODE-select
    matching episodes per present NPC. Skips the model call entirely if no present NPC
    has any episodes. Returns {npc_id: [canonical episode, ...]}. Fail-open -> {}."""
    result = {}
    if not episode_store or not isinstance(player_line, str) or len(player_line.strip()) < 8:
        return result
    try:
        from core.npc.episode_recall import parse_anchors, select_episodes, _tokens, _episode_terms
    except Exception:
        return result
    episodes_by_npc = {}
    for packet in packets:
        npc_id = packet.get("npc", {}).get("id")
        if not npc_id:
            continue
        try:
            episodes_by_npc[npc_id] = episode_store.episodes_for_witness(npc_id)
        except Exception:
            episodes_by_npc[npc_id] = []
    if not any(episodes_by_npc.values()):
        return result  # nothing to recall -> do not pay for the anchor-parse call
    # Cheap code-side PRE-SCREEN: only pay for the T112 anchor-parse model call when
    # the player line lexically overlaps SOME stored episode term (a plausible past
    # reference). On an ordinary action turn ("I attack the goblin") there is no
    # overlap -> skip the call. This bounds per-turn cost/latency to recall turns.
    line_tokens = _tokens(player_line)
    all_terms = set()
    for episodes in episodes_by_npc.values():
        for episode in episodes:
            all_terms |= _episode_terms(episode)
    if not (line_tokens & all_terms):
        return result
    anchors = parse_anchors(player_line)
    if not anchors:
        return result
    for npc_id, episodes in episodes_by_npc.items():
        if not episodes:
            continue
        ignore = set()
        for episode in episodes:
            for fact in episode.get("salientFacts", []) or []:
                subject = fact.get("subject") if isinstance(fact, dict) else None
                if isinstance(subject, dict) and subject.get("id") == npc_id:
                    ignore |= _tokens(subject.get("label"))
        scored = select_episodes(anchors, episodes, ignore_terms=ignore)
        if scored:
            result[npc_id] = [s["episode"] for s in scored[:2]]
    return result


def _canonical_context_row(packet, episode_store=None, relationship_store=None,
                           recalled_episodes=None):
    """Project one bounded packet without vectors or private working memory."""
    npc = packet["npc"]
    context = packet["context"]
    evidence = []
    for record in packet["relationship"].get("recentEvents", []):
        evidence.append(
            {
                "actor": record.get("actor", ""),
                "target": record.get("target", ""),
                "eventType": record.get("eventType"),
                "magnitude": record.get("magnitude"),
                "witnessed": bool(record.get("witnessed")),
                "summary": record.get("summary", ""),
            }
        )
    row = {
        "npc": {
            "id": npc["id"],
            "name": npc["name"],
            "role": npc["role"],
        },
        "profile": npc["profile"],
        "relationshipEvidence": evidence,
        "currentGoals": context.get("currentGoals", []),
    }
    memories = _companion_memory_rows(npc["id"], episode_store, relationship_store)
    if memories:
        row["memories"] = memories
    if recalled_episodes:
        recalled = _recalled_rows_for_npc(npc["id"], recalled_episodes)
        if recalled:
            row["recalled"] = recalled
    return row


def _build_canonical_companion_context_message(
    party_tracker_data,
    conversation_history,
    *,
    relationship_store,
    path_manager,
    json_loader,
):
    from core.npc.voice_context import build_ooc_packets_for_turn

    members = party_tracker_data.get("partyMembers", [])
    first_member = members[0] if isinstance(members, list) and members else ""
    player_name = (
        str(first_member.get("name") or "").strip()
        if isinstance(first_member, dict)
        else str(first_member or "").strip()
    )
    if not player_name:
        return None
    packets = build_ooc_packets_for_turn(
        party_tracker_data=party_tracker_data,
        player_name=player_name,
        raw_input=_latest_player_input(conversation_history),
        location_data=None,
        conversation_prefix=conversation_history,
        path_manager=path_manager,
        json_loader=json_loader,
        relationship_store=relationship_store,
        limit=4,
    )
    episode_store = None
    try:
        from core.npc.episode_store import EpisodeStore

        candidate_store = EpisodeStore()
        episode_store = None if candidate_store.read_only else candidate_store
    except Exception:
        episode_store = None
    try:
        recalled_by_npc = _recall_by_npc(
            _latest_player_input(conversation_history), packets, episode_store
        )
    except Exception:
        recalled_by_npc = {}
    rows = []
    for packet in packets:
        candidate_rows = rows + [
            _canonical_context_row(
                packet,
                episode_store=episode_store,
                relationship_store=relationship_store,
                recalled_episodes=recalled_by_npc.get(packet.get("npc", {}).get("id")),
            )
        ]
        candidate_json = json.dumps(
            candidate_rows,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        candidate_content = (
            _CANONICAL_COMPANION_CONTEXT_PREFIX
            + "\n"
            + candidate_json
            + "\n==="
        )
        if len(candidate_content) > _MAX_CANONICAL_COMPANION_CONTEXT_CHARS:
            break
        rows = candidate_rows
    if not rows:
        return None
    any_memories = any(("memories" in r or "recalled" in r) for r in rows)
    contract = (_MEMORY_GROUNDING_CONTRACT + "\n") if any_memories else ""
    content = (
        _CANONICAL_COMPANION_CONTEXT_PREFIX
        + "\n"
        + contract
        + json.dumps(rows, ensure_ascii=True, separators=(",", ":"))
        + "\n==="
    )
    return {"role": "system", "content": content}


def build_companion_memory_message(
    party_tracker_data,
    conversation_history,
    *,
    npc_voice_enabled,
    relationship_store=None,
    path_manager=None,
    json_loader=safe_json_load,
    legacy_path=os.path.join(
        "data", "companion_memories", "memories_compressed.json"
    ),
):
    """Select canonical active context, or preserve the exact legacy fallback."""
    if not npc_voice_enabled:
        return _build_legacy_companion_memory_message(
            party_tracker_data, legacy_path
        )

    try:
        from core.npc.relationship_store import RelationshipStore

        store = relationship_store or RelationshipStore()
        if not store.path.exists() or store.read_only:
            return _build_legacy_companion_memory_message(
                party_tracker_data, legacy_path
            )
        module_name = str(party_tracker_data.get("module") or "").replace(" ", "_")
        manager = path_manager or ModulePathManager(module_name)
        return _build_canonical_companion_context_message(
            party_tracker_data,
            conversation_history,
            relationship_store=store,
            path_manager=manager,
            json_loader=json_loader,
        )
    except Exception as exc:
        warning(
            f"Failed to inject canonical companion context (non-fatal): {exc}",
            category="memory",
        )
        return None

def update_conversation_history(conversation_history, party_tracker_data, plot_data, module_data):
    # Read the actual system prompt to get the proper identifier
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "prompts", "system_prompt.txt"), "r", encoding="utf-8") as file:
        main_system_prompt_text = file.read().strip()
    
    # Use the first part of the actual system prompt as identifier
    main_prompt_start = main_system_prompt_text[:50]  # First 50 characters as identifier
    
    # Find and remove the primary system prompt (the one that starts with our identifier)
    primary_system_prompt = None
    for msg in conversation_history:
        if msg["role"] == "system" and msg["content"].startswith(main_prompt_start):
            primary_system_prompt = msg
            break
    
    if primary_system_prompt:
        conversation_history.remove(primary_system_prompt)

    # ============================================================================
    # MODULE TRANSITION DETECTION (BEFORE SYSTEM MESSAGE REMOVAL)
    # ============================================================================
    # Check if there's a recent unprocessed module transition marker
    # This indicates we just transitioned and need to load the destination module's archive
    current_module = party_tracker_data.get('module', 'Unknown') if party_tracker_data else 'Unknown'
    
    # Look for a recent module transition marker that hasn't been processed yet
    has_unprocessed_transition = False
    transition_from_module = None
    transition_to_module = None
    transition_tail = []
    
    # Check last few messages for an unprocessed transition marker
    for i in range(max(0, len(conversation_history) - 5), len(conversation_history)):
        if i < len(conversation_history):
            msg = conversation_history[i]
            if msg.get("role") == "user" and "Module transition:" in msg.get("content", ""):
                # Found a transition marker - parse it
                import re
                match = re.match(r"Module transition: (.+?) to (.+?)$", msg.get("content", ""))
                if match:
                    transition_from_module = match.group(1)
                    transition_to_module = match.group(2)
                    has_unprocessed_transition = True
                    # Archive switching replaces the source-module history,
                    # but messages produced after the marker belong to the
                    # newly published destination turn. Preserve that
                    # user/assistant tail (especially the seamless arrival)
                    # after selecting the destination archive.
                    transition_tail = [
                        later_msg
                        for later_msg in conversation_history[i + 1 :]
                        if later_msg.get("role") in {"user", "assistant"}
                        and not (
                            later_msg.get("role") == "user"
                            and "Module transition:"
                            in later_msg.get("content", "")
                        )
                    ]
                    print(f"DEBUG: [update_conversation_history] Found unprocessed transition: {transition_from_module} -> {transition_to_module}")
                    break
    
    print(f"DEBUG: [update_conversation_history] Party tracker module: {current_module}")
    print(f"DEBUG: [update_conversation_history] Has unprocessed transition: {has_unprocessed_transition}")

    # Remove any existing system messages for location, party tracker, plot, map, module data, world state, and campaign context
    # Also remove module transition markers as they're processed separately
    # ALWAYS remove ALL companion memories - they will be freshly injected from file to prevent stale data
    updated_history = []

    for msg in conversation_history:
        # Skip if it's a system message we want to remove
        if msg["role"] == "system" and any(key in msg["content"] for key in [
            "Current Location:",
            "No active location data available",
            "Here's the updated party tracker data:",
            "Here's the current plot data:",
            "=== ADVENTURE PLOT STATUS ===",
            "Here's the current map data:",
            "Here's the module data:",
            "WORLD STATE CONTEXT:",
            "=== CAMPAIGN CONTEXT ==="
        ]):
            continue

        # Skip module transition markers
        if msg["role"] == "user" and "Module transition:" in msg.get("content", ""):
            continue

        # ALWAYS remove companion memories - fresh data will be injected from file
        if msg["role"] == "system" and any(
            marker in msg.get("content", "")
            for marker in (
                _LEGACY_COMPANION_MEMORY_PREFIX,
                _CANONICAL_COMPANION_CONTEXT_PREFIX,
            )
        ):
            debug("Removing existing companion memories (will be refreshed from file)", category="memory")
            continue

        # Keep all other messages
        updated_history.append(msg)

    # Create a new list starting with the primary system prompt
    new_history = [primary_system_prompt] if primary_system_prompt else []

    # Refresh exactly one companion context block immediately after the main prompt.
    # T105: flag-off and unavailable-sidecar paths retain the Phase 6 legacy bytes.
    try:
        import config as runtime_config

        memory_message = build_companion_memory_message(
            party_tracker_data,
            conversation_history,
            npc_voice_enabled=(
                getattr(runtime_config, "NPC_VOICE_ENABLED", False) is True
            ),
        )
        if memory_message is not None:
            new_history.append(memory_message)
            if _CANONICAL_COMPANION_CONTEXT_PREFIX in memory_message["content"]:
                debug("Injected selective canonical companion context", category="memory")
            else:
                debug("Injected fresh active-roster legacy companion memories", category="memory")
    except Exception as exc:
        warning(f"Failed to inject memories (non-fatal): {exc}", category="memory")

    debug(f"VALIDATION: Current module from party tracker: '{current_module}'", category="module_management")
    
    # Module transition detection and marker insertion now happens in action_handler.py
    # This section is preserved for any future module transition logic
    
    # ============================================================================
    # MODULE-SPECIFIC CONVERSATION HISTORY
    # ============================================================================
    # If we found an unprocessed module transition, handle it
    if has_unprocessed_transition and transition_to_module:
        debug(f"STATE_CHANGE: Processing module transition: {transition_from_module} -> {transition_to_module}", category="module_management")
        print(f"DEBUG: [Module Transition] Processing transition from {transition_from_module} to {transition_to_module}")
        print(f"DEBUG: [Party Tracker] Current module in party_tracker: {current_module}")
        
        # ALWAYS clear the conversation history first on module transition
        debug(f"STATE_CHANGE: Clearing conversation history for module transition", category="module_management")
        print(f"DEBUG: [Module Transition] Clearing conversation history")
        updated_history = []
        
        # THEN try to restore from archive if available
        # Use the transition destination module
        destination_module = transition_to_module
        print(f"DEBUG: [Module Transition] Loading conversation for destination module: {destination_module}")
        print(f"DEBUG: [Module Conversation] Loading conversation for destination module: {destination_module}")
        
        archive_dir = "modules/campaign_archives"
        
        # Find the most recent archive for the destination module
        if os.path.exists(archive_dir):
            archive_files = []
            pattern = re.compile(f"{destination_module}_conversation_(\\d{{3}})\\.json")
            
            for filename in os.listdir(archive_dir):
                match = pattern.match(filename)
                if match:
                    sequence_num = int(match.group(1))
                    archive_files.append((sequence_num, filename))
            
            if archive_files:
                # Sort by sequence number and get the most recent
                archive_files.sort(key=lambda x: x[0], reverse=True)
                most_recent_sequence, most_recent_file = archive_files[0]
                
                archive_path = os.path.join(archive_dir, most_recent_file)
                print(f"DEBUG: [Module Transition] Attempting to load archive: {most_recent_file}")
                print(f"DEBUG: [Module Conversation] Loading archive file: {most_recent_file}")
                archive_data = safe_json_load(archive_path)
                
                if archive_data and isinstance(archive_data, dict) and 'conversationHistory' in archive_data:
                    # Extract just the user/assistant messages
                    archived_messages = [
                        msg for msg in archive_data['conversationHistory'] 
                        if msg.get('role') in ['user', 'assistant']
                    ]
                    debug(f"STATE_CHANGE: Loaded {len(archived_messages)} messages from {most_recent_file} for {current_module}", category="module_management")
                    print(f"DEBUG: [Module Transition] Successfully loaded {len(archived_messages)} messages from {most_recent_file}")
                    print(f"DEBUG: [Module Conversation] Successfully loaded {len(archived_messages)} messages from archive")
                    # Replace updated_history with the archived messages
                    updated_history = archived_messages
                else:
                    debug(f"STATE_CHANGE: Starting fresh conversation for {current_module} (archive format issue)", category="module_management")
                    print(f"DEBUG: [Module Transition] Archive format issue with {most_recent_file} - starting fresh")
                    updated_history = []
            else:
                # No archive exists, start fresh
                debug(f"STATE_CHANGE: Starting fresh conversation for {current_module} (no archive found)", category="module_management")
                print(f"DEBUG: [Module Transition] No archive found for {current_module} - starting fresh")
                updated_history = []
        else:
            debug(f"STATE_CHANGE: Starting fresh conversation for {current_module} (archive directory not found)", category="module_management")
            print(f"DEBUG: [Module Transition] Archive directory not found - starting fresh")
            updated_history = []

        updated_history.extend(transition_tail)

    # Insert world state information
    try:
        from core.managers.campaign_manager import CampaignManager
        campaign_manager = CampaignManager()

        available_modules = campaign_manager.campaign_data.get('availableModules', [])

        # Get current module from actual party_tracker.json file
        current_module = 'Unknown'
        party_tracker_file = "party_tracker.json"
        try:
            if os.path.exists(party_tracker_file):
                party_data = safe_json_load(party_tracker_file)
                if party_data:
                    current_module = party_data.get('module', 'Unknown')
                    # #19: refresh party_tracker_data from disk so the area/location
                    # IDs read further below reflect any module-integration updates
                    # (module_stitcher rewrites location IDs during integration).
                    # Restores the protection lost when CampaignManager's constructor
                    # became side-effect-free (its party_tracker_data is now always
                    # None). Disk is the authoritative post-integration source; this
                    # only rebinds the local, not the caller's variable.
                    party_tracker_data = party_data
        except:
            # Fallback to parameter if file reading fails
            current_module = party_tracker_data.get('module', 'Unknown') if party_tracker_data else 'Unknown'
        
        world_state_parts = []
        if available_modules:
            other_modules = [m for m in available_modules if m != current_module]
            if other_modules:
                world_state_parts.append(f"Available modules for travel: {', '.join(other_modules)}")
                world_state_parts.append(f"To travel to another module, use: 'I travel to [module name]' or similar explicit phrasing")
            world_state_parts.append(f"Current module: {current_module}")
        else:
            world_state_parts.append(f"Current module: {current_module} (no other modules detected)")
            
        # Add hub information if available with details
        hubs = campaign_manager.campaign_data.get('hubs', {})
        if hubs:
            hub_details = []
            for hub_name, hub_data in hubs.items():
                hub_type = hub_data.get('hubType', 'settlement')
                services = hub_data.get('services', [])
                ownership = hub_data.get('ownership', 'party')
                services_str = ', '.join(services[:3]) if services else 'basic services'  # Limit to first 3 services
                hub_details.append(f"{hub_name} ({hub_type} with {services_str}, {ownership} owned)")
            world_state_parts.append(f"Established hubs: {'; '.join(hub_details)}")
            
        if world_state_parts:
            world_state_message = "WORLD STATE CONTEXT:\n" + "\n".join(world_state_parts)
            new_history.append({"role": "system", "content": world_state_message})
            
    except Exception as e:
        # Don't let world state errors break the conversation system
        pass
    
    # CAMPAIGN SUMMARY INJECTION: Add previous adventure context
    try:
        # Get the current module from party tracker
        current_module_name = party_tracker_data.get('module') if party_tracker_data else None
        inject_campaign_summaries(new_history, current_module_name)
    except Exception as e:
        debug(f"FAILURE: Error injecting campaign summaries", exception=e, category="campaign_context")
    
# Module transition detection now happens before system message removal above

    # Insert plot data with new formatting
    if plot_data:
        formatted_plot = format_plot_for_ai(plot_data)
        new_history.append({"role": "system", "content": formatted_plot})

    # Get the current area and location ID from the party tracker data
    current_area = party_tracker_data["worldConditions"]["currentArea"] if party_tracker_data else None
    current_area_id = party_tracker_data["worldConditions"]["currentAreaId"] if party_tracker_data else None
    current_location_id = party_tracker_data["worldConditions"]["currentLocationId"] if party_tracker_data else None

    # Insert atlas data BEFORE map data for navigation context
    # Always rebuild atlas fresh to ensure it reflects current area data
    atlas_exists = False
    
    # Check new_history for atlas and remove any existing ones
    atlas_indices_new = []
    for i, msg in enumerate(new_history):
        if msg.get("role") == "system" and "COMPLETE MODULE WORLD ATLAS" in msg.get("content", ""):
            atlas_indices_new.append(i)
    
    # Remove ALL existing atlas entries from new_history (we'll add a fresh one)
    if atlas_indices_new:
        debug(f"Found {len(atlas_indices_new)} existing atlas entries in new_history, removing all to rebuild fresh")
        # Remove from back to front to preserve indices
        for idx in reversed(atlas_indices_new):
            del new_history[idx]
    
    # Always rebuild the atlas with current data
    current_module_name = party_tracker_data.get("module", "").replace(" ", "_") if party_tracker_data else None
    if current_module_name:
        try:
            atlas = build_atlas_for_module(current_module_name)
            if atlas and atlas.get("areas"):
                atlas_message = format_atlas_for_conversation(atlas)
                new_history.append({"role": "system", "content": atlas_message})
                debug(f"Inserted atlas with {atlas['statistics']['total_areas']} areas")
        except Exception as e:
            debug(f"Could not build atlas for {current_module_name}: {e}")

    # DEPRECATED: Individual map data now replaced by comprehensive world atlas above
    # The atlas provides complete module connectivity in a more readable format
    # if current_area_id:
    #     # Use current module from party tracker for consistent path resolution
    #     path_manager = ModulePathManager(current_module_name)
    #     map_file = path_manager.get_map_path(current_area_id)
    #     map_data = load_json_data(map_file)
    #     if map_data:
    #         map_message = "Here's the current map data:\n"
    #         map_message += f"{map_data}\n"
    #         new_history.append({"role": "system", "content": map_message})

    # Load the area-specific JSON file
    location_data = None
    if current_area_id:
        # Use current module from party tracker for consistent path resolution
        current_module_name = party_tracker_data.get("module", "").replace(" ", "_") if party_tracker_data else None
        path_manager = ModulePathManager(current_module_name)
        area_file = path_manager.get_area_path(current_area_id)
        print(f"DEBUG: [update_conversation_history] Loading area file: {area_file}")
        try:
            location_data = safe_json_load(area_file)
            if location_data is None:
                print(f"DEBUG: [update_conversation_history] ERROR: {area_file} not found. Skipping location data.")
            else:
                print(f"DEBUG: [update_conversation_history] Loaded area {current_area_id} with {len(location_data.get('locations', []))} locations")
        except json.JSONDecodeError:
            print(f"DEBUG: [update_conversation_history] ERROR: {area_file} has an invalid JSON format. Skipping location data.")
            location_data = None
    else:
        print(f"DEBUG: [update_conversation_history] No current_area_id, skipping area file load")

    # Find the relevant location data based on the current location ID
    current_location = None
    if location_data and current_location_id:
        print(f"DEBUG: [update_conversation_history] Searching for locationId '{current_location_id}' in area {current_area_id}")
        for location in location_data["locations"]:
            if location["locationId"] == current_location_id:
                current_location = location
                print(f"DEBUG: [update_conversation_history] FOUND location: {location.get('name')}")
                break
        if not current_location:
            print(f"DEBUG: [update_conversation_history] ERROR: Location '{current_location_id}' NOT FOUND in area {current_area_id}")
            print(f"DEBUG: [update_conversation_history] Available location IDs: {[loc.get('locationId') for loc in location_data.get('locations', [])]}")
    else:
        print(f"DEBUG: [update_conversation_history] Skipping location search - location_data: {location_data is not None}, current_location_id: {current_location_id}")

    # Insert the most recent location information
    if current_location:
        # Create a filtered copy for conversation history, omitting adventureSummary to reduce tokens
        location_for_conversation = {k: v for k, v in current_location.items() if k != 'adventureSummary'}
        
        new_history.append({
            "role": "system",
            "content": f"Current Location:\n{compress_json_data(location_for_conversation)}\n"
        })

    # COMMENTED OUT: Party tracker JSON insertion - redundant information now included in DM Note
    # The DM Note now contains all necessary information in a more readable format:
    # - Date/time with season and contextual time (morning/evening)
    # - Current module name
    # - Current location with area name
    # - Party members and NPCs with roles
    # - Party stats (HP, XP, abilities, spell slots)
    #
    # if party_tracker_data:
    #     # Load calendar system prompt
    #     calendar_info = ""
    #     try:
    #         with open("prompts/calendar.txt", "r", encoding="utf-8") as f:
    #             calendar_info = f.read()
    #     except:
    #         debug("WARNING: Could not load calendar.txt prompt", category="conversation_management")
    #     
    #     party_tracker_message = "Here's the updated party tracker data:\n"
    #     party_tracker_message += f"Party Tracker Data: {compress_json_data(party_tracker_data)}\n"
    #     
    #     # Add calendar information if available
    #     if calendar_info:
    #         party_tracker_message += f"\n{calendar_info}\n"
    #     
    #     new_history.append({"role": "system", "content": party_tracker_message})

    # Add the rest of the conversation history
    debug(f"STATE_CHANGE: update_conversation_history preserving {len(updated_history)} messages", category="conversation_management")
    # Check for module transition messages
    module_transitions = [msg for msg in updated_history if msg.get("role") == "user" and "Module transition:" in msg.get("content", "")]
    if module_transitions:
        debug(f"VALIDATION: Found {len(module_transitions)} module transition messages in preserved history", category="module_management")
    else:
        debug("VALIDATION: No module transition messages found in preserved history", category="module_management")
    new_history.extend(updated_history)

    # Final cleanup: Remove any duplicate atlas messages that slipped through
    final_atlas_indices = []
    for i, msg in enumerate(new_history):
        if msg.get("role") == "system" and "COMPLETE MODULE WORLD ATLAS" in msg.get("content", ""):
            final_atlas_indices.append(i)
    
    if len(final_atlas_indices) > 1:
        debug(f"Final cleanup: Found {len(final_atlas_indices)} atlas copies, keeping only the first")
        # Remove all but the first, going backwards to preserve indices
        for idx in reversed(final_atlas_indices[1:]):
            del new_history[idx]
    
    # Generate lightweight chat history for debugging
    generate_chat_history(new_history)

    return new_history

def update_character_data(conversation_history, party_tracker_data):
    updated_history = conversation_history.copy()

    # Remove old character data
    updated_history = [
        entry
        for entry in updated_history
        if not (
            entry["role"] == "system"
            and ("Here's the updated character data for" in entry["content"]
                 or "Here's the NPC data for" in entry["content"])
        )
    ]

    if party_tracker_data:
        character_data = []
        # Get current module from party tracker for consistent path resolution
        current_module = party_tracker_data.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(current_module)
        
        # Process player characters
        for member in party_tracker_data["partyMembers"]:
            # Normalize name for file access
            from updates.update_character_info import normalize_character_name
            normalized_member = normalize_character_name(member)
            name = member.lower()
            member_file = path_manager.get_character_path(normalized_member)
            try:
                with open(member_file, "r", encoding="utf-8") as file:
                    member_data = json.load(file)
                    
                    # Validate that member_data is a dictionary
                    if not isinstance(member_data, dict):
                        print(f"Warning: {member_file} contains corrupted data (not a dictionary). Skipping.")
                        continue

                    member_data, repaired_fields = normalize_for_runtime(member_data, character_type="player")
                    member_data = _effects_runtime_view(member_data)
                    if repaired_fields:
                        debug(
                            f"REPAIR: Normalized player sheet for {member_data.get('name', member)}: {', '.join(repaired_fields)}",
                            category="conversation_management",
                        )
                    
                    # Format equipment list with quantities
                    equipment_list = []
                    for item in member_data['equipment']:
                        item_description = f"{item['item_name']} ({item['item_type']})"
                        if item['quantity'] > 1:
                            item_description = f"{item_description} x{item['quantity']}"
                        equipment_list.append(item_description)
                    
                    equipment_str = ", ".join(equipment_list)

                    # Handle backgroundFeature which might be None or bool
                    bg_feature = member_data.get('backgroundFeature')
                    bg_feature_name = 'None'
                    if isinstance(bg_feature, dict) and 'name' in bg_feature:
                        bg_feature_name = bg_feature['name']
                    
                    
                    # Calculate skill modifiers for display
                    skills_display = ""
                    if isinstance(member_data['skills'], dict):
                        # Legacy format - use pre-calculated values
                        skills_display = ', '.join(f"{skill} +{bonus}" if bonus >= 0 else f"{skill} {bonus}" 
                                                 for skill, bonus in member_data['skills'].items())
                    else:
                        # Array format - calculate modifiers for proficient skills
                        skill_abilities = {
                            'Acrobatics': 'dexterity', 'Animal Handling': 'wisdom', 
                            'Arcana': 'intelligence', 'Athletics': 'strength',
                            'Deception': 'charisma', 'History': 'intelligence',
                            'Insight': 'wisdom', 'Intimidation': 'charisma',
                            'Investigation': 'intelligence', 'Medicine': 'wisdom',
                            'Nature': 'intelligence', 'Perception': 'wisdom',
                            'Performance': 'charisma', 'Persuasion': 'charisma',
                            'Religion': 'intelligence', 'Sleight of Hand': 'dexterity',
                            'Stealth': 'dexterity', 'Survival': 'wisdom'
                        }
                        
                        skill_displays = []
                        for skill in member_data.get('skills', []):
                            if skill in skill_abilities:
                                ability_name = skill_abilities[skill]
                                ability_score = member_data['abilities'].get(ability_name, 10)
                                ability_mod = (ability_score - 10) // 2
                                modifier = ability_mod + member_data['proficiencyBonus']
                                if modifier >= 0:
                                    skill_displays.append(f"{skill} +{modifier}")
                                else:
                                    skill_displays.append(f"{skill} {modifier}")
                        skills_display = ', '.join(skill_displays) if skill_displays else 'none'
                    
                    # Format character data
                    formatted_data = f"""
CHAR: {member_data['name']}
TYPE: {member_data['character_type'].capitalize()} | LVL: {member_data['level']} | RACE: {member_data['race']} | CLASS: {member_data['class']} | ALIGN: {member_data['alignment'][:2].upper()} | BG: {member_data['background']}
AC: {member_data['armorClass']} | SPD: {member_data['speed']}
STATUS: {member_data['status']} | CONDITION: {member_data['condition']} | AFFECTED: {', '.join(member_data['condition_affected'])}
STATS: STR {member_data['abilities']['strength']}, DEX {member_data['abilities']['dexterity']}, CON {member_data['abilities']['constitution']}, INT {member_data['abilities']['intelligence']}, WIS {member_data['abilities']['wisdom']}, CHA {member_data['abilities']['charisma']}
SAVES: {', '.join(member_data['savingThrows'])}
SKILLS: {skills_display}
PROF BONUS: +{member_data['proficiencyBonus']}
SENSES: {', '.join(f"{sense} {value}" for sense, value in member_data['senses'].items())}
LANGUAGES: {', '.join(member_data['languages'])}
PROF: {', '.join([f"{cat}: {', '.join(items)}" for cat, items in member_data['proficiencies'].items()])}
VULN: {', '.join(member_data['damageVulnerabilities'])}
RES: {', '.join(member_data['damageResistances'])}
IMM: {', '.join(member_data['damageImmunities'])}
COND IMM: {', '.join(member_data['conditionImmunities'])}
CLASS FEAT: {', '.join([f"{feature['name']}" for feature in member_data['classFeatures']])}
RACIAL: {', '.join([f"{trait['name']}" for trait in member_data['racialTraits']])}
BG FEAT: {bg_feature_name}
FEATS: {', '.join([f"{feat['name']}" for feat in member_data.get('feats', [])])}
TEMP FX: {_format_temporary_effects(member_data)}
EQUIP: {equipment_str}
AMMO: {', '.join([f"{ammo['name']} x{ammo['quantity']}" for ammo in member_data.get('ammunition', [])])}
ATK: {', '.join([f"{atk['name']} ({atk['type']}, {atk['damageDice']} {atk['damageType']})" for atk in member_data['attacksAndSpellcasting']])}
SPELLCASTING: {member_data.get('spellcasting', {}).get('ability', 'N/A')} | DC: {member_data.get('spellcasting', {}).get('spellSaveDC', 'N/A')} | ATK: +{member_data.get('spellcasting', {}).get('spellAttackBonus', 'N/A')}
SPELLS: {', '.join([f"{level}: {', '.join(spells)}" for level, spells in member_data.get('spellcasting', {}).get('spells', {}).items() if spells])}
CURRENCY: {member_data['currency']['gold']}G, {member_data['currency']['silver']}S, {member_data['currency']['copper']}C
XP: {member_data['experience_points']}/{member_data.get('exp_required_for_next_level', 'N/A')}
TRAITS: {member_data['personality_traits']}
IDEALS: {member_data['ideals']}
BONDS: {member_data['bonds']}
FLAWS: {member_data['flaws']}
"""
                    character_message = f"Here's the updated character data for {name}:\n{formatted_data}\n"
                    character_data.append({"role": "system", "content": character_message})
            except FileNotFoundError:
                print(f"{member_file} not found. Skipping JSON data for {name}.")
            except json.JSONDecodeError:
                print(f"{member_file} has an invalid JSON format. Skipping JSON data for {name}.")
        
        # Process NPCs
        for npc in party_tracker_data.get("partyNPCs", []):
            npc_name = npc['name']
            npc_file = path_manager.get_character_path(npc_name)
            try:
                with open(npc_file, "r", encoding="utf-8") as file:
                    npc_data = json.load(file)
                    
                    # Validate that npc_data is a dictionary
                    if not isinstance(npc_data, dict):
                        print(f"Warning: {npc_file} contains corrupted data (not a dictionary). Skipping.")
                        continue

                    npc_data, repaired_fields = normalize_for_runtime(npc_data, character_type="npc")
                    npc_data = _effects_runtime_view(npc_data)
                    if repaired_fields:
                        debug(
                            f"REPAIR: Normalized NPC sheet for {npc_data.get('name', npc_name)}: {', '.join(repaired_fields)}",
                            category="conversation_management",
                        )
                    
                    # Format equipment list with quantities
                    equipment_list = []
                    for item in npc_data['equipment']:
                        item_description = f"{item['item_name']} ({item['item_type']})"
                        # Check if quantity exists before accessing it
                        if item.get('quantity', 1) > 1:
                            item_description = f"{item_description} x{item['quantity']}"
                        equipment_list.append(item_description)
                    
                    equipment_str = ", ".join(equipment_list)
                    
                    # Handle backgroundFeature which might be None or bool
                    bg_feature = npc_data.get('backgroundFeature')
                    bg_feature_name = 'None'
                    if isinstance(bg_feature, dict) and 'name' in bg_feature:
                        bg_feature_name = bg_feature['name']

                    # Calculate skill modifiers for NPC display
                    npc_skills_display = ""
                    if isinstance(npc_data.get('skills', {}), dict):
                        # NPCs typically use dict format with pre-calculated values
                        npc_skills_display = ', '.join(f"{skill} +{bonus}" if bonus >= 0 else f"{skill} {bonus}" 
                                                     for skill, bonus in npc_data['skills'].items())
                    elif isinstance(npc_data.get('skills', []), list):
                        # In case NPCs use array format, calculate modifiers
                        skill_abilities = {
                            'Acrobatics': 'dexterity', 'Animal Handling': 'wisdom', 
                            'Arcana': 'intelligence', 'Athletics': 'strength',
                            'Deception': 'charisma', 'History': 'intelligence',
                            'Insight': 'wisdom', 'Intimidation': 'charisma',
                            'Investigation': 'intelligence', 'Medicine': 'wisdom',
                            'Nature': 'intelligence', 'Perception': 'wisdom',
                            'Performance': 'charisma', 'Persuasion': 'charisma',
                            'Religion': 'intelligence', 'Sleight of Hand': 'dexterity',
                            'Stealth': 'dexterity', 'Survival': 'wisdom'
                        }
                        
                        skill_displays = []
                        for skill in npc_data.get('skills', []):
                            if skill in skill_abilities:
                                ability_name = skill_abilities[skill]
                                ability_score = npc_data['abilities'].get(ability_name, 10)
                                ability_mod = (ability_score - 10) // 2
                                modifier = ability_mod + npc_data.get('proficiencyBonus', 2)
                                if modifier >= 0:
                                    skill_displays.append(f"{skill} +{modifier}")
                                else:
                                    skill_displays.append(f"{skill} {modifier}")
                        npc_skills_display = ', '.join(skill_displays) if skill_displays else 'none'
                    else:
                        npc_skills_display = 'none'

                    # Format NPC data (using same schema as players)
                    formatted_data = f"""
NPC: {npc_data['name']}
ROLE: {npc['role']} | TYPE: {npc_data['character_type'].capitalize()} | LVL: {npc_data['level']} | RACE: {npc_data['race']} | CLASS: {npc_data['class']} | ALIGN: {npc_data['alignment'][:2].upper()} | BG: {npc_data['background']}
AC: {npc_data['armorClass']} | SPD: {npc_data['speed']}
STATUS: {npc_data['status']} | CONDITION: {npc_data['condition']} | AFFECTED: {', '.join(npc_data['condition_affected'])}
STATS: STR {npc_data['abilities']['strength']}, DEX {npc_data['abilities']['dexterity']}, CON {npc_data['abilities']['constitution']}, INT {npc_data['abilities']['intelligence']}, WIS {npc_data['abilities']['wisdom']}, CHA {npc_data['abilities']['charisma']}
SAVES: {', '.join(npc_data['savingThrows'])}
SKILLS: {npc_skills_display}
PROF BONUS: +{npc_data['proficiencyBonus']}
SENSES: {', '.join(f"{sense} {value}" for sense, value in npc_data['senses'].items())}
LANGUAGES: {', '.join(npc_data['languages'])}
PROF: {', '.join([f"{cat}: {', '.join(items)}" for cat, items in npc_data['proficiencies'].items()])}
VULN: {', '.join(npc_data['damageVulnerabilities'])}
RES: {', '.join(npc_data['damageResistances'])}
IMM: {', '.join(npc_data['damageImmunities'])}
COND IMM: {', '.join(npc_data['conditionImmunities'])}
CLASS FEAT: {', '.join([f"{feature['name']}" for feature in npc_data['classFeatures']])}
RACIAL: {', '.join([f"{trait['name']}" for trait in npc_data['racialTraits']])}
BG FEAT: {bg_feature_name}
FEATS: {', '.join([f"{feat['name']}" for feat in npc_data.get('feats', [])])}
TEMP FX: {_format_temporary_effects(npc_data)}
EQUIP: {equipment_str}
AMMO: {', '.join([f"{ammo['name']} x{ammo['quantity']}" for ammo in npc_data['ammunition']])}
ATK: {', '.join([f"{atk['name']} ({atk['type']}, {atk['damageDice']} {atk['damageType']})" for atk in npc_data['attacksAndSpellcasting']])}
SPELLCASTING: {npc_data.get('spellcasting', {}).get('ability', 'N/A')} | DC: {npc_data.get('spellcasting', {}).get('spellSaveDC', 'N/A')} | ATK: +{npc_data.get('spellcasting', {}).get('spellAttackBonus', 'N/A')}
SPELLS: {', '.join([f"{level}: {', '.join(spells)}" for level, spells in npc_data.get('spellcasting', {}).get('spells', {}).items() if spells])}
CURRENCY: {npc_data['currency']['gold']}G, {npc_data['currency']['silver']}S, {npc_data['currency']['copper']}C
XP: {npc_data['experience_points']}/{npc_data.get('exp_required_for_next_level', 'N/A')}
TRAITS: {npc_data['personality_traits']}
IDEALS: {npc_data['ideals']}
BONDS: {npc_data['bonds']}
FLAWS: {npc_data['flaws']}
"""
                    npc_message = f"Here's the NPC data for {npc_data['name']}:\n{formatted_data}\n"
                    character_data.append({"role": "system", "content": npc_message})
            except FileNotFoundError:
                print(f"{npc_file} not found. Skipping JSON data for NPC {npc['name']}.")
            except json.JSONDecodeError:
                print(f"{npc_file} has an invalid JSON format. Skipping JSON data for NPC {npc['name']}.")
        
        # Insert character and NPC data after party tracker data
        party_tracker_index = next((i for i, msg in enumerate(updated_history) if msg["role"] == "system" and "Here's the updated party tracker data:" in msg["content"]), -1)
        if party_tracker_index != -1:
            for i, char_data in enumerate(character_data):
                updated_history.insert(party_tracker_index + 1 + i, char_data)
        else:
            updated_history.extend(character_data)

    return updated_history

def generate_chat_history(conversation_history):
    """Generate a lightweight chat history without system messages"""
    output_file = "modules/conversation_history/chat_history.json"
    
    try:
        # Filter out system messages and keep only user and assistant messages
        chat_history = [msg for msg in conversation_history if msg["role"] != "system"]
        
        # Write the filtered chat history to the output file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chat_history, f, indent=2)
        
        # Print statistics
        system_count = len(conversation_history) - len(chat_history)
        total_count = len(conversation_history)
        user_count = sum(1 for msg in chat_history if msg["role"] == "user")
        assistant_count = sum(1 for msg in chat_history if msg["role"] == "assistant")
        
        info(f"SUCCESS: Lightweight chat history updated!", category="conversation_history")
        debug(f"System messages removed: {system_count}", category="conversation_history")
        debug(f"User messages: {user_count}", category="conversation_history")
        debug(f"Assistant messages: {assistant_count}", category="conversation_history")
        
    except Exception as e:
        error(f"FAILURE: Error generating chat history: {str(e)}", exception=e, category="conversation_history")
