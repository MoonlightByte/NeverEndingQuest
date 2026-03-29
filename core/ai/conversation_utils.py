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
from utils.plot_formatting import format_plot_for_ai
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from core.ai.atlas_builder import build_atlas_for_module, format_atlas_for_conversation

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


def _is_numeric_list(values, expected_len):
    """Return True when values is a numeric list of the expected length."""
    if not isinstance(values, list) or len(values) != expected_len:
        return False

    try:
        for value in values:
            float(value)
    except (TypeError, ValueError):
        return False

    return True


def _build_party_npc_role_map(party_tracker_data):
    """Build a simple name-to-role map for party NPCs."""
    role_map = {}
    if not party_tracker_data:
        return role_map

    for npc in party_tracker_data.get('partyNPCs', []):
        if isinstance(npc, dict):
            name = str(npc.get('name', '')).strip()
            role = str(npc.get('role', '')).strip()
        else:
            name = str(npc).strip()
            role = ''

        if name:
            role_map[name.lower()] = role

    return role_map


def _build_party_member_identity_map(party_tracker_data):
    """Build normalized lookup map for party-member identities."""
    identity_map = {}
    if not party_tracker_data:
        return identity_map

    def normalize_character_name(value):
        name = str(value or '').strip().lower()
        name = name.replace(' ', '_').replace("'", '_')
        name = re.sub(r'[^a-z0-9_]', '_', name)
        name = re.sub(r'_+', '_', name)
        return name.strip('_')

    try:
        from utils.pc_manager import get_character_state
    except Exception:
        get_character_state = None

    for member in party_tracker_data.get('partyMembers', []):
        display_name = str(member or '').strip()
        if not display_name:
            continue

        character_id = ''
        if get_character_state:
            try:
                character_data = get_character_state(display_name, fields=['character_id', 'name']) or {}
                character_id = str(character_data.get('character_id', '')).strip()
                display_name = str(character_data.get('name') or display_name).strip() or display_name
            except Exception:
                character_id = ''

        normalized_name = normalize_character_name(display_name)
        edge_key = character_id or normalized_name
        identity = {
            'key': edge_key,
            'display_name': display_name,
            'normalized_name': normalized_name,
        }

        aliases = [display_name, normalized_name]
        tokens = [token for token in re.split(r'[\s_]+', display_name) if token]
        if tokens:
            aliases.append(tokens[0])
            aliases.append(tokens[-1])

        for alias in aliases:
            alias_text = str(alias or '').strip()
            if not alias_text:
                continue
            alias_key = normalize_character_name(alias_text)
            if alias_key:
                identity_map[alias_key] = identity

    return identity_map


def _resolve_active_pc_identity(party_tracker_data):
    """Resolve active PC identity for active-PC-first companion projection."""
    identity_map = _build_party_member_identity_map(party_tracker_data)
    active_name = str((party_tracker_data or {}).get('active_character', '')).strip()

    if active_name:
        active_key = str(active_name or '').strip().lower()
        active_key = active_key.replace(' ', '_').replace("'", '_')
        active_key = re.sub(r'[^a-z0-9_]', '_', active_key)
        active_key = re.sub(r'_+', '_', active_key).strip('_')

        if active_key in identity_map:
            return identity_map[active_key]

    unique_identities = []
    seen = set()
    for identity in identity_map.values():
        identity_key = identity.get('key')
        if identity_key in seen:
            continue
        unique_identities.append(identity)
        seen.add(identity_key)

    if len(unique_identities) == 1:
        return unique_identities[0]
    return None


def _relationship_edge_strength(edge):
    """Score a compressed relationship edge for projection priority."""
    if not isinstance(edge, dict):
        return 0.0

    edge_values = edge.get('e', [])
    if not _is_numeric_list(edge_values, 5):
        return 0.0

    return (
        abs(float(edge_values[0])) +
        abs(float(edge_values[1])) +
        float(edge_values[2]) +
        float(edge_values[3]) +
        float(edge_values[4]) * 1.25 +
        (0.2 if edge.get('rt') else 0.0)
    )


