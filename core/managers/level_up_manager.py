# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Level Up Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

#!/usr/bin/env python3
# ============================================================================
# LEVEL_UP_MANAGER.PY - AI-DRIVEN CHARACTER PROGRESSION
# ============================================================================
#
# ARCHITECTURE ROLE: Game Systems Layer - Character Progression Management
#
# This module provides AI-guided character advancement with complete 5th edition
# rule compliance, operating in isolated subprocess execution to prevent game
# state corruption during the level-up process.
#
# KEY RESPONSIBILITIES:
# - Interactive AI-driven level-up interview process for players
# - Automated optimized advancement choices for NPCs
# - 5th edition of the world's most popular roleplaying game rule compliance validation and verification
# - Isolated subprocess execution for fault tolerance
# - Character advancement state management without direct I/O
# - Integration with main game loop through summary reports
# - Atomic character update operations with rollback capability
#

"""
Level Up Manager Module for NeverEndingQuest

Handles character level up process as a separate, focused conversation.
This module is fully agentic, conducting an interactive interview with the player,
and is designed to be driven by an external UI loop.

Features:
- Manages level-up conversation state without direct I/O.
- AI-driven interview process for players.
- Automatic, optimized choices for NPCs.
- 5e rules compliance with validation.
- Returns a final summary to the main game upon completion.
"""

import json
import os
import sys
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T047", "core/managers/level_up_manager.py", 212)
register_callsite("T048", "core/managers/level_up_manager.py", 253)
from utils.file_operations import safe_read_json
from updates.update_character_info import update_character_info, normalize_character_name
from utils.encoding_utils import safe_json_dump
from utils.module_path_manager import ModulePathManager

# Token tracking import
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except ImportError:
    USAGE_TRACKING_AVAILABLE = False

# --- Class-based Level Up Manager ---

