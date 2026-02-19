#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
AI-powered initiative tracker that analyzes combat conversation to determine who has acted.
Used to enhance the combat state display with live turn tracking.
"""

import json
import re
import os
from openai import OpenAI
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T046", "core/managers/initiative_tracker_ai.py", 172)
from config import OPENAI_API_KEY, DM_MAIN_MODEL
import logging

logger = logging.getLogger(__name__)

# Load initiative tracker prompt from file (compressed version)
INITIATIVE_TRACKER_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../../prompts/initiative_tracker_compressed.txt")

try:
    with open(INITIATIVE_TRACKER_PROMPT_PATH, 'r', encoding='utf-8') as f:
        INITIATIVE_TRACKER_PROMPT = f.read()
    logger.debug(f"Loaded compressed initiative tracker prompt from {INITIATIVE_TRACKER_PROMPT_PATH}")
except FileNotFoundError:
    logger.error(f"Initiative tracker prompt file not found at {INITIATIVE_TRACKER_PROMPT_PATH}")
    raise FileNotFoundError(f"Required prompt file missing: {INITIATIVE_TRACKER_PROMPT_PATH}")

def extract_recent_combat_messages(conversation, current_round):
    """Extract messages relevant to the current and previous round."""
    # Filter out system messages
    non_system_messages = [msg for msg in conversation if msg["role"] != "system"]
    
    # Look for round markers
    round_markers = []
    for i, msg in enumerate(conversation):
        if msg["role"] == "system":
            continue
            
        content = msg["content"]
        
        # Look for round markers in user messages (combat state)
        if msg["role"] == "user" and "Round:" in content:
            match = re.search(r"Round:\s*(\d+)", content)
            if match:
                round_num = int(match.group(1))
                round_markers.append({"index": i, "round": round_num})
        
        # Look for round markers in assistant messages
        elif msg["role"] == "assistant":
            json_match = re.search(r'"combat_round"\s*:\s*(\d+)', content)
            if json_match:
                round_num = int(json_match.group(1))
                round_markers.append({"index": i, "round": round_num})
    
    # Find messages for current and previous round
    previous_round = current_round - 1 if current_round > 1 else 1
    start_idx = 0
    
    # Find the start of the previous round
    for marker in round_markers:
        if marker["round"] == previous_round:
            start_idx = marker["index"]
            break
    
    # Extract relevant messages
    relevant_messages = []
    for i in range(start_idx, len(conversation)):
        if conversation[i]["role"] != "system":
            relevant_messages.append(conversation[i])
    
    return relevant_messages[-6:]  # Limit to last 6 messages - enough for current round context

def create_initiative_prompt(messages, creatures, current_round):
    """Create prompt for AI to analyze initiative."""
    
    # Find the player character
    player_character = next((c for c in creatures if c.get("type") == "player"), None)
    player_name = player_character.get("name", "Unknown") if player_character else "Unknown"
    
    # Format initiative order WITHOUT role tags - clean names only
    initiative_order = []
    for creature in sorted(creatures, key=lambda x: x.get("initiative", 0), reverse=True):
        name = creature.get("name", "Unknown")
        init_value = creature.get("initiative", 0)
        status = creature.get("status", "alive")
        # Clean format - no (player) or other role tags
        initiative_order.append(f"- {name} ({init_value}) - {status}")
    
    # Format conversation
    conversation_text = ""
    for msg in messages:
        role = "Player" if msg["role"] == "user" else "DM"
        conversation_text += f"\n{role}: {msg['content']}\n"
    
    # Debug logging
    logger.debug(f"Initiative AI analyzing Round {current_round}")
    logger.debug(f"Player identified as: {player_name}")
    logger.debug(f"Number of messages: {len(messages)}")
    if messages:
        logger.debug(f"Last message role: {messages[-1]['role']}")
        logger.debug(f"Last message preview: {messages[-1]['content'][:200]}...")
    
    # Return data in the format the compressed prompt expects
    # NO formatting instructions - let the prompt handle everything
    prompt = f"""--- ROUND INFO ---
