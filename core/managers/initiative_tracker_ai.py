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
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T046", "core/managers/initiative_tracker_ai.py", 461)
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


_INSTRUCTION_HEADERS = (
    ">>> PROCESS ALL OF THESE IN ONE RESPONSE (Initiative Order):",
    ">>> CURRENT:",
    ">>> PROCESS TO END ROUND:",
    ">>> ROUND COMPLETE",
)


def _normalize_ai_tracker_pointer(tracker_text, creatures):
    """Repair one missing current-turn marker from an exact instruction block.

    The compressed prompt's process-window examples historically used
    ``[ ]`` on the first actor even though the strict runtime contract requires
    ``[>]``. The instruction list is already authoritative, so this narrow
    normalization aligns that marker without accepting an incomplete window.
    """
    if not isinstance(tracker_text, str) or "[>]" in tracker_text:
        return tracker_text

    target = None
    for header in (
        ">>> PROCESS ALL OF THESE IN ONE RESPONSE (Initiative Order):",
        ">>> PROCESS TO END ROUND:",
    ):
        header_index = tracker_text.find(header)
        if header_index < 0:
            continue
        instruction_text = tracker_text[header_index + len(header):]
        for creature in sorted(
            creatures,
            key=lambda item: item.get("initiative", 0),
            reverse=True,
        ):
            instruction_line = (
                f"- {creature.get('name', 'Unknown')} "
                f"({creature.get('initiative', 0)})"
            )
            line_index = instruction_text.find(instruction_line)
            if line_index >= 0 and (target is None or line_index < target[0]):
                target = (line_index, creature)
        break

    if target is None and ">>> CURRENT:" in tracker_text:
        target_creature = _player_character(creatures)
    else:
        target_creature = target[1] if target is not None else None

    if target_creature is None:
        return tracker_text

    name = target_creature.get("name", "Unknown")
    initiative = target_creature.get("initiative", 0)
    marker_pattern = re.compile(
        rf"(?m)^- \[ \] ((?:\*\*)?{re.escape(name)} "
        rf"\({re.escape(str(initiative))}\)(?:\*\*)? - .+)$"
    )
    return marker_pattern.sub(r"- [>] \1", tracker_text, count=1)


def _player_character(creatures):
    """Return the living player character required by the tracker contract."""
    return next(
        (
            creature
            for creature in creatures
            if isinstance(creature, dict)
            and creature.get("type") == "player"
            and creature.get("status", "alive").lower() not in {"dead", "defeated"}
        ),
        None,
    )


