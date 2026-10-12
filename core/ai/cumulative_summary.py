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
from core.ai import history_markers as hm
import json
import os
import re
from datetime import datetime
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T018", "core/ai/cumulative_summary.py", 171)
register_callsite("T019", "core/ai/cumulative_summary.py", 299)

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass
from utils.module_path_manager import ModulePathManager
from utils.encoding_utils import sanitize_text, safe_json_load, safe_json_dump
from core.managers.status_manager import status_generating_summary
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
    summary_entry = hm.marker(
        "assistant",
        "=== LOCATION SUMMARY ===\n\n%s:\n%s\n%s"
        % (
            leaving_location_name,
            "-" * len(leaving_location_name + ":"),
            summary,
        ),
        hm.LOCATION_SUMMARY,
        message_id=summary_message_id,
    )
    if (
        source_index < len(conversation_history)
        and hm.same_message(conversation_history[source_index], summary_entry)
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