def _format_relationship_edge_summary(edge):
    """Convert a compressed relationship edge into bounded prose."""
    if not isinstance(edge, dict):
        return ''

    edge_values = edge.get('e', [])
    if not _is_numeric_list(edge_values, 5):
        return ''

    display_name = str(edge.get('d', 'that companion')).strip() or 'that companion'
    trust, respect, intimacy, fear, resentment = [float(value) for value in edge_values]

    if resentment >= 0.45 and trust <= 0.0:
        summary = f"distrusts {display_name}"
    elif trust >= 0.45 and respect >= 0.25:
        summary = f"trusts {display_name} and respects their lead"
    elif trust >= 0.4:
        summary = f"trusts {display_name}"
    elif respect >= 0.45:
        summary = f"respects {display_name}"
    elif intimacy >= 0.45:
        summary = f"feels close to {display_name}"
    elif fear >= 0.45:
        summary = f"is wary of {display_name}"
    else:
        summary = f"has unresolved history with {display_name}"

    recent_triggers = edge.get('rt', [])
    if isinstance(recent_triggers, list) and recent_triggers:
        trigger_text = str(recent_triggers[-1]).strip()
        if '@' in trigger_text:
            trigger_text = trigger_text.split('@', 1)[0]
        if trigger_text:
            summary += f" after {trigger_text}"

    return summary[:140]


def _classify_companion_memory_packet(npc):
    """Classify a compressed companion memory packet for prompt safety."""
    if not isinstance(npc, dict):
        return 'malformed'

    npc_name = npc.get('n')
    memories = npc.get('mem', [])
    emotional_state = npc.get('es', [0.0, 0.0, 0.0, 0.0, 0.0])
    behavioral_model = npc.get('bm', [0.0, 0.0, 0.0, 0.0, 0.0])
    recent_notes = npc.get('rm', [])
    relationship_edges = npc.get('re', [])

    if not isinstance(npc_name, str) or not npc_name.strip():
        return 'malformed'
    if not isinstance(memories, list):
        return 'malformed'
    if not _is_numeric_list(emotional_state, 5):
        return 'malformed'
    if not _is_numeric_list(behavioral_model, 5):
        return 'malformed'
    if recent_notes is not None and not isinstance(recent_notes, list):
        return 'malformed'
    if relationship_edges is not None and not isinstance(relationship_edges, list):
        return 'malformed'

    try:
        interaction_count = int(npc.get('ti', 0))
        mention_count = int(npc.get('mc', interaction_count))
    except (TypeError, ValueError):
        return 'malformed'

    if any(abs(float(value)) > 0.0 for value in emotional_state) or len(memories) > 0:
        return 'healthy'
    if any(_relationship_edge_strength(edge) > 0.0 for edge in relationship_edges or []):
        return 'healthy'
    if interaction_count > 0 or len(recent_notes) > 0:
        return 'degraded_extract'
    if mention_count > 0:
        return 'sparse'

    return 'sparse'


