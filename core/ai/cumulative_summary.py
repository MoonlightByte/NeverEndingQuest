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

import json
import os
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
from utils.file_operations import safe_write_json, safe_read_json
from utils.encoding_utils import sanitize_text, safe_json_load, safe_json_dump
from core.managers.status_manager import status_generating_summary, status_updating_journal, status_compressing_history
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

def generate_enhanced_adventure_summary(conversation_history_data, party_tracker_data, leaving_location_name):
    """
    Generate an enhanced adventure summary when leaving a location.
    This is called by the transition handler to create journal entries.
    """
    debug_print(f"Generating enhanced adventure summary for {leaving_location_name}")
    
    # Find the most recent location transition message
    transition_index = None
    for i in range(len(conversation_history_data) - 1, -1, -1):
        msg = conversation_history_data[i]
        if msg.get("role") == "user" and "Location transition:" in msg.get("content", ""):
            transition_index = i
            debug_print(f"Found most recent transition at index {i}: {msg.get('content', '')}")
            break
    
    if transition_index is None:
        debug_print("No location transition found in conversation history")
        return None
    
    # Find the previous boundary (either another transition or the last system message)
    previous_boundary_index = None
    
    # Look backwards from the current transition
    for i in range(transition_index - 1, -1, -1):
        msg = conversation_history_data[i]
        
        # Stop at previous transition
        if msg.get("role") == "user" and "Location transition:" in msg.get("content", ""):
            previous_boundary_index = i
            debug_print(f"Found previous transition at index {i}")
            break
            
        # Stop at location summary (from previous compression)
        if msg.get("role") == "assistant" and "=== LOCATION SUMMARY ===" in msg.get("content", ""):
            previous_boundary_index = i
            debug_print(f"Found previous location summary at index {i}")
            break
    
    # If no previous transition found, find the last system message
    if previous_boundary_index is None:
        for i in range(transition_index - 1, -1, -1):
            if conversation_history_data[i].get("role") == "system":
                previous_boundary_index = i
                debug_print(f"Using last system message at index {i} as boundary")
        
        # If still nothing, start from beginning
        if previous_boundary_index is None:
            previous_boundary_index = -1
            debug_print("Starting from beginning of conversation")
    
    # Collect messages between boundaries (excluding the boundaries themselves)
    location_messages = []
    for i in range(previous_boundary_index + 1, transition_index):
        msg = conversation_history_data[i]
        # Include all messages except system messages
        if msg.get("role") != "system":
            location_messages.append(msg)
    
    debug_print(f"Collected {len(location_messages)} messages for location summary")
    
    if not location_messages:
        debug_print(f"No messages found for location {leaving_location_name}")
        return None
    
    # Generate the summary using the same function
    summary = generate_location_summary(leaving_location_name, location_messages)
    
    # For journal entries, we want a more detailed summary
    if summary:
        # Enhance the summary with specific details
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

