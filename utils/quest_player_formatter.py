#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Quest Player Formatter Module
Uses AI to convert DM-oriented quest descriptions into immersive player-friendly journal entries
"""

import json
import os
from datetime import datetime
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T090", "utils/quest_player_formatter.py", 92)
from utils.module_path_manager import ModulePathManager
from utils.file_operations import safe_read_json, safe_write_json
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.encoding_utils import sanitize_text

# Set script name for logging
set_script_name("quest_player_formatter")

# Constants
TEMPERATURE = 0.3
MAX_RETRIES = 3

SYSTEM_PROMPT = """You are a quest journal formatter for a fantasy RPG. Your task is to convert DM-oriented quest descriptions into immersive, player-friendly journal entries.

CRITICAL RULES:
1. Remove ALL location IDs in parentheses (e.g., MRV001, ARL001, DC001)
2. Remove ALL meta-game language like "introduces NPCs", "sets the stage", "this quest", "plot point"
3. Write from the player's perspective using "you" instead of "the party"
4. Focus on what the player needs to DO, not module structure
5. Keep the mystery, atmosphere, and fantasy feel
6. Make it sound like a quest journal entry, not a module description
7. Preserve important details like NPC names, locations, and objectives
8. Keep descriptions concise but flavorful (1-3 sentences ideal)
9. Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols. Use straight quotes and double hyphens instead.

FORMATTING GUIDELINES:
- Main quests: Clear objective + atmospheric context
- Side quests: Brief, intriguing hooks
- Completed quests: Past tense summary of what was accomplished
- In-progress quests: Present tense, current situation

OUTPUT FORMAT:
Return ONLY a JSON object with quest IDs as keys and reformatted descriptions as values.
Do not include any markdown formatting or code blocks.