def _project_companion_memory_packet(npc, npc_role='', active_pc_identity=None):
    """Project a compressed companion memory packet into healthy or fallback form."""
    quality = _classify_companion_memory_packet(npc)
    if quality == 'malformed':
        return None

    emotional_state = npc.get('es', [0.0, 0.0, 0.0, 0.0, 0.0])
    behavioral_model = npc.get('bm', [0.0, 0.0, 0.0, 0.0, 0.0])

    projected = {
        'n': npc.get('n', 'unknown'),
        'q': quality,
        'ti': int(npc.get('ti', 0)),
        'mc': int(npc.get('mc', npc.get('ti', 0))),
        'es': emotional_state,
        'bm': behavioral_model,
        'mem': list(npc.get('mem', [])) if quality == 'healthy' else [],
    }

    group_state = npc.get('gs', [])
    if _is_numeric_list(group_state, 6):
        projected['gs'] = group_state

    recent_notes = []
    for note in npc.get('rm', [])[:2]:
        note_text = str(note).strip()
        if note_text:
            recent_notes.append(note_text[:100])
    if recent_notes:
        projected['rm'] = recent_notes

    relationship_edges = [edge for edge in npc.get('re', []) if _relationship_edge_strength(edge) > 0.0]
    active_edge = None
    if active_pc_identity:
        active_key = str(active_pc_identity.get('key', '')).strip()
        normalized_key = str(active_pc_identity.get('normalized_name', '')).strip()
        for edge in relationship_edges:
            edge_key = str(edge.get('k', '')).strip()
            if edge_key and edge_key in (active_key, normalized_key):
                active_edge = edge
                break
    if not active_edge and len(relationship_edges) == 1:
        active_edge = relationship_edges[0]

    if active_edge:
        active_summary = _format_relationship_edge_summary(active_edge)
        if active_summary:
            projected['ap'] = active_summary

    secondary_candidates = []
    for edge in relationship_edges:
        if active_edge and edge is active_edge:
            continue
        secondary_candidates.append((_relationship_edge_strength(edge), edge))
    secondary_candidates.sort(key=lambda item: item[0], reverse=True)

    if secondary_candidates:
        secondary_summary = _format_relationship_edge_summary(secondary_candidates[0][1])
        if secondary_summary:
            projected['sp'] = secondary_summary

    if npc_role:
        projected['r'] = npc_role

    return projected