class LevelUpSession:
    """Manages the state of a single level-up session."""

    def __init__(self, character_name, current_level, new_level):
        self.character_name = character_name
        self.current_level = current_level
        self.new_level = new_level
        self.conversation = []
        self.is_player = True
        self.character_data = None
        self.is_complete = False
        self.summary = ""
        self.success = False
        self.conversation_file = "modules/conversation_history/level_up_conversation.json"

    def start(self):
        """
        Initializes the session and returns the first AI message.
        Returns:
            str: The initial greeting/prompt from the AI.
        """
        print(f"[Level Up Session] Starting for {self.character_name}")
        # Load character data
        party_tracker = safe_read_json("party_tracker.json")
        module_name = party_tracker.get("module", "").replace(" ", "_")
        path_manager = ModulePathManager(module_name)
        char_file = path_manager.get_character_path(normalize_character_name(self.character_name))
        self.character_data = safe_read_json(char_file)

        if not self.character_data:
            self.is_complete = True
            self.success = False
            self.summary = f"Error: Could not load character data for {self.character_name}."
            return self.summary

        self.is_player = self.character_data.get('character_type', 'player').lower() == 'player'
        
        # Initialize conversation
        self._initialize_conversation()

        # Get the first AI response
        ai_response = self._get_ai_response()
        self.conversation.append({"role": "assistant", "content": ai_response})
        
        # Save state after the first turn
        self._save_conversation()

        return ai_response

    def handle_input(self, user_input):
        """
        Processes user input and returns the next AI response.
        Returns:
            str: The next AI prompt or the final confirmation message.
        """
        if self.is_complete:
            return "The level up process is already complete."

        # Add user input to conversation
        self.conversation.append({"role": "user", "content": user_input})

        # Get the next AI response
        ai_response = self._get_ai_response()
        self.conversation.append({"role": "assistant", "content": ai_response})

        # Check if the AI has concluded the interview
        update_params = self._extract_update_action(ai_response)
        if update_params:
            print("[Level Up Session] AI returned final action. Validating...")
            is_valid, validation_msg = self._validate_level_up_response(ai_response)

            if is_valid:
                changes = update_params.get("changes", "{}")
                
                # Strip experience_points from level-up changes to prevent XP bug
                try:
                    import json
                    changes_dict = json.loads(changes)
                    if "experience_points" in changes_dict:
                        print(f"[Level Up Session] Removing experience_points from level-up changes")
                        del changes_dict["experience_points"]
                        changes = json.dumps(changes_dict)
                except:
                    pass  # If parsing fails, just pass through original
                
                if update_character_info(self.character_name, changes):
                    print(f"[Level Up Session] SUCCESS! {self.character_name} updated.")
                    self.is_complete = True
                    self.success = True
                    self.summary = self._generate_level_up_summary(ai_response)
                    # Return the full AI response so the main DM can generate proper narration
                    return ai_response
                else:
                    self.is_complete = True
                    self.success = False
                    self.summary = "Error: The final character update failed to apply."
                    return self.summary
            else:
                # If validation fails, tell the AI to fix it
                correction_prompt = f"That final JSON was not valid. Reason: {validation_msg}. Please correct the JSON and provide it again, containing ALL the level up changes."
                self.conversation.append({"role": "user", "content": correction_prompt})
                # Get the corrected response from the AI
                corrected_response = self._get_ai_response()
                self.conversation.append({"role": "assistant", "content": corrected_response})
                # Save state and return the corrected response for the UI
                self._save_conversation()
                return corrected_response

        # Save state and return the AI's next question
        self._save_conversation()
        return ai_response

    def _initialize_conversation(self):
        level_up_prompt, _, leveling_info = self._load_system_prompts()
        self.conversation = [
            {"role": "system", "content": level_up_prompt},
            {"role": "system", "content": f"LEVELING INFORMATION (Reference):\n{leveling_info}"},
            {"role": "system", "content": f"Current Character Data:\n{json.dumps(self.character_data, indent=2)}"},
            {"role": "user", "content": f"Begin the interactive level-up interview for {self.character_name}, who is advancing from level {self.current_level} to level {self.new_level}."}
        ]

    def _save_conversation(self):
        """Saves the current state of the level-up conversation to its file."""
        safe_json_dump(self.conversation, self.conversation_file)

    def _get_ai_response(self):
        try:
            # Select model config per provider
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                conv_config = config.LEVELUP_CONV_GPT52_NONE
            elif MODEL_PROVIDER == "gemini":
                conv_config = config.LEVELUP_CONV_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                conv_config = config.LEVELUP_CONV_LMSTUDIO
            else:  # legacy
                conv_config = config.LEVELUP_CONV_LEGACY

            response = capture_and_fanout("T047", api_client.create_completion,
                messages=self.conversation,
                model=conv_config["model"],
                temperature=0.7,
                **{k: v for k, v in conv_config.items() if k != "model"})

            # Track token usage with context for telemetry
            if USAGE_TRACKING_AVAILABLE:
                try:
                    from utils.openai_usage_tracker import get_global_tracker
                    tracker = get_global_tracker()
                    tracker.track(response, context={'endpoint': 'level_up', 'purpose': 'level_up_processing', 'character': self.character_name})
                except:
                    pass

            return response.choices[0].message.content
        except Exception as e:
            print(f"[ERROR] Getting AI response: {e}")
            return "I'm having trouble processing that. Could you clarify your choice?"

    def _validate_level_up_response(self, ai_response):
        _, validation_prompt, leveling_info = self._load_system_prompts()
        validation_messages = [
            {"role": "system", "content": validation_prompt},
            {"role": "system", "content": f"CURRENT CHARACTER DATA:\n{json.dumps(self.character_data, indent=2)}"},
            {"role": "system", "content": f"LEVELING INFORMATION (Reference):\n{leveling_info}"},
            {"role": "user", "content": f"Validate this final level up action JSON. Is it a valid, complete, and rules-compliant update?\n\n{ai_response}"}
        ]
        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            val_config = config.LEVELUP_VAL_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            val_config = config.LEVELUP_VAL_GEMINI_PRO_LOW
        elif MODEL_PROVIDER == "lmstudio":
            val_config = config.LEVELUP_VAL_LMSTUDIO
        else:  # legacy
            val_config = config.LEVELUP_VAL_LEGACY

        # Use a separate call to the validation model
        try:
            response = capture_and_fanout("T048", api_client.create_completion,
                messages=validation_messages,
                model=val_config["model"],
                temperature=0.2,
                **{k: v for k, v in val_config.items() if k != "model"})
            
            # Track token usage with context for telemetry
            if USAGE_TRACKING_AVAILABLE:
                try:
                    from utils.openai_usage_tracker import get_global_tracker
                    tracker = get_global_tracker()
                    tracker.track(response, context={'endpoint': 'level_up', 'purpose': 'level_up_processing', 'character': self.character_name})
                except:
                    pass
            
            validation_response = response.choices[0].message.content
            if validation_response and "VALID" in validation_response.upper():
                return True, validation_response
            else:
                return False, validation_response
        except Exception as e:
            print(f"[ERROR] Validating AI response: {e}")
            return False, "Validation system error."


    @staticmethod
    def _extract_update_action(ai_response):
        try:
            if not (ai_response.strip().startswith('{') and ai_response.strip().endswith('}')):
                return None
            response_data = json.loads(ai_response)
            actions = response_data.get("actions", [])
            for action in actions:
                if action.get("action") == "updateCharacterInfo":
                    return action.get("parameters", {})
        except (json.JSONDecodeError, AttributeError):
            return None
        return None

    @staticmethod
    def _generate_level_up_summary(final_ai_response):
        try:
            response_data = json.loads(final_ai_response)
            narration = response_data.get("narration", "Level up complete.")
            return f"Level Up: {narration}"
        except (json.JSONDecodeError, AttributeError):
            return "Level Up: The character has grown stronger and gained new abilities."

    @staticmethod
    def _load_system_prompts():
        # Get project root from the current manager location
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '..', '..')
        
        with open(os.path.join(project_root, "prompts/leveling/level_up_system_prompt.txt"), "r") as f:
            level_up_prompt = f.read()
        with open(os.path.join(project_root, "prompts/leveling/leveling_validation_prompt.txt"), "r") as f:
            validation_prompt = f.read()
        with open(os.path.join(project_root, "prompts/leveling/leveling_info.txt"), "r") as f:
            leveling_info = f.read()
        return level_up_prompt, validation_prompt, leveling_info