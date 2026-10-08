# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# CUMULATIVE_SUMMARY.PY - AI CONTEXT OPTIMIZATION LAYER
# ============================================================================
# 
# ARCHITECTURE ROLE: AI Integration Layer - Long-Term Memory Management
# 
# This module implements intelligent conversation compression and long-term
# memory management for extended 5th edition sessions. It solves the AI context
# limitation problem while preserving module continuity.
# 
# KEY RESPONSIBILITIES:
# - Compress lengthy conversation histories into coherent summaries
# - Preserve critical game state information across context reductions
# - Generate adventure logs for long-term module memory
# - Optimize AI context for better performance and token management
# - Maintain narrative continuity during session transitions
# 
# COMPRESSION STRATEGY:
# - Event-based summarization preserving key decisions and outcomes
# - Character development tracking across sessions
# - Important NPC interaction preservation
# - Combat outcome summarization with consequences
# - Plot progression highlights and future hooks
# 
# MEMORY OPTIMIZATION:
# - Rolling window approach for recent events
# - Hierarchical summarization for older sessions
# - Key moment extraction and preservation
# - State snapshot creation for quick context rebuilding
# 
# ARCHITECTURAL INTEGRATION:
# - Used by conversation_utils.py for context management
# - Integrates with main.py for session continuity
# - Supports dm_wrapper.py with optimized context
# - Coordinates with party_tracker.json for state preservation
# 
# AI INTEGRATION:
# - Specialized summarization model for narrative compression
# - Intelligent event prioritization and selection
# - Context-aware summary generation
# - Multi-session continuity maintenance
# 
# This module ensures our AI can maintain coherent long-term modules
# while respecting token limitations and performance requirements.
# ============================================================================

import copy
import json
import os
import re
from datetime import datetime
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T018", "core/ai/cumulative_summary.py", 293)
register_callsite("T019", "core/ai/cumulative_summary.py", 579)

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json
from utils.encoding_utils import sanitize_text, safe_json_load, safe_json_dump
from core.managers.status_manager import status_generating_summary, status_compressing_history
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("cumulative_summary")

TEMPERATURE = 0.8

def debug_print(text, log_to_file=True):
    """Print debug message and optionally log to file"""
    debug(f"PROCESSING: {text}", category="cumulative_summary")
    if log_to_file:
        try:
            with open("modules/logs/cumulative_summary_debug.log", "a") as log_file:
                log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {text}\n")
        except Exception as e:
            error(f"FAILURE: Could not write to debug log file: {str(e)}", category="file_operations")