def _valid_ai_tracker(tracker_text, creatures, current_round):
    """Validate the structural T046 contract before handing output to T045."""
    if not isinstance(tracker_text, str):
        return False

    player = _player_character(creatures)
    if player is None:
        return False

    player_name = player.get("name", "")
    player_initiative = player.get("initiative", 0)
    required_sections = (
        "--- ROUND INFO ---",
        "--- LIVE TRACKER ---",
        "**Live Initiative Tracker:**",
    )
    section_positions = [tracker_text.find(section) for section in required_sections]
    if any(position < 0 for position in section_positions):
        return False
    if section_positions != sorted(section_positions):
        return False

    if not re.search(
        rf"(?m)^combat_round:\s*{re.escape(str(current_round))}\s*$",
        tracker_text,
    ):
        return False
    if not re.search(
        rf"(?m)^player_name:\s*{re.escape(player_name)}\s*$",
        tracker_text,
    ):
        return False
    if "--- CURRENT TURN ---" in tracker_text:
        return False

    instruction_counts = [tracker_text.count(header) for header in _INSTRUCTION_HEADERS]
    if sum(instruction_counts) != 1:
        return False
    instruction_start = min(
        tracker_text.find(header)
        for header, count in zip(_INSTRUCTION_HEADERS, instruction_counts)
        if count
    )

    tracker_start = tracker_text.find("**Live Initiative Tracker:**")
    tracker_section = tracker_text[tracker_start:instruction_start]
    tracker_lines = [
        line.strip()
        for line in tracker_section.splitlines()
        if line.strip().startswith("- [")
    ]
    sorted_creatures = sorted(
        creatures,
        key=lambda creature: creature.get("initiative", 0),
        reverse=True,
    )
    if len(tracker_lines) != len(sorted_creatures):
        return False

    markers = {}
    for line, creature in zip(tracker_lines, sorted_creatures):
        if "(player)" in line.lower() or "(npc)" in line.lower():
            return False
        name = creature.get("name", "Unknown")
        initiative = creature.get("initiative", 0)
        match = re.fullmatch(
            rf"- \[(X|>| |D)\] (?:\*\*)?{re.escape(name)} "
            rf"\({re.escape(str(initiative))}\)(?:\*\*)? - .+",
            line,
        )
        if not match:
            return False
        marker = match.group(1)
        markers[name] = marker
        is_dead = creature.get("status", "alive").lower() in {"dead", "defeated"}
        if is_dead != (marker == "D"):
            return False

    pointer_names = [name for name, marker in markers.items() if marker == ">"]
    player_index = sorted_creatures.index(player)
    living_before_player = [
        creature
        for creature in sorted_creatures[:player_index]
        if creature.get("status", "alive").lower() not in {"dead", "defeated"}
    ]
    living_after_player = [
        creature
        for creature in sorted_creatures[player_index + 1:]
        if creature.get("status", "alive").lower() not in {"dead", "defeated"}
    ]

    def marker_for(creature):
        return markers.get(creature.get("name", "Unknown"))

    def expected_window_lines(window_creatures):
        return [
            f"- {creature.get('name', 'Unknown')} ({creature.get('initiative', 0)})"
            for creature in window_creatures
        ]

    def instruction_window(end_line):
        end_index = tracker_text.find(end_line, instruction_start)
        if end_index < 0:
            return None
        active_header = next(
            header
            for header, count in zip(_INSTRUCTION_HEADERS, instruction_counts)
            if count
        )
        body_start = instruction_start + len(active_header)
        body_lines = [
            line.strip()
            for line in tracker_text[body_start:end_index].splitlines()
            if line.strip()
        ]
        if not body_lines or any(not line.startswith("- ") for line in body_lines):
            return None
        return body_lines

    if instruction_counts[0]:
        stop_line = f">>> THEN STOP AT: {player_name} (Player)"
        window_lines = instruction_window(stop_line)
        first_unacted_index = next(
            (
                index
                for index, creature in enumerate(living_before_player)
                if marker_for(creature) != "X"
            ),
            None,
        )
        if first_unacted_index is None:
            return False
        window_creatures = living_before_player[first_unacted_index:]
        if not window_creatures or window_lines != expected_window_lines(window_creatures):
            return False
        if [marker_for(creature) for creature in window_creatures] != (
            [">"] + [" "] * (len(window_creatures) - 1)
        ):
            return False
        if pointer_names != [window_creatures[0].get("name", "Unknown")]:
            return False
        if markers.get(player_name) != " ":
            return False
        if any(marker_for(creature) != " " for creature in living_after_player):
            return False
    elif instruction_counts[1]:
        expected_current = (
            f">>> CURRENT: {player_name} ({player_initiative}) - "
            "PLAYER TURN (await input)"
        )
        if expected_current not in tracker_text:
            return False
        if pointer_names != [player_name]:
            return False
        if any(marker_for(creature) != "X" for creature in living_before_player):
            return False
        if any(marker_for(creature) != " " for creature in living_after_player):
            return False
    elif instruction_counts[2]:
        expected_footer = (
            f">>> THEN: End Round {current_round}, Start Round {current_round + 1}"
        )
        window_lines = instruction_window(expected_footer)
        if any(marker_for(creature) != "X" for creature in living_before_player):
            return False
        if markers.get(player_name) != "X":
            return False
        first_unacted_index = next(
            (
                index
                for index, creature in enumerate(living_after_player)
                if marker_for(creature) != "X"
            ),
            None,
        )
        if first_unacted_index is None:
            return False
        window_creatures = living_after_player[first_unacted_index:]
        if not window_creatures or window_lines != expected_window_lines(window_creatures):
            return False
        if [marker_for(creature) for creature in window_creatures] != (
            [">"] + [" "] * (len(window_creatures) - 1)
        ):
            return False
        if pointer_names != [window_creatures[0].get("name", "Unknown")]:
            return False
    else:
        if "All creatures have acted. Increment combat_round." not in tracker_text:
            return False
        living_names = {
            creature.get("name", "Unknown")
            for creature in creatures
            if creature.get("status", "alive").lower() not in {"dead", "defeated"}
        }
        if any(markers.get(name) != "X" for name in living_names):
            return False
        if pointer_names:
            return False

    return True


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
        str: AI-formatted initiative tracker, or a deterministic tracker when
            AI generation is unavailable. Returns None when required encounter
            combatants are missing.
    """
    if not isinstance(encounter_data, dict):
        logger.warning("Invalid encounter data supplied to initiative tracker")
        return None

    # Get current round and combatants before entering the fallible AI path so
    # every downstream failure can use the same deterministic representation.
    if current_round is None:
        current_round = encounter_data.get("current_round", encounter_data.get("combat_round", 1))

    creatures = encounter_data.get("creatures", [])
    if not creatures:
        logger.warning("No creatures found in encounter data")
        return None

    fallback_tracker = format_fallback_initiative(creatures, current_round)

    try:
        # Extract relevant messages
        relevant_messages = extract_recent_combat_messages(conversation_history, current_round)
        if not relevant_messages:
            logger.warning("No relevant combat messages found")
            return fallback_tracker
        
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
        
        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            tracker_config = config.INIT_TRACKER_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            tracker_config = config.INIT_TRACKER_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            tracker_config = config.INIT_TRACKER_LMSTUDIO
        else:  # legacy
            tracker_config = config.INIT_TRACKER_LEGACY

        response = capture_and_fanout("T046", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=api_messages,
            model=tracker_config["model"],
            temperature=0.1,
            **{k: v for k, v in tracker_config.items() if k != "model"})
        
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
        
        tracker_text = _normalize_ai_tracker_pointer(tracker_text, creatures)

        # The compressed prompt returns the tracker with instruction blocks
        # Just return the full response as it includes important turn window info
        if _valid_ai_tracker(tracker_text, creatures, current_round):
            # Return the full tracker output including instruction blocks
            # The combat sim needs the instruction blocks to know what to process
            return tracker_text.strip()
        else:
            logger.warning("AI response did not satisfy the initiative tracker contract")
            return fallback_tracker
            
    except Exception as e:
        logger.error(f"Error generating live initiative tracker: {e}")
        return fallback_tracker

def format_fallback_initiative(creatures, current_round):
    """
    Create a fallback initiative display if AI generation fails.
    
    Args:
        creatures: List of creatures from encounter data
        current_round: Current combat round
        
    Returns:
        str | None: Conservative player-only tracker, or None when no living
            player exists
    """
    player = _player_character(creatures)
    if player is None:
        logger.warning("Cannot build deterministic tracker without a living player")
        return None

    sorted_creatures = sorted(creatures, key=lambda x: x.get("initiative", 0), reverse=True)
    player_name = player.get("name", "Unknown")
    player_initiative = player.get("initiative", 0)
    lines = [
        "--- ROUND INFO ---",
        f"combat_round: {current_round}",
        f"player_name: {player_name}",
        "",
        "--- LIVE TRACKER ---",
        "**Live Initiative Tracker:**",
    ]

    for creature in sorted_creatures:
        name = creature.get("name", "Unknown")
        init = creature.get("initiative", 0)
        status = creature.get("status", "alive").lower()
        if status in {"dead", "defeated"}:
            lines.append(f"- [D] {name} ({init}) - Dead")
        elif creature is player:
            lines.append(f"- [>] {name} ({init}) - CURRENT TURN")
        else:
            lines.append(f"- [ ] {name} ({init}) - Waiting")

    metadata = {
        "player_name": player_name,
        "process_until": player_name,
        "turn_window": [player_name],
        "resolve_submitted_player_action": True,
        "allow_npc_turns": False,
        "allow_round_advance": False,
    }
    lines.extend([
        "",
        (
            f">>> CURRENT: {player_name} ({player_initiative}) - PLAYER TURN "
            "(resolve submitted action only)"
        ),
        "",
        "--- TURN WINDOW ---",
        f"turn_window: {json.dumps([player_name])}",
        f"process_until: {player_name} (Player)",
        f"stop_after: {player_name} (Player)",
        "constraints:",
        f"- Resolve only {player_name}'s submitted action in the PLAYER ACTION section.",
        "- The player action is already submitted; do not ask for it again.",
        "- Do not process NPC or allied NPC turns.",
        "- Do not increment combat_round.",
        f"- Stop immediately after resolving {player_name}'s submitted action.",
        "",
        "```json",
        json.dumps(metadata, indent=2),
        "```",
    ])
    return "\n".join(lines)