def update_journal_with_summary(adventure_summary, party_tracker_data, location_name):
    """
    Update the journal with the new adventure summary.
    This adds to the journal but doesn't affect conversation history.
    """
    status_updating_journal()
    debug_print(f"Updating journal with summary for {location_name}")
    
    journal_data = safe_read_json("journal.json")
    if not journal_data:
        journal_data = {"entries": []}
    
    world_conditions = party_tracker_data.get('worldConditions', {})
    new_entry = {
        "date": f"{world_conditions.get('year', 'N/A')} {world_conditions.get('month','N/A')} {world_conditions.get('day','N/A')}",
        "time": world_conditions.get('time', 'N/A'),
        "location": location_name,
        "summary": adventure_summary
    }
    
    journal_data["entries"].append(new_entry)

    if safe_write_json("journal.json", journal_data):
        debug_print("Journal updated successfully")

        # Process memories for companion NPCs
        try:
            from core.memories.companion_memory import CompanionMemoryManager
            from utils.npc_name_canonicalizer import get_canonical_name
            memory_manager = CompanionMemoryManager()

            # Get list of party NPCs with canonical names
            party_npcs = []
            for npc in party_tracker_data.get('partyNPCs', []):
                npc_name = npc.get('name', '') if isinstance(npc, dict) else str(npc)
                if npc_name:
                    # Use AI-based canonicalization to handle all D&D naming conventions
                    canonical_name = get_canonical_name(npc_name)
                    if canonical_name:
                        party_npcs.append(canonical_name)

            # Process the journal entry for memories
            if party_npcs:
                memories_created = memory_manager.process_journal_entry(
                    new_entry,
                    party_npcs
                )

                if memories_created:
                    debug_print(f"Created memories for: {', '.join(memories_created.keys())}")

                    # Auto-compress the memories for AI consumption
                    try:
                        import subprocess
                        result = subprocess.run(
                            ["python", "scripts/memory_management/compress_memories.py"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            debug_print("Compressed memories for AI consumption")
                    except Exception as compress_error:
                        debug_print(f"Memory compression failed (non-fatal): {compress_error}")
        except Exception as e:
            # Don't let memory system errors break journal updates
            debug_print(f"Memory processing error (non-fatal): {e}")

        return True
    else:
        debug_print("Failed to update journal")
        return False

def check_and_compact_missing_summaries(conversation_history, party_tracker_data):
    """
    Scan conversation history for location transitions without summaries and generate them.
    This function prevents double-compacting by checking for existing summaries.
    Returns the updated conversation history.
    """
    debug_print("Checking for missing location summaries")
    
    if not conversation_history or len(conversation_history) < 2:
        return conversation_history
    
    # First, find all location transitions
    transitions = []
    for i, msg in enumerate(conversation_history):
        if msg.get("role") == "user" and "Location transition:" in msg.get("content", ""):
            transitions.append(i)
    
    debug_print(f"Found {len(transitions)} total transitions")
    
    # Track locations that need summaries
    missing_summaries = []
    already_summarized_count = 0
    
    # Check each transition
    for i, trans_idx in enumerate(transitions):
        msg = conversation_history[trans_idx]
        
        # Check if next message is already a location summary
        is_already_summarized = False
        if trans_idx + 1 < len(conversation_history):
            next_msg = conversation_history[trans_idx + 1]
            if next_msg.get("role") == "assistant" and "=== LOCATION SUMMARY ===" in next_msg.get("content", ""):
                already_summarized_count += 1
                is_already_summarized = True
        
        if not is_already_summarized:
            # This transition needs a summary  
            # The content to summarize is AFTER this transition (the location we're arriving at)
            # We need to find where we LEAVE this location (the next transition FROM this location)
            
            # Extract the destination location from this transition
            try:
                import re
                transition_content = msg.get("content", "")
                
                # Try new format with IDs first
                id_pattern = r'Location transition: (.+?) \(([A-Z]\d+)\) to (.+?) \(([A-Z]\d+)\)'
                id_match = re.match(id_pattern, transition_content)
                
                if id_match:
                    arriving_location_name = id_match.group(3).strip()
                    arriving_location_id = id_match.group(4)
                else:
                    # Fall back to old format
                    parts = transition_content.split(" to ")
                    if len(parts) == 2:
                        arriving_location_name = parts[1].strip()
                        arriving_location_id = None
                    else:
                        debug_print(f"Could not parse transition at index {trans_idx}")
                        continue
                
                # Find the next transition FROM this location
                next_boundary = None
                for j in range(i + 1, len(transitions)):
                    next_trans_idx = transitions[j]
                    next_trans_msg = conversation_history[next_trans_idx]
                    next_trans_content = next_trans_msg.get("content", "")
                    
                    # Check if this transition is FROM our arriving location
                    if arriving_location_id:
                        # Use ID if available
                        if f" {arriving_location_name} ({arriving_location_id}) to" in next_trans_content:
                            next_boundary = next_trans_idx
                            break
                    else:
                        # Use name only
                        if next_trans_content.startswith(f"Location transition: {arriving_location_name} to"):
                            next_boundary = next_trans_idx
                            break
                
                # If no next transition found, this is the current active location - don't compact it
                if next_boundary is None:
                    debug_print(f"No departure transition found for {arriving_location_name} - this is the current active location, skipping")
                    continue
                
                debug_print(f"Location {arriving_location_name}: content from {trans_idx} to {next_boundary}")
                
                
                # Double-check: Make sure there's no summary between trans_idx and next_boundary
                has_summary_between = False
                for j in range(trans_idx + 1, next_boundary):
                    check_msg = conversation_history[j]
                    if check_msg.get("role") == "assistant" and "=== LOCATION SUMMARY ===" in check_msg.get("content", ""):
                        debug_print(f"Found existing summary between boundaries at index {j}, skipping")
                        has_summary_between = True
                        break
                
                if has_summary_between:
                    continue
                
                # Collect messages between boundaries
                messages_to_summarize = []
                for j in range(trans_idx + 1, next_boundary):
                    if conversation_history[j].get("role") != "system":
                        messages_to_summarize.append(conversation_history[j])
                
                if messages_to_summarize:
                    debug_print(f"Found {len(messages_to_summarize)} messages to summarize for {arriving_location_name}")
                    missing_summaries.append({
                        "transition_index": trans_idx,
                        "location_name": arriving_location_name,
                        "messages": messages_to_summarize,
                        "prev_boundary": trans_idx  # The transition itself is the boundary
                    })
                else:
                    debug_print(f"No messages to summarize for {arriving_location_name}")
                    
            except Exception as e:
                debug_print(f"Error processing transition at index {trans_idx}: {str(e)}")
    
    # If no missing summaries found, return original history
    if not missing_summaries:
        debug_print("No missing summaries found")
        return conversation_history
    
    debug_print(f"Found {len(missing_summaries)} location transitions missing summaries")
    
    # Process missing summaries in reverse order to maintain indices
    for summary_info in reversed(missing_summaries):
        try:
            location_name = summary_info["location_name"]
            messages = summary_info["messages"]
            transition_index = summary_info["transition_index"]
            prev_boundary = summary_info["prev_boundary"]
            
            debug_print(f"Generating summary for {location_name}")
            
            # Generate the summary
            summary = generate_location_summary(location_name, messages)
            
            if summary:
                # Find where this location content ends (the next transition FROM this location)
                location_end_boundary = None
                for j in range(transition_index + 1, len(conversation_history)):
                    check_msg = conversation_history[j]
                    if (check_msg.get("role") == "user" and "Location transition:" in check_msg.get("content", "")):
                        # Check if this transition is FROM our current location
                        trans_content = check_msg.get("content", "")
                        if f"{location_name} (" in trans_content or trans_content.startswith(f"Location transition: {location_name} to"):
                            location_end_boundary = j
                            break
                
                # If no end boundary found, this location goes to the end
                if location_end_boundary is None:
                    location_end_boundary = len(conversation_history)
                
                # Create new conversation history with summary
                new_history = []
                
                # Keep everything up to and including the transition
                for j in range(0, transition_index + 1):
                    new_history.append(conversation_history[j])
                
                # Insert the summary (replacing the content between transition and next boundary)
                summary_message = {
                    "role": "assistant",
                    "content": f"=== LOCATION SUMMARY ===\n\n{location_name}:\n{'-' * len(location_name + ':')}\n{summary}"
                }
                new_history.append(summary_message)
                
                # Add everything from the location end boundary onwards
                for j in range(location_end_boundary, len(conversation_history)):
                    new_history.append(conversation_history[j])
                
                # Update conversation history for next iteration
                conversation_history = new_history
                
                debug_print(f"Successfully added summary for {location_name}")
                
                # Also update journal
                try:
                    # Create a mock conversation history for journal entry generation
                    mock_history = []
                    if prev_boundary >= 0:
                        # Include system messages if any
                        for j in range(0, prev_boundary + 1):
                            if conversation_history[j].get("role") == "system":
                                mock_history.append(conversation_history[j])
                    mock_history.extend(messages)
                    
                    enhanced_summary = generate_enhanced_adventure_summary(
                        mock_history,
                        party_tracker_data,
                        location_name
                    )
                    if enhanced_summary:
                        update_journal_with_summary(
                            enhanced_summary,
                            party_tracker_data,
                            location_name
                        )
                except Exception as e:
                    debug_print(f"Failed to update journal: {str(e)}")
                    
            else:
                debug_print(f"Failed to generate summary for {location_name}")
                
        except Exception as e:
            debug_print(f"Error processing missing summary: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Consolidated summary of location compression scan
    debug_print(f"Location compression scan complete: {len(transitions)} transitions checked, {already_summarized_count} already summarized, {len(missing_summaries)} new summaries added")
    return conversation_history