def load_json_file(file_path):
    """Load a JSON file with error handling and encoding sanitization"""
    try:
        return safe_json_load(file_path)
    except FileNotFoundError:
        debug_print(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        debug_print(f"Invalid JSON in {file_path}: {str(e)}")
        return None
    except Exception as e:
        debug_print(f"Error loading {file_path}: {str(e)}")
        return None

def save_json_file(file_path, data):
    """Save data to a JSON file with error handling and encoding sanitization"""
    try:
        safe_json_dump(data, file_path)
        return True
    except Exception as e:
        debug_print(f"Error saving {file_path}: {str(e)}")
        return False

def extract_location_from_conversation(conversation_history):
    """Extract the current location from recent conversation messages"""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user" and "Current location:" in msg.get("content", ""):
            # Extract location from DM note
            content = msg["content"]
            loc_match = content.find("Current location:")
            if loc_match != -1:
                loc_text = content[loc_match:].split(".")[0]
                # Extract location name (before the ID in parentheses)
                if "(" in loc_text:
                    location_name = loc_text.split("(")[0].replace("Current location:", "").strip()
                    # Handle encoding issues - normalize the location name
                    # Replace common problematic characters
                    location_name = location_name.replace('\u2019', "'")
                    location_name = location_name.replace('\u2018', "'")
                    location_name = location_name.replace('\u201c', '"')
                    location_name = location_name.replace('\u201d', '"')
                    location_name = location_name.replace('\u2014', '-')
                    location_name = location_name.replace('\u2013', '-')
                    location_name = location_name.replace('\u00e2\u20ac\u2122', "'")
                    location_name = location_name.replace('â€™', "'")
                    location_name = location_name.replace('â€"', '-')
                    location_name = location_name.replace('â€˜', "'")
                    location_name = location_name.replace('â€œ', '"')
                    location_name = location_name.replace('â€', '"')
                    return location_name
    return "Unknown Location"

def extract_location_id_from_conversation(conversation_history):
    """Extract the current location ID (e.g., R01, R02) from recent conversation messages"""
    import re
    for msg in reversed(conversation_history):
        if msg.get("role") == "user" and "Current location:" in msg.get("content", ""):
            # Extract location ID from DM note
            content = msg["content"]
            # Look for pattern like (R01) or (R02) etc.
            id_match = re.search(r'\(([A-Z]\d+)\)', content)
            if id_match:
                return id_match.group(1)  # Return just the ID without parentheses
    return None

def get_session_start_index(conversation_history):
    """Find where the current play session starts in conversation history"""
    # Look for the first user message after the system prompts
    for i, msg in enumerate(conversation_history):
        if msg.get("role") == "user" and not msg.get("content", "").startswith("Adventure History Context:"):
            # This is likely the first actual player input of the session
            return i
    return 0

def build_location_summaries_from_conversation(conversation_history):
    """
    Build location summaries from the current conversation history only.
    This creates summaries for each location visited during the current play session.
    """
    debug_print("Building location summaries from current conversation")
    
    session_start = get_session_start_index(conversation_history)
    debug_print(f"Session starts at index {session_start}")
    
    # Track location changes and collect messages for each location
    location_segments = []
    current_location = None
    current_segment = []
    
    for i in range(session_start, len(conversation_history)):
        msg = conversation_history[i]
        
        # Check for location changes in user messages (DM notes)
        if msg.get("role") == "user" and "Current location:" in msg.get("content", ""):
            new_location = extract_location_from_conversation([msg])
            
            if current_location and current_location != new_location and current_segment:
                # Save the previous location's messages
                location_segments.append({
                    "location": current_location,
                    "messages": current_segment.copy()
                })
                current_segment = []
            
            current_location = new_location
        
        # Add message to current segment (skip system messages and adventure history)
        if msg.get("role") != "system" and not (
            msg.get("role") == "user" and msg.get("content", "").startswith("Adventure History Context:")
        ):
            current_segment.append(msg)
        
        # Also check for location transitions in assistant messages
        if msg.get("role") == "assistant" and "transitionLocation" in msg.get("content", ""):
            # This is a transition message, should trigger a segment save
            if current_location and current_segment and len(current_segment) > 2:
                # Make sure we haven't already saved this segment
                if not location_segments or location_segments[-1].get("location") != current_location:
                    location_segments.append({
                        "location": current_location,
                        "messages": current_segment.copy()
                    })
                    debug_print(f"Saved segment for {current_location} due to transition")
    
    # Save the final location segment
    if current_location and current_segment:
        location_segments.append({
            "location": current_location,
            "messages": current_segment
        })
    
    debug_print(f"Found {len(location_segments)} location segments in current session")
    
    # Generate summaries for each location
    summaries = []
    for segment in location_segments:
        if len(segment["messages"]) > 2:  # Only summarize if there's meaningful content
            summary = generate_location_summary(segment["location"], segment["messages"])
            if summary:
                summaries.append({
                    "location": segment["location"],
                    "summary": summary
                })
    
    return summaries

def generate_location_summary(location_name, messages):
    """Generate a summary for what happened in a specific location"""
    status_generating_summary()
    debug_print(f"Generating summary for {location_name}")
    
    # Extract conversation content
    dialogue = f"Events in {location_name}:\n\n"
    for message in messages:
        role = message.get('role')
        content = message.get('content', '')
        
        if role == 'assistant':
            # Extract narration from JSON if present
            if content.strip().startswith("{"):
                try:
                    parsed = json.loads(content)
                    narration = parsed.get("narration", content)
                    dialogue += f"Dungeon Master: {narration}\n\n"
                except:
                    dialogue += f"Dungeon Master: {content}\n\n"
            else:
                dialogue += f"Dungeon Master: {content}\n\n"
        elif role == 'user':
            # Extract player content from DM notes
            if "Player:" in content:
                player_part = content.split("Player:", 1)[1].strip()
                dialogue += f"Player: {player_part}\n\n"
    
    # Create summary prompt
    messages = [
        {"role": "system", "content": f"""You are a chronicler documenting a 5th edition campaign using only information provided in this location scene. Your task is to write a concise yet vivid summary of what occurred in '{location_name}', formatted as a single narrative entry for a campaign journal or codex.

Your summary should capture the following, as specifically as possible:
1. What the party did upon arrival
2. Who they encountered (NPCs, monsters, groups)
3. Any combat or challenges faced, including tactical choices or emotional stakes
4. Significant conversations, confessions, or discoveries
5. Items found, resources used, or abilities expended
6. How the visit ended or transitioned
7. Interpersonal moments—conflict, bonding, romantic tension, loyalty shifts, leadership, etc.
8. Any event that would leave a lasting memory for a character or NPC (such as a heroic act, death, reconciliation, or symbolic gesture)

Use past tense and third person. Be vivid, specific, and emotional where appropriate. Focus on what actually happened -- not what might happen. Avoid generic phrases. Prioritize character-driven consequences and story-critical developments. Include emotional tone, narrative closure, and forward momentum for what might come next. Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode. Do NOT use markdown formatting (no **, no ###, no bullet points)."""
},
        {"role": "user", "content": dialogue}
    ]
    
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

        response = capture_and_fanout("T018", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=messages,
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

        summary = response.choices[0].message.content.strip()
        # Sanitize AI response to prevent encoding issues
        summary = sanitize_text(summary)
        debug_print(f"Summary generated for {location_name}")
        return summary
    except Exception as e:
        debug_print(f"ERROR: Failed to generate summary for {location_name}: {str(e)}")
        return None

def get_cumulative_adventure_summary():
    """
    Build a cumulative adventure summary from the current play session only.
    Returns a formatted string containing summaries of locations visited this session.
    """
    debug_print("Building cumulative adventure summary for current session")
    
    # Load current conversation history
    conversation_history = safe_read_json("modules/conversation_history/conversation_history.json")
    if not conversation_history:
        debug_print("No conversation history found")
        return ""
    
    # Get summaries for this session
    location_summaries = build_location_summaries_from_conversation(conversation_history)
    
    if not location_summaries:
        debug_print("No location summaries generated for current session")
        return ""
    
    # Build the cumulative summary
    summary_parts = []
    summary_parts.append("=== CURRENT SESSION SUMMARY ===\n")
    summary_parts.append("Summary of locations visited during this play session:\n")
    
    for loc_summary in location_summaries:
        summary_parts.append(f"\n{loc_summary['location']}:")
        summary_parts.append("-" * len(loc_summary['location'] + ":"))
        summary_parts.append(loc_summary['summary'])
        summary_parts.append("")  # Blank line between entries
    
    cumulative_summary = "\n".join(summary_parts)
    debug_print(f"Built cumulative summary with {len(cumulative_summary)} characters")
    
    return cumulative_summary

def clean_old_summaries_from_conversation(conversation_history):
    """
    Remove old-style summary messages and error notes from conversation history.
    """
    debug_print("Cleaning old-style summaries from conversation history")
    cleaned_history = []
    removed_count = 0
    
    for msg in conversation_history:
        # Skip old-style summary messages, adventure history messages, and error notes
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if (content.startswith("Summary of previous interactions:") or
                content.startswith("Adventure History Context:") or
                content.startswith("Error Note:")):
                removed_count += 1
                continue
        cleaned_history.append(msg)
    
    if removed_count > 0:
        debug_print(f"Removed {removed_count} old summary messages and error notes")
    
    return cleaned_history

def compress_conversation_history_on_transition(conversation_history, leaving_location_name,
                                                party_tracker_data=None, path_manager=None,
                                                player_name=""):
    """
    Compress conversation history when transitioning out of a location.
    Creates a summary of the location being left and removes those messages.
    Uses location transition messages as markers.
    Returns the compressed conversation history.

    party_tracker_data/path_manager/player_name are optional; when provided,
    a best-effort per-companion episode is captured from the raw
    segment before it is compressed away (Phase 1d). Capture is offloaded and
    fail-open -- it never gates, mutates, or blocks the summary/history.
    """
    status_compressing_history()
    debug_print(f"Compressing conversation history when leaving {leaving_location_name}")
    debug_print(f"Total messages in history: {len(conversation_history)}")
    
    # First clean old summaries
    conversation_history = clean_old_summaries_from_conversation(conversation_history)
    
    # Find the most recent location transition message
    transition_index = None
    for i in range(len(conversation_history) - 1, -1, -1):
        msg = conversation_history[i]
        if msg.get("role") == "user" and "Location transition:" in msg.get("content", ""):
            transition_index = i
            debug_print(f"Found transition at index {i}: {msg.get('content', '')}")
            break
    
    if transition_index is None:
        debug_print("No location transition found in conversation history")
        return conversation_history
    
    # Find the previous marker (transition, adventure history, or last system message)
    previous_marker_index = None
    
    # Look backwards from the transition
    for i in range(transition_index - 1, -1, -1):
        msg = conversation_history[i]
        
        # Stop at previous transition
        if msg.get("role") == "user" and "Location transition:" in msg.get("content", ""):
            previous_marker_index = i
            debug_print(f"Found previous transition at index {i}")
            break
            
        # Stop at assistant summary (from previous compression)
        if msg.get("role") == "assistant" and "=== LOCATION SUMMARY ===" in msg.get("content", ""):
            previous_marker_index = i
            debug_print(f"Found previous summary at index {i}")
            break
    
    # If no previous marker found, find the last system message
    if previous_marker_index is None:
        for i in range(transition_index - 1, -1, -1):
            if conversation_history[i].get("role") == "system":
                previous_marker_index = i
                debug_print(f"Using last system message at index {i} as start marker")
    
    # If still nothing, start from beginning
    if previous_marker_index is None:
        previous_marker_index = -1
    
    debug_print(f"Collecting messages from index {previous_marker_index + 1} to {transition_index - 1}")
    
    # Collect messages to summarize (between markers, excluding the markers themselves)
    messages_to_summarize = []
    for i in range(previous_marker_index + 1, transition_index):
        msg = conversation_history[i]
        # Include all messages except system messages and error notes
        if msg.get("role") == "system":
            continue
        if msg.get("role") == "user" and msg.get("content", "").startswith("Error Note:"):
            continue
        messages_to_summarize.append(msg)
    
    debug_print(f"Found {len(messages_to_summarize)} messages to summarize")
    
    # Generate summary if we have messages to summarize
    if len(messages_to_summarize) > 0:
        summary = generate_location_summary(leaving_location_name, messages_to_summarize)

        # Phase 1d: best-effort per-companion episode capture from the SAME raw
        # segment, before it is compressed away. Offloaded (fire-and-forget) and
        # fail-open: never gates or mutates the summary/history.
        try:
            if party_tracker_data is not None and path_manager is not None:
                from core.npc.episode_capture import (
                    capture_location_episode_async,
                    leaving_location_id_from_marker,
                    location_close_position,
                    boundary_turn_id_for_position,
                )
                import copy as _copy
                position = location_close_position(conversation_history, transition_index)
                capture_location_episode_async(
                    leaving_location_name=leaving_location_name,
                    leaving_location_id=leaving_location_id_from_marker(
                        conversation_history[transition_index].get("content", "")),
                    segment_messages=list(messages_to_summarize),
                    # Snapshot the tracker: the offloaded thread reads module/world
                    # seconds later (after the luna call), and the main loop mutates
                    # the live dict on the very next action (often a module transition)
                    # -- a live reference would corrupt the episode's module coordinate.
                    party_tracker_data=_copy.deepcopy(party_tracker_data),
                    path_manager=path_manager,
                    boundary_turn_id=boundary_turn_id_for_position(position),
                    player_name=player_name,
                )
        except Exception:
            pass

        if summary:
            # Build the new conversation history
            new_history = []
            
            # 1. Keep everything up to and including the previous marker
            for i in range(0, previous_marker_index + 1):
                new_history.append(conversation_history[i])
            
            # 2. Insert the summary as an assistant message
            summary_message = {
                "role": "assistant",
                "content": f"=== LOCATION SUMMARY ===\n\n{leaving_location_name}:\n{'-' * len(leaving_location_name + ':')}\n{summary}"
            }
            new_history.append(summary_message)
            
            # 3. Add everything from the transition onwards (including the transition itself)
            for i in range(transition_index, len(conversation_history)):
                new_history.append(conversation_history[i])
            
            debug_print(f"Compressed history from {len(conversation_history)} to {len(new_history)} messages")
            debug_print(f"Removed {len(messages_to_summarize)} messages from {leaving_location_name}")
            
            return new_history
        else:
            debug_print("Failed to generate summary")
            return conversation_history
    else:
        debug_print(f"No messages to summarize for {leaving_location_name}")
        return conversation_history


def compact_with_accepted_departure_summary(
    conversation_history,
    *,
    source_index,
    source_entries_before,
    leaving_location_name,
    summary,
    summary_message_id,
):
    """Replace one exact raw segment using the already accepted T016 text."""
    if not isinstance(source_index, int) or source_index < 0:
        raise ValueError("departure compaction source index is invalid")
    if not isinstance(source_entries_before, list):
        raise TypeError("departure compaction source must be a list")
    summary_entry = {
        "role": "assistant",
        "content": (
            "=== LOCATION SUMMARY ===\n\n%s:\n%s\n%s"
            % (
                leaving_location_name,
                "-" * len(leaving_location_name + ":"),
                summary,
            )
        ),
        "message_id": summary_message_id,
    }
    if (
        source_index < len(conversation_history)
        and conversation_history[source_index] == summary_entry
    ):
        return conversation_history, summary_entry
    current_slice = conversation_history[
        source_index : source_index + len(source_entries_before)
    ]
    # Loading an existing game applies the long-standing DM-note compaction
    # before travel recovery runs.  That formatting-only normalization can
    # therefore be the exact on-disk value after a restart even though the
    # transition staged the unabridged value before movement.  Accept only
    # those two exact representations; every other change remains a conflict.
    normalized_source = normalize_legacy_dm_notes(source_entries_before)
    if current_slice not in (source_entries_before, normalized_source):
        raise ValueError("departure conversation segment changed before compaction")
    result = list(conversation_history)
    result[
        source_index : source_index + len(source_entries_before)
    ] = [summary_entry]
    return result, summary_entry


def normalize_legacy_dm_notes(conversation_history):
    """Return the legacy request-history representation without mutating input."""
    normalized = copy.deepcopy(conversation_history)
    for message in normalized:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not (
            message.get("role") == "user"
            and isinstance(content, str)
            and content.startswith("Dungeon Master Note:")
        ):
            continue
        parts = content.split("Player:", 1)
        if len(parts) != 2:
            continue
        date_time = re.search(r"Current date and time: ([^.]+)", parts[0])
        if date_time:
            message["content"] = (
                f"Dungeon Master Note: {date_time.group(0)}. Player:{parts[1]}"
            )
    return normalized

def enhance_location_summary(summary):
    """Run the legacy T019 enrichment over one already accepted T018 summary.

    Keeping this proposal step separate lets old-save repair freeze every
    mutation before it exposes a journal, memory, or conversation write.
    """
    if summary:
        messages = [
            {"role": "system", "content": """Expand this summary into a detailed journal entry that captures ALL important details:
- Exact sequence of events
- All NPCs encountered and their responses
- Combat details (who attacked, damage dealt, outcomes)
- Items found and their properties
- Information learned
- Decisions made and their immediate consequences
- State of the party when leaving

Keep the narrative engaging but factual. Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode. Do NOT use markdown formatting (no **, no ###, no bullet points)."""},
            {"role": "user", "content": f"Original summary: {summary}\n\nPlease expand this into a comprehensive journal entry."}
        ]
        
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

            response = capture_and_fanout("T019", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=messages,
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

            enhanced_summary = response.choices[0].message.content.strip()
            # Sanitize AI response to prevent encoding issues
            enhanced_summary = sanitize_text(enhanced_summary)
            debug_print("Enhanced adventure summary generated successfully")
            return enhanced_summary
        except Exception as e:
            debug_print(f"ERROR: Failed to enhance adventure summary: {str(e)}")
            return summary  # Return original if enhancement fails

    return None