def update_conversation_history(conversation_history, party_tracker_data, plot_data, module_data):
    # Read the actual system prompt to get the proper identifier
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "prompts", "system_prompt_compressed.txt"), "r", encoding="utf-8") as file:
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
        if msg["role"] == "system" and "=== COMPANION MEMORIES (Compressed) ===" in msg.get("content", ""):
            debug("Removing existing companion memories (will be refreshed from file)", category="memory")
            continue

        # Keep all other messages
        updated_history.append(msg)

    # Create a new list starting with the primary system prompt
    new_history = [primary_system_prompt] if primary_system_prompt else []

    # ALWAYS inject fresh compressed companion memories from file
    # This prevents stale data from being perpetuated in conversation history
    try:
        compressed_path = os.path.join("data", "companion_memories", "memories_compressed.json")
        if os.path.exists(compressed_path):
            with open(compressed_path, 'r', encoding='utf-8') as f:
                memories = json.load(f)

            # Format memories compactly for AI
            if memories and 'npcs' in memories:
                npc_role_map = _build_party_npc_role_map(party_tracker_data)
                active_pc_identity = _resolve_active_pc_identity(party_tracker_data)
                valid_npcs = []
                for npc in memories['npcs']:
                    npc_name = npc.get('n', 'unknown')
                    npc_role = npc_role_map.get(str(npc_name).lower(), '')
                    quality = _classify_companion_memory_packet(npc)

                    if quality == 'malformed':
                        warning(f"Detected malformed memory data for {npc_name}. " +
                               "This NPC will be excluded from context until memories regenerate.",
                               category="memory")
                        continue

                    if quality == 'degraded_extract':
                        warning(f"Detected degraded memory data for {npc_name}: meaningful companion history exists " +
                               "but no crystallized memory state is available. Using bounded fallback context.",
                               category="memory")
                    elif quality == 'sparse':
                        debug(f"Detected sparse memory data for {npc_name}. Using bounded fallback context.", category="memory")

                    projected_npc = _project_companion_memory_packet(npc, npc_role, active_pc_identity=active_pc_identity)
                    if projected_npc:
                        valid_npcs.append(projected_npc)

                if valid_npcs:
                    memory_content = "=== COMPANION MEMORIES (Compressed) ===\n"
                    memory_content += json.dumps(valid_npcs, separators=(',', ':'))
                    memory_content += "\n@GUIDE: Use ES (emotional state) for tone, BM (behavioral model) for consistency"
                    memory_content += "\n==="

                    # Insert right after system prompt
                    memory_message = {'role': 'system', 'content': memory_content}
                    new_history.append(memory_message)
                    debug(f"Injected fresh companion memories for {len(valid_npcs)} NPCs", category="memory")
                else:
                    debug("No valid companion memories to inject (all NPC packets malformed)", category="memory")
    except Exception as e:
        warning(f"Failed to inject memories (non-fatal): {e}", category="memory")

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

    # Insert world state information
    try:
        from core.managers.campaign_manager import CampaignManager
        campaign_manager = CampaignManager()

        # CRITICAL: Use fresh party_tracker_data from campaign_manager if available
        # CampaignManager reloads party_tracker after module integration, fixing stale location IDs
        if hasattr(campaign_manager, 'party_tracker_data') and campaign_manager.party_tracker_data:
            party_tracker_data = campaign_manager.party_tracker_data
            print(f"DEBUG: [update_conversation_history] Using fresh party_tracker from CampaignManager. Location: {party_tracker_data.get('worldConditions', {}).get('currentLocationId', 'Unknown')}")

        available_modules = campaign_manager.campaign_data.get('availableModules', [])

        # Get current module from actual party_tracker.json file
        current_module = 'Unknown'
        party_tracker_file = "party_tracker.json"
        try:
            if os.path.exists(party_tracker_file):
                party_data = safe_json_load(party_tracker_file)
                if party_data:
                    current_module = party_data.get('module', 'Unknown')
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
TEMP FX: {', '.join([f"{effect['name']}" for effect in member_data.get('temporaryEffects', [])])}
EQUIP: {equipment_str}
AMMO: {', '.join([f"{ammo.get('name', 'Unknown')} x{ammo.get('quantity', 0)}" for ammo in member_data.get('ammunition', [])])}
ATK: {', '.join([f"{atk['name']} ({atk['type']}, {atk['damageDice']} {atk['damageType']})" for atk in member_data['attacksAndSpellcasting']])}
SPELLCASTING: {member_data.get('spellcasting', {}).get('ability', 'N/A')} | DC: {member_data.get('spellcasting', {}).get('spellSaveDC', 'N/A')} | ATK: +{member_data.get('spellcasting', {}).get('spellAttackBonus', 'N/A')}
SPELLS: {', '.join([f"{level}: {', '.join(spells)}" for level, spells in member_data.get('spellcasting', {}).get('spells', {}).items() if spells])}
CURRENCY: {member_data['currency']['gold']}G, {member_data['currency']['silver']}S, {member_data['currency']['copper']}C
XP: {member_data['experience_points']}/{member_data.get('exp_required_for_next_level', 'N/A')}
TRAITS: {member_data['personality_traits']}
IDEALS: {member_data['ideals']}
BONDS: {member_data['bonds']}
FLAWS: {member_data['flaws']}
BACKSTORY: {member_data.get('backstory', 'N/A')[:120] if member_data.get('backstory') else 'N/A'}
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
TEMP FX: {', '.join([f"{effect['name']}" for effect in npc_data.get('temporaryEffects', [])])}
EQUIP: {equipment_str}
AMMO: {', '.join([f"{ammo.get('name', 'Unknown')} x{ammo.get('quantity', 0)}" for ammo in npc_data.get('ammunition', [])])}
ATK: {', '.join([f"{atk['name']} ({atk['type']}, {atk['damageDice']} {atk['damageType']})" for atk in npc_data['attacksAndSpellcasting']])}
SPELLCASTING: {npc_data.get('spellcasting', {}).get('ability', 'N/A')} | DC: {npc_data.get('spellcasting', {}).get('spellSaveDC', 'N/A')} | ATK: +{npc_data.get('spellcasting', {}).get('spellAttackBonus', 'N/A')}
SPELLS: {', '.join([f"{level}: {', '.join(spells)}" for level, spells in npc_data.get('spellcasting', {}).get('spells', {}).items() if spells])}
CURRENCY: {npc_data['currency']['gold']}G, {npc_data['currency']['silver']}S, {npc_data['currency']['copper']}C
XP: {npc_data['experience_points']}/{npc_data.get('exp_required_for_next_level', 'N/A')}
TRAITS: {npc_data['personality_traits']}
IDEALS: {npc_data['ideals']}
BONDS: {npc_data['bonds']}
FLAWS: {npc_data['flaws']}
BACKSTORY: {npc_data.get('backstory', 'N/A')[:120] if npc_data.get('backstory') else 'N/A'}
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