combat_round: {current_round}
player_name: {player_name}

INITIATIVE ORDER:
{chr(10).join(initiative_order)}

--- RECENT COMBAT CONVERSATION ---
{conversation_text}"""
    
    return prompt

def generate_live_initiative_tracker(encounter_data, conversation_history, current_round=None):
    """
    Generate a live initiative tracker showing who has acted in the current round.
    
    Args:
        encounter_data: The encounter data with creatures list
        conversation_history: Recent combat conversation messages
        current_round: The current combat round (optional, will use encounter data if not provided)
    
    Returns:
        str: Formatted initiative tracker or None if generation fails
    """
    try:
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured, cannot generate initiative tracker")
            return None
        
        # Get current round
        if current_round is None:
            current_round = encounter_data.get("current_round", encounter_data.get("combat_round", 1))
        
        # Get creatures from encounter
        creatures = encounter_data.get("creatures", [])
        if not creatures:
            logger.warning("No creatures found in encounter data")
            return None
        
        # Extract relevant messages
        relevant_messages = extract_recent_combat_messages(conversation_history, current_round)
        if not relevant_messages:
            logger.warning("No relevant combat messages found")
            return None
        
        # Create prompt
        prompt = create_initiative_prompt(relevant_messages, creatures, current_round)
        
        # Prepare messages for API
        api_messages = [
            {"role": "system", "content": INITIATIVE_TRACKER_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        # Export initiative tracker messages for debugging (same pattern as combat/validation)
        with open("debug/api_captures/initiative_messages_to_api.json", "w", encoding="utf-8") as f:
            json.dump(api_messages, f, indent=2, ensure_ascii=False)
        print(f"DEBUG: [INITIATIVE] Exported messages to debug/api_captures/initiative_messages_to_api.json")
        
        # Query AI model
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = capture_and_fanout("T046", client.chat.completions.create, messages=api_messages, model=DM_MAIN_MODEL, temperature=0.1)
        
        # Extract the tracker from response
        tracker_text = response.choices[0].message.content
        
        # Append the assistant's response to the debug file
        try:
            # Read the existing debug file
            with open("debug/api_captures/initiative_messages_to_api.json", "r", encoding="utf-8") as f:
                debug_data = json.load(f)
            
            # Add the assistant's response
            debug_data.append({
                "role": "assistant",
                "content": tracker_text
            })
            
            # Write back the complete conversation including response
            with open("debug/api_captures/initiative_messages_to_api.json", "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
            print(f"DEBUG: [INITIATIVE] Added assistant response to debug/api_captures/initiative_messages_to_api.json")
            
        except Exception as e:
            logger.error(f"Failed to append initiative response: {e}")
        
        # The compressed prompt returns the tracker with instruction blocks
        # Just return the full response as it includes important turn window info
        if "**Live Initiative Tracker:**" in tracker_text:
            # Return the full tracker output including instruction blocks
            # The combat sim needs the instruction blocks to know what to process
            return tracker_text.strip()
        else:
            logger.warning("AI response did not contain properly formatted tracker")
            return None
            
    except Exception as e:
        logger.error(f"Error generating live initiative tracker: {e}")
        return None

def format_fallback_initiative(creatures, current_round):
    """
    Create a fallback initiative display if AI generation fails.
    
    Args:
        creatures: List of creatures from encounter data
        current_round: Current combat round
        
    Returns:
        str: Formatted initiative order
    """
    lines = [f"Round: {current_round}", "Initiative Order:"]
    
    # Sort by initiative
    sorted_creatures = sorted(creatures, key=lambda x: x.get("initiative", 0), reverse=True)
    
    # Format each creature
    creature_strs = []
    for creature in sorted_creatures:
        name = creature.get("name", "Unknown")
        init = creature.get("initiative", 0)
        status = creature.get("status", "alive")
        creature_strs.append(f"{name} ({init}, {status})")
    
    lines.append(" -> ".join(creature_strs))
    return "\n".join(lines)