Example input: "The party arrives at Marrow's Rest Village (MRV001), shrouded in dense mist. This sets the stage for the adventure."
Example output: {"description": "You find yourself in the mist-shrouded village of Marrow's Rest, where an unsettling quiet hangs in the air."}"""


def format_quest_batch(quests_to_format):
    """
    Send a batch of quests to AI for reformatting
    
    Args:
        quests_to_format (dict): Dictionary of quest data to format
        
    Returns:
        dict: Reformatted descriptions or None on failure
    """
    try:
        # Prepare the quest data for AI
        quest_input = {}
        for quest_id, quest_data in quests_to_format.items():
            quest_input[quest_id] = {
                'title': quest_data.get('title', ''),
                'description': quest_data.get('description', ''),
                'status': quest_data.get('status', 'not started')
            }
        
        user_prompt = f"Reformat these quest descriptions into player-friendly journal entries:\n\n{json.dumps(quest_input, indent=2)}"
        
        debug(f"AI_REQUEST: Sending {len(quest_input)} quests for reformatting", category="quest_formatting")

        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
        elif MODEL_PROVIDER == "gemini":
            mini_cfg = config.MINI_UTIL_GEMINI_FLASH_MINIMAL
        elif MODEL_PROVIDER == "lmstudio":
            mini_cfg = config.MINI_UTIL_LMSTUDIO
        else:  # legacy
            mini_cfg = config.MINI_UTIL_LEGACY

        response = capture_and_fanout("T090", api_client.create_completion,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            model=mini_cfg["model"],
            temperature=TEMPERATURE,
            **{k: v for k, v in mini_cfg.items() if k != "model"})
        
        ai_response = response.choices[0].message.content.strip()
        
        # Parse the response
        try:
            # Remove any markdown code blocks if present
            if ai_response.startswith("```"):
                ai_response = ai_response.split("```")[1]
                if ai_response.startswith("json"):
                    ai_response = ai_response[4:]
            
            reformatted = json.loads(ai_response)
            info(f"SUCCESS: Reformatted {len(reformatted)} quest descriptions", category="quest_formatting")
            return reformatted
            
        except json.JSONDecodeError as e:
            error(f"FAILURE: AI response was not valid JSON: {e}", category="quest_formatting")
            debug(f"AI_RESPONSE: {ai_response}", category="quest_formatting")
            return None
            
    except Exception as e:
        error(f"FAILURE: Error calling AI for quest formatting", exception=e, category="quest_formatting")
        return None


def format_quests_for_player(module_name):
    """
    Main function to format all active/completed quests for a module
    
    Args:
        module_name (str): Name of the module
        
    Returns:
        bool: Success or failure
    """
    try:
        info(f"STATE_CHANGE: Starting quest formatting for module {module_name}", category="quest_formatting")
        
        # Load the module plot data
        path_manager = ModulePathManager(module_name)
        plot_path = path_manager.get_plot_path()
        
        plot_data = safe_read_json(plot_path)
        if not plot_data:
            error(f"FAILURE: Could not load plot data for {module_name}", category="quest_formatting")
            return False
        
        # Prepare the player quest structure
        player_quests = {
            "module": module_name,
            "lastUpdated": datetime.now().isoformat(),
            "quests": {}
        }
        
        # Collect all quests that need formatting (not "not started")
        quests_to_format = {}
        
        # Process main plot points
        for plot_point in plot_data.get('plotPoints', []):
            if plot_point.get('status') != 'not started':
                quest_id = plot_point.get('id')
                quests_to_format[quest_id] = plot_point
                
                # Also get side quests for this plot point
                for side_quest in plot_point.get('sideQuests', []):
                    if side_quest.get('status') != 'not started':
                        sq_id = side_quest.get('id')
                        quests_to_format[sq_id] = side_quest
        
        if not quests_to_format:
            debug("No active or completed quests to format", category="quest_formatting")
            # Still save an empty player quests file
            player_quests_path = os.path.join(path_manager.module_dir, f"player_quests_{module_name}.json")
            return safe_write_json(player_quests_path, player_quests)
        
        debug(f"Found {len(quests_to_format)} quests to format", category="quest_formatting")
        
        # Send to AI for reformatting in batches (to handle large modules)
        batch_size = 10
        all_reformatted = {}
        
        quest_ids = list(quests_to_format.keys())
        for i in range(0, len(quest_ids), batch_size):
            batch_ids = quest_ids[i:i + batch_size]
            batch_quests = {qid: quests_to_format[qid] for qid in batch_ids}
            
            for attempt in range(MAX_RETRIES):
                reformatted = format_quest_batch(batch_quests)
                if reformatted:
                    all_reformatted.update(reformatted)
                    break
                elif attempt < MAX_RETRIES - 1:
                    warning(f"RETRY: Attempt {attempt + 1} failed, retrying...", category="quest_formatting")
            else:
                error(f"FAILURE: Could not reformat batch after {MAX_RETRIES} attempts", category="quest_formatting")
                # Use original descriptions as fallback
                for qid in batch_ids:
                    all_reformatted[qid] = quests_to_format[qid].get('description', '')
        
        # Build the final player quests structure
        for plot_point in plot_data.get('plotPoints', []):
            quest_id = plot_point.get('id')
            if quest_id in all_reformatted:
                player_quest = {
                    "id": quest_id,
                    "title": sanitize_text(plot_point.get('title', '')),
                    "playerDescription": sanitize_text(all_reformatted.get(quest_id, plot_point.get('description', ''))),
                    "originalDescription": sanitize_text(plot_point.get('description', '')),
                    "status": plot_point.get('status', 'not started'),
                    "type": "main",
                    "sideQuests": {}
                }
                
                # Add side quests
                for side_quest in plot_point.get('sideQuests', []):
                    sq_id = side_quest.get('id')
                    if sq_id in all_reformatted:
                        player_quest["sideQuests"][sq_id] = {
                            "id": sq_id,
                            "title": sanitize_text(side_quest.get('title', '')),
                            "playerDescription": sanitize_text(all_reformatted.get(sq_id, side_quest.get('description', ''))),
                            "status": side_quest.get('status', 'not started'),
                            "type": "side"
                        }
                
                player_quests["quests"][quest_id] = player_quest
        
        # Ensure the module directory exists (for non-standard game folders)
        os.makedirs(path_manager.module_dir, exist_ok=True)
        
        # Save the player quests file
        player_quests_path = os.path.join(path_manager.module_dir, f"player_quests_{module_name}.json")
        
        if safe_write_json(player_quests_path, player_quests):
            info(f"SUCCESS: Saved player-friendly quests to {player_quests_path}", category="quest_formatting")
            return True
        else:
            error(f"FAILURE: Could not save player quests file", category="quest_formatting")
            return False
            
    except Exception as e:
        error(f"FAILURE: Unexpected error in format_quests_for_player", exception=e, category="quest_formatting")
        return False


# For testing
if __name__ == "__main__":
    # Test with current module
    try:
        party_data = safe_read_json("party_tracker.json")
        if party_data and party_data.get("module"):
            module = party_data["module"]
            print(f"Testing quest formatter with module: {module}")
            success = format_quests_for_player(module)
            print(f"Result: {'Success' if success else 'Failed'}")
        else:
            print("No active module found in party_tracker.json")
    except Exception as e:
        print(f"Test failed: {e}")